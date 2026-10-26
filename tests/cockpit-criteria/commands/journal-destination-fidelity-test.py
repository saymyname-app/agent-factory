#!/usr/bin/env python3
"""Criterion tests 1 and 2 of F, the Prototype Fold of the Journal
reference (af-njwz8v; Spec af-fgcw0d, Testing Decisions 5): the anchors and
the tokens the reference approves, in journal-content, journal-long, journal-empty, journal-error and journal-logs.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page it serves at GET /journal (the logs once their tab is opened) -- as a headless Chromium
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
    CONTENT_ANCHORS, EMPTY_ANCHORS, ERROR_ANCHORS, LOGS_ANCHORS, TOKENS, LaunchTree, anchor_deviations,
    measure, measure_until,
)

WIDTHS = (1440, 390)
THEMES = ("dark", "light")


class JournalDestinationFidelity(unittest.TestCase):
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

    # Criterion 1 ---------------------------------------------------------

    def test_journal_content_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("journal-content", CONTENT_ANCHORS)

    def test_journal_long_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("journal-long", CONTENT_ANCHORS)

    def test_journal_empty_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("journal-empty", EMPTY_ANCHORS)

    def test_journal_error_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("journal-error", ERROR_ANCHORS, wait="error-1")

    # Criterion 2 ---------------------------------------------------------

    def test_journal_logs_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("journal-logs", LOGS_ANCHORS, opened="Logs techniques")


if __name__ == "__main__":
    unittest.main()
