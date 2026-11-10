#!/usr/bin/env python3
"""bin/tdd-step on a repair whose criteria all hold at the start commit
(af-oa2ci4): a repair that only moves a proof -- it restores a rule of
docs/TEST_GUIDELINE.md -- goes on all satisfied and finishes once the
forbidden proof is removed; a repair of a behavior still stops, as a slice
does (tests/tdd-step-test.py). Same harness as tests/tdd-step-test.py,
loaded from there: command lines on a fake tracker state, the Delivery
Fixture City launched for real, the proofs filed for real."""

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

MOVES_A_PROOF, OF_A_BEHAVIOR, OF_ANOTHER_RULE = "fx-r1", "fx-r2", "fx-r3"
OLD_PROOF = "tests/old-health-test.py"


def repair(restores):
    return f"""## What to build

Le contrôle de santé se prouve par la route servie.

## Restores

{restores}

## Acceptance criteria

- [ ] Point d'entrée : GET /health — Observable : champ status — Faux si : il n'est prouvé que par une fonction interne

## Target rigs

delivery-fixture-city"""


class ProofMoveTest(first.TddStepTest):
    def repair_tickets(self):
        return {
            MOVES_A_PROOF: repair("repo_rule : docs/TEST_GUIDELINE.md : The internal functions stay forbidden: "
                                  "a test that calls one is not a test of the tool."),
            OF_A_BEHAVIOR: repair("spec_line : le contrôle de santé répond ok"),
            OF_ANOTHER_RULE: repair("repo_rule : AGENTS.md : Architecture changes update durable documentation "
                                    "in the same change"),
        }

    def all_green(self):
        """The forbidden proof is in the product at the start commit; the
        author committed the black-box test of the one criterion, already
        green there."""
        self.base = self.commit("ancienne preuve", {OLD_PROOF: "# appelle une fonction interne\n"})
        self.commit_tests({first.HEALTH_FILE: first.HEALTH_TEST_ALREADY_GREEN},
                          table=self.table({"1": [first.HEALTH_ID]}))

    def test_a_repair_that_moves_a_proof_goes_on_all_green_and_finishes_once_the_old_proof_is_removed(self):
        self.all_green()

        self.red(MOVES_A_PROOF)

        self.assertIsNone(self.ticket_state(MOVES_A_PROOF)["stop"])
        _, red = self.piece("tdd_red", MOVES_A_PROOF)
        self.assertEqual(("red", self.base, ["1"]), (red["verdict"], red["base"], red["satisfied"]))
        self.assertEqual({first.HEALTH_ID: "passed"}, {test["id"]: test["outcome"] for test in red["tests"]})
        self.ok("freeze", MOVES_A_PROOF)
        head = self.commit("ancienne preuve retirée", remove=[OLD_PROOF])

        self.ok("green", MOVES_A_PROOF)

        self.assertEqual(head, self.ticket_state(MOVES_A_PROOF)["tdd"]["green"]["commit"])
        _, green = self.piece("tdd_green", MOVES_A_PROOF)
        self.assertEqual(("green", ["1"]), (green["verdict"], green["satisfied"]))
        self.assertEqual({"tdd_red", "tdd_freeze", "tdd_green"}, self.verified(MOVES_A_PROOF))

    def test_a_repair_of_a_behavior_or_of_another_rule_whose_criteria_are_all_green_still_stops(self):
        self.all_green()

        for ticket in (OF_A_BEHAVIOR, OF_ANOTHER_RULE):
            with self.subTest(ticket=ticket):
                proc = self.run_tool("red", ticket, "--base", self.base, "--table", first.TABLE)
                self.assertEqual(first.EXIT_STOPPED, proc.returncode, proc.stdout + proc.stderr)
                self.assertIn("critère 1 déjà vert", json.loads(proc.stdout)["error"])
                self.assertEqual("criterion_already_green", self.ticket_state(ticket)["stop"]["reason"])


def load_tests(loader, tests, pattern):
    """Only the cases written here: those of the harness run in their own file."""
    return unittest.TestSuite(ProofMoveTest(name) for name in loader.getTestCaseNames(ProofMoveTest)
                              if name in vars(ProofMoveTest))


if __name__ == "__main__":
    unittest.main()
