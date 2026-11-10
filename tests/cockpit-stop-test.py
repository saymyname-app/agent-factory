"""Clean stop / restart driver tests (T23, af-s5e3yo -- Spec af-oohx2x
§"Arrêt propre et redémarrage").

``StopDriver`` has no CLI or HTTP surface of its own yet (process wiring,
the hidden button, the "Ce qui t'attend" feed are later tickets' jobs --
same precedent as T17/T18), so this test drives it directly: a fake clock,
a fake gc city client (``tests/fixtures/cockpit/stop/fake_gc_city.py``)
that only exposes the gestures the driver is allowed to use, and an
in-memory state store standing in for a JSON file across a simulated
cockpit restart.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT / "tests" / "fixtures" / "cockpit" / "stop"))

from cockpit.heartbeat.emitter import HeartbeatEmitter  # noqa: E402
from cockpit.core.readmodel import ReadModel  # noqa: E402
from cockpit.notify.state_store import InMemoryStateStore  # noqa: E402
from cockpit.stop.driver import (  # noqa: E402
    ARRET_EN_COURS,
    ARRET_FORCE,
    ARRET_INTERROMPU,
    ARRETEE_PROPREMENT,
    EN_MARCHE,
    REDEMARRAGE,
    REPRISE_AVEC_ECARTS,
    REPRISE_VERIFIEE,
    StopDriver,
)

from fake_gc_city import FakeGcCity  # noqa: E402

ALLOWED_GC_CALLS = {"status", "suspend", "resume", "force_stop_sessions"}


class FakeClock:
    def __init__(self, start=1_000_000.0):
        self._now = start

    def now(self):
        return self._now

    def advance(self, seconds):
        self._now += seconds


def snapshot_of(fake):
    """The "photo" the driver takes: every known bead (any status, so a
    later comparison can tell "closed normally" from "vanished") plus the
    live sessions."""
    return {"beads": {k: dict(v) for k, v in fake.beads.items()}, "sessions": [dict(s) for s in fake.sessions]}


def new_driver(fake, clock, store):
    return StopDriver(fake, lambda: snapshot_of(fake), clock, store)


class StopDriverTest(unittest.TestCase):
    # ------------------------------------------------------------------
    # AC1 -- En marche -> Arrêt en cours -> Arrêtée proprement, bilan de 0
    # perte, état persistant après un redémarrage du cockpit.
    # ------------------------------------------------------------------
    def test_full_clean_stop_with_zero_loss_and_persists_across_restart(self):
        clock = FakeClock()
        store = InMemoryStateStore()
        fake = FakeGcCity(sessions=[{"session_id": "s1", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}])
        driver = new_driver(fake, clock, store)

        self.assertEqual(EN_MARCHE, driver.state())

        driver.request_stop()
        self.assertEqual(ARRET_EN_COURS, driver.state())
        self.assertEqual(["suspend"], [c for c in fake.calls if c == "suspend"])
        self.assertTrue(fake.suspended)

        # Still one session draining its ticket -- not clean yet.
        clock.advance(5)
        self.assertEqual(ARRET_EN_COURS, driver.tick())

        # The session finishes its ticket and ends.
        fake.end_session("s1")
        clock.advance(5)
        self.assertEqual(ARRETEE_PROPREMENT, driver.tick())
        self.assertEqual([], driver.bilan())  # 0 perte
        self.assertIn("Arrêtée proprement à", driver.label())

        # Simulate a cockpit restart: a fresh StopDriver reading the same
        # persisted state must resume exactly where it left off.
        driver2 = new_driver(fake, clock, store)
        self.assertEqual(ARRETEE_PROPREMENT, driver2.state())
        self.assertEqual([], driver2.bilan())

    def test_lost_bead_is_reported_in_the_bilan(self):
        clock = FakeClock()
        store = InMemoryStateStore()
        fake = FakeGcCity(sessions=[{"session_id": "s1", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}])
        driver = new_driver(fake, clock, store)

        driver.request_stop()
        # Simulated data loss: af-1 disappears entirely instead of closing
        # normally -- driver.bilan() must surface it, not report 0 perte.
        fake.end_session("s1")
        fake.lose_bead("af-1")
        self.assertEqual(ARRETEE_PROPREMENT, driver.tick())
        self.assertEqual(["af-1"], driver.bilan())

    def test_a_normally_closed_bead_is_not_reported_as_lost(self):
        clock = FakeClock()
        store = InMemoryStateStore()
        fake = FakeGcCity(sessions=[{"session_id": "s1", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}])
        driver = new_driver(fake, clock, store)

        driver.request_stop()
        fake.end_session("s1")  # ticket finished normally -- bead closes
        self.assertEqual(ARRETEE_PROPREMENT, driver.tick())
        self.assertEqual([], driver.bilan())

    # ------------------------------------------------------------------
    # AC2 -- "L'arrêt n'avance plus" after 30 min without progress, never
    # an automatic switch to forced stop, a forced stop that keeps beads
    # assigned.
    # ------------------------------------------------------------------
    def test_no_progress_request_after_thirty_minutes_never_auto_forces(self):
        clock = FakeClock()
        store = InMemoryStateStore()
        fake = FakeGcCity(sessions=[{"session_id": "s1", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}])
        driver = new_driver(fake, clock, store)
        driver.request_stop()

        clock.advance(29 * 60)
        driver.tick()
        self.assertEqual([], driver.pending_requests())
        self.assertEqual(ARRET_EN_COURS, driver.state())  # never auto-forced

        clock.advance(2 * 60)
        driver.tick()
        self.assertEqual(ARRET_EN_COURS, driver.state())  # still never auto-forced
        pending = driver.pending_requests()
        self.assertEqual(1, len(pending))
        self.assertEqual("stop:no-progress", pending[0].id)

    def test_a_session_event_resets_the_no_progress_clock(self):
        clock = FakeClock()
        store = InMemoryStateStore()
        fake = FakeGcCity(sessions=[{"session_id": "s1", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}])
        driver = new_driver(fake, clock, store)
        driver.request_stop()

        clock.advance(29 * 60)
        fake.touch_session("s1", clock.now())  # progress: a session event
        driver.tick()

        clock.advance(29 * 60)
        driver.tick()
        self.assertEqual([], driver.pending_requests())  # clock reset by the touch above

    def test_forced_stop_requires_the_offer_and_keeps_bead_assigned(self):
        clock = FakeClock()
        store = InMemoryStateStore()
        fake = FakeGcCity(sessions=[{"session_id": "s1", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}])
        driver = new_driver(fake, clock, store)
        driver.request_stop()

        # Not yet offered -> refuses.
        with self.assertRaises(ValueError):
            driver.force_stop()

        clock.advance(31 * 60)
        driver.tick()
        self.assertEqual(1, len(driver.pending_requests()))

        driver.force_stop()
        self.assertEqual(ARRET_FORCE, driver.state())
        self.assertIn("force_stop_sessions", fake.calls)
        self.assertEqual(["af-1"], driver.bilan())
        self.assertIn("perdu : af-1", driver.label())
        # "garde leur bead et leur travail assigné" -- the fake never had its
        # assignee field cleared by force_stop_sessions.
        self.assertEqual([], fake.sessions)  # session itself ends...
        # ...but the assignment the session held is exactly what bilan()
        # reports as lost, not silently dropped.

    # ------------------------------------------------------------------
    # AC3 -- "usine arrêtée par toi" without a false alarm, heartbeat
    # pauses only at "Arrêtée proprement", "Arrêt interrompu" with écarts.
    # ------------------------------------------------------------------
    def test_source_label_reads_stopped_by_operator_not_a_false_alarm(self):
        clock = FakeClock()
        store = InMemoryStateStore()
        fake = FakeGcCity(sessions=[])
        driver = new_driver(fake, clock, store)

        self.assertIsNone(driver.source_label())
        driver.request_stop()
        self.assertIn("usine arrêtée par toi à", driver.source_label())
        driver.tick()
        self.assertEqual(ARRETEE_PROPREMENT, driver.state())
        self.assertIn("usine arrêtée par toi à", driver.source_label())

    def _fresh_read_model(self, clock):
        read_model = ReadModel(clock, validity_seconds={"gc": 120, "beads": 120})
        for name in ("gc", "beads"):
            read_model.register(name)
            read_model.ingest(name, {"ok": True}, at=clock.now())
        return read_model

    def test_heartbeat_pauses_only_once_driver_reaches_cleanly_stopped(self):
        clock = FakeClock()
        store = InMemoryStateStore()
        fake = FakeGcCity(sessions=[{"session_id": "s1", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}])
        driver = new_driver(fake, clock, store)
        read_model = self._fresh_read_model(clock)
        emitter = HeartbeatEmitter(
            read_model, clock, secret_loader=lambda: "https://hc-ping.com/x",
            ping=lambda url: None, state_provider=driver.state,
        )

        self.assertEqual("pinged", emitter.tick())

        driver.request_stop()
        clock.advance(300)
        for name in ("gc", "beads"):
            read_model.ingest(name, {"ok": True}, at=clock.now())
        self.assertEqual(ARRET_EN_COURS, driver.state())
        self.assertEqual("pinged", emitter.tick())  # not cleanly stopped yet

        fake.end_session("s1")
        driver.tick()
        self.assertEqual(ARRETEE_PROPREMENT, driver.state())
        clock.advance(300)
        self.assertEqual("paused", emitter.tick())

    def test_pc_reboot_mid_stop_gives_arret_interrompu_with_ecarts(self):
        clock = FakeClock()
        store = InMemoryStateStore()
        fake = FakeGcCity(sessions=[{"session_id": "s1", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}])
        driver = new_driver(fake, clock, store)
        driver.request_stop()
        clock.advance(10)

        # The PC reboots before the suspend ever really took hold, and
        # someone else picks the bead up in the meantime.
        fake.suspended = False
        fake.reassign("af-1", "w2")

        # Simulated cockpit restart: a brand-new StopDriver instance reads
        # the persisted arret_en_cours state.
        driver2 = new_driver(fake, clock, store)
        self.assertEqual(ARRET_EN_COURS, driver2.state())

        clock.advance(5)
        self.assertEqual(ARRET_INTERROMPU, driver2.tick())
        self.assertEqual(["af-1"], driver2.ecarts())
        self.assertEqual("Arrêt interrompu", driver2.label())

        # A later tick never re-derives "Arrêt interrompu" from scratch --
        # only the first post-restart tick can.
        fake.reassign("af-1", "w1")
        driver2.tick()
        self.assertEqual(ARRET_INTERROMPU, driver2.state())

    # ------------------------------------------------------------------
    # AC4 -- the driver never runs gc stop / gc stop --force, and only
    # ever touches the city.
    # ------------------------------------------------------------------
    def test_never_calls_gc_stop_or_gc_stop_force(self):
        clock = FakeClock()
        store = InMemoryStateStore()
        fake = FakeGcCity(sessions=[{"session_id": "s1", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}])
        driver = new_driver(fake, clock, store)

        driver.request_stop()
        clock.advance(31 * 60)
        driver.tick()
        driver.force_stop()

        self.assertEqual([], fake.forbidden_calls)
        self.assertTrue(set(fake.calls).issubset(ALLOWED_GC_CALLS))
        with self.assertRaises(AssertionError):
            fake.stop()
        with self.assertRaises(AssertionError):
            fake.stop_force()

    # ------------------------------------------------------------------
    # Resume / reprise vérifiée vs. reprise avec écarts.
    # ------------------------------------------------------------------
    def test_resume_verified_when_work_resumes_without_reassignment(self):
        clock = FakeClock()
        store = InMemoryStateStore()
        fake = FakeGcCity(sessions=[{"session_id": "s1", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}])
        driver = new_driver(fake, clock, store)
        driver.request_stop()
        fake.end_session("s1")
        driver.tick()
        self.assertEqual(ARRETEE_PROPREMENT, driver.state())

        driver.resume()
        self.assertEqual(REDEMARRAGE, driver.state())
        self.assertEqual(["resume"], [c for c in fake.calls if c == "resume"])

        # Same work resumes under the same assignee.
        fake.sessions = [{"session_id": "s2", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}]
        self.assertEqual(REPRISE_VERIFIEE, driver.tick())
        self.assertEqual([], driver.pending_requests())

    def test_resume_with_gaps_raises_an_a_faire_request(self):
        clock = FakeClock()
        store = InMemoryStateStore()
        fake = FakeGcCity(sessions=[{"session_id": "s1", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}])
        driver = new_driver(fake, clock, store)
        driver.request_stop()
        fake.end_session("s1")
        driver.tick()
        driver.resume()

        # af-1 comes back reassigned to someone else instead of w1.
        fake.sessions = [{"session_id": "s2", "bead_id": "af-1", "assignee": "w2", "last_event_at": clock.now()}]
        self.assertEqual(REPRISE_AVEC_ECARTS, driver.tick())
        pending = driver.pending_requests()
        self.assertEqual(1, len(pending))
        self.assertEqual("stop:reprise-ecarts", pending[0].id)
        self.assertEqual(["af-1"], driver.ecarts())


if __name__ == "__main__":
    unittest.main()
