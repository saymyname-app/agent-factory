#!/usr/bin/env python3
"""Run one test file so that nothing it starts outlives it (category P, af-8cfygl).

    python3 lib/ci_test_reaper.py COMMAND [ARGUMENT...]

bin/ci-run-tests runs each test file through this. It becomes a child
subreaper (prctl PR_SET_CHILD_SUBREAPER): a process the test starts and
leaves behind comes back to it as its child, whatever its environment and
whatever its session. When the test has ended, any such process still alive
after a short grace is killed, named on stderr, and the test fails.

On 10/11/2026 a Cockpit test terminated its isolated cockpit while the
cockpit was reading the operator's language through a door that never
answers: each run left that door alive, 16 of them up to 23 h old on the
host, adopted by systemd --user, the subreaper above the battery. The
cockpit had replaced the environment and the cockpit launcher opens sessions
of its own, so neither an environment mark nor a process group finds them;
being their subreaper does.

Where prctl is not there (not Linux), the test simply runs.
"""
from __future__ import annotations

import ctypes
import os
import signal
import subprocess
import sys
import time

PR_SET_CHILD_SUBREAPER = 36
# A process the test stopped may take a moment to be gone.
GRACE_SECONDS = 3.0


def subreaper() -> bool:
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        return libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) == 0
    except (OSError, AttributeError):
        return False


def reap() -> None:
    """Collect the children that already ended."""
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0:
            return


def children() -> list[int]:
    """The live children of this process: the test's leftovers once it ended."""
    me, found = str(os.getpid()), []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat", encoding="utf-8", errors="replace") as handle:
                state, parent = handle.read().rsplit(")", 1)[1].split()[:2]
        except (OSError, ValueError):
            continue
        if parent == me and state != "Z":
            found.append(int(entry))
    return found


def command_line(pid: int) -> str:
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as handle:
            return handle.read().replace(b"\0", b" ").decode(errors="replace").strip()[:300]
    except OSError:
        return "?"


def main(argv: list[str]) -> int:
    if not argv:
        sys.stderr.write("usage: ci_test_reaper.py COMMAND [ARGUMENT...]\n")
        return 2
    if not subreaper():
        os.execvp(argv[0], argv)
    status = subprocess.call(argv)
    deadline = time.monotonic() + GRACE_SECONDS
    while True:
        reap()
        left = children()
        if not left or time.monotonic() >= deadline:
            break
        time.sleep(0.1)
    if not left:
        return status
    named: dict[int, str] = {}
    # Killing a leftover hands its own children to this process: repeat.
    while left:
        for pid in left:
            named.setdefault(pid, command_line(pid))
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        time.sleep(0.1)
        reap()
        left = children()
    sys.stderr.write("ci-run-tests: the test ended and left these processes alive, now killed -- "
                     "a test stops what it starts (docs/DEFECT_CLASSES.md, P):\n"
                     + "".join(f"  {pid} {line}\n" for pid, line in named.items()))
    return status or 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
