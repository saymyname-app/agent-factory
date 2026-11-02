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
host needed: the reader of the cockpit with the collection as its observer,
against a supervisor that answers over HTTP.
"""

import json
import sys
import tempfile
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))

from cockpit.runs.trace import SessionTrace  # noqa: E402
from cockpit.stop.gc_city import GcCityReader  # noqa: E402

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
        elif path.endswith("/sessions"):
            answer = {"items": []}
        elif path.endswith("/transcript"):
            answer = {"id": SESSION["id"], "format": "raw", "messages": []}
        elif path.endswith("/session/" + SESSION["id"]):
            answer = SESSION
        else:
            wanted = urllib.parse.parse_qs(query)["type"][0]
            items = [event for event in self.events if event["type"] == wanted]
            if wanted == "session.woke" and not self.events:
                self.events.extend([WOKE, STOPPED])
            answer = {"items": items}
        body = json.dumps(answer).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class SessionLogCollected(unittest.TestCase):
    def setUp(self):
        Supervisor.events = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Supervisor)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.kept = Path(directory.name) / "sessions.jsonl"

    def test_a_waking_logged_between_two_questions_is_kept_at_the_next_collection(self):
        trace = SessionTrace(str(self.kept))
        reader = GcCityReader("http://127.0.0.1:%d" % self.server.server_port, city="demo", observer=trace.collect)
        reader.status()
        reader.status()
        kinds = [json.loads(line).get("kind") for line in self.kept.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(1, kinds.count("woke"), "the waking of the session is lost")
        self.assertEqual(1, kinds.count("stopped"))


if __name__ == "__main__":
    unittest.main()
