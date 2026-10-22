#!/usr/bin/env python3
"""Criterion test 2 of C2a « Runs — sessions, configuration et prompts
collectés » (af-k2rbw1; Spec af-fgcw0d, user stories 137, 138, 139 and 145,
Testing Decisions 1, 7 and 8): what is collected when the sessions of a
dispatched ticket are sent, collected once however often the collection is
replayed, and never a secret.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on a dataset the case declares from job-sessions -- the
synthetic city where the dispatch door dispatched the ticket of « Recherche
dans les notes » -- with the place where the launch keeps the projection of
the sessions. In the first case the synthetic supervisor sends the two
sessions of « Réaliser » once the cockpit is up, as it dispatches a ticket:
the first wakes and stops between two readings of the sessions, and is
never listed; the second is listed while it runs, with only what its trace
replays of the first recorded, and what it was sent is recorded by the time
it stops. The case reads GET /runs/job -- the job « Réaliser » -- as a
headless Chromium renders it and over HTTP, and the projection the launch
kept; then launches the cockpit again on the same projection, which reads
the same supervisor again from its start.

False if a session sent between two readings, or what a session was sent
after it was first read, is not collected; if a session, a prompt or a
configuration is listed twice, or the projection grows, once the collection
is replayed; if a record replayed by a later session is taken for one sent
to it; or if the projection or anything the cockpit serves holds a secret
or a private reasoning recorded in the trace of a session.
"""

from __future__ import annotations

import shutil
import stat
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_destination import dataset_of, launch_declared  # noqa: E402
from runs_destination import LaunchTree, observe, section  # noqa: E402
from runs_trace import projection, prompts, raw_texts, served_text, wait_served  # noqa: E402

FIRST, LAST = "demo-search-alex-1", "demo-search-alex-2"
# What each session of « Réaliser » was sent as its user prompt says which
# one it is; both were sent the same system prompt.
SENT_TO_FIRST = "Version : exemple synthétique, première session"
SENT_TO_LAST = "Version : exemple synthétique\n"
SYSTEM_SENT = "# Auteur\n\n# Mission\nRéaliser sur le périmètre approuvé."
# More than three readings of the sources of the launch (one a second).
REPLAYS_SECONDS = 4


