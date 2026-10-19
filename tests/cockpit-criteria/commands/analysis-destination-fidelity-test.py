#!/usr/bin/env python3
"""Criterion test 1 of the Prototype Fold « Analyses » (T42, af-muqyxm;
Spec af-2zseit, Testing Decisions 5): the anchors and the tokens the
reference approves, in each of the four states analysis-*.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page it serves at GET /analyses -- as a headless Chromium renders
it, at 1440 and 390 px, in the dark and the light theme, and from its style
sources. analysis-time is read once the tab « Délais » was activated on the
page served, as the reference opens it. It holds the page to the Validated
Prototype (prototype/cockpit-b-zones-20261012 at 632deea,
prototypes/c01-complete/frozen-panorama-analysis/states/<state>.html), whose
values are written below, each case naming those of its state:

- every anchor of the state, numbered ones (`div-3`, `strong-2`,
  `circle-7`) as much as named ones, once, drawn by the same element inside
  the same anchor, in the type of the reference (its computed font-family
  and line-height);
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

from analysis_destination import PATH, token_deviations  # noqa: E402
from home_destination import LaunchTree, anchor_deviations, measure, outline  # noqa: E402

WIDTHS = (1440, 390)
THEMES = ("dark", "light")

# The tokens of the reference, the same in its four states: their names and
# their values, in the dark and the light theme.
TOKENS = {
    "dark": {"--bg": "#0d1015", "--surface": "#161b23", "--line": "#2a3240", "--ink": "#ecedf3",
             "--muted": "#9aa6b9", "--accent": "#99aaff", "--ok": "#55c89d", "--warn": "#efc778"},
    "light": {"--bg": "#f3f5f9", "--surface": "#fff", "--line": "#dbe0e8", "--ink": "#17202e",
              "--muted": "#657185", "--accent": "#415fce", "--ok": "#1c7954", "--warn": "#97691e"},
}

# Every anchor of the frozen page of a state, in the order of the page: the
# anchor, the element that draws it, its line-height, indented under the
# anchor that holds it -- all in system-ui, the type of the reference. Read
# from the frozen pages as headless Chromium renders them at 1440 and 390 px
# in the dark and the light theme (the four renderings agree); the states
# drawn the same share one outline.

# analysis-content, analysis-narrow, analysis-light: open on « Résultats »
RESULTS_ANCHORS = outline("""
shell-nav-1 aside normal
  brand-1 header normal
    div-1 div normal
      strong-1 strong normal
      small-1 small normal
    live-1 span normal
  nav-1 nav normal
    button-1 button normal
      badge-count-1 span normal
    button-2 button normal
    button-3 button normal
    button-4 button normal
    button-5 button normal
    button-6 button normal
    selected-1 button normal
main-1 main normal
  h1-1 h1 normal
  page-lead-1 p 24px
  metric-tabs-1 div normal
    primary-1 button normal
    button-7 button normal
    button-8 button normal
    button-9 button normal
  panel-1 section normal
    h2-1 h2 normal
    p-1 p 22.5px
      strong-2 strong 22.5px
    chart-key-1 div normal
      span-1 span normal
    volumes-quotidiens-compar-s-sur-sept-jours-pr-fusionn-es-tickets-livr-s-ex-cutions-ci-r-ussies-1 svg normal
      g-1 g normal
        line-1 line normal
        line-2 line normal
        line-3 line normal
        line-4 line normal
      g-2 g normal
        text-1 text normal
        text-2 text normal
        text-3 text normal
        text-4 text normal
        text-5 text normal
        text-6 text normal
        text-7 text normal
        text-8 text normal
        text-9 text normal
        text-10 text normal
        text-11 text normal
      polyline-1 polyline normal
      circle-1 circle normal
        title-1 title normal
      circle-2 circle normal
        title-2 title normal
      circle-3 circle normal
        title-3 title normal
      circle-4 circle normal
        title-4 title normal
      circle-5 circle normal
        title-5 title normal
      circle-6 circle normal
        title-6 title normal
      circle-7 circle normal
        title-7 title normal
    metrics-history-1 div normal
      div-2 div normal
        strong-3 strong normal
        small-2 small normal
      div-3 div normal
        strong-4 strong normal
        small-3 small normal
      div-4 div normal
        strong-5 strong normal
        small-4 small normal
    details-1 details normal
      summary-1 summary normal
      p-2 p 21px
