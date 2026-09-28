#!/usr/bin/env python3

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "idle-ready-work-wake"
FAKE_BD = ROOT / "tests" / "fixtures" / "idle-ready-work-wake" / "bd"
FAKE_GC = ROOT / "tests" / "fixtures" / "idle-ready-work-wake" / "gc"

READY_ONE_DELIVERY_BEAD = json.dumps([
    {"id": "af-ready1", "metadata": {"gc.plane": "delivery"}},
])
READY_NONE = "[]"


class IdleReadyWorkWakeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="idle-ready-work-wake-test-"))
        self.gc_log = self.tmp / "gc.log"

    def run_tick(self, now, ready=READY_ONE_DELIVERY_BEAD, mayor_active="0"):
        env = {
            **os.environ,
            "BD_BIN": str(FAKE_BD),
            "GC_BIN": str(FAKE_GC),
            "IDLE_TEST_READY": ready,
            "IDLE_TEST_MAYOR_ACTIVE": mayor_active,
            "IDLE_TEST_GC_LOG": str(self.gc_log),
            "IDLE_READY_WORK_NOW": now,
        }
        proc = subprocess.run(
            (str(TOOL), "--repo-root", str(self.tmp)),
            env=env, text=True, capture_output=True, check=True,
        )
        return json.loads(proc.stdout)

    def wake_calls(self):
        if not self.gc_log.exists():
            return []
        return [json.loads(line) for line in self.gc_log.read_text(encoding="utf-8").splitlines()]

    def test_stays_silent_before_15_minutes_of_idle_ready_work(self):
        first = self.run_tick("2026-09-28T10:00:00+00:00")
        self.assertFalse(first["fired"])
        self.assertEqual([], self.wake_calls())

        just_under = self.run_tick("2026-09-28T10:14:59+00:00")
        self.assertFalse(just_under["fired"])
        self.assertEqual([], self.wake_calls())

    def test_fires_after_idle_ready_work_crosses_15_minutes(self):
        self.run_tick("2026-09-28T10:00:00+00:00")
        self.run_tick("2026-09-28T10:10:00+00:00")

        fired = self.run_tick("2026-09-28T10:15:01+00:00")
        self.assertTrue(fired["fired"])
        self.assertEqual(1, fired["ready_count"])
        calls = self.wake_calls()
        self.assertEqual(1, len(calls))
        self.assertEqual(["mail", "send", "mayor", "--notify"], calls[0][:4])

    def test_stays_silent_while_a_worker_is_active(self):
        self.run_tick("2026-09-28T10:00:00+00:00", mayor_active="1")
        later = self.run_tick("2026-09-28T10:30:00+00:00", mayor_active="1")
        self.assertFalse(later["fired"])
        self.assertEqual([], self.wake_calls())

    def test_a_worker_becoming_active_resets_the_idle_window(self):
        self.run_tick("2026-09-28T10:00:00+00:00")
        self.run_tick("2026-09-28T10:10:00+00:00", mayor_active="1")
        # The window reset when the worker showed up, so 10 more idle
        # minutes is not yet 15 from the new start.
        result = self.run_tick("2026-09-28T10:20:00+00:00")
        self.assertFalse(result["fired"])
        self.assertEqual([], self.wake_calls())

    def test_stays_silent_with_no_ready_delivery_plane_work(self):
        self.run_tick("2026-09-28T10:00:00+00:00", ready=READY_NONE)
        result = self.run_tick("2026-09-28T10:30:00+00:00", ready=READY_NONE)
        self.assertFalse(result["fired"])
        self.assertEqual([], self.wake_calls())


if __name__ == "__main__":
    unittest.main()
