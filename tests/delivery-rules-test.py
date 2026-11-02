#!/usr/bin/env python3
"""Category R: each known duplicated delivery rule has one shared function."""

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from delivery_rules import evaluation_proven_by_test, names_in_texts, review_replay_due, tdd_evidence_piece  # noqa: E402


RULE_READERS = {
    "review_replay_due": (
        ("bin/code-review", "wanted_round"),
        ("lib/convoy_state.py", "cmd_open_code_review"),
    ),
    "tdd_evidence_piece": (
        ("bin/ticket-end", "condition_handoff"),
        ("bin/ticket-end", "condition_tdd"),
        ("bin/tdd-step", "check_freeze"),
    ),
    "names_in_texts": (
        ("bin/ticket-evaluation", "Convoy.datasets"),
        ("bin/ticket-end", "named_states"),
    ),
    "evaluation_proven_by_test": (
        ("lib/convoy_state.py", "cmd_record_evaluation"),
        ("bin/ticket-end", "condition_evaluation"),
    ),
}


def function_at(path: Path, qualified_name: str) -> ast.FunctionDef:
    nodes = [ast.parse(path.read_text(encoding="utf-8"))]
    for part in qualified_name.split("."):
        nodes = [child for parent in nodes for child in parent.body
                 if isinstance(child, (ast.ClassDef, ast.FunctionDef)) and child.name == part]
    if len(nodes) != 1 or not isinstance(nodes[0], ast.FunctionDef):
        raise AssertionError(f"{path.relative_to(ROOT)}: fonction {qualified_name} absente ou ambiguë")
    return nodes[0]


def calls(node: ast.AST, name: str) -> bool:
    return any(isinstance(call.func, ast.Name) and call.func.id == name
               for call in ast.walk(node) if isinstance(call, ast.Call))


class SharedRules(unittest.TestCase):
    def test_review_replay_rule(self):
        review = {"kind": "review", "commit": "old", "responses": {}}
        judgement = {"kind": "judgement", "commit": "old"}
        self.assertTrue(review_replay_due(review, "tip", None, ["F1"], []))
        self.assertFalse(review_replay_due(review, "tip", "correction", ["F1"], []))
        self.assertTrue(review_replay_due(judgement, "tip", "old", ["F1"], []))
        self.assertTrue(review_replay_due(judgement, "tip", None, ["F1"], ["F1"]))
        self.assertFalse(review_replay_due(judgement, "old", "old", ["F1"], ["F1"]))

    def test_amended_red_piece(self):
        amended = {"red": {"commit": "new"}, "amendment": {"commit": "new"}}
        first = {"red": {"commit": "old"}, "amendment": {"commit": "new"}}
        self.assertEqual(tdd_evidence_piece(amended, "red"), "tdd_amendment")
        self.assertEqual(tdd_evidence_piece(first, "red"), "tdd_red")
        self.assertEqual(tdd_evidence_piece({}, "red"), "tdd_red")
        self.assertEqual(tdd_evidence_piece(amended, "green"), "tdd_green")

    def test_names_are_whole_identifiers(self):
        candidates = ["A", "state-one", "state"]
        self.assertEqual(names_in_texts(candidates, ["A and state-one, not estate or state-two"]),
                         ["A", "state-one"])

    def test_proven_by_test_is_exact_current_and_from_the_answered_lift(self):
        item = {"text": "la ligne", "state": "unobservable", "cause": "criterion"}
        refused = {"kind": "evaluation", "commit": "a" * 40, "criteria": [], "demonstration_line": item,
                   "outcome": "planning_exception", "at": "2026-10-30T10:00:00Z"}
        replay = {**refused, "outcome": "favorable", "at": "2026-10-30T10:03:00Z"}
        lift = {"cause": "planning_exception", "option": "a", "parked_at": "2026-10-30T10:01:00Z",
                "at": "2026-10-30T10:02:00Z",
                "proven_by_test": [{"what": "ligne de démonstration", "text": "la ligne"}]}
        self.assertEqual(["ligne de démonstration"], evaluation_proven_by_test(replay, [refused], [lift]))
        for name, changed in (
            ("absent", []),
            ("unanswered", [{**lift, "option": "b"}]),
            ("stale", [{**lift, "at": "2026-10-30T10:04:00Z"}]),
            ("different text", [{**lift, "proven_by_test": [
                {"what": "ligne de démonstration", "text": "une autre ligne"}]}]),
        ):
            with self.subTest(name=name):
                self.assertEqual([], evaluation_proven_by_test(replay, [refused], changed))
        self.assertEqual([], evaluation_proven_by_test(
            {**replay, "commit": "b" * 40}, [refused], [lift]))

    def test_proven_by_test_migrates_the_r3_and_d_decisions_only_to_a_green_tip(self):
        item = {"text": "la ligne", "state": "unobservable", "cause": "criterion"}
        lift = {"cause": "planning_exception", "option": "a", "parked_at": "2026-10-21T10:01:00Z",
                "at": "2026-10-21T10:02:00Z",
                "proven_by_test": [{"what": "ligne de démonstration", "text": "la ligne"}]}
        histories = {
            # af-plu8kn: refusal and answered replay at cbf516…, then a new-tip replay at aeb0c5….
            "R3": ["cbf516a2760aeb6da72944f5fb93f7d22ac27778",
                   "cbf516a2760aeb6da72944f5fb93f7d22ac27778",
                   "aeb0c5e74f36c2f9d8caf230fb04794e26c9960e"],
            # af-ten1sp: the same decision survived several evaluations and commit changes up to 62660d….
            "D": ["95462ee4d7bb5092e49979586172a55c0ed1c027",
                  "95462ee4d7bb5092e49979586172a55c0ed1c027",
                  "7f9313b62664632082d3736c1f6257a2cb6655e8",
                  "548d0b54d3345b97c52af800787f22702e17cbf2",
                  "62660d5d45b8248cf9463343d98d74f70a87239b"],
        }
        for name, commits in histories.items():
            with self.subTest(history=name):
                rounds = [
                    {"kind": "evaluation", "commit": commit, "criteria": [], "demonstration_line": item,
                     "outcome": "planning_exception" if index == 0 else "favorable",
                     "proven_by_test": ["ligne de démonstration"] if index else None,
                     "at": f"2026-10-2{index + 1}T10:0{index}:00Z"}
                    for index, commit in enumerate(commits)
                ]
                rounds[0].pop("proven_by_test")
                current, previous = rounds[-1], rounds[:-1]
                tip = current["commit"]

                self.assertGreaterEqual(len(rounds), 2)
                self.assertGreater(len(set(commits)), 1)
                self.assertEqual(["ligne de démonstration"],
                                 evaluation_proven_by_test(current, previous, [lift], tip))
                self.assertEqual([], evaluation_proven_by_test(current, previous, [], tip),
                                 "un verdict favorable historique seul ne migre aucune preuve")
                self.assertEqual([], evaluation_proven_by_test(current, previous, [lift], commits[0]),
                                 "le vert doit être prouvé à la pointe actuelle")


class OneRuleOneFunctionLint(unittest.TestCase):
    def test_every_known_reader_calls_its_shared_rule(self):
        for rule, readers in RULE_READERS.items():
            for relative, function in readers:
                with self.subTest(rule=rule, reader=f"{relative}:{function}"):
                    self.assertTrue(calls(function_at(ROOT / relative, function), rule),
                                    f"{relative}:{function} ne lit plus la règle commune {rule}")


if __name__ == "__main__":
    unittest.main()
