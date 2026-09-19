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
    assess_stall_frequency,
    assess_workflow,
    merge_signals,
    stall_frequency,
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


class StallFrequencyRules(unittest.TestCase):
    """Rolling-window BLOCKED_STALLED count over lib/factory_continuity.py's own
    record_transition history (one entry per state *change*, not per tick).
    """

    def test_below_threshold_is_not_flagged(self):
        history = [
            {"state": "DISPATCHING", "since": "2026-09-16T08:00:00Z"},
            {"state": "BLOCKED_STALLED", "since": "2026-09-16T09:00:00Z"},
        ]
        self.assertIsNone(assess_stall_frequency(history, NOW))

    def test_count_reaching_threshold_is_flagged(self):
        history = []
        for hour in range(5):
            history.append({"state": "DISPATCHING", "since": f"2026-09-16T0{hour}:00:00Z"})
            history.append({"state": "BLOCKED_STALLED", "since": f"2026-09-16T0{hour}:30:00Z"})
        verdict = assess_stall_frequency(history, NOW, threshold_count=5)
        self.assertIsNotNone(verdict)
        code, message = verdict
        self.assertEqual("stall_frequency_high", code)
        self.assertIn("5 BLOCKED_STALLED", message)
        self.assertIn("from DISPATCHING", message)

    def test_entries_outside_the_window_are_not_counted(self):
        history = [
            {"state": "DISPATCHING", "since": "2026-09-10T00:00:00Z"},
            {"state": "BLOCKED_STALLED", "since": "2026-09-10T01:00:00Z"},  # 6 days old
        ]
        result = stall_frequency(history, NOW)
        self.assertEqual(0, result["count"])

    def test_first_recorded_entry_with_no_predecessor_is_cause_unknown(self):
        history = [{"state": "BLOCKED_STALLED", "since": "2026-09-16T09:00:00Z"}]
        result = stall_frequency(history, NOW)
        self.assertEqual(1, result["count"])
        self.assertIsNone(result["stalls"][0]["preceding_state"])
        verdict = assess_stall_frequency(history, NOW, threshold_count=1)
        self.assertIn("cause unknown", verdict[1])

    def test_threshold_is_configurable(self):
        history = [
            {"state": "DISPATCHING", "since": "2026-09-16T08:00:00Z"},
            {"state": "BLOCKED_STALLED", "since": "2026-09-16T09:00:00Z"},
        ]
        self.assertIsNone(assess_stall_frequency(history, NOW, threshold_count=2))
        self.assertIsNotNone(assess_stall_frequency(history, NOW, threshold_count=1))