""")

# analysis-time: open on « Délais »
TIME_ANCHORS = outline("""
shell-nav-1 aside normal
  brand-1 header normal
    div-1 div normal
      strong-1 strong normal
      small-1 small normal
    live-1 span normal
  nav-1 nav normal
    button-1 button normal
      badge-count-1 span normal
    button-2 button normal
    button-3 button normal
    button-4 button normal
    button-5 button normal
    button-6 button normal
    selected-1 button normal
main-1 main normal
  h1-1 h1 normal
  page-lead-1 p 24px
  metric-tabs-1 div normal
    button-7 button normal
    primary-1 button normal
    button-8 button normal
    button-9 button normal
  panel-1 section normal
    h2-1 h2 normal
    p-1 p 22.5px
      strong-2 strong 22.5px
    chart-key-1 div normal
      span-1 span normal
      span-2 span normal
    duration-row-1 div normal
      span-3 span normal
      div-2 div normal
        duration-bar-1 div normal
      strong-3 strong normal
    duration-row-2 div normal
      span-4 span normal
      div-3 div normal
        duration-bar-2 div normal
      strong-4 strong normal
    duration-row-3 div normal
      span-5 span normal
      div-4 div normal
        duration-bar-3 div normal
      strong-5 strong normal
    duration-row-4 div normal
      span-6 span normal
      div-5 div normal
        duration-bar-4 div normal
      strong-6 strong normal
    duration-row-5 div normal
      span-7 span normal
      div-6 div normal
        duration-bar-5 div normal
      strong-7 strong normal
    duration-row-6 div normal
      span-8 span normal
      div-7 div normal
        duration-bar-6 div normal
      strong-8 strong normal
    duration-row-7 div normal
      span-9 span normal
      div-8 div normal
        duration-bar-7 div normal
      strong-9 strong normal
    notice-1 div normal
    details-1 details normal
      summary-1 summary normal
      p-2 p 21px
      p-3 p 21px
""")


class AnalysisDestinationFidelity(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_reference(self, state: str, anchors: list[tuple], tab: str | None = None) -> None:
        """The page served at GET /analyses on the dataset `state` carries
        every anchor of `anchors` and every token of TOKENS, at both widths
        in both themes; with `tab`, once that tab was activated on it."""
        address = self.tree.launch(state)
        self.assertEqual([], token_deviations(address, TOKENS), f"the tokens of {state} are not the reference's")
        found = {}
        for theme in THEMES:
            for frame in measure(address, PATH, theme=theme, widths=WIDTHS, click=tab):
                self.assertEqual(PATH, frame["path"], "the state is not served at GET /analyses")
                if tab is not None:
                    self.assertTrue(frame["after"]["found"], f"no tab « {tab} » at {frame['width']} px, {theme}")
                    frame = frame["after"]
                    self.assertEqual(PATH, frame["path"], f"« {tab} » left the destination")
                deviations = anchor_deviations(frame, anchors)
                if deviations:
                    found[f"{frame['width']} px, {theme}"] = deviations
        self.assertEqual({}, found, f"the anchors of {state} are not the reference's")

    # Criterion 1 ---------------------------------------------------------

    def test_analysis_content_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("analysis-content", RESULTS_ANCHORS)

    def test_analysis_narrow_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("analysis-narrow", RESULTS_ANCHORS)

    def test_analysis_light_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("analysis-light", RESULTS_ANCHORS)

    def test_analysis_time_carries_every_anchor_and_token_of_its_reference(self):
        self.assert_reference("analysis-time", TIME_ANCHORS, tab="Délais")


if __name__ == "__main__":
    unittest.main()
