#!/usr/bin/env python3
"""Regression command of the cockpit (`launch.regression_command` of
`config/project-descriptors/agent-factory.json`; T01R4, af-u2fa7b).

    python3 tests/cockpit-criteria/regression.py

Run from the root of a clean tree, it exits 0 when green: what
`bin/tdd-step prefactoring` runs before and after a change, and
`bin/spec-integration` on each merged result. It runs the test files of the
cockpit that CI runs -- `tests/cockpit-*-test.py`, the criterion tests of
its tickets among them (`tests/cockpit-criteria-test.py`) -- and those of
the launcher and of the profile the launch goes through. A file marked
`# ci: local-only` needs the live runtime and is left out, as in CI.

A clean tree the gates give it (`bin/tdd-step` exports the commit with `git
archive`) is no repository, and the launcher's tests launch a commit of
their own tree: such a tree is first recorded as one commit of a repository
of its own, which leaves its files as they are.

One battery at a time on the host (study C, docs/research/2026-10-22-
strategie-tests-budgets.md, T1): run beside the batteries of two authors and
a merge, the same tests took 1.9 times as long (load 35 to 108 on 8 cores,
22/10/2026) and the gates refused tickets that were green. So it takes the
host lock of `bin/ci-run-tests` and waits its turn, at most
REGRESSION_HOST_WAIT seconds (600). Its budget, REGRESSION_BUDGET seconds
(600), counts from the lock obtained. Past either, it exits 75 and says NOT
RUN: the gates take that as no answer, never as a red.
Exit: 0 green, 1 red, 75 not run.
"""

from __future__ import annotations

import fcntl
import os
import re
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL_ONLY = re.compile(r"^#\s*ci:\s*local-only", re.MULTILINE)
ALSO = ("tests/project-launch-test.py", "tests/project-planning-profile-test.py")
JOBS = 4
# The criterion tests launch cockpits and a headless browser for minutes:
# run beside the others, they starve the tests that time a reading (a
# recheck answered within 3 s, a supervisor read before the sessions). They
# run alone, after the others.
ALONE = ("tests/cockpit-criteria-test.py",)
NOT_RUN = 75
# The lock of bin/ci-run-tests: CI_RUN_TESTS_HOST_LOCK_FILE names another
# one (tests only); a run started inside a battery that holds it
# (CI_RUN_TESTS_HOST_LOCK_HELD) inherits that battery's turn.
HOST_LOCK = os.environ.get("CI_RUN_TESTS_HOST_LOCK_FILE") or f"/tmp/agent-factory-ci-run-tests-{os.getuid()}.lock"


def seconds(name: str, default: int) -> int:
    value = os.environ.get(name, str(default))
    if not value.isdigit():
        print(f"regression: {name} wants a number of seconds, got: {value}", file=sys.stderr)
        sys.exit(2)
    return int(value)


def not_run(why: str) -> None:
    print(f"regression: NOT RUN -- {why}. This is not a test failure: start it again later.", flush=True)
    sys.exit(NOT_RUN)


def take_host(wait: int):
    """The host lock, or None where it is not taken. Exits NOT RUN past `wait`."""
    if os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("CI_RUN_TESTS_HOST_LOCK_HELD") == HOST_LOCK:
        return None
    handle = open(HOST_LOCK, "a")
    started, said = time.monotonic(), None
    while True:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            waited = time.monotonic() - started
            try:
                holder = Path(f"{HOST_LOCK}.holder").read_text().strip() or "another session"
            except OSError:
                holder = "another session"
            if waited >= wait:
                not_run(f"the battery of {holder} still holds the host after {waited:.0f}s (REGRESSION_HOST_WAIT={wait})")
            # Tried every second, said every 30 s.
            if said is None or waited - said >= 30:
                print(f"regression: waiting for the battery of {holder} -- one battery at a time on this host; "
                      f"waited {waited:.0f}s of at most {wait}s", flush=True)
                said = waited
            time.sleep(1)
    try:
        Path(f"{HOST_LOCK}.holder").write_text(f"{ROOT} (pid {os.getpid()}, since {time.strftime('%H:%M')}, regression)\n")
    except OSError:
        pass
    os.environ["CI_RUN_TESTS_HOST_LOCK_HELD"] = HOST_LOCK
    return handle


