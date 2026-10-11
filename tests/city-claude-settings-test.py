#!/usr/bin/env python3
"""The city's Claude settings, .claude/settings.json (af-miske8). Reads the
repository's own file; starts nothing.

Gas City merges that file over its own defaults into .gc/settings.json each
time it creates a session, and hands the result to every Claude session of
the city with --settings (gc 1.5.0, internal/hooks: installClaude). A
--settings flag in a profile of city.toml would do nothing: gc appends its
own after args_append and Claude keeps the last one only (measured).

- syncClaudeAiPlugins and syncClaudeAiSkills are false: without them a
  session is listed, on every turn, the skills of the 11 plugins synced from
  the operator's claude.ai account (unity, marketing, design, ...). Measured
  2026-10-11 on Claude CLI 2.1.290, one headless turn in a Factory worktree
  with the flags the Claude profiles get from af-qgwvgi: 26,722 context
  tokens and 145 skills without the two keys, 18,802 and 27 with them. What
  sessions call stays listed: core.gc-*, code-review, security-review. To
  give the plugins back, set syncClaudeAiPlugins to true and measure. The
  three delivery roles hold the same two keys in their own overlay
  (agents/<role>/overlay/.claude/settings.local.json), which their adoption
  trial vouches for.
- enableAllProjectMcpServers is false: gc's default is true, which loads any
  .mcp.json that lands in a checkout (audit 2026-09-17, S1; bin/factory-guard
  reports it). Until this file existed the value lived only in the untracked
  .gc/settings.json.
- No hooks key: Claude Code also reads this file as the project settings of
  any session opened in the repository, so a hook here would run in an
  operator's session too. gc adds its own hooks at projection.
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CityClaudeSettingsTest(unittest.TestCase):
    def setUp(self):
        self.settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))

    def test_sessions_are_not_listed_the_account_plugins_and_skills(self):
        self.assertIs(self.settings.get("syncClaudeAiPlugins"), False)
        self.assertIs(self.settings.get("syncClaudeAiSkills"), False)

    def test_a_checked_out_mcp_json_is_not_loaded(self):
        self.assertIs(self.settings.get("enableAllProjectMcpServers"), False)

    def test_the_file_carries_no_hook(self):
        self.assertNotIn("hooks", self.settings)


if __name__ == "__main__":
    unittest.main()
