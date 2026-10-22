#!/usr/bin/env python3
"""Criterion test 2 of the Prototype Fold « Runs et détail des jobs » (C1,
af-lzti7w; Spec af-fgcw0d, user stories 128, 129, 131, 132 and 135,
Testing Decisions 1, 5 and 7): the frise of a run, states run-active,
run-completed, run-waiting, run-abandoned and run-stale.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page the cockpit serves at its address GET /runs/run -- the run
the state shows -- as a headless Chromium renders it. It holds the page to
the Validated Prototype (prototype/c01-parcours-20261011 at d8cb462,
prototypes/c01-flow/frozen-runs): a lane Humain, a lane Code and one lane
per logical agent, each job with its observed duration or open, the time
relative to the trigger, the horizon now for a run still open and frozen
at the end of a finished one, what a run waits for, and a stale reading
with the last moment it was observed. Its head says what triggered it and
its project.

False if the timer makes a job, an event or a verdict, if two agents of
the same role share a lane, if a new session of an agent opens a lane of
its own, if the lane Humain or Code is missing because it holds no job, or
if a run abandoned is drawn as a success. The page at 390 px is in
runs-destination-layout-test.py; every state of Runs, in both themes, on a
desktop and a phone, in runs-destination-readable-*-test.py.
"""

from __future__ import annotations

import itertools
import re
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runs_destination import LaunchTree, anchor, family, lanes, observe, seconds, text  # noqa: E402

OPEN = None  # a job still open: « en cours », its duration up to now

# The lanes of the runs of the datasets, as the reference draws them: who,
# their role, and their jobs -- name, duration observed, or OPEN.
BENJAMIN, CODE = ("Benjamin", "Humain"), ("Code", "Contrôles et transitions")
ALEX, LEA, NOE = ("Alex", "Auteur · Codex"), ("Léa", "Relectrice · Claude"), ("Noé", "Évaluateur · Codex")
COCKPIT_LANES = [
    (BENJAMIN, [("Déclencheur", "18 s")]),
    (CODE, [("Préparer le travail", "24 s"), ("Geler", "13 s")]),
    (ALEX, [("Préparer les tests", "1 min 20 s"), ("Réaliser", "2 min 55 s")]),
    (LEA, [("Relire les tests", "55 s"), ("Revue du code", OPEN)]),
    (NOE, [("Essayer la tâche", OPEN)]),
]
SEARCH_LANES = [
    (BENJAMIN, [("Déclencheur", "18 s"), ("Juger le résultat", "15 s")]),
    (CODE, [("Préparer le travail", "24 s"), ("Geler", "13 s"), ("Vérifier l’ensemble", "2 min 0 s"),
            ("Fusionner et clore", "15 s")]),
    (ALEX, [("Préparer les tests", "1 min 20 s"), ("Réaliser", "2 min 55 s")]),
    (LEA, [("Relire les tests", "55 s"), ("Revue du code", "1 min 5 s")]),
    (NOE, [("Essayer la tâche", "1 min 20 s"), ("Essayer le produit", "2 min 0 s")]),
]
WAIT_LANES = [
    (BENJAMIN, [("Déclencheur", "18 s"), ("Décision attendue", OPEN)]),
    (CODE, [("Préparer le travail", "24 s")]),
    (ALEX, [("Préparer les tests", "1 min 20 s")]),
    (LEA, [("Relire les tests", "55 s")]),
]
ABANDON_LANES = [
    (BENJAMIN, [("Déclencheur", "18 s"), ("Abandonner", "30 s")]),
    (CODE, [("Préparer le travail", "24 s")]),
    (ALEX, [("Préparer les tests", "1 min 20 s")]),
]

# run-active, reworded: Noé is a second author beside Alex.
SECOND_AUTHOR = {'"role": "Évaluateur · Codex"': '"role": "Auteur · Codex"'}
# run-abandoned, reworded: Alex did every job, Benjamin's and the code's.
ALEX_ALONE = {'"lane": "human"': '"lane": "alex"', '"lane": "code"': '"lane": "alex"'}
LAST_SEEN = re.compile(r"(?<!\d)\d{1,2}[:h]\d\d(?!\d)")


def events_drawn(reading: dict) -> list[str]:
    """The events drawn on the frise, as each says what it is."""
    return [c["name"] for c in reading["controls"] if c["name"].startswith("Événement")]


def sessions_of(reading: dict, who: str) -> set[str]:
    """The sessions the events of the frise say `who` worked in."""
    said = re.compile(rf"{re.escape(who)} · session (\S+)")
    return {found.group(1) for name in events_drawn(reading) for found in [said.search(name)] if found}


