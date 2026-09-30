#!/usr/bin/env python3

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "rituals-status"
RITUALS = ROOT / "tests" / "fixtures" / "rituals-status" / "rituals.toml"

FAKE_GH = """#!/usr/bin/env bash
echo "$*" >> "{log}"
case "$*" in
  *example-org/widgets*) echo 7 ;;
  *example-org/gadgets*) echo 2 ;;
  *) echo "fake gh: no canned response for: $*" >&2; exit 1 ;;
esac
"""


class RitualsStatusTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        self.gh_log = Path(self.tmp.name) / "gh.log"
        gh_stub = bin_dir / "gh"
        gh_stub.write_text(FAKE_GH.format(log=self.gh_log))
        gh_stub.chmod(gh_stub.stat().st_mode | stat.S_IEXEC)
        self.env = dict(os.environ)
        self.env["PATH"] = f"{bin_dir}:{self.env['PATH']}"

    def status(self, ritual_id, check=False, env=None):
        return subprocess.run(
            (str(TOOL), "status", str(RITUALS), ritual_id),
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=check,
            env=env if env is not None else self.env,
        )

    def test_paused_ritual_reports_paused_without_calling_gh(self):
        # No gh on PATH at all -- if the tool tried to call gh for a paused
        # ritual, this would fail instead of reporting paused.
        env_without_gh = dict(os.environ)
        env_without_gh["PATH"] = "/usr/bin:/bin"
        result = self.status("architecture:factory", check=True, env=env_without_gh)
        payload = json.loads(result.stdout)
        self.assertEqual("paused", payload["status"])
        self.assertIn("refactor churn", payload["reason"])
        self.assertIn("some later event", payload["resume_when"])

    def test_pr_threshold_ritual_reports_due_when_merged_meets_threshold(self):
        result = self.status("architecture:widgets", check=True)
        payload = json.loads(result.stdout)
        self.assertEqual("due", payload["status"])
        self.assertEqual(7, payload["merged_since"])
        self.assertEqual(5, payload["threshold"])
        self.assertIn("example-org/widgets", self.gh_log.read_text())

    def test_pr_threshold_ritual_reports_ok_when_below_threshold(self):
        result = self.status("architecture:gadgets", check=True)
        payload = json.loads(result.stdout)
        self.assertEqual("ok", payload["status"])
        self.assertEqual(2, payload["merged_since"])
        self.assertEqual(5, payload["threshold"])

    def test_unknown_ritual_id_is_refused(self):
        result = self.status("architecture:nonexistent")
        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("error", payload["status"])
        self.assertIn("architecture:nonexistent", payload["error"])


if __name__ == "__main__":
    unittest.main()
