#!/usr/bin/env python3
"""Criterion test 3 of the Prototype Fold « Runs et détail des jobs » (C1,
af-lzti7w; Spec af-fgcw0d, user stories 131, 133, 134 and 135, Testing
Decisions 1, 5 and 7): the detail of a job, states job-code and job-event.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on a dataset of the profile, and reads the page the
cockpit serves -- GET /runs/job, the job the state shows, or GET /runs/run
and a click on a job of its frise -- as a headless Chromium renders it. It
holds the page to the Validated Prototype (prototype/c01-parcours-20261011
at d8cb462, prototypes/c01-flow/frozen-runs): the detail opens under the
frise of its run, with its head, its sections that fold, and its events in
the order they happened, at their hour in Paris, each drawn in the colour
of its kind (tools turquoise, controls green, sessions purple, others
grey); a click opens the very event clicked, which says all it records, its
text whole; a reload keeps what was selected. Each event drawn on the frise
is a target a finger or a pointer hits: 24 px by 24 at least, on no other.

What the datasets hold of a job is what the tracker records of it: its
name, its lane, its start, its end and its text, the session that claimed
it, and the check its closing ran -- its events are those: its start and
its end (others), the session (sessions), the check and its outcome
(controls). The configuration, the prompts, the usage, the outputs and the
tool calls are not collected yet (C2a and C2b collect them), and the page
says so.

False if the detail opens in a dialog or on a page of its own without the
frise, if a datum not collected is drawn as a value, if an event is drawn
in another colour than its kind's or cut, or if a reload loses the job or
the event selected.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runs_destination import (  # noqa: E402
    LaunchTree, anchor, anchors, details, events, family, lanes, observe, problems, section, text,
)

NOT_COLLECTED = "non collecté"
# What the reference draws for its example only: values no dataset holds,
# so that a page showing them would have made them up.
EXAMPLE_ONLY = ("synthetic fixture", "demo-search-alex", "demo/search/", "gpt-6.1-sol", "Résultat enregistré",
                "Version correspondante", "31 554", "148 680", "594 720", "Tokens connus")
SEARCH_WHO = ["Benjamin", "Code", "Alex", "Léa", "Noé"]
LEGEND = ("outils (turquoise)", "contrôles (vert)", "sessions (violet)", "autres (gris)")
# job-code, reworded: the job of the code has a long name, a word longer
# than a phone is wide in it.
LONG_NAME = ("Geler l’empreinte des critères et des tests de la tranche avant la réalisation "
             "tests/cockpit-criteria/commands/runs-destination-job-test.py::RunsDestinationJob")
LONG_JOB = {'"name": "Geler"': f'"name": "{LONG_NAME}"'}
TARGET = 24


def overlapping(boxes: list[tuple[str, dict]]) -> list[str]:
    """The pairs of named boxes drawn on each other."""
    found = []
    for index, (one, a) in enumerate(boxes):
        for other, b in boxes[index + 1:]:
            if min(a["right"], b["right"]) - max(a["left"], b["left"]) > 0.5 and \
                    min(a["bottom"], b["bottom"]) - max(a["top"], b["top"]) > 0.5:
                found.append(f"{one} on {other}")
    return found


class RunsDestinationJob(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_detail_under_the_frise(self, reading: dict, run: str, *head: str) -> None:
        """The page shows the frise of the run `run` with all its lanes, and
        under it one detail of a job -- no dialog --, whose head says each of
        `head`."""
        self.assertEqual(run, text(reading, "h1"), "the frise of the run of the job is not on the page")
        self.assertEqual(SEARCH_WHO, [lane["name"].split()[0] if lane["name"] else "" for lane in lanes(reading)],
                         "the frise of the run is not whole beside the detail")
        self.assertEqual([], reading["dialogs"], "the detail of the job opens in a dialog")
        shown = details(reading)
        self.assertEqual(1, len(shown), "not one detail of a job on the page")
        frise = anchor(reading, "chart-box")
        self.assertIsNotNone(frise, "the frise of the run is not drawn")
        self.assertGreaterEqual(shown[0]["box"]["top"], frise["box"]["bottom"] - 1,
                                "the detail of the job is not under the frise")
        said = text(reading, "inspector-head")
        self.assertEqual([], [phrase for phrase in head if phrase not in said],
                         f"the head of the detail does not say it; it says « {said} »")

    def assert_section(self, reading: dict, title: str, *phrases: str) -> None:
        """The detail has a section `title` that folds, which says each of
        `phrases`, open or not."""
        found = section(reading, title)
        self.assertIsNotNone(found, f"the detail has no section « {title} »")
        self.assertEqual("details", found["tag"], f"the section « {title} » does not fold")
        self.assertEqual([], [phrase for phrase in phrases if phrase not in found["content"]],
                         f"the section « {title} » does not say it; it says « {found['content']} »")

    def assert_nothing_made_up(self, reading: dict) -> None:
        detail = details(reading)[0]["content"] if details(reading) else ""
        self.assertEqual([], [value for value in EXAMPLE_ONLY if value in reading["text"] or value in detail],
                         "the page draws values no source holds")

    def test_job_code_opens_its_detail_under_the_frise_with_its_sections_and_events(self):
        reading, = observe(self.tree.launch("job-code"), "/runs/job")[0]
        self.assert_detail_under_the_frise(reading, "Recherche dans les notes", "Geler", "Terminé", "13 s", "Code")
        # A job of the code calls no model: no agent, no prompt, no usage.
        self.assert_section(reading, "Configuration", "Ce job n’utilise pas un agent modèle.")
        self.assert_section(reading, "Description", "Empreinte des critères enregistrée.")
        self.assert_section(reading, "Prompts", "Sans objet")
        self.assert_section(reading, "Contrôles", NOT_COLLECTED)
        self.assert_section(reading, "Tokens et coût", "Aucun appel modèle")
        self.assert_section(reading, "Sorties", NOT_COLLECTED)
        self.assert_nothing_made_up(reading)
        # Its events: the check run and its outcome, as observed, at their
        # hour in Paris -- events of a control: green.
        listed = events(reading)
        self.assertEqual(["14:12:57", "14:13:10"], [event["time"] for event in listed],
                         f"the events of the job are not its check run and its outcome: {[e['text'] for e in listed]}")
        self.assertIn("passé", listed[-1]["text"], "the outcome of the check is not said")
        self.assertEqual([["vert"]] * 2, [sorted({family(c) for c in event["colours"]}) for event in listed],
                         "an event of the job is not drawn in the colour of its kind")
        self.assertEqual([], [phrase for phrase in LEGEND if phrase not in text(reading, "legend")],
                         "the legend does not name the colour of each kind of event")

    def test_job_event_opens_its_detail_with_what_is_not_collected_said_so(self):
        reading, = observe(self.tree.launch("job-event"), "/runs/job")[0]
        self.assert_detail_under_the_frise(reading, "Recherche dans les notes", "Réaliser", "Terminé", "2 min 55 s",
                                           "Alex")
        self.assert_section(reading, "Configuration", NOT_COLLECTED)
        self.assert_section(reading, "Sessions", NOT_COLLECTED)
        self.assert_section(reading, "Description", "Implémenter le périmètre approuvé du cockpit en conservant "
                                                    "la boîte de réception.")
        self.assert_section(reading, "Prompts", NOT_COLLECTED)
        self.assert_section(reading, "Contrôles", NOT_COLLECTED)
        self.assert_section(reading, "Tokens et coût", NOT_COLLECTED)
        self.assert_section(reading, "Sorties", NOT_COLLECTED)
        self.assert_nothing_made_up(reading)
        listed = events(reading)
        times = [event["time"] for event in listed]
        self.assertTrue(times and times[0] == "14:13:10" and times[-1] == "14:16:05" and times == sorted(times),
                        f"the events of the job are not in order from its start to its end: {times}")
        # Its start and its end grey, the session of Alex that claimed it
        # purple, the check its closing ran green -- each its kind's colour.
        kinds = [(event["kind"], sorted({family(c) for c in event["colours"]})) for event in listed]
        self.assertEqual([("Début", ["gris"]), ("Session", ["violet"]), ("Contrôle", ["vert"]), ("Fin", ["gris"])],
                         kinds, "the events of the job are not drawn in the colour of their kind")
        self.assertIn("Alex", listed[1]["text"], "the session event does not say whose session it is")

    def test_a_click_on_a_job_opens_its_detail_under_the_frise_and_a_reload_keeps_it(self):
        frise, built, reloaded, other = observe(self.tree.launch("run-completed"), "/runs/run", steps=(
            {"click": "Réaliser", "within": "chart"},
            {"reload": True},
            {"click": "Geler", "within": "chart"},
        ))[0]
        self.assertEqual([], details(frise), "a job is open before any click")
        self.assertTrue(built["step"]["found"], "no job « Réaliser » to click in the frise")
        self.assert_detail_under_the_frise(built, "Recherche dans les notes", "Réaliser", "2 min 55 s")
        self.assert_detail_under_the_frise(reloaded, "Recherche dans les notes", "Réaliser", "2 min 55 s")
        self.assertTrue(other["step"]["found"], "no job « Geler » to click in the frise")
        self.assert_detail_under_the_frise(other, "Recherche dans les notes", "Geler", "13 s")
        self.assertNotIn("Réaliser", text(other, "inspector-head"), "the detail of the job before stays drawn")

    def test_a_click_on_an_event_opens_that_event_and_a_reload_keeps_it(self):
        job, clicked, reloaded = observe(self.tree.launch("job-code"), "/runs/job", steps=(
            {"click": "14:13:10", "within": "event-list"},
            {"reload": True},
        ))[0]
        self.assert_detail_under_the_frise(job, "Recherche dans les notes", "Geler")
        self.assertTrue(clicked["step"]["found"], "no event of 14:13:10 to click")
        for reading in (clicked, reloaded):
            self.assert_detail_under_the_frise(reading, "Recherche dans les notes", "Geler")
            opened = [event for event in events(reading) if event["open"]]
            self.assertEqual(["14:13:10"], [event["time"] for event in opened],
                             "the event clicked is not the one event open")
            self.assertGreater(len(opened[0]["content"]), len(opened[0]["text"]),
                               "the event open says nothing more than its line")
            self.assertGreaterEqual(opened[0]["content"].count("Geler : passé"), 2,
                                    "the event open does not say its text whole, beside its line")

    def test_each_event_of_the_frise_is_a_target_of_24_px_on_no_other(self):
        address = self.tree.launch("job-event")
        for reading in (frame[0] for frame in observe(address, "/runs/job", widths=(1440, 390))):
            marks = [a for a in anchors(reading, "mark", within="chart") if a["drawn"]]
            # The run « Recherche dans les notes »: 2 events for each of the 6
            # jobs of Benjamin and of the code, 4 for each of the 6 of agents.
            self.assertEqual(36, len(marks), f"not every event of the run is drawn on its frise at {reading['width']} px")
            small = [f"{m['name']} {m['box']['width']:.0f}x{m['box']['height']:.0f}" for m in marks
                     if m["box"]["width"] < TARGET - 0.5 or m["box"]["height"] < TARGET - 0.5]
            self.assertEqual([], small, f"an event of the frise is smaller than {TARGET} px at {reading['width']} px")
            targets = [(a["name"], a["box"]) for a in reading["anchors"] if a["drawn"] and "chart" in a["chain"]
                       and re.fullmatch(r"(?:mark|job-select)(?:-\d+)?", a["name"])]
            self.assertEqual([], overlapping(targets), f"two targets of the frise overlap at {reading['width']} px")

    def test_a_long_event_is_said_whole_on_a_phone_and_on_a_desktop(self):
        address = self.tree.launch("job-code", self.tree.reword("job-code", LONG_JOB))
        for theme in ("dark", "light"):
            frames = observe(address, "/runs/job", widths=(1440, 390), theme=theme,
                             steps=({"click": "14:13:10", "within": "event-list"},))
            for job, opened in frames:
                self.assertIn(LONG_NAME, text(job, "inspector-head"), "the detail is not that of the long job")
                listed = [event for event in events(opened) if event["open"]]
                self.assertEqual(["14:13:10"], [event["time"] for event in listed], "the event clicked is not open")
                self.assertIn(f"{LONG_NAME} : passé", listed[0]["text"], "the line of the event does not say it whole")
                self.assertGreaterEqual(listed[0]["content"].count(f"{LONG_NAME} : passé"), 2,
                                        "the event open does not say its text whole, beside its line")
            self.assertEqual({}, problems([reading for frame in frames for reading in frame], theme, ("detail",)),
                             "the detail of a job with a long name is not read whole")


if __name__ == "__main__":
    unittest.main()
