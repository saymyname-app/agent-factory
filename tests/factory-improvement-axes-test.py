#!/usr/bin/env python3
"""docs/FACTORY_CONTINUITY.md sec1/sec4, ADR-0016 sec7: the named improvement
axes and the maintain-alive master switch. Pure-logic tests mirror
provider-failover-test.py's Resolution class; the end-to-end class exercises
bin/factory-improvement-axes exactly as the cockpit and mayor-campaign do.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

import factory_improvement_axes as fia  # noqa: E402


def policy(**overrides):
    value = {
        "contract": "factory-improvement-axes/v1",
        "maintain_alive_default": True,
        "axes": [
            {"name": "code-review", "description": "d", "scope_boundary": "s",
             "default_enabled": True, "draft_only": False,
             "mechanism": {"status": "wired", "ref": "skill:code-review"}},
            {"name": "dead-code", "description": "d", "scope_boundary": "s",
             "default_enabled": True, "draft_only": False,
             "mechanism": {"status": "not_implemented"}},
            {"name": "auth-providers", "description": "d", "scope_boundary": "réservée",
             "default_enabled": False, "draft_only": True,
             "mechanism": {"status": "not_implemented"}},
            {"name": "i18n", "description": "d", "scope_boundary": "s",
             "default_enabled": False, "draft_only": False,
             "mechanism": {"status": "not_implemented"}},
        ],
    }
    value.update(overrides)
    return value


class ValidatePolicyTest(unittest.TestCase):
    def test_the_shipped_config_validates(self):
        value = json.loads((ROOT / "config" / "factory-improvement-axes.json").read_text(encoding="utf-8"))
        fia.validate_policy(value)  # must not raise

    def test_wrong_contract_is_rejected(self):
        with self.assertRaises(fia.AxesPolicyError):
            fia.validate_policy({"contract": "x", "maintain_alive_default": True, "axes": [{}]})

    def test_duplicate_axis_names_are_rejected(self):
        value = policy()
        value["axes"].append(dict(value["axes"][0]))
        with self.assertRaises(fia.AxesPolicyError):
            fia.validate_policy(value)

    def test_a_wired_mechanism_requires_a_ref(self):
        value = policy()
        value["axes"][0]["mechanism"] = {"status": "wired"}
        with self.assertRaises(fia.AxesPolicyError):
            fia.validate_policy(value)

    def test_empty_axes_is_rejected(self):
        with self.assertRaises(fia.AxesPolicyError):
            fia.validate_policy(policy(axes=[]))


class NormalizeStateTest(unittest.TestCase):
    def test_a_missing_state_degrades_to_policy_defaults(self):
        state = fia.normalize_state(None, policy())
        self.assertTrue(state["maintain_alive"])
        self.assertEqual(
            {"code-review": True, "dead-code": True, "auth-providers": False, "i18n": False},
            state["axes"],
        )

    def test_a_malformed_state_degrades_to_defaults_not_a_crash(self):
        state = fia.normalize_state("not a dict", policy())
        self.assertTrue(state["maintain_alive"])

    def test_overrides_apply_only_where_present(self):
        state = fia.normalize_state({"maintain_alive": False, "axes": {"i18n": True}}, policy())
        self.assertFalse(state["maintain_alive"])
        self.assertTrue(state["axes"]["i18n"])
        self.assertTrue(state["axes"]["code-review"])  # untouched, falls back to default


class SelectImprovementAxisTest(unittest.TestCase):
    def test_maintain_alive_off_selects_nothing(self):
        state = fia.empty_state(policy())
        state["maintain_alive"] = False
        self.assertIsNone(fia.select_improvement_axis(policy(), state))

    def test_first_enabled_wired_axis_wins(self):
        state = fia.empty_state(policy())
        axis = fia.select_improvement_axis(policy(), state)
        self.assertEqual(("code-review", "dispatch"), (axis["name"], axis["action"]))

    def test_a_disabled_axis_is_never_selected(self):
        state = fia.empty_state(policy())
        state["axes"]["code-review"] = False
        axis = fia.select_improvement_axis(policy(), state)
        # dead-code is enabled but not_implemented (non-draft): skipped as a
        # deliberate no-op, matching the generative rungs' own "if nothing
        # merits it, create nothing" -- nothing left enabled and usable.
        self.assertIsNone(axis)

    def test_a_stub_axis_is_skipped_for_the_next_enabled_one(self):
        state = fia.empty_state(policy())
        state["axes"]["code-review"] = False
        state["axes"]["dead-code"] = False
        state["axes"]["auth-providers"] = True
        axis = fia.select_improvement_axis(policy(), state)
        self.assertEqual(("auth-providers", "propose"), (axis["name"], axis["action"]))

    def test_a_draft_only_axis_never_dispatches(self):
        state = fia.empty_state(policy())
        state["axes"]["code-review"] = False
        state["axes"]["dead-code"] = False
        state["axes"]["auth-providers"] = True
        axis = fia.select_improvement_axis(policy(), state)
        self.assertNotEqual("dispatch", axis["action"])
        self.assertEqual("propose", axis["action"])


class ApplyControlTest(unittest.TestCase):
    def test_maintain_alive_toggle(self):
        state = fia.empty_state(policy())
        fia.apply_control(state, policy(), "maintain-alive", {"enabled": False}, "operator", "2026-09-17T00:00:00Z")
        self.assertFalse(state["maintain_alive"])

    def test_enable_and_disable_an_axis(self):
        state = fia.empty_state(policy())
        fia.apply_control(state, policy(), "enable", {"axis": "i18n"}, "operator", "2026-09-17T00:00:00Z")
        self.assertTrue(state["axes"]["i18n"])
        fia.apply_control(state, policy(), "disable", {"axis": "i18n"}, "operator", "2026-09-17T00:00:00Z")
        self.assertFalse(state["axes"]["i18n"])

    def test_an_unknown_axis_is_rejected(self):
        state = fia.empty_state(policy())
        with self.assertRaises(fia.AxesPolicyError):
            fia.apply_control(state, policy(), "enable", {"axis": "nope"}, "operator", "2026-09-17T00:00:00Z")

    def test_history_is_recorded_and_capped(self):
        state = fia.empty_state(policy())
        for i in range(20):
            fia.apply_control(
                state, policy(), "maintain-alive", {"enabled": i % 2 == 0}, "operator", "2026-09-17T00:00:00Z",
            )
        self.assertEqual(15, len(state["history"]))


class EndToEndCLITest(unittest.TestCase):
    """bin/factory-improvement-axes exactly as the cockpit and mayor-campaign call it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.env = {
            **os.environ,
            "FACTORY_IMPROVEMENT_AXES_POLICY_FILE": str(ROOT / "config" / "factory-improvement-axes.json"),
            "FACTORY_IMPROVEMENT_AXES_STATE_FILE": str(self.d / "state.json"),
            "FACTORY_IMPROVEMENT_AXES_NOW": "1789555200",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def run_tool(self, *args, check=True):
        return subprocess.run(
            [sys.executable, str(ROOT / "bin" / "factory-improvement-axes"), *args],
            env=self.env, text=True, capture_output=True, check=check,
        )

    def test_status_defaults_to_the_policy_and_writes_nothing(self):
        result = self.run_tool("status", "--json")
        payload = json.loads(result.stdout)
        self.assertTrue(payload["maintain_alive"])
        self.assertEqual("code-review", payload["next_selected"]["name"])
        self.assertFalse((self.d / "state.json").exists())

    def test_set_maintain_alive_off_then_status_reflects_it(self):
        self.run_tool("set", "--action", "maintain-alive", "--args", '{"enabled": false}')
        payload = json.loads(self.run_tool("status", "--json").stdout)
        self.assertFalse(payload["maintain_alive"])
        self.assertIsNone(payload["next_selected"])

    def test_disabling_the_default_axis_falls_through_to_the_next_one(self):
        self.run_tool("set", "--action", "disable", "--args", '{"axis": "code-review"}')
        payload = json.loads(self.run_tool("status", "--json").stdout)
        self.assertNotEqual("code-review", (payload["next_selected"] or {}).get("name"))

    def test_a_draft_only_axis_never_produces_a_dispatch_action(self):
        for axis in ("code-review", "dead-code", "ui-ux", "security", "docs-debt"):
            self.run_tool("set", "--action", "disable", "--args", json.dumps({"axis": axis}))
        self.run_tool("set", "--action", "enable", "--args", '{"axis": "auth-providers"}')
        payload = json.loads(self.run_tool("status", "--json").stdout)
        selected = payload["next_selected"]
        # architecture-debt (also draft_only, ahead of auth-providers in
        # policy order) is still enabled by default and wins first -- the
        # acceptance claim under test is that whichever draft_only axis is
        # selected, it is only ever a proposal.
        self.assertIn(selected["name"], {"architecture-debt", "auth-providers", "v2-scope-exploration"})
        self.assertEqual("propose", selected["action"])

    def test_a_malformed_state_file_degrades_to_defaults(self):
        (self.d / "state.json").write_text("not json", encoding="utf-8")
        payload = json.loads(self.run_tool("status", "--json").stdout)
        self.assertTrue(payload["maintain_alive"])

    def test_an_unknown_axis_is_refused(self):
        result = self.run_tool(
            "set", "--action", "enable", "--args", '{"axis": "nope"}', check=False,
        )
        self.assertEqual(2, result.returncode)
        self.assertFalse(json.loads(result.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
