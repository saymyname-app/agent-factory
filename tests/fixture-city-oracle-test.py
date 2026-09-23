#!/usr/bin/env python3

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ORACLE = ROOT / "bin" / "fixture-city-oracle"
FIXTURES = ROOT / "tests" / "fixtures" / "fixture-city"
OPERATOR = FIXTURES / "operator"


class FixtureCityOracleTest(unittest.TestCase):
    def invoke(self, scenario, *, check=True):
        return subprocess.run(
            (
                str(ORACLE),
                "run",
                str(FIXTURES / scenario),
                "--operator",
                str(OPERATOR),
                "--publication-door",
                str(OPERATOR),
            ),
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=check,
        )

    def test_single_rig_run_observes_the_public_lifecycle_deterministically(self):
        first = self.invoke("single-rig.json")
        second = self.invoke("single-rig.json")
        self.assertEqual(first.stdout, second.stdout)

        result = json.loads(first.stdout)
        self.assertTrue(result["ok"])
        self.assertEqual("single-rig", result["scenario_id"])
        self.assertEqual(
            [
                "REQUESTED",
                "SPEC_AWAITING_APPROVAL",
                "APPROVED_SPEC",
                "DELIVERY_GRAPH_PUBLISHED",
                "DELIVERING",
                "DELIVERED_OUTCOME",
                "ACCEPTED_OUTCOME",
            ],
            result["planning_states"],
        )
        self.assertEqual("published", result["publication"]["state"])
        self.assertTrue(result["publication"]["convoy_id"].startswith("convoy-"))
        self.assertEqual("single-rig", result["integration"]["mode"])
        self.assertEqual(
            [{
                "rig": "fixture-app",
                "revision": "7a9e5aeffb4f73c649a22fd666208a22a80d9f46",
                "verified": True,
            }],
            [
                {key: evidence[key] for key in ("rig", "revision", "verified")}
                for evidence in result["integration"]["evidence"]
            ],
        )
        self.assertRegex(result["integration"]["evidence"][0]["tree"], r"^[0-9a-f]{40}$")
        self.assertTrue(result["integration"]["assembly_check"]["passed"])
        self.assertEqual(
            {"delivered": True, "accepted": True}, result["outcome"]
        )
        self.assertEqual([], result["effects"])
        self.assertEqual(["publish"], result["interfaces"]["write_doors"])
        self.assertNotIn("cockpit", json.dumps(result).lower())

    def test_multi_rig_run_requires_the_exact_participating_revisions(self):
        result = json.loads(self.invoke("multi-rig.json").stdout)
        self.assertEqual("exact-revision-multi-rig", result["integration"]["mode"])
        self.assertEqual(
            [
                {
                    "rig": "fixture-api",
                    "revision": "73ac3a0db24ecb1d522b83a454526b75c4a83668",
                    "verified": True,
                },
                {
                    "rig": "fixture-web",
                    "revision": "97e20dbabc2ae1c7874c5ae9be50fee49d3ac654",
                    "verified": True,
                },
            ],
            [
                {key: evidence[key] for key in ("rig", "revision", "verified")}
                for evidence in result["integration"]["evidence"]
            ],
        )
        self.assertTrue(result["integration"]["assembly_check"]["passed"])
        self.assertEqual(2, len(result["integration"]["assembly_check"]["participants"]))
        self.assertEqual(
            {"delivered": True, "accepted": True}, result["outcome"]
        )

    def test_injected_publication_failure_leaves_no_graph_or_convoy(self):
        result = json.loads(self.invoke("publication-failure.json").stdout)
        self.assertTrue(result["ok"])
        self.assertEqual("failed_atomically", result["publication"]["state"])
        self.assertIsNone(result["publication"]["graph_digest"])
        self.assertIsNone(result["publication"]["convoy_id"])
        self.assertEqual(
            {"delivered": False, "accepted": False}, result["outcome"]
        )
        self.assertEqual([], result["integration"]["evidence"])
        self.assertIsNone(result["integration"]["assembly_check"])
        self.assertEqual([], result["effects"])

    def test_oracle_rejects_a_failed_door_that_leaks_a_partial_graph(self):
        result = self.invoke("partial-publication-bug.json", check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("failed publication left a partial delivery graph", result.stderr)

    def test_oracle_rejects_an_arbitrary_revision_string(self):
        result = self.invoke("wrong-revision.json", check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("not pinned revision", result.stderr)

    def test_exact_revisions_still_fail_when_their_public_interfaces_are_incompatible(self):
        advertised = json.loads(
            (FIXTURES / "rigs" / "fixture-web-incompatible" / "fixture-interface.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual({"fixture-status/v1": "ready"}, advertised["requires"])
        result = self.invoke("incompatible-assembly.json", check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("assembled public behavior failed", result.stderr)

    def test_oracle_rejects_a_publication_with_a_duplicate_slice_key(self):
        result = self.invoke("duplicate-graph-node.json", check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("exact approved slice keys", result.stderr)

    def test_adapter_runs_without_host_identity_files_network_or_system_writes(self):
        result = json.loads(self.invoke("containment.json").stdout)
        self.assertTrue(result["ok"])
        self.assertEqual([], result["effects"])

    def test_adapter_cannot_replace_bytes_in_an_exact_revision_checkout(self):
        result = self.invoke("dirty-assembly-attempt.json", check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("assembly checkout is read-only", result.stderr)

    def test_reference_protocol_does_not_overclaim_three_rig_coverage(self):
        result = self.invoke("unsupported-three-rig.json", check=False)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("support one or two exact-revision rigs", result.stderr)


if __name__ == "__main__":
    unittest.main()
