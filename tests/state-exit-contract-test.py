#!/usr/bin/env python3
"""Category I: every stop, parking and offered option has an exit contract.

This is a structural control, not another simulation of the delivery flow.
The behavioural tests named by ``proof`` exercise the public commands.  This
table keeps their coverage closed over the reasons accepted by convoy-state
and over the option builders that reach Benjamin.  A deliberate gap stays
visible only as a dated exception naming the door that still owns it.
"""

from __future__ import annotations

import ast
import datetime as dt
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def transition(path: str, proof: str) -> dict[str, str]:
    return {"outcome": "transition", "path": path, "proof": proof}


def operator(gate: str) -> dict[str, str]:
    return {"outcome": "operator", "gate": gate}


AMENDMENT_PROOF = (
    "tests/convoy-advance-resumes-stops-end-test.py::"
    "test_an_exhausted_amendment_answered_a_is_resumed_once_and_its_stop_kept_on_the_resume"
)
STAGE_REMOVED_PROOF = "lib/convoy_state.py::\"stage_removed\": (\"test_review_refused\", \"test_review_no_result\")"
CODE_REVIEW_PROOF = "lib/convoy_state.py::\"code_review_no_result\": (\"code_review_no_result\",)"
EVALUATION_PROOF = "tests/convoy-state-test.py::test_open_resume_lifts_a_stop_without_evaluation_result_only_and_keeps_it"
OVERRIDE_PROOF = (
    "tests/convoy-advance-resumes-stops-end-test.py::"
    "test_a_ticket_stopped_still_refused_without_its_override_is_not_resumed_by_a_returned_merge"
)
NEW_TIP_PROOF = "lib/convoy_state.py::record.pop(\"stop\", None)"
LIFT_PROOF = "tests/convoy-state-test.py::test_lift_park_unparks_the_ticket_and_those_it_parked_and_keeps_the_record"
EXHAUSTED_PROOF = (
    "tests/convoy-advance-resumes-stops-end-test.py::"
    "test_the_answer_that_lifts_makes_the_ticket_and_its_descendants_startable_again"
)


