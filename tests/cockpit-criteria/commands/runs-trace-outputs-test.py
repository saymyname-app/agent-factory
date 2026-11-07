#!/usr/bin/env python3
"""Criterion test 1 of C2b « Runs — événements, contrôles, sorties, usage et
historique durable » (af-ofz29f; Spec af-fgcw0d, user story 142, Testing
Decisions 1, 7 and 8): the structured outputs of a job, states job-output
and job-usage-unavailable.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on job-usage-unavailable or on a dataset the case
declares from job-output, and reads GET /runs/job -- the job the state
selects, under the frise of its run -- as a headless Chromium renders it.

The job « Réaliser » of « Recherche dans les notes » is a step that must
record a structured output: the case writes its attempts -- the first
recorded an output its check refused as invalid, the second a valid one
naming its artifacts. The section « Sorties » lists each output with its
content as recorded, its validity, its attempt and its artifacts. The job
« Essayer la tâche » of « Reprise du cockpit », in job-usage-unavailable,
recorded none.

False if an output is missing, if an invalid output is said valid or
rewritten, if an output is shown on another attempt than the one that
recorded it, or if a job that recorded none shows one.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_destination import dataset_of, launch_declared  # noqa: E402
from runs_destination import LaunchTree, observe, section  # noqa: E402
from runs_job_trace import job_of, outputs  # noqa: E402

# What the first attempt recorded: a text cut short, not JSON.
INVALID = '{"status": "success", "summary": "Changement enregistré'
VALID = {"status": "success", "summary": "Changement et démonstration enregistrés.",
         "artifacts": ["demo/search/build/result.json", "demo/search/build/demonstration.png"],
         "version": "synthetic-example"}


class RunsTraceOutputs(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def test_job_output_lists_each_structured_output_with_its_content_its_validity_its_attempt_and_its_artifacts(self):
        dataset = dataset_of(self.tree, "job-output")
        job_of(dataset, "search", "build")["attempts"] = [
            {"end": 290, "outcome": "fail", "output": INVALID, "output_valid": False},
            {"end": 365, "outcome": "pass", "output": json.dumps(VALID, ensure_ascii=False), "output_valid": True},
        ]
        reading, = observe(launch_declared(self.tree, "job-output-attempts", dataset), "/runs/job")[0]
        listed = outputs(reading)
        self.assertEqual(2, len(listed), f"the outputs listed: {[output['title'] for output in listed]}")
        first, second = (next((output for output in listed if f"tentative {number}" in output["title"].lower()), None)
                         for number in (1, 2))
        self.assertIsNotNone(first, f"no output of the first attempt: {[output['title'] for output in listed]}")
        self.assertIsNotNone(second, f"no output of the second attempt: {[output['title'] for output in listed]}")
        self.assertIn("non valide", first["title"], f"the invalid output is not said invalid: « {first['title']} »")
        self.assertIn(" ".join(INVALID.split()), first["content"], "the invalid output is not shown as it was recorded")
        self.assertIn("valide", second["title"], f"the valid output is not said valid: « {second['title']} »")
        self.assertNotIn("non valide", second["title"], f"the valid output is said invalid: « {second['title']} »")
        for phrase in ("Changement et démonstration enregistrés.", "synthetic-example"):
            self.assertIn(phrase, second["content"], f"the valid output does not show « {phrase} » it holds")
        for artifact in VALID["artifacts"]:
            self.assertIn(artifact, second["content"], f"the valid output does not name its artifact {artifact}")
            self.assertNotIn(artifact, first["content"], f"the invalid output names {artifact} it did not record")

    def test_a_job_that_recorded_no_output_says_so_and_shows_none(self):
        reading, = observe(self.tree.launch("job-usage-unavailable"), "/runs/job")[0]
        found = section(reading, "Sorties")
        self.assertIsNotNone(found, "the detail has no section « Sorties »")
        self.assertEqual([], outputs(reading), "a job that recorded no output shows one")
        self.assertIn("Aucune sortie enregistrée", found["content"],
                      f"the section does not say the job recorded no output: « {found['content']} »")


if __name__ == "__main__":
    unittest.main()
