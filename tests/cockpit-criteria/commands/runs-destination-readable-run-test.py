#!/usr/bin/env python3
"""Criterion test 2 of the Prototype Fold « Runs et détail des jobs » (C1,
af-lzti7w; Spec af-fgcw0d, user stories 124 and 175, Testing Decisions 5 and
7): the frise of a run readable and usable in each of its states,
run-active, run-completed, run-waiting, run-abandoned and run-stale, in both
themes, on a desktop and on a phone, and with the keyboard.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page GET /runs/run -- the run the state shows -- as a headless
Chromium renders it, 1440 and 390 px wide, in the dark theme and in the
light one.

False if, in a state, the page is wider than the screen, a text is cut or
drawn on another -- the name of a short job among them --, a contrast is too
low, a control is out of reach of the keyboard, cannot be activated with it
or shows no focus, or the frise is hidden by its box rather than scrolled in
it; or if a job does not open its detail from the keyboard.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runs_destination import LaunchTree, details, observe_themes, text, unreadable  # noqa: E402


class RunsDestinationReadableRun(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_readable(self, dataset: str, title: str) -> None:
        """The frise of the run `title` the state `dataset` shows is readable
        and usable in both themes, on a desktop and on a phone."""
        by_theme = observe_themes(self.tree.launch(dataset), "/runs/run")
        for frames in by_theme.values():
            for reading in (frame[0] for frame in frames):
                self.assertEqual(title, text(reading, "h1"), f"not the frise of {dataset} at {reading['width']} px")
        self.assertEqual({}, unreadable(by_theme, ("chart",)), f"the frise of {dataset} is not readable")

    def test_run_active_is_readable_in_both_themes_on_a_desktop_and_a_phone(self):
        self.assert_readable("run-active", "Reprise du cockpit")

    def test_run_completed_is_readable_in_both_themes_on_a_desktop_and_a_phone(self):
        self.assert_readable("run-completed", "Recherche dans les notes")

    def test_run_waiting_is_readable_in_both_themes_on_a_desktop_and_a_phone(self):
        self.assert_readable("run-waiting", "Préciser le périmètre du dossier")

    def test_run_abandoned_is_readable_in_both_themes_on_a_desktop_and_a_phone(self):
        self.assert_readable("run-abandoned", "Ancienne proposition de filtre")

    def test_run_stale_is_readable_in_both_themes_on_a_desktop_and_a_phone(self):
        self.assert_readable("run-stale", "Reprise du cockpit")

    def test_a_job_opens_its_detail_from_the_keyboard(self):
        by_theme = observe_themes(self.tree.launch("run-completed"), "/runs/run",
                                  steps=({"click": "✓ Réaliser", "within": "chart", "keys": True},))
        for frames in by_theme.values():
            for frise, opened in frames:
                self.assertEqual([], details(frise), "a job is open before any key")
                self.assertTrue(opened["step"]["found"], "no job « Réaliser » to reach in the frise")
                self.assertEqual(1, len(details(opened)), f"Enter on the job did not open its detail: {opened['href']}")
                self.assertIn("Réaliser", text(opened, "inspector-head"), "Enter opened the detail of another job")
        self.assertEqual({}, unreadable(by_theme, ("chart",)), "the frise is not readable with a job open")


if __name__ == "__main__":
    unittest.main()
