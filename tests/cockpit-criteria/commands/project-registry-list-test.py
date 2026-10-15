#!/usr/bin/env python3
"""Criterion test of the project registry (T62, af-yj8xc9; Spec af-2zseit,
user story 100: one rig belongs to exactly one project).

It goes through `bin/project-planning-profile list`, the public command that
lists the declared projects, given the rigs the City registers
(`--city-registry`, the JSON array `register` already reads). Nothing here
reads the code of the tool.

The decor is a temporary directory of descriptors written in each case: the
values a case verifies stay in the case.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "bin/project-planning-profile"


def descriptor(project_id: str, rigs: list[str]) -> dict:
    return {
        "contract": "agent-factory-project-descriptor/v1",
        "project_id": project_id,
        "display_name": project_id,
        "rigs": rigs,
        "stacks": {rig: ["fixture-stack"] for rig in rigs},
        "knowledge_repo": f"zz-fixture/{project_id}",
        "roadmap_path": "docs/roadmap.toml",
        "rituals_status_command": "bin/rituals-status",
        "promotion_branch": {},
    }


class ProjectRegistryList(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="project-registry-"))
        self.descriptors = self.tmp / "descriptors"
        self.descriptors.mkdir()

    def tearDown(self) -> None:
        subprocess.run(("rm", "-rf", str(self.tmp)), check=False)

    def declare(self, project_id: str, rigs: list[str]) -> None:
        (self.descriptors / f"{project_id}.json").write_text(json.dumps(descriptor(project_id, rigs)), encoding="utf-8")

    def list_projects(self, registered: list[str]) -> tuple[int, dict]:
        registry = self.tmp / "city-registry.json"
        registry.write_text(json.dumps(registered), encoding="utf-8")
        proc = subprocess.run(
            (str(TOOL), "list", "--descriptors-dir", str(self.descriptors), "--city-registry", str(registry)),
            cwd=ROOT, text=True, capture_output=True,
        )
        try:
            answer = json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.fail(f"list answered no JSON object (exit {proc.returncode}): {proc.stdout!r} {proc.stderr!r}")
        return proc.returncode, answer

    def test_a_registry_where_each_rig_has_one_project_is_listed_and_a_rig_without_or_with_two_projects_is_refused_by_its_cause(self):
        self.declare("projet-alpha", ["rig-alpha"])
        self.declare("projet-beta", ["rig-beta-back", "rig-beta-front"])

        status, valid = self.list_projects(["rig-alpha", "rig-beta-back", "rig-beta-front"])
        self.assertEqual(status, 0, valid)
        self.assertTrue(valid["ok"], valid)
        self.assertEqual(sorted(project["project_id"] for project in valid["projects"]), ["projet-alpha", "projet-beta"])

        status, orphan = self.list_projects(["rig-alpha", "rig-beta-back", "rig-beta-front", "rig-orphelin"])
        self.assertNotEqual(status, 0, orphan)
        self.assertFalse(orphan["ok"], orphan)
        self.assertNotIn("projects", orphan)
        self.assertIn("rig-orphelin", orphan["error"])
        self.assertIn("no declared project", orphan["error"])

        self.declare("projet-gamma", ["rig-alpha"])
        status, twice = self.list_projects(["rig-alpha", "rig-beta-back", "rig-beta-front"])
        self.assertNotEqual(status, 0, twice)
        self.assertFalse(twice["ok"], twice)
        self.assertNotIn("projects", twice)
        self.assertIn("rig-alpha", twice["error"])
        self.assertIn("more than one project", twice["error"])
        self.assertIn("projet-alpha", twice["error"])
        self.assertIn("projet-gamma", twice["error"])
        self.assertNotIn("no declared project", twice["error"])


if __name__ == "__main__":
    unittest.main()
