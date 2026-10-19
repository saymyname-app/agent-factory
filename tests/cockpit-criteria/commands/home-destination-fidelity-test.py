#!/usr/bin/env python3
"""Criterion test 1 of the Prototype Fold « Vue d’ensemble, décisions et
résultat » (T02R2, af-r2c0tx, replacing T02R af-vbb4ol; Spec af-2zseit,
Testing Decisions 5): the anchors and the tokens the reference approves, in
each of the ten states home-*.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page it serves at GET / -- as a headless Chromium renders it, at
1440 and 390 px, in the dark and the light theme, and from its style
sources. It holds the page to the Validated Prototype
(prototype/cockpit-b-zones-20261012 at 632deea,
prototypes/c01-complete/frozen-panorama-home, read into
home_reference.json):

- every anchor of the state, numbered ones (`div-3`, `strong-1`, `circle-7`)
  as much as named ones, once, drawn by the same element inside the same
  anchor, in the type of the reference (its computed font-family and
  line-height);
- the tokens of the reference under their names (`--bg`, `--surface`,
  `--line`, `--ink`, `--muted`, `--accent`, `--ok`, `--warn`), with its
  values, in the dark and the light theme.

False if an anchor of the reference is missing, doubled, drawn otherwise or
elsewhere, or set in another type, or if a token of the reference is absent
or has another value: the hierarchy approved is not the one served.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import (  # noqa: E402
    REFERENCE_STATES, LaunchTree, anchor_deviations, measure, measure_until, token_deviations,
)

WIDTHS = (1440, 390)
THEMES = ("dark", "light")


class HomeDestinationFidelity(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_reference(self, state: str, ready: str | None = None) -> None:
        """The page served at GET / on the dataset `state` carries every
        anchor and every token of `state` in the reference, at both widths
        in both themes; with `ready`, once the page shows that anchor (a
        state the cockpit reaches after a time)."""
        self.assertIn(state, REFERENCE_STATES)
        address = self.tree.launch(state)
        self.assertEqual([], token_deviations(address), f"the tokens of {state} are not the reference's")
        found = {}
        for theme in THEMES:
            options = {"theme": theme, "widths": WIDTHS}
            if ready is None:
                frames = measure(address, **options)
            else:
                frames = measure_until(
                    address, lambda frames: all(ready in frame["texts"] for frame in frames), seconds=15, **options)
            for frame in frames:
                self.assertEqual("/", frame["path"], "the state is not served at GET /")
                deviations = anchor_deviations(frame, state)
                if deviations:
                    found[f"{frame['width']} px, {theme}"] = deviations
        self.assertEqual({}, found, f"the anchors of {state} are not the reference's")

    # Criterion 1 ---------------------------------------------------------

    def test_home_content_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("home-content")

    def test_home_content_full_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("home-content-full")

    def test_home_narrow_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("home-narrow")

    def test_home_light_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("home-light")

    def test_home_long_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("home-long")

    def test_home_empty_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("home-empty")

    def test_home_loading_carries_every_anchor_and_token_of_its_reference(self):
        # Nothing is read yet: the page is measured as soon as it is served.
        self.assert_reference("home-loading")

    def test_home_error_carries_every_anchor_and_token_of_its_reference(self):
        # Once the cockpit has given up reading the sources.
        self.assert_reference("home-error", ready="error-1")

    def test_home_stale_carries_every_anchor_and_token_of_its_reference(self):
        # Once the reading is stale.
        self.assert_reference("home-stale", ready="notice-1")

    def test_home_offline_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("home-offline", ready="notice-1")


if __name__ == "__main__":
    unittest.main()
