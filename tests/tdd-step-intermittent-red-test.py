#!/usr/bin/env python3
"""bin/tdd-step red on a criterion test that passes by luck at the start
commit (af-batj8g): R23 (af-ujme6p) was stopped « déjà vert » on one pass of
a test red 7 times out of 8. A test that passes is run again, up to the
profile's k runs; one run that fails makes it red, and only a test that
passed at each run is green. Same harness as tests/tdd-step-test.py, loaded
from there: command lines on a fake tracker state, the Delivery Fixture City
launched for real, the proofs filed for real."""

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


# The module is bound, not its classes: unittest would run the cases of
# tests/tdd-step-test.py here too.
first = load("tdd-step-test.py")

# Passes at its first run only: it then asks what the start commit does not
# serve, like a test whose red depends on what an earlier run left behind.
HEALTH_TEST_GREEN_ONCE = """import json
import os
import pathlib
import unittest
import urllib.request


class HealthTest(unittest.TestCase):
    def test_dataset_is_named(self):
        body = json.loads(urllib.request.urlopen(os.environ["PRODUCT_ADDRESS"] + "/health").read())
        ran = pathlib.Path(__file__).with_suffix(".ran")
        if not ran.exists():
            ran.write_text("")
            self.assertEqual("ok", body.get("status"))
        else:
            self.assertEqual("content", body.get("dataset"))
"""


class IntermittentRedTest(first.TddStepTest):
    def test_a_test_green_once_then_red_at_the_start_commit_is_red_not_already_green(self):
        self.commit_tests({first.HEALTH_FILE: HEALTH_TEST_GREEN_ONCE},
                          table=self.table({"1": [first.HEALTH_ID], "2": [first.HEALTH_ID]}))

        self.red()

        self.assertIsNone(self.ticket_state()["stop"])
        _, proof = self.piece("tdd_red")
        self.assertEqual([], proof["satisfied"])
        self.assertEqual([{"id": first.HEALTH_ID, "outcome": "failure", "runs": ["passed", "failure"]}],
                         [{key: test[key] for key in ("id", "outcome", "runs")} for test in proof["tests"]])

    def test_a_ticket_stops_already_green_only_on_a_test_that_passed_at_each_of_k_runs(self):
        self.commit_tests({first.HEALTH_FILE: first.HEALTH_TEST_ALREADY_GREEN},
                          table=self.table({"1": [first.HEALTH_ID], "2": [first.HEALTH_ID]}))

        proc = self.run_tool("red", first.SLICE, "--base", self.base, "--table", first.TABLE,
                             profile=self.descriptor(k=2))

        self.assertEqual(first.EXIT_STOPPED, proc.returncode, proc.stdout + proc.stderr)
        detail = " ; ".join(f"critère {number} déjà vert : {first.HEALTH_ID} passe au commit de départ "
                            "à chacune de ses 2 exécutions" for number in (1, 2))
        self.assertEqual(f"refus : {detail}", json.loads(proc.stdout)["error"])
        self.assertEqual(("criterion_already_green", detail),
                         (self.ticket_state()["stop"]["reason"], self.ticket_state()["stop"]["detail"]))


def load_tests(loader, tests, pattern):
    """Only the cases written here: those of the harness run in their own file."""
    return unittest.TestSuite(IntermittentRedTest(name) for name in loader.getTestCaseNames(IntermittentRedTest)
                              if name in vars(IntermittentRedTest))


if __name__ == "__main__":
    unittest.main()
