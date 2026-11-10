#!/usr/bin/env python3
"""bin/outcome-evaluation, every declared dataset open to the Evaluator of
the end, and the stop « story_unobservable » the factory caused lifted by
code (af-ip0nrq; Benjamin, 2026-11-09 21:53 Paris: « Oui, ouvre-les »).

An « unobservable » is handed in with the declared datasets opened to look
for its story, else `record` refuses it. A stop on an unobservable story a
Factory maintenance is linked to (bin/convoy-state link-outcome-repair) is
lifted by `settle` once that maintenance is merged with its CI proven: its
request leaves the operator's list without an answer, the evaluation is
made again at the same commit, and no round of the end is taken.

The decor is the one of tests/outcome-evaluation-test.py: the verified
convoy of the gate's suite, its product launched by the real
bin/project-launch, every piece captured by the real bin/evidence-capture,
the request read back from the real bin/escalation-door."""

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
MAINTENANCE = "fx-maint"
COUNTER = "gc.flow.counter.end_rounds"
UNOBSERVABLE = {"cause": "criterion", "reason": "aucun jeu ouvert ne montre la situation de la story"}


def delivered(number, head, merge):
    return {
        "gc.delivery_contract": "pr-ci-merged-v1", "gc.authorized_by": "operator-intent: fixture",
        "gc.delivery_status": "merged", "gc.work_outcome": "shipped",
        "gc.github_repo": "example/factory", "gc.pr_number": number,
        "gc.pr_head": head, "gc.merge_commit": merge,
        "gc.pr_url": f"https://github.com/example/factory/pull/{number}",
        "pr_number": number, "merge_result": "merged", "merged_sha": merge,
        "merged_target": "main", "gc.required_ci_workflow": "Factory CI",
        "gc.ci_run_id": number, "gc.ci_head_sha": head, "gc.ci_conclusion": "success",
    }


class OutcomeEvaluationEveryDatasetTest(outcome.Harness):
    def write_bead(self, bead_id, **fields):
        state = json.loads(self.tracker.read_text())
        state["beads"][bead_id] = {**state["beads"].get(bead_id, {}), **fields}
        self.tracker.write_text(json.dumps(state))

    def test_an_unobservable_without_a_dataset_tried_or_on_one_never_opened_is_refused(self):
        brief = self.opened()
        self.assertEqual((["content"], ["content"]), (brief["datasets"], brief["cited"]))
        result = self.result(brief)
        result["stories"][2].update(state="unobservable", **UNOBSERVABLE)

        answer = self.assert_record_refused(result, "user story 3", "tried")

        self.assertNotIn("jamais ouvert", answer["error"])
        result["stories"][2]["tried"] = ["empty"]
        self.assert_record_refused(result, "user story 3", "jamais ouvert", "empty")
        result["stories"][2]["tried"] = ["content"]
        self.assertEqual("planning_exception", self.record(result)["outcome"])
        self.assertEqual(["content"], self.outcome()["rounds"][0]["stories"][2]["tried"])

    def test_a_stop_linked_to_a_delivered_maintenance_is_lifted_and_evaluated_again_without_a_round_of_the_end(self):
        commit = self.verified()
        self.write_bead(CONVOY, metadata={**self.metadata(CONVOY), COUNTER: 1})
        self.write_bead(MAINTENANCE, title="Ouvrir tous les jeux", status="open", issue_type="bug",
                        labels=["maintenance"], metadata={"gc.authorized_by": "operator-intent: fixture"})
        # Story 3 unobservable on the one dataset opened, story 2 not observed.
        self.evaluator({"stories": {"3": {"unobservable": {**UNOBSERVABLE, "tried": ["content"]}},
                                    "2": {"path": "/absent", "look_for": "rien"}}})
        self.assertEqual("launched", self.settle()["action"])
        self.assertEqual("stopped", self.settle()["action"])
        stop = self.outcome()["stop"]
        self.assertEqual(("story_unobservable", commit), (stop["reason"], stop["commit"]))
        self.assertIn("raised", stop)
        self.assertNotEqual("none", self.metadata(CONVOY)["gc.needs_benjamin"])
        self.assertEqual((2, commit), (self.metadata(CONVOY)[COUNTER],
                                       json.loads(self.metadata(CONVOY)["gc.flow.end_round"])["commit"]))
        self.state("link-outcome-repair", CONVOY, "--repair", MAINTENANCE)

        # Linked, not delivered: the stop waits, and its request stays on the list.
        self.assertEqual("none", self.settle()["action"])
        self.assertEqual([MAINTENANCE], [entry["id"] for entry in self.outcome()["stop"]["repairs"]])
        self.write_bead(MAINTENANCE, status="closed", metadata=delivered("901", "a" * 40, "b" * 40))
        self.evaluator({"stories": {"2": {"path": "/absent", "look_for": "rien"}}})
        lifted = self.settle()

        self.assertEqual(("launched", commit, [MAINTENANCE]), (lifted["action"], lifted["commit"], lifted["lifted"]))
        shown = self.outcome()
        self.assertIsNone(shown["stop"])
        self.assertEqual([("planning_exception", commit), ("repair", commit)],
                         [(round_["outcome"], round_["commit"]) for round_ in shown["rounds"]])
        metadata = self.metadata(CONVOY)
        self.assertEqual("none", metadata["gc.needs_benjamin"])
        self.assertNotIn("gc.escalation_response_option", metadata)
        # No round of the end for a stop the factory caused, though the bound (2) is reached.
        self.assertEqual(2, metadata[COUNTER])
        self.assertNotIn("gc.flow.end_stop", metadata)
        record = json.loads(metadata["gc.flow.outcome_evaluation"])
        self.assertEqual([("story_unobservable", commit, [MAINTENANCE])],
                         [(lift["reason"], lift["commit"], lift["repairs"]) for lift in record["lifts"]])
        self.assertEqual("none", self.settle()["action"])

    def test_only_a_stop_on_an_unobservable_story_is_linked_and_only_to_a_provable_repair(self):
        self.verified()
        self.write_bead(MAINTENANCE, title="Note", status="open", issue_type="task", metadata={})

        proc = self.run_cmd(gate.STATE_TOOL, "link-outcome-repair", CONVOY, "--repair", MAINTENANCE)

        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout)
        self.assertIn("inobservable", json.loads(proc.stdout)["error"])
        self.evaluator({"stories": {"3": {"unobservable": {**UNOBSERVABLE, "tried": ["content"]}}}})
        self.settle()
        self.assertEqual("stopped", self.settle()["action"])
        before = self.snapshot()
        proc = self.run_cmd(gate.STATE_TOOL, "link-outcome-repair", CONVOY, "--repair", MAINTENANCE)
        self.assertEqual(EXIT_REFUSED, proc.returncode, proc.stdout)
        self.assertIn("maintenance autorisée", json.loads(proc.stdout)["error"])
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
