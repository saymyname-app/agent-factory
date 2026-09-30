#!/usr/bin/env python3

import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "project-roadmap"
FIXTURES = ROOT / "tests" / "fixtures" / "project-roadmap"


class ProjectRoadmapTest(unittest.TestCase):
    def validate(self, name, check=False):
        return subprocess.run(
            (str(TOOL), "validate", str(FIXTURES / name)),
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=check,
        )

    def check_target(self, name, target, check=False):
        return subprocess.run(
            (str(TOOL), "check-target", str(FIXTURES / name), target),
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=check,
        )

    def test_valid_roadmap_validates_clean(self):
        result = self.validate("valid.toml", check=True)
        self.assertEqual({"valid": True}, json.loads(result.stdout))

    def test_missing_field_is_refused_and_names_the_step(self):
        result = self.validate("missing_field.toml")
        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["valid"])
        self.assertIn("X2", payload["error"])
        self.assertIn("done_when", payload["error"])

    def test_duplicate_id_is_refused_and_names_the_step(self):
        result = self.validate("duplicate_id.toml")
        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["valid"])
        self.assertIn("X1", payload["error"])
        self.assertIn("duplicate", payload["error"].lower())

    def test_duplicate_order_is_refused_and_names_the_step(self):
        result = self.validate("duplicate_order.toml")
        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["valid"])
        self.assertIn("X1", payload["error"])
        self.assertIn("X2", payload["error"])
        self.assertIn("order", payload["error"].lower())

    def test_unknown_status_is_refused_and_names_the_step(self):
        result = self.validate("unknown_status.toml")
        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["valid"])
        self.assertIn("X2", payload["error"])
        self.assertIn("blocked", payload["error"])

    def test_check_target_finds_a_real_step(self):
        result = self.check_target("valid.toml", "X2", check=True)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["valid"])
        self.assertEqual("X2", payload["step"]["id"])

    def test_check_target_refuses_an_unknown_id(self):
        result = self.check_target("valid.toml", "X9")
        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["valid"])
        self.assertIn("X9", payload["error"])


if __name__ == "__main__":
    unittest.main()
