#!/usr/bin/env python3
"""The two evaluation flows share durable host admission."""

import os
import subprocess
import time
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from evaluation_capacity import admission, Busy


class CapacityTest(unittest.TestCase):
    def test_two_flows_share_two_slots_and_failed_cleanup_keeps_one(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ticket = root / "ticket"
            outcome = root / "outcome"
            ticket.mkdir()
            outcome.mkdir()
            env = {"TICKET_EVALUATION_STATE_DIR": str(ticket),
                   "OUTCOME_EVALUATION_STATE_DIR": str(outcome),
                   "EVALUATION_CAPACITY_STATE_DIR": str(root / "capacity")}
            with patch.dict(os.environ, env):
                first = ticket / "one.json"
                second = outcome / "two.json"
                third = ticket / "three.json"
                with admission(first):
                    first.write_text("provisional")
                with admission(second):
                    second.write_text("running")
                with self.assertRaises(Busy):
                    with admission(third):
                        third.write_text("must not start")
                self.assertFalse(third.exists())
                # A stop whose confirmation failed retains its launch record
                # and therefore continues occupying the slot.
                first.unlink()
                with admission(third):
                    third.write_text("running")
                self.assertTrue(third.exists())

    def test_child_holds_admission_if_parent_crashes_before_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ticket = root / "ticket"
            ticket.mkdir()
            env = {**os.environ, "TICKET_EVALUATION_STATE_DIR": str(ticket),
                   "OUTCOME_EVALUATION_STATE_DIR": str(root / "outcome"),
                   "EVALUATION_CAPACITY_STATE_DIR": str(root / "capacity")}
            launcher = ("import os, subprocess, sys; "
                        "from pathlib import Path; "
                        "from evaluation_capacity import admission; "
                        "with admission(Path(sys.argv[1])) as fd: "
                        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(1)'], "
                        "pass_fds=(fd,), stdout=subprocess.DEVNULL); os._exit(0)")
            # A compound `with` statement needs a real newline in -c code.
            launcher = launcher.replace("; with admission", "\nwith admission")
            subprocess.run([sys.executable, "-c", launcher, str(ticket / "pending.json")],
                           env={**env, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "lib")},
                           check=True, timeout=5)
            started = time.monotonic()
            with patch.dict(os.environ, env), admission(ticket / "next.json"):
                pass
            self.assertGreaterEqual(time.monotonic() - started, 0.5)

    def test_interrupted_admission_recovers_from_provisional_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ticket = root / "ticket"
            ticket.mkdir()
            capacity = root / "capacity"
            capacity.mkdir()
            (capacity / "interrupted.reservation").write_text("interrupted")
            env = {"TICKET_EVALUATION_STATE_DIR": str(ticket),
                   "OUTCOME_EVALUATION_STATE_DIR": str(root / "outcome"),
                   "EVALUATION_CAPACITY_STATE_DIR": str(capacity)}
            with patch.dict(os.environ, env):
                with admission(ticket / "recover.json"):
                    (ticket / "recover.json").write_text("provisional")
                self.assertEqual([], list(capacity.glob("*.reservation")))


if __name__ == "__main__":
    unittest.main()
