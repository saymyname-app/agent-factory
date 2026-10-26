#!/usr/bin/env python3
"""Criterion test 3 of F, the Prototype Fold of the Journal reference
(af-njwz8v; Spec af-fgcw0d, user stories 124 and 175, Testing Decisions
5): the journal on journal-narrow, journal-light, journal-loading,
journal-stale and journal-offline, readable and usable at 1440 and 390 px,
in the light and the dark theme, with the keyboard.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset of its state, and has a headless
Chromium render GET /journal in two frames, 1440 and 390 px wide, once with
the dark and once with the light colour scheme preferred; a state the
cockpit reaches after a time (a reading gone stale) is rendered once its
notice is drawn. On each rendering it requires the parts of the state,
then reads what makes the page unreadable or unusable
(home_destination.problems, as in journal-destination-layout-test.py).

The reference draws some of these defects itself: they are measured on the
product, not copied from the frozen page.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from journal_destination import LaunchTree, measure, measure_until, problems  # noqa: E402

WIDTHS = (1440, 390)
HEAD = ("nav-1", "main-1", "filter-row-1", "filter-row-2")
CONTENT_PARTS = HEAD + ("timeline-1", "timeline-2")


class JournalDestinationStatesLayout(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_readable(self, dataset: str, parts: tuple[str, ...], wait: bool = False) -> None:
        address = self.tree.launch(dataset)
        drawn = lambda frames: all(p in frames[0]["texts"] for p in parts)  # noqa: E731
        found = {}
        for theme in ("dark", "light"):
            options = {"path": "/journal", "theme": theme, "widths": WIDTHS}
            frames = measure_until(address, drawn, seconds=15, **options) if wait else measure(address, **options)
            found.update(problems(frames, theme, parts))
        self.assertEqual({}, found)

    # Criterion 3 ---------------------------------------------------------

    def test_journal_narrow_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("journal-narrow", CONTENT_PARTS)

    def test_journal_light_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("journal-light", CONTENT_PARTS)

    def test_journal_loading_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("journal-loading", HEAD + ("panel-1", "skeleton-1"))

    def test_journal_stale_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("journal-stale", ("notice-1",) + CONTENT_PARTS, wait=True)

    def test_journal_offline_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("journal-offline", ("notice-1",) + CONTENT_PARTS, wait=True)


if __name__ == "__main__":
    unittest.main()
