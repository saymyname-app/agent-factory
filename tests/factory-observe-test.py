#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "factory-observe"
POLICY = ROOT / "config" / "factory-observe-policy.json"

sys.path.insert(0, str(ROOT / "lib"))
import factory_observe as fo  # noqa: E402
import factory_measures as fm  # noqa: E402


class ToolMixin:
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="factory-observe-test-"))
        cleanup = lambda: subprocess.run(["rm", "-rf", str(self.tmp)])  # noqa: E731
        if hasattr(self, "addCleanup"):
            self.addCleanup(cleanup)
        else:
            self._cleanup = cleanup
        self.state_file = self.tmp / "state.json"

    def env(self, extra=None):
        base = {
            **os.environ,
            "FACTORY_OBSERVE_STATE_FILE": str(self.state_file),
            "FACTORY_OBSERVE_POLICY_FILE": str(POLICY),
        }
        base.update(extra or {})
        return base

    def write_json(self, name, payload):
        path = self.tmp / name
        path.write_text(json.dumps(payload))
        return path

    def run_tool(self, *args, env=None, check=False):
        return subprocess.run(
            (str(TOOL), *[str(a) for a in args]), text=True, capture_output=True, check=check,
            env=self.env(env),
        )


# --- AC1: repeated observation of unchanged state makes zero wakes ----------


class ZeroIdleCallTest(unittest.TestCase):
    def test_diff_of_identical_snapshots_is_empty(self):
        snap = {"delivery": {"af-x": {"status": "in_progress"}}}
        self.assertEqual(fo.diff_snapshot(snap, snap), [])
        self.assertEqual(fo.diff_snapshot(snap, dict(snap)), [])

    def test_observe_called_twice_with_unchanged_input_wakes_zero_both_times(self):
        policy = fo.validate_policy(json.loads(POLICY.read_text()))
        state = fo.empty_state()
        areas = {"delivery": {"af-x": {"status": "in_progress"}}}
        evidence = {}

        first = fo.observe(state, policy, areas, evidence, "2026-01-01T00:00:00Z")
        # First call against an empty prior snapshot IS a new fact -- it must wake.
        self.assertEqual(first["action"], "wake")
        self.assertEqual(len(first["wakes"]), 1)

        second = fo.observe(state, policy, areas, evidence, "2026-01-01T00:05:00Z")
        third = fo.observe(state, policy, areas, evidence, "2026-01-01T00:10:00Z")
        for result in (second, third):
            self.assertEqual(result["action"], "none")
            self.assertEqual(result["wakes"], [])
            self.assertEqual(result["exemption_transitions"], [])

    def test_cli_observe_twice_with_identical_snapshot_wakes_zero_the_second_time(self):
        with ToolCase() as case:
            snapshot = case.write_json("s.json", {"areas": {"delivery": {"af-x": {"status": "open"}}}})
            first = json.loads(case.run_tool("observe", "--snapshot", snapshot, check=True).stdout)
            self.assertEqual(first["action"], "wake")
            second = json.loads(case.run_tool("observe", "--snapshot", snapshot, check=True).stdout)
            self.assertEqual(second["action"], "none")
            self.assertEqual(second["wakes"], [])


class ToolCase(ToolMixin):
    """Reusable outside unittest.TestCase via context-manager protocol."""

    def __enter__(self):
        self.setUp()
        return self

    def __exit__(self, *exc):
        getattr(self, "_cleanup", lambda: None)()


# --- AC2: a new actionable fact wakes the smallest qualified role once, with evidence -----


