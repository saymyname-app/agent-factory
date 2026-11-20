"""The lock a trial holds on its work folder for as long as it lives
(category P, af-3vcqd3).

A trial (a `bin/tdd-step` check, a `bin/spec-integration` pass) runs a
branch's own commands from a folder of its own; what they launch in a
session of their own can outlive the trial when the trial is killed, its
subreaper with it. On 11/11/2026 a `bin/cockpit run` of a tdd-step tree,
handed to systemd --user, polled its synthetic city for 61 h: its folder
was still there, so nothing told the sweep that its trial was gone
(af-p4v2q2).

    with trial_lock.hold(folder):
        ...  # the trial

The trial holds an exclusive lock on `<folder>.trial` beside its folder;
the kernel releases it however the trial ends, SIGKILL included, and the
descriptor is not inherited by what the trial launches.
`bin/project-launch sweep` asks `gone(folder)` of every folder above the
work tree of a program handed to init: a lock file it can take means the
trial has ended, and the program is stopped.

A shell trial cannot hold a lock its children do not inherit: it runs

    python3 lib/trial_lock.py hold-while <folder> <pid>

which holds the lock for as long as process <pid> lives
(tests/lib/isolated-city.sh, isolated_city_hold_trial). On 20/11/2026
three test cities whose trial had ended, killed past the trap that stops
them, ran for up to 8 h 52 under systemd --user and held the host at a
load of 20 on 8 cores; six orders failed their budget (af-myowqa).
"""
from __future__ import annotations

import contextlib
import fcntl
import os
import signal
import sys
import time
from pathlib import Path
from typing import Iterator

SUFFIX = ".trial"


def lock_file(folder: Path) -> Path:
    return folder.with_name(folder.name + SUFFIX)


@contextlib.contextmanager
def hold(folder: Path) -> Iterator[None]:
    """Hold the trial lock of `folder` until the block ends."""
    path = lock_file(Path(folder))
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        with contextlib.suppress(OSError):
            path.unlink()
        os.close(descriptor)


def gone(folder: Path) -> bool:
    """Whether `folder` is the folder of a trial that has ended: its lock
    file is there and nobody holds it. A folder no trial declared is not."""
    try:
        descriptor = os.open(lock_file(Path(folder)), os.O_RDONLY | os.O_CLOEXEC)
    except OSError:
        return False
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    else:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        return True
    finally:
        os.close(descriptor)


def ended_trial(folder: Path, root: Path) -> Path | None:
    """The folder of an ended trial under `root` that `folder` lies in, if any."""
    return next((candidate for candidate in (folder, *folder.parents)
                 if root in candidate.parents and gone(candidate)), None)


def _identity(pid: int) -> str | None:
    """The start time of a live process `pid`: a pid reused later differs."""
    try:
        state, *fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    except (OSError, IndexError):
        return None
    return None if state in ("Z", "X") or len(fields) < 19 else fields[18]


def hold_while(folder: Path, owner: int, poll: float = 0.5) -> None:
    """Hold the trial lock of `folder` while process `owner` lives. The lock
    file stays when the folder outlives its owner (a trial killed before its
    cleanup), so the sweep sees an ended trial; it goes with the folder."""
    folder = Path(folder)
    identity = _identity(owner)
    path = lock_file(folder)
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        while identity is not None and _identity(owner) == identity:
            time.sleep(poll)
        if not folder.exists():
            with contextlib.suppress(OSError):
                path.unlink()
    finally:
        os.close(descriptor)


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "hold-while" or not sys.argv[3].isdigit():
        sys.exit("usage: trial_lock.py hold-while FOLDER PID")
    # It ends with its owner. A caller's deadline stops the owner's whole
    # group: stopped with it, before the owner's cleanup removed the folder,
    # it would leave its lock file behind for good.
    for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(number, signal.SIG_IGN)
    hold_while(Path(sys.argv[2]), int(sys.argv[3]))
