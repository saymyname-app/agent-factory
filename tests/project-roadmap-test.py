#!/usr/bin/env python3
"""bin/project-roadmap. The cases of `done_requires` (R5, af-3r1tmr) call
the command's entry function in this process, with the arguments of the
command line (docs/TEST_GUIDELINE.md, point 2); the other cases launch it as
a real process, and hold its pass and its refusal on the command line."""

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "project-roadmap"
FIXTURES = ROOT / "tests" / "fixtures" / "project-roadmap"

_loader = importlib.machinery.SourceFileLoader("project_roadmap", str(TOOL))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
tool = importlib.util.module_from_spec(_spec)
_loader.exec_module(tool)


def call(*args):
    """The command line, in this process: (exit code, stdout)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = tool.main(list(args))
    return code, out.getvalue()


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

    def validate_here(self, name):
        """`validate` on the fixture `name`, in this process: (exit code, payload)."""
        code, out = call("validate", str(FIXTURES / name))
        return code, json.loads(out)

    def assert_done_requires_refused(self, name, *named):
        code, payload = self.validate_here(name)
        self.assertEqual(1, code)
        self.assertFalse(payload["valid"])
        for word in ("X2", "done_requires", *named):
            self.assertIn(word, payload["error"])
        return payload["error"]

    def test_done_requires_naming_steps_of_the_roadmap_validates_clean(self):
        self.assertEqual((0, {"valid": True}), self.validate_here("done_requires.toml"))

    def test_done_requires_naming_no_step_is_refused_and_names_both(self):
        self.assert_done_requires_refused("done_requires_unknown.toml", "X9", "no step")

    def test_done_requires_that_is_not_a_list_is_refused_and_names_the_step(self):
        self.assert_done_requires_refused("done_requires_not_a_list.toml", "list of step ids")

    def test_done_requires_holding_an_empty_id_is_refused_and_names_the_step(self):
        self.assert_done_requires_refused("done_requires_empty_id.toml", "list of step ids")

    def test_done_requires_holding_a_value_that_is_not_text_is_refused_and_names_the_step(self):
        self.assert_done_requires_refused("done_requires_not_text.toml", "list of step ids")

    def test_done_requires_naming_the_step_itself_is_refused(self):
        error = self.assert_done_requires_refused("done_requires_itself.toml")
        self.assertIn("itself", error)

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
