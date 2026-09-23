#!/usr/bin/env python3

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ORACLE = ROOT / "bin" / "planning-map-concurrency-prototype"
MANIFEST = ROOT / "config" / "planning-map-concurrency-prototype.json"


def load_default_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


class PlanningMapConcurrencyPrototypeTest(unittest.TestCase):
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
        self.assertEqual("agent-factory-planning-map-concurrency-result/v1", result["contract"])
        self.assertTrue(result["acceptance_met"])
        for criterion in result["acceptance"].values():
            self.assertTrue(criterion["value"], criterion["reason"])

    def test_two_independent_decisions_both_progress(self):
        result = json.loads(self.invoke("run").stdout)
        final_map = result["interleaving_replay"]["final_map"]
        self.assertEqual("alpha:approved", final_map["alpha_resolution"])
        self.assertEqual("beta:approved", final_map["beta_resolution"])

    def test_each_decision_claimed_exactly_once(self):
        result = json.loads(self.invoke("run").stdout)
        for decision_id in result["decisions"]:
            successes = [
                entry
                for entry in result["interleaving_replay"]["claim_log"]
                if entry["decision_id"] == decision_id and entry["succeeded"]
            ]
            self.assertEqual(1, len(successes))

    def test_conflicting_shared_write_is_rejected_then_recovered_on_retry(self):
        result = json.loads(self.invoke("run").stdout)
        write_log = result["interleaving_replay"]["write_log"]
        rejected = [w for w in write_log if w["op"] == "write" and not w["applied"]]
        retried = [w for w in write_log if w["op"] == "retry" and w["applied"]]
        self.assertTrue(rejected, "the scripted interleaving must exercise a genuine CAS rejection")
        self.assertTrue(retried, "the rejected writer must recover via a scripted retry")
        shared_index = result["interleaving_replay"]["final_map"]["resolved_decision_index"]
        self.assertEqual(["decision-alpha", "decision-beta"], sorted(shared_index))

    def test_claim_race_stress_covers_every_arrival_order(self):
        result = json.loads(self.invoke("run").stdout)
        stress = result["claim_stress"]
        self.assertTrue(stress["every_order_claimed_exactly_once"])
        self.assertTrue(stress["every_order_first_writer_wins"])
        for entry in stress["per_decision"].values():
            self.assertGreaterEqual(entry["orders_tried"], 2)
            for outcome in entry["outcomes"]:
                self.assertEqual(1, outcome["success_count"])
                self.assertEqual(outcome["order"][0], outcome["winner"])

    def test_rejects_fewer_than_two_decisions(self):
        manifest = load_default_manifest()
        manifest["decisions"] = manifest["decisions"][:1]
        completed = self.run_manifest(manifest, check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("at least two decisions", completed.stderr)

    def test_rejects_colliding_map_keys(self):
        manifest = load_default_manifest()
        manifest["decisions"][1]["map_key"] = manifest["decisions"][0]["map_key"]
        completed = self.run_manifest(manifest, check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("disjoint map_key", completed.stderr)

    def test_rejects_shared_index_key_colliding_with_a_decision_key(self):
        manifest = load_default_manifest()
        manifest["shared_index_key"] = manifest["decisions"][0]["map_key"]
        completed = self.run_manifest(manifest, check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("must not collide", completed.stderr)

    def test_rejects_single_claimant_race(self):
        manifest = load_default_manifest()
        manifest["claim_race"]["decision-beta"] = ["reviewer-4"]
        completed = self.run_manifest(manifest, check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("at least two racing claimants", completed.stderr)

    def test_rejects_singular_writer_overlap_with_concurrent_map_writers(self):
        manifest = load_default_manifest()
        manifest["singular_writers"] = ["decision-alpha"]
        completed = self.run_manifest(manifest, check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("must never overlap", completed.stderr)

    def test_flags_resolution_by_a_non_winning_claimant(self):
        manifest = load_default_manifest()
        manifest["interleaving"].append(
            {
                "op": "write",
                "writer": "reviewer-1",
                "key": "alpha_resolution",
                "compute": "set_value",
                "value": "alpha:hijacked",
            }
        )
        result = json.loads(self.run_manifest(manifest, check=False).stdout)
        self.assertFalse(result["acceptance_met"])
        self.assertFalse(
            result["acceptance"]["each_child_claimed_and_resolved_exactly_once"]["value"]
        )


if __name__ == "__main__":
    unittest.main()
