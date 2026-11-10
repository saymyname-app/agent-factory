#!/usr/bin/env python3
"""The fake gc gives its journal by pages, as gc 1.5.0 does (af-yxxa68).

The fake beside `bin/cockpit-isolated` gave no journal at all, so a session
sent while the cockpit was stopped could not be missed then read back by
pages: the defect R20 repairs (af-3l6hbt, F1.38) could not be seen red.
These cases ask the fake over HTTP; `tests/cockpit-fake-gc-contract-test.py`
(local only) holds the same answers to the installed supervisor.
"""
import json
import sys
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "fixtures" / "cockpit" / "core"))

from fake_gc import CITY, FakeGc  # noqa: E402


class FakeGcJournal(unittest.TestCase):
    def setUp(self):
        self.gc = FakeGc().start()
        self.addCleanup(self.gc.stop)

    def get(self, rest):
        """(status, content type, parsed body) of GET /v0/city/<city>/<rest>."""
        url = "%s/v0/city/%s/%s" % (self.gc.base_url, CITY, rest)
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                return resp.status, resp.headers["Content-Type"], json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            return exc.code, exc.headers["Content-Type"], json.loads(exc.read())

    def test_120_events_come_in_pages_of_50_50_20_newest_first(self):
        for n in range(120):
            self.gc.emit("session.woke", subject="s-%d" % n)
        pages, query = [], "events?limit=50"
        while True:
            status, _, body = self.get(query)
            self.assertEqual(200, status)
            self.assertEqual(120, body["total"])
            pages.append([event["seq"] for event in body["items"]])
            if "next_cursor" not in body:
                break
            query = "events?limit=50&cursor=" + body["next_cursor"]
        self.assertEqual([50, 50, 20], [len(page) for page in pages])
        self.assertEqual(list(range(120, 0, -1)), [seq for page in pages for seq in page])

    def test_without_limit_a_page_holds_100(self):
        for n in range(101):
            self.gc.emit("bead.closed", subject="af-%d" % n)
        for query in ("events", "events?limit=0"):
            status, _, body = self.get(query)
            self.assertEqual(200, status)
            self.assertEqual(100, len(body["items"]))
            self.assertIn("next_cursor", body)
        status, _, body = self.get("events?cursor=" + body["next_cursor"])
        self.assertEqual(([1], 101), ([e["seq"] for e in body["items"]], body["total"]))
        self.assertNotIn("next_cursor", body)

    def test_type_and_actor_filter_the_journal(self):
        self.gc.emit("bead.closed", subject="af-1")
        self.gc.emit("session.woke", subject="s-1")
        status, _, body = self.get("events?type=session.woke&actor=controller")
        self.assertEqual((200, ["s-1"], 1), (status, [e["subject"] for e in body["items"]], body["total"]))

    def test_an_event_keeps_the_time_actor_and_keys_it_was_logged_with(self):
        self.gc.emit("session.woke", subject="factory-worker", payload={"session_id": "s-1"},
                     ts="2026-11-10T16:00:00+00:00", actor="gc", session_id="s-1")
        _, _, body = self.get("events")
        self.assertEqual({"seq": 1, "type": "session.woke", "ts": "2026-11-10T16:00:00+00:00", "actor": "gc",
                          "subject": "factory-worker", "payload": {"session_id": "s-1"}, "session_id": "s-1"},
                         body["items"][0])

    def test_refuses_what_gc_refuses(self):
        cases = {
            "events?limit=1001": (422, "validation-failed"),
            "events?limit=-1": (422, "validation-failed"),
            "events?limit=abc": (422, "validation-failed"),
            "events?cursor=garbage": (400, "invalid-cursor"),
            "events?cursor=v1:eyJrIjoic3MiLCJzIjoxfQ": (400, "invalid-cursor"),  # a sessions cursor
            "sessions?limit=1001": (422, "validation-failed"),
        }
        for query, (code, problem) in cases.items():
            with self.subTest(query=query):
                status, content_type, body = self.get(query)
                self.assertEqual((code, "application/problem+json", problem),
                                 (status, content_type, body["code"]))

    def test_blocking_and_since_reads_are_refused_not_ignored(self):
        for query in ("events?index=3", "events?wait=5s", "events?since=5m"):
            with self.subTest(query=query):
                status, _, body = self.get(query)
                self.assertEqual((400, "not-in-fake"), (status, body["code"]))

    def test_sessions_come_in_pages_in_the_order_given(self):
        self.gc.set_sessions([{"id": "s-%d" % n, "running": True} for n in range(3)])
        status, _, first = self.get("sessions?limit=2")
        self.assertEqual((200, ["s-0", "s-1"], 3), (status, [s["id"] for s in first["items"]], first["total"]))
        status, _, second = self.get("sessions?limit=2&cursor=" + first["next_cursor"])
        self.assertEqual((200, ["s-2"]), (status, [s["id"] for s in second["items"]]))
        self.assertNotIn("next_cursor", second)


if __name__ == "__main__":
    unittest.main()
