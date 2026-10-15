#!/usr/bin/env python3
# ci: over-ceiling — second half of tests/fixture-city-oracle-test.py, itself above the ceiling when it was set (CI01, af-q9urgr); each case walks the whole delivery flow
"""bin/fixture-city-oracle on the scenarios of tests/fixtures/fixture-city: the
cases of the ticket parked out of resumes (T20), of the convoy abandoned and
of the protected branch that moves before the answer (T30), and of the
author's step going through its real gates (T37).

The harness is the one of tests/fixture-city-oracle-test.py, loaded from
there: the launches of the oracle and the drivers made to go wrong (Spec
CI01, af-q9urgr: that file was the longest of the battery, cut in two; then
af-vqew1x, cut again). The cases of the answer « accepté » are in
tests/fixture-city-oracle-accepted-answer-test.py, those of the story
repaired then Delivered in
tests/fixture-city-oracle-repaired-delivered-test.py.

Since the second cut of af-vqew1x the cases of the parked ticket (T20) are
in tests/fixture-city-oracle-parked-test.py."""

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
# named at the top of a file, and the cases of the first half run there.
first = load("fixture-city-oracle-test.py")
ORACLE = first.ORACLE
FIXTURES = first.FIXTURES
OPERATOR = first.OPERATOR
DELIVERY_DRIVER = first.DELIVERY_DRIVER
DELIVERY_STATES = first.DELIVERY_STATES
AUTHOR_GATES = first.AUTHOR_GATES


