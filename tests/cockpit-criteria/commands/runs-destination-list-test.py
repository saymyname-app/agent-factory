#!/usr/bin/env python3
"""Criterion test 1 of the Prototype Fold « Runs et détail des jobs » (C1,
af-lzti7w; Spec af-fgcw0d, user stories 127, 128 and 135, Testing
Decisions 1, 5 and 7): the list of runs, states runs-all, runs-active and
runs-completed.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page the cockpit serves at its address GET /runs as a headless
Chromium renders it. It holds the page to the Validated Prototype
(prototype/c01-parcours-20261011 at d8cb462, prototypes/c01-flow/frozen-runs):
one card per complete workflow -- its type, its status, its title, its
step, what triggered it and its project, its start, its duration and a
mini frise with a row per participant and a bar per job --, the filters
Tous / En cours / Terminés, and a card that opens its run.

A delivery D01 of the datasets is written as the tracker holds one: the
author's workflow runs on its ticket, its code review and its Ticket
Evaluation each run as a workflow of their own, on the bead the dispatch
door wrote to launch them. One card per D01 is therefore a card that holds
them all, Léa's and Noé's rows in its mini frise.

False if a card stands for one session or one job instead of a whole
workflow, if the runs listed change from one reading to the next, or if a
result Delivered that waits for Benjamin's judgment is listed as finished.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runs_destination import LaunchTree, anchor, cards, observe, seconds, text  # noqa: E402

# The five workflows of the datasets, as the reference draws their cards:
# what each card says, the rows of its mini frise (who, bars), and, for a
# run still open, the least it has lasted -- its horizon is now.
PUBLISHED = ["Déclencheur : Graphe publié", "par benjamin", "Projet : agent-factory"]
COCKPIT = {"says": ["Livraison D01", "En cours", "Reprise du cockpit", "Revue du code · Essayer la tâche",
                    "Début 15:00 (Paris)", *PUBLISHED],
           "rows": [("Humain", 1), ("Code", 2), ("Alex", 2), ("Léa", 2), ("Noé", 1)], "at_least": 450}
SEARCH = {"says": ["Livraison D01", "Fusionné", "Recherche dans les notes",
                   "Exécution terminée · historique disponible", "Début 14:10 (Paris)", "12 min 0 s", *PUBLISHED],
          "rows": [("Humain", 2), ("Code", 4), ("Alex", 2), ("Léa", 2), ("Noé", 2)]}
FIX = {"says": ["Maintenance", "Terminé", "Corriger le tri des demandes",
                "Exécution terminée · historique disponible", "Début 13:45 (Paris)", "5 min 1 s",
                "Déclencheur : Corriger le tri des demandes", "par benjamin", "Projet : agent-factory"],
       "rows": [("Humain", 1), ("Code", 2), ("Alex", 1), ("Léa", 1)]}
WAIT = {"says": ["Livraison D01", "Ta décision", "Préciser le périmètre du dossier", "Décision attendue",
                 "Début 13:00 (Paris)", *PUBLISHED],
        "rows": [("Humain", 2), ("Code", 1), ("Alex", 1), ("Léa", 1)], "at_least": 580}
ABANDON = {"says": ["Livraison D01", "Abandonné", "Ancienne proposition de filtre",
                    "Exécution terminée · historique disponible", "Début 12:20 (Paris)", "4 min 20 s", *PUBLISHED],
           "rows": [("Humain", 2), ("Code", 1), ("Alex", 1)]}

# runs-all, reworded: « Recherche dans les notes » is Delivered and waits
# for Benjamin's judgment -- « Juger le résultat » is open, nothing was
# merged, the workflow has not ended.
DELIVERED_TO_JUDGE = {
    '"status": "Fusionné",\n        "elapsed": 720,\n        "started": "14:10",\n        "end": 720,':
        '"status": "Ta décision",\n        "elapsed": 690,\n        "started": "14:10",\n        "end": null,',
    '"end": 705,\n            "prompt": "J’ai essayé cette version, elle me convient.",\n'
    '            "result": "Acceptation enregistrée sur la version du dossier."':
        '"end": null,\n            "prompt": "Essayer le résultat livré, puis l’accepter, rendre des constats '
        'ou l’abandonner.",\n            "result": null',
    ',\n          {\n            "id": "promote",\n            "lane": "code",\n'
    '            "name": "Fusionner et clore",\n            "start": 705,\n            "end": 720,\n'
    '            "prompt": null,\n'
    '            "result": "Recontrôles favorables ; fusion prouvée et workflow clos."\n          }': "",
}
SEARCH_TO_JUDGE = {"says": ["Livraison D01", "Ta décision", "Recherche dans les notes", "Juger le résultat",
                            "Début 14:10 (Paris)", *PUBLISHED],
                   "rows": [("Humain", 2), ("Code", 3), ("Alex", 2), ("Léa", 2), ("Noé", 2)], "at_least": 690}


class RunsDestinationList(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def readings(self, dataset: str, steps=(), commit: str | None = None) -> list[dict]:
        """The page GET /runs of the cockpit launched on `dataset`, 1440 px
        wide: read once settled, then after each step."""
        return observe(self.tree.launch(dataset, commit), "/runs", steps=steps)[0]

    def assert_list(self, reading: dict, chosen: str, expected: list[dict]) -> None:
        """The page is the list of runs with the filter `chosen` on, and
        its cards are those `expected`, in their order: each says what the
        card of its workflow says, draws its mini frise, and an open run
        has lasted at least as long as the reference shows it."""
        self.assertTrue(reading["href"].startswith("/runs"), f"not the list of runs: {reading['href']}")
        self.assertEqual("Runs", text(reading, "h1"))
        self.assertEqual(["Tous", "En cours", "Terminés"],
                         [c["name"] for c in reading["controls"] if c["anchor"] in ("chosen", "button", "button-2")
                          and c["name"] in ("Tous", "En cours", "Terminés")],
                         "the filters Tous / En cours / Terminés are not drawn")
        self.assertEqual(chosen, text(reading, "chosen"), "the filter on is not the one the state shows")
        served = cards(reading)
        self.assertEqual(len(expected), len(served),
                         f"not one card per workflow: {[card['text'][:60] for card in served]}")
        for card, wanted in zip(served, expected):
            self.assertEqual([], [phrase for phrase in wanted["says"] if phrase not in card["text"]],
                             f"a card does not say what its workflow is: « {card['text']} »")
            self.assertEqual(wanted["rows"], card["rows"], f"the mini frise of « {wanted['says'][2]} »")
            if "at_least" in wanted:
                lasted = seconds(card["text"])
                self.assertTrue(lasted is not None and lasted >= wanted["at_least"],
                                f"« {wanted['says'][2]} » open has not lasted up to now: « {card['text']} »")

    def test_runs_all_lists_one_card_per_complete_workflow_the_same_on_each_reading(self):
        first, _, again = self.readings("runs-all", steps=({"wait": 1000}, {"reload": True}))
        self.assert_list(first, "Tous", [COCKPIT, SEARCH, FIX, WAIT, ABANDON])
        # Read again: the same five workflows, in the same order -- a run is
        # a stable instance, not a new card at each reading.
        self.assert_list(again, "Tous", [COCKPIT, SEARCH, FIX, WAIT, ABANDON])

    def test_runs_active_lists_the_workflows_still_open(self):
        reading, = self.readings("runs-active")
        self.assert_list(reading, "En cours", [COCKPIT, WAIT])

    def test_runs_completed_lists_the_workflows_that_ended(self):
        reading, = self.readings("runs-completed")
        self.assert_list(reading, "Terminés", [SEARCH, FIX, ABANDON])

    def test_a_filter_keeps_its_runs_and_a_card_opens_its_run(self):
        listed, finished, opened = self.readings("runs-all", steps=(
            {"click": "Terminés", "within": "filters"},
            {"click": "Recherche dans les notes", "within": "grid"},
        ))
        self.assert_list(listed, "Tous", [COCKPIT, SEARCH, FIX, WAIT, ABANDON])
        self.assertTrue(finished["step"]["found"], "no filter « Terminés » to click")
        self.assert_list(finished, "Terminés", [SEARCH, FIX, ABANDON])
        self.assertTrue(opened["step"]["found"], "no card « Recherche dans les notes » to click")
        self.assertTrue(opened["href"].startswith("/runs/run"), f"the card did not open its run: {opened['href']}")
        self.assertEqual("Recherche dans les notes", text(opened, "h1"), "the card opened another run")

    def test_a_result_delivered_and_waiting_for_judgment_is_a_run_still_open(self):
        reworded = self.tree.reword("runs-all", DELIVERED_TO_JUDGE)
        listed, in_progress, finished = self.readings("runs-all", commit=reworded, steps=(
            {"click": "En cours", "within": "filters"},
            {"click": "Terminés", "within": "filters"},
        ))
        self.assert_list(listed, "Tous", [COCKPIT, SEARCH_TO_JUDGE, FIX, WAIT, ABANDON])
        card = next(card for card in cards(listed) if "Recherche dans les notes" in card["text"])
        self.assertEqual([], [word for word in ("Fusionné", "Terminé", "Exécution terminée") if word in card["text"]],
                         f"a result waiting for judgment is shown finished: « {card['text']} »")
        self.assert_list(in_progress, "En cours", [COCKPIT, SEARCH_TO_JUDGE, WAIT])
        self.assert_list(finished, "Terminés", [FIX, ABANDON])
        self.assertIsNotNone(anchor(finished, "grid"), "the list of runs is not drawn")


if __name__ == "__main__":
    unittest.main()
