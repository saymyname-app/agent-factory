#!/usr/bin/env python3
"""Criterion test 3 of the Prototype Fold « Analyses » (D, af-ten1sp; Spec
af-fgcw0d, user stories 124 and 175, Testing Decisions 5): the four states
analysis-* of its reference, as a headless Chromium renders them, the page
walked with the keyboard, and long contents.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page the cockpit serves at GET /analyses -- on the view of its
state: « Délais » for analysis-time -- in frames of 1440 and 390 pixels. It
holds the page to the Validated Prototype (prototype/cockpit-b-zones-20261012
at 632deea, prototypes/c01-complete/frozen-panorama-analysis): the named
parts of the state, each its element inside the same named part, written
in the case, and the navigation B with this destination open; and to what
makes a page readable and usable, in the theme of its state: nothing wider
than the frame, no text cut or drawn on another, contrast, every control
named, reached and activated by the keyboard with a focus one sees.

False if a defect of rendering of the prototype is copied, or if the focus
is trapped or lost: the page is walked with Tab, key by key, as a person
walks it, and a tab of the views is opened with Enter.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyses_destination import Keyboard  # noqa: E402
from home_destination import NAVIGATION, LaunchTree, hierarchy, measure, problems  # noqa: E402

# The chart of the daily volumes, by the start of the anchor its label names.
CHART = "volumes-quotidiens-compar-s-sur-sept-jours"


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
        """The page at 1440 and 390 px in `theme`, each frame checked to be
        the destination « Analyses » open in the navigation B."""
        frames = measure(address, path, theme=theme, widths=(1440, 390))
        # No subTest: the harness of the profile records none of them.
        for frame in frames:
            width = frame["width"]
            self.assertEqual("/analyses", frame["path"],
                             f"{width} px: the state is not served at the address of the destination")
            labels = [entry["label"].rstrip("0123456789 ") for entry in frame["nav"]]
            self.assertEqual(NAVIGATION, labels, f"{width} px: the navigation B is not the reference's")
            self.assertEqual(["Analyses"], [label for label, entry in zip(labels, frame["nav"]) if entry["current"]],
                             f"{width} px: the navigation does not say « Analyses » is open")
        return frames

    def test_analysis_content_carries_its_reference_and_is_readable_at_both_widths(self):
        """The view « Résultats »: its chart of daily volumes in the panel
        of the view, the merged results under it."""
        frames = self.frames(self.tree.launch("analysis-content"), "/analyses", "dark")
        for frame in frames:
            expected = {
                "shell-nav-1": ("aside", None), "brand-1": ("header", "shell-nav-1"), "live-1": ("span", "brand-1"),
                "nav-1": ("nav", "shell-nav-1"), "badge-count-1": ("span", "nav-1"),
                "selected-1": ("button", "nav-1"), "main-1": ("main", None), "page-lead-1": ("p", "main-1"),
                "metric-tabs-1": ("div", "main-1"), "primary-1": ("a", "metric-tabs-1"),
                "panel-1": ("section", "main-1"), "chart-key-1": ("div", "panel-1"),
                "metrics-history-1": ("div", "panel-1"),
            }
            self.assertEqual(expected, {name: value for name, value in hierarchy(frame).items() if name in expected},
                             f"{frame['width']} px: the named parts of the page are not the reference's")
            self.assertEqual([("svg", "panel-1")], [value for name, value in hierarchy(frame).items()
                                                    if name.startswith(CHART)],
                             f"{frame['width']} px: the chart of the daily volumes is not drawn in the panel of the view")
        self.assertEqual({}, problems(frames, "dark", ("panel-1",)), "analysis-content is not readable and usable")

    def test_analysis_narrow_carries_its_reference_and_is_readable_at_390_px(self):
        frames = self.frames(self.tree.launch("analysis-narrow"), "/analyses", "dark")
        for frame in frames:
            expected = {
                "shell-nav-1": ("aside", None), "brand-1": ("header", "shell-nav-1"), "live-1": ("span", "brand-1"),
                "nav-1": ("nav", "shell-nav-1"), "badge-count-1": ("span", "nav-1"),
                "selected-1": ("button", "nav-1"), "main-1": ("main", None), "page-lead-1": ("p", "main-1"),
                "metric-tabs-1": ("div", "main-1"), "primary-1": ("a", "metric-tabs-1"),
                "panel-1": ("section", "main-1"), "chart-key-1": ("div", "panel-1"),
                "metrics-history-1": ("div", "panel-1"),
            }
            self.assertEqual(expected, {name: value for name, value in hierarchy(frame).items() if name in expected},
                             f"{frame['width']} px: the named parts of the page are not the reference's")
            self.assertEqual([("svg", "panel-1")], [value for name, value in hierarchy(frame).items()
                                                    if name.startswith(CHART)],
                             f"{frame['width']} px: the chart of the daily volumes is not drawn in the panel of the view")
        self.assertEqual({}, problems(frames, "dark", ("panel-1",)), "analysis-narrow is not readable and usable")

    def test_analysis_light_carries_its_reference_and_is_readable_in_the_light_theme(self):
        frames = self.frames(self.tree.launch("analysis-light"), "/analyses", "light")
        for frame in frames:
            expected = {
                "shell-nav-1": ("aside", None), "brand-1": ("header", "shell-nav-1"), "live-1": ("span", "brand-1"),
                "nav-1": ("nav", "shell-nav-1"), "badge-count-1": ("span", "nav-1"),
                "selected-1": ("button", "nav-1"), "main-1": ("main", None), "page-lead-1": ("p", "main-1"),
                "metric-tabs-1": ("div", "main-1"), "primary-1": ("a", "metric-tabs-1"),
                "panel-1": ("section", "main-1"), "chart-key-1": ("div", "panel-1"),
                "metrics-history-1": ("div", "panel-1"),
            }
            self.assertEqual(expected, {name: value for name, value in hierarchy(frame).items() if name in expected},
                             f"{frame['width']} px: the named parts of the page are not the reference's")
            self.assertEqual([("svg", "panel-1")], [value for name, value in hierarchy(frame).items()
                                                    if name.startswith(CHART)],
                             f"{frame['width']} px: the chart of the daily volumes is not drawn in the panel of the view")
        self.assertEqual({}, problems(frames, "light", ("panel-1",)), "analysis-light is not readable and usable")

    def test_analysis_time_carries_its_reference_and_is_readable_at_both_widths(self):
        """The view « Délais »: a row per portion of the delay, and the
        notice of what the records do not time."""
        frames = self.frames(self.tree.launch("analysis-time"), "/analyses?vue=delais", "dark")
        for frame in frames:
            expected = {
                "shell-nav-1": ("aside", None), "brand-1": ("header", "shell-nav-1"), "live-1": ("span", "brand-1"),
                "nav-1": ("nav", "shell-nav-1"), "badge-count-1": ("span", "nav-1"),
                "selected-1": ("button", "nav-1"), "main-1": ("main", None), "page-lead-1": ("p", "main-1"),
                "metric-tabs-1": ("div", "main-1"), "primary-1": ("a", "metric-tabs-1"),
                "panel-1": ("section", "main-1"), "chart-key-1": ("div", "panel-1"),
                "duration-row-1": ("div", "panel-1"), "duration-row-2": ("div", "panel-1"),
                "duration-row-3": ("div", "panel-1"), "notice-1": ("div", "panel-1"),
            }
            self.assertEqual(expected, {name: value for name, value in hierarchy(frame).items() if name in expected},
                             f"{frame['width']} px: the named parts of the page are not the reference's")
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
