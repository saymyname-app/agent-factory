#!/usr/bin/env python3
"""Criterion test 2 of the Prototype Fold « Runs et détail des jobs » (C1,
af-lzti7w; Spec af-fgcw0d, user stories 124 and 175, Testing Decisions 5
and 7), on a narrow screen: the frise of each state run-* at 390 px.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page GET /runs/run as a headless Chromium renders it 390 px wide.

False if the page is wider than the screen: the frise, wider than a phone,
scrolls inside its own box (Spec af-fgcw0d, « Défilement horizontal sur
mobile sans débordement de page »), and every lane stays drawn.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runs_destination import LaunchTree, lanes, observe, text  # noqa: E402

# The boxes of the reference that hold the frise and may scroll it.
FRISE_BOXES = ("chart-box", "scroll", "chart")


class RunsDestinationLayout(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_fits_a_phone(self, dataset: str, title: str, who: list[str]) -> None:
        """At 390 px, the page of the run `title` is no wider than the
        screen, draws the lanes of `who`, and its frise scrolls in its box."""
        reading = observe(self.tree.launch(dataset), "/runs/run", widths=(390,))[0][0]
        self.assertEqual(title, text(reading, "h1"), "the page is not the frise of the run the state shows")
        self.assertEqual(0, reading["overflow"], "the page is wider than a 390 px screen")
        self.assertEqual(who, [lane["name"].split()[0] if lane["name"] else "" for lane in lanes(reading)],
                         "a lane of the run is not drawn at 390 px")
        self.assertTrue(any(box in FRISE_BOXES for box in reading["scrolls"]),
                        f"the frise does not scroll in its own box at 390 px: {reading['scrolls']}")

    def test_run_active_fits_a_390_px_screen(self):
        self.assert_fits_a_phone("run-active", "Reprise du cockpit", ["Benjamin", "Code", "Alex", "Léa", "Noé"])

    def test_run_completed_fits_a_390_px_screen(self):
        self.assert_fits_a_phone("run-completed", "Recherche dans les notes",
                                 ["Benjamin", "Code", "Alex", "Léa", "Noé"])

    def test_run_waiting_fits_a_390_px_screen(self):
        self.assert_fits_a_phone("run-waiting", "Préciser le périmètre du dossier", ["Benjamin", "Code", "Alex", "Léa"])

    def test_run_abandoned_fits_a_390_px_screen(self):
        self.assert_fits_a_phone("run-abandoned", "Ancienne proposition de filtre", ["Benjamin", "Code", "Alex"])

    def test_run_stale_fits_a_390_px_screen(self):
        self.assert_fits_a_phone("run-stale", "Reprise du cockpit", ["Benjamin", "Code", "Alex", "Léa", "Noé"])


if __name__ == "__main__":
    unittest.main()
