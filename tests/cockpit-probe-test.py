#!/usr/bin/env python3
"""bin/cockpit-probe, run as the timer runs it, against a fake Cockpit and a
fake Pushover: one notification per change of state, a restart after two
local failures in a row, exit 1 while an address is down."""
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROBE = ROOT / "bin" / "cockpit-probe"


class Handler(http.server.BaseHTTPRequestHandler):
    posts = []

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def do_POST(self):
        Handler.posts.append(self.rfile.read(int(self.headers["Content-Length"])))
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


def serve():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class CockpitProbeTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.cockpit = serve()
        self.pushover = serve()
        secrets = Path(self.home, "pushover.json")
        secrets.write_text(json.dumps({"token": "t", "user_key": "u", "e2e_key": "ab" * 32}))
        self.restarted = Path(self.home, "restarted")
        self.port = self.cockpit.server_address[1]
        self.env = dict(os.environ, COCKPIT_PORT=str(self.port), COCKPIT_PID_FILE=str(Path(self.home, "cockpit.pid")),
                        COCKPIT_LOCAL_CONFIG=str(Path(self.home, "none.json")),
                        COCKPIT_PUBLIC_URL="http://127.0.0.1:%d/tailnet" % self.port,
                        COCKPIT_PUSHOVER_SECRETS_FILE=str(secrets),
                        COCKPIT_PUSHOVER_URL="http://127.0.0.1:%d/" % self.pushover.server_address[1],
                        COCKPIT_PROBE_RESTART="touch %s" % self.restarted)
        Handler.posts = []

    def tearDown(self):
        self.pushover.shutdown()
        self.pushover.server_close()

    def probe(self):
        return subprocess.run([sys.executable, str(PROBE)], env=self.env, capture_output=True, text=True, timeout=120)

    def test_up_down_restart_up(self):
        first = self.probe()
        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        self.assertIn("adresse tailnet http://127.0.0.1:%d/tailnet/ → 200" % self.port, first.stdout)
        self.assertEqual([], Handler.posts, "a Cockpit that stays up is not notified")

        self.cockpit.shutdown()
        self.cockpit.server_close()
        down = self.probe()
        self.assertEqual(1, down.returncode)
        self.assertEqual(1, len(Handler.posts), "the fall is notified once")
        self.assertFalse(self.restarted.exists(), "one failure is no reason to restart")

        again = self.probe()
        self.assertEqual(1, again.returncode)
        self.assertEqual(1, len(Handler.posts), "a state that stays down is not notified again")
        self.assertTrue(self.restarted.exists(), "two local failures in a row restart the unit")

        self.cockpit = http.server.ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        threading.Thread(target=self.cockpit.serve_forever, daemon=True).start()
        back = self.probe()
        self.assertEqual(0, back.returncode, back.stdout + back.stderr)
        self.assertEqual(2, len(Handler.posts), "the return is notified once")
        self.cockpit.shutdown()
        self.cockpit.server_close()


if __name__ == "__main__":
    unittest.main()
