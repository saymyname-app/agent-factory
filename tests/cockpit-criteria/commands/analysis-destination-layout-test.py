#!/usr/bin/env python3
"""Criterion test 2 of the Prototype Fold « Analyses » (T42, af-muqyxm;
Spec af-2zseit, user stories 124 and 175, Testing Decisions 5): the
destination and its panels, on the four states analysis-* of its
reference and on long content, at 1440 and 390 px, in the light and the
dark theme, with the keyboard.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset of its state, and has a headless
Chromium render GET /analyses -- open on « Délais » for analysis-time, the
tab activated on the page -- in two frames, 1440 and 390 px wide, once
with the dark and once with the light colour scheme preferred. On each
rendering it requires the panels of the state, then reads what makes the
page unreadable or unusable (home_destination.problems): the document
wider than the frame, a text cut or drawn on another, a contrast under
4.5:1, a useful local scroll lost or out of reach of the keyboard, a
control without a name, out of reach of the keyboard, that the keyboard
cannot activate, without a focus a person sees, or whose box stands out
under 3:1, a page that is not in the theme the browser asked for. It also
requires each mark of the chart -- its line and its points -- to stand out
at 3:1 at least from what is behind the chart.

The reference draws some of these defects itself (the boxes of its tabs
under 3:1, a line of its chart under 3:1 on the light theme): they are
measured on the product, not copied from the frozen page.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analysis_destination import CHART, PATH  # noqa: E402
from home_destination import LaunchTree, measure, problems, says  # noqa: E402

WIDTHS = (1440, 390)
# The panels of the destination open on « Résultats »: the navigation, the
# tabs, the panel of the merged results with its chart and their list.
RESULTS_PANELS = ("nav-1", "main-1", "metric-tabs-1", "panel-1", CHART, "metrics-history-1")
# Open on « Délais »: the panel of the lead time, its rows and its notice.
TIME_PANELS = ("nav-1", "main-1", "metric-tabs-1", "panel-1", "duration-row-1", "duration-row-7", "notice-1")
# The marks of the chart of the merged results: its line and its seven
# points.
CHART_MARKS = ("polyline-1",) + tuple(f"circle-{n}" for n in range(1, 8))


class AnalysisDestinationLayout(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def rendered(self, dataset: str, commit: str | None = None, tab: str | None = None) -> dict[str, list[dict]]:
        """GET /analyses of the cockpit launched on `dataset`, rendered dark
        then light at both widths -- with `tab`, once that tab was
        activated on it --: theme -> frames."""
        address = self.tree.launch(dataset, commit)
        renderings = {}
        for theme in ("dark", "light"):
            frames = measure(address, PATH, theme=theme, widths=WIDTHS, click=tab)
            if tab is not None:
                self.assertEqual([True, True], [frame["after"]["found"] for frame in frames],
                                 f"no tab « {tab} » ({theme})")
                frames = [{**frame["after"], "width": frame["width"]} for frame in frames]
            renderings[theme] = frames
        return renderings

    def assert_readable(self, dataset: str, panels: tuple[str, ...], commit: str | None = None,
                        tab: str | None = None) -> dict:
        renderings = self.rendered(dataset, commit, tab)
        found = {}
        for theme, frames in renderings.items():
            found.update(problems(frames, theme, panels))
        self.assertEqual({}, found)
        return renderings

    def assert_marks_stand_out(self, renderings: dict) -> None:
        """Each mark of the chart of the merged results stands out at 3:1
        at least from what is behind the chart, in both themes."""
        found = {}
        for theme, frames in renderings.items():
            for frame in frames:
                marks = {mark["name"]: mark["contrast"] for mark in frame.get("marks", [])}
                faint = [f"{name} : {marks.get(name)}" for name in CHART_MARKS
                         if marks.get(name) is None or marks[name] < 3 - 0.01]
                if faint:
                    found[f"{frame['width']} px, {theme}"] = faint
        self.assertEqual({}, found, "marks of the chart under 3:1 against the chart's background")

    # Criterion 2 ---------------------------------------------------------

    def test_analysis_content_is_readable_and_usable_at_both_widths_in_both_themes(self):
        renderings = self.assert_readable("analysis-content", RESULTS_PANELS)
        self.assert_marks_stand_out(renderings)
        # Activated by the keyboard -- focused, then Enter --, the tab
        # « Délais » opens the lead times, at both widths.
        address = self.tree.launch("analysis-content")
        for frame in measure(address, PATH, theme="dark", widths=WIDTHS, click="Délais", keys=True):
            after = frame["after"]
            self.assertTrue(after["found"], f"no tab « Délais » at {frame['width']} px")
            self.assertEqual(PATH, after["path"], f"Enter on « Délais » left the destination at {frame['width']} px")
            self.assertIn("Où passe le temps ?", says(after, "panel-1"),
                          f"Enter on « Délais » did not open the lead times at {frame['width']} px")

    def test_analysis_narrow_is_readable_and_usable_at_both_widths_in_both_themes(self):
        renderings = self.assert_readable("analysis-narrow", RESULTS_PANELS)
        self.assert_marks_stand_out(renderings)

    def test_analysis_light_is_readable_and_usable_at_both_widths_in_both_themes(self):
        renderings = self.assert_readable("analysis-light", RESULTS_PANELS)
        self.assert_marks_stand_out(renderings)

    def test_analysis_time_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("analysis-time", TIME_PANELS, tab="Délais")

    def test_long_titles_and_words_stay_whole_and_inside_the_page_at_both_widths_in_both_themes(self):
        # The same dataset, at another commit, where two merged results
        # have long titles, one of them a word longer than a phone is wide:
        # every rendering stays readable, and each title is said whole
        # where the reference says the short one.
        long_title = ("Fiabilisation des reprises après un arrêt propre de la cité, avec la comparaison du "
                      "travail conservé et des écarts relevés pour chaque session")
        long_word = "Import_des_documents_archivés_depuis_le_premier_trimestre_sans_espace_ni_tiret"
        reworded = self.tree.reword("analysis-content", {"Fiabilisation des reprises": long_title,
                                                         "Import des documents": long_word})
        renderings = self.assert_readable("analysis-content", RESULTS_PANELS, commit=reworded)
        for theme, frames in renderings.items():
            for frame in frames:
                listed = says(frame, "metrics-history-1")
                self.assertEqual((True, True), (long_title in listed, long_word in listed),
                                 f"a long title is not said whole at {frame['width']} px, {theme}")


if __name__ == "__main__":
    unittest.main()
