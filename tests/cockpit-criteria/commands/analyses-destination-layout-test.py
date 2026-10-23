#!/usr/bin/env python3
"""Criterion test 3 of the Prototype Fold « Analyses » (D, af-ten1sp; Spec
af-fgcw0d, user stories 124 and 175, Testing Decisions 5): the four states
analysis-* of its reference, as a headless Chromium renders them, the page
walked with the keyboard, and long contents.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page the cockpit serves at GET /analyses -- on the view of its
state: « Délais » for analysis-time -- in frames of 1440 and 390 pixels, and
from its style sources. It holds the page to the Validated Prototype
(prototype/cockpit-b-zones-20261012 at 632deea,
prototypes/c01-complete/frozen-panorama-analysis/states/<state>.html),
whose values are written below, each case naming those of its state:

- every anchor of the state, numbered ones (`div-3`, `text-5`, `circle-7`)
  as much as named ones, once, drawn by the same element inside the same
  anchor, in the type of the reference (its computed font-family and
  line-height), the corrective deviations written with their cause;
- the tokens of the reference under their names, with its values, in the
  dark and the light theme;
- the navigation B with this destination open, the title, the lead and the
  label of the method the reference writes;

and to what makes a page readable and usable, in the theme of its state:
nothing wider than the frame, no text cut or drawn on another, contrast,
every control named, reached and activated by the keyboard with a focus
one sees.

False if an anchor of the reference is missing, doubled, drawn otherwise or
elsewhere, or set in another type, if a token of the reference is absent or
has another value, if a defect of rendering of the prototype is copied, or
if the focus is trapped or lost: the page is walked with Tab, key by key,
as a person walks it, and a tab of the views is opened with Enter.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyses_destination import Keyboard  # noqa: E402
from home_destination import (  # noqa: E402
    LaunchTree, anchor_deviations, measure, outline, problems, token_deviations,
)

# The tokens of the reference, the same in its four analysis states: their
# names and their values, in the dark and the light theme.
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
# drawn the same share one outline. Where the served page corrects a defect
# of the reference, the line is the corrected one, and says so:
#
# (a) the tabs of the views are links to their view (`primary-1`, `a-1` to
#     `a-3`), where the reference draws buttons (`button-7` to `button-9`)
#     that open nothing: each view has its address, opened with the keyboard
#     as with a click;
# (b) the chart draws the volumes its label names, one line and seven
#     points a series (`polyline-1` to `-4`, `circle-1` to `-28`, each its
#     key `span-1` to `-4`), and says its unit (`text-12`, « nombre par
#     jour »): the reference names three series it does not draw and draws
#     a fourth it does not name -- its anchor is named after the label it
#     carries;
# (c) every result merged over the period is listed (`div-2` to `div-7`),
#     where the reference lists three of the six it counts;
# (d) the method says each part on its line (`p-2` to `p-6`: population,
#     period, sources, timestamp, calculation), where the reference writes
#     one paragraph of example;
# (e) the view « Délais » shows the three portions the records of the flow
#     date (`duration-row-1` to `-3`), where the reference draws seven, four
#     of which no record dates: the notice says what is not timed.

# analysis-content, analysis-narrow, analysis-light: the view « Résultats ».
CONTENT_ANCHORS = outline("""
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
    primary-1 a normal
    a-1 a normal
    a-2 a normal
    a-3 a normal
  panel-1 section normal
    h2-1 h2 normal
    p-1 p 22.5px
      strong-2 strong 22.5px
    chart-key-1 div normal
      span-1 span normal
      span-2 span normal
      span-3 span normal
      span-4 span normal
    volumes-quotidiens-compar-s-sur-sept-jours-r-sultats-fusionn-s-pr-fusionn-es-tickets-livr-s-ex-cutions-ci-r-ussies-1 svg normal
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
        text-12 text normal
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
      polyline-2 polyline normal
      circle-8 circle normal
        title-8 title normal
      circle-9 circle normal
        title-9 title normal
      circle-10 circle normal
        title-10 title normal
      circle-11 circle normal
        title-11 title normal
      circle-12 circle normal
        title-12 title normal
      circle-13 circle normal
        title-13 title normal
      circle-14 circle normal
        title-14 title normal
      polyline-3 polyline normal
      circle-15 circle normal
        title-15 title normal
      circle-16 circle normal
        title-16 title normal
      circle-17 circle normal
        title-17 title normal
      circle-18 circle normal
        title-18 title normal
      circle-19 circle normal
        title-19 title normal
      circle-20 circle normal
        title-20 title normal
      circle-21 circle normal
        title-21 title normal
      polyline-4 polyline normal
      circle-22 circle normal
        title-22 title normal
      circle-23 circle normal
        title-23 title normal
      circle-24 circle normal
        title-24 title normal
      circle-25 circle normal
        title-25 title normal
      circle-26 circle normal
        title-26 title normal
      circle-27 circle normal
        title-27 title normal
      circle-28 circle normal
        title-28 title normal
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
      div-5 div normal
        strong-6 strong normal
        small-5 small normal
      div-6 div normal
        strong-7 strong normal
        small-6 small normal
      div-7 div normal
        strong-8 strong normal
        small-7 small normal
    details-1 details normal
      summary-1 summary normal
      p-2 p 21px
      p-3 p 21px
      p-4 p 21px
      p-5 p 21px
      p-6 p 21px
