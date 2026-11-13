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

One limit for the heavy runs of the host (study C, docs/research/2026-10-22-
strategie-tests-budgets.md, T1; af-lsbqj9): run beside the batteries of two
authors and a merge, the same tests took 1.9 times as long (load 35 to 108
on 8 cores, 22/10/2026) and the gates refused tickets that were green. So it
takes a slot of the host pool (lib/host_slots.py) and waits its turn, at
most REGRESSION_HOST_WAIT seconds (600) -- none when its caller holds one
for it (bin/tdd-step, bin/spec-integration). Its budget, REGRESSION_BUDGET
seconds (`full_seconds` of config/test-budgets.json, at a ticket's green
too), counts from the slot obtained. Past either, it exits 75 and
says NOT RUN: the gates take that as no answer, never as a red.
Exit: 0 green, 1 red, 75 not run.
"""

from __future__ import annotations

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
    """A slot of the host pool, or None where none is taken (a GitHub
    runner, a caller's turn, a tree without lib/host_slots.py). Exits NOT
    RUN past `wait`."""
    sys.path.insert(0, str(ROOT / "lib"))
    try:
        import host_slots
    except ImportError:
        return None
    try:
        return host_slots.take(f"the regression of {ROOT}", wait,
                               say=lambda line: print(f"regression: {line}", flush=True))
    except host_slots.NotRun as exc:
        not_run(str(exc))


def files() -> list[Path]:
    found = sorted(ROOT.glob("tests/cockpit-*-test.py")) + [ROOT / name for name in ALSO]
    return [path for path in found if not LOCAL_ONLY.search(path.read_text(encoding="utf-8"))]


def run(path: Path, deadline: float) -> tuple[Path, int | None, float, str]:
    """One test file, in a session of its own: past the deadline, it and
    everything it started are killed, and its status is None. The session
    also dies with the regression, however that ends (af-8cfygl), where the
    tree has lib/bounded_process.py; a tree without it keeps the session
    alone, as budgets() keeps its defaults. Where the tree has
    lib/ci_test_reaper.py, the file runs through it: what it leaves alive
    when it ends is killed, named, and fails it (af-i9llwm: one synthetic
    door per regression, 23 alive on the host on 11/11/2026)."""
    sys.path.insert(0, str(ROOT / "lib"))
    try:
        import bounded_process
    except ImportError:
        bounded_process = None

    started = time.monotonic()
    argv = [sys.executable, str(path)]
    reaper = ROOT / "lib" / "ci_test_reaper.py"
    if reaper.is_file():
        argv = [sys.executable, str(reaper), *argv]
    options = dict(cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    proc = (bounded_process.popen(argv, **options) if bounded_process
            else subprocess.Popen(argv, start_new_session=True, **options))
    try:
        output, _ = proc.communicate(timeout=max(0.0, deadline - time.monotonic()))
        status: int | None = proc.returncode
    except subprocess.TimeoutExpired:
        if bounded_process:
            bounded_process.kill_group(proc)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
        output, _ = proc.communicate()
        status = None
    finally:
        if bounded_process:
            bounded_process.release(proc)
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
        return {"host_wait_seconds": 600, "full_seconds": 600, "alert_ratio": 0.8}
    return load(ROOT)


def main() -> int:
    known = budgets()
    # At a ticket's green bin/tdd-step names its tests and the series keeps
    # to their families (study C, T4); its run is measured as a green one.
    # It has the budget of the whole series all the same: a family is a part
    # of it, and of any size. Until 13/11/2026 a green budget of its own,
    # measured on the greens that ended within it, refused three times at
    # 1260 s the ticket of the « runs » family, 24 classes (af-hafyxx).
    kind = "green" if os.environ.get("TDD_STEP_TICKET_TESTS", "").strip() else "full"
    wait = seconds("REGRESSION_HOST_WAIT", int(known["host_wait_seconds"]))
    budget = seconds("REGRESSION_BUDGET", int(known["full_seconds"]))
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
