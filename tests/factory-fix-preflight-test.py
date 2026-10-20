#!/usr/bin/env python3
"""bin/factory-fix-preflight on a throwaway repository and fake gh/gc
(af-frflvz). Before a Factory fix is coded, and again before its pull
request opens, the tool names what else is changing the same files -- an
open pull request, a recent branch -- and the decisions that name them, and
lists every decision of the last days to read. #681 made fidelity blocking
while Benjamin, in another session, had just decided it would not be
(af-hcriwn); #682 undid it an hour later."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "factory-fix-preflight"
EXIT_FOUND, EXIT_REFUSED = 1, 2


def iso(delta_hours):
    return (datetime.now(timezone.utc) - timedelta(hours=delta_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


class FactoryFixPreflightTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="factory-fix-preflight-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.remote = self.tmp / "remote.git"
        self.repo = self.tmp / "repo"
        self.git(self.tmp, "init", "-q", "--bare", "-b", "main", str(self.remote))
        self.git(self.tmp, "clone", "-q", str(self.remote), str(self.repo))
        for name in ("bin/ticket-exit", "bin/ticket-end", "docs/PROTOTYPE_FIDELITY.md"):
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("base\n")
        self.commit("base")
        self.git(self.repo, "push", "-q", "origin", "HEAD:main")
        self.git(self.repo, "checkout", "-q", "-b", "fix/mine")
        self.prs = self.tmp / "prs.json"
        self.prs.write_text("[]")
        self.decisions = self.tmp / "decisions.json"
        self.decisions.write_text("[]")
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "gh").write_text(
            '#!/bin/sh\n[ "$1 $2" = "pr list" ] || exit 1\n[ -f "$PREFLIGHT_FAKE_PRS" ] || exit 1\n'
            'cat "$PREFLIGHT_FAKE_PRS"\n')
        (bin_dir / "gc").write_text(
            '#!/bin/sh\necho "$*" >> "$PREFLIGHT_FAKE_GC_LOG"\n[ "$1 $2 $3" = "bd list --all" ] || exit 1\n'
            'cat "$PREFLIGHT_FAKE_DECISIONS"\n')
        for stub in ("gh", "gc"):
            (bin_dir / stub).chmod(0o755)
        self.env = {**os.environ, "GH_BIN": str(bin_dir / "gh"), "GC_BIN": str(bin_dir / "gc"),
                    "PREFLIGHT_FAKE_PRS": str(self.prs), "PREFLIGHT_FAKE_DECISIONS": str(self.decisions),
                    "PREFLIGHT_FAKE_GC_LOG": str(self.tmp / "gc.log"),
                    "FACTORY_ROOT": str(self.tmp),
                    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}

    def git(self, cwd, *args):
        return subprocess.run(("git", "-C", str(cwd), "-c", "user.name=essai", "-c", "user.email=essai@example.invalid",
                               *args), text=True, capture_output=True, check=True).stdout.strip()

    def commit(self, message):
        self.git(self.repo, "add", "-A")
        self.git(self.repo, "commit", "-q", "-m", message)

    def other_branch(self, name, path):
        """Another session's branch, pushed, changing `path`."""
        self.git(self.repo, "checkout", "-q", "-b", name, "origin/main")
        (self.repo / path).write_text(f"{name}\n")
        self.commit(f"travail de {name}")
        self.git(self.repo, "push", "-q", "origin", name)
        self.git(self.repo, "checkout", "-q", "fix/mine")

    def preflight(self, *paths, expect=0):
        proc = subprocess.run((str(TOOL), "--repo", str(self.repo), *paths), env=self.env, text=True,
                              capture_output=True)
        self.assertEqual(expect, proc.returncode, proc.stdout + proc.stderr)
        return json.loads(proc.stdout)

    def test_nothing_else_on_the_files_is_clear(self):
        answer = self.preflight("bin/ticket-exit")

        self.assertEqual((True, [], [], []),
                         (answer["ok"], answer["prs"], answer["branches"], answer["decisions_naming"]))
        self.assertEqual(["bin/ticket-exit"], answer["paths"])

    def test_an_open_pull_request_on_the_same_file_stops_the_fix(self):
        self.prs.write_text(json.dumps([{"number": 682, "title": "Fidelity never blocking", "url": "u/682",
                                         "headRefName": "fix/visual-fidelity",
                                         "files": [{"path": "bin/ticket-exit"}, {"path": "docs/ADR.md"}]}]))

        answer = self.preflight("bin/ticket-exit", "bin/ticket-end", expect=EXIT_FOUND)

        self.assertFalse(answer["ok"])
        self.assertEqual([(682, "fix/visual-fidelity", ["bin/ticket-exit"])],
                         [(pr["number"], pr["branch"], pr["files"]) for pr in answer["prs"]])

    def test_the_fix_own_pull_request_is_not_counted(self):
        self.prs.write_text(json.dumps([{"number": 681, "title": "mine", "url": "u/681", "headRefName": "fix/mine",
                                         "files": [{"path": "bin/ticket-exit"}]}]))

        self.assertTrue(self.preflight("bin/ticket-exit")["ok"])

    def test_a_pushed_branch_on_the_same_file_stops_the_fix(self):
        self.other_branch("fix/visual-fidelity", "bin/ticket-exit")

        answer = self.preflight("bin/ticket-exit", expect=EXIT_FOUND)

        self.assertEqual([("fix/visual-fidelity", ["bin/ticket-exit"])],
                         [(branch["branch"], branch["files"]) for branch in answer["branches"]])

    def test_the_branch_of_a_merged_pull_request_is_not_counted(self):
        # fix/ticket-exit-fidelity (#681) and fix/visual-fidelity (#682) stay
        # on the remote once squashed into main: finished work, not a fix in
        # progress.
        self.other_branch("fix/visual-fidelity", "bin/ticket-exit")
        self.prs.write_text(json.dumps([{"number": 682, "state": "MERGED", "headRefName": "fix/visual-fidelity"}]))

        self.assertTrue(self.preflight("bin/ticket-exit")["ok"])

    def test_a_directory_covers_the_files_under_it(self):
        self.other_branch("fix/docs", "docs/PROTOTYPE_FIDELITY.md")

        answer = self.preflight("docs/", expect=EXIT_FOUND)

        self.assertEqual(["fix/docs"], [branch["branch"] for branch in answer["branches"]])

    def test_a_branch_on_other_files_is_not_counted(self):
        self.other_branch("fix/elsewhere", "bin/ticket-end")

        self.assertTrue(self.preflight("bin/ticket-exit")["ok"])

    def test_a_decision_naming_the_file_stops_the_fix(self):
        self.decisions.write_text(json.dumps([
            {"id": "af-dec1", "title": "Décision : la sortie de l'auteur", "status": "open", "updated_at": iso(3),
             "description": "bin/ticket-exit ne mesure plus la fidélité."}]))

        answer = self.preflight("bin/ticket-exit", expect=EXIT_FOUND)

        self.assertEqual(["af-dec1"], [decision["id"] for decision in answer["decisions_naming"]])

    def test_every_recent_decision_is_listed_to_read_even_when_it_names_no_file(self):
        # af-hcriwn: « la fidélité au prototype se juge sur ce qui s'affiche »,
        # no file named; #681 changed bin/ticket-exit an hour later.
        self.decisions.write_text(json.dumps([
            {"id": "af-hcriwn", "title": "Décision : la fidélité se juge sur ce qui s'affiche", "status": "closed",
             "updated_at": iso(1), "description": "Fidélité visuelle : ce qui s'affiche doit ressembler au prototype."},
            {"id": "af-old", "title": "Décision ancienne", "status": "closed", "updated_at": iso(24 * 9),
             "description": "rien"}]))

        answer = self.preflight("bin/ticket-exit")

        self.assertTrue(answer["ok"])
        self.assertEqual(["af-hcriwn"], [decision["id"] for decision in answer["decisions_to_read"]])
        self.assertIn("--label-any decision", (self.tmp / "gc.log").read_text())

    def test_an_unreadable_source_is_never_read_as_clear(self):
        self.prs.unlink()

        answer = self.preflight("bin/ticket-exit", expect=EXIT_REFUSED)

        self.assertFalse(answer["ok"])
        self.assertIn("gh pr list", answer["error"])

    def test_no_path_is_refused(self):
        proc = subprocess.run((str(TOOL), "--repo", str(self.repo)), env=self.env, text=True, capture_output=True)
        self.assertNotEqual(0, proc.returncode)


if __name__ == "__main__":
    unittest.main()
