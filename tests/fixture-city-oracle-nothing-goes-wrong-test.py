#!/usr/bin/env python3
"""bin/fixture-city-oracle on the scenarios of tests/fixtures/fixture-city: the
walk where nothing goes wrong, Delivered without a repair and without a
round (T26, T28).

The case was in tests/fixture-city-oracle-repaired-delivered-test.py
(af-vqew1x: no test file should hold a lot of a CI run alone).
The harness is the one of tests/fixture-city-oracle-test.py, loaded from
there."""

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
first = load("fixture-city-oracle-test.py")


class FixtureCityOracleTest(first.FixtureCityOracleHarness):
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
