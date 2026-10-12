#!/usr/bin/env python3
"""The criterion tests of the cockpit, run as CI and the regression run them
(T01, af-oigubn; Spec af-2zseit, Testing Decisions 1).

The criterion tests of the tickets of the cockpit live under
`tests/cockpit-criteria/`, where the Factory's profile declares its seams
(`config/project-descriptors/agent-factory.json`, `launch.seams`).
`bin/tdd-step` runs them one by one for the ticket that wrote them; this
file runs every one of them again, through the same harness, so that a later
change that breaks one is red in CI and on a merged result.

One class is left out where it cannot run: it reads the Validated Prototypes
at their approved commits, which are private and exist only in the
repository of the host that delivers. It runs wherever those commits can be
read, and the answer says when it was left out.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "fixtures" / "delivery-fixture-city" / "tests" / "harness.py"
COMMANDS = ROOT / "tests" / "cockpit-criteria" / "commands"
# Test id -> the private commits it reads.
NEEDS_APPROVED_COMMITS = {
    "tests/cockpit-criteria/commands/frozen-states-test.py::ApprovedReferences": (
        "632deea09daa22d8213807ef48a79891edf1c7bf",
        "d8cb462d3287234ce5349d358899441a5796353c",
    ),
}


def criterion_tests() -> list[str]:
    """One id per test class of each criterion test file."""
    ids = []
    for path in sorted(COMMANDS.glob("*-test.py")):
        spec = importlib.util.spec_from_file_location("criterion_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        ids += [
            f"{path.relative_to(ROOT).as_posix()}::{name}"
            for name, value in vars(module).items()
            if isinstance(value, type) and issubclass(value, unittest.TestCase)
        ]
    return ids


def readable(commits: tuple[str, ...]) -> bool:
    repository = os.environ.get("PROTOTYPE_REFERENCES_REPO") or str(ROOT)
    return all(
        subprocess.run(["git", "-C", repository, "cat-file", "-e", f"{commit}^{{commit}}"],
                       capture_output=True).returncode == 0
        for commit in commits
    )


class CockpitCriteria(unittest.TestCase):
    def test_every_criterion_test_of_the_cockpit_passes(self):
        ids = criterion_tests()
        self.assertIn(
            "tests/cockpit-criteria/commands/isolated-launch-test.py::IsolatedCockpitLaunch", ids,
            "the criterion tests of the launch are not found",
        )
        failed = []
        for test_id in ids:
            if test_id in NEEDS_APPROVED_COMMITS and not readable(NEEDS_APPROVED_COMMITS[test_id]):
                print(f"left out, its approved commits cannot be read here: {test_id}", file=sys.stderr)
                continue
            with tempfile.TemporaryDirectory(prefix="cockpit-criteria-") as tmp:
                proc = subprocess.run(
                    [sys.executable, str(HARNESS), test_id, str(Path(tmp) / "report.xml")],
                    cwd=ROOT, text=True, capture_output=True, stdin=subprocess.DEVNULL,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                )
                if proc.returncode != 0:
                    report = Path(tmp) / "report.xml"
                    failed.append(f"{test_id}: {report.read_text(encoding='utf-8') if report.exists() else proc.stderr}")
        self.assertEqual([], failed)


if __name__ == "__main__":
    unittest.main()
