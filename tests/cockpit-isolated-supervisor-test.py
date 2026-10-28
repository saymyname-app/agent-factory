#!/usr/bin/env python3
"""The synthetic supervisor of an isolated cockpit for a clean stop
(af-npz9v1.21, before H af-69qhlk; Spec af-fgcw0d, Testing Decision 4):
it takes the two writes the installed supervisor publishes for a stop, and
a dataset may say the host restarted during a stop
(`host_restarted_during_stop`).

The cockpit is launched by its recipe, `bin/cockpit-isolated`, and read
by GET /usine, as the criterion tests of H read it.
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
DATASETS = ROOT / "config" / "cockpit-datasets"
sys.path.insert(0, str(ROOT / "tests" / "fixtures" / "cockpit" / "core"))
from fake_gc import FakeGc  # noqa: E402


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def send(method, url, body=None):
    """(status, JSON answer) of one write."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


class TheWrites(unittest.TestCase):

    def setUp(self):
        self.gc = FakeGc(city="ville")
        self.gc.set_sessions([{"id": "s-1", "template": "auteur", "session_name": "auteur-1", "running": True,
                               "last_active": "2026-10-27T20:00:00Z"}])
        self.gc.start()
        self.addCleanup(self.gc.stop)
        self.city = self.gc.base_url + "/v0/city/ville"

    def read(self, rest):
        with urllib.request.urlopen(f"{self.city}/{rest}", timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_the_city_is_suspended_and_resumed_by_its_patch(self):
        self.assertEqual((200, {"status": "ok"}), send("PATCH", self.city, {"suspended": True}))
        self.assertTrue(self.read("status")["suspended"])
        self.assertEqual((200, {"status": "ok"}), send("PATCH", self.city, {"suspended": False}))
        self.assertFalse(self.read("status")["suspended"])
        self.assertEqual(422, send("PATCH", self.city, {"suspended": "oui"})[0])

    def test_a_session_is_stopped_by_its_post(self):
        self.assertEqual((200, {"id": "s-1", "status": "ok"}), send("POST", self.city + "/session/s-1/stop"))
        [session] = self.read("sessions")["items"]
        self.assertFalse(session["running"])
        self.assertEqual(404, send("POST", self.city + "/session/s-9/stop")[0])

    def test_every_write_is_kept_and_another_one_is_not_taken(self):
        self.assertEqual(404, send("POST", self.city + "/session/s-1/kill")[0])
        send("PATCH", self.city, {"suspended": True})
        self.assertEqual([("POST", "/v0/city/ville/session/s-1/kill"), ("PATCH", "/v0/city/ville")],
                         [(write["method"], write["path"]) for write in self.gc.writes])
        self.assertTrue(self.read("sessions")["items"][0]["running"], "a write it does not take changed a session")


class AHostRestartedDuringAStop(unittest.TestCase):

    def usine(self, dataset, until):
        """The page /usine of the cockpit launched on `dataset`, once it
        holds `until`."""
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name, "dataset.json")
        path.write_text(json.dumps(dataset, ensure_ascii=False), encoding="utf-8")
        port = free_port()
        proc = subprocess.Popen([sys.executable, str(RECIPE), "--port", str(port), "--dataset", str(path)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(proc.wait, 30)
        self.addCleanup(proc.terminate)
        deadline, page = time.monotonic() + 40, ""
        while until not in page:
            self.assertLess(time.monotonic(), deadline, f"« {until} » never shown: {page[-2000:]}")
            time.sleep(0.5)
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/usine", timeout=3) as response:
                    page = response.read().decode("utf-8")
            except (urllib.error.URLError, ConnectionError, OSError):
                pass
        return page

    def dataset(self, name):
        return json.loads((DATASETS / f"{name}.json").read_text(encoding="utf-8"))

    def test_an_unsuspended_supervisor_after_the_restart_is_an_interrupted_stop(self):
        dataset = {**self.dataset("home-content"), "host_restarted_during_stop": True}
        # Its tickets hold no session: the photo has no assignment to lose.
        self.usine(dataset, "Arrêt interrompu")

    def test_a_supervisor_still_suspended_after_the_restart_goes_on_with_the_stop(self):
        dataset = {**self.dataset("factory-suspended"), "host_restarted_during_stop": True}
        page = self.usine(dataset, "Arrêtée proprement")
        self.assertNotIn("Arrêt interrompu", page)

    def test_a_dataset_that_says_nothing_starts_with_no_stop(self):
        page = self.usine(self.dataset("home-content"), "En marche")
        self.assertNotIn("Arrêt interrompu", page)

    def test_a_restart_that_is_not_true_or_false_is_refused(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name, "dataset.json")
        path.write_text(json.dumps({**self.dataset("home-content"), "host_restarted_during_stop": "oui"}),
                        encoding="utf-8")
        proc = subprocess.run([sys.executable, str(RECIPE), "--port", "1", "--dataset", str(path)],
                              capture_output=True, text=True, timeout=60)
        self.assertNotEqual(0, proc.returncode)
        self.assertIn("host_restarted_during_stop", proc.stderr)


if __name__ == "__main__":
    unittest.main()
