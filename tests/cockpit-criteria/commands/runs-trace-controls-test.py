#!/usr/bin/env python3
"""Criterion test 1 of C2b « Runs — événements, contrôles, sorties, usage et
historique durable » (af-ofz29f; Spec af-fgcw0d, user story 140, Testing
Decisions 1, 7 and 8): the controls of a job, states job-gates and
job-usage-unavailable.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on job-usage-unavailable or on a dataset the case
declares from job-gates, and reads GET /runs/job -- the job the state
selects, under the frise of its run -- as a headless Chromium renders it.

The job « Réaliser » of « Recherche dans les notes » (run triggered at
14:10, Paris) is a step whose closing runs a check, as the author's steps
are: the case writes its attempts -- the first refused by its check with
what the check printed, the second passed once the evidence store holds
the pieces its gate reads, captured in that attempt. The section
« Contrôles » lists each attempt with its state, its time and its pieces,
each said present when the evidence store holds it. The job « Essayer la
tâche » of « Reprise du cockpit », in job-usage-unavailable, is still
worked by its session: its check has not run.

False if an attempt is missing, if a refused attempt is said passed or
loses what its check printed, if a piece is listed on an attempt that did
not capture it, or if a check whose session still runs is said passed.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_destination import dataset_of, launch_declared  # noqa: E402
from runs_destination import LaunchTree, observe, section  # noqa: E402
from runs_job_trace import gates, job_of  # noqa: E402

REFUSED = "refus : test en échec : tests/cockpit-criteria/commands/runs-trace-usage-test.py"


class RunsTraceControls(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def test_job_gates_lists_each_attempt_of_the_check_with_its_state_its_time_and_its_pieces(self):
        dataset = dataset_of(self.tree, "job-gates")
        # « Réaliser » runs from +3 min 10 s to +6 min 5 s: its first
        # attempt is closed at +4 min 50 s and refused by its check, the
        # second closed at +6 min 5 s and passed, with the two pieces it
        # captured.
        job_of(dataset, "search", "build")["attempts"] = [
            {"end": 290, "outcome": "fail", "log": REFUSED},
            {"end": 365, "outcome": "pass", "pieces": ["tdd_green", "demonstration"]},
        ]
        reading, = observe(launch_declared(self.tree, "job-gates-attempts", dataset), "/runs/job")[0]
        listed = gates(reading)
        self.assertEqual(2, len(listed), f"the controls listed: {[gate['title'] for gate in listed]}")
        first, second = (next((gate for gate in listed if f"Tentative {number}" in gate["title"]), None)
                         for number in (1, 2))
        self.assertIsNotNone(first, f"no control of the first attempt: {[gate['title'] for gate in listed]}")
        self.assertIsNotNone(second, f"no control of the second attempt: {[gate['title'] for gate in listed]}")
        # 12:14:50 UTC is 14:14:50 in Paris; 12:16:05 UTC, 14:16:05.
        self.assertIn("refusé", first["content"], f"the first attempt is not said refused: « {first['content']} »")
        self.assertNotIn("passé", first["content"], f"the refused attempt is said passed: « {first['content']} »")
        self.assertIn(REFUSED, first["content"], "the first attempt does not say what its check printed")
        self.assertIn("14:14:50", first["content"], "the first attempt does not say when it was closed")
        for piece in ("tdd_green", "demonstration"):
            self.assertNotIn(piece, first["content"], f"the first attempt lists the piece {piece} it did not capture")
        self.assertIn("passé", second["content"], f"the second attempt is not said passed: « {second['content']} »")
        self.assertIn("14:16:05", second["content"], "the second attempt does not say when it was closed")
        for piece in ("tdd_green", "demonstration"):
            self.assertIn(f"{piece} · présente", second["content"],
                          f"the second attempt does not say its piece {piece} present: « {second['content']} »")

    def test_a_check_whose_session_still_runs_is_awaited_and_never_said_passed(self):
        reading, = observe(self.tree.launch("job-usage-unavailable"), "/runs/job")[0]
        found = section(reading, "Contrôles")
        self.assertIsNotNone(found, "the detail has no section « Contrôles »")
        listed = gates(reading)
        self.assertEqual(1, len(listed), f"the controls listed: {[gate['title'] for gate in listed]}")
        awaited, = listed
        self.assertIn("Tentative 1", awaited["title"], f"the control does not name its attempt: « {awaited['title']} »")
        self.assertIn("en attente", awaited["content"],
                      f"the check of a job its session still works is not said awaited: « {awaited['content']} »")
        for said in ("passé", "refusé", "✓"):
            self.assertNotIn(said, found["content"], f"a check that has not run says « {said} »")


if __name__ == "__main__":
    unittest.main()
