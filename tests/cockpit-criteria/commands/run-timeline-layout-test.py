#!/usr/bin/env python3
"""Criterion test 3 of the run timeline « frise du run » (T03R, af-hd8wzb,
cut from T03; Spec af-2zseit, user story 175, Testing Decisions 5): the
timeline of each of its five frozen states, and of long job titles, at
1280 and 390 px, in the dark and the light theme, with the keyboard.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset of its state, and has a headless
Chromium render GET /runs/run in two frames, 1280 and 390 px wide, once
with the dark and once with the light colour scheme preferred. On each
rendering it requires the parts of the timeline -- the run, its summary,
the timeline itself and its legend --, then reads what makes the page
unreadable or unusable (home_destination.problems, the measure of the
destination « Vue d’ensemble », reused):

- the document wider than the frame (a global overflow), a text cut -- by
  a box that hides what overflows it, by points of suspension, or pushed
  out of the frame; a text inside a box that scrolls is not cut --, two
  texts drawn on each other, a contrast under 4.5:1 (3:1 when large);
- the local scroll of the timeline lost: a box that scrolls on its own
  whose content larger than it is hidden rather than scrolled, or that
  the keyboard cannot reach;
- a control without a name, a control enabled but out of reach of the
  keyboard or that the keyboard cannot activate, a control whose focus a
  person does not see, a button whose box stands out under 3:1;
- a page that is not in the theme the browser asked for.

The reference draws some of these defects itself -- the titles of short
jobs cut by points of suspension, two job titles drawn on each other at
390 px in run-completed, the ticks of the axis cut by the box of the
timeline --: they are measured on the product, not copied from the frozen
pages (Testing Decisions 5: a rendering accident is corrected, not
prescribed).

Selecting a job, by a click or by the keyboard, is in
run-timeline-selection-test.py.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from home_destination import measure_until  # noqa: E402
from run_timeline import THEMES, TIMELINE, WIDTHS, LaunchTree, problems, tracks  # noqa: E402

# The parts of the timeline every state draws: the title of the run, its
# summary, the timeline and its legend.
PARTS = ("h1", "run-summary", "chart-box", "chart", "legend")


class RunTimelineLayout(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_readable(self, dataset: str, parts: tuple[str, ...] = PARTS, commit: str | None = None) -> dict:
        """GET /runs/run of the cockpit launched on `dataset` (at `commit`),
        rendered dark then light at both widths once its parts are drawn
        (or as it stands after 15 s), holds no problem: theme -> frames."""
        address = self.tree.launch(dataset, commit)
        renderings, found = {}, {}
        for theme in THEMES:
            frames = measure_until(address, lambda frames: all(p in frames[0]["texts"] for p in parts), seconds=15,
                                   path=TIMELINE, theme=theme, widths=WIDTHS)
            renderings[theme] = frames
            found.update(problems(frames, theme, parts))
        self.assertEqual({}, found)
        return renderings

    # Criterion 3 ---------------------------------------------------------

    def test_run_active_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("run-active")

    def test_run_completed_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("run-completed")

    def test_run_waiting_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("run-waiting")

    def test_run_abandoned_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("run-abandoned")

    def test_run_stale_is_readable_and_usable_at_both_widths_in_both_themes(self):
        self.assert_readable("run-stale", ("notice",) + PARTS)

    def test_long_job_titles_stay_whole_without_overlap_at_both_widths_in_both_themes(self):
        # The same dataset, at another commit, where a job of a short
        # duration has a long title: every rendering stays readable, and
        # its lane says that title whole.
        long_title = "Relire les tests de la frise, de ses libellés longs et de leurs durées avant la revue"
        reworded = self.tree.reword("run-active", {"Relire les tests": long_title})
        renderings = self.assert_readable("run-active", commit=reworded)
        for theme, frames in renderings.items():
            for frame in frames:
                served = tracks(frame)
                self.assertEqual(5, len(served), f"not the five lanes of the run at {frame['width']} px, {theme}")
                # The fourth lane, Léa's, draws the job.
                self.assertIn(long_title, served[3],
                              f"the long title is not said whole in its lane at {frame['width']} px, {theme}")


if __name__ == "__main__":
    unittest.main()
