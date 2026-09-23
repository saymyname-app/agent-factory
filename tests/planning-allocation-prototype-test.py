#!/usr/bin/env python3

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "bin" / "planning-allocation-prototype"
MANIFEST = ROOT / "config" / "planning-allocation-prototype.json"
REGISTER = ROOT / "docs" / "ADAPTATION_REGISTER.md"


class PlanningAllocationPrototypeTest(unittest.TestCase):
    def invoke(self, *arguments, check=True):
        return subprocess.run(
            (str(PROTOTYPE), *arguments),
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=check,
        )

    def result(self):
        first = self.invoke("run").stdout
        second = self.invoke("run").stdout
        self.assertEqual(first, second)
        return json.loads(first)

    def test_compares_two_viable_allocations_through_the_same_boundary(self):
        result = self.result()

        self.assertEqual("agent-factory-planning-allocation-result/v1", result["contract"])
        self.assertEqual(
            "spec-agent-factory-project-agnostic-refactor",
            result["spec_trace"]["id"],
        )
        self.assertEqual("skill-loaded-planner", result["selection"]["candidate_id"])
        self.assertEqual("provisional", result["selection"]["status"])
        self.assertEqual(2, len(result["candidates"]))

        for candidate in result["candidates"]:
            self.assertTrue(all(candidate["method_fidelity"].values()))
            self.assertEqual(
                {
                    "human_conversation",
                    "specialist_work",
                    "phase_sequencing",
                    "eligibility_triggers",
                    "validation",
                },
                set(candidate["execution_sites"]),
            )
            self.assertEqual(
                {"simple", "wayfinding"},
                {run["kind"] for run in candidate["runs"]},
            )
            for run in candidate["runs"]:
                self.assertEqual(
                    "CONVOY_CONTINUATION_READY", run["final_state"]
                )
                self.assertEqual("convoy-continuation", run["boundary"])
                self.assertEqual(1, len(run["canonical_writer_actors"]))
                self.assertEqual("mayor", run["delivery_authority"])
                self.assertEqual(
                    {"grill-with-docs", "to-spec", "to-tickets"},
                    set(run["skills_exercised"]),
                )

    def test_selected_candidate_is_the_smallest_passing_allocation(self):
        result = self.result()
        costs = {
            candidate["id"]: candidate["maintenance_cost"]["configuration_units"]
            for candidate in result["candidates"]
        }

        self.assertEqual(min(costs, key=costs.get), result["selection"]["candidate_id"])
        self.assertLess(
            costs["skill-loaded-planner"], costs["phase-specialized-roles"]
        )

    def test_failure_probes_stop_before_a_partial_convoy(self):
        result = self.result()

        for candidate in result["candidates"]:
            writer = candidate["failure_probes"]["canonical_writer_unavailable"]
            publication = candidate["failure_probes"]["draft_validation_failure"]
            self.assertEqual("WRITER_RETRYABLE", writer["state"])
            self.assertIsNone(writer["convoy_id"])
            self.assertEqual("TICKET_GRAPH_DRAFT_INVALID", publication["state"])
            self.assertIsNone(publication["convoy_id"])
            self.assertEqual([], publication["published_nodes"])

    def test_bounded_reversal_preserves_durable_state_and_changes_only_bindings(self):
        reversal = self.result()["reversal"]

        self.assertEqual("WAYFINDING_CLEAR", reversal["checkpoint"])
        self.assertEqual("skill-loaded-planner", reversal["from"])
        self.assertEqual("phase-specialized-roles", reversal["to"])
        self.assertEqual(
            reversal["before"]["planning_run_id"],
            reversal["after"]["planning_run_id"],
        )
        self.assertEqual(
            reversal["before"]["planning_map_id"],
            reversal["after"]["planning_map_id"],
        )
        self.assertEqual(
            reversal["before"]["resolved_decisions"],
            reversal["after"]["resolved_decisions"],
        )
        self.assertEqual("CONVOY_CONTINUATION_READY", reversal["after"]["state"])
        self.assertEqual(1, len(reversal["after"]["canonical_writer_actors"]))

    def test_rejects_planning_base_and_duplicate_delivery_authority(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["candidates"][0]["allocation"]["formulas"].append("planning-base")
        result = self.validate_mutation(manifest)
        self.assertIn("planning-base is forbidden", result.stderr)

        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["candidates"][0]["delivery_authorities"].append("shadow-mayor")
        result = self.validate_mutation(manifest)
        self.assertIn("exactly one delivery authority", result.stderr)

    def test_single_adaptation_register_entry_records_evidence_and_reversal(self):
        register = REGISTER.read_text(encoding="utf-8")

        self.assertEqual(1, register.count("## AR-001"))
        self.assertIn("Orchestration Gas City de la méthode de Matt", register)
        self.assertIn("skill-loaded-planner", register)
        self.assertIn("WAYFINDING_CLEAR", register)
        self.assertIn("tests/planning-allocation-prototype-test.py", register)

    def validate_mutation(self, manifest):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            return self.invoke("validate", "--manifest", str(path), check=False)


if __name__ == "__main__":
    unittest.main()
