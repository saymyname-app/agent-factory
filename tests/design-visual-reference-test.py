#!/usr/bin/env python3
"""Changed visual references require a fresh ticket declaration in a disposable repo."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / "default-standards/react-typescript/design/design-bench/check-visual-change.py"
SNAPSHOT = "design-bench/bench.spec.mjs-snapshots/home-390-light.png"
DECLARATION = "design-bench/visual-changes.json"


class VisualReferenceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        self.git_env = {**os.environ, "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
                        "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.invalid"}
        (self.repo / SNAPSHOT).parent.mkdir(parents=True)
        (self.repo / SNAPSHOT).write_bytes(b"first image")
        (self.repo / DECLARATION).write_text(json.dumps({
            "contract": "agent-factory-visual-changes/v1", "entries": []}))
        self.commit()
        self.base = self.git("rev-parse", "HEAD").stdout.strip()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              capture_output=True, text=True, env=self.git_env)

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-qm", "snapshot")

    def check(self):
        return subprocess.run(["python3", str(TOOL), "--repo", str(self.repo),
                               "--base", self.base, "--head", "HEAD"], capture_output=True, text=True)

    def declaration(self, ticket="af-ticket", intent="La navigation change de forme"):
        (self.repo / DECLARATION).write_text(json.dumps({
            "contract": "agent-factory-visual-changes/v1", "entries": [
                {"path": SNAPSHOT, "ticket": ticket, "intent": intent}]}))

    def test_modified_reference_requires_fresh_declared_visual_change(self):
        (self.repo / SNAPSHOT).write_bytes(b"changed image")
        self.commit()
        denied = self.check()
        self.assertNotEqual(0, denied.returncode)
        self.assertIn("changement visuel non déclaré", denied.stderr)
        self.declaration()
        self.commit()
        allowed = self.check()
        self.assertEqual(0, allowed.returncode, allowed.stderr)
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        (self.repo / SNAPSHOT).write_bytes(b"another changed image")
        self.commit()
        denied = self.check()
        self.assertNotEqual(0, denied.returncode)
        self.assertIn("changement visuel non déclaré", denied.stderr)

    def test_new_reference_is_initial_capture_but_deletion_requires_declaration(self):
        second = self.repo / "design-bench/bench.spec.mjs-snapshots/home-1440-dark.png"
        second.write_bytes(b"initial image")
        self.commit()
        self.assertEqual(0, self.check().returncode)
        (self.repo / SNAPSHOT).unlink()
        self.commit()
        denied = self.check()
        self.assertNotEqual(0, denied.returncode)
        self.assertIn("changement visuel non déclaré", denied.stderr)

    def test_removing_a_declaration_does_not_authorize_a_reference_change(self):
        self.declaration()
        self.commit()
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        (self.repo / SNAPSHOT).write_bytes(b"changed image")
        (self.repo / DECLARATION).unlink()
        self.commit()
        denied = self.check()
        self.assertNotEqual(0, denied.returncode)
        self.assertIn("changement visuel non déclaré", denied.stderr)


if __name__ == "__main__":
    unittest.main()
