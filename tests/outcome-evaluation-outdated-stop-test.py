#!/usr/bin/env python3
"""bin/outcome-evaluation, a stop at a commit the gate has left
(af-mmefvq; Benjamin, 2026-11-10 15:32 Paris: « gère les soucis pour moi »).

A stop of the Outcome Evaluation holds its commit only. Once the gate is
at another commit, `settle` sets it aside under `lifts`
(bin/convoy-state lift-outcome-stop --outdated-by), its request leaves the
operator's list without an answer, and the evaluation is made at the new
commit; no counter moves. At the commit of the gate the stop holds and its
request stays on the list.

The decor is the one of tests/outcome-evaluation-test.py: the verified
convoy of the gate's suite, its product launched by the real
bin/project-launch, the request read back from the real bin/escalation-door."""

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


outcome = load("outcome-evaluation-test.py")
gate = outcome.gate
CONVOY, EXIT_REFUSED = outcome.CONVOY, outcome.EXIT_REFUSED
COUNTER = "gc.flow.counter.end_rounds"
UNOBSERVABLE = {"cause": "criterion", "reason": "aucun jeu ouvert ne montre la situation de la story",
                "tried": ["content"]}


class OutcomeEvaluationOutdatedStopTest(outcome.Harness):
    def test_a_stop_the_gate_moved_past_leaves_the_list_without_an_answer_and_is_evaluated_at_the_new_tip(self):
        commit = self.verified()
        self.evaluator({"stories": {"3": {"unobservable": UNOBSERVABLE}}})
        self.settle()
        self.assertEqual("stopped", self.settle()["action"])
        request = self.metadata(CONVOY)["gc.needs_benjamin"]
        self.assertIn("user story inobservable", request)

        # At the commit of the gate the stop holds, and its request stays on the list.
        self.assertEqual("none", self.settle()["action"])
        self.assertEqual(request, self.metadata(CONVOY)["gc.needs_benjamin"])
        before = self.snapshot()
        proc = self.run_cmd(gate.STATE_TOOL, "lift-outcome-stop", CONVOY, "--commit", commit, "--outdated-by", commit)
        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout)
        self.assertIn("rien à lever", json.loads(proc.stdout)["error"])
        self.assertEqual(before, self.snapshot())

        self.note(gate.INTEGRATION)
        _, answer = self.run_gate()
        tip = answer["commit"]
        self.assertNotEqual(commit, tip)
        counter = self.metadata(CONVOY)[COUNTER]
        self.evaluator({})

        again = self.settle()

        self.assertEqual(("launched", tip), (again["action"], again["commit"]))
        self.assertEqual({"reason": "story_unobservable", "commit": commit, "outdated_by": tip}, again["outdated"])
        self.assertIsNone(self.outcome()["stop"])
        metadata = self.metadata(CONVOY)
        self.assertEqual("none", metadata["gc.needs_benjamin"])
        self.assertNotIn("gc.escalation_response_option", metadata)
        self.assertEqual(counter, metadata[COUNTER])
        record = json.loads(metadata["gc.flow.outcome_evaluation"])
        self.assertEqual([("story_unobservable", commit, tip)],
                         [(lift["reason"], lift["commit"], lift["outdated_by"]) for lift in record["lifts"]])
        self.assertNotIn("repairs", record["lifts"][0])


if __name__ == "__main__":
    unittest.main()