def files() -> list[Path]:
    found = sorted(ROOT.glob("tests/cockpit-*-test.py")) + [ROOT / name for name in ALSO]
    return [path for path in found if not LOCAL_ONLY.search(path.read_text(encoding="utf-8"))]


def run(path: Path, deadline: float) -> tuple[Path, int | None, float, str]:
    """One test file, in a session of its own: past the deadline, it and
    everything it started are killed, and its status is None."""
    started = time.monotonic()
    proc = subprocess.Popen([sys.executable, str(path)], cwd=ROOT, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True)
    try:
        output, _ = proc.communicate(timeout=max(0.0, deadline - time.monotonic()))
        status: int | None = proc.returncode
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        output, _ = proc.communicate()
        status = None
    return path, status, time.monotonic() - started, output


def as_repository() -> None:
    """Make the tree a repository of one commit, when it is none."""
    inside = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
    if inside.returncode == 0:
        return
    identity = ["-c", "user.name=regression", "-c", "user.email=regression@example.invalid", "-c", "commit.gpgsign=false"]
    for args in (["init", "--quiet"], ["add", "--all", "--force"], [*identity, "commit", "--quiet", "--no-verify",
                                                                        "--message", "the tree under regression"]):
        subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True)


def budgets() -> dict:
    """config/test-budgets.json of this tree (study C, T3), through
    lib/test_budgets.py; the defaults of 600 s where the tree has neither."""
    sys.path.insert(0, str(ROOT / "lib"))
    try:
        from test_budgets import load
    except ImportError:
        return {"host_wait_seconds": 600, "green_seconds": 600, "full_seconds": 600, "alert_ratio": 0.8}
    return load(ROOT)


def main() -> int:
    known = budgets()
    # At a ticket's green bin/tdd-step names its tests and the series keeps
    # to their families (study C, T4): the green budget; else the full one.
    kind = "green" if os.environ.get("TDD_STEP_TICKET_TESTS", "").strip() else "full"
    wait = seconds("REGRESSION_HOST_WAIT", int(known["host_wait_seconds"]))
    budget = seconds("REGRESSION_BUDGET", int(known[f"{kind}_seconds"]))
    host = take_host(wait)  # noqa: F841 -- held until the process ends
    started = time.monotonic()
    deadline = started + budget
    as_repository()
    failed, late = 0, []
    alone = [path for path in files() if path.relative_to(ROOT).as_posix() in ALONE]
    together = [path for path in files() if path not in alone]
    with ThreadPoolExecutor(max_workers=JOBS) as pool:
        results = list(pool.map(lambda path: run(path, deadline), together))
    results += [run(path, deadline) for path in alone]
    for path, status, took, output in results:
        name = path.relative_to(ROOT)
        if status is None:
            late.append(str(name))
            print(f"LATE {name} ({took:.0f}s)", flush=True)
            continue
        print(f"{'PASS' if status == 0 else 'FAIL'} {name} ({took:.0f}s)", flush=True)
        for timing in (line for line in output.splitlines() if line.startswith("regression: took ")):
            print(timing, flush=True)
        if status != 0:
            failed += 1
            print(output, flush=True)
    # The measure bin/test-budgets reads back (study C, T2/T3).
    took = time.monotonic() - started
    print(f"regression: took {took:.0f}s with the host held ({kind} budget {budget}s)", flush=True)
    if took > known["alert_ratio"] * budget:
        print(f"regression: ALERT -- {took:.0f}s is over {known['alert_ratio']:.0%} of the {kind} budget of "
              f"{budget}s: refresh config/test-budgets.json (bin/test-budgets refresh) before it runs out",
              flush=True)
    if failed:
        return 1
    if late:
        not_run(f"the budget of {budget}s (REGRESSION_BUDGET) ran out before {', '.join(late)} ended")
    return 0


if __name__ == "__main__":
    sys.exit(main())
