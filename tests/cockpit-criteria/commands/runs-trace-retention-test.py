#!/usr/bin/env python3
"""Criterion test 2 of C2b « Runs — événements, contrôles, sorties, usage et
historique durable » (af-ofz29f; Spec af-fgcw0d, user story 144, Testing
Decisions 1, 7 and 8): the trace of a dispatched ticket found again after
the cockpit restarts and the D01 pieces are purged.

The case launches the real cockpit with the launcher of the profile,
bin/project-launch, on a dataset it declares from job-sessions -- the
synthetic city where the dispatch door dispatched the ticket of « Recherche
dans les notes » -- with the place where the launch keeps the projection of
the sessions and the evidence store the flow files its pieces in. The
synthetic supervisor sends the two sessions of « Réaliser » once the
cockpit is up, as it dispatches a ticket: what Codex recorded of each -- the
tools it called, its usage -- and the job's attempts, the second passed
with the pieces it captured and the structured output it recorded. The
case reads GET /runs/job -- the job « Réaliser » -- as a headless Chromium
renders it and over HTTP.

Then the cockpit stops, the evidence store of the Spec is purged as the
purge of the evidence capture (« purge --spec ») does once the Outcome is
promoted -- its folder removed, the fingerprints left in the tracker -- and
the supervisor
no longer holds what the providers recorded of those sessions; the cockpit
is launched again on the same projection and the same store, and the case
reads the same job.

False if the events, the tool calls, the usage, the controls or the
outputs of the job are lost at the restart, if any of them is listed twice,
or if a piece the purge removed is still said present or offered by a
link.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_destination import dataset_of, launch_declared  # noqa: E402
from runs_destination import LaunchTree, events, observe, section, text  # noqa: E402
from runs_job_trace import (codex_start, codex_tool, codex_usage, gates, job_of, number, outputs,  # noqa: E402
                            tokens, tool_calls, usage_table, wait_page)
from runs_trace import projection  # noqa: E402

# More than three readings of the sources of the launch (one a second).
REPLAYS_SECONDS = 4
SYSTEM = "# Auteur\n\n# Mission\nRéaliser sur le périmètre approuvé."
OUTPUT = {"status": "success", "summary": "Changement et démonstration enregistrés.",
          "artifacts": ["demo/search/build/result.json"]}


def first_session() -> list[dict]:
    return (codex_start("demo-search-alex-1", "12:13:10.000", SYSTEM, "# Tâche\nRéaliser, première session.")
            + codex_tool("call_alex1_read", "12:13:15.200", 0.64, "read", "docs/spec-recherche.md")
            + codex_usage([("12:14:30.000", tokens(31554, 24000, 2537, 673))]))


def second_session() -> list[dict]:
    return (first_session()
            + codex_start("demo-search-alex-2", "12:14:37.000", SYSTEM, "# Tâche\nRéaliser, seconde session.")
            + codex_tool("call_alex2_write", "12:15:02.000", 1.25, "write", "notes/search.py")
            + codex_usage([("12:15:50.000", tokens(18446, 16616, 2000, 300))]))


class RunsTraceRetention(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def setUp(self) -> None:
        self.place = Path(tempfile.mkdtemp(prefix="cockpit-retention-"))
        self.kept = self.place / "trace" / "sessions.jsonl"
        self.store = self.place / "evidence"

    def tearDown(self) -> None:
        self.tree.stop_all()
        shutil.rmtree(self.place, ignore_errors=True)

    def dataset(self, recorded: bool) -> dict:
        """job-sessions, its projection kept at `self.kept` and its pieces
        filed in `self.store`; « Réaliser » refused once by its check, then
        passed with its pieces and its output. With `recorded`, the two
        sessions of « Réaliser » sent once the cockpit is up, the supervisor
        holding what Codex recorded of each; else the supervisor holds
        nothing of what they were sent and did."""
        dataset = dataset_of(self.tree, "job-sessions")
        dataset["session_trace"] = str(self.kept)
        dataset["evidence_store"] = str(self.store)
        job = job_of(dataset, "search", "build")
        job["attempts"] = [
            {"end": 290, "outcome": "fail", "log": "refus : test en échec"},
            {"end": 365, "outcome": "pass", "pieces": ["tdd_green", "demonstration"],
             "output": json.dumps(OUTPUT, ensure_ascii=False), "output_valid": True},
        ]
        sessions = [{"name": "demo-search-alex-1", "provider": "codex", "model": "gpt-6.1-sol", "start": 190, "end": 277},
                    {"name": "demo-search-alex-2", "provider": "codex", "model": "gpt-6.1-sol", "start": 277, "end": 365}]
        if recorded:
            sessions[0].update(transcript=first_session(), dispatched={"after_seconds": 2, "running_seconds": 0})
            sessions[1].update(transcript=second_session(),
                               dispatched={"after_seconds": 2, "running_seconds": 4, "recorded_while_running": 9})
        job["sessions"] = sessions
        return dataset

    def trace(self, address: str, reading: dict) -> dict:
        """What the detail of « Réaliser » shows of its trace: its events,
        its tool calls, the total of its usage, the tokens known of the
        run, its controls and its outputs."""
        table = usage_table(address, reading["href"])
        return {
            "events": [event["text"] for event in events(reading)],
            "tool calls": [(call["time"], call["text"]) for call in tool_calls(reading)],
            "total": table.get("Total", [""])[0],
            "head": text(reading, "run-summary"),
            "controls": [gate["title"] for gate in gates(reading)],
            "outputs": [output["title"] for output in outputs(reading)],
        }

    def test_the_trace_of_a_dispatched_ticket_is_found_again_after_a_restart_once_and_a_purged_piece_is_said_absent(self):
        name = "job-sessions-retained"
        address = launch_declared(self.tree, name, self.dataset(recorded=True))
        # What the last session recorded is collected by the time it stops.
        wait_page(address, "/runs/job", ("notes/search.py",))
        time.sleep(REPLAYS_SECONDS)
        before, = observe(address, "/runs/job")[0]
        shown = self.trace(address, before)
        # Both tool calls, each once, the first session's not replayed by
        # the second; the usage of both sessions, 34 091 + 20 446.
        self.assertEqual([("14:13:15", "read"), ("14:15:02", "write")],
                         [(moment, next((tool for tool in ("read", "write") if tool in said), said))
                          for moment, said in shown["tool calls"]],
                         f"the tool calls collected: {shown['tool calls']}")
        self.assertRegex(shown["total"], number(54537), f"the usage collected: {shown['total']!r}")
        self.assertRegex(shown["head"], number(54537), f"the head of the run: « {shown['head']} »")
        self.assertEqual(2, len(shown["controls"]), f"the controls of the job: {shown['controls']}")
        self.assertEqual(1, len(shown["outputs"]), f"the outputs of the job: {shown['outputs']}")
        passed = next(gate for gate in gates(before) if "Tentative 2" in gate["title"])
        for piece in ("tdd_green", "demonstration"):
            self.assertIn(f"{piece} · présente", passed["content"], f"the piece {piece} is not said present")
        # The cockpit stops; the purge removes the folder of the Spec from
        # the store -- the only one it holds -- as the purge of the evidence
        # capture (« purge --spec ») does.
        self.tree.stop_all()
        folders = [folder for folder in self.store.iterdir() if folder.is_dir()] if self.store.is_dir() else []
        self.assertEqual(1, len(folders), f"the store does not hold the folder of one Spec: {folders}")
        shutil.rmtree(folders[0])
        # Launched again on the same projection and the same store, the
        # supervisor holding nothing more of those sessions.
        again = launch_declared(self.tree, name, self.dataset(recorded=False))
        time.sleep(REPLAYS_SECONDS)
        after, reloaded = observe(again, "/runs/job", steps=({"reload": True},))[0]
        for when, reading in (("after the restart", after), ("reloaded", reloaded)):
            found = self.trace(again, reading)
            self.assertEqual({key: shown[key] for key in ("events", "tool calls", "total", "head", "outputs")},
                             {key: found[key] for key in ("events", "tool calls", "total", "head", "outputs")},
                             f"the trace of the job {when}")
            self.assertEqual(shown["controls"], found["controls"], f"the controls of the job {when}")
            passed = next(gate for gate in gates(reading) if "Tentative 2" in gate["title"])
            for piece in ("tdd_green", "demonstration"):
                self.assertIn(f"{piece} · absente", passed["content"],
                              f"{when}: the piece {piece} the purge removed is not said absent: « {passed['content']} »")
                self.assertNotIn(f"{piece} · présente", passed["content"], f"{when}: the purged piece {piece} is said present")
            links = [control["name"] for control in reading.get("controls") or []
                     if control["tag"] == "a" and any(piece in control["name"] for piece in ("tdd_green", "demonstration"))]
            self.assertEqual([], links, f"{when}: a link offers a piece the purge removed")
            controls = section(reading, "Contrôles")
            self.assertIsNotNone(controls, f"{when}: the detail has no section « Contrôles »")
        # The projection holds each record once.
        records = projection(self.kept)
        self.assertEqual(len(records), len({json.dumps(record, sort_keys=True) for record in records}),
                         "the projection holds a record twice")


if __name__ == "__main__":
    unittest.main()
