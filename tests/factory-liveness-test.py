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

from factory_liveness import assess  # noqa: E402

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
