#!/usr/bin/env python3
# ci: over-ceiling — cut from tests/fixture-city-oracle-test.py, itself above the ceiling when it was set (CI01, af-q9urgr); each case walks the whole delivery flow of one ticket
"""bin/fixture-city-oracle on the scenarios of tests/fixtures/fixture-city: the
cases of the delivery of one ticket of a marked convoy, walked through the
whole delivery flow and closed by the ticket-end gate, on each project of
the fixture (T19, T35).

They were in tests/fixture-city-oracle-test.py (af-vqew1x: no test file should hold a lot of a CI run alone).
The harness is the one of that file, loaded from there."""

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
# named at the top of a file, and the cases of that file run there.
first = load("fixture-city-oracle-test.py")
DELIVERY_DRIVER = first.DELIVERY_DRIVER
DELIVERY_STATES = first.DELIVERY_STATES
FIXTURES = first.FIXTURES
GATE_CONDITIONS = first.GATE_CONDITIONS
ORACLE = first.ORACLE


class FixtureCityOracleTest(first.FixtureCityOracleHarness):
    # --- the delivery of one ticket of a marked convoy (T19, af-iefuud) ---------

    def test_one_ticket_walks_the_whole_flow_and_is_closed_by_the_ticket_end_gate(self):
        proc = self.deliver("one-ticket-end-to-end.json")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)
        self.assert_walked_through_the_gates_of_the_author(result, tickets=1)

        self.assertTrue(result["ok"])
        self.assertEqual(DELIVERY_STATES, result["lifecycle"])
        # Each state is observed once, in the order of the flow, on the
        # public state read after an event; none is skipped.
        self.assertEqual(DELIVERY_STATES, [state for seen in result["observations"] for state in seen])
        for alone in DELIVERY_STATES[:6]:
            self.assertIn([alone], result["observations"])
        self.assertTrue(result["closed"])
        gate = result["ticket_end"]
        self.assertEqual("ticket-end/v1", gate["version"])
        self.assertEqual([(number, name, "pass") for number, name in enumerate(GATE_CONDITIONS, start=1)],
                         [(entry["number"], entry["name"], entry["verdict"]) for entry in gate["conditions"]])
        self.assertTrue(result["evidence"]["verified"])
        for piece in ("tdd_red", "tdd_freeze", "tdd_green", "demonstration", "handoff_records", "fidelity", "merged_tests"):
            self.assertIn(piece, result["evidence"]["pieces"])
        # What the oracle reads is the public state, and nothing of the agents.
        self.assertEqual(["convoy-state show", "git merge-base", "ticket-end check", "evidence-capture verify"],
                         result["interfaces"]["read"])
        for hidden in ("prompt", "formula", "role", "session"):
            self.assertNotIn(hidden, proc.stdout.lower())
        # Equal public behavior gives an equal result: no path, commit or time in it.
        self.assertEqual(proc.stdout, self.deliver("one-ticket-end-to-end.json").stdout)

    def test_the_same_walk_with_a_condition_missing_leaves_the_ticket_open_and_the_gate_names_it(self):
        proc = self.deliver("one-ticket-missing-condition.json")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)

        self.assertFalse(result["closed"])
        self.assertEqual(DELIVERY_STATES[:7], result["lifecycle"])
        self.assertEqual([1, 6], result["ticket_end"]["missing"])
        verdicts = {entry["name"]: entry["verdict"] for entry in result["ticket_end"]["conditions"]}
        self.assertEqual(("fail", "fail"), (verdicts["criteria"], verdicts["merge"]))
        self.assertEqual({"pass"}, {verdict for name, verdict in verdicts.items() if name not in ("criteria", "merge")})
        self.assertNotIn("merged_tests", result["evidence"]["pieces"])

    def test_a_ticket_closed_outside_the_ticket_end_gate_fails_the_oracle(self):
        proc = self.deliver("one-ticket-closed-by-hand.json")

        self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("", proc.stdout)
        self.assertIn("closed outside the gate", proc.stderr)

    # --- the same walk on the second project of the fixture (T35, af-f62cxt) ------

    def test_one_ticket_of_the_second_project_walks_the_same_flow_and_is_closed_by_the_ticket_end_gate(self):
        proc = self.deliver("one-ticket-second-project.json")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)
        self.assert_walked_through_the_gates_of_the_author(result, tickets=1)

        self.assertTrue(result["ok"])
        self.assertEqual("delivery-fixture-city-api", result["project"])
        self.assertEqual(DELIVERY_STATES, result["lifecycle"])
        self.assertEqual(DELIVERY_STATES, [state for seen in result["observations"] for state in seen])
        self.assertTrue(result["closed"])
        gate = result["ticket_end"]
        self.assertEqual("ticket-end/v1", gate["version"])
        self.assertEqual([(number, name, "pass") for number, name in enumerate(GATE_CONDITIONS, start=1)],
                         [(entry["number"], entry["name"], entry["verdict"]) for entry in gate["conditions"]])
        self.assertTrue(result["evidence"]["verified"])
        for piece in ("tdd_red", "tdd_freeze", "tdd_green", "demonstration", "handoff_records", "merged_tests",
                      "evaluation.c1", "evaluation.demo"):
            self.assertIn(piece, result["evidence"]["pieces"])
        # Its interface is not a web page: no screen was compared to a prototype.
        self.assertNotIn("fidelity", result["evidence"]["pieces"])
        # The same flow as the first project: same states, observed at the
        # same events, and the same list of conditions with the same verdicts.
        first = json.loads(self.deliver("one-ticket-end-to-end.json").stdout)
        self.assertNotIn("project", first)
        for same in ("lifecycle", "observations", "closed", "ticket_end", "interfaces"):
            self.assertEqual(first[same], result[same], same)

    def test_a_delivery_scenario_naming_a_project_the_driver_does_not_know_fails_the_oracle(self):
        scenario = json.loads((FIXTURES / "one-ticket-second-project.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            for project, named in (("projet-inconnu", "projet-inconnu"), ("../ailleurs", "project"), (3, "project")):
                broken = Path(tmp) / "scenario.json"
                broken.write_text(json.dumps({**scenario, "project": project}))
                proc = subprocess.run((str(ORACLE), "run", str(broken), "--delivery-driver", str(DELIVERY_DRIVER)),
                                      cwd=ROOT, text=True, capture_output=True, check=False)
                self.assertEqual(1, proc.returncode, project)
                self.assertEqual("", proc.stdout)
                self.assertIn(named, proc.stderr)


if __name__ == "__main__":
    unittest.main()
