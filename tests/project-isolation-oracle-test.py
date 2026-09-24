#!/usr/bin/env python3

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ORACLE = ROOT / "bin" / "project-isolation-oracle"
FIXTURES = ROOT / "tests" / "fixtures" / "project-isolation"
SCENARIOS = FIXTURES / "scenarios"


class ProjectIsolationOracleTest(unittest.TestCase):
    def run_scenario(self, name, check=True):
        return subprocess.run(
            (str(ORACLE), "run", str(SCENARIOS / f"{name}.json")),
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=check,
        )

    def test_single_scope_is_deterministic_and_denies_the_unscoped_rig(self):
        first = self.run_scenario("single-scope").stdout
        second = self.run_scenario("single-scope").stdout
        self.assertEqual(first, second)

        result = json.loads(first)
        self.assertEqual(
            "agent-factory-project-isolation-oracle-result/v1", result["schema"]
        )
        self.assertTrue(result["isolation_holds"])
        self.assertEqual(["project-a"], result["effective_scope"])
        self.assertTrue(result["read_results"]["project-a"]["readable"])
        self.assertFalse(result["read_results"]["project-b"]["readable"])
        self.assertIsNone(result["read_results"]["project-b"]["digest"])

    def test_registering_both_rigs_grants_no_cross_project_access(self):
        # single-scope.json registers project-a AND project-b in city_registry
        # but declares no grant -- the agent still cannot read project-b.
        result = json.loads(self.run_scenario("single-scope").stdout)
        self.assertEqual(["project-a", "project-b"], result["city_registry"])
        self.assertEqual(["project-a"], result["agent_scope"])
        self.assertFalse(result["read_results"]["project-b"]["readable"])

    def test_declared_multi_project_grant_exposes_only_named_participants(self):
        result = json.loads(self.run_scenario("multi-project-grant").stdout)
        self.assertTrue(result["isolation_holds"])
        self.assertEqual(["project-a", "project-b"], result["effective_scope"])
        self.assertTrue(result["read_results"]["project-a"]["readable"])
        self.assertTrue(result["read_results"]["project-b"]["readable"])
        self.assertEqual(
            "cross-project-outcome-1", result["declared_grant"]["outcome_id"]
        )

    def test_revoking_the_grant_removes_access_without_changing_project_b(self):
        granted = json.loads(self.run_scenario("multi-project-grant").stdout)
        self.assertTrue(granted["read_results"]["project-b"]["readable"])
        project_b_digest_while_granted = granted["read_results"]["project-b"]["digest"]

        revoked = json.loads(self.run_scenario("grant-revoked").stdout)
        self.assertFalse(revoked["read_results"]["project-b"]["readable"])
        self.assertIsNone(revoked["read_results"]["project-b"]["digest"])

        # project-b's own content is untouched by revocation -- read it back
        # in a fresh grant to prove the fixture itself did not change.
        regranted = json.loads(self.run_scenario("multi-project-grant").stdout)
        self.assertEqual(
            project_b_digest_while_granted,
            regranted["read_results"]["project-b"]["digest"],
        )

    def test_mechanism_and_host_support_are_explicit(self):
        result = json.loads(self.run_scenario("single-scope").stdout)
        self.assertTrue(result["mechanism"])
        self.assertIn("bubblewrap", result["host_support"])
        self.assertTrue(result["host_support"]["note"])

    def test_undeclared_grant_participant_is_rejected(self):
        completed = self.run_scenario("undeclared-participant", check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("project-c", completed.stderr)

    def test_unregistered_agent_scope_is_rejected(self):
        completed = self.run_scenario("scope-not-registered", check=False)
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("project-c", completed.stderr)

    def test_validate_accepts_the_default_scenarios(self):
        for name in ("single-scope", "multi-project-grant", "grant-revoked"):
            subprocess.run(
                (str(ORACLE), "validate", str(SCENARIOS / f"{name}.json")),
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )


if __name__ == "__main__":
    unittest.main()
