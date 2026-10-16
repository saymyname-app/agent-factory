#!/usr/bin/env python3
"""Criterion test of the regression command of the cockpit on a clean tree
outside any Git repository (R1, af-qsloqo; Spec af-2zseit).

The regression command of the Factory's profile
(`config/project-descriptors/agent-factory.json`, `launch.regression_command`)
is run by the TDD green step and by the integration of a Spec at the root
of a tree extracted by `git archive`: no `.git` there, nor around it. Among
its files are the tests of the isolated launcher, `bin/project-launch`
(`tests/project-launch-test.py`), which asked the tree they run in for
`git rev-parse HEAD` and launched `--commit HEAD`: « not a git repository ».

The decor is a copy of the tree this test runs in, without `.git`, in a
fresh temporary directory that no Git repository holds. The test runs the
launcher's test file there as the regression command runs it: from the root
of the tree, with the same interpreter, nothing on stdin.

Why that file and not the whole command: the command runs this very test
(through `tests/cockpit-criteria-test.py`), so running the command from here
would run itself again. Every other file of the command is run by the
command as it is, by CI, and by the demonstration line of the ticket.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = "bin/project-launch"
LAUNCHER_TESTS = "tests/project-launch-test.py"


class RegressionOutsideGit(unittest.TestCase):
    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="cockpit-regression-outside-git-"))
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)
        self.tree = self.work / "tree"
        shutil.copytree(
            ROOT, self.tree, symlinks=True,
            ignore=shutil.ignore_patterns(".git", ".gc", "__pycache__", "var", "node_modules"),
        )
        # The decor holds only if no Git repository is around the copy.
        probe = subprocess.run(
            ["git", "-C", str(self.tree), "rev-parse", "--git-dir"],
            text=True, capture_output=True, stdin=subprocess.DEVNULL,
        )
        self.assertNotEqual(0, probe.returncode, f"a Git repository holds the copy: {probe.stdout}")

    # Criterion 1 ---------------------------------------------------------

    def test_the_isolated_launcher_tests_of_the_regression_pass_on_a_clean_tree_outside_git(self):
        proc = subprocess.run(
            [sys.executable, LAUNCHER_TESTS], cwd=self.tree,
            text=True, capture_output=True, stdin=subprocess.DEVNULL,
        )
        output = proc.stdout + proc.stderr
        self.assertNotIn("not a git repository", output,
                         f"the tests of {LAUNCHER} asked for a Git repository around the tree:\n{output[-4000:]}")
        self.assertEqual(0, proc.returncode,
                         f"{LAUNCHER_TESTS} exited {proc.returncode} outside Git:\n{output[-4000:]}")


if __name__ == "__main__":
    unittest.main()
