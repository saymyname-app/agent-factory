#!/usr/bin/env python3
"""Rules of lib/factory_session_boot.py that the guard integration test does not reach."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from factory_session_boot import (  # noqa: E402
    assess_identity,
    extract_record,
    group_by_identity,
    mayor_page_since,
)

NOW = 1789555200.0  # 2026-09-16T10:40:00Z


def iso(offset_minutes):
    return f"2026-09-16T{10 + (40 - offset_minutes) // 60:02d}:{(40 - offset_minutes) % 60:02d}:00Z"


def event(minutes_ago, state, identity="mayor", **extra):
    """A raw gc-events-shaped object, `minutes_ago` before NOW."""
    ts_epoch = NOW - minutes_ago * 60
    from datetime import datetime, timezone
    ts = datetime.fromtimestamp(ts_epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    metadata = {
        "configured_named_mode": "always",
        "configured_named_identity": identity,
        "agent_name": identity,
        "state": state,
        "command": "codex --model gpt-5.5",
        "provider": "codex",
    }
    metadata.update(extra)
    return {"type": "bead.updated", "ts": ts, "payload": {"bead": {"id": "af-x", "metadata": metadata}}}


class ExtractRecord(unittest.TestCase):
    def test_ignores_sessions_not_configured_named_always(self):
        ev = event(1, "creating")
        ev["payload"]["bead"]["metadata"]["configured_named_mode"] = "on_demand"
        self.assertIsNone(extract_record(ev))

    def test_ignores_malformed_events(self):
        self.assertIsNone(extract_record({}))
        self.assertIsNone(extract_record({"payload": {}}))
        self.assertIsNone(extract_record({"payload": {"bead": {}}}))

    def test_extracts_the_fields_this_module_needs(self):
        rec = extract_record(event(5, "creating", identity="mayor", state_reason="booting"))
        self.assertEqual(rec["identity"], "mayor")
        self.assertEqual(rec["state"], "creating")
        self.assertEqual(rec["state_reason"], "booting")


class AssessIdentity(unittest.TestCase):
    def test_no_records_is_no_data_not_an_alarm(self):
        self.assertEqual("no_data", assess_identity([], NOW)[1])

    def test_a_healthy_awake_session_is_ok(self):
        records = [extract_record(event(5, "awake"))]
        self.assertEqual(("ok", "ok"), assess_identity(records, NOW)[:2])

    def test_freshly_creating_is_not_yet_an_alarm(self):
        records = [extract_record(event(3, "creating"))]
        level, code, _ = assess_identity(records, NOW)
        self.assertEqual(("info", "booting"), (level, code))

    def test_stuck_past_the_threshold_is_flagged(self):
        records = [extract_record(event(20, "creating"))]
        level, code, message = assess_identity(records, NOW)
        self.assertEqual(("bad", "session-boot-stuck"), (level, code))
        self.assertIn("mayor", message)
        self.assertIn("20 min", message)

    def test_churn_across_bead_ids_still_counts_as_one_streak(self):
        """af-jj9u7's actual incident: creating -> failed-create -> creating,
        never reaching awake, across many different session bead ids."""
        records = [
            extract_record(event(30, "creating")),
            extract_record(event(25, "failed-create", close_reason="provider 400")),
            extract_record(event(24, "creating")),
            extract_record(event(19, "failed-create", close_reason="provider 400")),
        ]
        level, code, message = assess_identity(records, NOW)
        self.assertEqual(("bad", "session-boot-stuck"), (level, code))
        self.assertIn("30 min", message)  # streak started at the earliest creating
        self.assertIn("provider 400", message)  # last known reason surfaces

    def test_a_transition_back_to_awake_resets_the_streak(self):
        records = [
            extract_record(event(30, "creating")),
            extract_record(event(20, "awake")),
            extract_record(event(5, "creating")),
        ]
        level, code, message = assess_identity(records, NOW)
        self.assertEqual(("info", "booting"), (level, code))
        self.assertIn("5 min", message)

    def test_threshold_is_configurable(self):
        records = [extract_record(event(10, "creating"))]
        self.assertEqual("booting", assess_identity(records, NOW)[1])
        self.assertEqual("session-boot-stuck", assess_identity(records, NOW, threshold_minutes=5)[1])

    def test_names_provider_command_and_reason_for_diagnosis(self):
        records = [extract_record(event(
            20, "failed-create", close_reason="model not supported", provider="codex-spark",
            command="codex -m gpt-5.3-codex-spark",
        ))]
        _, _, message = assess_identity(records, NOW)
        self.assertIn("codex-spark", message)
        self.assertIn("gpt-5.3-codex-spark", message)
        self.assertIn("model not supported", message)


class GroupByIdentity(unittest.TestCase):
    def test_groups_and_sorts_multiple_identities_independently(self):
        events = [
            event(5, "creating", identity="mayor"),
            event(20, "creating", identity="ux-reviewer"),
            event(1, "creating", identity="mayor"),
        ]
        groups = group_by_identity(events)
        self.assertEqual({"mayor", "ux-reviewer"}, set(groups))
        self.assertEqual(2, len(groups["mayor"]))
        self.assertLess(groups["mayor"][0]["ts"], groups["mayor"][1]["ts"])


class Cli(unittest.TestCase):
    def run_cli(self, events):
        payload = "\n".join(json.dumps(e) for e in events)
        result = subprocess.run(
            [sys.executable, str(ROOT / "lib" / "factory_session_boot.py")],
            input=payload, capture_output=True, text=True,
            env={**os.environ, "FACTORY_GUARD_NOW": str(NOW)},
        )
        return [line.split("\t") for line in result.stdout.strip().splitlines() if line]

    def test_prints_one_line_per_identity(self):
        rows = self.run_cli([event(20, "creating", identity="mayor"), event(1, "awake", identity="witness")])
        by_identity = {r[0]: r[1:] for r in rows}
        self.assertEqual(["bad", "session-boot-stuck"], by_identity["mayor"][:2])
        self.assertEqual(["ok", "ok"], by_identity["witness"][:2])

    def test_ignores_garbage_lines(self):
        rows = self.run_cli([])
        self.assertEqual([], rows)


class MayorPage(unittest.TestCase):
    def test_only_asleep_or_quarantine_past_the_grace_window_pages(self):
        recent = {"state": "quarantined", "last_active": "2026-09-16T10:35:00Z"}  # 5 min ago
        self.assertIsNone(mayor_page_since(recent, NOW))
        overdue = {"state": "quarantined", "last_active": "2026-09-16T10:00:00Z"}  # 40 min ago
        self.assertEqual("2026-09-16T10:00:00Z", mayor_page_since(overdue, NOW))
        active = {"state": "active", "last_active": "2026-09-16T10:00:00Z"}
        self.assertIsNone(mayor_page_since(active, NOW))
        # creating/failed-create already has its own alert (af-jj9u7).
        booting = {"state": "creating", "last_active": "2026-09-16T10:00:00Z"}
        self.assertIsNone(mayor_page_since(booting, NOW))
        self.assertIsNone(mayor_page_since(None, NOW))


if __name__ == "__main__":
    unittest.main(verbosity=1)
