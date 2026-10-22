#!/usr/bin/env python3
"""Criterion test 3 of the Prototype Fold « Runs et détail des jobs » (C1,
af-lzti7w; Spec af-fgcw0d, user stories 124 and 175, Testing Decisions 5 and
7): the detail of a job readable and usable in the states job-code,
job-configuration, job-event and job-gates, in both themes, on a desktop and
on a phone.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page GET /runs/job -- the job the state shows, under the frise of
its run -- as a headless Chromium renders it, 1440 and 390 px wide, in the
dark theme and in the light one. The other states of a job are in
runs-destination-readable-sessions-test.py and
runs-destination-readable-prompts-test.py.

False if, in a state, the page is wider than the screen, a text is cut or
drawn on another, a contrast is too low, a control is out of reach of the
keyboard, cannot be activated with it or shows no focus, or a box hides what
it should scroll.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runs_destination import LaunchTree, details, observe_themes, text, unreadable  # noqa: E402


class RunsDestinationReadableJobs(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_readable(self, dataset: str, run: str, job: str) -> None:
        """The detail of the job `job` of the run `run` the state `dataset`
        shows is drawn under its frise, readable and usable in both themes,
        on a desktop and on a phone."""
        by_theme = observe_themes(self.tree.launch(dataset), "/runs/job")
        for frames in by_theme.values():
            for reading in (frame[0] for frame in frames):
                self.assertEqual(run, text(reading, "h1"), f"not the frise of {dataset} at {reading['width']} px")
                self.assertEqual(1, len(details(reading)), f"no detail of a job in {dataset}")
                self.assertIn(job, text(reading, "inspector-head"), f"not the job {dataset} shows")
        self.assertEqual({}, unreadable(by_theme, ("chart", "detail")), f"the detail of {dataset} is not readable")

    def test_job_code_is_readable_in_both_themes_on_a_desktop_and_a_phone(self):
        self.assert_readable("job-code", "Recherche dans les notes", "Geler")

    def test_job_configuration_is_readable_in_both_themes_on_a_desktop_and_a_phone(self):
        self.assert_readable("job-configuration", "Recherche dans les notes", "Réaliser")

    def test_job_event_is_readable_in_both_themes_on_a_desktop_and_a_phone(self):
        self.assert_readable("job-event", "Recherche dans les notes", "Réaliser")

    def test_job_gates_is_readable_in_both_themes_on_a_desktop_and_a_phone(self):
        self.assert_readable("job-gates", "Recherche dans les notes", "Réaliser")


if __name__ == "__main__":
    unittest.main()
