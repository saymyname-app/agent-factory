#!/usr/bin/env python3

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "planning-run-reservation"


class PlanningRunReservationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="planning-run-reservation-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.runtime_path = self.tmp / ".gc" / "runtime" / "planning-run-reservation.json"
        self.seed_path = self.tmp / "config" / "planning-run-reservation.json"

    def run_tool(self, *args, check=True):
        return subprocess.run(
            (str(TOOL), "--repo-root", str(self.tmp), *[str(a) for a in args]),
            text=True, capture_output=True, check=check,
        )

    def write_reservation(self, reserved_for="C01", cleared_at=None, next_reservation=None):
        self.runtime_path.parent.mkdir(parents=True, exist_ok=True)
        reservation = {
            "contract": "agent-factory-planning-run-reservation/v1",
            "reserved_for": reserved_for,
            "note": "test reservation",
            "reserved_at": "2026-09-24",
            "reserved_by": "planning-run-reservation-test",
            "cleared_at": cleared_at,
        }
        if next_reservation is not None:
            reservation["next"] = next_reservation
        self.runtime_path.write_text(json.dumps(reservation), encoding="utf-8")

    # --- check: no reservation --------------------------------------------

    def test_check_with_no_reservation_is_allowed(self):
        result = json.loads(self.run_tool("check").stdout)
        self.assertTrue(result["ok"])
        self.assertFalse(result["active"])
        self.assertTrue(result["allowed"])
        self.assertIsNone(result["reserved_for"])

    # --- check: matching target is accepted ---------------------------------

    def test_check_with_matching_target_is_allowed(self):
        self.write_reservation(reserved_for="C01")
        result = json.loads(self.run_tool("check", "--target", "C01").stdout)
        self.assertTrue(result["ok"])
        self.assertTrue(result["active"])
        self.assertTrue(result["allowed"])
        self.assertEqual("C01", result["reserved_for"])
        self.assertNotIn("reason", result)

    # --- check: a different target is refused while active -----------------

    def test_check_with_a_different_target_is_refused(self):
        self.write_reservation(reserved_for="C01")
        result = json.loads(self.run_tool("check", "--target", "some-other-run").stdout)
        self.assertTrue(result["ok"])
        self.assertTrue(result["active"])
        self.assertFalse(result["allowed"])
        self.assertEqual("C01", result["reserved_for"])
        self.assertIn("C01", result["reason"])

    def test_check_with_no_target_declared_is_refused_while_active(self):
        self.write_reservation(reserved_for="C01")
        result = json.loads(self.run_tool("check").stdout)
        self.assertTrue(result["ok"])
        self.assertFalse(result["allowed"])
        self.assertEqual("C01", result["reserved_for"])

    # --- advance: promotes next, or clears ----------------------------------

    def test_advance_promotes_the_next_reservation(self):
        self.write_reservation(
            reserved_for="factory-operations-v2",
            next_reservation={"reserved_for": "C01", "requirements": ["ntfy"]},
        )
        result = json.loads(self.run_tool("advance").stdout)
        self.assertTrue(result["ok"])
        self.assertTrue(result["advanced"])
        self.assertEqual("promoted", result["result"])
        self.assertEqual("C01", result["reserved_for"])

        after = json.loads(self.runtime_path.read_text())
        self.assertEqual("C01", after["reserved_for"])
        self.assertIsNone(after["cleared_at"])
        self.assertEqual("factory-operations-v2", after["promoted_after"])
        self.assertEqual(["ntfy"], after["requirements"])

        # The promoted reservation now gates every other target.
        blocked = json.loads(self.run_tool("check", "--target", "factory-operations-v2").stdout)
        self.assertFalse(blocked["allowed"])
        self.assertEqual("C01", blocked["reserved_for"])

    def test_advance_with_no_next_clears_the_reservation(self):
        self.write_reservation(reserved_for="C01")
        result = json.loads(self.run_tool("advance").stdout)
        self.assertTrue(result["ok"])
        self.assertTrue(result["advanced"])
        self.assertEqual("cleared", result["result"])
        self.assertIsNone(result["reserved_for"])

        after = json.loads(self.runtime_path.read_text())
        self.assertIsNotNone(after["cleared_at"])

        # Once cleared, every target is allowed through.
        unblocked = json.loads(self.run_tool("check").stdout)
        self.assertTrue(unblocked["allowed"])
        self.assertFalse(unblocked["active"])

    def test_advance_with_no_reservation_is_a_no_op(self):
        result = json.loads(self.run_tool("advance").stdout)
        self.assertTrue(result["ok"])
        self.assertFalse(result["advanced"])
        self.assertEqual("no_reservation", result["result"])
        self.assertFalse(self.runtime_path.exists())

    # --- the tracked seed is never written by this tool ---------------------

    def test_check_and_advance_never_write_the_tracked_seed(self):
        self.write_reservation(reserved_for="C01")
        self.assertFalse(self.seed_path.exists())

        json.loads(self.run_tool("check", "--target", "C01").stdout)
        self.assertFalse(self.seed_path.exists())

        json.loads(self.run_tool("advance").stdout)
        self.assertFalse(self.seed_path.exists())

    def test_a_tracked_seed_is_copied_into_untracked_runtime_state_on_first_read(self):
        self.seed_path.parent.mkdir(parents=True, exist_ok=True)
        self.seed_path.write_text(json.dumps({
            "contract": "agent-factory-planning-run-reservation/v1",
            "reserved_for": "C01",
            "cleared_at": None,
            "reserved_at": "2026-09-24",
            "reserved_by": "seed",
        }), encoding="utf-8")
        self.assertFalse(self.runtime_path.exists())

        result = json.loads(self.run_tool("check", "--target", "C01").stdout)

        self.assertTrue(result["allowed"])
        # The seed is copied, not moved -- it stays a read-only fallback for
        # any other checkout that has not yet run this tool.
        self.assertTrue(self.runtime_path.exists())
        self.assertTrue(self.seed_path.exists())
        self.assertEqual("C01", json.loads(self.runtime_path.read_text())["reserved_for"])


if __name__ == "__main__":
    unittest.main()
