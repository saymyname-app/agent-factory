#!/usr/bin/env python3
"""Criterion test 1 of C2b « Runs — événements, contrôles, sorties, usage et
historique durable » (af-ofz29f; Spec af-fgcw0d, user story 143, Testing
Decisions 1, 7 and 8): the events of a job and the tool calls of its
sessions, state job-event.

Each case launches the real cockpit with the launcher of the profile,
bin/project-launch, on a dataset the case declares from job-event: the job
« Réaliser » of « Recherche dans les notes » (run triggered at 14:10, Paris)
worked by two sessions of Alex the case writes, each with what Codex
recorded of it -- the tools it called, when, and what they printed -- the
second replaying at its head what the first recorded, as a resumed Codex
session does. The case reads GET /runs/job -- that job, under the frise of
its run -- as a headless Chromium renders it, and over HTTP.

The events beside the detail list the tool calls of the sessions among the
other events of the job, in the order they happened, each at its time of
Paris, with its duration and the session that called it; opening one shows
what it was given.

False if a tool call is missing, listed twice because a later session
replays it, out of the order of the events, at another time than Paris's,
without its duration or its session; or if what a tool was given shows a
credential it carried.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_destination import dataset_of, launch_declared  # noqa: E402
from runs_destination import LaunchTree, events, family, observe  # noqa: E402
from runs_job_trace import codex_start, codex_tool, duration, job_of, served, tool_calls  # noqa: E402

SYSTEM = "# Auteur\n\n# Mission\nRéaliser sur le périmètre approuvé."
CREDENTIAL = "ghp_SYNTHETIQUEnepascollecter0000000000"


def first_session() -> list[dict]:
    """What Codex recorded of demo-search-alex-1 (+3 min 10 s to +4 min 37
    s): it read the Spec, then ran the tests."""
    return (codex_start("demo-search-alex-1", "12:13:10.000", SYSTEM, "# Tâche\nRéaliser, première session.")
            + codex_tool("call_alex1_read", "12:13:15.200", 0.64, "read", "docs/spec-recherche.md")
            + codex_tool("call_alex1_exec", "12:13:27.000", 2.5, "exec", "python3 -m pytest -q tests/notes"))


def second_session() -> list[dict]:
    """What Codex recorded of demo-search-alex-2 (+4 min 37 s to +6 min 5
    s): what the first recorded, replayed at its head, then it wrote the
    search and pushed it -- the address it pushed to carrying a token."""
    return (first_session()
            + codex_start("demo-search-alex-2", "12:14:37.000", SYSTEM, "# Tâche\nRéaliser, seconde session.")
            + codex_tool("call_alex2_write", "12:15:02.000", 1.25, "write", "notes/search.py")
            + codex_tool("call_alex2_push", "12:15:20.000", 0.4, "exec",
                         f"git push https://{CREDENTIAL}@example.invalid/notes.git main"))


class RunsTraceEvents(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def tearDown(self) -> None:
        self.tree.stop_all()

    def launch(self, name: str, opened: bool = True) -> str:
        """job-event, its job « Réaliser » worked by the two sessions; with
        `opened` false, no event open at first."""
        dataset = dataset_of(self.tree, "job-event")
        if not opened:
            dataset["ui"]["selected_event"] = None
        job_of(dataset, "search", "build")["sessions"] = [
            {"name": "demo-search-alex-1", "provider": "codex", "model": "gpt-6.1-sol", "start": 190, "end": 277,
             "transcript": first_session()},
            {"name": "demo-search-alex-2", "provider": "codex", "model": "gpt-6.1-sol", "start": 277, "end": 365,
             "transcript": second_session()},
        ]
        return launch_declared(self.tree, name, dataset)

    def test_job_event_lists_each_tool_call_once_in_order_with_its_paris_time_its_duration_and_its_session(self):
        address = self.launch("job-event-tools")
        reading, = observe(address, "/runs/job")[0]
        listed = events(reading)
        self.assertTrue(listed, "no event is listed beside the detail of the job")
        # Every event of the job, tool calls among them, in the order they
        # happened.
        times = [event["time"] for event in listed]
        self.assertNotIn(None, times, f"an event says no time of day: {[event['text'] for event in listed]}")
        self.assertEqual(sorted(times), times, "the events of the job are not listed in the order they happened")
        # The four tools the sessions called, each once: the first two are
        # replayed by the second session and stay the first's. 12:13:15 UTC
        # is 14:13:15 in Paris on 12 October.
        expected = [
            ("14:13:15", "read", "docs/spec-recherche.md", "0,64", "demo-search-alex-1"),
            ("14:13:27", "exec", "python3 -m pytest -q tests/notes", "2,5", "demo-search-alex-1"),
            ("14:15:02", "write", "notes/search.py", "1,25", "demo-search-alex-2"),
            ("14:15:20", "exec", "git push", "0,4", "demo-search-alex-2"),
        ]
        calls = tool_calls(reading)
        self.assertEqual([moment for moment, *_ in expected], [call["time"] for call in calls],
                         f"the tool calls listed: {[call['text'] for call in calls]}")
        for (moment, tool, given, lasted, session), call in zip(expected, calls):
            self.assertIn(tool, call["text"], f"the call at {moment} does not name its tool: « {call['text']} »")
            self.assertIn(given, call["content"], f"the call at {moment} does not say what it was given")
            self.assertRegex(call["text"], duration(lasted), f"the call at {moment} does not say it lasted {lasted} s")
            self.assertIn(session, call["content"], f"the call at {moment} does not say its session {session}")
            self.assertEqual("turquoise", family(call["colours"][0]) if call["colours"] else None,
                             f"the call at {moment} is not drawn in the colour of the tools")
        # The calls replayed by the second session are not listed again.
        self.assertEqual(1, sum("docs/spec-recherche.md" in event["content"] for event in listed),
                         "the call the second session replays is listed twice")
        page = served(address, reading["href"])
        self.assertNotIn(CREDENTIAL, page, "the page shows the token a tool was given")

    def test_opening_a_tool_call_shows_what_it_was_given_its_session_and_its_duration_and_a_reload_keeps_it(self):
        # No event open at first: the one open is the one the case opens.
        address = self.launch("job-event-opened", opened=False)
        shown, opened, reloaded = observe(address, "/runs/job", steps=(
            {"click": "python3 -m pytest", "within": "event-list"},
            {"reload": True},
        ))[0]
        self.assertTrue(opened["step"]["found"], "no event of the call that ran the tests can be opened")
        for when, reading in (("opened", opened), ("reloaded", reloaded)):
            open_ = [event for event in events(reading) if event["open"]]
            self.assertEqual(1, len(open_), f"{when}: not one event is open: {[e['text'] for e in open_]}")
            said = open_[0]["content"]
            for phrase in ("python3 -m pytest -q tests/notes", "demo-search-alex-1", "14:13:27"):
                self.assertIn(phrase, said, f"{when}: the call opened does not say « {phrase} »: « {said} »")
            self.assertRegex(said, duration("2,5"), f"{when}: the call opened does not say it lasted 2,5 s")


if __name__ == "__main__":
    unittest.main()
