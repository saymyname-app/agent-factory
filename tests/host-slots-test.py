#!/usr/bin/env python3
"""One host-wide limit for every heavy test run (af-lsbqj9): lib/host_slots.py.

More runs than slots are started at once; at most N run together, the others
wait their turn, and the wait is neither a failure nor part of a run's
budget. Each case runs `host_slots.py run` as a real process on a pool of
its own (HOST_SLOTS_DIR, HOST_SLOTS) and stand-in commands that mark when
they run.
"""

from __future__ import annotations

import fcntl
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLOTS = ROOT / "lib" / "host_slots.py"
NOT_RUN = 75

# A stand-in run: enters, records how many are inside at once, stays a moment.
STAND_IN = r"""
import fcntl, os, sys, time
from pathlib import Path
marks = Path(sys.argv[1])
def count(step):
    with open(marks / "lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        inside = marks / "inside"
        now = int(inside.read_text() or 0) + step if inside.exists() else step
        inside.write_text(str(now))
        with open(marks / "seen", "a") as seen:
            seen.write(f"{now}\n")
count(1)
time.sleep(float(sys.argv[2]))
count(-1)
"""


class HostSlots(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="host-slots-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.pool, self.marks = self.tmp / "pool", self.tmp / "marks"
        self.marks.mkdir()
        (self.tmp / "stand_in.py").write_text(STAND_IN)

    def env(self, slots: int, **extra: str) -> dict[str, str]:
        base = {key: value for key, value in os.environ.items() if key not in ("GITHUB_ACTIONS", "HOST_SLOT_HELD")}
        return {**base, "HOST_SLOTS_DIR": str(self.pool), "HOST_SLOTS": str(slots), **extra}

    def start(self, slots: int, *command: str, wait: str = "60", **extra: str) -> subprocess.Popen[str]:
        return subprocess.Popen([sys.executable, str(SLOTS), "run", "--label", "a stand-in run", "--wait", wait,
                                 "--", *command], env=self.env(slots, **extra), text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

    def stand_in(self, seconds: float) -> list[str]:
        return [sys.executable, str(self.tmp / "stand_in.py"), str(self.marks), str(seconds)]

    def hold(self, index: int = 0):
        """Another run holds slot `index` until the handle is closed."""
        self.pool.mkdir(exist_ok=True)
        handle = (self.pool / f"slot-{index}.lock").open("a")
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        (self.pool / f"slot-{index}.holder").write_text("the battery of somewhere\n")
        self.addCleanup(handle.close)
        return handle

    def test_more_runs_than_slots_never_exceed_the_slots_and_all_pass(self):
        # Eight cores, four for each run (config/host-slots.json): two at once.
        runs = [self.start(8, *self.stand_in(0.6)) for _ in range(5)]
        outputs = [run.communicate(timeout=60)[0] for run in runs]
        self.assertEqual([0] * 5, [run.returncode for run in runs], "\n".join(outputs))
        seen = [int(line) for line in (self.marks / "seen").read_text().split()]
        self.assertEqual(10, len(seen), "each of the five runs enters and leaves once")
        self.assertLessEqual(max(seen), 2, f"more runs than slots ran at once: {seen}")
        self.assertEqual(2, max(seen), f"the two slots were never both used: {seen}")
        self.assertTrue(any("waiting for a host slot" in output for output in outputs), "\n".join(outputs))

    def test_the_wait_is_not_counted_in_the_runs_budget(self):
        # The run's own budget is 3 s (`timeout 3`); the only slot is held
        # 4 s first. Its clock starts once the slot is taken, so it passes.
        holder = self.hold()
        run = self.start(1, "timeout", "3", *self.stand_in(1))
        time.sleep(4)
        self.assertIsNone(run.poll(), "the run did not wait for the held slot")
        self.assertFalse((self.marks / "seen").exists(), "the run started while the only slot was held")
        holder.close()
        output, _ = run.communicate(timeout=30)
        self.assertEqual(0, run.returncode, output)

    def test_past_its_wait_a_run_is_not_run_exit_75_and_runs_nothing(self):
        self.hold()
        run = self.start(1, *self.stand_in(0), wait="1")
        output, _ = run.communicate(timeout=30)
        self.assertEqual(NOT_RUN, run.returncode, output)
        self.assertIn("NOT RUN", output)
        self.assertIn("not a test failure", output)
        self.assertIn("the battery of somewhere", output)
        self.assertFalse((self.marks / "seen").exists())

    def test_a_run_in_a_holders_turn_takes_no_slot_and_never_waits_on_itself(self):
        self.hold()
        run = self.start(1, *self.stand_in(0), wait="1", HOST_SLOT_HELD=str(self.pool))
        output, _ = run.communicate(timeout=30)
        self.assertEqual(0, run.returncode, output)
        self.assertNotIn("waiting", output)

    def test_a_slot_comes_back_when_its_holder_is_killed(self):
        first = self.start(1, "sleep", "60")
        deadline = time.monotonic() + 10
        while not (self.pool / "slot-0.holder").exists():
            self.assertLess(time.monotonic(), deadline, "the first run never took its slot")
            time.sleep(0.05)
        first.kill()
        first.communicate()
        run = self.start(1, *self.stand_in(0), wait="10")
        output, _ = run.communicate(timeout=30)
        self.assertEqual(0, run.returncode, output)


if __name__ == "__main__":
    unittest.main()
