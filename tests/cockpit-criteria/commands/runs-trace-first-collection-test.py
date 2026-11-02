#!/usr/bin/env python3
"""Criterion test of R9 « Collecte des traces Runs » (af-gfqzbk; Spec
af-fgcw0d, Testing Decisions 1, 7 and 8): a session sent once the cockpit is
up is kept at work from the first collection, however long the cockpit took
to come up.

runs-trace-collection-test.py turned red now and then, whatever else was on
the branch: on a busy host the cockpit took longer to come up than the
seconds the supervisor gave demo-search-alex-2, which had stopped when the
cockpit first read the sessions, and was first seen at work when the
collection was replayed. This case does not wait for a busy host: it launches
the real cockpit with the launcher of the profile, bin/project-launch, on
job-sessions with its projection kept, the session at work for a tenth of a
second, far less than any launch takes. It reads GET /runs/job, then the
projection, then launches the cockpit again on the same projection.

False if the projection does not hold demo-search-alex-2 at work on its bead
once the first cockpit collected it, or grows when the collection is
replayed.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_destination import dataset_of, launch_declared  # noqa: E402
from runs_destination import LaunchTree  # noqa: E402
from runs_trace import projection, wait_served  # noqa: E402

# More than three readings of the sources of the launch (one a second).
REPLAYS_SECONDS = 4


class RunsTraceFirstCollection(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def setUp(self) -> None:
        self.kept = Path(tempfile.mkdtemp(prefix="cockpit-trace-")) / "sessions.jsonl"

    def tearDown(self) -> None:
        self.tree.stop_all()
        shutil.rmtree(self.kept.parent, ignore_errors=True)

    def dataset(self) -> dict:
        """job-sessions, its projection kept at `self.kept`; the two sessions
        of « Réaliser » sent at once, the second at work a tenth of a
        second."""
        dataset = dataset_of(self.tree, "job-sessions")
        dataset["session_trace"] = str(self.kept)
        run = next(run for run in dataset["fixtures"]["runs"] if run["id"] == "search")
        sessions = {session["name"]: session
                    for session in next(job for job in run["jobs"] if job["id"] == "build")["sessions"]}
        sessions["demo-search-alex-1"]["dispatched"] = {"after_seconds": 0, "running_seconds": 0}
        sessions["demo-search-alex-2"]["dispatched"] = {"after_seconds": 0, "running_seconds": 0.1,
                                                        "recorded_while_running": 9}
        return dataset

    def at_work(self) -> list[str]:
        """The beads the projection holds demo-search-alex-2 at work on."""
        return [record["active_bead"] for record in projection(self.kept)
                if record.get("kind") == "session" and record.get("session") == "demo-search-alex-2"
                and record.get("active_bead")]

    def test_a_session_at_work_is_kept_from_the_first_collection_and_the_replay_adds_nothing(self):
        name = "job-sessions-first-collection"
        address = launch_declared(self.tree, name, self.dataset())
        wait_served(address, "/runs/job", ("Version : exemple synthétique\n",))
        time.sleep(REPLAYS_SECONDS)
        self.assertTrue(self.kept.is_file(), f"no projection is kept at {self.kept}")
        self.assertEqual(["synthetic-workflow-search-build-attempt-1"], self.at_work(),
                         "the session at work is not kept by the first collection")
        kept = self.kept.read_bytes()
        self.tree.stop_all()
        again = launch_declared(self.tree, name, self.dataset())
        wait_served(again, "/runs/job", ("Version : exemple synthétique\n",))
        time.sleep(REPLAYS_SECONDS)
        self.assertEqual(kept, self.kept.read_bytes(), "the projection grows when the collection is replayed")


if __name__ == "__main__":
    unittest.main()
