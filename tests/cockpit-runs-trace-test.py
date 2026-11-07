#!/usr/bin/env python3
"""What the trace of the sessions keeps of a job (C2b, af-ofz29f): the
input of a tool call with no credential in clear (AGENTS.md: never put
secrets in logs), and the usage of a job that is missing when no counter
of its session falls within the job, never zero."""
import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from cockpit.runs.trace import done  # noqa: E402
from cockpit.runs.workflows import workflow_runs  # noqa: E402

SECRET = "s3cr3t-de-recette-42"


def ts(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


def codex_call(call, arguments):
    return {"timestamp": "2026-10-19T10:02:00Z", "type": "response_item",
            "payload": {"type": "function_call", "call_id": call, "name": "shell", "arguments": arguments}}


def claude_call(call, given):
    return {"timestamp": "2026-10-19T10:02:00Z", "type": "assistant",
            "message": {"id": "msg-" + call, "content": [{"type": "tool_use", "id": call, "name": "Bash",
                                                         "input": given}]}}


class ToolInputMasked(unittest.TestCase):
    def test_no_credential_shows_in_clear_in_what_a_tool_was_given(self):
        records = [
            claude_call("c1", {"api_key": SECRET}),
            claude_call("c2", {"command": "curl -H 'X' --data '{\"api_key\": \"%s\"}' x" % SECRET}),
            claude_call("c3", {"command": "export GITHUB_TOKEN=\"%s\" && gh pr list" % SECRET}),
            claude_call("c4", {"command": "PASSWORD='%s' run" % SECRET}),
            codex_call("c5", json.dumps({"password": SECRET, "user": "alex"})),
            codex_call("c6", json.dumps({"cmd": "deploy", "env": {"API_KEY": SECRET}})),
        ]
        calls, _ = done(records)
        self.assertEqual(6, len(calls), calls)
        for call in calls:
            with self.subTest(call=call["call"]):
                self.assertNotIn(SECRET, call["input"])
                self.assertIn("•••", call["input"])

    def test_what_is_not_a_credential_stays_as_given(self):
        calls, _ = done([claude_call("c1", {"command": "pytest tests/ -k token_count"})])
        self.assertEqual("pytest tests/ -k token_count", calls[0]["input"])


SESSION = "delivery-author-af-wisp-x"
TRACKER = [
    {"id": "af-c", "issue_type": "convoy", "status": "open", "title": "Notes", "created_at": "2026-10-19T10:00:00Z",
     "metadata": {"gc.flow.mark": "new-flow/v1", "gc.graph_digest": "sha256:g"}},
    {"id": "af-t", "issue_type": "task", "status": "open", "title": "N1 — Recherche",
     "created_at": "2026-10-19T10:00:00Z",
     "metadata": {"gc.flow.mark": "new-flow/v1", "gc.graph_digest": "sha256:g", "gc.ticket_id": "N1"}},
    {"id": "af-w-in", "issue_type": "convoy", "status": "open", "created_at": "2026-10-19T10:01:00Z",
     "metadata": {"gc.synthetic": "true"},
     "dependencies": [{"issue_id": "af-w-in", "depends_on_id": "af-t", "type": "tracks"}]},
    {"id": "af-w", "issue_type": "task", "status": "in_progress", "title": "mol-ticket-author",
     "created_at": "2026-10-19T10:01:00Z",
     "metadata": {"gc.kind": "workflow", "gc.formula_name": "mol-ticket-author", "gc.input_convoy_id": "af-w-in",
                  "gc.routed_to": "delivery-author"}},
    {"id": "af-w-s", "issue_type": "task", "status": "closed", "title": "implement",
     "created_at": "2026-10-19T10:01:00Z", "closed_at": "2026-10-19T10:03:00Z",
     "metadata": {"gc.kind": "ralph", "gc.root_bead_id": "af-w", "gc.step_id": "implement", "gc.outcome": "pass"}},
    {"id": "af-w-s-1", "issue_type": "task", "status": "closed", "title": "implement",
     "created_at": "2026-10-19T10:01:00Z", "closed_at": "2026-10-19T10:03:00Z",
     "metadata": {"gc.logical_bead_id": "af-w-s", "gc.root_bead_id": "af-w", "gc.attempt": "1",
                  "gc.session_id": "af-wisp-x", "gc.session_name": SESSION,
                  "gc.claimed_at": "2026-10-19T10:01:00Z", "gc.outcome": "pass"}},
]


def usage_of_the_job(counted_at):
    """The usage of the job af-w-s, worked from 10:01 to 10:03 by one
    session, stopped at 10:05, whose provider counted at `counted_at`."""
    trace = {SESSION: {"session": SESSION, "agent_name": "delivery-author", "provider": "codex",
                       "created_at": "2026-10-19T09:50:00Z", "beads": ["af-w-s-1"], "calls": [], "prompts": [],
                       "tools": [], "ended_at": ts("2026-10-19T10:05:00Z"),
                       "usage": [{"at": ts(at), "provider": "codex", "counts": {"input": n, "output": n, "total": 2 * n}}
                                 for n, at in enumerate(counted_at, start=100)]}}
    run = next(r for r in workflow_runs(TRACKER, [], ts("2026-10-19T11:00:00Z"), trace=trace) if r["id"] == "af-c")
    return next(item["usage"] for item in run["items"] if item.get("usage") is not None)


class JobUsage(unittest.TestCase):
    def test_a_stopped_session_with_no_counter_within_the_job_leaves_its_usage_missing_not_zero(self):
        for case, counted_at in (("before", ["2026-10-19T09:55:00Z"]), ("after", ["2026-10-19T10:04:00Z"]),
                                 ("around", ["2026-10-19T09:55:00Z", "2026-10-19T10:04:00Z"])):
            with self.subTest(counted=case):
                usage = usage_of_the_job(counted_at)
                self.assertEqual([{"name": SESSION, "total": None, "running": False}], usage["sessions"])
                self.assertFalse(usage["complete"])
                self.assertEqual({}, usage["providers"])

    def test_a_counter_within_the_job_counts_what_the_session_used_since_the_job_began(self):
        usage = usage_of_the_job(["2026-10-19T09:55:00Z", "2026-10-19T10:02:00Z"])
        self.assertEqual([{"name": SESSION, "total": 2, "running": False}], usage["sessions"])
        self.assertTrue(usage["complete"])
        self.assertEqual({"codex": {"input": 1, "output": 1, "total": 2}}, usage["providers"])


if __name__ == "__main__":
    unittest.main()
