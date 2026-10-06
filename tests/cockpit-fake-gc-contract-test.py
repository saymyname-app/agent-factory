#!/usr/bin/env python3
# ci: local-only — requires the running gc supervisor, not just the fake
"""The cockpit's fake gc must answer like the real supervisor (af-mjfvwx).

The first fake served ``/status`` as JSON and ``/events`` as an SSE stream;
the real supervisor serves its HTML dashboard on both, so the cockpit was
green in tests and never read gc on the live host. This test asks the same
questions of the installed supervisor (``COCKPIT_GC_BASE_URL``, default
``http://127.0.0.1:8372``, read-only GETs) and of
``tests/fixtures/cockpit/core/fake_gc.py``, and fails on any difference in
status code, content type, JSON keys the cockpit reads, or stream framing.
"""
import json
import os
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "fixtures" / "cockpit" / "core"))

from fake_gc import CITY as FAKE_CITY  # noqa: E402
from fake_gc import FakeGc  # noqa: E402

REAL_BASE_URL = os.environ.get("COCKPIT_GC_BASE_URL", "http://127.0.0.1:8372")

# Keys lib/cockpit/core/gc_client.py reads, per endpoint.
STATUS_KEYS = {"suspended", "agents", "work"}
READY_KEYS = {"items", "total"}
EVENT_KEYS = {"seq", "type", "ts", "actor", "subject", "payload"}


def get(base_url, path, timeout=20):
    """(status, main content type, body bytes) — a 4xx is an answer too."""
    req = urllib.request.Request(base_url + path)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, _main_type(resp), resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, _main_type(exc), exc.read()


def _main_type(resp):
    return resp.headers.get("Content-Type", "").split(";")[0].strip()


def first_frames(base_url, path, wanted, timeout=40):
    """Read the stream until every event name in ``wanted`` was seen;
    returns {event name: parsed data of its first frame}."""
    seen = {}
    req = urllib.request.Request(base_url + path, headers={"Accept": "text/event-stream"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        assert _main_type(resp) == "text/event-stream", _main_type(resp)
        name, data = "", []
        for raw in resp:
            line = raw.decode("utf-8").rstrip("\r\n")
            if line == "":
                if name and name not in seen:
                    seen[name] = json.loads("\n".join(data))
                name, data = "", []
                if wanted <= set(seen):
                    return seen
            elif line.startswith("event:"):
                name = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data.append(line[len("data:"):].lstrip())
    return seen


class FakeGcAnswersLikeTheRealOne(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = FakeGc(heartbeat_seconds=0.2).start()
        cls.fake_url = cls.fake.base_url
        status, content_type, body = get(REAL_BASE_URL, "/v0/cities")
        assert (status, content_type) == (200, "application/json"), "real gc unreachable at " + REAL_BASE_URL
        cls.real_city = json.loads(body)["items"][0]["name"]

    @classmethod
    def tearDownClass(cls):
        cls.fake.stop()

    def both(self, path_template):
        real = get(REAL_BASE_URL, path_template % self.real_city if "%s" in path_template else path_template)
        fake = get(self.fake_url, path_template % FAKE_CITY if "%s" in path_template else path_template)
        self.assertEqual(real[:2], fake[:2], "status / content type differ on " + path_template)
        return real[2], fake[2]

    def test_dashboard_paths_are_html_not_an_api(self):
        for path in ("/events", "/status"):
            self.both(path)
            self.assertEqual("text/html", get(self.fake_url, path)[1])

    def test_unknown_paths_and_unknown_city(self):
        self.both("/v0/status")
        real = get(REAL_BASE_URL, "/v0/city/no-such-city-xyz/status")
        fake = get(self.fake_url, "/v0/city/no-such-city-xyz/status")
        self.assertEqual(real[:2], fake[:2])
        self.assertEqual(set(json.loads(real[2])), set(json.loads(fake[2])))

    def test_cities(self):
        real, fake = (json.loads(b) for b in self.both("/v0/cities"))
        self.assertEqual(set(real), set(fake))
        self.assertEqual(set(real["items"][0]), set(fake["items"][0]))

    def test_city_status(self):
        real, fake = (json.loads(b) for b in self.both("/v0/city/%s/status"))
        self.assertLessEqual(STATUS_KEYS, set(real))
        self.assertLessEqual(set(fake), set(real) | {"partial", "partial_errors"})
        for key in ("agents", "work"):
            self.assertEqual(set(real[key]), set(fake[key]), key)
        self.assertIsInstance(real["suspended"], bool)

    def test_partial_status_shape(self):
        self.fake.set_status(partial_errors=["x"])
        try:
            fake = json.loads(get(self.fake_url, "/v0/city/%s/status" % FAKE_CITY)[2])
        finally:
            self.fake.set_status(partial_errors=[])
        self.assertIs(True, fake["partial"])
        self.assertIsInstance(fake["partial_errors"], list)
        real = json.loads(get(REAL_BASE_URL, "/v0/city/%s/status" % self.real_city)[2])
        if real.get("partial"):
            self.assertIs(True, real["partial"])
            self.assertIsInstance(real["partial_errors"], list)

    def test_ready_beads(self):
        real, fake = (json.loads(b) for b in self.both("/v0/city/%s/beads/ready"))
        self.assertEqual(READY_KEYS, set(real))
        self.assertEqual(READY_KEYS, set(fake))
        if real["items"]:
            self.assertIn("metadata", real["items"][0])

    def test_sessions(self):
        self.fake.set_sessions([{
            "id": "af-s1", "kind": "agent", "template": "factory-worker", "state": "active", "title": "t",
            "session_name": "factory-worker", "running": True, "last_active": "2026-10-06T15:07:21+02:00",
            "active_bead": "af-b1",
        }])
        try:
            real, fake = (json.loads(b) for b in self.both("/v0/city/%s/sessions"))
        finally:
            self.fake.set_sessions([])
        self.assertEqual({"items", "total"}, set(real))
        self.assertEqual({"items", "total"}, set(fake))
        # Every field the cockpit reads exists on a real session; active_bead
        # only on the ones holding a ticket.
        for item in real["items"]:
            self.assertLessEqual({"id", "template", "running", "last_active"}, set(item))
        self.assertLessEqual(set(fake["items"][0]) - {"active_bead"}, set(real["items"][0]) | {"session_name"})

    def test_city_event_stream_framing(self):
        real = first_frames(REAL_BASE_URL, "/v0/city/%s/events/stream" % self.real_city, {"heartbeat"})
        self.fake.emit("bead.closed", subject="af-fake")  # nobody listening yet: harmless
        import threading

        timer = threading.Timer(0.5, lambda: self.fake.emit("bead.closed", subject="af-fake"))
        timer.start()
        try:
            fake = first_frames(self.fake_url, "/v0/city/%s/events/stream" % FAKE_CITY, {"heartbeat", "event"})
        finally:
            timer.cancel()
        self.assertEqual(set(real["heartbeat"]), set(fake["heartbeat"]))
        self.assertEqual(EVENT_KEYS, set(fake["event"]))
        if "event" in real:
            self.assertLessEqual(EVENT_KEYS, set(real["event"]))


if __name__ == "__main__":
    unittest.main()
