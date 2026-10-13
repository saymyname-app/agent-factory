#!/usr/bin/env python3
"""Public CLI behavior of the project standards status gesture."""
import json
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


if __name__ == "__main__":
    unittest.main()
