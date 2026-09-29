#!/usr/bin/env python3
"""P16 (af-45knz): bin/overlap-conflict-log records publish-time scope-overlap
edges and PR conflicts to one append-only log, carrying both tickets, their
declared scopes and (for a conflict) the sha; and files exactly one "dynamic
leases" proposal bead the moment undeclared-scope conflicts (declared scopes
that did NOT overlap) reach 3 within the trailing 7-day window -- a declared
overlap never counts toward that threshold.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "overlap-conflict-log"

sys.path.insert(0, str(ROOT / "lib"))
import overlap_conflict_log as ocl  # noqa: E402


FAKE_GC = """#!/usr/bin/env bash
echo "$@" >> "$GC_CALLS_LOG"
echo '{"id":"af-fakeprop"}'
"""


class OverlapConflictLogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.log_path = root / "log.jsonl"
        self.marker_path = root / "marker"
        self.gc_calls_log = root / "gc.log"
        self.gc_calls_log.write_text("", encoding="utf-8")
        fake_gc = root / "gc"
        fake_gc.write_text(FAKE_GC, encoding="utf-8")
        fake_gc.chmod(0o755)
        self.env = {
            **os.environ,
            "GC_BIN": str(fake_gc),
            "GC_CALLS_LOG": str(self.gc_calls_log),
        }

    def invoke(self, *args, now=None, check=True):
        cmd = [sys.executable, str(CLI), "--log-path", str(self.log_path),
               "--marker-path", str(self.marker_path)]
        if now is not None:
            cmd += ["--now", str(now)]
        cmd += list(args)
        return subprocess.run(cmd, env=self.env, text=True, capture_output=True, check=check)

    def entries(self):
        return ocl.load_entries(self.log_path)

    def test_overlap_entry_carries_both_tickets_and_scopes(self):
        self.invoke(
            "record-overlap", "--ticket-a", "P16", "--scope-a", "bin/pr-autopilot",
            "--ticket-b", "P11", "--scope-b", "bin/pr-autopilot,bin/ticket-graph-publish",
            "--digest", "sha256:abc", "--rig", "agent-factory", now=1000,
        )
        entries = self.entries()
        self.assertEqual(1, len(entries))
        entry = entries[0]
        self.assertEqual("overlap", entry["kind"])
        self.assertEqual(("P11", "P16"), (entry["ticket_a"], entry["ticket_b"]))
        self.assertEqual(["bin/pr-autopilot", "bin/ticket-graph-publish"], entry["scope_a"])
        self.assertEqual(["bin/pr-autopilot"], entry["scope_b"])
        self.assertTrue(entry["declared_overlap"])
        self.assertEqual("sha256:abc", entry["digest"])

    def test_overlap_recording_is_idempotent_per_pair_and_digest(self):
        for _ in range(2):
            self.invoke(
                "record-overlap", "--ticket-a", "P16", "--scope-a", "x",
                "--ticket-b", "P11", "--scope-b", "y",
                "--digest", "sha256:abc", "--rig", "agent-factory", now=1000,
            )
        self.assertEqual(1, len(self.entries()))

    def test_conflict_entry_carries_both_tickets_scopes_and_sha(self):
        self.invoke(
            "record-conflict", "--ticket-a", "P20", "--scope-a", "a.txt",
            "--ticket-b", "P21", "--scope-b", "b.txt",
            "--sha", "deadbeef", "--rig", "agent-factory", now=2000,
        )
        entries = self.entries()
        self.assertEqual(1, len(entries))
        entry = entries[0]
        self.assertEqual("conflict", entry["kind"])
        self.assertEqual(("P20", "P21"), (entry["ticket_a"], entry["ticket_b"]))
        self.assertEqual("deadbeef", entry["sha"])
        self.assertFalse(entry["declared_overlap"])

    def test_declared_overlap_conflict_is_flagged_and_never_counted(self):
        self.invoke(
            "record-conflict", "--ticket-a", "P28", "--scope-a", "z.txt",
            "--ticket-b", "P29", "--scope-b", "z.txt",
            "--sha", "sha1", "--rig", "agent-factory", now=2000,
        )
        entry = self.entries()[0]
        self.assertTrue(entry["declared_overlap"])
        self.assertFalse(self.marker_path.exists())
        self.assertEqual("", self.gc_calls_log.read_text(encoding="utf-8"))

    def test_third_undeclared_conflict_in_7_days_files_exactly_one_proposal(self):
        for index, (ticket_a, ticket_b, sha, now) in enumerate([
            ("P20", "P21", "sha1", 1000),
            ("P22", "P23", "sha2", 2000),
            ("P24", "P25", "sha3", 3000),
            ("P26", "P27", "sha4", 4000),
        ]):
            self.invoke(
                "record-conflict", "--ticket-a", ticket_a, "--scope-a", "a.txt",
                "--ticket-b", ticket_b, "--scope-b", "b.txt",
                "--sha", sha, "--rig", "agent-factory", now=now,
            )
        calls = self.gc_calls_log.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(1, len(calls))
        self.assertIn("bd create", calls[0])
        self.assertIn("-l proposal", calls[0])
        self.assertTrue(self.marker_path.exists())

    def test_a_declared_overlap_conflict_does_not_count_toward_the_threshold(self):
        for ticket_a, ticket_b, sha in [("P20", "P21", "sha1"), ("P22", "P23", "sha2")]:
            self.invoke(
                "record-conflict", "--ticket-a", ticket_a, "--scope-a", "a.txt",
                "--ticket-b", ticket_b, "--scope-b", "b.txt",
                "--sha", sha, "--rig", "agent-factory", now=1000,
            )
        # Same declared paths on both sides -> a declared overlap, never counted.
        self.invoke(
            "record-conflict", "--ticket-a", "P24", "--scope-a", "z.txt",
            "--ticket-b", "P25", "--scope-b", "z.txt",
            "--sha", "sha3", "--rig", "agent-factory", now=1000,
        )
        self.assertEqual("", self.gc_calls_log.read_text(encoding="utf-8"))
        self.assertFalse(self.marker_path.exists())

    def test_conflicts_older_than_7_days_fall_out_of_the_window(self):
        self.invoke(
            "record-conflict", "--ticket-a", "P20", "--scope-a", "a.txt",
            "--ticket-b", "P21", "--scope-b", "b.txt",
            "--sha", "sha1", "--rig", "agent-factory", now=0,
        )
        self.invoke(
            "record-conflict", "--ticket-a", "P22", "--scope-a", "a.txt",
            "--ticket-b", "P23", "--scope-b", "b.txt",
            "--sha", "sha2", "--rig", "agent-factory", now=1,
        )
        # 8 days later: the first two entries are outside the trailing window.
        self.invoke(
            "record-conflict", "--ticket-a", "P24", "--scope-a", "a.txt",
            "--ticket-b", "P25", "--scope-b", "b.txt",
            "--sha", "sha3", "--rig", "agent-factory", now=8 * 24 * 3600,
        )
        self.assertEqual("", self.gc_calls_log.read_text(encoding="utf-8"))
        self.assertFalse(self.marker_path.exists())

    def test_report_summarises_the_log(self):
        self.invoke(
            "record-overlap", "--ticket-a", "P16", "--scope-a", "x",
            "--ticket-b", "P11", "--scope-b", "y",
            "--digest", "sha256:abc", "--rig", "agent-factory", now=1000,
        )
        self.invoke(
            "record-conflict", "--ticket-a", "P20", "--scope-a", "a.txt",
            "--ticket-b", "P21", "--scope-b", "b.txt",
            "--sha", "sha1", "--rig", "agent-factory", now=1000,
        )
        result = self.invoke("report", now=1000)
        self.assertIn("entries=2", result.stdout)
        self.assertIn("overlaps=1", result.stdout)
        self.assertIn("conflicts=1", result.stdout)
        self.assertIn("undeclared_conflicts_7d=1", result.stdout)


class OverlapConflictLogLibTest(unittest.TestCase):
    def test_scopes_overlap_matches_glob_either_direction(self):
        self.assertTrue(ocl.scopes_overlap(["bin/foo.py"], ["bin/foo.py"]))
        self.assertTrue(ocl.scopes_overlap(["bin/*.py"], ["bin/foo.py"]))
        self.assertTrue(ocl.scopes_overlap(["bin/foo.py"], ["bin/*.py"]))
        self.assertFalse(ocl.scopes_overlap(["bin/foo.py"], ["bin/bar.py"]))

    def test_parse_scope_splits_and_trims(self):
        self.assertEqual(["a", "b"], ocl.parse_scope(" a , b "))
        self.assertEqual([], ocl.parse_scope(""))
        self.assertEqual([], ocl.parse_scope(None))


if __name__ == "__main__":
    unittest.main()
