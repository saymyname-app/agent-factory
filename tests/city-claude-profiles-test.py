#!/usr/bin/env python3
"""The Claude profiles of city.toml and the provider policy must agree
(af-qgwvgi). Reads the repository's own city.toml, config/provider-policy.json
and config/model-catalog.json; starts nothing.

- Every Claude profile carries the same --disallowedTools list and
  --strict-mcp-config: the three blocks are copies, and one left behind would
  give a role back the tools and the claude.ai connectors the others lost.
- The list never names a tool Factory sessions call.
- city.toml, the policy and the catalog name the same providers: a profile
  deleted from one but still in a fallback chain would stop the city config
  from loading the day the chain reaches it.
"""

import json
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Called by Factory sessions in the 7 days before 2026-10-11 ("Task" is the
# name the CLI lists the Agent tool under).
TOOLS_SESSIONS_CALL = {"Agent", "Task", "Bash", "Edit", "Monitor", "Read", "ScheduleWakeup",
                       "Skill", "TaskStop", "TaskOutput", "ToolSearch", "Write"}
UNATTENDED_TRAPS = {"AskUserQuestion", "EnterPlanMode", "ExitPlanMode"}


def providers():
    return tomllib.loads((ROOT / "city.toml").read_text(encoding="utf-8"))["providers"]


def claude_profiles():
    return {name: p for name, p in providers().items() if p.get("base") == "builtin:claude"}


def disallowed(profile):
    args = profile["args_append"]
    return args[args.index("--disallowedTools") + 1]


class CityClaudeProfilesTest(unittest.TestCase):
    def test_every_claude_profile_carries_the_same_tool_list(self):
        lists = {name: disallowed(p) for name, p in claude_profiles().items()}
        self.assertGreaterEqual(len(lists), 3)
        self.assertEqual(1, len(set(lists.values())), lists)

    def test_every_claude_profile_loads_no_mcp_server(self):
        for name, profile in claude_profiles().items():
            self.assertIn("--strict-mcp-config", profile["args_append"], name)

    def test_the_list_keeps_what_sessions_call_and_drops_the_unattended_traps(self):
        for name, profile in claude_profiles().items():
            names = set(disallowed(profile).split(","))
            self.assertEqual(set(), names & TOOLS_SESSIONS_CALL, name)
            self.assertEqual(UNATTENDED_TRAPS, names & UNATTENDED_TRAPS, name)

    def test_city_policy_and_catalog_name_the_same_providers(self):
        policy = json.loads((ROOT / "config" / "provider-policy.json").read_text(encoding="utf-8"))
        catalog = json.loads((ROOT / "config" / "model-catalog.json").read_text(encoding="utf-8"))
        city = set(providers())
        self.assertEqual(city, set(policy["providers"]))
        self.assertEqual(city, set(catalog["providers"]))
        for target, entry in policy["targets"].items():
            self.assertEqual(set(), set(entry["chain"]) - city, target)


if __name__ == "__main__":
    unittest.main()
