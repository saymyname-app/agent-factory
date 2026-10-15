#!/usr/bin/env python3
"""bin/convoy-graph on a fake `gc` (tracker list and session list): which
sessions count as active, which tickets are ready, the critical path and the
width per level of the work left, and that nothing is written."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEW = ROOT / "bin" / "convoy-graph"

FAKE_GC = '''#!/usr/bin/env python3
import json, os, sys
argv = sys.argv[1:]
with open(os.environ["FAKE_GC_LOG"], "a") as log:
    log.write(json.dumps(argv) + "\\n")
if argv[:2] == ["--city", os.environ["CONVOY_GRAPH_CITY"]]:
    argv = argv[2:]
if argv[:2] == ["bd", "list"]:
    print(open(os.environ["FAKE_GC_BEADS"]).read())
elif argv[:2] == ["session", "list"]:
    print(open(os.environ["FAKE_GC_SESSIONS"]).read())
else:
    sys.exit("unexpected: " + " ".join(argv))
'''


def ticket(bead_id, key, blocked_by="", status="open", **metadata):
    return {"id": bead_id, "title": f"{key} — titre", "issue_type": "task", "status": status, "metadata": {
        "gc.spec_id": "spec-1", "gc.plane": "delivery", "gc.ticket_id": key, "gc.blocked_by": blocked_by,
        **metadata}}


GATE = '{"at":"2026-10-15T18:05:32Z"}'


class ConvoyGraphTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="convoy-graph-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        gc = self.tmp / "gc"
        gc.write_text(FAKE_GC)
        gc.chmod(0o755)
        self.log = self.tmp / "gc.log"
        self.env = {**os.environ, "GC_BIN": str(gc), "CONVOY_GRAPH_CITY": str(self.tmp), "FAKE_GC_LOG": str(self.log),
                    "FAKE_GC_BEADS": str(self.tmp / "beads.json"), "FAKE_GC_SESSIONS": str(self.tmp / "sessions.json")}
        # T1 delivered; T2 started by a session still active; T3 started by
        # a session gone; T4 and T5 wait for T2 only; T6 waits for T4 and
        # T5; T7 waits for a withdrawn ticket; T8 for a key nobody carries;
        # T9 finished, not merged yet.
        self.beads = [
            {"id": "cv-1", "title": "Convoi", "issue_type": "convoy", "status": "open",
             "metadata": {"gc.spec_id": "spec-1"}},
            ticket("af-1", "T1", status="closed"),
            ticket("af-2", "T2", "T1", status="in_progress", **{
                "gc.flow.gate.dispatch": GATE, "gc.flow.session": '{"at":"x","name":"author-a"}'}),
            ticket("af-3", "T3", **{"gc.flow.gate.dispatch": GATE, "gc.flow.session": '{"at":"x","name":"author-gone"}'}),
            ticket("af-4", "T4", "T2"),
            ticket("af-5", "T5", "T2,T1"),
            ticket("af-6", "T6", "T4,T5"),
            ticket("af-7", "T7", "TW"),
            ticket("af-w", "TW", status="closed", **{"gc.flow.gate.withdrawn": GATE}),
            ticket("af-8", "T8", "TX"),
            ticket("af-9", "T9", status="in_progress", **{
                "gc.flow.gate.dispatch": GATE, "gc.flow.exit": '{"at":"x","exit":"finished"}'}),
        ]
        self.sessions = {"ok": True, "sessions": [
            {"id": "s-1", "name": "author-a", "template": "delivery-author", "state": "active", "closed": False},
            {"id": "s-2", "name": "mayor", "template": "mayor", "state": "active", "closed": False},
            {"id": "s-3", "name": "author-old", "template": "delivery-author", "state": "suspended", "closed": False},
        ]}

    def run_view(self, *extra):
        (self.tmp / "beads.json").write_text(json.dumps(self.beads))
        (self.tmp / "sessions.json").write_text(json.dumps(self.sessions))
        return subprocess.run((str(VIEW), "spec-1", *extra), env=self.env, text=True, capture_output=True)

    def shown(self):
        proc = self.run_view("--json")
        self.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)

    def test_active_sessions_come_from_session_list_and_name_their_ticket(self):
        sessions = {s["name"]: s["ticket"] for s in self.shown()["sessions"]}
        self.assertEqual({"author-a": "T2", "mayor": None}, sessions)

    def test_ready_tickets_wait_for_nothing_left_and_were_never_started(self):
        # T7: its blocker is withdrawn. T3 is started, T8 waits for an unknown key.
        state = self.shown()
        self.assertEqual(["T7"], [t["key"] for t in state["ready"]])
        self.assertEqual({"T8": ["TX"]}, state["unknown_blockers"])

    def test_running_tickets_say_whether_their_session_is_active(self):
        running = {t["key"]: t["session_active"] for t in self.shown()["running"]}
        self.assertEqual({"T2": True, "T3": False}, running)
        self.assertEqual(["T9"], [t["key"] for t in self.shown()["finished_unmerged"]])

    def test_critical_path_and_width_per_level_of_the_work_left(self):
        state = self.shown()
        self.assertEqual({"length": 3, "chain": ["T2", "T4", "T6"]}, state["critical_path"])
        self.assertEqual({"1": 5, "2": 2, "3": 1}, state["width_per_level"])
        self.assertEqual({"tickets": 9, "delivered": 1, "withdrawn": 1, "left": 8}, state["counts"])

    def test_text_names_sessions_ready_tickets_and_the_critical_path(self):
        proc = self.run_view()
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertIn("Sessions actives (gc session list) : 2", proc.stdout)
        self.assertIn("  T7  af-7", proc.stdout)
        self.assertIn("session author-gone (pas active)", proc.stdout)
        self.assertIn("Chemin critique du reste : 3 — T2 → T4 → T6", proc.stdout)
        self.assertIn("Largeur par niveau : 1:5  2:2  3:1", proc.stdout)

    def test_reads_only(self):
        self.shown()
        calls = [json.loads(line)[2:] for line in self.log.read_text().splitlines()]
        self.assertEqual([["bd", "list"], ["session", "list"]], [call[:2] for call in calls])

    def test_a_spec_without_tickets_is_refused(self):
        self.beads = []
        proc = self.run_view()
        self.assertEqual(1, proc.returncode)
        self.assertIn("aucun ticket ne porte gc.spec_id=spec-1", proc.stderr)


if __name__ == "__main__":
    unittest.main()