class RunsDestinationFrise(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def reading(self, address: str) -> dict:
        """The page GET /runs/run of the cockpit at `address`, 1440 px wide."""
        return observe(address, "/runs/run")[0][0]

    def head(self, reading: dict) -> str:
        """What the head of the run says above its frise: its summary
        (status, time of the trigger, duration, horizon), what triggered it
        and its project, and the line of its jobs."""
        return f"{text(reading, 'run-summary')} {text(reading, 'origin')} {text(reading, 'p')}"

    def assert_run(self, reading: dict, title: str, *phrases: str) -> None:
        """The page is the frise of the run `title`, whose head says each of
        `phrases`, with its time relative to the trigger: the axis starts at
        0 and the legend says so."""
        self.assertTrue(reading["href"].startswith("/runs/run"), f"not the page of a run: {reading['href']}")
        self.assertEqual(title, text(reading, "h1"), "the page is not the frise of the run the state shows")
        said = self.head(reading)
        self.assertEqual([], [phrase for phrase in phrases if phrase not in said],
                         f"the head of the run does not say it; it says « {said} »")
        self.assertTrue(text(reading, "ticks").startswith("0s"),
                        f"the axis is not the time relative to the trigger: « {text(reading, 'ticks')} »")
        self.assertIn("Origine 0 : déclencheur", text(reading, "legend"))

    def assert_lanes(self, reading: dict, expected: list) -> None:
        """The frise has exactly the lanes `expected`, in their order: who
        and their role, and each job -- its name, and its observed duration
        or « en cours »."""
        served = lanes(reading)
        labels = [f"{who} {role}" for (who, role), _ in expected]
        names = [lane["name"] for lane in served]
        self.assertEqual(labels, [label if name.startswith(label) else name
                                  for name, label in itertools.zip_longest(names, labels, fillvalue="")],
                         "the lanes are not Humain, Code and one per agent of the run")
        for lane, ((who, _), jobs) in zip(served, expected):
            self.assertEqual(len(jobs), len(lane["jobs"]), f"the lane {who} has not its jobs: {lane['jobs']}")
            for job, (name, lasted) in zip(lane["jobs"], jobs):
                self.assertIn(name, job, f"the lane {who} does not draw « {name} »")
                if lasted is OPEN:
                    self.assertIn("en cours", job, f"« {name} » open is not drawn open: « {job} »")
                else:
                    self.assertNotIn("en cours", job, f"« {name} » ended is drawn open: « {job} »")
                    self.assertEqual(seconds(lasted), seconds(job), f"« {name} » has not its observed duration")

    def test_run_active_has_a_lane_per_participant_up_to_now(self):
        reading = self.reading(self.tree.launch("run-active"))
        self.assert_run(reading, "Reprise du cockpit", "En cours", "15:00 (Paris)", "Horizon : maintenant",
                        "Revue du code", "Essayer la tâche", "Déclencheur : Graphe publié", "par benjamin",
                        "Projet : agent-factory")
        self.assertIn("Livraison D01", reading["text"])
        self.assert_lanes(reading, COCKPIT_LANES)
        # The state is the run seven minutes and a half after its trigger,
        # and its horizon is now: no shorter, and not days later.
        lasted = seconds(text(reading, "run-summary"))
        self.assertTrue(lasted is not None and 450 <= lasted < 450 + 600,
                        f"the run open has not lasted from its trigger up to now: « {text(reading, 'run-summary')} »")

    def test_the_timer_only_extends_the_horizon_and_the_jobs_still_open(self):
        address = self.tree.launch("run-active")
        before = self.reading(address)
        time.sleep(3)
        after = self.reading(address)
        for reading in (before, after):
            self.assert_lanes(reading, COCKPIT_LANES)
        self.assertGreater(seconds(text(after, "run-summary")) or 0, seconds(text(before, "run-summary")) or 0,
                           "the horizon of the run open did not move with the time")
        for lane_before, lane_after in zip(lanes(before), lanes(after)):
            for job_before, job_after in zip(lane_before["jobs"], lane_after["jobs"]):
                if "en cours" in job_before:
                    self.assertGreater(seconds(job_after), seconds(job_before),
                                       f"the job open did not last up to now: « {job_before} » then « {job_after} »")
                else:
                    self.assertEqual(job_before, job_after, "a job ended changed with the time")
        self.assertEqual(len(before["controls"]), len(after["controls"]),
                         "the timer added or removed something to click (a job, an event)")
        # Nor a verdict: the status of the run, what it is at, and the state
        # of each job (✓ ended, ● open) are what they were.
        self.assertEqual((text(before, "badge"), text(before, "p")), (text(after, "badge"), text(after, "p")),
                         "the timer changed the status of the run or what it is at")
        self.assertEqual([[job.split()[0] for job in lane["jobs"]] for lane in lanes(before)],
                         [[job.split()[0] for job in lane["jobs"]] for lane in lanes(after)],
                         "the timer changed the state of a job (ended, open)")
        self.assertEqual(events_drawn(before), events_drawn(after), "the timer made or changed an event")

    def test_run_completed_is_frozen_at_its_end(self):
        address = self.tree.launch("run-completed")
        before = self.reading(address)
        self.assert_run(before, "Recherche dans les notes", "Fusionné", "14:10 (Paris)", "12 min 0 s",
                        "Temps final figé", "Déclencheur : Graphe publié", "Projet : agent-factory")
        self.assertTrue(text(before, "ticks").endswith("12m"), f"the axis does not end at the end: {text(before, 'ticks')}")
        self.assert_lanes(before, SEARCH_LANES)
        time.sleep(2)
        after = self.reading(address)
        self.assertEqual((text(before, "run-summary"), lanes(before)), (text(after, "run-summary"), lanes(after)),
                         "a finished run changed with the time")

    def test_run_waiting_says_what_it_waits_for(self):
        reading = self.reading(self.tree.launch("run-waiting"))
        self.assert_run(reading, "Préciser le périmètre du dossier", "Ta décision", "13:00 (Paris)",
                        "Horizon : maintenant", "Décision attendue")
        self.assert_lanes(reading, WAIT_LANES)

    def test_run_abandoned_shows_its_participants_frozen_at_its_end(self):
        reading = self.reading(self.tree.launch("run-abandoned"))
        self.assert_run(reading, "Ancienne proposition de filtre", "Abandonné", "12:20 (Paris)", "4 min 20 s",
                        "Temps final figé")
        self.assertTrue(text(reading, "ticks").endswith("4m20s"),
                        f"the axis does not end at the end: {text(reading, 'ticks')}")
        self.assert_lanes(reading, ABANDON_LANES)
        # Abandoned is not a success: not ticked, not in the colour of one.
        badge = anchor(reading, "badge")
        self.assertIn("Abandonné", badge["text"])
        self.assertNotIn("✓", badge["text"], "the run abandoned is ticked as a success")
        self.assertNotIn("vert", {family(c) for c in badge["colours"]}, "the run abandoned is drawn as a success")

    def test_run_stale_says_the_reading_is_stale_and_when_it_was_last_observed(self):
        address = self.tree.launch("run-stale")
        deadline = time.monotonic() + 20
        while True:
            reading = self.reading(address)
            if (anchor(reading, "notice") or {}).get("drawn") or time.monotonic() > deadline:
                break
            time.sleep(1)
        self.assert_run(reading, "Reprise du cockpit", "En cours", "15:00 (Paris)", "Derniers jobs observés")
        notice = text(reading, "notice")
        self.assertIn("Lecture périmée", notice, "the stale reading is not said")
        self.assertRegex(notice, LAST_SEEN, f"the stale reading does not say when it was last observed: « {notice} »")
        self.assertNotIn("Job courant", self.head(reading), "a stale reading still claims the current jobs")
        self.assert_lanes(reading, COCKPIT_LANES)

    def test_a_run_without_a_job_of_benjamin_or_of_the_code_keeps_their_lanes(self):
        reading = self.reading(self.tree.launch("run-abandoned", self.tree.reword("run-abandoned", ALEX_ALONE)))
        self.assert_run(reading, "Ancienne proposition de filtre", "Abandonné")
        self.assert_lanes(reading, [(BENJAMIN, []), (CODE, []),
                                    (ALEX, [("Déclencheur", "18 s"), ("Préparer le travail", "24 s"),
                                            ("Préparer les tests", "1 min 20 s"), ("Abandonner", "30 s")])])

    def test_a_new_session_of_an_agent_keeps_its_lane(self):
        reading = self.reading(self.tree.launch("run-active"))
        # Alex prepared the tests in a session, then did the work in another:
        # one lane, both jobs.
        self.assertGreaterEqual(len(sessions_of(reading, "Alex")), 2,
                                f"the run does not show Alex in two sessions: {events_drawn(reading)}")
        self.assert_lanes(reading, COCKPIT_LANES)

    def test_two_agents_of_the_same_role_keep_a_lane_each(self):
        reading = self.reading(self.tree.launch("run-active", self.tree.reword("run-active", SECOND_AUTHOR)))
        self.assert_run(reading, "Reprise du cockpit", "En cours")
        self.assert_lanes(reading, [*COCKPIT_LANES[:4], (("Noé", "Auteur · Codex"), [("Essayer la tâche", OPEN)])])


if __name__ == "__main__":
    unittest.main()
