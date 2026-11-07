#!/usr/bin/env python3
"""The two declared datasets that let a read-only Evaluator observe criterion
2 of C2b (af-ofz29f; Spec af-fgcw0d, user story 144, Testing Decisions 7 and
8): the launched cockpit restarted, the D01 pieces purged, with no gesture
but the launches of the recipe.

The case launches the real cockpit with bin/project-launch on
job-retention-before, reads GET /runs/job, stops it, and launches
job-retention-purged at the same commit: the supervisor holds nothing more
of those sessions, and the recipe ran the real purge of the evidence capture
on the synthetic store of the first launch.

False if the trace is lost or listed twice, if a purged piece is said present
or linked, if a piece is purged in a store a dataset names, or if a launch
of job-retention-before finds what an earlier one left.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_destination import dataset_of  # noqa: E402
from runs_destination import LaunchTree, events, observe, text  # noqa: E402
from runs_job_trace import gates, outputs, tool_calls, usage_table, wait_page  # noqa: E402
from runs_trace import projection  # noqa: E402

BEFORE = "job-retention-before"
PURGED = "job-retention-purged"
PIECES = ("tdd_green", "demonstration")
ROOT = Path(tempfile.gettempdir()) / "cockpit-synthetic-retention"


class RunsTraceRetentionDatasets(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()
        cls.place = ROOT / f"job-retention-{cls.tree.head}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()
        shutil.rmtree(cls.place, ignore_errors=True)

    def tearDown(self) -> None:
        self.tree.stop_all()

    def trace(self, address: str, reading: dict) -> dict:
        return {
            "events": [event["text"] for event in events(reading)],
            "tool calls": [(call["time"], call["text"]) for call in tool_calls(reading)],
            "total": usage_table(address, reading["href"]).get("Total", [""])[0],
            "head": text(reading, "run-summary"),
            "controls": [gate["title"] for gate in gates(reading)],
            "outputs": [output["title"] for output in outputs(reading)],
        }

    def read_before(self) -> tuple[str, dict]:
        address = self.tree.launch(BEFORE, self.tree.head)
        wait_page(address, "/runs/job", ("Tentative 2",))
        reading, = observe(address, "/runs/job")[0]
        return address, reading

    def test_the_second_launch_finds_the_trace_once_and_says_the_purged_pieces_absent(self):
        address, before = self.read_before()
        shown = self.trace(address, before)
        self.assertTrue(shown["tool calls"], "the first launch shows no tool call")
        passed = next(gate for gate in gates(before) if "Tentative 2" in gate["title"])
        for piece in PIECES:
            self.assertIn(f"{piece} · présente", passed["content"])
        self.tree.stop_all()

        again = self.tree.launch(PURGED, self.tree.head)
        wait_page(again, "/runs/job", ("Tentative 2",))
        after, reloaded = observe(again, "/runs/job", steps=({"reload": True},))[0]
        for when, reading in (("after the restart", after), ("reloaded", reloaded)):
            self.assertEqual(shown, self.trace(again, reading), f"the trace of the job {when}")
            passed = next(gate for gate in gates(reading) if "Tentative 2" in gate["title"])
            for piece in PIECES:
                self.assertIn(f"{piece} · absente", passed["content"], when)
                self.assertNotIn(f"{piece} · présente", passed["content"], when)
            links = [control["name"] for control in reading.get("controls") or []
                     if control["tag"] == "a" and any(piece in control["name"] for piece in PIECES)]
            self.assertEqual([], links, f"{when}: a link offers a purged piece")
        records = projection(self.place / "sessions.jsonl")
        self.assertEqual(len(records), len({json.dumps(record, sort_keys=True) for record in records}),
                         "the projection holds a record twice")
        self.assertEqual([], [path for path in (self.place / "evidence").rglob("*.json")],
                         "the purge left a piece in the synthetic store")

        # The first dataset starts over: the pieces are filed again.
        self.tree.stop_all()
        _, restarted = self.read_before()
        passed = next(gate for gate in gates(restarted) if "Tentative 2" in gate["title"])
        for piece in PIECES:
            self.assertIn(f"{piece} · présente", passed["content"], "the first dataset kept the purge")

    def test_a_dataset_names_no_place_of_its_own_for_the_purge(self):
        for name in (BEFORE, PURGED):
            dataset = dataset_of(self.tree, name)
            self.assertNotIn("evidence_store", dataset, f"{name} names a store")
            self.assertNotIn("session_trace", dataset, f"{name} names a projection")
            self.assertEqual({"place": "job-retention", "purge": name == PURGED}, dataset["retention"])


if __name__ == "__main__":
    unittest.main()