# The keys are the public closed lists accepted by bin/convoy-state.  ``exit``
# covers the stop/parking itself; ``options`` covers every choice its request
# builder can offer.  ``*`` means any answer to an operator-authored request.
CONTRACT = {
    ("ticket_stop", "criterion_already_green"): {
        "exit": operator("Planning Run: close or revise the approved ticket"),
        "options": {
            "Clore ce ticket comme satisfait par le code existant":
                operator("Planning Run: close the ticket as already satisfied"),
            "Laisser le ticket arrêté": operator("escalation-door on the stopped ticket"),
        },
    },
    ("ticket_stop", "amendment_exhausted"): {
        "exit": transition("open-resume --cause amendment_granted", AMENDMENT_PROOF),
        "options": {
            "Accepter un amendement de plus de ses tests et faire reprendre le ticket":
                transition("open-resume --cause amendment_granted", AMENDMENT_PROOF),
            "Laisser le ticket arrêté": operator("escalation-door on the stopped ticket"),
        },
    },
    ("ticket_stop", "test_review_refused"): {
        "exit": transition("open-resume --cause stage_removed", STAGE_REMOVED_PROOF),
        "options": {
            "Accepter un amendement de plus de ses tests et faire reprendre le ticket":
                operator("Planning Run: the removed test-review stage cannot be resumed after its bound"),
            "Laisser le ticket arrêté": operator("escalation-door on the stopped ticket"),
        },
    },
    ("ticket_stop", "test_review_no_result"): {
        "exit": transition("open-resume --cause stage_removed", STAGE_REMOVED_PROOF),
        "options": {
            "Accepter un amendement de plus de ses tests et faire reprendre le ticket":
                operator("Planning Run: the removed test-review stage cannot be resumed after its bound"),
            "Laisser le ticket arrêté": operator("escalation-door on the stopped ticket"),
        },
    },
    ("ticket_stop", "code_review_no_result"): {
        "exit": transition("open-resume --cause code_review_no_result", CODE_REVIEW_PROOF),
        "options": {
            "Faire vérifier le rôle relecteur par la maintenance de l'usine":
                operator("escalation-door on the stopped ticket, after reviewer maintenance"),
            "Laisser le ticket arrêté": operator("escalation-door on the stopped ticket"),
        },
    },
    ("ticket_stop", "evaluation_no_result"): {
        "exit": transition("open-resume --cause evaluation_no_result on a new integration tip", EVALUATION_PROOF),
        "options": {
            "Faire vérifier le rôle Evaluator par la maintenance de l'usine":
                operator("escalation-door on the stopped ticket, after Evaluator maintenance"),
            "Laisser le ticket arrêté": operator("escalation-door on the stopped ticket"),
        },
    },
    ("ticket_stop", "evaluation_outage"): {
        "exit": operator("escalation-door on the stopped ticket, then Factory maintenance"),
        "options": {
            "Faire réparer l'environnement d'évaluation par la maintenance de l'usine":
                operator("escalation-door on the stopped ticket, then Factory maintenance"),
            "Laisser le ticket arrêté": operator("escalation-door on the stopped ticket"),
        },
    },
    ("ticket_stop", "still_refused"): {
        "exit": operator("Mayor arbitration, or Planning Run through correction-round escalate"),
        "options": {
            "Passer outre un Blocking Finding de la revue de code, avec tes mots":
                transition("correction-round override, then returned merge", OVERRIDE_PROOF),
            "Accorder le tour exceptionnel, avec tes mots (une fois par ticket)": transition(
                "correction-round grant --exceptional",
                "tests/correction-round-test.py::"
                "test_a_ticket_stopped_after_its_only_round_takes_the_round_the_bound_now_allows_once_its_approver_grants_it",
            ),
            "Ouvrir une Planning Exception": operator("Planning Run through correction-round escalate"),
            "Laisser le ticket arrêté": operator("escalation-door on the stopped ticket"),
        },
    },
    ("outcome_stop", "outcome_evaluation_no_result"): {
        "exit": transition("open-outcome-evaluation on a new integration tip", NEW_TIP_PROOF),
        "options": {
            "Faire vérifier le rôle Evaluator par la maintenance de l'usine":
                operator("Factory maintenance; the next integration tip reopens Outcome Evaluation"),
            "Laisser la fin de Spec arrêtée": operator("escalation-door on the stopped convoy"),
        },
    },
    ("outcome_stop", "outcome_evaluation_outage"): {
        "exit": transition("open-outcome-evaluation on a new integration tip", NEW_TIP_PROOF),
        "options": {
            "Faire réparer l'environnement d'évaluation par la maintenance de l'usine":
                operator("Factory maintenance; the next integration tip reopens Outcome Evaluation"),
            "Laisser la fin de Spec arrêtée": operator("escalation-door on the stopped convoy"),
        },
    },
    ("outcome_stop", "story_unobservable"): {
        "exit": operator("Planning Run on the stopped convoy"),
        "options": {
            "Trancher dans le Planning Run": operator("Planning Run: decide the unobservable story"),
            "Retirer la story par un graphe révisé": operator("Planning Run: revise the Spec and ticket graph"),
        },
    },
    ("park", "planning_exception"): {
        "exit": operator("escalation-door on the parked ticket"),
        "options": {
            "Juger ce qui est inobservable prouvé par son test de critère vert":
                transition("lift-park --option a", LIFT_PROOF),
            "Retirer le ticket du graphe": operator("Planning Run: revise the ticket graph"),
            "Réévaluer sur le produit relancé": transition("lift-park --option c and reevaluate", LIFT_PROOF),
        },
    },
    ("park", "operator_request"): {
        "exit": transition("lift-park after any answer, or after every linked repair is delivered", LIFT_PROOF),
        "options": {"*": transition("lift-park with the answered request", LIFT_PROOF)},
    },
    ("park", "resumes_exhausted"): {
        "exit": operator("grouped escalation-door request on the convoy"),
        "options": {
            "Relancer les tickets aux reprises épuisées":
                transition("lift-park from the grouped request", EXHAUSTED_PROOF),
            "Laisser ces tickets parqués": operator("grouped escalation-door request on the convoy"),
        },
    },
}


# These are the five open occurrences named by the class-I registry.  The
# date is when the complete control first made each gap explicit.  Removing a
# gap means removing it here and replacing its operator route above with a
# proved transition; adding an exception without a date makes this test fail.
DATED_EXCEPTIONS = {
    ("ticket_stop", "evaluation_outage"): ("2026-10-29", "ticket escalation-door + Factory maintenance"),
    ("ticket_stop", "criterion_already_green"): ("2026-10-29", "Planning Run"),
    ("outcome_stop", "outcome_evaluation_no_result"): ("2026-10-29", "next integration tip only"),
    ("outcome_stop", "outcome_evaluation_outage"): ("2026-10-29", "next integration tip only"),
    ("outcome_stop", "story_unobservable"): ("2026-10-29", "Planning Run"),
}


BUILDERS = {
    ("bin/convoy-advance", "tdd_stop_request"): ({2}, {
        ("ticket_stop", reason) for reason in
        ("criterion_already_green", "amendment_exhausted", "test_review_refused", "test_review_no_result")
    }),
    ("bin/code-review", "raise_stop"): ({2}, {("ticket_stop", "code_review_no_result")}),
    ("bin/ticket-evaluation", "raise_stop"): (
        {2}, {("ticket_stop", "evaluation_no_result"), ("ticket_stop", "evaluation_outage")}),
    ("bin/ticket-evaluation", "planning_exception_request"): ({3}, {("park", "planning_exception")}),
    ("bin/outcome-evaluation", "raise_stop"): (
        {2}, {("outcome_stop", reason) for reason in
              ("outcome_evaluation_no_result", "outcome_evaluation_outage", "story_unobservable")}),
    ("bin/correction-round", "operator_request"): ({3, 4}, {("ticket_stop", "still_refused")}),
    ("bin/convoy-advance", "grouped_request"): ({2}, {("park", "resumes_exhausted")}),
}


