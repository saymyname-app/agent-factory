#!/usr/bin/env python3
"""Category R: each known duplicated delivery rule has one shared function."""

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from delivery_rules import names_in_texts, review_replay_due, tdd_evidence_piece  # noqa: E402


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


class OneRuleOneFunctionLint(unittest.TestCase):
    def test_every_known_reader_calls_its_shared_rule(self):
        for rule, readers in RULE_READERS.items():
            for relative, function in readers:
                with self.subTest(rule=rule, reader=f"{relative}:{function}"):
                    self.assertTrue(calls(function_at(ROOT / relative, function), rule),
                                    f"{relative}:{function} ne lit plus la règle commune {rule}")


if __name__ == "__main__":
    unittest.main()
