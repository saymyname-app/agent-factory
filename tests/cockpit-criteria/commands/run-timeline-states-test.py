#!/usr/bin/env python3
"""Criterion test 1 of the run timeline « frise du run » (T03R, af-hd8wzb,
cut from T03; Spec af-2zseit, user story 129, Testing Decisions 1, 5 and
7): its five frozen states run-active, run-completed, run-waiting,
run-abandoned and run-stale.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page the cockpit serves at GET /runs/run -- the timeline of the
run it shows -- as a headless Chromium renders it, at 1280 and 390 px. It
holds the page to the Validated Prototype of Runs
(prototype/c01-parcours-20261011 at d8cb462,
prototypes/c01-flow/frozen-runs/states/<state>.html), whose words are
written below, each case naming those of its state:

- the navigation B of the cockpit, with Runs as the destination open;
- the run: its workflow, its title, its summary (status, start, duration,
  horizon or final time);
- its lanes, in their order: the human (Benjamin), the code, then one lane
  per logical agent of the run, each its name and role and, for an agent,
  the context of its last session -- no more lanes than these;
- what each lane draws: its jobs, in their order, each its title and
  duration.

False if a state is not rendered (its run, a lane or a job missing), if a
lane is missing or doubled, if the page is an artificial one (served
elsewhere than at GET /runs/run, or not following the data the cockpit
serves), or if the timeline is not that of the run shown.

The marks of each job and every anchor of the reference are held by
run-timeline-fidelity-test.py; criteria 2 and 3 are in
run-timeline-layout-test.py and run-timeline-selection-test.py.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import measure_until  # noqa: E402
from run_timeline import NAVIGATION, TIMELINE, WIDTHS, LaunchTree, lanes, measure, says, tracks  # noqa: E402

# The lanes of the reference: each the phrases it says, in their order.
BENJAMIN = ["Benjamin", "Humain"]
CODE = ["Code", "Contrôles et transitions"]
SESSION = "Contexte · dernière session"
ALEX_7 = ["Alex", "Auteur · Codex", SESSION, "7 %"]
ALEX_19 = ["Alex", "Auteur · Codex", SESSION, "19 %"]
LEA_3 = ["Léa", "Relectrice · Claude", SESSION, "3 %"]
LEA_11 = ["Léa", "Relectrice · Claude", SESSION, "11 %"]
NOE = ["Noé", "Évaluateur · Codex", SESSION, "non collecté"]

# The run « Reprise du cockpit », as run-active and run-stale draw it.
COCKPIT = {
    "workflow": "Livraison D01",
    "title": "Reprise du cockpit",
    "summary": ["En cours", "Déclenché à 15:00 (Paris)", "7 min 30 s", "Horizon : maintenant",
                "Tokens connus 591 653 · usage partiel", "Coût non collecté"],
    "lanes": [BENJAMIN, CODE, ALEX_7, LEA_3, NOE],
    "tracks": [
        ["✓ Déclencheur", "18 s"],
        ["✓ Préparer le travail", "24 s", "✓ Geler", "13 s"],
        ["✓ Préparer les tests", "1 min 20 s", "✓ Réaliser", "2 min 55 s"],
        ["✓ Relire les tests", "55 s", "● Revue du code", "1 min 25 s · en cours"],
        ["● Essayer la tâche", "1 min 20 s · en cours"],
    ],
}
# The run « Recherche dans les notes », as run-completed draws it.
SEARCH = {
    "workflow": "Livraison D01",
    "title": "Recherche dans les notes",
    "summary": ["✓ Fusionné", "Déclenché à 14:10 (Paris)", "12 min 0 s", "Temps final figé",
                "Tokens connus 594 720 · usage partiel", "Coût non collecté"],
    "lanes": [BENJAMIN, CODE, ALEX_7, LEA_3, NOE],
    "tracks": [
        ["✓ Déclencheur", "18 s", "✓ Juger le résultat", "15 s"],
        ["✓ Préparer le travail", "24 s", "✓ Geler", "13 s", "✓ Vérifier l’ensemble", "2 min 0 s",
         "✓ Fusionner et clore", "15 s"],
        ["✓ Préparer les tests", "1 min 20 s", "✓ Réaliser", "2 min 55 s"],
        ["✓ Relire les tests", "55 s", "✓ Revue du code", "1 min 5 s"],
        ["✓ Essayer la tâche", "1 min 20 s", "✓ Essayer le produit", "2 min 0 s"],
    ],
}
# The run « Préciser le périmètre du dossier », as run-waiting draws it.
WAITING = {
    "workflow": "Livraison D01",
    "title": "Préciser le périmètre du dossier",
    "summary": ["Ta décision", "Déclenché à 13:00 (Paris)", "9 min 40 s", "Horizon : maintenant",
                "Tokens connus 297 360 · usage partiel", "Coût non collecté"],
    "lanes": [BENJAMIN, CODE, ALEX_19, LEA_11],
    "tracks": [
        ["✓ Déclencheur", "18 s", "● Décision attendue", "6 min 43 s · en cours"],
        ["✓ Préparer le travail", "24 s"],
        ["✓ Préparer les tests", "1 min 20 s"],
        ["✓ Relire les tests", "55 s"],
    ],
}
# The run « Ancienne proposition de filtre », as run-abandoned draws it.
ABANDONED = {
    "workflow": "Livraison D01",
    "title": "Ancienne proposition de filtre",
    "summary": ["✓ Abandonné", "Déclenché à 12:20 (Paris)", "4 min 20 s", "Temps final figé",
                "Tokens connus 148 680 · usage partiel", "Coût non collecté"],
    "lanes": [BENJAMIN, CODE, ALEX_19],
    "tracks": [
        ["✓ Déclencheur", "18 s", "✓ Abandonner", "30 s"],
        ["✓ Préparer le travail", "24 s"],
        ["✓ Préparer les tests", "1 min 20 s"],
    ],
}


def missing_in_order(text: str, phrases: list[str]) -> list[str]:
    """The phrases `text` does not say, each after the one before it."""
    missing, at = [], 0
    for phrase in phrases:
        found = text.find(phrase, at)
        if found < 0:
            missing.append(phrase)
        else:
            at = found + len(phrase)
    return missing


class RunTimelineStates(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def served(self, dataset: str, commit: str | None = None, ready: str = "chart") -> list[dict]:
        """GET /runs/run of the cockpit launched on `dataset` (at `commit`),
        rendered at both widths once the page shows the anchor `ready`, or
        as it stands after 15 s."""
        address = self.tree.launch(dataset, commit)
        return measure_until(address, lambda frames: all(ready in frame["texts"] for frame in frames), seconds=15,
                             path=TIMELINE, theme="dark", widths=WIDTHS)

    def assert_run(self, frames: list[dict], run: dict) -> None:
        """Each frame is the timeline of `run`, at its address, in the
        navigation B with Runs open: its workflow, title and summary, then
        exactly its lanes, each saying what the reference says, drawing its
        jobs in their order."""
        for frame in frames:
            width = f"{frame['width']} px"
            self.assertEqual(TIMELINE, frame["path"], f"the timeline is not served at its own address ({width})")
            labels = [entry["label"].rstrip("0123456789 ") for entry in frame["nav"]]
            self.assertEqual(NAVIGATION, labels, f"the navigation B is not the cockpit's ({width})")
            self.assertEqual(["Runs"], [label for label, entry in zip(labels, frame["nav"]) if entry["current"]],
                             f"the navigation does not say Runs is open ({width})")
            self.assertEqual(run["title"], says(frame, "h1"), f"the timeline is not that of its run ({width})")
            self.assertIn(run["workflow"], says(frame, "crumb"), f"the workflow of the run is not said ({width})")
            self.assertEqual([], missing_in_order(says(frame, "run-summary"), run["summary"]),
                             f"the summary of the run does not say it; it says « {says(frame, 'run-summary')} » "
                             f"({width})")
            served_lanes = lanes(frame)
            self.assertEqual(len(run["lanes"]), len(served_lanes),
                             f"not one lane for the human, one for the code and one per agent: {served_lanes} "
                             f"({width})")
            self.assertEqual([[] for _ in run["lanes"]],
                             [missing_in_order(text, phrases) for text, phrases in zip(served_lanes, run["lanes"])],
                             f"a lane does not say who it is: {served_lanes} ({width})")
            served_tracks = tracks(frame)
            self.assertEqual(len(run["tracks"]), len(served_tracks), f"a lane draws no track ({width})")
            self.assertEqual([[] for _ in run["tracks"]],
                             [missing_in_order(text, jobs) for text, jobs in zip(served_tracks, run["tracks"])],
                             f"a lane does not draw its jobs in their order: {served_tracks} ({width})")

    # Criterion 1 ---------------------------------------------------------

    def test_run_active_draws_the_run_under_way_in_its_lanes_human_code_and_one_per_agent(self):
        frames = self.served("run-active")
        self.assert_run(frames, COCKPIT)
        for frame in frames:
            self.assertEqual("Job courant : Revue du code · Essayer la tâche", says(frame, "p"))

    def test_run_completed_draws_the_merged_run_at_its_final_time(self):
        self.assert_run(self.served("run-completed"), SEARCH)

    def test_run_waiting_draws_the_run_waiting_for_benjamin_in_his_lane(self):
        frames = self.served("run-waiting")
        self.assert_run(frames, WAITING)
        for frame in frames:
            self.assertEqual("Job courant : Décision attendue", says(frame, "p"))

    def test_run_abandoned_draws_the_abandoned_run_at_its_final_time(self):
        self.assert_run(self.served("run-abandoned"), ABANDONED)

    def test_run_stale_draws_the_last_observation_under_a_notice_that_it_is_stale(self):
        frames = self.served("run-stale", ready="notice")
        self.assert_run(frames, COCKPIT)
        for frame in frames:
            self.assertEqual("Lecture périmée · dernière observation conservée, activité actuelle non confirmée.",
                             says(frame, "notice"))
            self.assertEqual("Derniers jobs observés : Revue du code · Essayer la tâche", says(frame, "p"))

    def test_the_timeline_follows_the_data_the_cockpit_serves_not_a_page_of_its_own(self):
        # The same dataset, at another commit, where the run has another
        # title and an agent another name: the page says them, at the head
        # and in the lane of that agent -- a page drawn for the state would
        # not change.
        reworded = self.tree.reword("run-active", {"Reprise du cockpit": "Reprise du tableau de bord",
                                                   "Léa": "Inès"})
        frames = self.served("run-active", commit=reworded)
        renamed = {**COCKPIT, "title": "Reprise du tableau de bord",
                   "lanes": [BENJAMIN, CODE, ALEX_7, ["Inès", "Relectrice · Claude", SESSION, "3 %"], NOE]}
        self.assert_run(frames, renamed)
        for frame in frames:
            self.assertNotIn("Léa", frame["text"])

    def test_the_timeline_is_that_of_the_run_the_cockpit_shows(self):
        # The same dataset, at another commit, where the run shown is
        # another one of its runs: the head and the lanes are those of that
        # run, not those of the run of the state.
        reworded = self.tree.reword("run-active", {'"run": "cockpit"': '"run": "search"'})
        frames = self.served("run-active", commit=reworded)
        self.assert_run(frames, SEARCH)
        for frame in frames:
            self.assertNotIn("Reprise du cockpit", says(frame, "h1"))


if __name__ == "__main__":
    unittest.main()