class WakeQualificationTest(unittest.TestCase, ToolMixin):
    def setUp(self):
        ToolMixin.setUp(self)

    def test_new_delivery_fact_wakes_the_smaller_delivery_worker_role_not_the_mayor(self):
        policy = fo.validate_policy(json.loads(POLICY.read_text()))
        state = fo.empty_state()
        areas = {"delivery": {"af-x": {"status": "in_progress"}}}
        result = fo.observe(state, policy, areas, {}, "2026-01-01T00:00:00Z")
        self.assertEqual(result["action"], "wake")
        wake = result["wakes"][0]
        self.assertEqual(wake["role"], "delivery-worker")  # rank 1, not mayor (rank 2)
        self.assertEqual(wake["evidence"]["after"], {"status": "in_progress"})
        self.assertIsNone(wake["evidence"]["before"])

    def test_planning_run_fact_has_no_dedicated_worker_and_wakes_mayor(self):
        policy = fo.validate_policy(json.loads(POLICY.read_text()))
        state = fo.empty_state()
        areas = {"planning_runs": {"run-1": {"status": "open"}}}
        result = fo.observe(state, policy, areas, {}, "t")
        self.assertEqual(result["wakes"][0]["role"], "mayor")

    def test_unqualified_area_wakes_with_role_none_not_a_silent_fallback(self):
        policy = {"contract": fo.POLICY_CONTRACT, "roles": [
            {"name": "r1", "areas": ["delivery"], "rank": 1, "model": None, "effort": "low"},
        ], "exemptions": []}
        facts = fo.diff_snapshot({}, {"unmapped_area": {"x": {"a": 1}}})
        wakes = fo.plan_wakes(facts, policy)
        self.assertIsNone(wakes[0]["role"])

    def test_a_second_identical_fact_does_not_wake_again(self):
        policy = fo.validate_policy(json.loads(POLICY.read_text()))
        state = fo.empty_state()
        areas = {"delivery": {"af-x": {"status": "in_progress"}}}
        fo.observe(state, policy, areas, {}, "t1")
        repeat = fo.observe(state, policy, areas, {}, "t2")
        self.assertEqual(repeat["wakes"], [])

    def test_evidence_pointer_is_preserved_verbatim_across_state_persistence(self):
        with ToolCase() as case:
            snapshot = case.write_json("s.json", {
                "areas": {"delivery": {"af-x": {"status": "open", "detail": "spec drift"}}}
            })
            result = json.loads(case.run_tool("observe", "--snapshot", snapshot, check=True).stdout)
            self.assertEqual(
                result["wakes"][0]["evidence"]["after"],
                {"status": "open", "detail": "spec drift"},
            )


# --- AC3: measures separate by comparable work class ------------------------


class MeasuresTest(unittest.TestCase, ToolMixin):
    def setUp(self):
        ToolMixin.setUp(self)

    def measures_doc(self):
        return {
            "contract": fm.MEASURES_CONTRACT,
            "work_classes": {
                "simple": {
                    "lost_decisions": 0, "escaped_defects": 1, "human_rework": 2,
                    "maintainability": 0.9, "elapsed_seconds": 120, "tokens": 4000,
                },
                "wayfinding": {
                    "lost_decisions": 3, "escaped_defects": 0, "human_rework": 5,
                    "maintainability": 0.4, "elapsed_seconds": 900, "tokens": 40000,
                },
            },
        }

    def test_validate_accepts_a_complete_document(self):
        fm.validate_measures(self.measures_doc())  # no raise

    def test_validate_rejects_a_missing_key(self):
        doc = self.measures_doc()
        del doc["work_classes"]["simple"]["tokens"]
        with self.assertRaises(fm.MeasuresError):
            fm.validate_measures(doc)

    def test_two_work_classes_keep_distinct_values_no_cross_contamination(self):
        by_class = fm.aggregate_by_class(self.measures_doc())
        self.assertEqual(by_class["simple"]["escaped_defects"], 1)
        self.assertEqual(by_class["wayfinding"]["escaped_defects"], 0)
        self.assertNotEqual(by_class["simple"], by_class["wayfinding"])
        # mutating one class's returned dict must not touch the other
        by_class["simple"]["tokens"] = 999999
        self.assertEqual(by_class["wayfinding"]["tokens"], 40000)

    def test_compare_classes_reports_a_per_metric_delta_not_a_blended_total(self):
        delta = fm.compare_classes(self.measures_doc(), "wayfinding", "simple")
        self.assertEqual(delta["lost_decisions"], 3)
        self.assertEqual(delta["human_rework"], 3)

    def test_cli_measures_validate_and_show(self):
        measures = self.write_json("measures.json", self.measures_doc())
        ok = json.loads(self.run_tool("measures-validate", "--measures", measures, check=True).stdout)
        self.assertTrue(ok["ok"])
        shown = json.loads(self.run_tool("measures-show", "--measures", measures, check=True).stdout)
        self.assertEqual(set(shown["work_classes"]), {"simple", "wayfinding"})


# --- AC4: adaptation register entry exists and matches the field contract ---


class AdaptationRegisterTest(unittest.TestCase):
    def test_register_has_an_entry_for_this_adaptation(self):
        text = (ROOT / "docs" / "ADAPTATION_REGISTER.md").read_text(encoding="utf-8")
        self.assertIn("AR-004", text)
        for field in (
            "Statut", "Baseline", "But", "Adaptation sélectionnée",
            "Alternative maintenue viable", "Preuves", "Coût observé",
            "Réversibilité bornée", "Point de revue",
            "Règle conserver / remplacer / supprimer",
        ):
            self.assertIn(field, text)


# --- AC5: exemption/handoff activates only on evidence, restores on regression --