class MergeSignals(unittest.TestCase):
    """factory-watchdog-signals.json has three independently-scheduled writers
    (factory-watchdog, on-order-failed, on-session-stranded -- af-u61xq,
    tests/factory-cockpit-chaos-test.py's header comment, PR #82). A wholesale
    overwrite from one used to erase whatever another just wrote; merge_signals
    must instead read-modify-write, replacing only its own writer's slice.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = str(Path(self._tmp.name) / "factory-watchdog-signals.json")

    def _alerts(self):
        return json.loads(Path(self.path).read_text(encoding="utf-8"))["alerts"]

    def test_two_writers_do_not_clobber_each_other(self):
        merge_signals(self.path, "factory-watchdog", [{"kind": "aged_human_gate", "id": "af-oihx", "message": "gate aged"}])
        merge_signals(self.path, "on-order-failed", [{"kind": "order_failed", "id": "af-new1", "message": "dolt-remotes-patrol failing"}])
        alerts = self._alerts()
        self.assertEqual(2, len(alerts))
        sources = {a["source"] for a in alerts}
        self.assertEqual({"factory-watchdog", "on-order-failed"}, sources)

    def test_a_writer_re_running_replaces_only_its_own_slice(self):
        merge_signals(self.path, "factory-watchdog", [{"kind": "aged_human_gate", "id": "af-oihx", "message": "gate aged 30m"}])
        merge_signals(self.path, "on-session-stranded", [{"kind": "session_stranded", "id": "af-br7i", "message": "reopened af-stuck1"}])
        # factory-watchdog runs again with an updated view (gate resolved, nothing to report)
        merge_signals(self.path, "factory-watchdog", [])
        alerts = self._alerts()
        self.assertEqual(1, len(alerts))
        self.assertEqual("on-session-stranded", alerts[0]["source"])
        self.assertEqual("af-br7i", alerts[0]["id"])

    def test_untagged_legacy_entries_are_dropped_not_kept_forever(self):
        # Pre-dates the "source" tag (2026-09-18, C1): an entry with no
        # source can never be matched by any writer's replace-my-own-slice
        # pass, so it must be swept on the next merge instead of persisting
        # in the cockpit's signal file forever.
        Path(self.path).write_text(json.dumps({
            "generated_at": "2026-09-17T09:38:59Z",
            "alerts": [{"kind": "false_success_close", "id": "af-x4p4", "message": "legacy, no source"}],
        }), encoding="utf-8")
        merge_signals(self.path, "on-order-failed", [{"kind": "order_failed", "id": "af-new1", "message": "m1"}])
        alerts = self._alerts()
        self.assertEqual(1, len(alerts))
        self.assertEqual("af-new1", alerts[0]["id"])

    def test_a_writer_updates_its_own_stale_entry_in_place(self):
        merge_signals(self.path, "factory-watchdog", [{"kind": "aged_human_gate", "id": "af-oihx", "message": "gate aged 30m"}])
        merge_signals(self.path, "factory-watchdog", [{"kind": "aged_human_gate", "id": "af-oihx", "message": "gate aged 60m"}])
        alerts = self._alerts()
        self.assertEqual(1, len(alerts))
        self.assertEqual("gate aged 60m", alerts[0]["message"])

    def test_three_writers_all_survive_in_any_order(self):
        merge_signals(self.path, "on-session-stranded", [{"kind": "session_stranded", "id": "af-br7i", "message": "m1"}])
        merge_signals(self.path, "factory-watchdog", [{"kind": "pr_conflicting", "id": "57", "message": "m2"}])
        merge_signals(self.path, "on-order-failed", [{"kind": "order_failed", "id": "af-new1", "message": "m3"}])
        alerts = self._alerts()
        ids = {a["id"] for a in alerts}
        self.assertEqual({"af-br7i", "57", "af-new1"}, ids)

    def test_a_missing_or_malformed_file_starts_clean(self):
        Path(self.path).write_text("not json", encoding="utf-8")
        merge_signals(self.path, "factory-watchdog", [{"kind": "aged_human_gate", "id": "af-oihx", "message": "m"}])
        self.assertEqual(1, len(self._alerts()))


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

    def test_stall_frequency_cli_is_silent_below_threshold(self):
        history = [
            {"state": "DISPATCHING", "since": "2026-09-16T08:00:00Z"},
            {"state": "BLOCKED_STALLED", "since": "2026-09-16T09:00:00Z"},
        ]
        self.assertEqual([], self._run("stall-frequency", json.dumps(history)))

    def test_stall_frequency_cli_prints_one_line_at_threshold(self):
        history = []
        for hour in range(5):
            history.append({"state": "DISPATCHING", "since": f"2026-09-16T0{hour}:00:00Z"})
            history.append({"state": "BLOCKED_STALLED", "since": f"2026-09-16T0{hour}:30:00Z"})
        result = subprocess.run(
            [sys.executable, str(ROOT / "lib" / "factory_watchdog.py"), "stall-frequency"],
            input=json.dumps(history), capture_output=True, text=True,
            env={**os.environ, "FACTORY_GUARD_NOW": str(NOW), "FACTORY_WATCHDOG_STALL_THRESHOLD": "5"},
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(result.stdout.strip().startswith("stall_frequency_high\t"))

    def test_merge_signals_subcommand_round_trips_through_the_real_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "signals.json")
            for source, alert in (
                ("factory-watchdog", {"kind": "aged_human_gate", "id": "af-oihx", "message": "m1"}),
                ("on-order-failed", {"kind": "order_failed", "id": "af-new1", "message": "m2"}),
            ):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "lib" / "factory_watchdog.py"), "merge-signals", path, source],
                    input=json.dumps([alert]), capture_output=True, text=True,
                )
                self.assertEqual(0, result.returncode, result.stderr)
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(2, len(data["alerts"]))
            self.assertEqual({"factory-watchdog", "on-order-failed"}, {a["source"] for a in data["alerts"]})


if __name__ == "__main__":
    unittest.main(verbosity=1)
