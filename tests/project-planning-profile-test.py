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
PROJECTS_CONFIG_DIR = FIXTURES / "projects"
DESCRIPTORS = FIXTURES / "descriptors"
DESCRIPTORS_LIST = FIXTURES / "descriptors-list"
REAL_DESCRIPTORS_DIR = ROOT / "config" / "project-descriptors"


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

    # --- human-approver (W04: spec-approve's approver check) ----------------

    def human_approver(self, project, config_dir=PROJECTS_CONFIG_DIR, check=False):
        return subprocess.run(
            (str(TOOL), "human-approver", "--project", project, "--config-dir", str(config_dir)),
            cwd=ROOT, text=True, capture_output=True, check=check,
        )

    def test_human_approver_reports_the_declared_project_approver(self):
        result = json.loads(self.human_approver("project-a", check=True).stdout)
        self.assertTrue(result["ok"])
        self.assertEqual("project-a", result["project_id"])
        self.assertEqual("benjamin", result["human_approver"])

    def test_human_approver_fails_with_actionable_diagnostic_when_undeclared(self):
        proc = self.human_approver("project-without-approver")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("human_approver", error["error"])

    def test_human_approver_fails_with_actionable_diagnostic_when_no_project_file(self):
        proc = self.human_approver("no-such-project")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["ok"])
        self.assertIn("no-such-project", error["error"])

    # --- extended descriptor (T04, af-xqgvat: "un rig = un projet") --------

    def describe(self, path, check=False):
        return subprocess.run(
            (str(TOOL), "describe", str(path)),
            cwd=ROOT, text=True, capture_output=True, check=check,
        )

    def test_valid_descriptor_is_accepted_and_describes_the_project(self):
        result = json.loads(self.describe(DESCRIPTORS / "fixture-project-a.json", check=True).stdout)
        self.assertEqual("fixture-project-a", result["project_id"])
        self.assertEqual(["fixture-rig-a"], result["rigs"])
        self.assertEqual({}, result["promotion_branch"])

    def test_valid_descriptor_with_promotion_branch_is_accepted(self):
        result = json.loads(self.describe(DESCRIPTORS / "fixture-project-b.json", check=True).stdout)
        self.assertEqual(
            {"from": "dev", "to": "main"}, result["promotion_branch"]["fixture-rig-b-back"]
        )

    def test_descriptor_missing_a_required_field_is_rejected(self):
        proc = self.describe(DESCRIPTORS / "invalid-missing-field.json")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["valid"])
        self.assertIn("knowledge_repo", error["error"])

    def test_promotion_branch_naming_an_undeclared_rig_is_rejected(self):
        proc = self.describe(DESCRIPTORS / "invalid-promotion-undeclared-rig.json")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["valid"])
        self.assertIn("promotion_branch", error["error"])
        self.assertIn("not in rigs", error["error"])

    def test_descriptor_has_no_production_field(self):
        proc = self.describe(DESCRIPTORS / "invalid-production-field.json")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["valid"])
        self.assertIn("production", error["error"])

    def test_descriptor_has_no_language_field(self):
        descriptor = json.loads((DESCRIPTORS / "fixture-project-a.json").read_text())
        descriptor["language"] = "fr"
        tmp = DESCRIPTORS / "tmp-invalid-language-field.json"
        tmp.write_text(json.dumps(descriptor))
        try:
            proc = self.describe(tmp)
            self.assertNotEqual(0, proc.returncode)
            error = json.loads(proc.stdout)
            self.assertFalse(error["valid"])
            self.assertIn("language", error["error"])
        finally:
            tmp.unlink()

    def test_list_reports_declared_projects_as_json(self):
        proc = subprocess.run(
            (str(TOOL), "list", "--descriptors-dir", str(DESCRIPTORS_LIST)),
            cwd=ROOT, text=True, capture_output=True, check=True,
        )
        result = json.loads(proc.stdout)
        self.assertTrue(result["ok"])
        project_ids = {project["project_id"] for project in result["projects"]}
        self.assertEqual({"fixture-project-a", "fixture-project-b"}, project_ids)

    # --- real descriptors (acceptance criterion: agent-factory & saymyname) -

    def test_real_agent_factory_descriptor_has_no_promotion_branch(self):
        result = json.loads(
            self.describe(REAL_DESCRIPTORS_DIR / "agent-factory.json", check=True).stdout
        )
        self.assertEqual("agent-factory", result["project_id"])
        self.assertEqual(["agent-factory"], result["rigs"])
        self.assertEqual({}, result["promotion_branch"])
        self.assertEqual("docs/roadmap.toml", result["roadmap_path"])
        self.assertEqual("bin/rituals-status", result["rituals_status_command"])

    def test_real_saymyname_descriptor_declares_dev_to_main_promotion(self):
        result = json.loads(
            self.describe(REAL_DESCRIPTORS_DIR / "saymyname.json", check=True).stdout
        )
        self.assertEqual("saymyname", result["project_id"])
        self.assertEqual(["saymyname-backend", "saymyname-frontend"], result["rigs"])
        self.assertEqual("saymyname-app/Say-my-name-product", result["knowledge_repo"])
        self.assertEqual("knowledge/roadmap.toml", result["roadmap_path"])
        self.assertEqual("tools/rituals-status.sh", result["rituals_status_command"])
        for rig in result["rigs"]:
            self.assertEqual({"from": "dev", "to": "main"}, result["promotion_branch"][rig])

    def test_real_descriptors_are_listed(self):
        proc = subprocess.run(
            (str(TOOL), "list", "--descriptors-dir", str(REAL_DESCRIPTORS_DIR)),
            cwd=ROOT, text=True, capture_output=True, check=True,
        )
        result = json.loads(proc.stdout)
        self.assertTrue(result["ok"])
        project_ids = {project["project_id"] for project in result["projects"]}
        self.assertEqual({"agent-factory", "saymyname"}, project_ids)


if __name__ == "__main__":
    unittest.main()
