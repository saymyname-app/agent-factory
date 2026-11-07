#!/usr/bin/env python3
"""The operator in front of an isolated cockpit, at the address of its launch
(A2, af-ocz64w; Spec af-fgcw0d, Accès hôte and Testing Decisions 8, « le
cockpit lancé par sa recette isolée […] piloté en HTTP et au navigateur »).

In service the operator's browser reaches the cockpit through Tailscale
Serve, which names him; a browser at the address of a launch is named by no
one, and every gesture is refused (403 identity). A dataset that says
`"operator_front": true` puts at that address a synthetic Serve that names
whoever connects the operator of the launch: the cockpit keeps every check
of its guard, Origin and session cookie included.
"""

import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "bin" / "cockpit-isolated"
HOME_CONTENT = ROOT / "config" / "cockpit-datasets" / "home-content.json"
RESULT_ESSAI = ROOT / "config" / "cockpit-datasets" / "result-essai.json"
# What Essai answers on a chantier without a result: the action ran.
NO_RESULT = "Ce chantier n’a pas de résultat à essayer : rien n’est lancé."


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class OperatorFront(unittest.TestCase):

    def dataset(self, **extra):
        dataset = {**json.loads(HOME_CONTENT.read_text(encoding="utf-8")), **extra}
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name, "dataset.json")
        path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
        return path

    def launched(self, path):
        """The address of the cockpit the recipe serves, once it answers."""
        port = free_port()
        proc = subprocess.Popen([sys.executable, str(RECIPE), "--port", str(port), "--dataset", str(path)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(proc.wait, 30)
        self.addCleanup(proc.terminate)
        address = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + 30
        while True:
            try:
                with urllib.request.urlopen(address + "/api/status", timeout=2) as response:
                    if response.status == 200:
                        return address
            except (urllib.error.URLError, ConnectionError, OSError):
                pass
            self.assertLess(time.monotonic(), deadline, "the cockpit never answered")
            time.sleep(0.2)

    def essai(self, address, headers=None, origin=None):
        """Essai asked as a browser does from a page served at `address`:
        its session cookie and its Origin. (status, answer)."""
        with urllib.request.urlopen(address + "/", timeout=20) as response:
            cookie = (response.headers.get("Set-Cookie") or "").split(";", 1)[0]
        request = urllib.request.Request(
            address + "/api/actions/essai", method="POST",
            data=json.dumps({"chantier": "aucun", "commit": "0" * 40}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Origin": origin or address, "Cookie": cookie,
                     **(headers or {})})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_a_gesture_at_the_address_of_the_launch_is_the_operators(self):
        status, answer = self.essai(self.launched(self.dataset(operator_front=True)))
        self.assertNotEqual(403, status, answer)
        self.assertEqual(NO_RESULT, answer.get("error"), answer)

    def test_a_login_the_client_sends_is_not_the_one_the_cockpit_reads(self):
        status, answer = self.essai(self.launched(self.dataset(operator_front=True)),
                                    {"Tailscale-User-Login": "autre@example.ts.net"})
        self.assertEqual(NO_RESULT, answer.get("error"), (status, answer))

    def test_the_cockpit_still_refuses_another_origin(self):
        status, answer = self.essai(self.launched(self.dataset(operator_front=True)),
                                    origin="http://elsewhere.example")
        self.assertEqual((403, {"error": "origin"}), (status, answer))

    def test_without_it_a_gesture_at_the_address_is_named_by_no_one(self):
        self.assertEqual((403, {"error": "identity"}), self.essai(self.launched(self.dataset())))

    def test_a_front_that_is_not_true_or_false_or_is_beside_https_is_refused(self):
        for extra in ({"operator_front": "oui"}, {"operator_front": True, "https_identity_proxy": True}):
            with self.subTest(**{k: str(v) for k, v in extra.items()}):
                proc = subprocess.run([sys.executable, str(RECIPE), "--port", "1", "--dataset",
                                       str(self.dataset(**extra))], capture_output=True, text=True, timeout=60)
                self.assertNotEqual(0, proc.returncode)
                self.assertIn("operator_front", proc.stderr)

    def test_the_trial_of_essai_puts_the_operator_at_its_address(self):
        self.assertIs(True, json.loads(RESULT_ESSAI.read_text(encoding="utf-8")).get("operator_front"))


if __name__ == "__main__":
    unittest.main()
