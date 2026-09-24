#!/usr/bin/env python3

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "planning-run-to-spec-oracle"
FIXTURES = ROOT / "tests" / "fixtures" / "planning-run-to-spec"
SESSIONS = FIXTURES / "sessions"
CITY_REGISTRY = FIXTURES / "city-registry.json"

REQUIRED_SECTIONS = (
    "behavior",
    "boundaries",
    "decisions",
    "acceptance_evidence",
    "provenance",
    "experiments",
    "non_objectives",
)


class PlanningRunToSpecOracleTest(unittest.TestCase):
    def run_session(self, name, city_registry=CITY_REGISTRY, out=None, check=False):
        args = [
            str(TOOL),
            "run",
            str(SESSIONS / f"{name}.json"),
            "--city-registry",
            str(city_registry),
        ]
        if out is not None:
            args += ["--out", str(out)]
        return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=check)

    # -- loads only declared authoritative context -------------------------

    def test_run_loads_only_declared_authoritative_context(self):
        proc = self.run_session("simple-request", check=True)
        result = json.loads(proc.stdout)
        self.assertEqual("spec_synthesized", result["result"])

    def test_probing_an_undeclared_source_is_rejected_before_synthesis(self):
        proc = self.run_session("undeclared-context")
        self.assertNotEqual(0, proc.returncode)
        result = json.loads(proc.stdout)
        self.assertEqual("rejected", result["result"])
        self.assertIn("AGENTS.md", result["error"])
        self.assertIn("declared_context", result["error"])

    # -- Spec contains behavior, boundaries, decisions, acceptance evidence,
    #    provenance, experiments and non-objectives -----------------------

    def test_synthesized_spec_contains_all_required_sections(self):
        proc = self.run_session("simple-request", check=True)
        spec = json.loads(proc.stdout)["spec"]
        for section in REQUIRED_SECTIONS:
            self.assertIn(section, spec["sections"])
            self.assertTrue(spec["sections"][section], f"section {section} is empty")

    # -- stable identity and reproducible content digest -------------------

    def test_spec_identity_and_digest_are_reproducible_across_runs(self):
        first = json.loads(self.run_session("simple-request", check=True).stdout)["spec"]
        second = json.loads(self.run_session("simple-request", check=True).stdout)["spec"]
        self.assertEqual(first["spec_id"], second["spec_id"])
        self.assertEqual(first["content_digest"], second["content_digest"])

    def test_spec_digest_changes_when_confirmed_content_changes(self):
        original = json.loads(self.run_session("simple-request", check=True).stdout)["spec"]
        changed = json.loads(self.run_session("changed-content", check=True).stdout)["spec"]
        self.assertEqual(original["spec_id"], "spec-widget-export-csv-2026-09-24")
        self.assertEqual("spec-changed-content", changed["spec_id"])
        self.assertNotEqual(original["content_digest"], changed["content_digest"])

    # -- a real contradiction, missing trace, undecided behavior or new
    #    test seam returns to planning instead of being invented ----------

    def test_contradiction_returns_to_planning_instead_of_inventing_a_spec(self):
        proc = self.run_session("contradiction", check=True)
        result = json.loads(proc.stdout)
        self.assertEqual("returned_to_planning", result["result"])
        self.assertEqual("contradiction", result["signal"])
        self.assertNotIn("spec", result)

    def test_explicit_missing_trace_returns_to_planning(self):
        result = json.loads(self.run_session("missing-trace-signal", check=True).stdout)
        self.assertEqual("returned_to_planning", result["result"])
        self.assertEqual("missing_trace", result["signal"])

    def test_undecided_behavior_returns_to_planning(self):
        result = json.loads(self.run_session("undecided-behavior", check=True).stdout)
        self.assertEqual("returned_to_planning", result["result"])
        self.assertEqual("undecided_behavior", result["signal"])

    def test_new_test_seam_returns_to_planning(self):
        result = json.loads(self.run_session("new-test-seam", check=True).stdout)
        self.assertEqual("returned_to_planning", result["result"])
        self.assertEqual("new_test_seam", result["signal"])

    def test_missing_required_topic_returns_to_planning_rather_than_fabricating(self):
        result = json.loads(self.run_session("missing-topic", check=True).stdout)
        self.assertEqual("returned_to_planning", result["result"])
        self.assertEqual("missing_trace", result["signal"])
        self.assertIn("provenance", result["reason"])

    # -- no Release Contract or second prose artifact repeats the Spec -----

    def test_repeated_runs_write_exactly_one_spec_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.run_session("simple-request", out=tmp, check=True)
            self.run_session("simple-request", out=tmp, check=True)
            written = sorted(p.name for p in Path(tmp).iterdir())
            self.assertEqual(["spec-widget-export-csv-2026-09-24.json"], written)

    def test_repeated_runs_write_byte_identical_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.run_session("simple-request", out=tmp, check=True)
            first_bytes = (Path(tmp) / "spec-widget-export-csv-2026-09-24.json").read_bytes()
            self.run_session("simple-request", out=tmp, check=True)
            second_bytes = (Path(tmp) / "spec-widget-export-csv-2026-09-24.json").read_bytes()
            self.assertEqual(first_bytes, second_bytes)

    # -- a simple request stays in one healthy interactive session ---------

    def test_simple_request_does_not_require_wayfinder_ceremony(self):
        proc = self.run_session("wayfinder-ceremony")
        self.assertNotEqual(0, proc.returncode)
        result = json.loads(proc.stdout)
        self.assertEqual("rejected", result["result"])
        self.assertIn("Wayfinder ceremony", result["error"])

    def test_simple_request_does_not_require_another_interview_round(self):
        proc = self.run_session("extra-interview-round")
        self.assertNotEqual(0, proc.returncode)
        result = json.loads(proc.stdout)
        self.assertEqual("rejected", result["result"])
        self.assertIn("interview round", result["error"])

    # -- target rigs are checked against the City's rig registry -----------

    def test_target_rig_outside_registry_is_rejected(self):
        proc = self.run_session("rig-out-of-registry")
        self.assertNotEqual(0, proc.returncode)
        result = json.loads(proc.stdout)
        self.assertEqual("rejected", result["result"])
        self.assertIn("unregistered-rig", result["error"])


if __name__ == "__main__":
    unittest.main()
