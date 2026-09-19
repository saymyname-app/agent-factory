#!/usr/bin/env python3
"""Rules of lib/factory_liveness.py that the guard integration test does not reach."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from factory_liveness import assess, identify_cause, mayor_page_since  # noqa: E402

NOW = 1789555200.0  # 2026-09-16T10:40:00Z


def meta(**extra):
    value = {
        "gc.campaign_mode": "automatic", "gc.campaign_state": "active",
        "gc.campaign_sentinel_at": "2026-09-16T10:39:00Z",
        "gc.campaign_progress_at": "2026-09-16T10:30:00Z",
        "gc.campaign_failure_count": "0",
    }
    value.update(extra)
    return value


class LivenessRules(unittest.TestCase):
    def test_an_inactive_campaign_is_not_expected_to_move(self):
        self.assertEqual("inactive", assess({"gc.campaign_mode": "inactive"}, NOW)[1])

    def test_first_deploy_has_no_heartbeat_and_is_not_an_alarm(self):
        level, code, _ = assess(meta(**{"gc.campaign_sentinel_at": ""}), NOW)
        self.assertEqual(("info", "no_heartbeat"), (level, code))
        level, code, _ = assess(meta(**{"gc.campaign_progress_at": ""}), NOW)
        self.assertEqual(("info", "no_progress_stamp"), (level, code))

    def test_a_campaign_that_never_progresses_is_still_caught(self):
        """The gap found live: 'no progress yet' must not be a permanent excuse."""
        never = meta(**{"gc.campaign_progress_at": "",
                        "gc.campaign_watch_since": "2026-09-16T09:00:00Z"})
        level, code, message = assess(never, NOW)
        self.assertEqual(("bad", "stale"), (level, code))
        self.assertIn("100 min of watching", message)
        recent = meta(**{"gc.campaign_progress_at": "",
                         "gc.campaign_watch_since": "2026-09-16T10:20:00Z"})
        self.assertEqual(("info", "no_progress_stamp"), assess(recent, NOW)[:2])

    def test_recent_result_activity_overrides_a_stale_progress_stamp(self):
        """af-ooob8: gc.campaign_progress_at only refreshes for the three
        transition reasons bin/mayor-campaign's planner recognizes, so a
        phase outside that set (a review sub-session after delivery, say)
        can run for hours without it. The in-flight result bead's own
        heartbeat/update is ground truth that the campaign is not stuck."""
        stale = meta(**{"gc.campaign_progress_at": "2026-09-16T09:10:00Z"})
        current_result = {"metadata": {"gc.last_heartbeat_at": "2026-09-16T10:35:00Z"}}
        level, code, message = assess(stale, NOW, current_result=current_result)
        self.assertEqual(("ok", "active_result"), (level, code))
        self.assertIn("active 5 min ago", message)

        # No recent activity on the result either: still stale.
        cold_result = {"metadata": {"gc.last_heartbeat_at": "2026-09-16T08:00:00Z"}}
        self.assertEqual(("bad", "stale"), assess(stale, NOW, current_result=cold_result)[:2])
        self.assertEqual(("bad", "stale"), assess(stale, NOW, current_result=None)[:2])

    def test_a_delegated_workflows_activity_also_overrides_a_stale_progress_stamp(self):
        """af-py8n1: gc.current can point at a static result bead that
        delegates its real work to a workflow tracked only by a shared
        convoy 'tracks' link (no --parent edge) -- e.g. smf-cgp delegating
        to workflow smf-uzv and its many decomposed/review children. Neither
        the result bead nor the workflow root ever get a heartbeat, but a
        currently open/in_progress step under the workflow does."""
        stale = meta(**{"gc.campaign_progress_at": "2026-09-16T09:10:00Z"})
        cold_result = {"updated_at": "2026-09-16T07:00:00Z", "metadata": {}}
        cold_workflow_root = {"id": "wf1", "updated_at": "2026-09-16T07:05:00Z", "metadata": {}}
        active_step = {"id": "step1", "metadata": {"gc.last_heartbeat_at": "2026-09-16T10:32:00Z"}}

        level, code, message = assess(
            stale, NOW, current_result=cold_result,
            current_workflow=[cold_workflow_root, active_step],
        )
        self.assertEqual(("ok", "active_result"), (level, code))
        self.assertIn("active 8 min ago", message)

        # No recent activity anywhere in the delegated workflow either: still stale.
        cold_step = {"id": "step1", "metadata": {"gc.last_heartbeat_at": "2026-09-16T07:10:00Z"}}
        self.assertEqual(
            ("bad", "stale"),
            assess(stale, NOW, current_result=cold_result,
                   current_workflow=[cold_workflow_root, cold_step])[:2],
        )
        # None found at all (best-effort discovery came up empty): still stale.
        self.assertEqual(
            ("bad", "stale"),
            assess(stale, NOW, current_result=cold_result, current_workflow=[])[:2],
        )
        self.assertEqual(
            ("bad", "stale"),
            assess(stale, NOW, current_result=cold_result, current_workflow=None)[:2],
        )

    def test_stale_heartbeat_is_not_masked_by_an_unrelated_metadata_write(self):
        """af-i64cb: once a result has ever sent a heartbeat, a later bare
        `updated_at` bump (a nudge, an unrelated bookkeeping write) must not
        be trusted as evidence of real progress -- only the heartbeat can
        revive it."""
        stale = meta(**{"gc.campaign_progress_at": "2026-09-16T09:10:00Z"})
        result = {
            "updated_at": "2026-09-16T10:39:00Z",  # 1 min ago: unrelated write
            "metadata": {"gc.last_heartbeat_at": "2026-09-16T08:00:00Z"},  # 2h40m ago: stale
        }
        self.assertEqual(("bad", "stale"), assess(stale, NOW, current_result=result)[:2])

    def test_updated_at_still_covers_a_result_that_never_heartbeat(self):
        """A result whose code never stamps gc.last_heartbeat_at at all still
        needs the updated_at fallback, or af-ooob8's original gap reopens."""
        stale = meta(**{"gc.campaign_progress_at": "2026-09-16T09:10:00Z"})
        result = {"updated_at": "2026-09-16T10:35:00Z", "metadata": {}}
        level, code, _ = assess(stale, NOW, current_result=result)
        self.assertEqual(("ok", "active_result"), (level, code))

    def test_a_pending_product_decision_still_expects_factory_progress(self):
        """ADR-0016 s.4: a decision parks product work, never the factory."""
        stalled = meta(**{
            "gc.campaign_state": "blocked", "gc.campaign_block_kind": "decision",
            "gc.campaign_cause": "Choix de périmètre",
            "gc.campaign_progress_at": "2026-09-16T08:00:00Z",
        })
        self.assertEqual(("bad", "stale"), assess(stalled, NOW)[:2])

    def test_a_limit_pause_is_deliberate(self):
        paused = meta(**{
            "gc.campaign_state": "blocked", "gc.campaign_block_kind": "limit",
            "gc.campaign_cause": "Tous les fournisseurs épuisés",
            "gc.campaign_progress_at": "2026-09-15T00:00:00Z",
        })
        self.assertEqual(("info", "paused"), assess(paused, NOW)[:2])

    def test_a_silent_loop_outranks_everything_else(self):
        """A dead sentinel cannot record a pause either, so it is checked first."""
        dead = meta(**{
            "gc.campaign_sentinel_at": "2026-09-16T09:00:00Z",
            "gc.campaign_state": "blocked", "gc.campaign_block_kind": "admin",
            "gc.campaign_cause": "Fenêtre",
        })
        self.assertEqual(("bad", "silent"), assess(dead, NOW)[:2])

    def test_transient_sentinel_failures_are_surfaced_without_alarm(self):
        level, code, message = assess(meta(**{
            "gc.campaign_failure_count": "2", "gc.campaign_last_error": "queue lock timeout",
        }), NOW)
        self.assertEqual(("ok", "ok"), (level, code))
        self.assertIn("2/3 consecutive sentinel failures: queue lock timeout", message)

    def test_the_threshold_is_configurable(self):
        forty_min = meta(**{"gc.campaign_progress_at": "2026-09-16T10:00:00Z"})
        self.assertEqual("ok", assess(forty_min, NOW)[1])
        self.assertEqual("stale", assess(forty_min, NOW, liveness_minutes=30)[1])

    def test_stale_names_no_provider_available_as_the_cause(self):
        """af-9ur0s / af-umyad: replay of 2026-09-18 03:21Z-08:30Z, where the
        anthropic pool was wrongly marked exhausted by DETECTION with no
        stated reset and the mark had stood unrefreshed for hours -- the
        liveness message must say 'aucun fournisseur disponible', and flag
        the mark itself as suspect, not just 'up but not advancing'."""
        stalled = meta(**{"gc.campaign_progress_at": "2026-09-16T05:00:00Z"})  # >5h stale
        provider_status = {
            "targets": {
                "mayor": {
                    "reason": "all_unavailable",
                    "next_reset": None,
                    "chain": [{
                        "provider": "claude-standard", "state": "exhausted",
                        "source": "detected", "reset_known": False,
                        "at": "2026-09-16T00:00:00Z",  # 10h30 before NOW
                        "evidence": "You've hit your session limit",
                    }],
                },
            },
        }
        level, code, message = assess(stalled, NOW, provider_status=provider_status)
        self.assertEqual(("bad", "stale"), (level, code))
        self.assertIn("aucun fournisseur disponible", message)
        self.assertIn("marque suspecte", message)
        self.assertIn("You've hit your session limit", message)

    def test_stale_names_the_mayor_session_as_the_cause_when_a_provider_is_available(self):
        """Second replay leg (af-umyad): pool cleared, Mayor quarantined."""
        stalled = meta(**{"gc.campaign_progress_at": "2026-09-16T05:00:00Z"})
        provider_status = {"targets": {"mayor": {"reason": "preferred"}}}
        mayor_session = {"state": "quarantined", "state_reason": "provider config rejected"}
        level, code, message = assess(
            stalled, NOW, provider_status=provider_status, mayor_session=mayor_session,
        )
        self.assertEqual(("bad", "stale"), (level, code))
        self.assertIn("le Mayor ne démarre pas", message)
        self.assertIn("provider config rejected", message)

    def test_stale_admits_cause_unknown_when_neither_is_proven(self):
        stalled = meta(**{"gc.campaign_progress_at": "2026-09-16T05:00:00Z"})
        level, code, message = assess(stalled, NOW)
        self.assertEqual(("bad", "stale"), (level, code))
        self.assertIn("cause inconnue", message)

    def test_identify_cause_prefers_provider_over_session(self):
        provider_status = {"targets": {"mayor": {"reason": "all_unavailable", "next_reset": None, "chain": []}}}
        mayor_session = {"state": "quarantined"}
        self.assertIn("aucun fournisseur disponible", identify_cause(provider_status, mayor_session, NOW))

    def test_mayor_page_since_only_fires_for_asleep_or_quarantine_past_the_grace_window(self):
        recent = {"state": "quarantined", "last_active": "2026-09-16T10:35:00Z"}  # 5 min ago
        self.assertIsNone(mayor_page_since(recent, NOW))
        overdue = {"state": "quarantined", "last_active": "2026-09-16T10:00:00Z"}  # 40 min ago
        self.assertEqual("2026-09-16T10:00:00Z", mayor_page_since(overdue, NOW))
        active = {"state": "active", "last_active": "2026-09-16T10:00:00Z"}
        self.assertIsNone(mayor_page_since(active, NOW))
        # creating/failed-create already has its own alert (af-jj9u7) -- must
        # not also fire here, or the same event pages twice via two doors.
        booting = {"state": "creating", "last_active": "2026-09-16T10:00:00Z"}
        self.assertIsNone(mayor_page_since(booting, NOW))

    def test_cli_rejects_a_missing_bead_rather_than_calling_it_inactive(self):
        run = lambda payload: subprocess.run(
            [sys.executable, str(ROOT / "lib" / "factory_liveness.py")],
            input=payload, capture_output=True, text=True,
            env={**os.environ, "FACTORY_GUARD_NOW": str(NOW)},
        ).stdout.strip().split("\t")
        self.assertEqual(["bad", "unreadable"], run("[]")[:2])
        self.assertEqual(["bad", "unreadable"], run("not json")[:2])
        self.assertEqual(["ok", "ok"], run(json.dumps([{"id": "af-1vr4", "metadata": meta()}]))[:2])


if __name__ == "__main__":
    unittest.main(verbosity=1)
