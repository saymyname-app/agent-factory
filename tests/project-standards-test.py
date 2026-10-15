#!/usr/bin/env python3
"""Public CLI behavior of the project standards status gesture."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / "bin" / "project-standards"


class ProjectStandardsStatusTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        descriptors = self.root / "config" / "project-descriptors"
        descriptors.mkdir(parents=True)
        (descriptors / "sample.json").write_text(json.dumps({
            "contract": "agent-factory-project-descriptor/v1",
            "project_id": "sample", "display_name": "Sample",
            "rigs": ["api", "web"],
            "stacks": {"api": ["java-spring-maven"], "web": ["react-typescript"]},
            "knowledge_repo": "owner/repo", "roadmap_path": "roadmap.toml",
            "rituals_status_command": "true"
        }))
        projects = self.root / "config" / "projects"
        projects.mkdir()
        (projects / "api.toml").write_text('rig_dir = "rigs/api"\n')
        (projects / "web.toml").write_text('rig_dir = "rigs/web"\n')
        (self.root / "rigs" / "api").mkdir(parents=True)
        (self.root / "rigs" / "web").mkdir(parents=True)

    def java_defaults(self):
        source = Path(__file__).resolve().parents[1] / "default-standards" / "java-spring-maven"
        target = self.root / "default-standards" / "java-spring-maven"
        target.mkdir(parents=True)
        for file in source.rglob("*"):
            if file.is_file():
                path = target / file.relative_to(source)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(file.read_bytes())

    def react_defaults(self):
        source = Path(__file__).resolve().parents[1] / "default-standards" / "react-typescript"
        target = self.root / "default-standards" / "react-typescript"
        target.mkdir(parents=True)
        for file in source.rglob("*"):
            if file.is_file():
                path = target / file.relative_to(source)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(file.read_bytes())

    def worktree(self):
        source = self.root / "project"
        source.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(source)], check=True)
        (source / "README.md").write_text("# Project\n")
        env = {**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
               "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}
        subprocess.run(["git", "-C", str(source), "add", "-A"], check=True, env=env)
        subprocess.run(["git", "-C", str(source), "commit", "-qm", "base"], check=True, env=env)
        target = self.root / "project-worktree"
        subprocess.run(["git", "-C", str(source), "worktree", "add", "-qb", "standards", str(target)], check=True)
        (self.root / "config/projects/api.toml").write_text('rig_dir = "project"\n')
        (self.root / "config/projects/web.toml").write_text('rig_dir = "project"\n')
        return source, target

    def adopt(self, target, rig="api", stack="java-spring-maven", package="org.example.app", domain=None):
        command = [str(TOOL), "--repo-root", str(self.root), "adopt", "--rig", rig,
                   "--stack", stack, "--target", str(target)]
        if package:
            command += ["--java-package", package]
        if domain:
            command += ["--domain", domain]
        result = subprocess.run(command, text=True, capture_output=True)
        return result.returncode, json.loads(result.stdout)

    def status(self):
        result = subprocess.run([str(TOOL), "--repo-root", str(self.root), "status"],
                                text=True, capture_output=True)
        return result.returncode, json.loads(result.stdout)

    def test_status_reports_each_rig_and_domain_from_files(self):
        (self.root / "rigs" / "api" / "STANDARDS.md").write_text("# Code\n")
        (self.root / "rigs" / "web" / "DESIGN.md").write_text("# Design\n")
        code, data = self.status()
        self.assertEqual(0, code, data)
        self.assertEqual({"code": "avec", "design": "sans"}, data["projects"][0]["rigs"][0]["standards"])
        self.assertEqual({"code": "sans", "design": "avec"}, data["projects"][0]["rigs"][1]["standards"])
        self.assertEqual(["react-typescript"], data["projects"][0]["rigs"][1]["stacks"])

    def test_adopt_copies_versioned_java_defaults_into_a_worktree(self):
        self.java_defaults()
        _, target = self.worktree()

        code, result = self.adopt(target)

        self.assertEqual(0, code, result)
        self.assertEqual("java-spring-maven", result["stack"])
        self.assertTrue(result["baseline_pending"])
        self.assertTrue((target / "STANDARDS.md").is_file())
        self.assertIn("<groupId>org.example.app</groupId>", (target / "pom.xml").read_text())
        self.assertTrue((target / "src/test/java/org/example/app/ArchitectureTest.java").is_file())
        self.assertNotIn("__JAVA_PACKAGE__", (target / "src/test/java/org/example/app/ArchitectureTest.java").read_text())
        self.assertIn("FreezingArchRule", (target / "src/test/java/org/example/app/ArchitectureTest.java").read_text())
        self.assertTrue((target / "src/test/resources/archunit.properties").is_file())
        self.assertTrue((target / ".github/workflows/code-standards.yml").is_file())
        self.assertTrue((target / ".factory/bin/standards-ratchet").is_file())
        self.assertIn("standards-ratchet", (target / ".github/workflows/code-standards.yml").read_text())
        self.assertEqual("java-spring-maven", json.loads(
            (target / ".factory" / "standards-origin.json").read_text())["stack"])

    def test_status_shows_copied_version_and_unconfirmed_choices(self):
        self.java_defaults()
        _, target = self.worktree()
        self.assertEqual(0, self.adopt(target)[0])
        with (target / "STANDARDS.md").open("a", encoding="utf-8") as handle:
            handle.write("- User choice: recommended — par défaut, non confirmée.\n")
        (target / ".factory/frozen-list.json").write_text(json.dumps({
            "contract": "agent-factory-frozen-list/v1",
            "entries": [{"rule": "architecture/layer", "path": "src/Old.java", "count": 2}]}))
        store = target / ".factory/archunit-freeze"
        store.mkdir()
        (store / "stored.rules").write_text("architecture=sample-id\n")
        (store / "sample-id").write_text(
            "Field <org.example.app.persistence.Dao.api> has type <org.example.app.web.Api> in (Dao.java:1)\n")
        (self.root / "config/projects/api.toml").write_text('rig_dir = "project-worktree"\n')

        code, result = self.status()

        self.assertEqual(0, code, result)
        api = result["projects"][0]["rigs"][0]
        self.assertEqual({"stack": "java-spring-maven", "version": "2"}, api["origin"])
        self.assertEqual({"java-spring-maven": "2"}, api["latest_versions"])
        self.assertFalse(api["update_available"])
        self.assertTrue(api["baseline_pending"])
        self.assertTrue(api["unconfirmed_choices"])
        self.assertEqual(1, api["frozen_counts"]["architecture/layer"])
        self.assertEqual(1, api["frozen_counts"]["archunit/persistence-to-web"])

    def test_adopt_refuses_unknown_stack_without_writing(self):
        self.java_defaults()
        _, target = self.worktree()

        code, result = self.adopt(target, stack="unknown-stack")

        self.assertNotEqual(0, code)
        self.assertIn("pile", result["error"])
        self.assertFalse((target / "STANDARDS.md").exists())

    def test_adopt_refuses_invalid_java_package_without_writing(self):
        self.java_defaults()
        _, target = self.worktree()
        for package in ("../../outside", "org.Example", "org.class"):
            with self.subTest(package=package):
                code, result = self.adopt(target, package=package)
                self.assertNotEqual(0, code)
                self.assertIn("paquet Java", result["error"])
                self.assertFalse((target / "pom.xml").exists())

    def test_adopt_refuses_declared_stack_without_defaults(self):
        _, target = self.worktree()
        code, result = self.adopt(target, rig="web", stack="react-typescript", package="")
        self.assertNotEqual(0, code)
        self.assertIn("aucun Default Standards", result["error"])
        self.assertFalse((target / "STANDARDS.md").exists())

    def test_adopt_refuses_main_checkout_and_existing_standard(self):
        self.java_defaults()
        source, target = self.worktree()
        code, result = self.adopt(source)
        self.assertNotEqual(0, code)
        self.assertIn("worktree", result["error"])
        (target / "STANDARDS.md").write_text("# Local\n")
        code, result = self.adopt(target)
        self.assertNotEqual(0, code)
        self.assertEqual("# Local\n", (target / "STANDARDS.md").read_text())

    def test_adopt_refuses_worktree_of_another_repo(self):
        self.java_defaults()
        self.worktree()
        other = self.root / "other"
        other.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(other)], check=True)
        (other / "README.md").write_text("# Other\n")
        env = {**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
               "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}
        subprocess.run(["git", "-C", str(other), "add", "-A"], check=True, env=env)
        subprocess.run(["git", "-C", str(other), "commit", "-qm", "base"], check=True, env=env)
        wrong = self.root / "other-worktree"
        subprocess.run(["git", "-C", str(other), "worktree", "add", "-qb", "standards", str(wrong)], check=True)

        code, result = self.adopt(wrong)

        self.assertNotEqual(0, code)
        self.assertIn("rig api", result["error"])
        self.assertFalse((wrong / "STANDARDS.md").exists())

    def test_adopt_copies_react_typescript_defaults_into_a_worktree(self):
        self.react_defaults()
        _, target = self.worktree()
        code, result = self.adopt(target, rig="web", stack="react-typescript", package="")
        self.assertEqual(0, code, result)
        self.assertTrue((target / "STANDARDS.md").is_file())
        self.assertTrue((target / "package.json").is_file())
        self.assertTrue((target / "package-lock.json").is_file())
        self.assertTrue((target / "eslint.config.mjs").is_file())
        self.assertTrue((target / ".dependency-cruiser.cjs").is_file())
        self.assertTrue((target / ".github/workflows/code-standards.yml").is_file())
        self.assertTrue((target / ".factory/bin/standards-ratchet").is_file())
        self.assertIn("standards-ratchet", (target / ".github/workflows/code-standards.yml").read_text())
        origin = json.loads((target / ".factory/standards-origin.json").read_text())
        self.assertEqual({"contract": "agent-factory-standards-origin/v1",
                          "stack": "react-typescript", "version": "2"}, origin)
        (target / "eslint-suppressions.json").write_text(json.dumps({
            "src/App.tsx": {"@typescript-eslint/no-explicit-any": {"count": 2}}}))
        (self.root / "config/projects/web.toml").write_text('rig_dir = "project-worktree"\n')
        self.assertEqual({"@typescript-eslint/no-explicit-any": 1}, self.status()[1]["projects"][0]["rigs"][1]["frozen_counts"])

    def test_react_code_adoption_does_not_activate_design(self):
        self.react_defaults()
        _, target = self.worktree()
        code, result = self.adopt(target, rig="web", stack="react-typescript", package="")
        self.assertEqual(0, code, result)
        self.assertFalse((target / "DESIGN.md").exists())
        self.assertFalse((target / "src/theme/tokens.css").exists())

    def test_design_adoption_copies_separate_defaults_and_reports_origin(self):
        self.react_defaults()
        generated = self.root / "default-standards/react-typescript/design/design-bench/node_modules/junk"
        generated.parent.mkdir(parents=True)
        generated.write_text("generated, not a standard")
        _, target = self.worktree()
        self.assertEqual(0, self.adopt(target, rig="web", stack="react-typescript", package="")[0])
        code, result = self.adopt(target, rig="web", stack="react-typescript", package="", domain="design")
        self.assertEqual(0, code, result)
        self.assertEqual("design", result["domain"])
        self.assertTrue((target / "DESIGN.md").is_file())
        self.assertTrue((target / "src/theme/tokens.css").is_file())
        self.assertTrue((target / ".github/workflows/design-standards.yml").is_file())
        self.assertTrue((target / "design-bench/package-lock.json").is_file())
        self.assertTrue((target / "design-bench/bench.spec.mjs").is_file())
        self.assertTrue((target / "design-bench/check-visual-change.py").is_file())
        self.assertTrue((target / "design-bench/visual-changes.json").is_file())
        self.assertFalse((target / "design-bench/node_modules").exists())
        design_origin = json.loads((target / ".factory/design-standards-origin.json").read_text())
        self.assertEqual({"contract": "agent-factory-standards-origin/v1",
                          "stack": "react-typescript", "version": "4"}, design_origin)
        (self.root / "config/projects/web.toml").write_text('rig_dir = "project-worktree"\n')
        code, status = self.status()
        self.assertEqual(0, code, status)
        web = status["projects"][0]["rigs"][1]
        self.assertEqual("avec", web["standards"]["design"])
        self.assertEqual({"stack": "react-typescript", "version": "4"}, web["design_origin"])
        self.assertEqual({"react-typescript": "4"}, web["latest_design_versions"])
        self.assertFalse(web["design_update_available"])
        (self.root / "default-standards/react-typescript/design/VERSION").write_text("5\n")
        code, status = self.status()
        self.assertEqual(0, code, status)
        self.assertTrue(status["projects"][0]["rigs"][1]["design_update_available"])

    def test_design_adoption_refuses_to_replace_a_project_design(self):
        self.react_defaults()
        _, target = self.worktree()
        (target / "DESIGN.md").write_text("# Product design\n")
        code, result = self.adopt(target, rig="web", stack="react-typescript", package="", domain="design")
        self.assertNotEqual(0, code)
        self.assertIn("fichier existant", result["error"])
        self.assertEqual("# Product design\n", (target / "DESIGN.md").read_text())
        self.assertFalse((target / ".factory/design-standards-origin.json").exists())

    def test_react_adoption_refuses_to_replace_existing_package(self):
        self.react_defaults()
        _, target = self.worktree()
        (target / "package.json").write_text('{"name":"local"}\n')
        code, result = self.adopt(target, rig="web", stack="react-typescript", package="")
        self.assertNotEqual(0, code)
        self.assertIn("fichier existant", result["error"])
        self.assertEqual('{"name":"local"}\n', (target / "package.json").read_text())
        self.assertFalse((target / "STANDARDS.md").exists())

    def test_status_refuses_missing_rig_checkout(self):
        (self.root / "rigs" / "web").rmdir()
        code, result = self.status()
        self.assertNotEqual(0, code)
        self.assertIn("web", result["error"])

    def test_status_refuses_missing_stack_declaration(self):
        path = self.root / "config" / "project-descriptors" / "sample.json"
        data = json.loads(path.read_text())
        del data["stacks"]["web"]
        path.write_text(json.dumps(data))
        code, result = self.status()
        self.assertNotEqual(0, code)
        self.assertIn("web", result["error"])

    def test_status_refuses_origin_from_undeclared_stack(self):
        (self.root / "rigs/api/.factory").mkdir()
        (self.root / "rigs/api/.factory/standards-origin.json").write_text(
            json.dumps({"contract": "agent-factory-standards-origin/v1",
                        "stack": "react-typescript", "version": "1"}))
        code, result = self.status()
        self.assertNotEqual(0, code)
        self.assertIn("api", result["error"])

    def test_status_reports_malformed_origin_as_json_refusal(self):
        (self.root / "rigs/api/.factory").mkdir()
        (self.root / "rigs/api/.factory/standards-origin.json").write_text("[]")
        code, result = self.status()
        self.assertNotEqual(0, code)
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
