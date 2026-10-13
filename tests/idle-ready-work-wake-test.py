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
# What `bd ready` returned on 2026-10-13 while the marked convoy af-pqfxmd
# was open: the convoy bead itself, on the delivery plane.
READY_MARKED_CONVOY_ONLY = json.dumps([
    {"id": "af-convoy", "issue_type": "convoy",
     "metadata": {"gc.plane": "delivery", "gc.flow.mark": "new-flow/v1"}},
])
READY_MARKED_TICKET_ONLY = json.dumps([
    {"id": "af-ticket", "issue_type": "task",
     "metadata": {"gc.plane": "delivery", "gc.flow.mark": "new-flow/v1"}},
])
READY_UNMARKED_CONVOY_ONLY = json.dumps([
    {"id": "af-oldconvoy", "issue_type": "convoy", "metadata": {"gc.plane": "delivery"}},
])


class IdleReadyWorkWakeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="idle-ready-work-wake-test-"))
        self.gc_log = self.tmp / "gc.log"

    def run_tick(self, now, ready=READY_ONE_DELIVERY_BEAD, worker_active="0"):
        env = {
            **os.environ,
            "BD_BIN": str(FAKE_BD),
            "GC_BIN": str(FAKE_GC),
            "IDLE_TEST_READY": ready,
            "IDLE_TEST_WORKER_ACTIVE": worker_active,
            "IDLE_TEST_GC_LOG": str(self.gc_log),
            "IDLE_READY_WORK_NOW": now,
        }
        proc = subprocess.run(
            (str(TOOL), "--repo-root", str(self.tmp)),
            env=env, text=True, capture_output=True, check=True,
        )
        return json.loads(proc.stdout)

    def run_check_only(self, now, ready=READY_ONE_DELIVERY_BEAD, worker_active="0"):
        env = {
            **os.environ,
            "BD_BIN": str(FAKE_BD),
            "GC_BIN": str(FAKE_GC),
            "IDLE_TEST_READY": ready,
            "IDLE_TEST_WORKER_ACTIVE": worker_active,
            "IDLE_TEST_GC_LOG": str(self.gc_log),
            "IDLE_READY_WORK_NOW": now,
        }
        proc = subprocess.run(
            (str(TOOL), "--repo-root", str(self.tmp), "--check-only"),
            env=env, text=True, capture_output=True,
        )
        return proc.returncode, json.loads(proc.stdout)

    def test_check_runs_with_the_empty_BD_BIN_the_controller_exports(self):
        # af-37a1xn: gc 1.5.0 gives an order's check BD_BIN= (empty). Read
        # as a binary name it crashed the check (exit 1) on every tick, so
        # this safety net could never fire. Empty means not set.
        env = {
            **os.environ,
            "BD_BIN": "",
            "GC_BIN": str(FAKE_GC),
            "PATH": f"{FAKE_BD.parent}{os.pathsep}{os.environ['PATH']}",
            "IDLE_TEST_READY": READY_NONE,
            "IDLE_TEST_WORKER_ACTIVE": "0",
            "IDLE_TEST_GC_LOG": str(self.gc_log),
            "IDLE_READY_WORK_NOW": "2026-09-28T10:00:00+00:00",
        }
        proc = subprocess.run(
            (str(TOOL), "--repo-root", str(self.tmp), "--check-only"),
            env=env, text=True, capture_output=True,
        )
        self.assertNotIn("Traceback", proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["ok"])

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
        self.run_tick("2026-09-28T10:00:00+00:00", worker_active="1")
        later = self.run_tick("2026-09-28T10:30:00+00:00", worker_active="1")
        self.assertFalse(later["fired"])
        self.assertEqual([], self.wake_calls())

    def test_a_worker_becoming_active_resets_the_idle_window(self):
        self.run_tick("2026-09-28T10:00:00+00:00")
        self.run_tick("2026-09-28T10:10:00+00:00", worker_active="1")
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

    def test_stays_silent_on_what_the_mayor_may_not_dispatch(self):
        # af-yzo8fo.1, af-vnv59w: a convoy bead is a container, and a marked
        # ticket is started by bin/convoy-advance, never by the Mayor.
        for ready in (READY_MARKED_CONVOY_ONLY, READY_MARKED_TICKET_ONLY, READY_UNMARKED_CONVOY_ONLY):
            with self.subTest(ready=ready):
                self.run_tick("2026-09-28T10:00:00+00:00", ready=ready)
                result = self.run_tick("2026-09-28T10:30:00+00:00", ready=ready)
                self.assertFalse(result["fired"])
                self.assertEqual(0, result["ready_count"])
                self.assertEqual([], self.wake_calls())

    def test_counts_only_the_dispatchable_bead_beside_a_marked_convoy(self):
        ready = json.dumps(
            json.loads(READY_MARKED_CONVOY_ONLY) + json.loads(READY_ONE_DELIVERY_BEAD)
        )
        self.run_tick("2026-09-28T10:00:00+00:00", ready=ready)
        fired = self.run_tick("2026-09-28T10:15:01+00:00", ready=ready)
        self.assertTrue(fired["fired"])
        self.assertEqual(1, fired["ready_count"])

    def test_does_not_renotify_on_every_evaluation_past_15_minutes(self):
        self.run_tick("2026-09-28T10:00:00+00:00")
        self.run_tick("2026-09-28T10:10:00+00:00")

        first = self.run_tick("2026-09-28T10:15:01+00:00")
        self.assertTrue(first["fired"])

        second = self.run_tick("2026-09-28T10:15:06+00:00")
        self.assertFalse(second["fired"])

        calls = self.wake_calls()
        self.assertEqual(1, len(calls))

    def test_renotifies_after_the_cooldown_elapses_while_still_idle(self):
        self.run_tick("2026-09-28T10:00:00+00:00")
        self.run_tick("2026-09-28T10:10:00+00:00")

        first = self.run_tick("2026-09-28T10:15:01+00:00")
        self.assertTrue(first["fired"])

        still_cooling = self.run_tick("2026-09-28T10:30:00+00:00")
        self.assertFalse(still_cooling["fired"])

        after_cooldown = self.run_tick("2026-09-28T11:15:02+00:00")
        self.assertTrue(after_cooldown["fired"])

        calls = self.wake_calls()
        self.assertEqual(2, len(calls))

    def test_check_only_reports_but_never_notifies(self):
        # af-1isbx: the order's `check=` leg must decide whether to run
        # `exec=` (exit 0/1) without itself paging the Mayor -- only the
        # `exec=` leg (the plain, non-check-only invocation) may notify.
        self.run_tick("2026-09-28T10:00:00+00:00")
        self.run_tick("2026-09-28T10:10:00+00:00")

        code, result = self.run_check_only("2026-09-28T10:15:01+00:00")
        self.assertEqual(0, code)
        self.assertTrue(result["fired"])
        self.assertEqual([], self.wake_calls())

        code, result = self.run_check_only("2026-09-28T10:15:02+00:00", worker_active="1")
        self.assertEqual(1, code)
        self.assertFalse(result["fired"])
        self.assertEqual([], self.wake_calls())


if __name__ == "__main__":
    unittest.main()
