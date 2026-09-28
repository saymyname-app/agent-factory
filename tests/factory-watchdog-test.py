#!/usr/bin/env python3
"""Rules of lib/factory_watchdog.py that the shell integration test does not reach."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from factory_watchdog import (  # noqa: E402
    assess_gate,
    assess_gh_auth,
    assess_pr,
    assess_quarantine,
    assess_workflow,
)

NOW = 1789555200.0  # 2026-09-16T10:40:00Z


class GateRules(unittest.TestCase):
    def test_a_fresh_human_gate_is_not_yet_an_alarm(self):
        gate = {
            "id": "af-oihx", "status": "open", "await_type": "human",
            "created_at": "2026-09-16T10:25:00Z",  # 15 min old
        }
        self.assertIsNone(assess_gate(gate, NOW))

    def test_a_human_gate_past_threshold_is_flagged(self):
        gate = {
            "id": "af-oihx", "status": "open", "await_type": "human",
            "created_at": "2026-09-16T09:50:00Z",  # 50 min old
            "description": "Ad-hoc gate blocking af-u8id.4\n\nReason: unread mayor decision",
        }
        code, message = assess_gate(gate, NOW)
        self.assertEqual("aged_human_gate", code)
        self.assertIn("af-oihx", message)
        self.assertIn("50 min", message)

    def test_a_closed_gate_is_never_flagged(self):
        gate = {
            "id": "af-oihx", "status": "closed", "await_type": "human",
            "created_at": "2026-09-16T01:00:00Z",
        }
        self.assertIsNone(assess_gate(gate, NOW))

    def test_a_non_human_gate_is_out_of_scope(self):
        gate = {
            "id": "af-timer1", "status": "open", "await_type": "timer",
            "created_at": "2026-09-16T01:00:00Z",
        }
        self.assertIsNone(assess_gate(gate, NOW))

    def test_the_threshold_is_configurable(self):
        gate = {
            "id": "af-oihx", "status": "open", "await_type": "human",
            "created_at": "2026-09-16T10:20:00Z",  # 20 min old
        }
        self.assertIsNone(assess_gate(gate, NOW, threshold_minutes=30))
        self.assertIsNotNone(assess_gate(gate, NOW, threshold_minutes=10))


class PrRules(unittest.TestCase):
    def test_a_fresh_conflicting_pr_is_not_yet_an_alarm(self):
        pr = {
            "number": 57, "isDraft": False, "mergeStateStatus": "CONFLICTING",
            "statusCheckRollup": [], "createdAt": "2026-09-16T10:20:00Z",  # 20 min
        }
        self.assertIsNone(assess_pr(pr, NOW))

    def test_a_conflicting_pr_past_threshold_is_flagged(self):
        pr = {
            "number": 57, "isDraft": False, "mergeStateStatus": "CONFLICTING",
            "statusCheckRollup": [{"conclusion": "SUCCESS"}],
            "createdAt": "2026-09-16T09:00:00Z",  # 100 min
        }
        num, code, message = ("57",) + assess_pr(pr, NOW)
        self.assertEqual("pr_conflicting", code)
        self.assertIn("#57", message)

    def test_a_pr_that_never_ran_ci_is_flagged_distinctly(self):
        pr = {
            "number": 57, "isDraft": False, "mergeStateStatus": "CLEAN",
            "statusCheckRollup": [], "createdAt": "2026-09-16T09:00:00Z",  # 100 min
        }
        code, message = assess_pr(pr, NOW)
        self.assertEqual("pr_no_ci", code)

    def test_a_pr_waiting_its_turn_with_green_checks_is_not_flagged(self):
        pr = {
            "number": 60, "isDraft": False, "mergeStateStatus": "BEHIND",
            "statusCheckRollup": [{"conclusion": "SUCCESS"}],
            "createdAt": "2026-09-16T09:00:00Z",  # 100 min
        }
        self.assertIsNone(assess_pr(pr, NOW))

    def test_a_draft_pr_is_out_of_scope(self):
        pr = {
            "number": 61, "isDraft": True, "mergeStateStatus": "CONFLICTING",
            "statusCheckRollup": [], "createdAt": "2026-09-16T09:00:00Z",
        }
        self.assertIsNone(assess_pr(pr, NOW))


class WorkflowRules(unittest.TestCase):
    def test_a_workflow_that_closed_pass_is_a_real_success(self):
        bead = {
            "id": "af-sbmf", "status": "closed",
            "metadata": {"gc.kind": "workflow", "gc.outcome": "pass"},
        }
        self.assertIsNone(assess_workflow(bead))

    def test_a_workflow_closed_with_a_fail_outcome_is_a_false_success(self):
        bead = {
            "id": "af-g7ts", "status": "closed", "title": "mol-scoped-work",
            "metadata": {"gc.kind": "workflow", "gc.outcome": "fail"},
        }
        code, message = assess_workflow(bead)
        self.assertEqual("false_success_close", code)
        self.assertIn("af-g7ts", message)
        self.assertIn("gc.outcome=fail", message)

    def test_a_non_workflow_bead_is_out_of_scope(self):
        bead = {
            "id": "af-x1", "status": "closed",
            "metadata": {"gc.kind": "step", "gc.outcome": "fail"},
        }
        self.assertIsNone(assess_workflow(bead))

    def test_an_open_workflow_is_not_yet_a_close_at_all(self):
        bead = {
            "id": "af-x2", "status": "open",
            "metadata": {"gc.kind": "workflow", "gc.outcome": "fail"},
        }
        self.assertIsNone(assess_workflow(bead))

    def test_a_workflow_with_no_outcome_recorded_yet_is_not_flagged(self):
        bead = {
            "id": "af-x3", "status": "closed",
            "metadata": {"gc.kind": "workflow"},
        }
        self.assertIsNone(assess_workflow(bead))


class GhAuthRules(unittest.TestCase):
    def test_a_healthy_gh_auth_is_not_flagged(self):
        self.assertIsNone(assess_gh_auth(0, "Logged in to github.com account benjamin-hurand"))

    def test_a_failing_gh_auth_is_flagged(self):
        code, message = assess_gh_auth(1, "You are not logged into any GitHub hosts")
        self.assertEqual("gh_auth_unreachable", code)
        self.assertIn("exit 1", message)
        self.assertIn("not logged into any GitHub hosts", message)

    def test_a_long_gh_auth_message_is_truncated(self):
        _, message = assess_gh_auth(1, "x" * 500)
        self.assertLessEqual(len(message), 200)


def _quarantined_bead(bead_id, reason, quarantined_at, error="controller error"):
    return {
        "id": bead_id,
        "metadata": {
            "gc.control_quarantined": True,
            "gc.control_quarantined_at": quarantined_at,
            "gc.failure_reason": reason,
            "gc.controller_error": error,
        },
    }


class QuarantineRules(unittest.TestCase):
    """af-uxz57: 126 gc:control-quarantined beads with the same failure_reason
    over 8 days raised zero signal. assess_quarantine groups by (rig,
    failure_reason) over a rolling window instead of alerting per bead.
    """

    def test_a_single_quarantine_in_window_is_flagged(self):
        beads = [_quarantined_bead("smb-1", "control_dispatch_error", "2026-09-16T10:00:00Z")]
        verdicts = assess_quarantine(beads, "saymyname-backend", NOW)
        self.assertEqual(1, len(verdicts))
        reason, code, message = verdicts[0]
        self.assertEqual("control_dispatch_error", reason)
        self.assertEqual("control_quarantined", code)
        self.assertIn("1 control step(s)", message)
        self.assertIn("saymyname-backend", message)

    def test_a_non_quarantined_bead_is_ignored(self):
        beads = [{"id": "smb-1", "metadata": {"gc.failure_reason": "control_dispatch_error"}}]
        self.assertEqual([], assess_quarantine(beads, "saymyname-backend", NOW))

    def test_a_quarantine_outside_the_window_is_not_counted(self):
        beads = [_quarantined_bead("smb-1", "control_dispatch_error", "2026-09-01T00:00:00Z")]
        self.assertEqual([], assess_quarantine(beads, "saymyname-backend", NOW, window_hours=24))

    def test_different_failure_reasons_produce_separate_groups(self):
        beads = [
            _quarantined_bead("smb-1", "control_dispatch_error", "2026-09-16T10:00:00Z"),
            _quarantined_bead("smb-2", "timeout", "2026-09-16T10:05:00Z"),
        ]
        verdicts = assess_quarantine(beads, "saymyname-backend", NOW)
        self.assertEqual({"control_dispatch_error", "timeout"}, {v[0] for v in verdicts})

    def test_message_names_the_first_controller_error_by_time_not_input_order(self):
        beads = [
            _quarantined_bead("smb-2", "control_dispatch_error", "2026-09-16T10:20:00Z", error="second error"),
            _quarantined_bead("smb-1", "control_dispatch_error", "2026-09-16T10:00:00Z", error="first error"),
        ]
        verdicts = assess_quarantine(beads, "saymyname-backend", NOW)
        self.assertEqual(1, len(verdicts))
        self.assertIn("first error", verdicts[0][2])
        self.assertNotIn("second error", verdicts[0][2])

    def test_67_in_8_days_pattern_produces_one_alert_not_67(self):
        beads = [
            _quarantined_bead(f"smb-{i}", "control_dispatch_error", "2026-09-16T09:00:00Z",
                               error="resolving gate condition path: lstat .../.gc/scripts: no such file or directory")
            for i in range(67)
        ]
        verdicts = assess_quarantine(beads, "saymyname-backend", NOW)
        self.assertEqual(1, len(verdicts))
        self.assertIn("67 control step(s)", verdicts[0][2])


class Cli(unittest.TestCase):
    def _run(self, subcommand: str, payload: str) -> list[str]:
        result = subprocess.run(
            [sys.executable, str(ROOT / "lib" / "factory_watchdog.py"), subcommand],
            input=payload, capture_output=True, text=True,
            env={**os.environ, "FACTORY_GUARD_NOW": str(NOW)},
        )
        return [line for line in result.stdout.strip().split("\n") if line]

    def test_gates_cli_prints_one_line_per_aged_gate(self):
        gates = [
            {"id": "af-fresh", "status": "open", "await_type": "human",
             "created_at": "2026-09-16T10:35:00Z"},
            {"id": "af-aged", "status": "open", "await_type": "human",
             "created_at": "2026-09-16T09:00:00Z"},
        ]
        lines = self._run("gates", json.dumps(gates))
        self.assertEqual(1, len(lines))
        self.assertTrue(lines[0].startswith("af-aged\taged_human_gate\t"))

    def test_workflows_cli_prints_nothing_when_all_passed(self):
        beads = [{"id": "af-1", "status": "closed",
                  "metadata": {"gc.kind": "workflow", "gc.outcome": "pass"}}]
        self.assertEqual([], self._run("workflows", json.dumps(beads)))

    def test_an_empty_array_is_silent_not_an_error(self):
        self.assertEqual([], self._run("gates", "[]"))
        self.assertEqual([], self._run("prs", "[]"))
        self.assertEqual([], self._run("workflows", "[]"))

    def test_gh_auth_cli_is_silent_when_healthy(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "lib" / "factory_watchdog.py"), "gh-auth", "0"],
            input="Logged in to github.com", capture_output=True, text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stdout.strip())

    def test_gh_auth_cli_prints_one_line_when_failing(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "lib" / "factory_watchdog.py"), "gh-auth", "1"],
            input="You are not logged into any GitHub hosts", capture_output=True, text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(result.stdout.strip().startswith("gh_auth_unreachable\t"))

    def test_quarantine_cli_is_silent_when_nothing_in_window(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "lib" / "factory_watchdog.py"), "quarantine", "saymyname-backend"],
            input="[]", capture_output=True, text=True,
            env={**os.environ, "FACTORY_GUARD_NOW": str(NOW)},
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("", result.stdout.strip())

    def test_quarantine_cli_prints_one_line_per_group(self):
        beads = [
            {"id": f"smb-{i}", "metadata": {
                "gc.control_quarantined": True,
                "gc.control_quarantined_at": "2026-09-16T09:00:00Z",
                "gc.failure_reason": "control_dispatch_error",
                "gc.controller_error": "lstat .../.gc/scripts: no such file or directory",
            }}
            for i in range(67)
        ]
        result = subprocess.run(
            [sys.executable, str(ROOT / "lib" / "factory_watchdog.py"), "quarantine", "saymyname-backend"],
            input=json.dumps(beads), capture_output=True, text=True,
            env={**os.environ, "FACTORY_GUARD_NOW": str(NOW)},
        )
        self.assertEqual(0, result.returncode, result.stderr)
        lines = [line for line in result.stdout.strip().split("\n") if line]
        self.assertEqual(1, len(lines))
        self.assertTrue(lines[0].startswith("control_dispatch_error\tcontrol_quarantined\t"))
        self.assertIn("67 control step(s)", lines[0])


if __name__ == "__main__":
    unittest.main(verbosity=1)
