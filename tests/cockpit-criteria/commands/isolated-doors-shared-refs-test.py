#!/usr/bin/env python3
"""Criterion test of R26 (af-qniv4b; Spec af-fgcw0d, Testing Decisions 1, 3
and 8): the regression of the cockpit stays green while another worktree of
its repository commits.

The regression of integration/af-fgcw0d was red on 14/11/2026 for one
reason only: the case `test_an_upkeep_cleans_throwaway_repositories_and_keeps_what_it_must`
of `tests/cockpit-isolated-doors-test.py` read every branch of the
repository it runs in before and after its cleaning, and found one moved.
That repository was a worktree of the Factory's, whose branches every
worktree shares: a commit of the operator on `operator/end2-all`, from its
own worktree, at 15:29:31 (Paris) during the run. The cleaning had touched
nothing of it.

The decor is a disposable Git repository holding the tree this test runs
in, and a second worktree of it on a branch `elsewhere`. The case of the
doors runs there as the regression runs it, its cockpit launched by the
recipe the profile gives `bin/project-launch`; once that cockpit runs,
this test commits in the second worktree, as the operator did, whatever
the case reads of its repository and when.

False if the case fails once another worktree has committed during it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOORS = Path("tests") / "cockpit-isolated-doors-test.py"
CASE = "TheDoors.test_an_upkeep_cleans_throwaway_repositories_and_keeps_what_it_must"
# The recipe of the profile, as the case launches its cockpit.
RECIPE = Path("bin") / "cockpit-isolated"
# Longer than the case takes, cockpit and cleaning included; shorter than forever.
CASE_SECONDS = 300
GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "criterion", "GIT_AUTHOR_EMAIL": "criterion@example.invalid",
           "GIT_COMMITTER_NAME": "criterion", "GIT_COMMITTER_EMAIL": "criterion@example.invalid"}


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, text=True, capture_output=True,
                          env=GIT_ENV).stdout.strip()


class SharedRefs(unittest.TestCase):
    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="isolated-doors-shared-refs-")).resolve()
        self.addCleanup(shutil.rmtree, self.work, True)
        self.repo = self.work / "repo"
        shutil.copytree(ROOT, self.repo, symlinks=True,
                        ignore=shutil.ignore_patterns(".git", ".gc", "__pycache__", "var", "node_modules"))
        git(self.repo, "init", "--quiet", "--initial-branch", "main")
        git(self.repo, "add", "--all", "--force")
        git(self.repo, "commit", "--quiet", "--message", "the tree under test")
        git(self.repo, "branch", "elsewhere")
        self.other = self.work / "elsewhere"
        git(self.repo, "worktree", "add", "--quiet", str(self.other), "elsewhere")

    def running(self, recipe: Path) -> bool:
        """A process of this host runs `recipe`: the cockpit of the case."""
        for cmdline in Path("/proc").glob("[0-9]*/cmdline"):
            try:
                if str(recipe).encode() in cmdline.read_bytes().split(b"\0"):
                    return True
            except OSError:
                pass
        return False

    def test_the_upkeep_case_passes_while_another_worktree_commits(self) -> None:
        before = git(self.repo, "rev-parse", "refs/heads/elsewhere")
        case = subprocess.Popen([sys.executable, str(self.repo / DOORS), CASE], cwd=self.repo, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
        self.addCleanup(case.kill)
        committed = False
        while case.poll() is None and not committed:
            if self.running(self.repo / RECIPE):
                git(self.other, "commit", "--quiet", "--allow-empty", "--message", "a commit of another worktree")
                committed = True
            time.sleep(0.05)
        stdout, stderr = case.communicate(timeout=CASE_SECONDS)
        # The decor did what the operator did: `elsewhere` moved during the case.
        self.assertTrue(committed, "the case ended before its cockpit was seen running")
        self.assertNotEqual(before, git(self.repo, "rev-parse", "refs/heads/elsewhere"))
        self.assertEqual(0, case.returncode, stdout[-4000:] + stderr[-4000:])


if __name__ == "__main__":
    unittest.main()
