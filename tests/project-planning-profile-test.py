#!/usr/bin/env python3

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "project-planning-profile"
FIXTURES = ROOT / "tests" / "fixtures" / "project-planning-profile"
PROFILES = FIXTURES / "profiles"
CITY_REGISTRY = FIXTURES / "city-registry.json"


class ProjectPlanningProfileTest(unittest.TestCase):
    def validate(self, name, check=False):
        return subprocess.run(
            (str(TOOL), "validate", str(PROFILES / f"{name}.json")),
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=check,
        )

    def register(self, name, city_registry=CITY_REGISTRY, check=False):
        return subprocess.run(
            (
                str(TOOL),
                "register",
                str(PROFILES / f"{name}.json"),
                "--city-registry",
                str(city_registry),
            ),
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=check,
        )

    def test_valid_profile_validates_clean(self):
        result = self.validate("project-a", check=True)
        self.assertEqual({"valid": True}, json.loads(result.stdout))

    def test_registration_succeeds_without_saymyname_or_factory_wide_fields(self):
        proc = self.register("project-a", check=True)
        result = json.loads(proc.stdout)
        self.assertTrue(result["registered"])
        self.assertEqual("project-a", result["project_id"])
        self.assertEqual(["project-a"], result["effective_scope"])
        self.assertEqual(["project-a-unit-tests"], result["checks"])
        self.assertNotIn("cost_policy", result)
        self.assertNotIn("saymyname", json.dumps(result).lower())

    def test_saymyname_specific_field_is_rejected(self):
        proc = self.validate("invalid-saymyname")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["valid"])
        self.assertIn("SayMyName-specific", error["error"])

    def test_copied_factory_wide_configuration_is_rejected(self):
        proc = self.validate("invalid-factory-wide")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["valid"])
        self.assertIn("Factory-wide configuration", error["error"])

    def test_missing_authoritative_source_fails_with_actionable_diagnostic(self):
        proc = self.validate("invalid-missing-source")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["valid"])
        self.assertIn("project_knowledge.path", error["error"])
        self.assertIn("does not exist", error["error"])

    def test_contradictory_authoritative_sources_fail_with_actionable_diagnostic(self):
        proc = self.validate("invalid-contradictory")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["valid"])
        self.assertIn("work_graph.rigs", error["error"])
        self.assertIn("participant_rigs", error["error"])

    def test_project_policy_cannot_disable_a_common_safety_principle(self):
        proc = self.validate("invalid-disabled-safety")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["valid"])
        self.assertIn("no_production_without_human", error["error"])
        self.assertIn("cannot be disabled", error["error"])

    def test_project_policy_can_tighten_safety_without_rejection(self):
        # project-a declares every required safety key explicitly as true,
        # and adds its own stricter risk_thresholds -- this must validate.
        result = self.validate("project-a", check=True)
        self.assertEqual({"valid": True}, json.loads(result.stdout))

    def test_registration_rejects_a_rig_outside_the_city_registry(self):
        registry = FIXTURES / "city-registry-project-a-only.json"
        registry.write_text(json.dumps(["project-a"]))
        try:
            proc = self.register("project-b", city_registry=registry)
            self.assertNotEqual(0, proc.returncode)
            error = json.loads(proc.stdout)
            self.assertFalse(error["registered"])
            self.assertIn("project-b", error["error"])
            self.assertIn("not registered", error["error"])
        finally:
            registry.unlink()

    def test_fixture_city_loads_two_profiles_without_either_becoming_default(self):
        # Registering project-a and project-b against the same City registry,
        # in either order, must produce independent registrations: each
        # keeps its own effective_scope, checks, risk_thresholds and
        # extensions, and neither call's result carries a "default" marker
        # or leaks the other project's fields.
        first = json.loads(self.register("project-a", check=True).stdout)
        second = json.loads(self.register("project-b", check=True).stdout)
        third = json.loads(self.register("project-a", check=True).stdout)

        self.assertEqual(first, third)
        self.assertNotEqual(first["project_id"], second["project_id"])
        self.assertEqual(["project-a"], first["effective_scope"])
        self.assertEqual(["project-b"], second["effective_scope"])
        self.assertEqual("strict", first["extensions"]["lint_profile"])
        self.assertEqual("relaxed", second["extensions"]["lint_profile"])
        for result in (first, second):
            self.assertNotIn("default", result)
            self.assertNotIn("is_default", result)


if __name__ == "__main__":
    unittest.main()
