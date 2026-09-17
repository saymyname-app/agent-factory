#!/usr/bin/env python3
"""Rules of lib/ntfy_notify.py: which cockpit findings page Benjamin's phone."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from ntfy_notify import compute_alerts, diff_alerts  # noqa: E402

CLEAR_SNAPSHOT = {
    "human_state": {
        "needs_benjamin": None,
        "resume": {"required": False, "mode": "mayor_finalization"},
        "campaign": {"blocked": False},
    },
    "needs_benjamin": None,
    "warnings": [],
}


class ComputeAlertsRules(unittest.TestCase):
    def test_a_clear_snapshot_pages_nobody(self):
        self.assertEqual([], compute_alerts(CLEAR_SNAPSHOT))

    def test_needs_benjamin_is_urgent(self):
        snapshot = {
            **CLEAR_SNAPSHOT,
            "human_state": {**CLEAR_SNAPSHOT["human_state"], "needs_benjamin": "Choisir le contrat"},
        }
        alerts = compute_alerts(snapshot)
        self.assertEqual(1, len(alerts))
        self.assertEqual("needs_benjamin", alerts[0]["key"])
        self.assertEqual("urgent", alerts[0]["priority"])
        self.assertIn("Choisir le contrat", alerts[0]["message"])

    def test_top_level_needs_benjamin_is_a_fallback(self):
        snapshot = {**CLEAR_SNAPSHOT, "needs_benjamin": "Decision en attente"}
        alerts = compute_alerts(snapshot)
        self.assertEqual(["needs_benjamin"], [a["key"] for a in alerts])

    def test_a_required_resume_is_urgent_and_keyed_by_mode(self):
        snapshot = {
            **CLEAR_SNAPSHOT,
            "human_state": {
                **CLEAR_SNAPSHOT["human_state"],
                "resume": {"required": True, "mode": "provider_exhausted", "prompt": "Relance manuelle"},
            },
        }
        alerts = compute_alerts(snapshot)
        self.assertEqual(["resume:provider_exhausted"], [a["key"] for a in alerts])
        self.assertEqual("urgent", alerts[0]["priority"])
        self.assertIn("Relance manuelle", alerts[0]["message"])

    def test_admin_or_limit_block_is_not_urgent(self):
        for kind in ("admin", "limit"):
            snapshot = {
                **CLEAR_SNAPSHOT,
                "human_state": {
                    **CLEAR_SNAPSHOT["human_state"],
                    "campaign": {"blocked": True, "blocker_kind": kind, "cause": "maintenance planifiee"},
                },
            }
            alerts = compute_alerts(snapshot)
            self.assertEqual("default", alerts[0]["priority"], kind)

    def test_a_durable_failure_block_is_urgent(self):
        snapshot = {
            **CLEAR_SNAPSHOT,
            "human_state": {
                **CLEAR_SNAPSHOT["human_state"],
                "campaign": {"blocked": True, "blocker_kind": "durable_failure", "cause": "3 echecs consecutifs"},
            },
        }
        alerts = compute_alerts(snapshot)
        self.assertEqual("urgent", alerts[0]["priority"])
        self.assertEqual("campaign_blocked:durable_failure", alerts[0]["key"])

    def test_warnings_become_default_priority_alerts(self):
        snapshot = {**CLEAR_SNAPSHOT, "warnings": ["disque a 92%"]}
        alerts = compute_alerts(snapshot)
        self.assertEqual(["warning:disque a 92%"], [a["key"] for a in alerts])
        self.assertEqual("default", alerts[0]["priority"])

    def test_a_dict_shaped_warning_reads_its_message_field(self):
        snapshot = {**CLEAR_SNAPSHOT, "warnings": [{"message": "provider degrade"}]}
        alerts = compute_alerts(snapshot)
        self.assertIn("provider degrade", alerts[0]["message"])


class DiffAlertsRules(unittest.TestCase):
    def test_a_brand_new_alert_is_due_immediately(self):
        alerts = [{"key": "needs_benjamin", "title": "t", "message": "m", "priority": "urgent"}]
        due, resolved = diff_alerts(alerts, {}, now=1000.0)
        self.assertEqual(alerts, due)
        self.assertEqual([], resolved)

    def test_a_recently_sent_alert_is_not_due_again(self):
        alerts = [{"key": "needs_benjamin", "title": "t", "message": "m", "priority": "urgent"}]
        state = {"needs_benjamin": 1000.0}
        due, resolved = diff_alerts(alerts, state, now=1000.0 + 60, remind_seconds=3600)
        self.assertEqual([], due)
        self.assertEqual([], resolved)

    def test_a_stuck_alert_pages_again_after_the_reminder_window(self):
        """The audit's exact gap: 'the sentinel sends at most 3 reminders then silence'."""
        alerts = [{"key": "needs_benjamin", "title": "t", "message": "m", "priority": "urgent"}]
        state = {"needs_benjamin": 1000.0}
        due, _ = diff_alerts(alerts, state, now=1000.0 + 3600, remind_seconds=3600)
        self.assertEqual(alerts, due)

    def test_a_key_that_stops_appearing_is_reported_resolved(self):
        due, resolved = diff_alerts([], {"needs_benjamin": 1000.0}, now=1000.0 + 60)
        self.assertEqual([], due)
        self.assertEqual(["needs_benjamin"], resolved)


if __name__ == "__main__":
    unittest.main()
