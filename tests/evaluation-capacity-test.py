#!/usr/bin/env python3
"""The two evaluation flows share durable host admission."""

import os
import json
import shutil
import socket
import subprocess
import time
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from evaluation_capacity import admission, Busy, ready_product, product_running, remove_attestation

ROOT = Path(__file__).resolve().parents[1]
LAUNCH = ROOT / "bin" / "project-launch"
DESCRIPTOR = ROOT / "tests" / "fixtures" / "delivery-fixture-city" / "descriptor.json"


class CapacityTest(unittest.TestCase):
    def test_sandbox_reuses_only_the_controller_attested_listener(self):
        if not shutil.which("bwrap"):
            self.skipTest("Bubblewrap required")
        state_home = Path.home() / ".local" / "state"
        state_home.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=state_home) as temporary:
            root = Path(temporary)
            state = root / "product.json"
            capacity = root / "capacity"
            env = {**os.environ, "EVALUATION_CAPACITY_STATE_DIR": str(capacity)}
            started = subprocess.run([str(LAUNCH), "--repo-root", str(ROOT), "start",
                                      str(DESCRIPTOR), "--commit", "HEAD", "--dataset",
                                      "content", "--state-file", str(state)],
                                     env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(0, started.returncode, started.stdout + started.stderr)
            try:
                record = json.loads(state.read_text())
                with patch.dict(os.environ, env):
                    self.assertTrue(product_running(record))
                    self.assertTrue(ready_product(str(state), record))

                def sandbox(ro_attestation=True, actual_wrapper=False):
                    code = ("import json,sys; from evaluation_capacity import ready_product,product_running; "
                            "r=json.loads(sys.argv[2]); "
                            "print(json.dumps([product_running(r),ready_product(sys.argv[1],r)]))")
                    if actual_wrapper:
                        args = [str(ROOT / "bin" / "delivery-role-sandbox"), "-c", code,
                                str(state), json.dumps(record)]
                    else:
                        args = ["bwrap", "--ro-bind", "/", "/", "--dev-bind", "/dev", "/dev",
                                "--proc", "/proc", "--tmpfs", "/tmp", "--bind", str(root), str(root)]
                        if ro_attestation:
                            args += ["--ro-bind", str(capacity / "attestations"),
                                     str(capacity / "attestations")]
                        args += ["--chdir", "/", "--", sys.executable, "-c", code,
                                 str(state), json.dumps(record)]
                    proc = subprocess.run(args, env={**env, "DELIVERY_ROLE_SANDBOXED": "1",
                                                     "DELIVERY_ROLE_SANDBOX_EXEC": sys.executable,
                                                     "PYTHONPATH": str(ROOT / "lib")},
                                          capture_output=True, text=True, timeout=10)
                    self.assertEqual(0, proc.returncode, proc.stderr)
                    return json.loads(proc.stdout)

                self.assertEqual([False, True], sandbox())
                self.assertEqual([False, True], sandbox(actual_wrapper=True))
                self.assertEqual([False, False], sandbox(ro_attestation=False))
                stopped = subprocess.run([str(LAUNCH), "stop", "--state-file", str(state)],
                                         env=env, capture_output=True, text=True, timeout=15)
                self.assertEqual(0, stopped.returncode, stopped.stdout + stopped.stderr)
                with socket.socket() as stranger:
                    stranger.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    stranger.bind(("127.0.0.1", record["port"]))
                    stranger.listen()
                    self.assertEqual([False, False], sandbox())
            finally:
                if state.exists():
                    subprocess.run([str(LAUNCH), "stop", "--state-file", str(state)],
                                   env=env, capture_output=True, timeout=15)
                with patch.dict(os.environ, env):
                    remove_attestation(str(state))

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
