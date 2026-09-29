#!/usr/bin/env python3
"""P13 (af-6675l): sessions wake only for claimable work; resolved
mail-reply beads close themselves. Exercises bin/mail-reply-reap against a
fake `bd` (tests/fixtures/mail-reply-reap/bd) -- no live city, no real gc/bd."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "mail-reply-reap"
FAKE_BD = ROOT / "tests" / "fixtures" / "mail-reply-reap" / "bd"

RESOLVED_MESSAGE = {
    "id": "af-wisp-y0cdyzb",
    "issue_type": "message",
    "status": "open",
    "assignee": "af-driu0",
    "description": (
        "ACTION: verified af-oihx already closed\n"
        "STATE: RESOLVED (stale escalation, no action needed)\n"
        "EVIDENCE: af-oihx (closed)\n"
        "NEXT: none — nothing further to do"
    ),
}

UNRESOLVED_MESSAGE = {
    "id": "af-wisp-sjupj8r",
    "issue_type": "message",
    "status": "open",
    "assignee": "mayor",
    "description": (
        "ACTION: pr-autopilot reconciled af-prmyy via PR #294\n"
        "STATE: SHIPPED\n"
        "EVIDENCE: PR #294\n"
        "NEXT: Mayor advances or finalizes work waiting on af-prmyy."
    ),
}

CLAIMABLE_TICKET = {"id": "af-realwork", "issue_type": "task", "status": "open", "assignee": "af-driu0"}


class MailReplyReapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mail-reply-reap-test-"))
        self.close_log = self.tmp / "close.log"

    def run_tool(self, *args, messages=None, assigned_map=None, check=True):
        env = {
            **os.environ,
            "BD_BIN": str(FAKE_BD),
            "MAIL_TEST_MESSAGES": json.dumps(messages if messages is not None else []),
            "MAIL_TEST_ASSIGNED_MAP": json.dumps(assigned_map or {}),
            "MAIL_TEST_CLOSE_LOG": str(self.close_log),
        }
        return subprocess.run(
            (str(TOOL), "--repo-root", str(self.tmp), *args),
            env=env, text=True, capture_output=True,
        )

    def closes(self):
        if not self.close_log.exists():
            return []
        return [json.loads(line) for line in self.close_log.read_text(encoding="utf-8").splitlines()]

    # -- sweep: a resolved mail-reply bead closes itself --------------------

    def test_sweep_closes_a_resolved_mail_reply_bead(self):
        proc = self.run_tool("sweep", messages=[RESOLVED_MESSAGE])
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(["af-wisp-y0cdyzb"], result["closed"])
        closes = self.closes()
        self.assertEqual(1, len(closes))
        self.assertEqual("af-wisp-y0cdyzb", closes[0]["id"])

    def test_sweep_leaves_an_unresolved_mail_reply_bead_open(self):
        proc = self.run_tool("sweep", messages=[UNRESOLVED_MESSAGE])
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual([], result["closed"])
        self.assertEqual(1, result["skipped"])
        self.assertEqual([], self.closes())

    def test_sweep_dry_run_reports_without_closing(self):
        proc = self.run_tool("sweep", "--dry-run", messages=[RESOLVED_MESSAGE])
        self.assertEqual(0, proc.returncode)
        self.assertEqual([], self.closes())

    def test_sweep_dry_run_exits_nonzero_when_nothing_to_close(self):
        proc = self.run_tool("sweep", "--dry-run", messages=[UNRESOLVED_MESSAGE])
        self.assertEqual(1, proc.returncode)

    # -- should-wake: message-type beads never count, real work always does -

    def test_assigned_message_type_bead_does_not_wake_a_session(self):
        proc = self.run_tool(
            "should-wake", "--assignee", "af-driu0",
            assigned_map={"af-driu0": []},  # bd list without --include-infra hides message beads
        )
        self.assertEqual(1, proc.returncode)
        result = json.loads(proc.stdout)
        self.assertFalse(result["should_wake"])
        self.assertEqual(0, result["claimable_count"])

    def test_a_real_claimable_ticket_still_wakes_its_worker(self):
        proc = self.run_tool(
            "should-wake", "--assignee", "af-driu0",
            assigned_map={"af-driu0": [CLAIMABLE_TICKET]},
        )
        self.assertEqual(0, proc.returncode)
        result = json.loads(proc.stdout)
        self.assertTrue(result["should_wake"])
        self.assertEqual(1, result["claimable_count"])


if __name__ == "__main__":
    unittest.main()
