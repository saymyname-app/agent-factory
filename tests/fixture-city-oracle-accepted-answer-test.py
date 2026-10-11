#!/usr/bin/env python3
# ci: over-ceiling — cut from tests/fixture-city-oracle-parked-answer-author-gates-test.py, itself above the ceiling (CI01, af-q9urgr); each case walks the whole delivery flow to the answer of the owner
"""bin/fixture-city-oracle on the scenarios of tests/fixtures/fixture-city: the
cases of the answer « accepté » (T30) -- the complete scenario observed
Delivered then Accepted, and the two drivers made to go wrong around it.

They were in tests/fixture-city-oracle-parked-answer-author-gates-test.py
(af-vqew1x: that file, alone on one core, set the duration of a CI run).
The harness is the one of tests/fixture-city-oracle-test.py, loaded from
there."""

import importlib.machinery
import importlib.util
import json
import subprocess
import tempfile
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
# named at the top of a file, and the cases of the first file run there.
first = load("fixture-city-oracle-test.py")
ORACLE = first.ORACLE
FIXTURES = first.FIXTURES
OPERATOR = first.OPERATOR
DELIVERY_DRIVER = first.DELIVERY_DRIVER
DELIVERY_STATES = first.DELIVERY_STATES
AUTHOR_GATES = first.AUTHOR_GATES


class FixtureCityOracleTest(first.FixtureCityOracleHarness):
    # --- after Benjamin's answer: Delivered, then Accepted (T30, af-vlzc6v) ---

    def test_the_complete_scenario_is_observed_delivered_then_accepted_and_the_protected_branch_receives_one_merge(self):
        proc = self.deliver("outcome-accepted.json")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)
        self.assert_walked_through_the_gates_of_the_author(result, tickets=2)

        self.assertTrue(result["closed"])
        self.assertEqual(DELIVERY_STATES, result["lifecycle"])
        outcome = result["outcome"]
        # Two states, observed one after the other on the public state.
        self.assertEqual(("accepted", ["delivered", "accepted"]), (outcome["state"], outcome["states"]))
        # While it was Delivered: the whole end-of-Spec gate at the tip, after the one repair, and the
        # Acceptance Request with its dossier; the evidence of the walked ticket was read then.
        self.assertEqual((1, None), (outcome["end_rounds"], outcome["end_stop"]))
        [repair] = outcome["repairs"]
        self.assertEqual(("repair", DELIVERY_STATES, True), (repair["kind"], repair["lifecycle"], repair["closed_by_the_gate"]))
        self.assertEqual((True, True, []), (outcome["spec_end"]["at_the_tip"], outcome["spec_end"]["delivered"],
                                            outcome["spec_end"]["missing"]))
        self.assertEqual({"request": 1, "dossier_linked": True, "launched_at_dossier_commit": True, "stopped": True},
                         outcome["acceptance"])
        self.assertTrue(result["evidence"]["verified"])
        # Before « accepté » was recorded the protected branch held no commit of the convoy; after it,
        # one merge: its first parent is the tip it had, its second the tip of the integration branch.
        self.assertEqual({"moved_before_the_answer": False, "convoy_commits_before_the_answer": 0, "merges": 1,
                          "first_parent_is_the_previous_tip": True, "second_parent_is_the_integration_tip": True},
                         outcome["protected_branch"])
        self.assertEqual({"kept": True, "at_the_judged_commit": True}, outcome["integration_branch"])
        # The convoy is closed on the words of its approver, and nothing is left on the operator's list.
        closed = outcome["closed"]
        self.assertEqual(("accepted", "benjamin"), (closed["how"], closed["approver"]))
        self.assertTrue(closed["said"].strip())
        self.assertEqual((1, 0), (outcome["requests"], outcome["requests_once_closed"]))
        self.assertIn("git rev-list", result["interfaces"]["read"])
        self.assertEqual(["prepare", "publish", "advance", "stop"], result["interfaces"]["driver"])
        for hidden in ("prompt", "formula", "role", "session"):
            self.assertNotIn(hidden, proc.stdout.lower().replace("acceptance-session", ""))
        self.assertNotRegex(proc.stdout, r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])|/tmp/|\d{4}-\d{2}-\d{2}T|127\.0\.0\.1")

    def test_a_convoy_closed_accepted_without_having_been_observed_delivered_first_fails_the_oracle(self):
        proc = self.deliver_with_a_faulty_driver("outcome-accepted.json", "answers-in-the-event-of-delivered")

        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("", proc.stdout)
        self.assertIn("without having been observed Delivered first", proc.stderr)

    def test_an_expected_answer_that_nobody_gives_fails_the_oracle(self):
        proc = self.deliver_with_a_faulty_driver("outcome-abandoned.json", "nobody-answers")

        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("", proc.stdout)
        self.assertIn("observed delivered", proc.stderr)
        self.assertIn("expects delivered, then abandoned", proc.stderr)


if __name__ == "__main__":
    unittest.main()
