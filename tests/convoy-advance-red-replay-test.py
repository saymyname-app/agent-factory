#!/usr/bin/env python3
"""bin/convoy-advance on a fake tracker state: the repair of a red
integration branch whose red did not reproduce for its author (af-3p6iz7).

The author left by an operator request with nothing to merge: the pass
runs the red control again itself, through bin/spec-integration take-up.
Green, the repair is closed without merge with that replay as its proof
and the red is withdrawn; red, the repair stays open on the new red, and
the same exit is not replayed twice. The harness is the one of
tests/convoy-advance-test.py, loaded from there."""

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
first = load("convoy-advance-test.py")
CONVOY = first.CONVOY
ESCALATION = first.ESCALATION
STATE = first.STATE

# A regression that names its failing file, then prints far more than the
# 300 characters a detail used to keep, the cause at the very end.
FLAKY = ("sh -c 'echo \"FAIL tests/flaky-test.py (3s)\"; "
         "for i in $(seq 120); do echo \"regression: took 1s for criterion class C$i\"; done; "
         "echo \"AssertionError: projection grew on replay\"; "
         "echo \"PASS tests/other-test.py (1s)\"; "
         "echo \"regression: took 9s with the host held (full budget 2340s)\"; exit 1'")


class RedRepairHarness(first.ConvoyAdvanceHarness):
    """The repair of a red integration branch, its author gone by an
    operator request (tests/convoy-advance-red-cleared-test.py loads it)."""

    def red_repair_asked(self, regression="true", commit=False):
        """The repair of the red at work, its author gone by an operator
        request with its branch at the integration tip (one commit more
        with `commit`). Returns the exit's time."""
        base = self.integrated(regression=regression)
        self.resumable()
        self.red_recorded(base)
        self.advance(CONVOY)
        self.git("branch", f"ticket/{self.REPAIR}", base)
        if commit:
            tip = self.git("commit-tree", f"{base}^{{tree}}", "-p", base, "-m", "a fix")
            self.git("update-ref", f"refs/heads/ticket/{self.REPAIR}", tip)
        self.run_ok(STATE, "set-branch", CONVOY, self.REPAIR, "--branch", f"ticket/{self.REPAIR}")
        self.taken(self.REPAIR, "auteur-repair")
        request = {
            "quoi": "Le rouge ne se reproduit pas : le même arbre passe la régression",
            "pourquoi": "Aucun commit à fusionner, aucune porte de clôture.",
            "que_faire": [{"option": "Corriger par maintenance sur main",
                           "consequence": "Le ticket reprend après la fusion."}],
            "langue": "fr", "bloquant": True,
        }
        self.run_ok(ESCALATION, "benjamin", self.REPAIR, json.dumps(request))
        self.run_ok(STATE, "park", CONVOY, self.REPAIR, "--cause", "operator_request", "--detail", request["quoi"])
        self.run_ok(STATE, "set-exit", CONVOY, self.REPAIR, "--exit", "operator_request")
        self.write_log.write_text("")
        return self.shown_state(self.REPAIR)["exit"]["at"]

    def red(self):
        return json.loads(self.run_ok(STATE, "show", CONVOY, "--repo", self.root).stdout)["convoy"]["integration_red"]


class ConvoyAdvanceTest(RedRepairHarness):

    def test_a_red_repair_with_nothing_to_merge_is_closed_without_merge_once_the_replay_is_green(self):
        self.red_repair_asked()

        answer = self.advance(CONVOY)

        replay = self.of(answer, "red_repair_replay")
        self.assertEqual((self.REPAIR, True, 0), (replay["ticket"], replay["closed"], replay["tests"]["exit_code"]))
        self.assertEqual([self.REPAIR], replay["lifted"])
        bead = self.bead(self.REPAIR)
        shown = self.shown_state(self.REPAIR)
        self.assertEqual("closed", bead["status"])
        self.assertIn("withdrawn", shown["gates"])
        self.assertIsNone(shown["merge"])
        self.assertIsNone(shown["park"])
        self.assertIn("rouge non reproduit, clos sans fusion par le code : true code 0", bead["notes"])
        self.assertIn(replay["tests"]["commit"], bead["notes"])
        self.assertIsNone(self.red())
        self.assertNotIn(self.REPAIR, "\n".join(self.needs()))
        self.assertEqual([], self.resume_launches())

        again = self.advance(CONVOY)

        self.assertEqual([], self.of(again, "red_repair_replay"))

    def test_a_red_repair_whose_replay_is_still_red_stays_open_and_is_replayed_once(self):
        exit_at = self.red_repair_asked(regression=FLAKY)
        before = self.red()

        answer = self.advance(CONVOY)

        replay = self.of(answer, "red_repair_replay")
        self.assertEqual((self.REPAIR, False), (replay["ticket"], replay["closed"]))
        self.assertNotEqual("closed", self.bead(self.REPAIR)["status"])
        self.assertEqual("operator_request", self.park_of(self.REPAIR)["cause"])
        red = self.red()
        self.assertEqual((self.REPAIR, exit_at), (red["repair"], red["replay"]))
        self.assertNotEqual(before["at"], red["at"])
        # The failing file and its output are kept, not only the run's end.
        self.assertIn("FAIL tests/flaky-test.py (3s)", red["detail"])
        self.assertIn("AssertionError: projection grew on replay", red["detail"])

        again = self.advance(CONVOY)

        self.assertEqual([], self.of(again, "red_repair_replay"))
        self.assertEqual(red, self.red())

    def test_a_red_repair_with_a_commit_to_merge_is_not_replayed(self):
        self.red_repair_asked(commit=True)
        before = self.red()

        answer = self.advance(CONVOY)

        self.assertEqual([], self.of(answer, "red_repair_replay"))
        self.assertNotEqual("closed", self.bead(self.REPAIR)["status"])
        self.assertEqual("operator_request", self.park_of(self.REPAIR)["cause"])
        self.assertEqual(before, self.red())


if __name__ == "__main__":
    unittest.main()
