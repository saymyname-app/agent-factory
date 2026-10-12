#!/usr/bin/env python3
"""Regression command of the cockpit (`launch.regression_command` of
`config/project-descriptors/agent-factory.json`; T01, af-oigubn).

    python3 tests/cockpit-criteria/regression.py

Run from the root of a clean tree, it exits 0 when green: what
`bin/tdd-step prefactoring` runs before and after a change, and
`bin/spec-integration` on each merged result. It runs the test files of the
cockpit that CI runs -- `tests/cockpit-*-test.py`, the criterion tests of
its tickets among them (`tests/cockpit-criteria-test.py`) -- and those of
the launcher and of the profile the launch goes through. A file marked
`# ci: local-only` needs the live runtime and is left out, as in CI.
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


def files() -> list[Path]:
    found = sorted(ROOT.glob("tests/cockpit-*-test.py")) + [ROOT / name for name in ALSO]
    return [path for path in found if not LOCAL_ONLY.search(path.read_text(encoding="utf-8"))]


def run(path: Path) -> tuple[Path, int, float, str]:
    started = time.monotonic()
    proc = subprocess.run([sys.executable, str(path)], cwd=ROOT, text=True, capture_output=True,
                          stdin=subprocess.DEVNULL)
    return path, proc.returncode, time.monotonic() - started, proc.stdout + proc.stderr


def main() -> int:
    failed = 0
    with ThreadPoolExecutor(max_workers=JOBS) as pool:
        for path, status, seconds, output in pool.map(run, files()):
            print(f"{'PASS' if status == 0 else 'FAIL'} {path.relative_to(ROOT)} ({seconds:.0f}s)", flush=True)
            if status != 0:
                failed += 1
                print(output, flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
