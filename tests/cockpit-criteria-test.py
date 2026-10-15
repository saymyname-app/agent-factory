#!/usr/bin/env python3
"""The criterion tests of the cockpit, run as CI and the regression run them
(T01R6, af-ltchro, from T01R5 af-7zhnnq and T01R4 af-u2fa7b; Spec af-2zseit,
Testing Decisions 1).

The criterion tests of the tickets of the cockpit live under
`tests/cockpit-criteria/`, where the Factory's profile declares its seams
(`config/project-descriptors/agent-factory.json`, `launch.seams`).
`bin/tdd-step` runs them one by one for the ticket that wrote them; this
file runs every one of them again, through the same harness, so that a later
change that breaks one is red in CI and on a merged result.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "fixtures" / "delivery-fixture-city" / "tests" / "harness.py"
COMMANDS = ROOT / "tests" / "cockpit-criteria" / "commands"


def criterion_tests() -> list[str]:
    """One id per test class of each criterion test file."""
    ids = []
    for path in sorted(COMMANDS.glob("*-test.py")):
        spec = importlib.util.spec_from_file_location("criterion_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name, value in vars(module).items():
            if isinstance(value, type) and issubclass(value, unittest.TestCase):
                ids.append(f"{path.relative_to(ROOT).as_posix()}::{name}")
    return ids


def run(test_id: str) -> str | None:
    """Run one criterion test class through the harness. What failed, or None."""
    with tempfile.TemporaryDirectory(prefix="cockpit-criteria-") as tmp:
        report = Path(tmp) / "report.xml"
        proc = subprocess.run(
            [sys.executable, str(HARNESS), test_id, str(report)],
            cwd=ROOT, text=True, capture_output=True, stdin=subprocess.DEVNULL,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        if proc.returncode == 0:
            return None
        return f"{test_id}: {report.read_text(encoding='utf-8') if report.exists() else proc.stderr}"


class CockpitCriteria(unittest.TestCase):
    def test_every_criterion_test_of_the_cockpit_passes(self):
        ids = criterion_tests()
        self.assertIn(
            "tests/cockpit-criteria/commands/isolated-launch-test.py::IsolatedCockpitLaunch", ids,
            "the criterion tests of the launch are not found",
        )
        # Each class launches its own products on its own ports: side by side.
        with ThreadPoolExecutor(max_workers=len(ids)) as pool:
            failed = [failure for failure in pool.map(run, ids) if failure]
        self.assertEqual([], failed)


if __name__ == "__main__":
    unittest.main()
