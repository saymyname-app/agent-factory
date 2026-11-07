#!/usr/bin/env python3
"""Criterion test 1 of C2b « Runs — événements, contrôles, sorties, usage et
historique durable » (af-ofz29f; Spec af-fgcw0d, user stories 140, 141,
142 and 175, Testing Decisions 1, 5 and 7): the controls, the usage and the
outputs of a job, opened from the keyboard and read on a desktop and on a
phone, in the dark theme and in the light one.

The case launches the real cockpit with the launcher of the profile,
bin/project-launch, on a dataset it declares from job-configuration --
which opens none of these sections at first -- the job
« Réaliser » with two attempts, the first refused by a check that printed a
long line, the second passed with a structured output naming long
artifacts, and a session whose usage Codex recorded -- and reads GET
/runs/job as a headless Chromium renders it at 1440 and 390 pixels, then
after each of the sections « Contrôles », « Tokens et coût » and
« Sorties » is opened from the keyboard.

False if a section cannot be opened from the keyboard, if what it opens is
not drawn, or if a reading is unreadable or unusable: the document wider
than the screen, a text cut or drawn on another, a contrast too low, a
control out of reach of the keyboard or without a visible focus.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_destination import dataset_of, launch_declared  # noqa: E402
from runs_destination import LaunchTree, anchor, observe_themes, section, unreadable  # noqa: E402
from runs_job_trace import codex_start, codex_usage, gates, job_of, outputs, tokens  # noqa: E402

LOG = ("refus : test en échec : tests/cockpit-criteria/commands/"
       "runs-trace-usage-test.py::RunsTraceUsage.test_job_usage_gives_each_codex_category_and_the_total")
OUTPUT = {"status": "success", "summary": "Changement et démonstration enregistrés.",
          "artifacts": ["demo/search/build/une-piece-de-resultat-au-nom-tres-long-pour-un-ecran-etroit.json"]}


class RunsTraceLayout(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def test_the_controls_the_usage_and_the_outputs_open_from_the_keyboard_readable_on_a_desktop_and_a_phone(self):
        dataset = dataset_of(self.tree, "job-configuration")
        job = job_of(dataset, "search", "build")
        job["attempts"] = [
            {"end": 290, "outcome": "fail", "log": LOG},
            {"end": 365, "outcome": "pass", "pieces": ["tdd_green"], "output": json.dumps(OUTPUT, ensure_ascii=False),
             "output_valid": True},
        ]
        job["sessions"] = [{
            "name": "demo-search-alex-1", "provider": "codex", "start": 190, "end": 365,
            "transcript": codex_start("demo-search-alex-1", "12:13:10.000", "# Auteur", "# Tâche\nRéaliser.")
            + codex_usage([("12:15:50.000", tokens(31554, 24000, 2537, 673))]),
        }]
        by_theme = observe_themes(launch_declared(self.tree, "job-configuration-layout", dataset), "/runs/job", steps=(
            {"click": "Contrôles", "within": "inspector-sections", "keys": True},
            {"click": "Tokens et coût", "within": "inspector-sections", "keys": True},
            {"click": "Sorties", "within": "inspector-sections", "keys": True},
        ))
        for theme, frames in by_theme.items():
            for _, controls, usage, done in frames:
                width = done["width"]
                for title, reading in (("Contrôles", controls), ("Tokens et coût", usage), ("Sorties", done)):
                    self.assertTrue(reading["step"]["found"], f"{theme}, {width} px: no control opens « {title} »")
                    found = section(reading, title)
                    self.assertTrue(found and found["open"], f"{theme}, {width} px: the keyboard does not open « {title} »")
                self.assertEqual(2, len(gates(done)), f"{theme}, {width} px: the attempts of the check are not listed")
                table = anchor(done, "usage")
                self.assertTrue(table and table["drawn"], f"{theme}, {width} px: the table of the usage is not drawn")
                self.assertEqual(1, len(outputs(done)), f"{theme}, {width} px: the output of the job is not listed")
        self.assertEqual({}, unreadable(by_theme, ("chart", "detail")),
                         "the controls, the usage and the outputs of a job are not readable")


if __name__ == "__main__":
    unittest.main()
