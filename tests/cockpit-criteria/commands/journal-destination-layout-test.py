#!/usr/bin/env python3
"""Criterion tests 1 and 2 of F, the Prototype Fold of the Journal
reference (af-njwz8v; Spec af-fgcw0d, user stories 124 and 175, Testing
Decisions 5): the useful events on journal-content, journal-long,
journal-empty and journal-error, and the technical logs on journal-logs,
readable and usable at 1440 and 390 px, in the light and the dark theme,
with long content and with the keyboard.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset of its state, and has a headless
Chromium render GET /journal -- the logs once their tab is opened -- in
two frames, 1440 and 390 px wide, once with the dark and once with the
light colour scheme preferred. On each rendering it requires the parts of
the state, then reads what makes the page unreadable or unusable
(home_destination.problems): the document wider than the frame, a text cut
or drawn on another, a contrast too low, a control without a name, out of
reach of the keyboard or whose focus a person does not see, a local scroll
lost, a page that is not in the theme asked for.

The reference draws some of these defects itself: they are measured on the
product, not copied from the frozen page.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from journal_destination import (  # noqa: E402
    LOG_SEARCH, TITLES, LaunchTree, measure, measure_until, problems, says,
)

WIDTHS = (1440, 390)
HEAD = ("nav-1", "main-1", "filter-row-1", "filter-row-2")
CONTENT_PARTS = HEAD + ("timeline-1", "timeline-2")
LOGS_PARTS = HEAD + ("log-search-1", "panel-1", "readonly-note-1")


class JournalDestinationLayout(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_readable(self, dataset: str, parts: tuple[str, ...], commit: str | None = None, wait: bool = False,
                        opened: str | None = None) -> dict:
        """GET /journal of the cockpit launched on `dataset`, rendered dark
        then light at both widths -- with `opened`, once the control of that
        name was activated --, readable and usable: theme -> frames. With
        `wait`, a state the cockpit reaches after a time is rendered once
        its parts are drawn, or as it stands after 15 s."""
        address = self.tree.launch(dataset, commit)
        drawn = lambda frames: all(p in frames[0]["texts"] for p in parts)  # noqa: E731
        renderings, found = {}, {}
        for theme in ("dark", "light"):
            options = {"path": "/journal", "theme": theme, "widths": WIDTHS, "click": opened}
            frames = measure_until(address, drawn, seconds=15, **options) if wait else measure(address, **options)
            if opened:
                self.assertEqual([True, True], [frame["after"]["found"] for frame in frames],
                                 f"no control « {opened} » on the journal ({theme})")
                frames = [frame["after"] for frame in frames]
            renderings[theme] = frames
            found.update(problems(frames, theme, parts))
        self.assertEqual({}, found)
        return renderings

    # Criterion 1 ---------------------------------------------------------

    def test_journal_content_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("journal-content", CONTENT_PARTS)

    def test_journal_long_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("journal-long", CONTENT_PARTS)

    def test_journal_empty_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("journal-empty", HEAD + ("panel-1",))

    def test_journal_error_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("journal-error", HEAD + ("error-1",), wait=True)

    def test_long_titles_and_words_stay_whole_and_inside_the_page_at_both_widths_in_both_themes(self):
        # The same dataset, at another commit, where an event has a long
        # title and another a word longer than a phone is wide: every
        # rendering stays readable, and each title is said whole.
        long_title = ("Deux améliorations proposées après une revue des parcours, des panneaux et des textes longs "
                      "du cockpit, comme celui-ci")
        long_word = ("Le format CSV a été choisi pour "
                     "Référence/synthétique/chemin_de_ressource_assez_long_pour_le_téléphone")
        reworded = self.tree.reword("journal-long", {"Deux améliorations proposées après une revue": long_title,
                                                     "Le format CSV a été choisi": long_word})
        renderings = self.assert_readable("journal-long", CONTENT_PARTS, commit=reworded)
        for theme, frames in renderings.items():
            for frame in frames:
                self.assertEqual((True, True), (long_title in says(frame, "timeline-item-1"),
                                                long_word in says(frame, "timeline-item-4")),
                                 f"a long title is not said whole at {frame['width']} px, {theme}")

    def test_a_category_and_a_tab_are_chosen_with_the_keyboard(self):
        # Focused, then Enter: « Bugs » keeps the bug alone, « Logs
        # techniques » opens the logs and their search, at both widths.
        address = self.tree.launch("journal-content")
        for frame in measure(address, "/journal", widths=WIDTHS, click="Bugs", keys=True):
            after = frame["after"]
            self.assertTrue(after["found"], f"no control « Bugs » at {frame['width']} px")
            self.assertEqual(["Une recherche sur des notes longues échoue"],
                             [title for title in TITLES if title in after["text"]],
                             f"Enter on « Bugs » did not keep the bug alone at {frame['width']} px")
        address = self.tree.launch("journal-logs")
        for frame in measure(address, "/journal", widths=WIDTHS, click="Logs techniques", keys=True):
            after = frame["after"]
            self.assertTrue(after["found"], f"no control « Logs techniques » at {frame['width']} px")
            self.assertIn(LOG_SEARCH, [c["name"] for c in after["controls"]],
                          f"Enter on « Logs techniques » did not open the logs at {frame['width']} px")

    # Criterion 2 ---------------------------------------------------------

    def test_journal_logs_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("journal-logs", LOGS_PARTS, opened="Logs techniques")


if __name__ == "__main__":
    unittest.main()
