#!/usr/bin/env python3
"""Criterion test 3 of I « Accès HTTPS sur la VM, veille de silence et
procédure de réglages opérateur » (af-cp4fzd; Spec af-fgcw0d, user story 67,
Implementation Decision « Notifications et veille » : « Heartbeat vide
toutes les cinq minutes seulement après lectures principales fraîches,
alerte au plus quinze minutes de silence », Testing Decisions 1, 4 and 8).

The heartbeat is simulated: each case launches the real cockpit with the
launcher of the profile, bin/project-launch, its heartbeat sent to a
recorder of this file at a pace the dataset gives (`heartbeat`), two
seconds standing for the five minutes of service. The recorder is the check
« Usine muette » as the procedure of the VM sets it on Healthchecks.io: a
period of five minutes and a grace of ten, written here, so it alerts once
no ping came for fifteen minutes -- six seconds at this pace.

- home-loading: the main sources are never read; the cockpit lives, and no
  heartbeat goes out.
- health-content: the main sources read fresh; heartbeats go out, never so
  far apart that the check alerts. Then the host falls silent -- the
  launch is stopped --: no heartbeat goes out any more, and the check
  alerts within fifteen minutes of the silence.

False if a heartbeat goes out without a fresh reading, or the silence does
not alert.
"""

from __future__ import annotations

import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from acces_vm import declare  # noqa: E402
from home_destination import LaunchTree  # noqa: E402

# The pace of the simulated heartbeat: two seconds for the five minutes of
# service.
INTERVAL_SECONDS = 2
SECONDS_PER_MINUTE = INTERVAL_SECONDS / 5
# The check « Usine muette » on Healthchecks.io, as the VM procedure sets it.
PERIOD_MINUTES = 5
GRACE_MINUTES = 10
# What user story 67 allows between the silence and the alert.
ALERT_WITHIN_MINUTES = 15
SILENCE_SECONDS = (PERIOD_MINUTES + GRACE_MINUTES) * SECONDS_PER_MINUTE
# How long the cockpit is watched: long enough for several heartbeats, and
# for the check to alert had they stopped.
WATCHED_SECONDS = 3 * SILENCE_SECONDS
# A heartbeat in flight when the silence begins may still arrive.
IN_FLIGHT_SECONDS = 1.0


class Recorder:
    """The check: when each ping arrived (time.monotonic)."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.pings: list[float] = []
        recorder = self

        class Ping(BaseHTTPRequestHandler):
            def answer(self):
                with recorder.lock:
                    recorder.pings.append(time.monotonic())
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"OK")

            do_GET = do_POST = do_HEAD = answer

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Ping)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/ping/usine-muette"

    def seen(self) -> list[float]:
        with self.lock:
            return list(self.pings)

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


class HeartbeatSilence(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.tree = LaunchTree()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tree.remove()

    def setUp(self) -> None:
        self.check = Recorder()
        self.addCleanup(self.check.close)

    def tearDown(self) -> None:
        self.tree.stop_all()

    def launched(self, base: str) -> float:
        """The cockpit launched on `base`, its heartbeat sent to the check:
        when it answered (time.monotonic)."""
        name = f"heartbeat-{base}"
        commit = declare(self.tree, name, base,
                         heartbeat={"ping_url": self.check.url, "interval_seconds": INTERVAL_SECONDS})
        self.tree.launch(name, commit)
        return time.monotonic()

    # --- Criterion 3 ------------------------------------------------------------

    def test_the_heartbeat_goes_out_only_on_fresh_readings_and_the_silent_host_alerts_within_fifteen_minutes(self):
        # The criterion names the heartbeat on fresh readings and the alert
        # once the host falls silent: one criterion observed whole.
        self.assert_no_heartbeat_without_a_fresh_reading()
        self.assert_the_silent_host_alerts_within_fifteen_minutes()

    def assert_no_heartbeat_without_a_fresh_reading(self) -> None:
        self.launched("home-loading")
        time.sleep(WATCHED_SECONDS)
        self.assertEqual([], self.check.seen(), "a heartbeat went out while the main sources were never read")
        self.tree.stop_all()

    def assert_the_silent_host_alerts_within_fifteen_minutes(self) -> None:
        started = self.launched("health-content")
        time.sleep(WATCHED_SECONDS)
        alive = [at for at in self.check.seen() if at >= started]
        self.assertGreaterEqual(len(alive), 3, f"the heartbeats of fresh readings did not go out: {len(alive)} seen")
        gaps = [later - earlier for earlier, later in zip([started] + alive, alive + [time.monotonic()])]
        self.assertLess(max(gaps[1:]), SILENCE_SECONDS,
                        f"the check alerted while the host answered: heartbeats {gaps} s apart")
        silent = time.monotonic()
        self.tree.stop_all()
        time.sleep(SILENCE_SECONDS + IN_FLIGHT_SECONDS)
        after = [at for at in self.check.seen() if at > silent + IN_FLIGHT_SECONDS]
        self.assertEqual([], after, "a heartbeat went out after the host fell silent")
        last = max(at for at in self.check.seen() if at >= started)
        alerted = last + SILENCE_SECONDS
        self.assertLessEqual(alerted - silent, ALERT_WITHIN_MINUTES * SECONDS_PER_MINUTE,
                             "the check alerts more than fifteen minutes after the silence")
        self.assertLessEqual(alerted, time.monotonic(), "the check has not alerted yet")


if __name__ == "__main__":
    unittest.main()
