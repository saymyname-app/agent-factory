#!/usr/bin/env python3
"""Criterion test of the journal of the isolated cockpit (T01R6, af-ltchro,
replacing T01R5 af-7zhnnq; Spec af-2zseit, user story 126).

It goes through `bin/project-launch`, the launcher an author, the Evaluator
and the Acceptance Session all use, with the Factory's own profile
(`config/project-descriptors/agent-factory.json`), then through the address
the launcher announces: GET /api/journal. Nothing here reads the code of the
cockpit.

The decor is a disposable Git repository holding the tree this test runs
in, with two commits: the tree as it is (`requested`), then the same tree
where the dataset `journal-content` says something else (`reworded`). A
journal read from the named dataset follows what that dataset says at the
commit launched; a journal read from the live source would not change with
it, and would not be empty on `journal-empty`.

What this proves that `tests/cockpit-isolated-recipe-test.py` does not: that
test proves what the recipe refuses to serve and the mark of its launch.
This proves what the launched cockpit serves from a dataset it accepts.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = "bin/project-launch"
PROFILE = "config/project-descriptors/agent-factory.json"


def git(repo: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "criterion", "GIT_AUTHOR_EMAIL": "criterion@example.invalid",
        "GIT_COMMITTER_NAME": "criterion", "GIT_COMMITTER_EMAIL": "criterion@example.invalid",
    }
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, text=True, capture_output=True, env=env
    ).stdout.strip()


def reword(repo: Path, name: str, replacements: dict[str, str]) -> None:
    """Rewrite the dataset `name` the profile of `repo` declares: each text
    of `replacements` becomes the other, wherever it is written."""
    profile = json.loads((repo / PROFILE).read_text(encoding="utf-8"))
    declared = profile["launch"]["datasets"][name]
    text = (repo / declared).read_text(encoding="utf-8")
    for before, after in replacements.items():
        assert before in text, f"{name} does not say {before!r}"
        text = text.replace(before, after)
    (repo / declared).write_text(text, encoding="utf-8")


def fetch(url: str) -> tuple[int, str, str]:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.status, response.headers.get("Content-Type", ""), response.read().decode("utf-8")


def instant(value) -> datetime | None:
    """The instant an entry's `quand` says, or None when it says none."""
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


