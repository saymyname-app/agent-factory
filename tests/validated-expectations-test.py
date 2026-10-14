#!/usr/bin/env python3
"""Validated scalar expectations gate the assembled product's verdict."""

import hashlib
import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("outcome_expectation_harness", str(ROOT / "tests/outcome-evaluation-test.py"))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)


class ValidatedExpectationsTest(module.Harness):
    def expect(self, brief, expected=...):
        story = brief["stories"][2]
        item = {
            "scope": "outcome", "owner": module.CONVOY, "number": story["number"], "text": story["text"], "dataset": "content",
            "source": {"reference": "validated factory-suspended scenario",
                       "digest": "sha256:" + hashlib.sha256(b"approved scenario").hexdigest()},
            "observation": {"path": "/status", "pointer": "/suspended"},
        }
        if expected is not ...:
            item["expected"] = expected
        for path in (self.outcome_profile, self.root / "config/project-descriptors/fx.json"):
            profile = json.loads(path.read_text())
            profile["validated_expectations"] = [item]
            path.write_text(json.dumps(profile))
        status, refreshed = self.tool("brief", "--profile", self.outcome_profile, env=self.session)
        self.assertEqual(0, status, refreshed)
        self.assertEqual(brief["commit"], refreshed["expectations"][0]["commit"])
        return refreshed

    def comparison(self, brief):
        product = brief["environments"][0]
        piece = "outcome.expected.suspended"
        proc = self.run_cmd(module.gate.CAPTURE_TOOL, "command", module.CONVOY, module.CONVOY,
                            "--piece", piece, "--launch-state", product["launch_state"], "--",
                            sys.executable, "-c", brief["capture"]["page"][-2], product["address"] + "/status",
                            env=self.session)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        return [{"id": brief["expectations"][0]["id"], "evidence": piece}]

    def test_unrelated_ticket_with_same_number_is_ignored(self):
        sys.path.insert(0, str(ROOT / "lib"))
        from validated_expectations import planned
        current = {"number": 1, "text": "current"}
        profile = {"validated_expectations": [
            {"scope": "ticket", "owner": "another-ticket", "number": 1, "text": "other"}]}
        self.assertEqual([], planned(profile, "ticket", [current], ["content"], "abc", "current-ticket"))

    def test_current_t01r2_keeps_the_approved_journal_comparison(self):
        sys.path.insert(0, str(ROOT / "lib"))
        from validated_expectations import planned
        profile = json.loads((ROOT / "config/project-descriptors/agent-factory.json").read_text())
        criterion = ("Point d'entrée : bin/project-launch start puis URL annoncée — Observable : "
                     "Le vrai cockpit répond à GET / et GET /api/status au commit demandé sur port isolé ; "
                     "son état provient du dataset nommé. — Faux si : Révision erronée, page de remplacement, "
                     "source live ou réponse absente.")
        entries = planned(profile, "ticket", [{"number": 1, "text": criterion}],
                          ["journal-content"], "4bf4fbf3ba28ba502bbf1dc014a63ae259b2f9f1", "af-6a98ip")
        self.assertEqual([("journal-content", "Deux améliorations proposées après une revue")],
                         [(entry["dataset"], entry["expected"]) for entry in entries if "gap" not in entry])

    def test_planning_gap_takes_precedence_over_other_comparison(self):
        sys.path.insert(0, str(ROOT / "lib"))
        from validated_expectations import enforce
        entries = [{"id": 1, "number": 3, "gap": "missing expected"},
                   {"id": 2, "number": 3, "dataset": "content", "expected": True,
                    "observation": {"path": "/status", "pointer": "/suspended"}}]
        given = {"stories": [{"number": 3, "state": "observed"}],
                 "comparisons": [{"id": 2, "evidence": "any"}]}
        result, failures = enforce(entries, given, "stories", lambda *_: self.fail("must not verify"), "")
        self.assertEqual([], failures)
        self.assertEqual("unobservable", result["stories"][0]["state"])
        self.assertEqual("criterion", result["stories"][0]["cause"])

    def test_fabricated_prefix_cannot_pass_as_product_capture(self):
        sys.path.insert(0, str(ROOT / "lib"))
        from validated_expectations import observed_value
        fetch = "trusted fetch code"
        record = {"kind": "command", "address": "http://127.0.0.1:8000",
                  "exit_code": 0, "output_truncated": False,
                  "command": [sys.executable, "-c", "print('200')", "-c", fetch,
                              "http://127.0.0.1:8000/status"],
                  "output": '200\n{"suspended": true}'}
        with self.assertRaisesRegex(ValueError, "declared product URL"):
            observed_value(record, record["address"],
                           {"path": "/status", "pointer": "/suspended"}, fetch)

    def test_validated_false_matches_served_false(self):
        brief = self.expect(self.opened(), False)
        result = self.result(brief, comparisons=self.comparison(brief))
        self.record(result)
        self.assertEqual("favorable", self.outcome()["rounds"][0]["outcome"])

    def test_validated_true_refuses_served_false_even_when_evaluator_claims_observed(self):
        brief = self.expect(self.opened(), True)
        result = self.result(brief, comparisons=self.comparison(brief))
        self.record(result)
        round_ = self.outcome()["rounds"][0]
        self.assertEqual("repair", round_["outcome"])
        self.assertEqual("not_observed", round_["stories"][2]["state"])
        self.assertIn("servi False", round_["stories"][2]["reason"])
        self.assertEqual(3, round_["repairs"][0]["story"])

    def test_missing_validated_value_is_a_planning_exception(self):
        brief = self.expect(self.opened())
        self.assertIn("gap", brief["expectations"][0])
        self.record(self.result(brief))
        round_ = self.outcome()["rounds"][0]
        self.assertEqual("planning_exception", round_["outcome"])
        self.assertEqual("criterion", round_["stories"][2]["cause"])


if __name__ == "__main__":
    import unittest
    unittest.main()
