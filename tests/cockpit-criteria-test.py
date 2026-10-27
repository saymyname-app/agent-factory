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


# The measures of fidelity to the prototype (anchors and tokens, in a headless
# browser) are never blocking (ADR-0032, af-ledn95; Benjamin, 2026-10-19:
# fidelity judged by his eye). On a CI runner the browser measured nothing
# (PR #683): they run where `bin/tdd-step` and a person run them, not in CI.
FIDELITY_GLOB = "*-fidelity-test.py"
# The end-to-end test kept in every selection: it launches a real cockpit.
SMOKE = "isolated-launch-test.py"


def family(path: str) -> str:
    """The screen a criterion test file belongs to: its name up to the
    first dash (`runs-destination-job-test.py` -> `runs`)."""
    return Path(path).name.split("-", 1)[0]


def selected(paths: list[Path], ticket_tests: str) -> list[Path]:
    """At a ticket's green, `bin/tdd-step` names the ticket's own test files
    (TDD_STEP_TICKET_TESTS): only the files of their families and the
    end-to-end test run, as the tests a ticket can break are those of the
    screen it changes (study C, T4, af-npz9v1.31). Run whole on 22/10/2026
    they grew with each ticket delivered, about 9 s a class, and refused
    green tickets at 600 s. Anything else -- a merge, CI, no name -- runs
    every file: a break elsewhere is caught at the merge."""
    families = {family(name) for name in ticket_tests.split()}
    if not families:
        return paths
    return [path for path in paths if path.name == SMOKE or family(path.name) in families]


def criterion_tests() -> list[str]:
    """One id per test class of each criterion test file."""
    ids = []
    skipped = set(COMMANDS.glob(FIDELITY_GLOB)) if os.environ.get("CI") else set()
    paths = selected(sorted(set(COMMANDS.glob("*-test.py")) - skipped), os.environ.get("TDD_STEP_TICKET_TESTS", ""))
    for path in paths:
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
        # Each class launches its own products on its own ports: side by side,
        # but no more at once than the host has cores -- the classes that
        # measure in a headless browser, all started together on a CI runner
        # of two cores, measured nothing (PR #683, 2026-10-19).
        with ThreadPoolExecutor(max_workers=max(1, min(len(ids), os.cpu_count() or 1))) as pool:
            failed = [failure for failure in pool.map(run, ids) if failure]
        self.assertEqual([], failed)


if __name__ == "__main__":
    unittest.main()
