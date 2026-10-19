#!/usr/bin/env python3
"""Criterion tests 2 and 3 of the run timeline « frise du run » (T03R,
af-hd8wzb, cut from T03; Spec af-2zseit, user stories 129 and 175, Testing
Decisions 5 and 7): a job selected on the timeline of a phone, in the dark
and the light theme, by a click and by the keyboard.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset run-active, and has a headless
Chromium open GET /runs/run in a frame 390 px wide, in one theme. There it
selects a job of the timeline -- the control whose text says the title of
the job, inside the timeline --, by a click or, focused, by Enter, then
reads the frame two seconds later and, for a refresh, reloads it and reads
it again (run_timeline.select_job). The job is « Revue du code », which
the reference draws at the right end of the timeline, beyond the width of
a phone: in view only once the timeline scrolled to it.

Each reading is held to (run_timeline.selection_problems): the job marked
as the one selected (aria-pressed, aria-selected or aria-current), and no
other job with it; the job in view -- at least its first 44 px across and
20 px down, once cut by the frame and by every box around it that hides
what overflows --; the document no wider than its frame. And the timeline
scrolls across on its own (a box around the job, wider in content than
it, that scrolls).

False if the document overflows, if the timeline cannot be scrolled or
reached, if the job selected is out of view, or if the selection is lost
when the page is refreshed.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_timeline import LaunchTree, select_job, selection_problems  # noqa: E402

PHONE = 390
JOB = "Revue du code"


class RunTimelineSelection(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def assert_selected_after_refresh(self, theme: str) -> None:
        address = self.tree.launch("run-active")
        read = select_job(address, JOB, theme=theme, width=PHONE, reload=True)
        self.assertEqual([], selection_problems(read["selected"], JOB), f"once selected ({theme})")
        self.assertTrue(read["selected"]["local"], f"the timeline does not scroll across on its own ({theme})")
        self.assertIsNotNone(read["reloaded"], f"the page was not reloaded ({theme})")
        self.assertEqual([], selection_problems(read["reloaded"], JOB), f"once the page is refreshed ({theme})")

    # Criterion 2 ---------------------------------------------------------

    def test_a_job_selected_on_a_phone_stays_in_view_and_selected_after_a_refresh_in_the_dark_theme(self):
        self.assert_selected_after_refresh("dark")

    def test_a_job_selected_on_a_phone_stays_in_view_and_selected_after_a_refresh_in_the_light_theme(self):
        self.assert_selected_after_refresh("light")

    # Criterion 3 ---------------------------------------------------------

    def test_a_job_is_selected_from_the_keyboard_on_a_phone_and_brought_into_view(self):
        # Focused, then Enter pressed on it: the same selection as a click.
        address = self.tree.launch("run-active")
        for theme in ("dark", "light"):
            read = select_job(address, JOB, theme=theme, width=PHONE, keys=True)
            self.assertEqual([], selection_problems(read["selected"], JOB), f"by the keyboard ({theme})")


if __name__ == "__main__":
    unittest.main()
