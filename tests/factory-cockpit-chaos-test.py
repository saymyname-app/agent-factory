#!/usr/bin/env python3
"""Chaos, as seen by the cockpit (docs/FACTORY_AUDIT_2026-09-17.md section
2.5: "no end-to-end or chaos test (stall, dead order, stuck PR, exhausted
provider, as seen by the cockpit)").

Every failure class already has its own mechanism-level test (liveness
rules, on-order-failed, pr-autopilot-stuck, provider-failover). What none of
them prove is that the cockpit -- the thing a human actually looks at --
correctly reflects each one. This file drives the two real wiring paths a
human-visible signal travels through:

  1. bin/factory-watchdog writes .gc/runtime/factory-watchdog-signals.json;
     the cockpit reads it (_read_watchdog_alerts) and carries it into the
     "Aujourd'hui" projection (_today_projection). A stalled campaign, a
     stuck PR, and an aged gate all travel this same path, tagged by "kind".
  2. bin/provider-failover's own status is read live through ProviderBridge
     (dependency-injected executor here, no live process).

Known gap, not covered here: a chronic order failure (on-order-failed) and a
stranded session (on-session-stranded) file a bead and mail the Mayor
directly -- the actual escalation contract -- but do not yet also write to
the watchdog-signals file, so the cockpit's *additional* passive display
does not show them today. Wiring that in needs a read-modify-write merge on
the shared signal file (three independently-scheduled scripts write it;
factory-watchdog currently overwrites wholesale), which is its own small,
separate change, not bundled into this test file.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from factory_cockpit import _read_watchdog_alerts, _today_projection, ProviderBridge  # noqa: E402


def write_signals(path, alerts):
    path.write_text(json.dumps({"generated_at": "2026-09-17T12:00:00Z", "alerts": alerts}),
                     encoding="utf-8")


class ChaosReachesTheCockpit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.signal_file = Path(self.tmp.name) / "factory-watchdog-signals.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_stalled_campaign_reaches_the_cockpit(self):
        # factory-watchdog relays a liveness defect factory-guard already
        # filed, tagged "liveness", for as long as it stays open.
        write_signals(self.signal_file, [
            {"kind": "liveness", "id": "af-live1",
             "message": "no campaign progress for 90 min while the loop itself is alive"},
        ])
        alerts = _read_watchdog_alerts(self.signal_file)
        projection = _today_projection(None, [], [], watchdog_alerts=alerts)
        self.assertEqual(
            [{"kind": "liveness", "id": "af-live1",
              "message": "no campaign progress for 90 min while the loop itself is alive"}],
            projection["watchdog_alerts"],
        )
        # A local stall signal must never read as the whole campaign stopped
        # (ADR-0016 section 7): today_projection never touches this key from
        # watchdog_alerts, only from gc.needs_benjamin.
        self.assertEqual([], projection["effective_blockers"])

    def test_a_stuck_pr_reaches_the_cockpit(self):
        write_signals(self.signal_file, [
            {"kind": "prs", "id": "57", "message": "PR #57 CONFLICTING for 45 min"},
        ])
        alerts = _read_watchdog_alerts(self.signal_file)
        projection = _today_projection(None, [], [], watchdog_alerts=alerts)
        self.assertEqual("prs", projection["watchdog_alerts"][0]["kind"])
        self.assertIn("57", projection["watchdog_alerts"][0]["message"])

    def test_an_aged_gate_reaches_the_cockpit(self):
        write_signals(self.signal_file, [
            {"kind": "aged_human_gate", "id": "af-oihx", "message": "gate af-oihx open 127 min"},
        ])
        alerts = _read_watchdog_alerts(self.signal_file)
        projection = _today_projection(None, [], [], watchdog_alerts=alerts)
        self.assertEqual("aged_human_gate", projection["watchdog_alerts"][0]["kind"])

    def test_several_simultaneous_findings_all_reach_the_cockpit(self):
        # A real chaos event rarely arrives alone -- prove the path does not
        # silently drop or dedupe distinct findings.
        write_signals(self.signal_file, [
            {"kind": "liveness", "id": "af-live1", "message": "stalled"},
            {"kind": "prs", "id": "57", "message": "stuck PR"},
            {"kind": "aged_human_gate", "id": "af-oihx", "message": "aged gate"},
        ])
        alerts = _read_watchdog_alerts(self.signal_file)
        projection = _today_projection(None, [], [], watchdog_alerts=alerts)
        self.assertEqual(3, len(projection["watchdog_alerts"]))
        self.assertEqual({"liveness", "prs", "aged_human_gate"},
                          {a["kind"] for a in projection["watchdog_alerts"]})

    def test_a_missing_signal_file_is_a_quiet_factory_not_an_error(self):
        alerts = _read_watchdog_alerts(self.signal_file)  # never written this run
        self.assertEqual([], alerts)
        projection = _today_projection(None, [], [], watchdog_alerts=alerts)
        self.assertEqual([], projection["watchdog_alerts"])


class ExhaustedProviderReachesTheCockpit(unittest.TestCase):
    def test_every_provider_exhausted_is_visible_through_the_bridge(self):
        status_json = json.dumps({
            "auto": True, "overlay_present": True,
            "pools": {
                "codex": {"state": "exhausted", "until": "2026-09-21T05:22:00Z", "evidence": "usage limit"},
                "anthropic": {"state": "exhausted", "until": "2026-09-16T16:50:00Z", "evidence": "session limit"},
            },
            "targets": {
                "workspace": {"provider": None, "reason": "all_unavailable",
                              "next_reset": "2026-09-16T16:50:00Z",
                              "default_chain": ["codex", "claude-standard"],
                              "chain_overridden": False, "chain": []},
            },
        })

        def fake_executor(*args, **kwargs):
            class Result:
                returncode = 0
                stdout = status_json
                stderr = ""
            return Result()

        bridge = ProviderBridge(executor=fake_executor)
        payload = bridge.status()
        self.assertEqual("all_unavailable", payload["targets"]["workspace"]["reason"])
        self.assertIsNone(payload["targets"]["workspace"]["provider"])
        self.assertEqual({"codex", "anthropic"}, set(payload["pools"]))
        self.assertTrue(all(p["state"] == "exhausted" for p in payload["pools"].values()))

    def test_a_provider_failover_crash_is_a_source_error_not_a_silent_gap(self):
        from factory_cockpit import SourceError

        def failing_executor(*args, **kwargs):
            class Result:
                returncode = 1
                stdout = ""
                stderr = "provider-failover: policy invalid"
            return Result()

        bridge = ProviderBridge(executor=failing_executor)
        with self.assertRaises(SourceError):
            bridge.status()


if __name__ == "__main__":
    unittest.main()
