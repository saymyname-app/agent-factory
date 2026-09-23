#!/usr/bin/env python3

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ORACLE = ROOT / "bin" / "planning-run-resume-oracle"
MANIFEST = ROOT / "config" / "planning-run-resume-prototype.json"


def load_default_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


class PlanningRunResumeOracleTest(unittest.TestCase):
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
        self.assertEqual("agent-factory-planning-run-resume-result/v1", result["contract"])
        self.assertTrue(result["acceptance_met"])
        self.assertTrue(result["provider_change"])
        self.assertTrue(result["surface_change"])
        self.assertTrue(result["resumed_without_repeat"])
        self.assertEqual("one_way", result["conversation_visibility"]["directionality"])
        self.assertFalse(result["conversation_visibility"]["reverse_exists"])
        for criterion in result["acceptance"].values():
            self.assertTrue(criterion["value"], criterion["reason"])

    def test_rejects_effort_above_medium(self):
        manifest = load_default_manifest()
        manifest["roles"][0]["effort"] = "high"
        completed = self.run_manifest(manifest, check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("medium-or-lower ceiling", completed.stderr)

    def test_rejects_forbidden_model(self):
        manifest = load_default_manifest()
        manifest["roles"][1]["model"] = "fable-5"
        completed = self.run_manifest(manifest, check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("no-fable contract", completed.stderr)

    def test_rejects_resume_without_provider_change(self):
        manifest = load_default_manifest()
        manifest["roles"][1]["provider"] = manifest["roles"][0]["provider"]
        completed = self.run_manifest(manifest, check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("provider change", completed.stderr)

    def test_rejects_resume_without_surface_change(self):
        manifest = load_default_manifest()
        manifest["roles"][1]["surface"] = manifest["roles"][0]["surface"]
        completed = self.run_manifest(manifest, check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("surface change", completed.stderr)

    def test_rejects_a_partially_compliant_retained_conversation_view(self):
        manifest = load_default_manifest()
        manifest["conversation_view"]["zero_token"] = False
        completed = self.run_manifest(manifest, check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("zero_token", completed.stderr)

    def test_rejects_an_unmeasured_reverse_visibility_claim(self):
        manifest = load_default_manifest()
        del manifest["conversation_view"]["reverse_exists"]
        completed = self.run_manifest(manifest, check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("measured explicitly", completed.stderr)

    def test_accepts_no_retained_conversation_view_at_all(self):
        manifest = load_default_manifest()
        manifest["conversation_view"] = None
        completed = self.run_manifest(manifest, check=False)
        result = json.loads(completed.stdout)
        self.assertIsNone(result["retained_conversation_view"])
        self.assertTrue(
            result["acceptance"]["conversation_view_retention_contract"]["value"]
        )
        # Dropping the view is valid, but it forfeits the one-way-visibility
        # criterion, which this prototype only demonstrates through a view.
        self.assertFalse(result["acceptance"]["visibility_measured_one_way"]["value"])
        self.assertFalse(result["acceptance_met"])
        self.assertEqual(1, completed.returncode)


if __name__ == "__main__":
    unittest.main()
