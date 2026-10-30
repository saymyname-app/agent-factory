#!/usr/bin/env python3
"""The time budgets of a ticket's tests come from one file, measured, and the
order convoy-advance covers one pass (study C, T3, af-npz9v1.32;
lib/test_budgets.py)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "test-budgets"
sys.path.insert(0, str(ROOT / "lib"))
import test_budgets  # noqa: E402


def piece(store: Path, ticket: str, name: str, output: str, exit_code: int = 0, at: str = "2026-10-26T00:00:00Z"):
    path = store / "af-spec" / ticket / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"at": at, "commit": None, "exit_code": str(exit_code), "output": output}))


class TestBudgets(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="test-budgets-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.store = self.tmp / "store"

    def tool(self, *args):
        return subprocess.run([str(TOOL), *args], text=True, capture_output=True)

    def test_the_order_of_this_repository_covers_one_pass(self):
        proc = self.tool("check-order")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)

    def test_an_order_shorter_than_one_pass_is_refused(self):
        root = self.tmp / "root"
        (root / "orders").mkdir(parents=True)
        (root / "config").mkdir()
        shutil.copy(ROOT / "config" / "test-budgets.json", root / "config" / "test-budgets.json")
        (root / "orders" / "convoy-advance.toml").write_text('[order]\ntimeout = "30m"\n')
        proc = self.tool("check-order", "--root", str(root))
        self.assertEqual(1, proc.returncode, proc.stdout)
        answer = json.loads(proc.stdout)
        self.assertEqual((False, 1800), (answer["ok"], answer["order_seconds"]))
        self.assertGreater(answer["pass_seconds"], 1800)

    def test_every_deadline_comes_from_the_file(self):
        budgets = test_budgets.load(ROOT)
        data = json.loads((ROOT / "config" / "test-budgets.json").read_text())
        for field in test_budgets.DEFAULTS:
            self.assertEqual(data[field], budgets[field], field)
        self.assertEqual(budgets["host_wait_seconds"] + budgets["full_seconds"] + budgets["margin_seconds"],
                         test_budgets.deadline(budgets, "full"))

    def test_a_missing_file_falls_back_to_600_s(self):
        self.assertEqual(600, test_budgets.load(self.tmp)["full_seconds"])

    def test_refresh_sets_each_budget_to_1_5_times_its_slowest_measured_run(self):
        for n, seconds in enumerate((200, 260, 240)):
            # A green piece holds the answer of bin/tdd-step, its timing inside.
            answer = {"regression": [{"timing": [f"regression: took {seconds}s with the host held (green budget 600s)"]}]}
            piece(self.store, f"g{n}", "tdd_green.json", json.dumps(answer, indent=2), at=f"2026-10-26T0{n}:00:00Z")
        # Older merged runs, before the took line: their files' seconds.
        for n, criteria in enumerate((300, 372, 340)):
            piece(self.store, f"m{n}", "merged_tests.json",
                  f"PASS tests/cockpit-a-test.py (40s)\nPASS tests/cockpit-b-test.py (40s)\n"
                  f"PASS tests/cockpit-criteria-test.py ({criteria}s)\n", at=f"2026-10-25T0{n}:00:00Z")
        found = test_budgets.runs(self.store)
        new = test_budgets.refreshed(test_budgets.DEFAULTS, found)
        self.assertEqual(60 * 7, new["green_seconds"])        # 1.5 x 260 = 390 -> 420
        self.assertEqual(60 * 10, new["full_seconds"])        # 1.5 x (20 + 372) = 588 -> 600
        self.assertEqual(600, new["host_wait_seconds"])

    def test_a_kind_with_fewer_than_three_runs_keeps_its_budget(self):
        piece(self.store, "g", "tdd_green.json", "regression: took 900s with the host held (green budget 600s)\n")
        new = test_budgets.refreshed({**test_budgets.DEFAULTS, "green_seconds": 480}, test_budgets.runs(self.store))
        self.assertEqual(480, new["green_seconds"])

    def test_a_red_merged_run_is_no_measure(self):
        piece(self.store, "m", "merged_tests.json",
              "FAIL tests/cockpit-criteria-test.py (900s)\n"
              "regression: took 900s with the host held (full budget 900s)\n", exit_code=1)
        self.assertEqual([], test_budgets.runs(self.store))


if __name__ == "__main__":
    unittest.main()