class FixtureCityOracleTest(first.FixtureCityOracleHarness):
    # --- after Benjamin's answer: Delivered, then Accepted or abandoned (T30, af-vlzc6v) ---

    def test_an_abandoned_convoy_is_closed_with_its_reason_and_the_protected_branch_does_not_move(self):
        proc = self.deliver("outcome-abandoned.json")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        outcome = json.loads(proc.stdout)["outcome"]
        self.assert_walked_through_the_gates_of_the_author(json.loads(proc.stdout), tickets=1)

        self.assertEqual(("abandoned", ["delivered", "abandoned"]), (outcome["state"], outcome["states"]))
        closed = outcome["closed"]
        self.assertEqual(("abandoned", "benjamin"), (closed["how"], closed["approver"]))
        self.assertTrue(closed["said"].strip())
        # Nothing is merged, and the integration branch stays where the Outcome was Delivered.
        self.assertEqual({"moved_before_the_answer": False, "convoy_commits_before_the_answer": 0, "merges": 0,
                          "unchanged": True}, outcome["protected_branch"])
        self.assertEqual({"kept": True, "at_the_judged_commit": True}, outcome["integration_branch"])
        self.assertEqual(0, outcome["requests_once_closed"])
        self.assertNotRegex(proc.stdout, r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])|/tmp/|\d{4}-\d{2}-\d{2}T|127\.0\.0\.1")

    def test_a_protected_branch_that_moves_before_the_answer_is_recorded_fails_the_oracle(self):
        proc = self.deliver_with_a_faulty_driver("outcome-accepted.json", "protected-branch-moved")

        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("", proc.stdout)
        self.assertIn("the protected branch moved before « accepté » was recorded", proc.stderr)
        self.assertIn("commit(s) of the convoy", proc.stderr)

    def test_the_answer_of_the_owner_is_one_the_driver_plays_only_when_asked(self):
        proc = subprocess.run((str(DELIVERY_DRIVER), "--workspace", "/nonexistent", "prepare", "--help"),
                              text=True, capture_output=True, check=False)
        self.assertIn("--answer {none,accepted,abandoned}", proc.stdout)

    def test_the_injection_of_a_story_not_observed_is_one_the_oracle_and_its_driver_both_know(self):
        proc = subprocess.run((str(DELIVERY_DRIVER), "--workspace", "/nonexistent", "prepare", "--help"),
                              text=True, capture_output=True, check=False)
        self.assertIn("story-not-observed", proc.stdout)
        with tempfile.TemporaryDirectory() as temporary:
            broken = Path(temporary) / "broken.json"
            broken.write_text(json.dumps({"contract": "agent-factory-fixture-delivery-scenario/v1", "scenario_id": "broken",
                                          "inject": {"delivery": "inconnue"}, "expect": {"closed": True}}))
            proc = subprocess.run((str(ORACLE), "run", str(broken), "--delivery-driver", str(DELIVERY_DRIVER)),
                                  cwd=ROOT, text=True, capture_output=True, check=False)
            self.assertEqual(1, proc.returncode)
            self.assertIn("story-not-observed", proc.stderr)
            # The second project already serves the story the injection leaves unserved: the driver refuses it.
            given = json.loads((FIXTURES / "story-repaired-delivered.json").read_text())
            broken.write_text(json.dumps({**given, "project": "delivery-fixture-city-api"}))
            proc = subprocess.run((str(ORACLE), "run", str(broken), "--delivery-driver", str(DELIVERY_DRIVER)),
                                  cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(1, proc.returncode, proc.stdout)
        self.assertIn("delivery-fixture-city only", proc.stderr)

    def test_a_scenario_is_walked_only_with_the_adapters_of_its_contract(self):
        planning = ("--operator", str(OPERATOR), "--publication-door", str(OPERATOR))
        proc = self.deliver("one-ticket-end-to-end.json", *planning)
        self.assertEqual(1, proc.returncode, proc.stdout)
        self.assertIn("--delivery-driver", proc.stderr)
        proc = self.deliver("single-rig.json")
        self.assertEqual(1, proc.returncode, proc.stdout)
        self.assertIn("--operator", proc.stderr)

    def test_a_delivery_scenario_that_expects_a_closed_ticket_with_a_missing_condition_is_rejected(self):
        scenario = FIXTURES / "one-ticket-end-to-end.json"
        with tempfile.TemporaryDirectory() as tmp:
            for expect in ({"closed": True, "missing": [1]}, {"closed": False}, {"closed": False, "missing": [10]}):
                broken = Path(tmp) / "scenario.json"
                broken.write_text(json.dumps({**json.loads(scenario.read_text()), "expect": expect}))
                proc = subprocess.run((str(ORACLE), "run", str(broken), "--delivery-driver", str(DELIVERY_DRIVER)),
                                      cwd=ROOT, text=True, capture_output=True, check=False)
                self.assertEqual(1, proc.returncode, expect)
                self.assertIn("expect", proc.stderr)

    # --- the author's step goes through its real gates (T37, af-fg8lhx) ---

    def test_a_state_of_the_author_written_by_convoy_state_and_not_by_its_gate_fails_the_oracle(self):
        for fault, state, gate in (("red", "« rouge »", "tdd-step red"), ("freeze", "« gel »", "tdd-step freeze"),
                                   ("exit", "« terminé »", "ticket-exit exit")):
            with self.subTest(fault=fault):
                proc = self.deliver_with_a_direct_writer("one-ticket-end-to-end.json", fault)
                self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
                self.assertEqual("", proc.stdout)
                self.assertIn(f"the state {state} of ticket fx-t1 was written outside its gate ({gate})", proc.stderr)

    def test_the_commands_of_the_flow_are_the_ones_the_oracle_saw_run_not_the_ones_a_driver_declares(self):
        # A driver that answers with a list of commands of its own changes nothing of the result.
        with tempfile.TemporaryDirectory() as temporary:
            driver = Path(temporary) / "delivery-driver"
            driver.write_text(
                "#!/usr/bin/env python3\nimport json, subprocess, sys\n"
                f"proc = subprocess.run(({str(DELIVERY_DRIVER)!r}, *sys.argv[1:]), text=True, capture_output=True)\n"
                "if proc.returncode != 0:\n    raise SystemExit(proc.stderr or proc.stdout)\n"
                "print(json.dumps({**json.loads(proc.stdout), 'flow': ['tdd-step declared'], 'author_gates': 'declared'}))\n")
            driver.chmod(0o755)
            proc = self.deliver("one-ticket-missing-condition.json", "--delivery-driver", str(driver))
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)
        self.assertNotIn("declared", proc.stdout)
        # The ticket went through every gate of the author, and is not closed: none is counted.
        for gate in AUTHOR_GATES:
            self.assertIn(gate, result["interfaces"]["flow"])
        self.assertEqual({"tickets": 0, "commands": AUTHOR_GATES}, result["author_gates"])


if __name__ == "__main__":
    unittest.main()
