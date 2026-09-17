#!/usr/bin/env python3
"""factory-gh-rollup rebuilds statusCheckRollup from Actions runs.

The Factory token is a fine-grained PAT, which GitHub does not let read check
runs. On 2026-09-18 that silently stopped pr-autopilot from listing any PR.
"""
import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "factory-gh-rollup"

RUNS = {"workflow_runs": [
    {"name": "Factory CI", "status": "completed", "conclusion": "success", "html_url": "u2"},
    {"name": "Factory CI", "status": "completed", "conclusion": "failure", "html_url": "u1"},
    {"name": "Lint", "status": "in_progress", "conclusion": None, "html_url": "u3"},
]}


class RollupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.gh = Path(self.temp.name) / "gh"

    def tearDown(self):
        self.temp.cleanup()

    def stub(self, body: str):
        self.gh.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
        self.gh.chmod(self.gh.stat().st_mode | stat.S_IEXEC)

    def run_tool(self, value):
        return subprocess.run(
            (str(TOOL), "o/r"), input=json.dumps(value), text=True, capture_output=True,
            env={**os.environ, "GH_BIN": str(self.gh)},
        )

    def test_latest_run_per_workflow_wins_and_shape_matches_check_runs(self):
        self.stub(f"echo \"$@\" >> {self.temp.name}/calls\ncat <<'EOF'\n{json.dumps(RUNS)}\nEOF\n")
        result = self.run_tool([{"number": 7, "headRefOid": "abc"}])
        self.assertEqual(0, result.returncode, result.stderr)
        rollup = json.loads(result.stdout)[0]["statusCheckRollup"]
        self.assertEqual(
            [("Factory CI", "COMPLETED", "SUCCESS"), ("Lint", "IN_PROGRESS", "")],
            [(c["name"], c["status"], c["conclusion"]) for c in rollup],
        )
        self.assertIn("head_sha=abc", Path(self.temp.name, "calls").read_text())

    def test_an_existing_rollup_passes_through_without_any_call(self):
        self.stub("exit 9\n")
        value = {"number": 7, "headRefOid": "abc", "statusCheckRollup": [{"name": "x"}]}
        result = self.run_tool(value)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(value, json.loads(result.stdout))

    def test_a_failed_lookup_fails_instead_of_reading_as_no_ci(self):
        self.stub("exit 1\n")
        result = self.run_tool([{"number": 7, "headRefOid": "abc"}])
        self.assertEqual(1, result.returncode)
        self.assertEqual("", result.stdout)


if __name__ == "__main__":
    unittest.main()
