#!/usr/bin/env python3
"""The synthetic identity proxy of an isolated cockpit (af-npz9v1.22,
before I af-cp4fzd; Spec af-fgcw0d, Testing Decisions 1 and 4): HTTPS on
127.0.0.1 with a certificate of the launch, the identity Tailscale Serve
would set, and nothing of the tailnet.

The proxy is read alone in front of a cockpit stand-in that answers the
headers it received, then in front of the cockpit its recipe launches.
"""

import json
import os
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "bin" / "cockpit-isolated"
HOME_CONTENT = ROOT / "config" / "cockpit-datasets" / "home-content.json"
RESULT_DATASETS = ("result-ready", "result-outage", "result-repairing")
sys.path.insert(0, str(ROOT / "tests" / "fixtures" / "cockpit" / "synthetic-city"))
import identity_proxy  # noqa: E402

BENJAMIN = "synthetic@example.ts.net"


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def fetch(url, ca, headers=None, data=None):
    """(status, headers, body) of one request through TLS checked against `ca`."""
    context = ssl.create_default_context(cafile=ca)
    request = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(request, timeout=10, context=context) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


class TheProxyAlone(unittest.TestCase):

    def setUp(self):
        class Echo(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                body = json.dumps({"path": self.path, "headers": dict(self.headers)}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        echo = ThreadingHTTPServer(("127.0.0.1", 0), Echo)
        threading.Thread(target=echo.serve_forever, daemon=True).start()
        self.addCleanup(echo.shutdown)
        home = tempfile.TemporaryDirectory()
        self.addCleanup(home.cleanup)
        announce_read, announce_write = os.pipe()
        alive_read, alive_write = os.pipe()
        threading.Thread(target=identity_proxy.serve, daemon=True,
                         args=(echo.server_address[1], home.name, announce_write, alive_read)).start()
        self.addCleanup(os.close, alive_write)
        with os.fdopen(announce_read, "rb") as announced:
            self.url = announced.read().decode("ascii")
        self.ca = os.path.join(home.name, "https", "cert.pem")

    def test_a_member_of_the_tailnet_reaches_the_cockpit_with_the_identity_serve_sets(self):
        status, _, body = fetch(self.url + "/usine?x=1", self.ca, {
            "X-Synthetic-Tailnet-Login": "autre@example.ts.net",
            "Tailscale-User-Login": BENJAMIN, "Tailscale-User-Profile-Pic": "forged"})
        self.assertEqual(200, status)
        seen = json.loads(body)
        self.assertEqual("/usine?x=1", seen["path"])
        headers = {name.lower(): value for name, value in seen["headers"].items()}
        self.assertEqual("autre@example.ts.net", headers["tailscale-user-login"])
        self.assertEqual("autre", headers["tailscale-user-name"])
        self.assertNotIn("tailscale-user-profile-pic", headers)
        self.assertNotIn("x-synthetic-tailnet-login", headers)

    def test_a_request_from_outside_the_tailnet_reaches_nothing(self):
        status, _, body = fetch(self.url + "/", self.ca, {"Tailscale-User-Login": BENJAMIN})
        self.assertEqual(403, status)
        self.assertIn(b"not a member of the tailnet", body)

    def test_its_refusal_says_how_a_member_of_the_tailnet_is_named(self):
        # Whoever tries the address with the header of Serve learns, from
        # the refusal, the one the synthetic proxy reads (I, af-cp4fzd:
        # the Evaluator met the refusal and nothing else).
        _, _, body = fetch(self.url + "/", self.ca, {"Tailscale-User-Login": BENJAMIN})
        self.assertIn(b"X-Synthetic-Tailnet-Login", body)

    def test_it_speaks_https_with_the_certificate_of_the_launch_only(self):
        with self.assertRaises(OSError):
            urllib.request.urlopen(self.url.replace("https:", "http:") + "/", timeout=5)
        with self.assertRaises(OSError):
            urllib.request.urlopen(self.url + "/", timeout=5, context=ssl.create_default_context())


class BehindTheProxy(unittest.TestCase):

    def dataset(self, **extra):
        dataset = {**json.loads(HOME_CONTENT.read_text(encoding="utf-8")), **extra}
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name, "dataset.json")
        path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
        return path

    def launched(self, path):
        """The environment of the cockpit the recipe serves, once it answers."""
        port = free_port()
        proc = subprocess.Popen([sys.executable, str(RECIPE), "--port", str(port), "--dataset", str(path)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(proc.wait, 30)
        self.addCleanup(proc.terminate)
        deadline = time.monotonic() + 30
        while True:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=2) as response:
                    if response.status == 200:
                        break
            except (urllib.error.URLError, ConnectionError, OSError):
                pass
            self.assertLess(time.monotonic(), deadline, "the cockpit never answered")
            time.sleep(0.2)
        pairs = Path(f"/proc/{proc.pid}/environ").read_bytes().decode().split("\0")
        return dict(pair.split("=", 1) for pair in pairs if "=" in pair)

    def test_the_cockpit_is_served_through_https_to_a_member_of_the_tailnet(self):
        env = self.launched(self.dataset(https_identity_proxy=True))
        url, ca = env["COCKPIT_TRIAL_HTTPS_URL"], env["COCKPIT_TRIAL_HTTPS_CA"]
        self.assertTrue(url.startswith("https://127.0.0.1:"), url)
        self.assertEqual(url, env["COCKPIT_ALLOWED_ORIGIN"])
        status, _, body = fetch(url + "/api/status", ca, {"X-Synthetic-Tailnet-Login": BENJAMIN})
        self.assertEqual(200, status)
        self.assertIn("gc", json.loads(body))
        self.assertEqual(403, fetch(url + "/api/status", ca)[0])
        # The supervisor's API is not behind the proxy: its address answers the cockpit's 404.
        status, _, body = fetch(url + "/v0/cities", ca, {"X-Synthetic-Tailnet-Login": BENJAMIN})
        self.assertNotEqual(200, status)

    def test_the_result_trials_use_the_identity_proxy_and_their_disposable_tracker(self):
        for name in RESULT_DATASETS:
            with self.subTest(dataset=name):
                path = ROOT / "config" / "cockpit-datasets" / f"{name}.json"
                env = self.launched(path)
                self.assertEqual(Path(env["HOME"], "tracker.json"), Path(env["FAKE_BD_STATE_FILE"]))
                url, ca = env["COCKPIT_TRIAL_HTTPS_URL"], env["COCKPIT_TRIAL_HTTPS_CA"]
                status, _, body = fetch(url + "/api/status", ca, {"X-Synthetic-Tailnet-Login": BENJAMIN})
                self.assertEqual(200, status)
                self.assertIn("gc", json.loads(body))
                if name == "result-ready":
                    visible = json.loads(path.read_text(encoding="utf-8"))["visible_text"]
                    self.assertIn("Essai ↗", visible)
                    self.assertIn("Avis", visible)
                    self.assertRegex(visible, "['’]")

    def test_without_it_the_cockpit_has_no_https(self):
        env = self.launched(self.dataset())
        self.assertNotIn("COCKPIT_TRIAL_HTTPS_URL", env)

    def test_a_proxy_that_is_not_true_or_false_is_refused(self):
        proc = subprocess.run([sys.executable, str(RECIPE), "--port", "1", "--dataset",
                               str(self.dataset(https_identity_proxy="oui"))],
                              capture_output=True, text=True, timeout=60)
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("https_identity_proxy", proc.stderr)


if __name__ == "__main__":
    unittest.main()
