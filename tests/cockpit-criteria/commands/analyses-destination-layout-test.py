#!/usr/bin/env python3
"""Criterion test 3 of the Prototype Fold « Analyses » (D, af-ten1sp; Spec
af-fgcw0d, user stories 124 and 175, Testing Decisions 5): the four states
analysis-* of its reference, as a headless Chromium renders them.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset that carries the name of its state, and
reads the page the cockpit serves at GET /analyses -- on the view of its
state: « Délais » for analysis-time -- in frames of 1440 and 390 pixels. It
holds the page to the Validated Prototype (prototype/cockpit-b-zones-20261012
at 632deea, prototypes/c01-complete/frozen-panorama-analysis): the named
parts of the state, each its element inside the same named part, and the
navigation B with this destination open; and to what makes a page readable
and usable, in the theme of its state: nothing wider than the frame, no
text cut or drawn on another, contrast, every control named, reached and
activated by the keyboard with a focus one sees.

False if a defect of rendering of the prototype is copied, or if the focus
is trapped or lost: the tabs of the views are opened with the keyboard.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import NAVIGATION, LaunchTree, hierarchy, measure, problems  # noqa: E402

# The named parts every state shows, as the reference draws them: part ->
# (element, the named part that holds it).
SHELL_PARTS = {
    "shell-nav-1": ("aside", None),
    "brand-1": ("header", "shell-nav-1"),
    "live-1": ("span", "brand-1"),
    "nav-1": ("nav", "shell-nav-1"),
    "badge-count-1": ("span", "nav-1"),
    "selected-1": ("button", "nav-1"),
    "main-1": ("main", None),
    "page-lead-1": ("p", "main-1"),
    "metric-tabs-1": ("div", "main-1"),
    # The tab of the view open: a link to its view, as the other tabs.
    "primary-1": ("a", "metric-tabs-1"),
    "panel-1": ("section", "main-1"),
    "chart-key-1": ("div", "panel-1"),
}
# analysis-content, analysis-narrow and analysis-light: the view « Résultats »,
# its chart of daily volumes and the merged results under it.
CONTENT_PARTS = {**SHELL_PARTS, "metrics-history-1": ("div", "panel-1")}
CHART = "volumes-quotidiens-compar-s-sur-sept-jours"
# analysis-time: the view « Délais », a row per portion of the delay, and the
# notice of what the records do not time.
TIME_PARTS = {
    **SHELL_PARTS,
    "duration-row-1": ("div", "panel-1"),
    "duration-row-2": ("div", "panel-1"),
    "duration-row-3": ("div", "panel-1"),
    "notice-1": ("div", "panel-1"),
}


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

    def assert_state(self, dataset: str, path: str, parts: dict, theme: str, chart: bool) -> None:
        """The state `dataset`, at `path`, in `theme`: at 1440 and 390 px,
        the named parts of its reference and the navigation B with
        « Analyses » open, then nothing that makes it unreadable or
        unusable."""
        address = self.tree.launch(dataset)
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
            served = hierarchy(frame)
            self.assertEqual(parts, {name: value for name, value in served.items() if name in parts},
                             f"{width} px: the named parts of the page are not the reference's")
            if chart:
                charts = [value for name, value in served.items() if name.startswith(CHART)]
                self.assertEqual([("svg", "panel-1")], charts,
                                 f"{width} px: the chart of the daily volumes is not drawn in the panel of the view")
        self.assertEqual({}, problems(frames, theme, ("panel-1",)), f"{dataset} is not readable and usable")

    def test_analysis_content_carries_its_reference_and_is_readable_at_both_widths(self):
        self.assert_state("analysis-content", "/analyses", CONTENT_PARTS, "dark", chart=True)

    def test_analysis_narrow_carries_its_reference_and_is_readable_at_390_px(self):
        self.assert_state("analysis-narrow", "/analyses", CONTENT_PARTS, "dark", chart=True)

    def test_analysis_light_carries_its_reference_and_is_readable_in_the_light_theme(self):
        self.assert_state("analysis-light", "/analyses", CONTENT_PARTS, "light", chart=True)

    def test_analysis_time_carries_its_reference_and_is_readable_at_both_widths(self):
        self.assert_state("analysis-time", "/analyses?vue=delais", TIME_PARTS, "dark", chart=False)

    def test_the_view_of_an_indicator_is_opened_with_the_keyboard(self):
        """From « Résultats », the tab « Délais » focused and Enter pressed
        opens the view of the delay, at both widths."""
        address = self.tree.launch("analysis-content")
        for frame in measure(address, "/analyses", widths=(1440, 390), click="Délais", keys=True):
            after = frame.get("after") or {}
            self.assertTrue(after.get("found"), f"{frame['width']} px: no tab « Délais » to activate")
            self.assertIn("Où passe le temps ?", after.get("text", ""),
                          f"{frame['width']} px: Enter on the tab « Délais » did not open the view of the delay")


if __name__ == "__main__":
    unittest.main()
