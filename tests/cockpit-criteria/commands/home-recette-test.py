#!/usr/bin/env python3
"""Criterion test 3 of A1 « Vue d’ensemble — résultat réel lu depuis le
flux, sans faux blocage » (af-c662qx; Spec af-fgcw0d, user stories 124, 125
and 175, Testing Decisions 5 and 6): the states home-content, home-stale,
home-narrow and home-light of the Validated Prototype
(prototype/cockpit-b-zones-20261012 at 632deea,
prototypes/c01-complete/frozen-panorama-home), with the recette of the
cockpit in the result they show.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset of its state, and has a headless
Chromium render GET / at 1440 and 390 px, in the dark and the light theme
(home_destination.measure). On each rendering the page is held to what
makes it unreadable or unusable (home_destination.problems: overflow, cut
or overlapping texts, contrast, controls out of reach of the keyboard or
without a visible focus, the theme asked for). Then « Ce qui reste à
vérifier » is opened with the keyboard, and the recette is read there: the
proofs of the recette (a stop and restart verified, an alert of a silent
Factory, the days of real use) are each named, and each one missing is
said missing -- the sources of these datasets hold none of them.

False if a rendering defect of the reference is copied, the focus is
invisible or trapped, or a missing proof of the recette is presented as
acquired.

home-empty and home-error show no result, hence no recette: their
hierarchy, anchors and layout at both widths in both themes are proven by
home-destination-states-test.py and home-destination-layout-test.py
(T02R2), which stay in the regression.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import LaunchTree, measure, measure_until, problems  # noqa: E402

WIDTHS = (1440, 390)
# The panels of the destination with its content: the requests, the result
# with its bar of actions, the projects.
CONTENT_PANELS = ("nav-1", "main-1", "metric-grid-1", "inbox-1", "panel-2", "panel-3", "actions-possibles-1",
                  "panel-4")
# The part of the result that holds the recette.
RECETTE = "Ce qui reste à vérifier"
# The proofs of the recette (Testing Decisions 6), each by the words that
# name it.
PROOFS = {
    "arrêt et reprise": r"(?i)arrêt|suspension|reprise vérifiée",
    "alerte": r"(?i)alerte|muette",
    "jours d’usage": r"(?i)jours? d[’']usage",
}
MISSING = re.compile(r"(?i)manqu")
ACQUIRED = re.compile(r"(?i)\b(?:vérifiée?s?|prouvée?s?|acquise?s?|obtenue?s?)\b")


class HomeRecette(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_state(self, dataset: str, stale: bool = False) -> None:
        address = self.tree.launch(dataset)
        found = {}
        for theme in ("dark", "light"):
            if stale:
                frames = measure_until(address, lambda frames: all("notice-1" in f["texts"] for f in frames),
                                       seconds=15, theme=theme, widths=WIDTHS)
            else:
                frames = measure(address, theme=theme, widths=WIDTHS)
            self.assertEqual(list(WIDTHS), [frame["width"] for frame in frames])
            found.update(problems(frames, theme, CONTENT_PANELS))
        self.assertEqual({}, found, f"{dataset} is not readable and usable at both widths in both themes")
        self.assert_recette(address)

    def assert_recette(self, address: str) -> None:
        """« Ce qui reste à vérifier », opened with the keyboard, names each
        proof of the recette, and says each one missing; none is said
        acquired."""
        for frame in measure(address, widths=WIDTHS, click=RECETTE, keys=True):
            opened = frame["after"]
            self.assertTrue(opened["found"], f"no « {RECETTE} » in the result at {frame['width']} px")
            self.assertEqual("/", opened["path"], "opening the recette left the destination")
            lines = [" ".join(line.split()) for line in opened["texts"].get("panel-3", "").split("\n") if line.strip()]
            said = {}
            for proof, words in PROOFS.items():
                said[proof] = [line for line in lines if re.search(words, line)]
            self.assertEqual([], [proof for proof, named in said.items() if not named],
                             f"the recette does not name every proof; the result says {lines}")
            self.assertEqual(
                [], [proof for proof, named in said.items() if not any(MISSING.search(line) for line in named)],
                f"a proof of the recette that the sources do not hold is not said missing: {said}",
            )
            self.assertEqual(
                [], [line for named in said.values() for line in named
                     if ACQUIRED.search(line) and not MISSING.search(line) and not re.search(r"(?i)\bnon\b", line)],
                "a missing proof of the recette is presented as acquired",
            )
            self.assertEqual({}, problems([opened], "dark", CONTENT_PANELS),
                             "the recette opened is not readable and usable")

    # Criterion 3 ---------------------------------------------------------

    def test_home_content_shows_the_recette_with_its_missing_proofs_at_both_widths_in_both_themes(self):
        self.assert_state("home-content")

    def test_home_stale_shows_the_recette_with_its_missing_proofs_at_both_widths_in_both_themes(self):
        self.assert_state("home-stale", stale=True)

    def test_home_narrow_shows_the_recette_with_its_missing_proofs_at_both_widths_in_both_themes(self):
        self.assert_state("home-narrow")

    def test_home_light_shows_the_recette_with_its_missing_proofs_at_both_widths_in_both_themes(self):
        self.assert_state("home-light")


if __name__ == "__main__":
    unittest.main()
