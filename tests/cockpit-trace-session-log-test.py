#!/usr/bin/env python3
"""The collection of the trace of the sessions follows the log of the
supervisor one kind of event at a time (R9, af-gfqzbk; Spec af-fgcw0d,
Testing Decisions 7, « Rejouer sans doublon »).

The reader asks the supervisor for its session.woke events, then for its
session.stopped ones. A session that wakes and stops between those two
questions is first seen by its stop, whose number is above its waking: the
waking is read at the next collection, and is kept. False if it is lost: a
later cockpit, reading the same log from its start, would add it to the
projection.

The case stands where runs-trace-collection-test.py turned red with no busy
host needed, and enters no code of the cockpit: it starts the real process,
bin/cockpit run, on a supervisor that answers over HTTP, waits for GET
/api/status, and reads the projection the process was told to keep.
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COCKPIT = ROOT / "bin" / "cockpit"
FAKE_BD = ROOT / "tests" / "fixtures" / "cockpit" / "core" / "fake-bd"

SESSION = {"id": "demo-1", "session_name": "demo-1", "template": "author", "created_at": "2026-10-12T12:13:10Z"}
WOKE = {"seq": 1, "type": "session.woke", "ts": "2026-10-12T12:13:10Z", "session_id": "demo-1"}
STOPPED = {"seq": 2, "type": "session.stopped", "ts": "2026-10-12T12:14:37Z", "session_id": "demo-1"}


class Supervisor(BaseHTTPRequestHandler):
    """Logs the session once its session.woke events have been asked for
    the first time."""
    events: list = []

    def log_message(self, *_):
        pass

    def do_GET(self):  # noqa: N802
        path, _, query = self.path.partition("?")
        if path.endswith("/status"):
            answer = {"suspended": False}
        elif path.endswith("/transcript"):
            answer = {"id": SESSION["id"], "format": "raw", "messages": []}
        elif path.endswith("/session/" + SESSION["id"]):
            answer = SESSION
        elif path.endswith("/events"):
            wanted = urllib.parse.parse_qs(query)["type"][0]
            items = [event for event in self.events if event["type"] == wanted]
            if wanted == "session.woke" and not self.events:
                self.events.extend([WOKE, STOPPED])
            answer = {"items": items}
        else:
            answer = {"items": []}
        body = json.dumps(answer).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as found:
        found.bind(("127.0.0.1", 0))
        return found.getsockname()[1]


class SessionLogCollected(unittest.TestCase):
    def setUp(self):
        Supervisor.events = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Supervisor)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.home = Path(directory.name)
        self.kept = self.home / "sessions.jsonl"

    def start_cockpit(self):
        port = free_port()
        cockpit = subprocess.Popen(
            [sys.executable, str(COCKPIT), "run"],
            env={"PATH": os.environ.get("PATH", os.defpath), "HOME": str(self.home),
                 "COCKPIT_HOST": "127.0.0.1", "COCKPIT_PORT": str(port),
                 "COCKPIT_PID_FILE": str(self.home / "cockpit.pid"),
                 "COCKPIT_LOCAL_CONFIG": str(self.home / "absent.json"),
                 "COCKPIT_GC_BASE_URL": "http://127.0.0.1:%d" % self.server.server_port,
                 "COCKPIT_GC_CITY": "demo", "COCKPIT_BD_BIN": str(FAKE_BD),
                 "COCKPIT_SESSIONS_POLL_SECONDS": "0.1", "COCKPIT_TRACE_FILE": str(self.kept)},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(cockpit.wait)
        self.addCleanup(cockpit.terminate)
        return port

    def wait_served(self, port, seconds=30):
        deadline = time.monotonic() + seconds
        while True:
            try:
                with urllib.request.urlopen("http://127.0.0.1:%d/api/status" % port, timeout=3) as answer:
                    return answer.status
            except (urllib.error.URLError, OSError):
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.1)

    def kinds(self):
        if not self.kept.is_file():
            return []
        return [json.loads(line).get("kind") for line in self.kept.read_text(encoding="utf-8").splitlines()]

    def test_a_waking_logged_between_two_questions_is_kept_at_the_next_collection(self):
        self.assertEqual(200, self.wait_served(self.start_cockpit()))
        # The stop is kept by the first collection that sees the session; a
        # dozen readings later its waking has had every chance to be.
        deadline = time.monotonic() + 30
        while "stopped" not in self.kinds() and time.monotonic() < deadline:
            time.sleep(0.1)
        time.sleep(1.2)
        kinds = self.kinds()
        self.assertEqual(1, kinds.count("woke"), "the waking of the session is lost")
        self.assertEqual(1, kinds.count("stopped"))


if __name__ == "__main__":
    unittest.main()
