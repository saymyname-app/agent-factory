#!/usr/bin/env python3
"""bin/convoy-advance on a fake tracker state: the repair of a red
integration branch whose red a control already found green (af-6vhm6r).

The protected branch moved, and bin/spec-integration merge ran the red
control on the new tip, green: it withdrew the red while its repair was
open, and kept that proof. The repair whose author left by an operator
request with nothing to merge is closed without merge on it, nothing
replayed; a repair with a commit to merge stays open. The harness is the
one of tests/convoy-advance-red-replay-test.py, loaded from there."""

import importlib.machinery
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_").removesuffix(".py"), str(ROOT / "tests" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


# The module is bound, not its classes: unittest collects the test classes
# named at the top of a file, and the cases of that file run there.
replay = load("convoy-advance-red-replay-test.py")
CONVOY = replay.CONVOY
STATE = replay.STATE
INTEGRATION_TOOL = replay.first.INTEGRATION_TOOL


class ConvoyAdvanceTest(replay.RedRepairHarness):

    def red_cleared_green(self):
        """The protected branch moves, and the merge pass finds the red
        green again on the new tip: it withdraws the red, its repair open."""
        main = self.git("rev-parse", "main")
        self.git("update-ref", "refs/heads/main",
                 self.git("commit-tree", f"{main}^{{tree}}", "-p", main, "-m", "a maintenance on main"))
        self.run_ok(INTEGRATION_TOOL, "merge", CONVOY, "--repo", self.root, "--profile",
                    self.root / "config" / "project-descriptors" / "fx.json")
        self.assertIsNone(self.red())
        return json.loads(self.run_ok(STATE, "show", CONVOY, "--repo", self.root).stdout)["convoy"][
            "integration_red_cleared"]

    def test_a_red_repair_whose_red_a_green_merge_pass_withdrew_is_closed_without_merge_on_that_proof(self):
        exit_at = self.red_repair_asked()
        cleared = self.red_cleared_green()
        self.assertEqual((self.REPAIR, "true", self.RED_CONTROL),
                         (cleared["repair"], cleared["command"], cleared["control"]))

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "red_repair_replay"))
        closed = self.of(answer, "red_repair_cleared")
        self.assertEqual((self.REPAIR, True, [self.REPAIR], cleared["commit"]),
                         (closed["ticket"], closed["closed"], closed["lifted"], closed["tests"]["commit"]))
        bead = self.bead(self.REPAIR)
        shown = self.shown_state(self.REPAIR)
        self.assertEqual("closed", bead["status"])
        self.assertIn("withdrawn", shown["gates"])
        self.assertIsNone(shown["merge"])
        self.assertIsNone(shown["park"])
        self.assertIn(f"rouge déjà retiré, clos sans fusion par le code : true code 0 sur {self.INTEGRATION} "
                      f"au commit {cleared['commit']}", bead["notes"])
        self.assertIn(exit_at, bead["notes"])
        self.assertNotIn(self.REPAIR, "\n".join(self.needs()))
        self.assertEqual([], self.resume_launches())

        again = self.advance(CONVOY)

        self.assertEqual([], self.of(again, "red_repair_cleared"))

    def test_a_red_repair_with_a_commit_to_merge_stays_open_when_a_green_merge_pass_withdrew_its_red(self):
        self.red_repair_asked(commit=True)
        self.red_cleared_green()

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "red_repair_cleared"))
        self.assertNotEqual("closed", self.bead(self.REPAIR)["status"])



if __name__ == "__main__":
    unittest.main()
