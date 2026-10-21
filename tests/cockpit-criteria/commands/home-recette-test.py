#!/usr/bin/env python3
"""Criterion test 3 of A1 « Vue d’ensemble — résultat réel lu depuis le
flux, sans faux blocage » (af-c662qx; Spec af-fgcw0d, user stories 124, 125
and 175, Testing Decisions 5 and 6): the states home-content, home-empty,
home-error, home-stale, home-narrow and home-light of the Validated
Prototype (prototype/cockpit-b-zones-20261012 at 632deea,
prototypes/c01-complete/frozen-panorama-home), with the recette of the
cockpit in the result they show.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset of its state, and has a headless
Chromium render GET / at 1440 and 390 px, in the dark and the light theme
(home_destination.measure). On each rendering the page is held to the
hierarchy and the anchors of the reference -- the navigation B, and exactly
the named parts the reference draws in that state, each its element, inside
the same named part (home_destination.assert_destination) -- and to what
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

home-empty and home-error show no result, hence no recette: held to their
hierarchy and anchors, readable and usable at both widths in both themes,
they say no proof of the recette at all, acquired or not -- the recette is
said where a result holds it, as home-content, read in the same case, says
it.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import (  # noqa: E402
    CONTENT_PARTS, SHELL_PARTS, LaunchTree, assert_destination, measure, measure_until, problems,
)

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
# The named parts of the reference in each state (home-destination-states-
# test.py writes them the same): the content; the content under a notice;
# the shell and one section that says nothing is to be shown; the shell and
# the section of the error.
STALE_PARTS = {**SHELL_PARTS, "notice-1": ("div", "main-1"),
               **{name: part for name, part in CONTENT_PARTS.items() if name not in SHELL_PARTS}}
EMPTY_PARTS = {**SHELL_PARTS, "panel-1": ("section", "main-1")}
ERROR_PARTS = {**SHELL_PARTS, "error-1": ("section", "main-1")}
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
        address = self.rendered(dataset, STALE_PARTS if stale else CONTENT_PARTS, CONTENT_PANELS,
                                "notice-1" if stale else None)
        self.assert_recette(address)

    def rendered(self, dataset: str, parts: dict, panels: tuple[str, ...], ready: str | None = None) -> str:
        """The address of the cockpit launched on `dataset`, once its page
        at GET / is held, at both widths in both themes, to the named parts
        `parts` of the reference and to readability (`panels` present);
        with `ready`, once every frame shows that part."""
        address = self.tree.launch(dataset)
        found = {}
        for theme in ("dark", "light"):
            if ready:
                frames = measure_until(address, lambda frames: all(ready in f["texts"] for f in frames),
                                       seconds=15, theme=theme, widths=WIDTHS)
            else:
                frames = measure(address, theme=theme, widths=WIDTHS)
            self.assertEqual(list(WIDTHS), [frame["width"] for frame in frames])
            for frame in frames:
                with self.subTest(dataset=dataset, theme=theme, width=frame["width"]):
                    assert_destination(self, frame, parts)
            found.update(problems(frames, theme, panels))
            self.frames = frames
        self.assertEqual({}, found, f"{dataset} is not readable and usable at both widths in both themes")
        return address

    def assert_no_recette(self) -> None:
        """The page last rendered says no proof of the recette, neither
        missing nor acquired: it shows no result."""
        for frame in self.frames:
            self.assertEqual([], [proof for proof, words in PROOFS.items() if re.search(words, frame["text"])],
                             f"a page without a result says a proof of the recette at {frame['width']} px")

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

    def test_home_empty_and_home_error_say_no_proof_of_the_recette_which_home_content_says_missing(self):
        self.rendered("home-empty", EMPTY_PARTS, ("nav-1", "main-1", "panel-1"))
        self.assert_no_recette()
        self.rendered("home-error", ERROR_PARTS, ("nav-1", "main-1", "error-1"), ready="error-1")
        self.assert_no_recette()
        # Where a result is shown, the recette is: each proof said missing.
        self.assert_recette(self.tree.launch("home-content"))

    def test_home_stale_shows_the_recette_with_its_missing_proofs_at_both_widths_in_both_themes(self):
        self.assert_state("home-stale", stale=True)

    def test_home_narrow_shows_the_recette_with_its_missing_proofs_at_both_widths_in_both_themes(self):
        self.assert_state("home-narrow")

    def test_home_light_shows_the_recette_with_its_missing_proofs_at_both_widths_in_both_themes(self):
        self.assert_state("home-light")


if __name__ == "__main__":
    unittest.main()
