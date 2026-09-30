#!/usr/bin/env python3
"""bin/operator-config must be the one place that reads the Operator
Language: a missing or empty `language` in config/operator.toml has to fail
with a clear, actionable message rather than let a caller silently default to
English (T01, C01 Cockpit V2). Drives the tool by its command line only, per
the Spec's Testing Decisions -- never by importing its internals."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "operator-config"


class OperatorConfigLanguageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="operator-config-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def write_config(self, text):
        path = self.tmp / "operator.toml"
        path.write_text(text)
        return path

    def run_language(self, config_path, check=False):
        return subprocess.run(
            (str(TOOL), "--config", str(config_path), "language"),
            text=True,
            capture_output=True,
            check=check,
        )

    def test_prints_the_configured_language(self):
        config = self.write_config('name = "Benjamin"\nlanguage = "fr"\n')
        result = self.run_language(config, check=True)
        self.assertEqual("fr", result.stdout.strip())

    def test_missing_language_field_fails_with_a_clear_message(self):
        config = self.write_config('name = "Benjamin"\n')
        result = self.run_language(config)
        self.assertNotEqual(0, result.returncode)
        self.assertIn(str(config), result.stderr)
        self.assertIn("language", result.stderr)

    def test_empty_language_field_fails_with_a_clear_message(self):
        config = self.write_config('name = "Benjamin"\nlanguage = ""\n')
        result = self.run_language(config)
        self.assertNotEqual(0, result.returncode)
        self.assertIn(str(config), result.stderr)
        self.assertIn("language", result.stderr)

    def test_missing_config_file_fails_with_a_clear_message(self):
        result = self.run_language(self.tmp / "does-not-exist.toml")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("cannot read", result.stderr)

    def test_unparsable_config_fails_with_a_clear_message(self):
        config = self.write_config("this is not valid toml [[[")
        result = self.run_language(config)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("cannot parse", result.stderr)

    def test_real_operator_toml_declares_a_language(self):
        result = self.run_language(ROOT / "config" / "operator.toml", check=True)
        self.assertTrue(result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
