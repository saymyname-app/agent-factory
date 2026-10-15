#!/usr/bin/env python3
"""Public behavior of the copied design bench on disposable project files."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "default-standards/react-typescript/design/design-bench"


class DesignBenchTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        shutil.copytree(BENCH, self.project / "design-bench")
        (self.project / "dist/assets").mkdir(parents=True)
        self.config = self.project / "design-bench/bench.config.json"

    def run_check(self):
        if shutil.which("node"):
            command = ["node", "design-bench/check-bundle.mjs"]
        else:
            command = ["docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}",
                       "-v", f"{self.project}:/app", "-w", "/app", "node:22", "node",
                       "design-bench/check-bundle.mjs"]
        return subprocess.run(command, cwd=self.project, text=True, capture_output=True)

    def test_bundle_under_budget_passes_and_growth_fails(self):
        config = json.loads(self.config.read_text())
        config["bundle"]["maxBytes"] = 100
        self.config.write_text(json.dumps(config))
        (self.project / "dist/assets/app.js").write_bytes(b"a" * 80)
        self.assertEqual(0, self.run_check().returncode)
        (self.project / "dist/assets/extra.css").write_bytes(b"b" * 21)
        result = self.run_check()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("budget", result.stderr)

    def test_missing_build_and_empty_screens_are_refused(self):
        result = self.run_check()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("budget", result.stderr)
        config = json.loads(self.config.read_text())
        config["bundle"]["maxBytes"] = 100
        self.config.write_text(json.dumps(config))
        result = self.run_check()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("aucun asset", result.stderr)


if __name__ == "__main__":
    unittest.main()
