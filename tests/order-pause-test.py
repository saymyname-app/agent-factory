#!/usr/bin/env python3
"""bin/order-pause (af-npz9v1.15): pause and resume an order of the Factory
without a PR, traced at the source, honoured by the gate every order runs.

Each case runs the command as a process on a tracker of its own (the
synthetic `gc`/`bd` of tests/fixtures/cockpit/synthetic-city), starting
empty; the orders and city.toml read are this repository's own.
"""
import json
import os
import shlex
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOOR = ROOT / "bin" / "order-pause"
SYNTHETIC_GC = ROOT / "tests" / "fixtures" / "cockpit" / "synthetic-city" / "gc"


class OrderPause(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.tracker = self.dir / "tracker.json"
        self.tracker.write_text("[]", encoding="utf-8")
        self.env = {**os.environ, "GC_BIN": str(SYNTHETIC_GC), "FAKE_BD_STATE_FILE": str(self.tracker)}
        self.env.pop("ORDER_PAUSE_ROOT", None)

    def door(self, *args, env=None):
        return subprocess.run([str(DOOR), *args], env=env or self.env, capture_output=True, text=True, timeout=30)

    def beads(self):
        return json.loads(self.tracker.read_text(encoding="utf-8"))

    def gate(self, order, exit_code=0):
        """Run `order`'s gate on a command that leaves a file and exits
        `exit_code`: (completed process, whether the command ran)."""
        mark = self.dir / "ran"
        mark.unlink(missing_ok=True)
        done = self.door("gate", order, "--", "sh", "-c", f'touch "{mark}"; exit {exit_code}')
        return done, mark.exists()

    def test_a_pause_is_recorded_with_who_when_words_and_reason_and_the_gate_runs_nothing(self):
        done = self.door("pause", "pr-autopilot", "--by", "benjamin", "--words", "stop le temps du test",
                         "--reason", "essai")
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertIn("pr-autopilot est en pause", done.stdout)
        [record] = self.beads()
        self.assertEqual("open", record["status"])
        self.assertIn("order-pause", record["labels"])
        metadata = record["metadata"]
        self.assertEqual("pr-autopilot", metadata["gc.order_pause"])
        self.assertEqual("benjamin", metadata["gc.order_pause_by"])
        self.assertEqual("stop le temps du test", metadata["gc.order_pause_words"])
        self.assertEqual("essai", metadata["gc.order_pause_reason"])
        self.assertRegex(metadata["gc.order_pause_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

        gated, ran = self.gate("pr-autopilot")
        self.assertEqual(0, gated.returncode, gated.stderr)
        self.assertFalse(ran, "the gate ran a paused order")
        self.assertIn("pr-autopilot est en pause", gated.stdout)
        self.assertIn("rien n'est lancé", gated.stdout)

        other, ran = self.gate("factory-guard")
        self.assertTrue(ran, "a pause held another order")

        shown = json.loads(self.door("show", "--json").stdout)["orders"]
        paused = [row for row in shown if row["state"] == "paused"]
        self.assertEqual([("pr-autopilot", "benjamin", "stop le temps du test", record["id"])],
                         [(row["order"], row["by"], row["words"], row["record"]) for row in paused])

    def test_a_resume_closes_the_record_with_who_and_words_and_the_gate_runs_the_order_again(self):
        self.door("pause", "convoy-advance", "--by", "usine", "--words", "pause pour réparation")
        done = self.door("resume", "convoy-advance", "--by", "benjamin", "--words", "relance")
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertIn("convoy-advance reprend", done.stdout)
        [record] = self.beads()
        self.assertEqual("closed", record["status"])
        self.assertEqual("usine", record["metadata"]["gc.order_pause_by"])
        self.assertEqual("benjamin", record["metadata"]["gc.order_resume_by"])
        self.assertEqual("relance", record["metadata"]["gc.order_resume_words"])

        gated, ran = self.gate("convoy-advance", exit_code=3)
        self.assertTrue(ran, "the gate held a resumed order")
        self.assertEqual(3, gated.returncode, "the gate did not hand the order's exit status back")
        self.assertIn("Aucun ordre en pause.", self.door("show").stdout)

    def test_pause_and_resume_already_in_their_state_write_nothing(self):
        self.assertEqual(0, self.door("resume", "pr-autopilot", "--by", "b", "--words", "w").returncode)
        self.assertEqual([], self.beads())
        self.door("pause", "pr-autopilot", "--by", "a", "--words", "premier")
        again = self.door("pause", "pr-autopilot", "--by", "b", "--words", "second")
        self.assertEqual(0, again.returncode, again.stderr)
        self.assertIn("déjà en pause", again.stdout)
        self.assertIn("par a", again.stdout)
        self.assertEqual(1, len(self.beads()))

    def test_refusals_say_why_in_french_and_write_nothing(self):
        cases = {
            ("pause", "no-such-order", "--by", "b", "--words", "w"): "n'est pas un ordre de l'usine",
            ("pause", "nudge-mail-sweep", "--by", "b", "--words", "w"): "[orders] skip de city.toml",
            ("resume", "nudge-mail-sweep", "--by", "b", "--words", "w"): "décision de config de Benjamin",
            ("pause", "pr-autopilot", "--by", "b"): "--words est obligatoire",
            ("resume", "pr-autopilot", "--words", "w", "--by", " "): "--by est obligatoire",
        }
        for args, reason in cases.items():
            with self.subTest(args=args):
                done = self.door(*args)
                self.assertEqual(2, done.returncode, done.stdout)
                self.assertIn(reason, done.stderr)
        self.assertEqual([], self.beads())

    def test_an_order_whose_exec_does_not_go_through_the_gate_is_refused(self):
        root = self.dir / "root"
        (root / "orders").mkdir(parents=True)
        (root / "city.toml").write_text("[orders]\nskip = []\n", encoding="utf-8")
        (root / "orders" / "bare.toml").write_text('[order]\nexec = "/bin/true"\n', encoding="utf-8")
        done = self.door("pause", "bare", "--by", "b", "--words", "w", env={**self.env, "ORDER_PAUSE_ROOT": str(root)})
        self.assertEqual(2, done.returncode, done.stdout)
        self.assertIn("ne passe pas par la porte", done.stderr)
        self.assertEqual([], self.beads())

    def test_the_gate_runs_the_order_when_the_tracker_cannot_be_read(self):
        self.door("pause", "pr-autopilot", "--by", "a", "--words", "w")
        self.env["FAKE_BD_FAIL_FLAG_FILE"] = str(self.tracker)
        gated, ran = self.gate("pr-autopilot")
        self.assertTrue(ran, "an unreadable tracker held the order")
        self.assertIn("le suivi ne se lit pas", gated.stderr)
        self.assertEqual(1, self.door("show").returncode)

    def test_show_names_the_orders_city_toml_skips(self):
        shown = json.loads(self.door("show", "--json").stdout)["orders"]
        skipped = {row["order"] for row in shown if row["state"] == "skipped"}
        self.assertIn("nudge-mail-sweep", skipped)

    def test_every_order_of_the_factory_runs_through_its_own_gate(self):
        for path in sorted((ROOT / "orders").glob("*.toml")):
            with self.subTest(order=path.stem):
                words = shlex.split(tomllib.loads(path.read_text(encoding="utf-8"))["order"]["exec"])
                self.assertEqual("order-pause", Path(words[0]).name)
                self.assertEqual(["gate", path.stem, "--"], words[1:4])
                self.assertGreater(len(words), 4, "the gate has no command to run")


if __name__ == "__main__":
    unittest.main()
