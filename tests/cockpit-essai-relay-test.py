#!/usr/bin/env python3
"""The relay of Essai (F2.4, lib/cockpit/actions/essai_relay.py): the entry
Tailscale Serve gives Essai on the tailnet, in front of a fake product on
loopback that records what reaches it. Each case sends what Serve would
send -- the operator's login, or another one -- and reads what the
product received and what the client got back."""
import http.client
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from cockpit.access.guard import ActionGuard  # noqa: E402
from cockpit.actions.essai_relay import RelayService, TrialTarget, make_relay  # noqa: E402

LOGIN = "benjamin@example.ts.net"
ENTRY = "https://factory-vm.example.ts.net:8443"


class FakeProduct(BaseHTTPRequestHandler):
    """Answers every request with what reached it, and a cookie of its own."""

    seen = []

    def log_message(self, fmt, *args):
        pass

    def answer(self):
        length = int(self.headers.get("Content-Length") or 0)
        received = {"method": self.command, "path": self.path, "headers": dict(self.headers.items()),
                    "body": self.rfile.read(length).decode("utf-8") if length else ""}
        type(self).seen.append(received)
        body = json.dumps(received).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Set-Cookie", "cockpit_session=product-token; Path=/; SameSite=Strict; HttpOnly")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = answer


class RelayTest(unittest.TestCase):
    def setUp(self):
        FakeProduct.seen = []
        self.product = ThreadingHTTPServer(("127.0.0.1", 0), FakeProduct)
        threading.Thread(target=self.product.serve_forever, daemon=True).start()
        self.addCleanup(self.product.server_close)
        self.addCleanup(self.product.shutdown)
        self.target = TrialTarget()
        relay = make_relay(ActionGuard(LOGIN, ENTRY, "cockpit-token"), self.target, port=0)
        self.port = relay.socket.getsockname()[1]
        self.service = RelayService(relay)
        self.service.start()
        self.addCleanup(self.service.join, 5)
        self.addCleanup(self.service.request_stop)

    def open_trial(self):
        self.target.set("http://127.0.0.1:%d" % self.product.server_address[1])

    def ask(self, method="GET", path="/", headers=None, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            answer = connection.getresponse()
            return answer.status, dict(answer.getheaders()), answer.read().decode("utf-8")
        finally:
            connection.close()

    def test_the_relay_listens_on_loopback_only(self):
        self.assertEqual("127.0.0.1", self.service.server.socket.getsockname()[0])
        with self.assertRaises(ValueError):
            make_relay(ActionGuard(LOGIN, ENTRY, "t"), self.target, port=0, host="0.0.0.0")

    def test_no_trial_open_is_said_and_nothing_is_relayed(self):
        status, _, text = self.ask(headers={"Tailscale-User-Login": LOGIN})

        self.assertEqual(503, status)
        self.assertIn("Aucun Essai n’est ouvert", text)

    def test_another_member_of_the_tailnet_is_refused_and_reaches_nothing(self):
        self.open_trial()

        status, _, text = self.ask(headers={"Tailscale-User-Login": "someone@example.ts.net"})

        self.assertEqual(403, status)
        self.assertIn("Accès refusé", text)
        self.assertEqual([], FakeProduct.seen)

    def test_the_operator_reaches_the_product_at_its_root_as_from_its_own_host(self):
        self.open_trial()
        product = "http://127.0.0.1:%d" % self.product.server_address[1]

        status, headers, text = self.ask("POST", "/api/actions/essai?x=1", headers={
            "Tailscale-User-Login": LOGIN, "Tailscale-User-Name": "benjamin",
            "Host": "factory-vm.example.ts.net:8443", "X-Forwarded-Host": "factory-vm.example.ts.net",
            "Origin": ENTRY, "Referer": ENTRY + "/projet/notes?y=2",
            "Cookie": "cockpit_session=the-cockpits-own; essai_cockpit_session=product-token",
            "Content-Type": "application/json"}, body=b'{"a": 1}')

        self.assertEqual(200, status, text)
        received = json.loads(text)
        sent = {name.lower(): value for name, value in received["headers"].items()}
        self.assertEqual(("POST", "/api/actions/essai?x=1", '{"a": 1}'),
                         (received["method"], received["path"], received["body"]))
        # Nothing of Serve's identity, nor of the entry, reaches the product.
        self.assertEqual([], [name for name in sent if name.startswith("tailscale-user-")
                              or name.startswith("x-forwarded-")])
        self.assertEqual((product[len("http://"):], product, product + "/projet/notes?y=2"),
                         (sent["host"], sent["origin"], sent["referer"]))
        # The product gets its own cookie back, never the cockpit's.
        self.assertEqual("cockpit_session=product-token", sent["cookie"])
        self.assertTrue(headers["Set-Cookie"].startswith("essai_cockpit_session=product-token;"),
                        headers["Set-Cookie"])

    def test_a_product_that_no_longer_answers_is_said(self):
        self.target.set("http://127.0.0.1:9")

        status, _, text = self.ask(headers={"Tailscale-User-Login": LOGIN})

        self.assertEqual(502, status)
        self.assertIn("ne répond plus", text)


if __name__ == "__main__":
    unittest.main()
