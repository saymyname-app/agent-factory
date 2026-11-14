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
"""
from __future__ import annotations

import contextlib
import fcntl
import os
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
