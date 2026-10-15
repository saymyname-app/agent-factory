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
"""

from __future__ import annotations

import re
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


def files() -> list[Path]:
    found = sorted(ROOT.glob("tests/cockpit-*-test.py")) + [ROOT / name for name in ALSO]
    return [path for path in found if not LOCAL_ONLY.search(path.read_text(encoding="utf-8"))]


def run(path: Path) -> tuple[Path, int, float, str]:
    started = time.monotonic()
    proc = subprocess.run([sys.executable, str(path)], cwd=ROOT, text=True, capture_output=True,
                          stdin=subprocess.DEVNULL)
    return path, proc.returncode, time.monotonic() - started, proc.stdout + proc.stderr


def as_repository() -> None:
    """Make the tree a repository of one commit, when it is none."""
    inside = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
    if inside.returncode == 0:
        return
    identity = ["-c", "user.name=regression", "-c", "user.email=regression@example.invalid", "-c", "commit.gpgsign=false"]
    for args in (["init", "--quiet"], ["add", "--all", "--force"], [*identity, "commit", "--quiet", "--no-verify",
                                                                        "--message", "the tree under regression"]):
        subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True)


def main() -> int:
    as_repository()
    failed = 0
    alone = [path for path in files() if path.relative_to(ROOT).as_posix() in ALONE]
    together = [path for path in files() if path not in alone]
    with ThreadPoolExecutor(max_workers=JOBS) as pool:
        for path, status, seconds, output in [*pool.map(run, together), *map(run, alone)]:
            print(f"{'PASS' if status == 0 else 'FAIL'} {path.relative_to(ROOT)} ({seconds:.0f}s)", flush=True)
            if status != 0:
                failed += 1
                print(output, flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
