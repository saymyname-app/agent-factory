"""Notification engine tests (bead af-9jrvmi, T17 — Spec af-oohx2x).

``NotificationEngine.tick()`` has no CLI or HTTP surface of its own (that
wiring, if any, is a later ticket's job — same precedent as
cockpit-heartbeat-test.py for the T18 heartbeat emitter), so this test
drives it directly, with a fake clock and a fake Pushover adapter that
records instead of ever reaching the network (Testing Decisions: "aucun
test n'atteint [...] Pushover").
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "notify"
sys.path.insert(0, str(ROOT / "lib"))

from cockpit.notify import content  # noqa: E402
from cockpit.notify.engine import CHANNEL_DOWN_MESSAGE, NotificationEngine  # noqa: E402
from cockpit.notify.model import PRIORITY_A_FAIRE, PRIORITY_URGENT  # noqa: E402
from cockpit.notify.pushover import PushoverAdapter, PushoverError  # noqa: E402
from cockpit.notify.secrets import read_secrets_from_file  # noqa: E402
from cockpit.notify.state_store import InMemoryStateStore, JsonFileStateStore  # noqa: E402
from cockpit.requests.model import (  # noqa: E402
    A_FAIRE,
    OperatorRequest,
    QUAND_TU_VEUX,
    TYPE_ESCALATION,
    TYPE_PROPOSAL,
    URGENT,
)


class FakeClock:
    def __init__(self, start=0.0):
        self._now = start

    def now(self):
        return self._now

    def advance(self, seconds):
        self._now += seconds


class FakeAdapter:
    """Records every send; can be told to fail the next N attempts."""

    def __init__(self, e2e=True):
        self.calls = []
        self.fail_next = 0
        self._e2e = e2e

    def e2e_available(self):
        return self._e2e

    def send(self, title, message, priority):
        if priority not in (0, 1):
            raise AssertionError("priority %r must never be used" % (priority,))
        self.calls.append({"title": title, "message": message, "priority": priority})
        if self.fail_next > 0:
            self.fail_next -= 1
            raise RuntimeError("simulated send failure")


def cockpit_url(req_id):
    return "https://cockpit.local/d/%s" % (req_id or "")


def make_request(
    req_id,
    niveau,
    req_type=TYPE_ESCALATION,
    quoi="Un secret marqueur : SECRET-DONNEE-PRODUIT ne doit jamais apparaître",
    projet="usine",
    acquittee=False,
    reportee=False,
):
    return OperatorRequest(
        id=req_id,
        type=req_type,
        niveau=niveau,
        quoi=quoi,
        pourquoi="Un corps de bead confidentiel qui ne doit jamais fuiter dans un push",
        que_faire=[{"lettre": "a", "option": "Faire X", "consequence": "Y", "recommande": False, "raison": ""}],
        projet=projet,
        depuis_quand=0.0,
        verifie_a=0.0,
        lien=req_id,
        acquittee=acquittee,
        reportee=reportee,
    )


def new_engine(adapter=None, state_store=None, clock=None):
    clock = clock or FakeClock()
    adapter = adapter or FakeAdapter()
    state_store = state_store if state_store is not None else InMemoryStateStore()
    return NotificationEngine(adapter, state_store, clock, cockpit_url), adapter, clock, state_store


class NotificationEngineTest(unittest.TestCase):
    # ------------------------------------------------------------------
    # AC1 — priorities, one push per request, no duplicate after restart.
    # ------------------------------------------------------------------
    def test_priorities_and_single_push_per_request(self):
        engine, adapter, clock, _ = new_engine()
        urgent = make_request("af-urgent", URGENT)
        a_faire = make_request("af-afaire", A_FAIRE)
        quand_tu_veux = make_request("af-qtv", QUAND_TU_VEUX, req_type=TYPE_PROPOSAL)

        engine.tick([urgent, a_faire, quand_tu_veux], now=0)

        self.assertEqual(2, len(adapter.calls))
        priorities = {c["priority"] for c in adapter.calls}
        self.assertEqual({PRIORITY_URGENT, PRIORITY_A_FAIRE}, priorities)

        # Same requests, same tick position immediately after: no repeat.
        engine.tick([urgent, a_faire, quand_tu_veux], now=1)
        self.assertEqual(2, len(adapter.calls))

    def test_no_duplicate_after_cockpit_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = str(Path(tmp) / "notify-state.json")
            urgent = make_request("af-urgent", URGENT)

            clock1 = FakeClock()
            adapter1 = FakeAdapter()
            engine1 = NotificationEngine(
                adapter1, JsonFileStateStore(state_path), clock1, cockpit_url
            )
            engine1.tick([urgent], now=0)
            self.assertEqual(1, len(adapter1.calls))

            # "Restart": a brand-new engine/adapter, same persisted file.
            clock2 = FakeClock()
            adapter2 = FakeAdapter()
            engine2 = NotificationEngine(
                adapter2, JsonFileStateStore(state_path), clock2, cockpit_url
            )
            engine2.tick([urgent], now=1)
            self.assertEqual([], adapter2.calls)

    # ------------------------------------------------------------------
    # AC2 — 2 h reminder, stops at ack; push at defer deadline; end push
    # for a resolved Urgent.
    # ------------------------------------------------------------------
    def test_reminder_every_two_hours_stops_at_ack(self):
        engine, adapter, clock, _ = new_engine()
        urgent = make_request("af-urgent", URGENT)

        engine.tick([urgent], now=clock.now())
        self.assertEqual(1, len(adapter.calls))

        clock.advance(7199)
        engine.tick([urgent], now=clock.now())
        self.assertEqual(1, len(adapter.calls), "no reminder before 2h elapsed")

        clock.advance(1)  # exactly 2h since the initial push
        engine.tick([urgent], now=clock.now())
        self.assertEqual(2, len(adapter.calls), "reminder fires at 2h")

        acked = make_request("af-urgent", URGENT, acquittee=True)
        clock.advance(7200)
        engine.tick([acked], now=clock.now())
        self.assertEqual(2, len(adapter.calls), "acquitter stops the reminder")

        clock.advance(7200)
        engine.tick([acked], now=clock.now())
        self.assertEqual(2, len(adapter.calls), "still no reminder while acked")

    def test_deferred_urgent_gets_no_push_until_its_deadline(self):
        engine, adapter, clock, _ = new_engine()
        urgent = make_request("af-urgent", URGENT)

        engine.tick([urgent], now=clock.now())
        self.assertEqual(1, len(adapter.calls))

        deferred = make_request("af-urgent", URGENT, reportee=True)
        clock.advance(7200)  # would be reminder time if not deferred
        engine.tick([deferred], now=clock.now())
        self.assertEqual(1, len(adapter.calls), "no reminder while deferred")

        clock.advance(3600)
        engine.tick([deferred], now=clock.now())
        self.assertEqual(1, len(adapter.calls), "still nothing while deferred")

        # Deadline reached: back to normal visibility.
        clock.advance(1)
        engine.tick([urgent], now=clock.now())
        self.assertEqual(2, len(adapter.calls), "exactly one push at the deadline")

        engine.tick([urgent], now=clock.now())
        self.assertEqual(2, len(adapter.calls), "no duplicate right after the deadline push")

    def test_resolved_urgent_gets_an_end_push_afaire_gets_none(self):
        engine, adapter, clock, _ = new_engine()
        urgent = make_request("af-urgent", URGENT)
        a_faire = make_request("af-afaire", A_FAIRE)

        engine.tick([urgent, a_faire], now=clock.now())
        self.assertEqual(2, len(adapter.calls))

        clock.advance(10)
        engine.tick([], now=clock.now())  # both resolved at the source
        self.assertEqual(3, len(adapter.calls), "exactly one end push, for the Urgent only")
        self.assertIn(content.RESOLVED_TITLE, adapter.calls[-1]["title"])

        clock.advance(10)
        engine.tick([], now=clock.now())
        self.assertEqual(3, len(adapter.calls), "no repeat end push")

    # ------------------------------------------------------------------
    # AC3 — hourly cap of 5, then one grouped push.
    # ------------------------------------------------------------------
    def test_hourly_cap_then_one_grouped_push(self):
        engine, adapter, clock, _ = new_engine()
        requests = [make_request("af-%d" % i, A_FAIRE) for i in range(7)]

        engine.tick(requests, now=clock.now())

        self.assertEqual(6, len(adapter.calls), "5 individual + 1 grouped")
        grouped = [c for c in adapter.calls if "autres demandes" in c["title"]]
        self.assertEqual(1, len(grouped))
        self.assertIn("2 autres demandes — voir le cockpit", grouped[0]["title"])
        for call in adapter.calls:
            self.assertIn(call["priority"], (0, 1))

        # The 7 requests are not retried individually next tick even
        # though only 6 of them were ever "sent" for real -- the grouped
        # push substitutes for the overflow, it does not queue a retry.
        clock.advance(1)
        engine.tick(requests, now=clock.now())
        self.assertEqual(6, len(adapter.calls))

    def test_urgent_is_never_starved_by_the_cap(self):
        engine, adapter, clock, _ = new_engine()
        a_faire_flood = [make_request("af-flood-%d" % i, A_FAIRE) for i in range(6)]
        urgent = make_request("af-urgent", URGENT)

        engine.tick(a_faire_flood + [urgent], now=clock.now())

        individual_titles = [c["title"] for c in adapter.calls if "autres demandes" not in c["title"]]
        self.assertTrue(
            any(c["priority"] == PRIORITY_URGENT for c in adapter.calls),
            "the Urgent request must be sent individually, not swallowed by the cap",
        )

    # ------------------------------------------------------------------
    # AC4 — retry on failure, "notification non livrée", health after 15
    # min of failure.
    # ------------------------------------------------------------------
    def test_retry_undelivered_flag_and_health_after_fifteen_minutes(self):
        engine, adapter, clock, _ = new_engine()
        adapter.fail_next = 99
        urgent = make_request("af-urgent", URGENT)

        engine.tick([urgent], now=clock.now())
        self.assertIn("af-urgent", engine.undelivered())
        self.assertEqual([], engine.health_issues(), "not yet 15 minutes of failure")

        clock.advance(899)
        engine.tick([urgent], now=clock.now())
        self.assertEqual([], engine.health_issues())

        clock.advance(2)
        engine.tick([urgent], now=clock.now())
        self.assertEqual([CHANNEL_DOWN_MESSAGE], engine.health_issues())

        # A later successful send clears both the undelivered flag and
        # the health issue -- never a retroactive erasure, a new better
        # reading (spec .36 in spirit).
        adapter.fail_next = 0
        clock.advance(10)
        engine.tick([urgent], now=clock.now())
        self.assertNotIn("af-urgent", engine.undelivered())
        self.assertEqual([], engine.health_issues())

    # ------------------------------------------------------------------
    # AC5 — no real-person data, secret, bead body, or product data in a
    # push.
    # ------------------------------------------------------------------
    def test_push_content_excludes_pourquoi_and_que_faire(self):
        engine, adapter, clock, _ = new_engine(adapter=FakeAdapter(e2e=True))
        urgent = make_request("af-urgent", URGENT, quoi="Approuver la Spec du Planning Run")
        engine.tick([urgent], now=clock.now())

        call = adapter.calls[0]
        combined = call["title"] + " " + call["message"]
        self.assertNotIn("corps de bead confidentiel", combined)
        self.assertIn("Approuver la Spec du Planning Run", combined)
        self.assertIn(urgent.projet, combined)
        self.assertIn(cockpit_url(urgent.id), combined)

    def test_quoi_omitted_when_channel_is_not_end_to_end_encrypted(self):
        engine, adapter, clock, _ = new_engine(adapter=FakeAdapter(e2e=False))
        urgent = make_request("af-urgent", URGENT, quoi="Approuver la Spec du Planning Run")
        engine.tick([urgent], now=clock.now())

        call = adapter.calls[0]
        combined = call["title"] + " " + call["message"]
        self.assertNotIn("Approuver la Spec du Planning Run", combined)

    def test_quoi_is_truncated(self):
        engine, adapter, clock, _ = new_engine()
        long_quoi = "x" * 500
        urgent = make_request("af-urgent", URGENT, quoi=long_quoi)
        engine.tick([urgent], now=clock.now())

        call = adapter.calls[0]
        self.assertNotIn(long_quoi, call["message"])
        self.assertLess(len(call["message"]), 500)

    # ------------------------------------------------------------------
    # AC6 — missing/invalid secret file -> health; journal + test button
    # work; priority 2 is never used.
    # ------------------------------------------------------------------
    def test_missing_or_invalid_secrets_file_reads_as_none(self):
        self.assertIsNone(read_secrets_from_file("/nonexistent/path/should-not-exist"))
        self.assertIsNone(read_secrets_from_file(None))
        self.assertIsNone(read_secrets_from_file(""))
        self.assertIsNone(read_secrets_from_file(str(FIXTURES / "invalid-secrets.json")))
        self.assertIsNone(read_secrets_from_file(str(FIXTURES / "incomplete-secrets.json")))

    def test_valid_secrets_file_is_read(self):
        secrets = read_secrets_from_file(str(FIXTURES / "valid-secrets.json"))
        self.assertEqual(
            {"token", "user_key", "e2e_key"}, set(secrets.keys())
        )
        self.assertTrue(all(secrets.values()))

    def test_pushover_adapter_refuses_priority_two(self):
        adapter = PushoverAdapter(secrets_loader=lambda: {"token": "t", "user_key": "u", "e2e_key": "k"})
        with self.assertRaises(PushoverError):
            adapter.send("titre", "message", 2)

    def test_pushover_adapter_reports_missing_secrets_as_health(self):
        engine, _, clock, _ = new_engine()
        real_adapter = PushoverAdapter(secrets_loader=lambda: None)
        engine_with_real_adapter = NotificationEngine(real_adapter, InMemoryStateStore(), clock, cockpit_url)
        urgent = make_request("af-urgent", URGENT)

        engine_with_real_adapter.tick([urgent], now=clock.now())
        self.assertIn("af-urgent", engine_with_real_adapter.undelivered())

    def test_journal_and_test_button_work(self):
        engine, adapter, clock, _ = new_engine()
        urgent = make_request("af-urgent", URGENT)
        engine.tick([urgent], now=clock.now())

        ok = engine.send_test()
        self.assertTrue(ok)
        entries = engine.journal_entries()
        self.assertTrue(any(e["kind"] == "test" and e["ok"] for e in entries))
        self.assertTrue(any(e["req_id"] == "af-urgent" for e in entries))

        for entry in entries:
            self.assertIn(entry["priority"], (0, 1))

    def test_test_notification_bypasses_dedup_and_cap(self):
        engine, adapter, clock, _ = new_engine()
        requests = [make_request("af-%d" % i, A_FAIRE) for i in range(5)]
        engine.tick(requests, now=clock.now())
        self.assertEqual(5, len(adapter.calls))

        ok = engine.send_test()
        self.assertTrue(ok)
        self.assertEqual(6, len(adapter.calls))


class UiRenderTest(unittest.TestCase):
    def test_render_journal_and_test_button(self):
        from cockpit.ui.notify import render

        self.assertIn("Aucun envoi", render.render_journal([]))
        entries = [{"req_id": "af-1", "kind": "initial", "priority": 1, "ok": True}]
        html_out = render.render_journal(entries)
        self.assertIn("af-1", html_out)
        self.assertIn("accepté", html_out)
        self.assertIn("notifier_test", render.TEST_BUTTON_HTML)
        from cockpit.ui.actions.render import SCRIPT as page_script

        self.assertIn("notifier_test", page_script)


if __name__ == "__main__":
    unittest.main()
