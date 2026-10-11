#!/usr/bin/env python3
# ci: over-ceiling — cut from tests/fixture-city-oracle-test.py, itself above the ceiling when it was set (CI01, af-q9urgr); each case walks the whole delivery flow to the end of its Spec
"""bin/fixture-city-oracle on the scenarios of tests/fixtures/fixture-city: the
cases of the story not observed at the end, repaired by one ticket then
Delivered, and of the walk where nothing goes wrong (T26).

They were in tests/fixture-city-oracle-test.py, whose harness is loaded
from there (af-vqew1x: that file, alone on one core, set the duration of a
CI run). The other cases of the oracle are in that file, in
tests/fixture-city-oracle-parked-answer-author-gates-test.py and in
tests/fixture-city-oracle-accepted-answer-test.py."""

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
    # --- a story not observed at the end: one repair, the gate replayed, Delivered (T26, af-vwcflt) ---

    def test_a_story_not_observed_at_the_end_is_repaired_by_one_ticket_and_the_convoy_is_delivered_on_the_new_tip(self):
        proc = self.deliver("story-repaired-delivered.json")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)
        self.assert_walked_through_the_gates_of_the_author(result, tickets=2)

        # The walked ticket went through its nine states before the end of the Spec was tried.
        self.assertTrue(result["closed"])
        self.assertEqual(DELIVERY_STATES, result["lifecycle"])
        outcome = result["outcome"]
        self.assertEqual("delivered", outcome["state"])
        # The first gate refused on the Outcome Evaluation, and on nothing before it.
        refused = outcome["refused"]
        self.assertEqual(["outcome_evaluation"], [entry["name"] for entry in refused["conditions"] if entry["verdict"] == "fail"])
        self.assertEqual({"pass"}, {entry["verdict"] for entry in refused["conditions"][:3]})
        # One round, one repair, published by the flow and delivered like any ticket.
        self.assertEqual((1, None), (outcome["end_rounds"], outcome["end_stop"]))
        [repair] = outcome["repairs"]
        self.assertEqual(("repair", DELIVERY_STATES, True), (repair["kind"], repair["lifecycle"], repair["closed_by_the_gate"]))
        self.assertNotIn(repair["id"], outcome["published"])
        # The whole gate replayed on the tip the repair left: its seven conditions, there.
        gate = outcome["spec_end"]
        self.assertEqual((True, True, True), (gate["at_the_tip"], gate["holds_every_repair"], gate["delivered"]))
        self.assertEqual([(number, "pass") for number in range(1, 8)],
                         [(entry["number"], entry["verdict"]) for entry in gate["conditions"]])
        self.assertEqual([], gate["missing"])
        self.assertTrue(outcome["delivered"]["at_the_tip"])
        # Never Delivered before the repair was closed, nor while the gate named a condition.
        self.assertEqual(1, outcome["delivered"]["repairs_closed_when_first_seen"])
        self.assertGreater(outcome["delivered"]["checked"], 0)
        # The one request of the operator's list is the Acceptance Request of the Delivered Outcome (T28).
        self.assertEqual(1, outcome["requests"])
        self.assertEqual({"request": 1, "dossier_linked": True, "launched_at_dossier_commit": True, "stopped": True},
                         outcome["acceptance"])
        for read in ("spec-end check", "escalation-door list", "git rev-parse", "evidence-pack check",
                     "acceptance-session open", "acceptance-session close"):
            self.assertIn(read, result["interfaces"]["read"])
        # Nothing of the agents: the only session named is the command of the Acceptance Session.
        for hidden in ("prompt", "formula", "role", "session"):
            self.assertNotIn(hidden, proc.stdout.lower().replace("acceptance-session", ""))
        # No path, commit or time in the result.
        self.assertNotRegex(proc.stdout, r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])|/tmp/|\d{4}-\d{2}-\d{2}T")

    def test_a_delivered_outcome_with_another_number_of_repairs_than_expected_fails_the_oracle(self):
        # No story is left unobserved on the walk where nothing goes wrong: no repair is published.
        proc = self.deliver_expecting("one-ticket-end-to-end.json", outcome="delivered", repairs=1)

        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("", proc.stdout)
        self.assertIn("0 repair", proc.stderr)
        self.assertIn("expects 1", proc.stderr)

    def test_a_repaired_story_expected_without_a_repair_fails_the_oracle(self):
        proc = self.deliver_expecting("story-repaired-delivered.json", repairs=0)

        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("", proc.stdout)
        self.assertIn("1 repair", proc.stderr)
        self.assertIn("expects 0", proc.stderr)

    def test_the_walk_where_nothing_goes_wrong_is_delivered_without_a_repair_and_without_a_round(self):
        proc = self.deliver_expecting("one-ticket-end-to-end.json", outcome="delivered")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        outcome = json.loads(proc.stdout)["outcome"]

        self.assertEqual(("delivered", [], 0, None), tuple(outcome[name] for name in ("state", "repairs", "end_rounds", "end_stop")))
        self.assertNotIn("refused", outcome)
        self.assertTrue(outcome["spec_end"]["delivered"])
        # After the Delivered Outcome the operator's list shows the Acceptance Request with the link of
        # the dossier; the session opens the product at the commit of the dossier, and closing it stops it (T28).
        self.assertEqual(1, outcome["requests"])
        self.assertEqual({"request": 1, "dossier_linked": True, "launched_at_dossier_commit": True, "stopped": True},
                         outcome["acceptance"])
        self.assertNotRegex(proc.stdout, r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])|/tmp/|\d{4}-\d{2}-\d{2}T|127\.0\.0\.1")
        # The scenario that asks for no outcome keeps the result it had: nothing of the end in it.
        plain = json.loads(self.deliver("one-ticket-end-to-end.json").stdout)
        self.assertNotIn("outcome", plain)
        self.assertNotIn("spec-end check", plain["interfaces"]["read"])
        self.assertNotIn("acceptance-session open", plain["interfaces"]["read"])


if __name__ == "__main__":
    unittest.main()
