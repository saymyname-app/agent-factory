#!/usr/bin/env python3
# ci: over-ceiling — the criterion of R9 is 64 trials, 8 at a time, each launching the cockpit twice: fewer would prove less than it says
"""Criterion test of R9 « Collecte des traces Runs » (af-gfqzbk; Spec
af-fgcw0d, Testing Decisions 1, 7 and 8): a session sent once the cockpit is
up is kept at work from the first collection, however long the cockpit took
to come up, at each of 64 trials run 8 at a time: four cases of 16, as a
criterion test must end within its budget on a busy host (600 s,
config/test-budgets.json; 64 in one case took 810 s at a load of 55).

runs-trace-collection-test.py turned red now and then, whatever else was on
the branch: on a busy host the cockpit took longer to come up than the
seconds the supervisor gave demo-search-alex-2, which had stopped when the
cockpit first read the sessions, and was first seen at work when the
collection was replayed. This case does not wait for a busy host: each trial
launches the real cockpit with the launcher of the profile,
bin/project-launch, on job-sessions with its projection kept, the session at
work for a tenth of a second, far less than any launch takes. It reads GET
/runs/job, then the projection, then launches the cockpit again on the same
projection. The trials run side by side, each on a tree of its own: the
launcher reads a dataset of the case in the tree while it starts. This file
runs at the merged result like any criterion test, in the regression of the
merge.

False if, at one trial, the projection does not hold demo-search-alex-2 at
work on its bead once the first cockpit collected it, or grows when the
collection is replayed.
"""

from __future__ import annotations

import queue
import shutil
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_destination import dataset_of, launch_declared  # noqa: E402
from runs_destination import LaunchTree  # noqa: E402
from runs_trace import projection, wait_served  # noqa: E402

# More than three readings of the sources of the launch (one a second).
REPLAYS_SECONDS = 4
TRIALS = 16
AT_ONCE = 8


class RunsTraceFirstCollection(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        with ThreadPoolExecutor(max_workers=AT_ONCE) as pool:
            cls.trees = list(pool.map(lambda _: LaunchTree(), range(AT_ONCE)))
        cls.free = queue.Queue()
        for tree in cls.trees:
            cls.free.put(tree)

    @classmethod
    def tearDownClass(cls) -> None:
        for tree in cls.trees:
            tree.remove()

    def setUp(self) -> None:
        self.refused = threading.Event()

    def dataset(self, tree: LaunchTree, kept: Path) -> dict:
        """job-sessions, its projection kept at `kept`; the two sessions of
        « Réaliser » sent at once, the second at work a tenth of a second."""
        dataset = dataset_of(tree, "job-sessions")
        dataset["session_trace"] = str(kept)
        run = next(run for run in dataset["fixtures"]["runs"] if run["id"] == "search")
        sessions = {session["name"]: session
                    for session in next(job for job in run["jobs"] if job["id"] == "build")["sessions"]}
        sessions["demo-search-alex-1"]["dispatched"] = {"after_seconds": 0, "running_seconds": 0}
        sessions["demo-search-alex-2"]["dispatched"] = {"after_seconds": 0, "running_seconds": 0.1,
                                                        "recorded_while_running": 9}
        return dataset

    def at_work(self, kept: Path) -> list[str]:
        """The beads the projection holds demo-search-alex-2 at work on."""
        return [record["active_bead"] for record in projection(kept)
                if record.get("kind") == "session" and record.get("session") == "demo-search-alex-2"
                and record.get("active_bead")]

    def trial(self, _number: int) -> dict | None:
        """One launch, then one on the same projection: what the projection
        held after the first, and whether the second left it byte for byte.
        None once a trial was refused: one is enough to refuse the criterion."""
        if self.refused.is_set():
            return None
        tree = self.free.get()
        kept = Path(tempfile.mkdtemp(prefix="cockpit-trace-")) / "sessions.jsonl"
        name = "job-sessions-first-collection"
        try:
            address = launch_declared(tree, name, self.dataset(tree, kept))
            wait_served(address, "/runs/job", ("Version : exemple synthétique\n",))
            time.sleep(REPLAYS_SECONDS)
            seen = self.at_work(kept) if kept.is_file() else []
            if seen != ["synthetic-workflow-search-build-attempt-1"]:
                self.refused.set()
                return {"at work": seen, "same after the replay": None}
            first = kept.read_bytes()
            tree.stop_all()
            again = launch_declared(tree, name, self.dataset(tree, kept))
            wait_served(again, "/runs/job", ("Version : exemple synthétique\n",))
            time.sleep(REPLAYS_SECONDS)
            same = first == kept.read_bytes()
            if not same:
                self.refused.set()
            return {"at work": seen, "same after the replay": same}
        finally:
            tree.stop_all()
            shutil.rmtree(kept.parent, ignore_errors=True)
            self.free.put(tree)

    def assert_every_trial_keeps_the_session_at_work(self) -> None:
        with ThreadPoolExecutor(max_workers=AT_ONCE) as pool:
            seen = list(pool.map(self.trial, range(TRIALS)))
        expected = {"at work": ["synthetic-workflow-search-build-attempt-1"], "same after the replay": True}
        self.assertEqual({}, {number: trial for number, trial in enumerate(seen) if trial not in (expected, None)},
                         "the trials where the session at work is not kept by the first collection, "
                         "or where the projection grows when the collection is replayed")
        self.assertEqual(16, seen.count(expected), "the trials that ran to their end")

    def test_trials_1_to_16(self):
        self.assert_every_trial_keeps_the_session_at_work()

    def test_trials_17_to_32(self):
        self.assert_every_trial_keeps_the_session_at_work()

    def test_trials_33_to_48(self):
        self.assert_every_trial_keeps_the_session_at_work()

    def test_trials_49_to_64(self):
        self.assert_every_trial_keeps_the_session_at_work()


if __name__ == "__main__":
    unittest.main()
