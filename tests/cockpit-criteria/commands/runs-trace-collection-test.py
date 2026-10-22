#!/usr/bin/env python3
"""Criterion test 2 of C2a « Runs — sessions, configuration et prompts
collectés » (af-k2rbw1; Spec af-fgcw0d, user stories 137, 138, 139 and 144,
Testing Decisions 1, 7 and 8): what is collected when the sessions of a
dispatched ticket are sent, collected once however often the collection is
replayed, and never a secret.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on the dataset job-sessions: the synthetic city where
the dispatch door dispatched the ticket of « Recherche dans les notes » and
its sessions were sent their work (what it holds is written in
runs_trace.py). The collection is read again at each reading of its
sources, once a second, and the trace of the second session of « Réaliser »
replays the records of the first at its head. The case reads GET /runs/job
-- the job « Réaliser » -- as a headless Chromium renders it, then again
after more than three readings of the sources and after a reload, and every
address the cockpit serves over HTTP.

False if a session, a prompt or a configuration is listed twice once the
collection is replayed, if a record replayed by a later session is taken
for one sent to it, or if anything the cockpit serves holds a secret or a
private reasoning recorded in the trace of a session.
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runs_destination import LaunchTree, observe, section  # noqa: E402
from runs_trace import (  # noqa: E402
    SECRETS, SERVED, SYSTEM_PROMPT, USER_PROMPT_1, USER_PROMPT_2, prompts, raw_texts, served_text,
)

SESSIONS = ("demo-search-alex-1", "demo-search-alex-2")
# More than three readings of the sources of the launch (one a second).
REPLAYS_SECONDS = 4


class RunsTraceCollection(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def collected(self, address: str, reading: dict) -> dict:
        """What the detail of « Réaliser » shows of what was collected: the
        title of its history, the times each session is listed in it, the
        prompts listed by kind, the texts sent as the page holds them."""
        history = section(reading, "Sessions du job")
        self.assertIsNotNone(history, "the detail has no section « Sessions du job »")
        configured = section(reading, "Configuration")
        self.assertIsNotNone(configured, "the detail has no section « Configuration »")
        sent = raw_texts(address, reading["href"])
        title = next((a["content"] for a in reading["anchors"]
                      if a["tag"] == "summary" and a["chain"][:1] == [history["name"]]), "")
        return {
            "history": title,
            "listed": {session: history["content"].count(session) for session in SESSIONS},
            "configured": configured["content"].count(SESSIONS[1]),
            "prompts": {kind: len(found) for kind, found in prompts(reading).items()},
            "sent": {"system": sent.count(SYSTEM_PROMPT), "user": sent.count(USER_PROMPT_2),
                     "replayed": sent.count(USER_PROMPT_1)},
        }

    def test_the_sessions_sent_are_collected_once_however_often_the_collection_is_replayed(self):
        address = self.tree.launch("job-sessions")
        first, = observe(address, "/runs/job")[0]
        time.sleep(REPLAYS_SECONDS)
        later, reloaded = observe(address, "/runs/job", steps=({"reload": True},))[0]
        expected = {
            "history": "Sessions du job (2)",
            "listed": {"demo-search-alex-1": 1, "demo-search-alex-2": 1},
            "configured": 1,
            "prompts": {"Prompt système": 1, "Prompt utilisateur": 1},
            # The second session was sent the system prompt and its own user
            # prompt; what its trace replays of the first is not sent to it.
            "sent": {"system": 1, "user": 1, "replayed": 0},
        }
        for when, reading in (("first read", first), ("read again", later), ("reloaded", reloaded)):
            self.assertEqual(expected, self.collected(address, reading), f"what is collected, {when}")

    def test_nothing_the_cockpit_serves_holds_a_secret_or_a_private_reasoning(self):
        address = self.tree.launch("job-sessions")
        shown, chosen = observe(address, "/runs/job", steps=({"click": SESSIONS[0], "within": "session-history"},))[0]
        # Both sessions and their prompts shown, then everything served.
        self.assertIn(USER_PROMPT_2, raw_texts(address, shown["href"]), "the prompts of the last session are not shown")
        self.assertTrue(chosen["step"]["found"], f"no control to choose the session {SESSIONS[0]}")
        pages = {path: served_text(address, path) for path in (*SERVED, shown["href"], chosen["href"])}
        held = {path: [secret for secret in SECRETS if secret in text] for path, text in pages.items()}
        self.assertEqual({path: [] for path in pages}, held, "what the cockpit serves holds a secret of a session")


if __name__ == "__main__":
    unittest.main()