class IsolatedCockpitLaunch(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.work = Path(tempfile.mkdtemp(prefix="cockpit-launch-criteria-"))
        cls.repo = cls.work / "repo"
        shutil.copytree(
            ROOT, cls.repo, symlinks=True,
            ignore=shutil.ignore_patterns(".git", ".gc", "__pycache__", "var", "node_modules"),
        )
        git(cls.repo, "init", "--quiet", "--initial-branch", "main")
        git(cls.repo, "add", "--all", "--force")
        git(cls.repo, "commit", "--quiet", "--message", "the tree under test")
        cls.requested = git(cls.repo, "rev-parse", "HEAD")

        # One event says another title, at another time of the same day,
        # of another project: it moves from fourth to second, newest first.
        reword(cls.repo, "journal-content", {"Le format CSV a été choisi": "Le format JSON a été choisi",
                                             "14:20 (Paris) · Notes": "14:45 (Paris) · Carnet",
                                             "Deux améliorations proposées": "Trois améliorations proposées"})
        git(cls.repo, "add", "--all")
        git(cls.repo, "commit", "--quiet", "--message", "journal-content says something else")
        cls.reworded = git(cls.repo, "rev-parse", "HEAD")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.work, ignore_errors=True)

    def setUp(self) -> None:
        self.states: list[Path] = []

    def tearDown(self) -> None:
        for state in self.states:
            if state.exists():
                subprocess.run(
                    [sys.executable, str(ROOT / LAUNCHER), "--repo-root", str(self.repo), "stop",
                     "--state-file", str(state)],
                    text=True, capture_output=True, stdin=subprocess.DEVNULL,
                )

    def launched(self, commit: str, dataset: str) -> str:
        """The address of the cockpit `bin/project-launch start` launched at
        `commit` on `dataset`."""
        state = self.work / f"launch-{self._testMethodName}-{len(self.states)}.json"
        self.states.append(state)
        proc = subprocess.run(
            [sys.executable, str(ROOT / LAUNCHER), "--repo-root", str(self.repo), "start", str(self.repo / PROFILE),
             "--commit", commit, "--dataset", dataset, "--state-file", str(state), "--timeout", "30"],
            text=True, capture_output=True, stdin=subprocess.DEVNULL,
        )
        try:
            record = json.loads(proc.stdout)
        except json.JSONDecodeError:
            self.fail(f"bin/project-launch start answered no JSON (exit {proc.returncode}): {proc.stdout}{proc.stderr}")
        self.assertIs(True, record.get("started"), record)
        self.assertEqual(commit, record["commit"])
        return record["address"]

    def journal(self, commit: str, dataset: str) -> dict:
        """GET /api/journal of the cockpit launched at `commit` on `dataset`,
        once the cockpit says it has read its journal, or as it stands
        after 20 s, for the assertions to say what is missing."""
        address = self.launched(commit, dataset)
        deadline = time.monotonic() + 20
        while True:
            code, content_type, body = fetch(address + "/api/status")
            self.assertEqual(200, code)
            if (json.loads(body).get("journal") or {}).get("freshness") == "fresh" or time.monotonic() > deadline:
                break
            time.sleep(0.2)
        code, content_type, body = fetch(address + "/api/journal")
        self.assertEqual(200, code)
        self.assertTrue(content_type.startswith("application/json"), content_type)
        return json.loads(body)

    # Criterion 1 ---------------------------------------------------------

    def test_the_journal_served_says_the_events_of_the_named_journal_dataset_newest_first(self):
        # journal-content, « Événements utiles », fixed on 12 October 2026:
        # four events under « Aujourd’hui », two under « Hier », newest
        # first, each its title and its « HH:MM (Paris) ».
        content = self.journal(self.requested, "journal-content")
        self.assertEqual("filled", content["state"])
        self.assertEqual(
            [
                ("Deux améliorations proposées après une revue", datetime.fromisoformat("2026-10-12T14:48:00+02:00")),
                ("Le cockpit est prêt à essayer", datetime.fromisoformat("2026-10-12T14:42:00+02:00")),
                ("Une recherche sur des notes longues échoue", datetime.fromisoformat("2026-10-12T14:36:00+02:00")),
                ("Le format CSV a été choisi", datetime.fromisoformat("2026-10-12T14:20:00+02:00")),
                ("La présentation a été fusionnée", datetime.fromisoformat("2026-10-11T18:10:00+02:00")),
                ("La connexion au superviseur a été rétablie", datetime.fromisoformat("2026-10-11T16:05:00+02:00")),
            ],
            [(entry.get("quoi"), instant(entry.get("quand"))) for entry in content["entries"]],
        )

        # The same dataset where one event says another title at another
        # time: the journal follows what the dataset launched says, and
        # orders by the time it says, not by the order it is written in.
        reworded = self.journal(self.reworded, "journal-content")
        self.assertEqual(
            [
                ("Trois améliorations proposées après une revue", datetime.fromisoformat("2026-10-12T14:48:00+02:00")),
                ("Le format JSON a été choisi", datetime.fromisoformat("2026-10-12T14:45:00+02:00")),
                ("Le cockpit est prêt à essayer", datetime.fromisoformat("2026-10-12T14:42:00+02:00")),
                ("Une recherche sur des notes longues échoue", datetime.fromisoformat("2026-10-12T14:36:00+02:00")),
                ("La présentation a été fusionnée", datetime.fromisoformat("2026-10-11T18:10:00+02:00")),
                ("La connexion au superviseur a été rétablie", datetime.fromisoformat("2026-10-11T16:05:00+02:00")),
            ],
            [(entry.get("quoi"), instant(entry.get("quand"))) for entry in reworded["entries"]],
        )

        # journal-empty, « Rien à afficher ici »: a journal read, and empty
        # -- not unknown, and nothing of the live source.
        empty = self.journal(self.requested, "journal-empty")
        self.assertEqual(("filled", []), (empty["state"], empty["entries"]))


if __name__ == "__main__":
    unittest.main()
