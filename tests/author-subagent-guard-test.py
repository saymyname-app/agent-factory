#!/usr/bin/env python3
"""The sub-agent guard of the author role (T12, af-i3q5a5), by its command
line: one tool call on stdin, as Claude Code gives it to a PreToolUse hook;
exit 0 lets the call through, exit 2 blocks it with the reason on stderr.

Whether a real session loads the guard is not proven here: that is the
adoption trial (bin/role-adoption-trial, role `author`)."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = ROOT / "agents" / "delivery-author" / "overlay" / ".claude"
GUARD = OVERLAY / "guards" / "author-subagent-guard"


def guard(call) -> subprocess.CompletedProcess[str]:
    stdin = call if isinstance(call, str) else json.dumps(call)
    return subprocess.run([str(GUARD)], input=stdin, text=True, capture_output=True)


class AuthorSubagentGuardTest(unittest.TestCase):
    def assertBlocked(self, call, mention="sub-agent"):
        proc = guard(call)
        self.assertEqual(2, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn(mention, proc.stderr)

    def test_a_read_only_sub_agent_passes(self):
        for tool in ("Agent", "Task"):
            for kind in ("Explore", "Plan"):
                proc = guard({"tool_name": tool, "tool_input": {"subagent_type": kind, "prompt": "read"}})
                self.assertEqual(0, proc.returncode, proc.stderr)
                self.assertEqual("", proc.stderr)

    def test_a_sub_agent_that_can_write_is_blocked(self):
        self.assertBlocked({"tool_name": "Agent", "tool_input": {"subagent_type": "general-purpose", "prompt": "write"}})
        self.assertBlocked({"tool_name": "Task", "tool_input": {"subagent_type": "claude", "prompt": "write"}})

    def test_a_sub_agent_with_no_type_is_blocked(self):
        self.assertBlocked({"tool_name": "Agent", "tool_input": {"prompt": "write"}})
        self.assertBlocked({"tool_name": "Agent"})

    def test_a_fork_of_the_session_is_blocked(self):
        self.assertBlocked({"tool_name": "Agent", "tool_input": {"subagent_type": "fork", "prompt": "write"}})

    def test_a_workflow_of_sub_agents_is_blocked(self):
        self.assertBlocked({"tool_name": "Workflow", "tool_input": {"script": "agent('write')"}}, mention="Workflow")

    def test_an_unreadable_call_is_blocked(self):
        self.assertBlocked("not json", mention="unreadable")
        self.assertBlocked("[]", mention="unreadable")

    def test_the_session_settings_run_the_guard_before_every_sub_agent_tool(self):
        hooks = json.loads((OVERLAY / "settings.json").read_text())["hooks"]["PreToolUse"]
        self.assertEqual(1, len(hooks))
        self.assertEqual({"Agent", "Task", "Workflow"}, set(hooks[0]["matcher"].split("|")))
        command = hooks[0]["hooks"][0]["command"]
        self.assertTrue(command.endswith("/.claude/guards/" + GUARD.name), command)
        self.assertTrue(GUARD.is_file() and GUARD.stat().st_mode & 0o111, "the guard is not executable")


if __name__ == "__main__":
    unittest.main()
