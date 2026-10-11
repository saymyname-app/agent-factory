#!/usr/bin/env python3
# ci: over-ceiling — cut from tests/fixture-city-oracle-parked-answer-author-gates-test.py, itself above the ceiling (CI01, af-q9urgr); its one long case walks the whole delivery flow three times
"""bin/fixture-city-oracle on the scenarios of tests/fixtures/fixture-city: the
cases of the ticket parked out of resumes with its descendant while the
other goes on, then the one grouped request (T20).

They were in tests/fixture-city-oracle-parked-answer-author-gates-test.py
(af-vqew1x: no test file should hold a lot of a CI run alone).
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
# named at the top of a file, and the cases of that file run there.
first = load("fixture-city-oracle-test.py")
DELIVERY_DRIVER = first.DELIVERY_DRIVER
DELIVERY_STATES = first.DELIVERY_STATES
ORACLE = first.ORACLE


class FixtureCityOracleTest(first.FixtureCityOracleHarness):
    # --- a ticket out of resumes is parked, the others go on, one grouped request (T20, af-y9pw9z) ---

    def test_a_ticket_that_fails_three_times_is_parked_with_its_descendant_while_the_other_goes_on_then_one_request(self):
        proc = self.deliver("three-failures-parked.json")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)
        self.assert_walked_through_the_gates_of_the_author(result, tickets=1)

        # The ticket that waits for no parked ticket walked the whole flow.
        self.assertTrue(result["closed"])
        self.assertEqual(DELIVERY_STATES, result["lifecycle"])
        parking = result["parking"]
        [sick] = [entry for entry in parking["parked"] if entry["origin"] == entry["id"]]
        [behind] = [entry for entry in parking["parked"] if entry["origin"] != entry["id"]]
        self.assertEqual(("resumes_exhausted", 3), (sick["cause"], sick["resumes"]))
        self.assertEqual((sick["id"], "resumes_exhausted"), (behind["origin"], behind["cause"]))
        # It went on after the parking, and was closed with the others still parked.
        self.assertIn("coded", parking["reached_after"])
        self.assertIn("closed", parking["reached_after"])
        # No request while a ticket could still advance; then exactly one, which names every parked ticket.
        self.assertEqual(0, parking["requests_before_only_parked_left"])
        self.assertEqual(1, parking["requests"])
        self.assertEqual(sorted([sick["id"], behind["id"]]), parking["named_by_the_request"])
        self.assertIn("escalation-door list", result["interfaces"]["read"])
        self.assertEqual(proc.stdout, self.deliver("three-failures-parked.json").stdout)

    def test_a_delivery_scenario_that_expects_parked_tickets_without_a_closed_one_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            broken = Path(temporary) / "broken.json"
            for expect in ({"closed": False, "missing": [1], "parked": 2}, {"closed": True, "parked": 0},
                           {"closed": True, "parked": "deux"}):
                broken.write_text(json.dumps({"contract": "agent-factory-fixture-delivery-scenario/v1",
                                              "scenario_id": "broken", "expect": expect}))
                proc = subprocess.run((str(ORACLE), "run", str(broken), "--delivery-driver", str(DELIVERY_DRIVER)),
                                      cwd=ROOT, text=True, capture_output=True, check=False)
                self.assertEqual(1, proc.returncode, proc.stdout + proc.stderr)
                self.assertIn("expect.parked", proc.stderr)


if __name__ == "__main__":
    unittest.main()
