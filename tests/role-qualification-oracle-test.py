#!/usr/bin/env python3

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ORACLE = ROOT / "bin" / "role-qualification-oracle"
MANIFEST = ROOT / "config" / "role-qualification-prototype.json"


def load_default_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


class RoleQualificationOracleTest(unittest.TestCase):
    def invoke(self, *arguments, manifest_path=None, check=True):
        args = list(arguments)
        if manifest_path is not None:
            args = ["--manifest", str(manifest_path), *args]
        return subprocess.run(
            (str(ORACLE), *args),
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=check,
        )

    def run_manifest(self, manifest, check=True):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, dir=tempfile.gettempdir()
        ) as handle:
            json.dump(manifest, handle)
            path = Path(handle.name)
        try:
            return self.invoke("run", manifest_path=path, check=check)
        finally:
            path.unlink(missing_ok=True)

    def test_default_manifest_validates(self):
        self.invoke("validate")

    def test_default_manifest_meets_every_acceptance_criterion_deterministically(self):
        first = self.invoke("run").stdout
        second = self.invoke("run").stdout
        self.assertEqual(first, second)

        result = json.loads(first)
        self.assertEqual("agent-factory-role-qualification-result/v1", result["contract"])
        self.assertTrue(result["acceptance_met"])
        self.assertEqual(["claude", "codex"], result["providers"])
        self.assertTrue(all(result["providers_meeting_standard"].values()))
        self.assertEqual("zero", result["retention"]["chosen_id"])
        self.assertEqual(12, result["concurrency"]["chosen_ceiling"])
        for criterion in result["acceptance"].values():
            self.assertTrue(criterion["value"], criterion["reason"])

    def test_rejects_effort_above_medium(self):
        manifest = load_default_manifest()
        manifest["work_classes"][0]["roles"][0]["effort"] = "high"
        completed = self.run_manifest(manifest, check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("medium-or-lower ceiling", completed.stderr)

    def test_rejects_forbidden_model(self):
        manifest = load_default_manifest()
        manifest["work_classes"][1]["roles"][1]["model"] = "fable-5"
        completed = self.run_manifest(manifest, check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("no-fable contract", completed.stderr)

    def test_rejects_missing_load_metric(self):
        manifest = load_default_manifest()
        del manifest["work_classes"][0]["load_evidence"][0]["tokens"]
        completed = self.run_manifest(manifest, check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("missing required metric", completed.stderr)

    def test_rejects_provider_set_mismatch_across_work_classes(self):
        manifest = load_default_manifest()
        manifest["work_classes"][1]["roles"][1]["provider"] = "cockpit"
        manifest["work_classes"][1]["load_evidence"][1]["role_id"] = (
            manifest["work_classes"][1]["roles"][1]["id"]
        )
        completed = self.run_manifest(manifest, check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("same provider set", completed.stderr)

    def test_rejects_a_low_initial_concurrency_ceiling(self):
        manifest = load_default_manifest()
        manifest["concurrency"]["initial_ceiling"] = manifest["concurrency"]["minimum_ceiling"]
        completed = self.run_manifest(manifest, check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("deliberately high", completed.stderr)

    def test_reduces_ceiling_when_host_pressure_is_observed(self):
        manifest = load_default_manifest()
        manifest["concurrency"]["observed_host_pressure"] = True
        completed = self.run_manifest(manifest, check=False)
        result = json.loads(completed.stdout)
        self.assertTrue(result["concurrency"]["reduction_justified"])
        self.assertEqual(
            manifest["concurrency"]["minimum_ceiling"], result["concurrency"]["chosen_ceiling"]
        )
        self.assertTrue(
            result["acceptance"]["concurrency_ceiling_reduced_only_when_justified"]["value"]
        )

    def test_reduces_ceiling_when_completion_quality_is_not_ok(self):
        manifest = load_default_manifest()
        manifest["concurrency"]["observed_completion_quality_ok"] = False
        completed = self.run_manifest(manifest, check=False)
        result = json.loads(completed.stdout)
        self.assertTrue(result["concurrency"]["reduction_justified"])
        self.assertEqual(
            manifest["concurrency"]["minimum_ceiling"], result["concurrency"]["chosen_ceiling"]
        )

    def test_prefers_zero_retention_when_planning_graph_evidence_is_sufficient(self):
        result = json.loads(self.invoke("run").stdout)
        self.assertEqual("zero", result["retention"]["chosen_id"])
        self.assertEqual(0, result["retention"]["chosen_retained_turns"])

    def test_falls_back_to_shortest_evidenced_diagnostic_retention(self):
        manifest = load_default_manifest()
        manifest["retention_candidates"][0]["planning_graph_evidence_sufficient"] = False
        manifest["retention_candidates"].append(
            {
                "id": "extended",
                "retained_turns": 8,
                "planning_graph_evidence_sufficient": False,
                "diagnostic_need_evidenced": True,
            }
        )
        completed = self.run_manifest(manifest, check=False)
        result = json.loads(completed.stdout)
        self.assertEqual("brief", result["retention"]["chosen_id"])
        self.assertEqual(3, result["retention"]["chosen_retained_turns"])

    def test_rejects_retention_with_no_evidenced_diagnostic_need(self):
        manifest = load_default_manifest()
        manifest["retention_candidates"][0]["planning_graph_evidence_sufficient"] = False
        manifest["retention_candidates"][1]["diagnostic_need_evidenced"] = False
        completed = self.run_manifest(manifest, check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("no retention candidate has an evidenced diagnostic need", completed.stderr)


if __name__ == "__main__":
    unittest.main()
