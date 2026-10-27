#!/usr/bin/env python3
"""Criterion test 1 of the Prototype Fold « Runs et détail des jobs » (C1,
af-lzti7w; Spec af-fgcw0d, user stories 124 and 175, Testing Decisions 5 and
7): the list of runs readable and usable in each of its states, runs-all,
runs-active and runs-completed, in both themes, on a desktop and on a phone,
with the keyboard, and with long contents.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page GET /runs as a headless Chromium renders it, 1440 and 390 px
wide, in the dark theme and in the light one.

False if, in a state, the page is wider than the screen, a text is cut or
drawn on another, a contrast is too low, a control is out of reach of the
keyboard, cannot be activated with it or shows no focus, or a box hides what
it should scroll; if a card does not open its run from the keyboard; or if a
long title or a long name of a job is cut.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runs_destination import LaunchTree, cards, observe_themes, text, unreadable  # noqa: E402

# runs-all, reworded: a workflow with a long title, a word longer than a
# phone is wide in it, and a job with a long name.
LONG_TITLE = ("Recherche dans les notes, les comptes rendus et les dossiers de livraison archivés "
              "notes/archives/2026/comptes-rendus-de-livraison-et-dossiers-de-jugement.md")
LONG_JOB = "Réaliser le périmètre approuvé en conservant la boîte de réception et ses replis"
LONG = {'"title": "Recherche dans les notes"': f'"title": "{LONG_TITLE}"',
        '"name": "Réaliser"': f'"name": "{LONG_JOB}"'}


class RunsDestinationReadableList(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_readable(self, dataset: str, titles: list[str]) -> None:
        """The list of runs of `dataset` shows the cards `titles`, and is
        readable and usable in both themes, on a desktop and on a phone."""
        by_theme = observe_themes(self.tree.launch(dataset), "/runs")
        for frames in by_theme.values():
            for reading in (frame[0] for frame in frames):
                self.assertEqual(titles, [title for card in cards(reading) for title in titles
                                          if title in card["text"]],
                                 f"the list of {dataset} does not show its runs at {reading['width']} px")
        self.assertEqual({}, unreadable(by_theme, ("grid",)), f"the list of {dataset} is not readable")

    def test_runs_all_is_readable_in_both_themes_on_a_desktop_and_a_phone(self):
        self.assert_readable("runs-all", ["Reprise du cockpit", "Recherche dans les notes",
                                          "Corriger le tri des demandes", "Préciser le périmètre du dossier",
                                          "Ancienne proposition de filtre"])

    def test_runs_active_is_readable_in_both_themes_on_a_desktop_and_a_phone(self):
        self.assert_readable("runs-active", ["Reprise du cockpit", "Préciser le périmètre du dossier"])

    def test_runs_completed_is_readable_in_both_themes_on_a_desktop_and_a_phone(self):
        self.assert_readable("runs-completed", ["Recherche dans les notes", "Corriger le tri des demandes",
                                                "Ancienne proposition de filtre"])

    def test_a_card_opens_its_run_from_the_keyboard_and_long_contents_are_read_whole(self):
        address = self.tree.launch("runs-all", self.tree.reword("runs-all", LONG))
        by_theme = observe_themes(address, "/runs", steps=({"click": LONG_TITLE[:40], "within": "grid", "keys": True},))
        for frames in by_theme.values():
            for listed, opened in frames:
                self.assertTrue(any(LONG_TITLE in card["text"] for card in cards(listed)),
                                f"the long title is not said whole at {listed['width']} px")
                self.assertTrue(opened["step"]["found"], "no card of the long title to open")
                self.assertTrue(opened["href"].startswith("/runs/run"),
                                f"Enter on the card did not open its run: {opened['href']}")
                self.assertEqual(LONG_TITLE, text(opened, "h1"), "the card opened another run")
                self.assertIn(LONG_JOB, text(opened, "chart"), "the long name of a job is not said whole")
        self.assertEqual({}, unreadable(by_theme, ()), "a run with long contents is not readable")


if __name__ == "__main__":
    unittest.main()
