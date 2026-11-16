#!/usr/bin/env python3
"""Criterion test 3 of F, the Prototype Fold of the Journal
reference (af-njwz8v; Spec af-fgcw0d, Testing Decisions 5): the anchors and
the tokens the reference approves, in journal-narrow, journal-light, journal-loading, journal-stale and journal-offline.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page it serves at GET /journal -- as a headless Chromium
renders it, at 1440 and 390 px, in the dark and the light theme, and from
its style sources. It holds the page to the Validated Prototype
(prototype/cockpit-b-zones-20261012 at 632deea,
prototypes/c01-complete/frozen-panorama-journal/states/<state>.html), whose
values are written in journal_destination.py, each case naming those of
its state:

- every anchor of the state, numbered ones as much as named ones, once,
  drawn by the same element inside the same anchor, in the type of the
  reference (its computed font-family and line-height);
- the tokens of the reference under their names, with its values, in the
  dark and the light theme.

False if an anchor of the reference is missing, doubled, drawn otherwise or
elsewhere, or set in another type, or if a token of the reference is absent
or has another value: the hierarchy approved is not the one served.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import tokens_of  # noqa: E402
from journal_destination import (  # noqa: E402
    CONTENT_ANCHORS, LOADING_ANCHORS, STALE_ANCHORS, TOKENS, LaunchTree, anchor_deviations,
    measure, measure_until,
)

WIDTHS = (1440, 390)
THEMES = ("dark", "light")


class JournalDestinationStatesFidelity(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_reference(self, dataset: str, anchors: list, wait: str | None = None, opened: str | None = None) -> None:
        """GET /journal of the cockpit launched on `dataset` -- with
        `opened`, once the control of that name was activated -- carries the
        anchors `anchors` at both widths in both themes, and declares the
        tokens of the reference. With `wait`, a state the cockpit reaches
        after a time is measured once the anchor `wait` is drawn."""
        address = self.tree.launch(dataset)
        found = {}
        for theme in THEMES:
            options = {"path": "/journal", "theme": theme, "widths": WIDTHS, "click": opened}
            frames = (measure_until(address, lambda frames: wait in frames[0]["texts"], seconds=15, **options)
                      if wait else measure(address, **options))
            for frame in frames:
                page = frame["after"] if opened else frame
                deviations = anchor_deviations(page, anchors)
                if deviations:
                    found[f"{frame['width']} px, {theme}"] = deviations
        served = tokens_of(address, "/journal")
        tokens = [f"{name} ({theme}) : {served[theme].get(name)!r}, the reference has {value!r}"
                  for theme, values in TOKENS.items() for name, value in values.items()
                  if served[theme].get(name) != value]
        if tokens:
            found["tokens"] = tokens
        self.assertEqual({}, found)

    # Criterion 3 ---------------------------------------------------------

    def test_journal_narrow_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("journal-narrow", CONTENT_ANCHORS)

    def test_journal_light_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("journal-light", CONTENT_ANCHORS)

    def test_journal_loading_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("journal-loading", LOADING_ANCHORS)

    def test_journal_stale_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("journal-stale", STALE_ANCHORS, wait="notice-1")

    def test_journal_offline_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("journal-offline", STALE_ANCHORS, wait="notice-1")


if __name__ == "__main__":
    unittest.main()
