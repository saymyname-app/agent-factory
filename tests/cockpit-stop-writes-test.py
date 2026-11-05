#!/usr/bin/env python3
"""The writes of a clean stop as the installed supervisor requires them
(H, af-69qhlk; gc 1.5.0, /openapi.json of the live host, read 2026-10-31):
each carries the anti-CSRF header `X-GC-Request`, which the synthetic
supervisor does not check, and an answer that never comes is an uncertain
outcome, not a refusal.
"""

import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from cockpit.stop.gc_city import GcCityReader, StopUncertain  # noqa: E402


class Supervisor(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _answer(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8")
        self.server.seen.append((self.command, self.path, self.headers.get("X-GC-Request"), body))
        status = self.server.status
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")

    do_PATCH = do_POST = _answer


class StopWrites(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), Supervisor)
        self.server.seen, self.server.status = [], 200
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.reader = GcCityReader("http://127.0.0.1:%d" % self.server.server_address[1], city="ville", timeout=2)

    def test_each_write_is_the_published_one_with_its_header(self):
        self.reader.suspend()
        self.reader.resume()
        self.reader.force_stop_sessions(["s 1"])
        self.assertEqual(
            [("PATCH", "/v0/city/ville", True, {"suspended": True}),
             ("PATCH", "/v0/city/ville", True, {"suspended": False}),
             ("POST", "/v0/city/ville/session/s%201/stop", True, None)],
            [(method, path, bool(header), json.loads(body) if body else None)
             for method, path, header, body in self.server.seen])

    def test_a_refusal_is_said_as_one(self):
        self.server.status = 409
        with self.assertRaisesRegex(ValueError, "409"):
            self.reader.suspend()

    def test_no_answer_is_uncertain(self):
        reader = GcCityReader("http://127.0.0.1:9", city="ville", timeout=1)
        with self.assertRaises(StopUncertain):
            reader.resume()


if __name__ == "__main__":
    unittest.main()
