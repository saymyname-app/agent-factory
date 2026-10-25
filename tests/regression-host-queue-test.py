#!/usr/bin/env python3
"""The cockpit's regression command waits its turn on the host and keeps to
its budget (study C, T1: docs/research/2026-10-22-strategie-tests-budgets.md;
docs/DELIVERY.md, one battery at a time).

On 22/10/2026 it ran beside the batteries of two authors and a merge: the
same tests took 1.9 times as long and bin/tdd-step refused, at 600 s, two
tickets that were green. Each case runs a copy of
tests/cockpit-criteria/regression.py on a tree of stand-in test files and a
lock file of its own.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGRESSION = ROOT / "tests" / "cockpit-criteria" / "regression.py"
NOT_RUN = 75

# A stand-in test file: it leaves a mark, then fails or lasts when asked.
STAND_IN = """import os, subprocess, sys, time
from pathlib import Path
name = Path(__file__).name
marks = Path(os.environ["MARKS"])
(marks / (name + ".ran")).write_text("ran")
if os.environ.get("FAIL") == name:
    sys.exit(1)
if os.environ.get("SLOW") == name:
    child = subprocess.Popen(["sleep", "60"])
    (marks / "grandchild.pid").write_text(str(child.pid))
    time.sleep(60)
"""
FILES = ("tests/cockpit-a-test.py", "tests/cockpit-criteria-test.py",
         "tests/project-launch-test.py", "tests/project-planning-profile-test.py")


class RegressionHostQueue(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="regression-host-queue-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.tree, self.marks, self.lock = self.tmp / "tree", self.tmp / "marks", self.tmp / "host.lock"
        self.marks.mkdir()
        (self.tree / "tests" / "cockpit-criteria").mkdir(parents=True)
        shutil.copy(REGRESSION, self.tree / "tests" / "cockpit-criteria" / "regression.py")
        for name in FILES:
            (self.tree / name).write_text(STAND_IN)

    def regression(self, **env):
        base = {key: value for key, value in os.environ.items()
                if key not in ("GITHUB_ACTIONS", "CI_RUN_TESTS_HOST_LOCK_HELD", "REGRESSION_HOST_WAIT", "REGRESSION_BUDGET")}
        started = time.monotonic()
        proc = subprocess.run([sys.executable, "tests/cockpit-criteria/regression.py"], cwd=self.tree, text=True,
                              capture_output=True, stdin=subprocess.DEVNULL, timeout=120,
                              env={**base, "MARKS": str(self.marks), "CI_RUN_TESTS_HOST_LOCK_FILE": str(self.lock), **env})
        return proc, time.monotonic() - started

    def hold_host(self, seconds):
        """Another battery holds the host lock for `seconds`."""
        ready = self.tmp / "held"
        holder = subprocess.Popen(["flock", str(self.lock), "sh", "-c", f"touch {ready}; sleep {seconds}"])
        self.addCleanup(lambda: (holder.kill(), holder.wait()))
        deadline = time.monotonic() + 10
        while not ready.exists():
            self.assertLess(time.monotonic(), deadline, "the lock holder never started")
            time.sleep(0.05)
        return holder

    def ran(self):
        return sorted(path.name for path in self.marks.glob("*.ran"))

    def test_a_free_host_runs_every_file_and_is_green(self):
        proc, _ = self.regression()
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual(sorted(Path(name).name + ".ran" for name in FILES), self.ran())
        self.assertIn("PASS tests/cockpit-criteria-test.py", proc.stdout)

    def test_a_host_held_past_the_wait_is_not_run_and_no_test_runs(self):
        self.hold_host(30)
        proc, took = self.regression(REGRESSION_HOST_WAIT="1")
        self.assertEqual(NOT_RUN, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("NOT RUN", proc.stdout)
        self.assertIn("not a test failure", proc.stdout)
        self.assertEqual([], self.ran())
        self.assertLess(took, 20)

    def test_it_waits_for_the_battery_that_holds_the_host_then_runs(self):
        self.hold_host(2)
        proc, took = self.regression(REGRESSION_HOST_WAIT="30")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("waiting for the battery", proc.stdout)
        self.assertEqual(len(FILES), len(self.ran()))

    def test_the_budget_counts_from_the_lock_and_a_spent_budget_is_not_run_with_nothing_left_running(self):
        self.hold_host(2)
        proc, took = self.regression(REGRESSION_HOST_WAIT="30", REGRESSION_BUDGET="3", SLOW="cockpit-criteria-test.py")
        self.assertEqual(NOT_RUN, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("LATE tests/cockpit-criteria-test.py", proc.stdout)
        self.assertIn("REGRESSION_BUDGET", proc.stdout)
        # The other files ran in the budget, which began once the lock was held.
        self.assertIn("PASS tests/cockpit-a-test.py", proc.stdout)
        self.assertLess(took, 30)
        grandchild = int((self.marks / "grandchild.pid").read_text())
        self.addCleanup(lambda: subprocess.run(["kill", "-9", str(grandchild)], capture_output=True))
        time.sleep(0.5)
        self.assertFalse(Path(f"/proc/{grandchild}").exists(), "a process the late file started still runs")

    def test_a_failing_file_is_red_not_not_run(self):
        proc, _ = self.regression(FAIL="cockpit-a-test.py")
        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("FAIL tests/cockpit-a-test.py", proc.stdout)

    def test_a_run_inside_the_battery_that_holds_the_host_does_not_wait(self):
        self.hold_host(30)
        proc, took = self.regression(REGRESSION_HOST_WAIT="1", CI_RUN_TESTS_HOST_LOCK_HELD=str(self.lock))
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertNotIn("waiting", proc.stdout)


if __name__ == "__main__":
    unittest.main()
