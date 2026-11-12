#!/usr/bin/env python3
"""Run one test file so that nothing it starts outlives it (category P, af-8cfygl).

    python3 lib/ci_test_reaper.py [--keep-status] COMMAND [ARGUMENT...]

bin/ci-run-tests and the Cockpit regression (tests/cockpit-criteria/
regression.py) run each test file through this. It becomes a child
subreaper (prctl PR_SET_CHILD_SUBREAPER): a process the test starts and
leaves behind comes back to it as its child, whatever its environment and
whatever its session. When the test has ended, any such process still alive
after a short grace is killed, named on stderr, and the test fails. A signal
that asks it to stop is passed to the test.

On 10/11/2026 a Cockpit test stopped its isolated cockpit while the cockpit
was reading the operator's language through a synthetic door that never
answers: each regression left that door alive, 23 of them up to 23 h old on
the host on 11/11, adopted by systemd --user (af-i9llwm). The cockpit
replaces the environment and the cockpit launcher opens sessions of its own,
so neither an environment mark nor a process group finds such a process;
being its subreaper does.

With --keep-status the leftovers are killed and named all the same, but
the exit status stays the command's: bin/tdd-step and bin/spec-integration
run a ticket's or a convoy's own test and regression commands through it
(af-8mjdai). Those commands come from the branch under test, whose harness
may predate this reaper: on 12/11/2026 a tdd-step tree's cockpit had polled
its synthetic city for 43 h, beside others, outside the host pool. Killing
what they leave is the Factory's; failing them is their harness's.

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
PASSED_ON = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)


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


def kill_left(grace: float = GRACE_SECONDS) -> dict[int, str]:
    """Once what this subreaper ran has ended: what it left alive after
    `grace`, killed, each pid with its command line."""
    deadline = time.monotonic() + grace
    while True:
        reap()
        left = children()
        if not left or time.monotonic() >= deadline:
            break
        time.sleep(0.1)
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
    return named


def main(argv: list[str]) -> int:
    keep_status = argv[:1] == ["--keep-status"]
    if keep_status:
        argv = argv[1:]
    if not argv:
        sys.stderr.write("usage: ci_test_reaper.py [--keep-status] COMMAND [ARGUMENT...]\n")
        return 2
    if not subreaper():
        os.execvp(argv[0], argv)
    test = subprocess.Popen(argv)
    for number in PASSED_ON:
        signal.signal(number, lambda received, _frame: test.send_signal(received))
    # Collect every child as it ends, the test's orphans among them: one left
    # uncollected stays in /proc while the test runs, and a test that waits
    # for a process it killed to be gone would wait on it (af-i9llwm).
    while True:
        pid, raw = os.waitpid(-1, 0)
        if pid == test.pid:
            status = test.returncode = os.waitstatus_to_exitcode(raw)
            break
    if status < 0:  # ended by a signal: the shell's way to say it
        status = 128 - status
    named = kill_left()
    if not named:
        return status
    sys.stderr.write(f"test reaper: {' '.join(argv)} ended and left these processes alive, now killed -- "
                     "a test stops what it starts (docs/DEFECT_CLASSES.md, P):\n"
                     + "".join(f"  {pid} {line}\n" for pid, line in named.items()))
    return status if keep_status else status or 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
