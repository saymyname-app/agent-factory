#!/usr/bin/env python3
"""The Beads history read whole once a day, otherwise only what changed
(af-tdpbg1): lib/beads_history_cache.py.

Each case gives the tool a stand-in read command that records its arguments
and prints the beads of a file the case writes, and a cache of its own. The
cases call the entry function; the last two launch the tool as a real
process, once passing and once refusing.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "lib" / "beads_history_cache.py"
sys.path.insert(0, str(ROOT / "lib"))
import beads_history_cache  # noqa: E402

# Prints the beads of $1, or fails with exit 3 when $1 does not exist;
# appends its own arguments, one call per line, to $2.
STAND_IN = r"""
import json, sys
with open(sys.argv[2], "a") as log:
    log.write(json.dumps(sys.argv[3:]) + "\n")
try:
    sys.stdout.write(open(sys.argv[1]).read())
except OSError:
    sys.exit(3)
"""


class BeadsHistoryCache(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="beads-history-cache-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.cache = self.tmp / "cache" / "rig.json"
        self.answer = self.tmp / "answer.json"
        self.calls = self.tmp / "calls"
        stand_in = self.tmp / "read.py"
        stand_in.write_text(STAND_IN)
        self.command = [sys.executable, str(stand_in), str(self.answer), str(self.calls),
                        "list", "--all", "--limit", "0", "--json"]

    def answer_with(self, beads):
        self.answer.write_text(json.dumps(beads))

    def run_tool(self, *options):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = beads_history_cache.main(["--cache", str(self.cache), *options, "--", *self.command])
        return code, out.getvalue()

    def read_args(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def age_cache(self, full_ago, read_ago):
        cache = json.loads(self.cache.read_text())
        now = time.time()
        cache["full_at"], cache["read_at"] = now - full_ago, now - read_ago
        self.cache.write_text(json.dumps(cache))
        return cache["read_at"]

    def test_without_a_cache_the_history_is_read_whole_and_kept(self):
        self.answer_with([{"id": "af-1", "status": "closed"}, {"id": "af-2", "status": "open"}])
        code, out = self.run_tool()
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), [{"id": "af-1", "status": "closed"}, {"id": "af-2", "status": "open"}])
        self.assertEqual(self.read_args(), [["list", "--all", "--limit", "0", "--json"]])
        self.assertEqual(json.loads(self.cache.read_text())["beads"], json.loads(out))

    def test_a_cache_read_whole_today_is_completed_by_what_changed_since_the_last_read(self):
        self.answer_with([{"id": "af-1", "status": "open"}, {"id": "af-2", "status": "open"}])
        self.run_tool()
        last_read = self.age_cache(full_ago=3600, read_ago=180)
        self.answer_with([{"id": "af-2", "status": "closed"}, {"id": "af-3", "status": "open"}])
        code, out = self.run_tool("--margin", "600")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), [{"id": "af-1", "status": "open"}, {"id": "af-2", "status": "closed"},
                                           {"id": "af-3", "status": "open"}])
        since = beads_history_cache._iso(last_read - 600)
        self.assertEqual(self.read_args()[-1], ["list", "--all", "--limit", "0", "--json", "--updated-after", since])
        self.assertEqual(json.loads(self.cache.read_text())["beads"], json.loads(out))

    def test_a_cache_read_whole_more_than_a_day_ago_is_read_whole_again(self):
        self.answer_with([{"id": "af-1", "status": "open"}, {"id": "af-gone", "status": "closed"}])
        self.run_tool()
        self.age_cache(full_ago=86401, read_ago=180)
        self.answer_with([{"id": "af-1", "status": "closed"}])
        code, out = self.run_tool()
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), [{"id": "af-1", "status": "closed"}])
        self.assertEqual(self.read_args()[-1], ["list", "--all", "--limit", "0", "--json"])

    def test_a_cache_of_another_read_command_is_not_used(self):
        self.answer_with([{"id": "af-1", "status": "open"}])
        self.run_tool()
        self.command[self.command.index("--limit") + 1] = "50"
        code, _ = self.run_tool()
        self.assertEqual(code, 0)
        self.assertEqual(self.read_args()[-1], ["list", "--all", "--limit", "50", "--json"])

    def test_a_failed_read_prints_nothing_leaves_the_cache_and_exits_with_the_read_s_code(self):
        self.answer_with([{"id": "af-1", "status": "open"}])
        self.run_tool()
        kept = self.cache.read_text()
        self.answer.unlink()
        code, out = self.run_tool()
        self.assertEqual(code, 3)
        self.assertEqual(out, "")
        self.assertEqual(self.cache.read_text(), kept)

    def test_a_read_that_prints_no_list_is_a_failure(self):
        self.answer.write_text('{"error": "no store"}')
        code, out = self.run_tool()
        self.assertNotEqual(code, 0)
        self.assertEqual(out, "")
        self.assertFalse(self.cache.exists())

    def test_the_command_line_prints_the_history(self):
        self.answer_with([{"id": "af-1", "status": "open"}])
        proc = subprocess.run([sys.executable, str(TOOL), "--cache", str(self.cache), "--", *self.command],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), [{"id": "af-1", "status": "open"}])

    def test_the_command_line_refuses_a_failed_read(self):
        proc = subprocess.run([sys.executable, str(TOOL), "--cache", str(self.cache), "--", *self.command],
                              capture_output=True, text=True, timeout=60)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")


if __name__ == "__main__":
    unittest.main()
