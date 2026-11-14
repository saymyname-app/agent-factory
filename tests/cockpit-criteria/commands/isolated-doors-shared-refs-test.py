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
recipe the profile gives `bin/project-launch`; a `git` placed first on its
PATH commits in the second worktree right after the case has read the
branches of its repository the first time, as the operator did.

False if the case fails once another worktree has committed during it.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOORS = Path("tests") / "cockpit-isolated-doors-test.py"
CASE = "TheDoors.test_an_upkeep_cleans_throwaway_repositories_and_keeps_what_it_must"
GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "criterion", "GIT_AUTHOR_EMAIL": "criterion@example.invalid",
           "GIT_COMMITTER_NAME": "criterion", "GIT_COMMITTER_EMAIL": "criterion@example.invalid"}

# The git of the case: the real one, and once, right after the first reading
# of the branches of the repository under test, a commit in another worktree.
# Its paths are written in it: the launch gives some of its processes an
# environment of its own.
OTHER_WORKTREE_COMMITS = """#!/bin/sh
{git} "$@"
code=$?
if [ "$1" = "-C" ] && [ "$2" = {repo} ] && [ "$3" = "for-each-ref" ] && [ ! -e {committed} ]; then
  : > {committed}
  {git} -C {other} -c user.name=operator -c user.email=operator@example.invalid \\
    commit -q --allow-empty -m "a commit of another worktree" >/dev/null 2>&1
fi
exit $code
"""


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
        tools = self.work / "tools"
        tools.mkdir()
        (tools / "git").write_text(OTHER_WORKTREE_COMMITS.format(
            git=shlex.quote(shutil.which("git")), repo=shlex.quote(str(self.repo)),
            other=shlex.quote(str(self.other)), committed=shlex.quote(str(self.work / "committed"))),
            encoding="utf-8")
        (tools / "git").chmod(0o755)
        self.env = {**os.environ, "PATH": f"{tools}{os.pathsep}{os.environ.get('PATH', os.defpath)}"}

    def test_the_upkeep_case_passes_while_another_worktree_commits(self) -> None:
        before = git(self.repo, "rev-parse", "refs/heads/elsewhere")
        case = subprocess.run([sys.executable, str(self.repo / DOORS), CASE], cwd=self.repo, env=self.env,
                              text=True, capture_output=True, stdin=subprocess.DEVNULL)
        # The decor did what the operator did: `elsewhere` moved during the case.
        self.assertTrue((self.work / "committed").exists(), "the case never read the branches of its repository")
        self.assertNotEqual(before, git(self.repo, "rev-parse", "refs/heads/elsewhere"))
        self.assertEqual(0, case.returncode, case.stdout[-4000:] + case.stderr[-4000:])


if __name__ == "__main__":
    unittest.main()