""")

# analysis-time: the view « Délais ».
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
    a-1 a normal
    primary-1 a normal
    a-2 a normal
    a-3 a normal
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
    notice-1 div normal
    details-1 details normal
      summary-1 summary normal
      p-2 p 21px
      p-3 p 21px
      p-4 p 21px
      p-5 p 21px
      p-6 p 21px
""")

NAVIGATION = ["Vue d’ensemble", "Projets", "Runs", "Journal", "Usine", "Rituels", "Analyses"]


class AnalysesDestinationLayout(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def frames(self, address: str, path: str, theme: str) -> list[dict]:
        """The page at 1440 and 390 px in `theme`."""
        return measure(address, path, theme=theme, widths=(1440, 390))

    def assert_reference(self, frames: list[dict], anchors: list[tuple], method: str) -> None:
        """Each frame is the destination « Analyses » at its own address,
        open in the navigation B, with the title, the lead and the label of
        its method the reference writes, and every anchor of `anchors`."""
        for frame in frames:
            labels = [entry["label"].rstrip("0123456789 ") for entry in frame["nav"]]
            self.assertEqual(("/analyses", NAVIGATION, ["Analyses"]),
                             (frame["path"], labels, [label for label, entry in zip(labels, frame["nav"])
                                                      if entry["current"]]),
                             f"{frame['width']} px: not the destination « Analyses » open in the navigation B")
            self.assertEqual(("Analyses", "Toute l’usine · 7 derniers jours", method),
                             tuple(frame["texts"].get(name, "").strip() for name in ("h1-1", "page-lead-1",
                                                                                      "summary-1")),
                             f"{frame['width']} px: the title, the lead or the method are not the reference's")
            self.assertEqual([], anchor_deviations(frame, anchors),
                             f"{frame['width']} px: the anchors of the page are not the reference's")

    def test_analysis_content_carries_its_reference_and_is_readable_at_both_widths(self):
        """The view « Résultats »: its chart of daily volumes in the panel
        of the view, the merged results under it."""
        address = self.tree.launch("analysis-content")
        frames = self.frames(address, "/analyses", "dark")
        self.assert_reference(frames, CONTENT_ANCHORS, "Définition et sources")
        self.assertEqual([], token_deviations(address, TOKENS), "the tokens are not the reference's")
        self.assertEqual({}, problems(frames, "dark", ("panel-1",)), "analysis-content is not readable and usable")

    def test_analysis_narrow_carries_its_reference_and_is_readable_at_390_px(self):
        address = self.tree.launch("analysis-narrow")
        frames = self.frames(address, "/analyses", "dark")
        self.assert_reference(frames, CONTENT_ANCHORS, "Définition et sources")
        self.assertEqual([], token_deviations(address, TOKENS), "the tokens are not the reference's")
        self.assertEqual({}, problems(frames, "dark", ("panel-1",)), "analysis-narrow is not readable and usable")

    def test_analysis_light_carries_its_reference_and_is_readable_in_the_light_theme(self):
        address = self.tree.launch("analysis-light")
        frames = self.frames(address, "/analyses", "light")
        self.assert_reference(frames, CONTENT_ANCHORS, "Définition et sources")
        self.assertEqual([], token_deviations(address, TOKENS), "the tokens are not the reference's")
        self.assertEqual({}, problems(frames, "light", ("panel-1",)), "analysis-light is not readable and usable")

    def test_analysis_time_carries_its_reference_and_is_readable_at_both_widths(self):
        """The view « Délais »: a row per portion of the delay, and the
        notice of what the records do not time."""
        address = self.tree.launch("analysis-time")
        frames = self.frames(address, "/analyses?vue=delais", "dark")
        self.assert_reference(frames, TIME_ANCHORS, "Méthode et couverture")
        self.assertEqual([], token_deviations(address, TOKENS), "the tokens are not the reference's")
        self.assertEqual({}, problems(frames, "dark", ("panel-1",)), "analysis-time is not readable and usable")

    def test_long_titles_projects_and_words_stay_readable_at_both_widths(self):
        """analysis-content with a long result title, a long project name and
        a word without a break: nothing wider than the frame, nothing cut
        or drawn on another, at 1440 and 390 px."""
        long_title = ("Présentation complète du projet avec ses galeries, ses textes traduits en quatre langues et la "
                      "recherche plein texte sur toutes les pages publiées "
                      "docs/projets/portfolio/presentation-complete-des-galeries-et-des-textes-traduits.md")
        long_project = "Portfolio de Benjamin, galeries photographiques et textes publiés"
        commit = self.tree.reword("analysis-content", {"Présentation du projet": long_title,
                                                       "\"Portfolio\"": f"\"{long_project}\""})
        frames = self.frames(self.tree.launch("analysis-content", commit), "/analyses", "dark")
        for frame in frames:
            self.assertEqual("/analyses", frame["path"], f"{frame['width']} px: not the destination « Analyses »")
            history = frame["texts"].get("metrics-history-1", "")
            self.assertIn("recherche plein texte sur toutes les pages publiées", history,
                          f"{frame['width']} px: the long title is not shown whole")
            self.assertIn("galeries photographiques et textes publiés", history,
                          f"{frame['width']} px: the long project name is not shown whole")
        self.assertEqual({}, problems(frames, "dark", ("panel-1",)), "long contents are not readable and usable")

    def test_the_page_is_walked_with_tab_and_a_view_opened_with_enter(self):
        """Tab pressed from the top of the page reaches every control once,
        in the order of the page -- the navigation, the tabs of the views,
        the method -- then leaves the page: the focus is not trapped. Tab up
        to « Délais », then Enter, opens the view of the delay. At both
        widths."""
        address = self.tree.launch("analysis-content")
        for width in (1440, 390):
            keyboard = Keyboard(address + "/analyses", width)
            try:
                walked = []
                for _ in range(30):
                    focused = keyboard.tab()
                    walked.append(focused["name"] if focused else None)
                    if focused is None:
                        break
                self.assertEqual(["Vue d’ensemble 2", "Projets", "Runs", "Journal", "Usine", "Rituels", "Analyses",
                                  "Résultats", "Délais", "Vérifications", "Activité", "Définition et sources", None],
                                 walked, f"{width} px: Tab does not walk the page, then leave it")
                keyboard.open(address + "/analyses")
                focused = None
                for _ in range(30):
                    focused = keyboard.tab()
                    if focused is None or focused["name"] == "Délais":
                        break
                self.assertEqual("Délais", (focused or {}).get("name"), f"{width} px: Tab never reaches « Délais »")
                keyboard.enter()
                self.assertEqual("Où passe le temps ?", keyboard.text("h2-1"),
                                 f"{width} px: Enter on the tab « Délais » did not open the view of the delay")
            finally:
                keyboard.close()


if __name__ == "__main__":
    unittest.main()
