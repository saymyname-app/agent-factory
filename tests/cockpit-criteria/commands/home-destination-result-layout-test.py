#!/usr/bin/env python3
"""Criterion test 2 of the Prototype Fold « Vue d’ensemble, décisions et
résultat » (T02, af-0gonc9; Spec af-2zseit, user stories 111, 124 and 175,
Testing Decisions 5): the panels of a result on the destination, on the
fourteen states result-* of its reference, at 1440 and 390 px, in the light
and the dark theme, with the keyboard.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset of its state, and has a headless
Chromium render GET / at both widths in both themes. It requires the panel
of the state and its bar of actions, then reads what makes the page
unreadable or unusable (home_destination.problems: global overflow, texts
cut outside a box that scrolls, texts drawn on each other, contrast,
controls without a name, out of reach of the keyboard or without a
visible focus, a page in another theme than the one asked for). The
states home-* are in home-destination-layout-test.py.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree, measure, problems  # noqa: E402

WIDTHS = (1440, 390)
SHELL = ("nav-1", "main-1", "inbox-1", "panel-2", "panel-4")
# The result to judge: the panel, its resources above, its bar below.
TO_JUDGE = SHELL + ("panel-3", "resource-list-1", "actions-possibles-1")
# A result already judged: the panel of its follow-up.
FOLLOW_UP = SHELL + ("panel-3",)


class HomeDestinationResultLayout(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_readable(self, dataset: str, panels: tuple[str, ...]) -> None:
        """GET / of the cockpit launched on `dataset`, rendered dark then
        light at both widths, has nothing that makes it unreadable or
        unusable."""
        address = self.tree.launch(dataset)
        found = {}
        for theme in ("dark", "light"):
            found.update(problems(measure(address, theme=theme, widths=WIDTHS), theme, panels))
        self.assertEqual({}, found)

    # Criterion 2 ---------------------------------------------------------

    def test_result_ready_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("result-ready", TO_JUDGE)

    def test_result_dossier_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("result-dossier", SHELL + ("panel-3", "row-1", "actions-possibles-1"))

    def test_result_findings_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("result-findings", TO_JUDGE)

    def test_result_returned_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("result-returned", FOLLOW_UP)

    def test_result_repairing_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("result-repairing", FOLLOW_UP)

    def test_result_accepted_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("result-accepted", FOLLOW_UP)

    def test_result_merging_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("result-merging", FOLLOW_UP)

    def test_result_merged_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("result-merged", FOLLOW_UP)

    def test_result_outdated_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("result-outdated", TO_JUDGE)

    def test_result_outage_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("result-outage", TO_JUDGE)

    def test_result_conflict_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("result-conflict", FOLLOW_UP)

    def test_result_abandoned_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("result-abandoned", FOLLOW_UP)

    def test_result_request_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("result-request", SHELL + ("panel-3", "actions-1"))

    def test_result_confirmation_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("result-confirmation", SHELL + ("panel-3", "actions-1", "notice-1"))


if __name__ == "__main__":
    unittest.main()