class ExemptionTest(unittest.TestCase):
    def entry(self):
        return {"name": "auto-x", "requires": ["signal_a", "signal_b"]}

    def test_no_activation_without_evidence(self):
        result = fo.evaluate_exemption(self.entry(), {})
        self.assertFalse(result["active"])
        self.assertEqual(sorted(result["missing"]), ["signal_a", "signal_b"])

    def test_no_activation_with_partial_evidence(self):
        result = fo.evaluate_exemption(self.entry(), {"signal_a": True})
        self.assertFalse(result["active"])
        self.assertEqual(result["missing"], ["signal_b"])

    def test_activates_when_all_required_evidence_holds(self):
        result = fo.evaluate_exemption(self.entry(), {"signal_a": True, "signal_b": True})
        self.assertTrue(result["active"])
        self.assertEqual(result["missing"], [])

    def test_apply_exemptions_records_one_activation_transition_then_none(self):
        policy = {"contract": fo.POLICY_CONTRACT, "roles": [
            {"name": "r1", "areas": ["delivery"], "rank": 1, "model": None, "effort": "low"},
        ], "exemptions": [self.entry()]}
        state = fo.empty_state()
        evidence = {"auto-x": {"signal_a": True, "signal_b": True}}

        first = fo.apply_exemptions(state, policy, evidence, "t1")
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["event"], "activated")
        self.assertTrue(state["exemptions"]["auto-x"])

        second = fo.apply_exemptions(state, policy, evidence, "t2")
        self.assertEqual(second, [])  # still active, no repeated transition

    def test_apply_exemptions_restores_the_instant_evidence_regresses(self):
        policy = {"contract": fo.POLICY_CONTRACT, "roles": [
            {"name": "r1", "areas": ["delivery"], "rank": 1, "model": None, "effort": "low"},
        ], "exemptions": [self.entry()]}
        state = fo.empty_state()
        fo.apply_exemptions(state, policy, {"auto-x": {"signal_a": True, "signal_b": True}}, "t1")
        self.assertTrue(state["exemptions"]["auto-x"])

        regressed = fo.apply_exemptions(state, policy, {"auto-x": {"signal_a": True, "signal_b": False}}, "t2")
        self.assertEqual(len(regressed), 1)
        self.assertEqual(regressed[0]["event"], "restored")
        self.assertFalse(state["exemptions"]["auto-x"])

    def test_cli_end_to_end_activation_and_restore_via_observe(self):
        with ToolCase() as case:
            snapshot = case.write_json("s.json", {"areas": {}})
            active_evidence = case.write_json("evidence-on.json", {
                "tactical-resolve-auto-handoff": {
                    "decision_kind_tactical": True, "patch_not_required": True,
                },
            })
            result = json.loads(
                case.run_tool("observe", "--snapshot", snapshot, "--evidence", active_evidence, check=True).stdout
            )
            self.assertTrue(result["exemptions"]["tactical-resolve-auto-handoff"])
            self.assertEqual(result["exemption_transitions"][0]["event"], "activated")

            regressed_evidence = case.write_json("evidence-off.json", {
                "tactical-resolve-auto-handoff": {
                    "decision_kind_tactical": True, "patch_not_required": False,
                },
            })
            result2 = json.loads(
                case.run_tool(
                    "observe", "--snapshot", snapshot, "--evidence", regressed_evidence, check=True
                ).stdout
            )
            self.assertFalse(result2["exemptions"]["tactical-resolve-auto-handoff"])
            self.assertEqual(result2["exemption_transitions"][0]["event"], "restored")


# --- policy validation guards ------------------------------------------------


class PolicyValidationTest(unittest.TestCase):
    def test_default_policy_file_is_valid(self):
        fo.validate_policy(json.loads(POLICY.read_text()))  # no raise

    def test_rejects_forbidden_model_token(self):
        bad = json.loads(POLICY.read_text())
        bad["roles"][0]["model"] = "astra-1"
        with self.assertRaises(fo.ObservePolicyError):
            fo.validate_policy(bad)

    def test_rejects_effort_above_medium(self):
        bad = json.loads(POLICY.read_text())
        bad["roles"][0]["effort"] = "high"
        with self.assertRaises(fo.ObservePolicyError):
            fo.validate_policy(bad)

    def test_cli_policy_validate(self):
        proc = subprocess.run(
            [str(TOOL), "policy-validate"], text=True, capture_output=True, check=True,
            env={**os.environ, "FACTORY_OBSERVE_POLICY_FILE": str(POLICY)},
        )
        self.assertTrue(json.loads(proc.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
