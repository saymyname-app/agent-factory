#!/usr/bin/env python3

import json
import subprocess
import tempfile
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

    # --- launch declarations (spec af-wf4w5r .12, T01, af-m8m1kc) ----------

    LAUNCH_FIXTURE_DESCRIPTOR = (
        ROOT / "tests" / "fixtures" / "delivery-fixture-city" / "descriptor.json"
    )

    def test_describe_renders_every_required_launch_declaration(self):
        result = json.loads(self.describe(self.LAUNCH_FIXTURE_DESCRIPTOR, check=True).stdout)
        launch = result["launch"]
        self.assertTrue(launch["recipe"])
        self.assertTrue(launch["entry_points"])
        self.assertEqual("/health", launch["health_probe"]["path"])
        self.assertTrue(launch["test_perimeter"])
        self.assertTrue(launch["frozen_harness_paths"])
        self.assertTrue(launch["test_command"])
        self.assertIn(launch["seam_mode"], ("black_box", "import_rule"))
        self.assertTrue(launch["regression_command"])
        self.assertGreaterEqual(launch["k"], 1)

    def test_descriptor_with_no_launch_block_describes_with_launch_null(self):
        result = json.loads(
            self.describe(REAL_DESCRIPTORS_DIR / "agent-factory.json", check=True).stdout
        )
        self.assertIsNone(result["launch"])

    def test_launch_block_missing_a_required_declaration_is_rejected(self):
        proc = self.describe(DESCRIPTORS / "invalid-launch-missing-field.json")
        self.assertNotEqual(0, proc.returncode)
        error = json.loads(proc.stdout)
        self.assertFalse(error["valid"])
        self.assertIn("launch", error["error"])
        self.assertIn("datasets", error["error"])


    # --- optional launch declarations read by bin/tdd-step (T10, af-j8jo02) --

    def describe_launch(self, without=(), **launch):
        """The fixture descriptor with other launch declarations."""
        descriptor = json.loads(self.LAUNCH_FIXTURE_DESCRIPTOR.read_text())
        descriptor["launch"].update(launch)
        for field in without:
            del descriptor["launch"][field]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "descriptor.json"
            path.write_text(json.dumps(descriptor))
            proc = self.describe(path)
        return proc.returncode, json.loads(proc.stdout)

    def test_describe_renders_the_declared_red_error_types_and_import_rule(self):
        rule = {"product_import": r"^import app\b", "entry_point_import": r"^import app$"}

        status, result = self.describe_launch(red_error_types=["AttributeError"], import_rule=rule)

        self.assertEqual(0, status)
        self.assertEqual(["AttributeError"], result["launch"]["red_error_types"])
        self.assertEqual(rule, result["launch"]["import_rule"])

    def test_launch_block_without_the_optional_declarations_renders_none_of_them(self):
        launch = json.loads(self.describe(self.LAUNCH_FIXTURE_DESCRIPTOR, check=True).stdout)["launch"]

        self.assertNotIn("red_error_types", launch)
        self.assertNotIn("import_rule", launch)

    # --- datasets, mode per seam, anchors and k required (T38, af-8o4jcp) -----

    SECOND_FIXTURE_DESCRIPTOR = ROOT / "tests" / "fixtures" / "delivery-fixture-city-api" / "descriptor.json"
    TESTS_OF_THE_FIXTURE = "tests/fixtures/delivery-fixture-city/tests"

    def test_a_launchable_profile_that_declares_no_dataset_is_refused_and_the_field_is_named(self):
        for change in ({"without": ("datasets", "screens"), "anchors": {"not_applicable": "sans écran"}},
                       {"without": ("screens",), "anchors": {"not_applicable": "sans écran"}, "datasets": {}}):
            with self.subTest(change=change):
                status, answer = self.describe_launch(**change)

                self.assertEqual(1, status)
                self.assertFalse(answer["valid"])
                self.assertIn("datasets", answer["error"])

    def test_listing_the_projects_refuses_a_launchable_profile_without_a_dataset(self):
        descriptor = json.loads(self.LAUNCH_FIXTURE_DESCRIPTOR.read_text())
        del descriptor["launch"]["screens"]
        descriptor["launch"].update(datasets={}, anchors={"not_applicable": "sans écran"})
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "fixture.json").write_text(json.dumps(descriptor))
            before = sorted(path.name for path in Path(tmp).iterdir())
            proc = subprocess.run((str(TOOL), "list", "--descriptors-dir", tmp), cwd=ROOT, text=True,
                                  capture_output=True)
            after = sorted(path.name for path in Path(tmp).iterdir())

        self.assertEqual(1, proc.returncode)
        self.assertIn("datasets", json.loads(proc.stdout)["error"])
        self.assertEqual(before, after, "the refusal wrote something")

    def test_a_profile_with_two_seams_of_different_modes_is_accepted_and_describes_each(self):
        seams = [
            {"name": "http", "mode": "black_box", "test_paths": [f"{self.TESTS_OF_THE_FIXTURE}/test_health.py"]},
            {"name": "library", "mode": "import_rule", "test_paths": [f"{self.TESTS_OF_THE_FIXTURE}/test_count.py"]},
        ]

        status, result = self.describe_launch(without=("seam_mode",), seams=seams)

        self.assertEqual(0, status, result)
        self.assertEqual(seams, result["launch"]["seams"])

    def test_a_profile_with_one_seam_mode_describes_one_seam_over_the_test_perimeter(self):
        launch = json.loads(self.describe(self.LAUNCH_FIXTURE_DESCRIPTOR, check=True).stdout)["launch"]

        self.assertEqual([{"name": "default", "mode": "black_box", "test_paths": launch["test_perimeter"]}],
                         launch["seams"])

    def test_malformed_seams_are_rejected(self):
        inside = f"{self.TESTS_OF_THE_FIXTURE}/test_health.py"
        seam = {"name": "http", "mode": "black_box", "test_paths": [inside]}
        for change, named in (
            ({"without": ("seam_mode",)}, "seam_mode"),
            ({"seams": [seam]}, "exactly one"),
            ({"without": ("seam_mode",), "seams": []}, "launch.seams"),
            ({"without": ("seam_mode",), "seams": [{**seam, "mode": "grey_box"}]}, "launch.seams[0].mode"),
            ({"without": ("seam_mode",), "seams": [{**seam, "test_paths": []}]}, "launch.seams[0].test_paths"),
            ({"without": ("seam_mode",), "seams": [{**seam, "test_paths": ["lib/"]}]}, "outside the test perimeter"),
            ({"without": ("seam_mode",), "seams": [seam, {**seam, "mode": "import_rule"}]}, "twice"),
            ({"without": ("seam_mode",), "seams": [seam, {"name": "library", "mode": "import_rule",
                                                         "test_paths": [self.TESTS_OF_THE_FIXTURE]}]},
             "a test goes through one seam"),
            ({"without": ("seam_mode",), "seams": [{**seam, "rule": "x"}]}, "rule"),
        ):
            with self.subTest(change=change):
                status, result = self.describe_launch(**change)

                self.assertEqual(1, status)
                self.assertFalse(result["valid"])
                self.assertIn(named, result["error"])

    def test_a_profile_without_a_screen_must_declare_the_equivalent_of_the_anchors_or_not_applicable(self):
        status, answer = self.describe_launch(without=("screens",))

        self.assertEqual(1, status)
        self.assertFalse(answer["valid"])
        self.assertIn("launch.anchors", answer["error"])

        status, answer = self.describe_launch(without=("screens",), anchors={"not_applicable": "une file de messages"})
        self.assertEqual(0, status, answer)
        self.assertEqual({"not_applicable": "une file de messages"}, answer["launch"]["anchors"])

    # --- an empty list of screens is no declared screen (T50, af-yorkna) ------

    def test_an_empty_list_of_screens_must_also_declare_the_equivalent_of_the_anchors_or_not_applicable(self):
        descriptor = json.loads(self.LAUNCH_FIXTURE_DESCRIPTOR.read_text())
        descriptor["launch"]["screens"] = []
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "descriptor.json"
            path.write_text(json.dumps(descriptor))
            before = {entry.name: entry.read_bytes() for entry in Path(tmp).iterdir()}
            proc = self.describe(path)
            after = {entry.name: entry.read_bytes() for entry in Path(tmp).iterdir()}
        answer = json.loads(proc.stdout)

        self.assertEqual(1, proc.returncode, answer)
        self.assertFalse(answer["valid"])
        self.assertIn("launch.anchors", answer["error"])
        self.assertEqual(before, after, "the refusal wrote something")

    def test_an_empty_list_of_screens_with_the_equivalent_of_the_anchors_or_not_applicable_is_accepted(self):
        equivalent = {"equivalent": [{"name": "sante", "entry_point": "GET /health", "observable": "le statut 200"}]}
        for anchors in (equivalent, {"not_applicable": "une file de messages"}):
            with self.subTest(anchors=anchors):
                status, answer = self.describe_launch(screens=[], anchors=anchors)

                self.assertEqual(0, status, answer)
                self.assertEqual(anchors, answer["launch"]["anchors"])
                self.assertEqual([], answer["launch"]["screens"])

    def test_the_two_profiles_of_the_fixture_city_are_accepted(self):
        for descriptor in (self.LAUNCH_FIXTURE_DESCRIPTOR, self.SECOND_FIXTURE_DESCRIPTOR):
            with self.subTest(descriptor=descriptor.parent.name):
                self.assertEqual(0, self.describe(descriptor).returncode)

    def test_a_profile_without_k_is_read_with_k_3_and_a_declared_k_is_kept(self):
        status, result = self.describe_launch(without=("k",))
        self.assertEqual((0, 3), (status, result["launch"]["k"]))

        status, result = self.describe_launch(k=5)
        self.assertEqual((0, 5), (status, result["launch"]["k"]))

        status, result = self.describe_launch(k=0)
        self.assertEqual(1, status)
        self.assertIn("launch.k", result["error"])

    # --- screens compared to the Validated Prototype (T16, af-622nya) ---------

    def test_describe_renders_the_screens_of_the_fixture(self):
        launch = json.loads(self.describe(self.LAUNCH_FIXTURE_DESCRIPTOR, check=True).stdout)["launch"]

        self.assertEqual([{"name": "accueil", "path": "/", "states": ["empty", "content"]}], launch["screens"])

    def test_malformed_screens_are_rejected(self):
        screen = {"name": "accueil", "path": "/", "states": ["empty"]}
        for screens, named in (
            ({"accueil": screen}, "screens"),
            ([{**screen, "path": "accueil"}], "screens[0].path"),
            ([{**screen, "states": []}], "screens[0].states"),
            ([{**screen, "states": ["inconnu"]}], "inconnu"),
            ([screen, {**screen, "path": "/autre"}], "accueil"),
            ([screen, {**screen, "name": "autre"}], "empty"),
        ):
            with self.subTest(screens=screens):
                status, error = self.describe_launch(screens=screens)
                self.assertNotEqual(0, status)
                self.assertFalse(error["valid"])
                self.assertIn(named, error["error"])

    def test_malformed_optional_launch_declarations_are_rejected(self):
        for launch, named in (
            ({"red_error_types": "AttributeError"}, "red_error_types"),
            ({"import_rule": {"product_import": r"^import app"}}, "import_rule.entry_point_import"),
            ({"import_rule": {"product_import": "(", "entry_point_import": "x"}}, "import_rule.product_import"),
        ):
            with self.subTest(launch=launch):
                status, error = self.describe_launch(**launch)
                self.assertNotEqual(0, status)
                self.assertFalse(error["valid"])
                self.assertIn(named, error["error"])

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
