#!/usr/bin/env python3
"""The doors of the Factory on an isolated cockpit, `bin/cockpit-isolated`
(B, af-4uzgzm; Spec af-fgcw0d, Testing Decisions 1, 3 and 8): a gesture the
cockpit sends goes through the real door of the commit and is written in the
tracker of the launch, and a dataset may say a door expires (`expires`), or
expires once its record is written (`records-then-expires`).

The doors are run as the cockpit runs them: the command and the environment
the launched cockpit carries (/proc/<pid>/environ).
"""

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "bin" / "cockpit-isolated"
HOME_CONTENT = ROOT / "config" / "cockpit-datasets" / "home-content.json"
REASON = "Les notes restent dans le projet."
# Longer than a door of the launch takes to answer; shorter than forever.
PATIENCE = 5


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TheDoors(unittest.TestCase):

    def dataset(self, doors=None):
        dataset = json.loads(HOME_CONTENT.read_text(encoding="utf-8"))
        if doors is not None:
            dataset["doors"] = doors
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name, "dataset.json")
        path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
        return path

    def launched(self, doors=None):
        """The environment of the cockpit the recipe serves, once it answers."""
        port = free_port()
        proc = subprocess.Popen([sys.executable, str(RECIPE), "--port", str(port), "--dataset",
                                 str(self.dataset(doors))], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(proc.wait, 30)
        self.addCleanup(proc.terminate)
        deadline = time.monotonic() + 30
        while True:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=2) as response:
                    if response.status == 200:
                        break
            except (urllib.error.URLError, ConnectionError, OSError):
                pass
            self.assertLess(time.monotonic(), deadline, "the cockpit never answered")
            time.sleep(0.2)
        pairs = Path(f"/proc/{proc.pid}/environ").read_bytes().decode().split("\0")
        return dict(pair.split("=", 1) for pair in pairs if "=" in pair)

    def tracker(self, env):
        return {bead["id"]: bead for bead in json.loads(Path(env["FAKE_BD_STATE_FILE"]).read_text(encoding="utf-8"))}

    def refuse(self, env):
        """The cockpit's refusal of a proposal, as it runs the door: the
        completed process, or None when the door did not answer in time."""
        # A proposal as bin/proposal-door (create) leaves it, put in the
        # tracker of the launch: a Panorama dataset holds none.
        bead, path = "af-x5c8d", Path(env["FAKE_BD_STATE_FILE"])
        beads = json.loads(path.read_text(encoding="utf-8"))
        beads.append({"id": bead, "title": "Ajouter un export des notes en CSV", "status": "open",
                      "labels": ["proposal"], "metadata": {"gc.proposal_state": "ouverte"}})
        path.write_text(json.dumps(beads, ensure_ascii=False), encoding="utf-8")
        try:
            return bead, subprocess.run([env["COCKPIT_PROPOSAL_DOOR_BIN"], "rejeter", bead, REASON, "benjamin"],
                                        env=env, capture_output=True, text=True, timeout=PATIENCE)
        except subprocess.TimeoutExpired:
            return bead, None

    def test_a_gesture_goes_through_the_real_door_onto_the_tracker_of_the_launch(self):
        env = self.launched()
        bead, done = self.refuse(env)
        self.assertIsNotNone(done, "the door of the launch never answered")
        self.assertEqual(0, done.returncode, f"the door of the launch refused: {done.stderr}")
        metadata = self.tracker(env)[bead]["metadata"]
        self.assertEqual("rejetee", metadata.get("gc.proposal_state"))
        self.assertEqual(REASON, metadata.get("gc.proposal_reject_reason"))

    def test_a_door_the_dataset_says_expires_never_answers_and_writes_nothing(self):
        env = self.launched({"proposal-door": "expires"})
        bead, done = self.refuse(env)
        self.assertIsNone(done, f"a door that expires answered: {done}")
        self.assertEqual("ouverte", self.tracker(env)[bead]["metadata"]["gc.proposal_state"])

    def test_a_door_that_records_then_expires_writes_its_record_and_never_answers(self):
        env = self.launched({"proposal-door": "records-then-expires"})
        bead, done = self.refuse(env)
        self.assertIsNone(done, f"a door that expires answered: {done}")
        self.assertEqual("rejetee", (self.tracker(env)[bead].get("metadata") or {}).get("gc.proposal_state"))

    def test_the_order_pause_door_writes_on_the_tracker_of_the_launch_and_may_expire(self):
        # B's « relancer un order » (af-npz9v1.15): a dataset may name
        # order-pause, and the real door writes its record there first.
        env = self.launched({"order-pause": "records-then-expires"})
        try:
            done = subprocess.run([env["COCKPIT_ORDER_PAUSE_BIN"], "pause", "convoy-advance", "--by", "usine",
                                   "--words", "pause d'essai"], env=env, capture_output=True, text=True,
                                  timeout=PATIENCE)
        except subprocess.TimeoutExpired:
            done = None
        self.assertIsNone(done, f"a door that expires answered: {done}")
        [record] = [bead for bead in self.tracker(env).values()
                    if (bead.get("metadata") or {}).get("gc.order_pause") == "convoy-advance"]
        self.assertEqual("open", record["status"])
        self.assertEqual("usine", record["metadata"]["gc.order_pause_by"])

    def door(self, env, variable, *args):
        return subprocess.run([env[variable], *args], env=env, capture_output=True, text=True, timeout=60)

    def test_a_setting_goes_through_provider_failover_onto_the_state_of_the_launch(self):
        # G2 (af-f8nlhr; af-npz9v1.20): a setting the door takes in charge,
        # then read back by the same door, never the Factory's own state.
        served = ROOT / ".gc" / "provider-state.json"
        before = served.stat().st_mtime if served.exists() else None
        env = self.launched()
        done = self.door(env, "COCKPIT_PROVIDER_FAILOVER_BIN", "set", "--action", "disable",
                         "--args", json.dumps({"provider": "codex", "reason": "essai"}), "--by", "usine")
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)
        self.assertTrue(json.loads(done.stdout)["ok"])
        # Written in the Factory tree the page Usine reads, of the launch.
        self.assertEqual(str(Path(env["HOME"], "factory")), env["COCKPIT_FACTORY_ROOT"])
        state = Path(env["COCKPIT_FACTORY_ROOT"], ".gc", "provider-state.json")
        self.assertIn("codex", state.read_text(encoding="utf-8"))
        read = self.door(env, "COCKPIT_PROVIDER_FAILOVER_BIN", "status", "--json")
        self.assertEqual(0, read.returncode, read.stdout + read.stderr)
        self.assertIn("codex", read.stdout)
        self.assertEqual(before, served.stat().st_mtime if served.exists() else None)

    def test_an_upkeep_cleans_throwaway_repositories_and_keeps_what_it_must(self):
        # G2: a preview, then the cleaning of the scope, on Git repositories
        # of the launch; an active worktree, a local change and a commit not
        # pushed are kept, and the commit not pushed is escalated on the
        # tracker of the launch. The repository of the commit keeps its own.
        own = subprocess.run(["git", "-C", str(ROOT), "for-each-ref", "refs/heads/"],
                             capture_output=True, text=True).stdout
        env = self.launched()
        worktrees = Path(env["HOME"], ".local", "share", "agent-factory-runtime-worktrees")
        preview = self.door(env, "COCKPIT_FACTORY_MAINTAIN_BIN", "clean-worktrees", "--dry-run")
        self.assertEqual(0, preview.returncode, preview.stdout + preview.stderr)
        self.assertIn(f"would remove: {worktrees / 'af-merged'} ", preview.stdout)
        self.assertIn(f"would escalate: {worktrees / 'af-unpushed'} ", preview.stdout)
        done = self.door(env, "COCKPIT_FACTORY_MAINTAIN_BIN", "clean-worktrees")
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)
        self.assertEqual(["af-active", "af-modified", "af-unpushed"], sorted(p.name for p in worktrees.iterdir()))
        self.assertTrue([bead for bead in self.tracker(env).values()
                         if bead["title"].startswith("[clean-worktrees] unpushed commits")])
        pruned = self.door(env, "COCKPIT_FACTORY_MAINTAIN_BIN", "prune-merged-branches")
        self.assertEqual(0, pruned.returncode, pruned.stdout + pruned.stderr)
        branches = subprocess.run(["git", "-C", str(Path(env["HOME"], "maintain", "factory")), "for-each-ref",
                                   "--format=%(refname:short)", "refs/heads/"], capture_output=True, text=True)
        self.assertNotIn("merged", branches.stdout.split())
        self.assertIn("unpushed", branches.stdout.split())
        self.assertEqual(own, subprocess.run(["git", "-C", str(ROOT), "for-each-ref", "refs/heads/"],
                                             capture_output=True, text=True).stdout)

    def test_the_operator_settings_are_read_from_the_commit(self):
        read = subprocess.run([sys.executable, str(ROOT / "bin" / "operator-config"), "language"],
                              capture_output=True, text=True)
        self.assertEqual(0, read.returncode, read.stderr)
        acting = self.launched()
        self.assertEqual(read.stdout, self.door(acting, "COCKPIT_OPERATOR_CONFIG_BIN", "language").stdout)
        # A dataset may say the door expires, as any door of the launch.
        expiring = self.launched({"operator-config": "expires"})
        with self.assertRaises(subprocess.TimeoutExpired):
            subprocess.run([expiring["COCKPIT_OPERATOR_CONFIG_BIN"], "language"], env=expiring,
                           capture_output=True, timeout=PATIENCE)

    def test_doors_that_are_not_each_a_door_and_how_it_answers_are_refused(self):
        for doors in ({"proposal-door": "answers twice"}, {"merge-door": "expires"}):
            path = self.dataset(doors)
            proc = subprocess.run([sys.executable, str(RECIPE), "--port", "1", "--dataset", str(path)],
                                  text=True, capture_output=True, timeout=30)
            self.assertNotEqual(0, proc.returncode, f"the recipe served the doors {doors}")
            self.assertRegex(proc.stderr, rf"cockpit-isolated: {re.escape(str(path))}: its doors \(doors\)")


if __name__ == "__main__":
    unittest.main()