def literal_value(node: ast.AST, known: dict[str, object]) -> object:
    if isinstance(node, ast.Name) and node.id in known:
        return known[node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        return tuple(literal_value(item, known) for item in node.elts)
    return ast.literal_eval(node)


def literal_tuple(path: str, name: str) -> tuple[str, ...]:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    known: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            try:
                value = literal_value(node.value, known)
            except (ValueError, KeyError):
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    known[target.id] = value
                    if target.id == name:
                        return tuple(value)
    raise AssertionError(f"{path}: constante {name} absente")


def offered_counts(path: str, function: str) -> set[int]:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and node.name == function]
    if len(functions) != 1:
        raise AssertionError(f"{path}: fonction {function} absente ou dupliquée")
    counts = set()
    named: dict[str, set[int]] = {}
    for node in ast.walk(functions[0]):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if isinstance(node.value, ast.List):
                fixed = sum(not isinstance(item, ast.Starred) for item in node.value.elts)
                optional = sum(isinstance(item, ast.Starred) for item in node.value.elts)
                for target in targets:
                    if isinstance(target, ast.Name):
                        named.setdefault(target.id, set()).update(range(fixed, fixed + optional + 1))
    for node in ast.walk(functions[0]):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value == "que_faire" and isinstance(value, ast.List):
                fixed = sum(not isinstance(item, ast.Starred) for item in value.elts)
                optional = sum(isinstance(item, ast.Starred) for item in value.elts)
                counts.update(range(fixed, fixed + optional + 1))
            elif isinstance(key, ast.Constant) and key.value == "que_faire" and isinstance(value, ast.Name):
                counts.update(named.get(value.id, set()))
    if not counts:
        raise AssertionError(f"{path}:{function}: aucune liste que_faire littérale")
    return counts


class StateExitContractTest(unittest.TestCase):
    def test_every_public_reason_has_one_exit_and_every_option_has_an_outcome(self) -> None:
        expected = {
            *(('ticket_stop', reason) for reason in literal_tuple("lib/convoy_state.py", "STOP_REASONS")),
            *(('outcome_stop', reason) for reason in literal_tuple("lib/convoy_state.py", "OUTCOME_STOPS")),
            *(('park', reason) for reason in literal_tuple("lib/convoy_state.py", "PARK_CAUSES")),
        }
        self.assertEqual(expected, set(CONTRACT), "reason added/removed without updating the class-I exit table")
        for key, entry in CONTRACT.items():
            with self.subTest(reason=key):
                self.assertTrue(entry["options"], "an offered-option table cannot be empty")
                for route in (entry["exit"], *entry["options"].values()):
                    self.assertIn(route.get("outcome"), {"transition", "operator"})
                    self.assertTrue(route.get("proof") if route["outcome"] == "transition" else route.get("gate"))

    def test_every_transition_names_a_present_proof(self) -> None:
        for entry in CONTRACT.values():
            for route in (entry["exit"], *entry["options"].values()):
                if route["outcome"] != "transition":
                    continue
                path, marker = route["proof"].split("::", 1)
                with self.subTest(path=path, marker=marker):
                    source = (ROOT / path).read_text(encoding="utf-8")
                    self.assertIn(marker, source)

    def test_option_builders_and_the_table_have_the_same_cardinality(self) -> None:
        for (path, function), (expected_counts, reasons) in BUILDERS.items():
            with self.subTest(path=path, function=function):
                self.assertEqual(expected_counts, offered_counts(path, function))
                table_counts = {len(CONTRACT[reason]["options"]) for reason in reasons}
                if expected_counts == {3, 4}:
                    self.assertEqual({4}, table_counts, "the table names the optional exceptional grant too")
                else:
                    self.assertEqual(expected_counts, table_counts)
                source = (ROOT / path).read_text(encoding="utf-8")
                for reason in reasons:
                    for label in CONTRACT[reason]["options"]:
                        if label != "*":
                            self.assertIn(label, source, f"{reason}: offered option changed without updating its route")

    def test_each_known_open_occurrence_is_a_dated_exception_with_its_gate(self) -> None:
        self.assertEqual({
            ("ticket_stop", "evaluation_outage"),
            ("ticket_stop", "criterion_already_green"),
            ("outcome_stop", "outcome_evaluation_no_result"),
            ("outcome_stop", "outcome_evaluation_outage"),
            ("outcome_stop", "story_unobservable"),
        }, set(DATED_EXCEPTIONS))
        today = dt.date.today()
        for key, (written, gate) in DATED_EXCEPTIONS.items():
            with self.subTest(reason=key):
                self.assertIn(key, CONTRACT)
                self.assertLessEqual(dt.date.fromisoformat(written), today)
                self.assertTrue(gate.strip())
                routes = (CONTRACT[key]["exit"], *CONTRACT[key]["options"].values())
                self.assertTrue(any(route["outcome"] == "operator" for route in routes))

    def test_the_paused_order_gap_has_a_state_changing_door(self) -> None:
        proof = ROOT / "tests/order-pause-test.py"
        self.assertIn(
            "test_a_resume_closes_the_record_with_who_and_words_and_the_gate_runs_the_order_again",
            proof.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
