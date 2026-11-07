#!/usr/bin/env python3
"""Criterion test 1 of K2 « Vue d'ensemble — indicateurs réels et cartes
Runs partagées », replacement of K (af-unu7jp; Spec af-fgcw0d, user story
151, decision « Une seule carte de run » 7; code review F1.4): the recent
runs of the home are of every status -- a run that waits for Benjamin and
an abandoned one too, not only those in progress, merged or finished that
home-recent-runs-test.py (K's) sees among the last started on runs-all.

The case declares a dataset of its own in the profile of the tree under
test, runs-recent -- runs-all, with the run that waits for Benjamin
started at 14:40 and the abandoned one at 14:30 --, launches the real
cockpit on it with the launcher of the profile, bin/project-launch
(project_destination.launch_declared: the next case sees none of it), and
reads the part « Derniers runs » of the home at GET / and the list of
the page Runs at GET /runs (filter « Tous »), over HTTP, as
home-recent-runs-test.py reads them.

False if the home leaves out the run that waits or the abandoned run among
the three last started, draws them in another order than the last started
first, or draws one of them otherwise than the page Runs does.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from home_destination import LaunchTree  # noqa: E402
from project_destination import dataset_of, launch_declared  # noqa: E402

# The reading of the cards of K's test: the cards of the home and of the
# page Runs, and the check that each card of the home is the card of Runs.
_spec = importlib.util.spec_from_file_location("home_recent_runs", HERE / "home-recent-runs-test.py")
home_recent_runs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(home_recent_runs)
text = home_recent_runs.text

# The runs of runs-all moved up among the last started: the one that waits
# for Benjamin (13:00 there) and the abandoned one (12:20 there).
STARTED = {"wait": "14:40", "abandon": "14:30"}


class HomeRecentRunsEveryStatus(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def test_the_home_draws_a_waiting_and_an_abandoned_run_among_the_last_started(self):
        """runs-recent: five workflows, started at 15:00 (in progress),
        14:40 (waits for Benjamin), 14:30 (abandoned), 14:10 (merged) and
        13:45 (a maintenance, finished). The home draws the three last
        started, the last first, each as the page Runs draws it."""
        dataset = dataset_of(self.tree, "runs-all")
        dataset["state"] = "runs-recent"
        for run in dataset["fixtures"]["runs"]:
            run["started"] = STARTED.get(run["id"], run["started"])
        address = launch_declared(self.tree, "runs-recent", dataset)
        cards = [text(card) for card in home_recent_runs.HomeRecentRuns.assert_cards_of_runs(self, address).values()]
        expected = [("Reprise du cockpit", "En cours", "Début 15:00 (Paris)"),
                    ("Préciser le périmètre du dossier", "Ta décision", "Début 14:40 (Paris)"),
                    ("Ancienne proposition de filtre", "Abandonné", "Début 14:30 (Paris)")]
        self.assertEqual(len(expected), len(cards), f"the home does not draw the three runs last started: {cards}")
        self.assertEqual(expected, [tuple(part for part in parts if part in card)
                                    for card, parts in zip(cards, expected)],
                         f"the home does not draw the waiting and abandoned runs last started, "
                         f"the last first: {cards}")


if __name__ == "__main__":
    unittest.main()