def strings(value) -> list[str]:
    """Every text a record holds, wherever it holds it."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [found for item in value.values() for found in strings(item)]
    if isinstance(value, list):
        return [found for item in value for found in strings(item)]
    return []


class RunsTraceCollection(unittest.TestCase):
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

    def dataset(self, dispatched: bool) -> dict:
        """job-sessions, its projection kept at `self.kept`; with
        `dispatched`, the sessions of « Réaliser » sent once the cockpit is
        up: the first wakes and stops at once, the second runs four seconds
        with the nine records its trace replays of the first."""
        dataset = dataset_of(self.tree, "job-sessions")
        dataset["session_trace"] = str(self.kept)
        if dispatched:
            run = next(run for run in dataset["fixtures"]["runs"] if run["id"] == "search")
            sessions = {session["name"]: session
                        for session in next(job for job in run["jobs"] if job["id"] == "build").get("sessions") or []}
            if FIRST in sessions:
                sessions[FIRST]["dispatched"] = {"after_seconds": 2, "running_seconds": 0}
            if LAST in sessions:
                sessions[LAST]["dispatched"] = {"after_seconds": 2, "running_seconds": 4, "recorded_while_running": 9}
        return dataset

    def collected(self, address: str, reading: dict) -> dict:
        """What the detail of « Réaliser » shows of what was collected: the
        title of its history, the times each session is listed in it and
        whether an end nothing recorded is said, the prompts listed by kind,
        the texts sent as the page holds them."""
        history = section(reading, "Sessions du job")
        self.assertIsNotNone(history, "the detail has no section « Sessions du job »")
        configured = section(reading, "Configuration")
        self.assertIsNotNone(configured, "the detail has no section « Configuration »")
        sent = "\n".join(raw_texts(address, reading["href"]))
        title = next((a["content"] for a in reading["anchors"]
                      if a["tag"] == "summary" and a["chain"][:1] == [history["name"]]), "")
        return {
            "history": title,
            "listed": {session: history["content"].count(session) for session in (FIRST, LAST)},
            "an end not collected": "non collecté" in history["content"],
            "configured": configured["content"].count(LAST),
            "prompts": {kind: len(found) for kind, found in prompts(reading).items()},
            "sent": {"system": sent.count(SYSTEM_SENT), "user": sent.count(SENT_TO_LAST),
                     "replayed": sent.count(SENT_TO_FIRST)},
        }

    def test_the_sessions_dispatched_are_collected_at_their_start_and_stop_once_however_often_replayed(self):
        name = "job-sessions-dispatched"
        address = launch_declared(self.tree, name, self.dataset(dispatched=True))
        # What the last session was sent is recorded by the time it stops.
        self.assertIn(SENT_TO_LAST, "\n".join(wait_served(address, "/runs/job", (SENT_TO_LAST,))),
                      "what the last session was sent after it was first read is not collected")
        time.sleep(REPLAYS_SECONDS)
        first, = observe(address, "/runs/job")[0]
        expected = {
            "history": "Sessions du job (2)",
            "listed": {FIRST: 1, LAST: 1},
            # Both stops were recorded by the supervisor.
            "an end not collected": False,
            "configured": 1,
            "prompts": {"Prompt système": 1, "Prompt utilisateur": 1},
            # The last session was sent the system prompt and its own user
            # prompt; what its trace replays of the first is not sent to it.
            "sent": {"system": 1, "user": 1, "replayed": 0},
        }
        self.assertEqual(expected, self.collected(address, first), "what is collected of the sessions dispatched")
        # The projection, private, holds each record once: the session that
        # was never listed, and what each session was sent.
        self.assertTrue(self.kept.is_file(), f"no projection is kept at {self.kept}")
        self.assertEqual(0o600, stat.S_IMODE(self.kept.stat().st_mode), "the projection is not private")
        kept = self.kept.read_bytes()
        records = projection(self.kept)
        self.assertEqual(len(records), len({repr(sorted(record.items())) for record in records}),
                         "the projection holds a record twice")
        held = "\n".join(text for record in records for text in strings(record))
        for text in (FIRST, LAST, SENT_TO_FIRST, SENT_TO_LAST, SYSTEM_SENT):
            self.assertIn(text, held, f"the projection does not hold {text!r}")
        # Read again, then replayed from the start of the supervisor by
        # another cockpit on the same projection: nothing is added.
        time.sleep(REPLAYS_SECONDS)
        self.assertEqual(kept, self.kept.read_bytes(), "the projection grows when the sources are read again")
        self.tree.stop_all()
        again = launch_declared(self.tree, name, self.dataset(dispatched=True))
        wait_served(again, "/runs/job", (SENT_TO_LAST,))
        time.sleep(REPLAYS_SECONDS)
        replayed, reloaded = observe(again, "/runs/job", steps=({"reload": True},))[0]
        self.assertEqual(kept, self.kept.read_bytes(), "the projection grows when the collection is replayed")
        for when, reading in (("replayed", replayed), ("reloaded", reloaded)):
            self.assertEqual(expected, self.collected(again, reading), f"what is collected, {when}")

    def test_nothing_the_collection_keeps_or_the_cockpit_serves_holds_a_secret_or_a_private_reasoning(self):
        # In what was recorded of demo-search-alex-2: the value of a key in
        # its environment, a token a tool printed, a private reasoning.
        secrets = ("sk-proj-SYNTHETIQUE-ne-pas-collecter", "ghp_SYNTHETIQUEnepascollecter0000000000",
                   "RAISONNEMENT-PRIVE-de-la-session")
        # The addresses the cockpit serves that could carry what a
        # collection kept.
        served = ("/runs", "/runs/run", "/runs/job", "/api/status", "/api/journal", "/api/health", "/api/requests",
                  "/api/notifications")
        address = launch_declared(self.tree, "job-sessions-kept", self.dataset(dispatched=False))
        shown, chosen = observe(address, "/runs/job", steps=({"click": FIRST, "within": "session-history"},))[0]
        # Both sessions and their prompts shown, then everything served.
        self.assertIn(SENT_TO_LAST, "\n".join(raw_texts(address, shown["href"])),
                      "the prompts of the last session are not shown")
        self.assertTrue(chosen["step"]["found"], f"no control to choose the session {FIRST}")
        pages = {path: served_text(address, path) for path in (*served, shown["href"], chosen["href"])}
        self.assertTrue(self.kept.is_file(), f"no projection is kept at {self.kept}")
        pages["the projection"] = self.kept.read_text(encoding="utf-8")
        self.assertIn(SENT_TO_LAST, "\n".join(strings(projection(self.kept))), "the projection holds no prompt sent")
        held = {path: [secret for secret in secrets if secret in text] for path, text in pages.items()}
        self.assertEqual({path: [] for path in pages}, held, "what the cockpit keeps or serves holds a secret")


if __name__ == "__main__":
    unittest.main()
