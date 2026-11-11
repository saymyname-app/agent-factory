#!/usr/bin/env python3
"""Criterion test 1 of R17 « Heartbeat maintenu tant que la suspension n'est
pas confirmée propre » (af-8hq9o8; Blocking Finding F1.30 of the end review
on 96b3429f0dee; Spec af-fgcw0d, user stories 67, 83 and 165, Implementation
Decision « Notifications et veille » : « pause uniquement à arrêt propre
confirmé, reprise au redémarrage », Testing Decisions 1, 4 and 8): a
suspension where a work is lost, POST /api/actions/arreter, then GET /usine
and the heartbeat.

The case launches the real cockpit with the launcher of the profile,
bin/project-launch, on health-content with what it adds to it: a synthetic
supervisor whose author leaves during the suspension with its ticket gone
from the tracker (usine_arret.serve_stop, `vanishes_when_drained`), and a
heartbeat sent to a recorder of this file at a pace the dataset gives
(`heartbeat`, as acces_vm.declare declares it), two seconds standing for the
five minutes of service. The gesture is sent as the browser sends it from a
page the cockpit served, behind the identity proxy of the host
(usine_arret.Operator).

False if the pings stop while /usine says « Suspension à vérifier ».

What this case proves that the cases below it do not (docs/TEST_GUIDELINE.md
§2, §6): tests/cockpit-heartbeat-test.py proves the rule of the emitter on a
read model and a state given by hand; factory-stop-test.py proves the words
of /usine on a lost work, and heartbeat-silence-test.py the heartbeat of a
launch with no stop. Here the state the emitter reads is the one the stop
asked through the cockpit leaves, and the page and the pings are read from
the same launch at the same time.
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
from home_destination import LaunchTree, git  # noqa: E402
from usine_arret import Operator, said, said_until, serve_stop  # noqa: E402

AUTHOR = {"session": "auteur-recus", "role": "Auteur", "ticket": "tk-recus", "title": "Trier les reçus du mois"}
REVIEWER = {"session": "relecteur-notes", "role": "Relecteur", "ticket": "tk-notes",
            "title": "Relire les notes de frais"}
# The pace of the simulated heartbeat: two seconds for the five minutes of
# service.
INTERVAL_SECONDS = 2
# How long the page is watched once it says the suspension is to verify:
# four beats.
WATCHED_SECONDS = 4 * INTERVAL_SECONDS
# A heartbeat already in flight when the watch begins does not count.
IN_FLIGHT_SECONDS = 1.0


class Recorder:
    """Where the heartbeat of the launch goes: when each ping arrived
    (time.monotonic)."""

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


class FactoryStopHeartbeat(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        # A tree of its own: the case commits its datasets in it.
        self.tree = LaunchTree()
        self.addCleanup(self.tree.remove)
        self.check = Recorder()
        self.addCleanup(self.check.close)

    def test_a_suspension_to_verify_keeps_the_heartbeat_going(self):
        # health-content with the heartbeat, then the supervisor of the case on top of it.
        base = declare(self.tree, "heartbeat-health-content", "health-content",
                       heartbeat={"ping_url": self.check.url, "interval_seconds": INTERVAL_SECONDS})
        git(self.tree.repo, "checkout", "--quiet", base)
        address, _ = serve_stop(self.tree, "heartbeat-health-content", {
            "work": [AUTHOR, REVIEWER], "drains_in_seconds": {"relecteur-notes": 1, "auteur-recus": 1},
            "vanishes_when_drained": ["tk-recus"]})
        launched = time.monotonic()

        answer = Operator(address).gesture("arreter", {"confirm": True})
        self.assertEqual("", answer.broken, f"the request broke: {answer}")
        self.assertEqual(200, answer.status, f"the suspension was not asked: {answer}")

        text = said_until(address, "Suspension à vérifier")
        self.assertIn("Suspension à vérifier", text, f"the loss is not said: « {text} »")
        self.assertNotIn("Suspension confirmée", text, "confirmed though a ticket of the photo is gone")
        before = [at for at in self.check.seen() if at >= launched]
        self.assertTrue(before, "no heartbeat went out on the fresh readings of the launch")

        # The page still says the suspension is to verify, and the pings go on.
        watched = time.monotonic()
        time.sleep(WATCHED_SECONDS)
        text = said(address)
        self.assertIn("Suspension à vérifier", text, f"the page no longer says the suspension is to verify: « {text} »")
        after = [at for at in self.check.seen() if at > watched + IN_FLIGHT_SECONDS]
        self.assertGreaterEqual(
            len(after), 2,
            f"the heartbeat stopped while /usine says « Suspension à vérifier »: {len(after)} ping(s) "
            f"in {WATCHED_SECONDS - IN_FLIGHT_SECONDS:.0f} s at one every {INTERVAL_SECONDS} s")


if __name__ == "__main__":
    unittest.main()
