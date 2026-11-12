#!/usr/bin/env python3
"""Criterion test of R20 « Trace des sessions collectée au point d'envoi,
même cockpit arrêté » (af-3l6hbt; Spec af-fgcw0d, user stories 137, 138,
139 and 145, Testing Decisions 1, 7 and 8, « La trace des runs est
collectée au point d'envoi des sessions »; Blocking Finding F1.38 of the
end review at 96b3429f0dee): a session sent while the cockpit was stopped
shows what it was sent and ran with once the cockpit is up again.

The case launches the real cockpit with the launcher of the profile,
bin/project-launch, on a dataset it declares from job-sessions -- the
synthetic city where the dispatch door dispatched the ticket of « Recherche
dans les notes » -- with the place where the launch keeps the projection of
the sessions. At the first launch the supervisor has sent the first session
of « Réaliser » only. The cockpit stops. While it is stopped the supervisor
sends the second session of « Réaliser », then the Factory goes on working:
sixty sessions of another ticket wake and stop after it, more than the
supervisor answers in one page of its log. The cockpit is launched again on
the same projection, and the case reads GET /runs/job -- the job
« Réaliser », whose last session is the one sent during the stop -- as a
headless Chromium renders it and over HTTP.

False if the page says « Aucun prompt n'est enregistré … non collecté » for
that session, or does not show the system prompt and the user prompt it was
sent and the configuration it ran with.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_destination import dataset_of, launch_declared  # noqa: E402
from runs_destination import LaunchTree, observe, section  # noqa: E402
from runs_trace import head_says, percent, prompts, wait_served  # noqa: E402

# More sessions than the supervisor answers in one page of its log (gc
# 1.5.0: 50 events of a type at a time, the latest first).
LATER_SESSIONS = 60


class RunsTraceStoppedCockpit(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def setUp(self) -> None:
        self.kept = Path(tempfile.mkdtemp(prefix="cockpit-stopped-")) / "sessions.jsonl"

    def tearDown(self) -> None:
        self.tree.stop_all()
        shutil.rmtree(self.kept.parent, ignore_errors=True)

    def dataset(self, during_the_stop: bool) -> dict:
        """job-sessions, its projection kept at `self.kept`. Without
        `during_the_stop`, the supervisor has sent the first session of
        « Réaliser » only; with it, also the second, then the sessions of
        « Écrire les tests » of the run « cockpit », one a second, each
        woken and stopped after it."""
        dataset = dataset_of(self.tree, "job-sessions")
        dataset["session_trace"] = str(self.kept)
        runs = {run["id"]: run for run in dataset["fixtures"]["runs"]}
        build = next(job for job in runs["search"]["jobs"] if job["id"] == "build")
        if not during_the_stop:
            build["sessions"] = [session for session in build["sessions"] if session["name"] == "demo-search-alex-1"]
            return dataset
        tests = next(job for job in runs["cockpit"]["jobs"] if job["id"] == "tests")
        tests["sessions"] = [{"name": f"demo-cockpit-alex-{number}", "provider": "codex",
                              "start": tests["start"] + number, "end": tests["start"] + number + 1}
                             for number in range(1, LATER_SESSIONS + 1)]
        return dataset

    def test_a_session_sent_while_the_cockpit_was_stopped_shows_its_prompts_and_configuration_once_it_is_up(self):
        # The first launch: the cockpit collects the first session of
        # « Réaliser », the only one sent yet.
        name = "job-sessions-before-the-stop"
        first = launch_declared(self.tree, name, self.dataset(during_the_stop=False))
        self.assertIn("Version : exemple synthétique, première session",
                      "\n".join(wait_served(first, "/runs/job", ("Version : exemple synthétique, première session",))),
                      "the first launch does not collect the session sent before the stop")
        self.tree.stop_all()
        # The cockpit is up again, on the same projection, after
        # demo-search-alex-2 and the sixty sessions after it were sent.
        again = launch_declared(self.tree, "job-sessions-after-the-stop", self.dataset(during_the_stop=True))
        sent = "\n".join(wait_served(again, "/runs/job", ("Version : exemple synthétique\n",)))
        reading, = observe(again, "/runs/job")[0]
        self.assertIn("Réaliser", head_says(reading), "the detail is not that of the job « Réaliser »")
        listed = section(reading, "Prompts envoyés")
        self.assertIsNotNone(listed, "the detail has no section « Prompts envoyés »")
        self.assertNotRegex(listed["content"], re.compile(r"Aucun prompt n.est enregistré"),
                            "the session sent while the cockpit was stopped has its prompts said not collected")
        # What demo-search-alex-2 was sent: the system prompt of the author,
        # and its own user prompt.
        self.assertIn("Session demo-search-alex-2", listed["content"], "the prompts shown are not those of demo-search-alex-2")
        self.assertEqual({"Prompt système": 1, "Prompt utilisateur": 1},
                         {kind: len(found) for kind, found in prompts(reading).items()},
                         "the prompts sent to demo-search-alex-2 are not each shown once")
        for text in ("# Auteur\n\n# Mission\nRéaliser sur le périmètre approuvé.", "Version : exemple synthétique\n"):
            self.assertIn(text, sent, f"the prompt sent {text!r} is not shown as it was sent")
        # What it ran with, as the supervisor reported it: codex,
        # gpt-6.1-sol, the effort high, in its work directory, its context
        # 7 %.
        configured = section(reading, "Configuration")
        self.assertIsNotNone(configured, "the detail has no section « Configuration »")
        said = configured["content"]
        self.assertIn("Configuration effective", said, f"the configuration in effect is not said: « {said} »")
        effective = said[said.index("Configuration effective"):said.index("Configuration déclarée")
                         if "Configuration déclarée" in said else len(said)]
        for phrase in ("demo-search-alex-2", "codex", "gpt-6.1-sol", "high", "workspace-write",
                       "/srv/synthetic/worktrees/recherche-dans-les-notes"):
            self.assertIn(phrase, effective, f"the configuration in effect does not say « {phrase} »: « {effective} »")
        self.assertRegex(effective, percent(7), f"the configuration in effect does not say its context: « {effective} »")


if __name__ == "__main__":
    unittest.main()
