"""Restart button / resume proof / stop button trial mode tests (T24,
af-j2mkpa -- Spec af-oohx2x §"Arrêt propre et redémarrage").

Same seam as T23's ``tests/cockpit-stop-test.py`` (a fake gc city client, an
in-memory state store standing in for a JSON file across a simulated
cockpit restart, a fake clock) plus :mod:`cockpit.ui.stop.render`, a pure
function of a :class:`~cockpit.stop.driver.StopDriver` -- rendering needs
no HTTP server to test.
"""
import html as html_module
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
from cockpit.ui.stop.render import ESSAI_TEXT, render_stop_section  # noqa: E402

from fake_gc_city import FakeGcCity  # noqa: E402

ALLOWED_GC_CALLS = {"status", "suspend", "resume", "force_stop_sessions"}
ESCAPED_ESSAI_TEXT = html_module.escape(ESSAI_TEXT)

ALL_STATES = (
    EN_MARCHE,
    ARRET_EN_COURS,
    ARRETEE_PROPREMENT,
    REDEMARRAGE,
    REPRISE_VERIFIEE,
    REPRISE_AVEC_ECARTS,
    ARRET_FORCE,
    ARRET_INTERROMPU,
)


class FakeClock:
    def __init__(self, start=1_000_000.0):
        self._now = start

    def now(self):
        return self._now

    def advance(self, seconds):
        self._now += seconds


def snapshot_of(fake):
    return {"beads": {k: dict(v) for k, v in fake.beads.items()}, "sessions": [dict(s) for s in fake.sessions]}


def new_driver(fake, clock, store):
    return StopDriver(fake, lambda: snapshot_of(fake), clock, store)


class RestartTest(unittest.TestCase):
    # ------------------------------------------------------------------
    # AC1 -- Redémarrage -> Reprise vérifiée / Reprise avec écarts (travail
    # réattribué ou perdu), on a fake gc.
    # ------------------------------------------------------------------
    def test_redemarrage_reaches_reprise_verifiee_on_a_fake_gc(self):
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

        fake.sessions = [{"session_id": "s2", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}]
        self.assertEqual(REPRISE_VERIFIEE, driver.tick())
        self.assertIn("Reprise vérifiée à", driver.label())

    def test_reprise_avec_ecarts_when_work_is_reassigned(self):
        clock = FakeClock()
        store = InMemoryStateStore()
        fake = FakeGcCity(sessions=[{"session_id": "s1", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}])
        driver = new_driver(fake, clock, store)
        driver.request_stop()
        fake.end_session("s1")
        driver.tick()
        driver.resume()

        fake.sessions = [{"session_id": "s2", "bead_id": "af-1", "assignee": "w2", "last_event_at": clock.now()}]
        self.assertEqual(REPRISE_AVEC_ECARTS, driver.tick())
        self.assertEqual(["af-1"], driver.ecarts())
        ids = [r.id for r in driver.pending_requests()]
        self.assertIn("stop:reprise-ecarts", ids)

    def test_reprise_avec_ecarts_when_work_is_lost(self):
        clock = FakeClock()
        store = InMemoryStateStore()
        fake = FakeGcCity(sessions=[{"session_id": "s1", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}])
        driver = new_driver(fake, clock, store)
        driver.request_stop()
        fake.end_session("s1")
        driver.tick()
        driver.resume()

        # af-1 never comes back at all -- no session claims it post-restart.
        fake.sessions = []
        self.assertEqual(REPRISE_AVEC_ECARTS, driver.tick())
        self.assertEqual(["af-1"], driver.ecarts())

    # ------------------------------------------------------------------
    # AC2 -- restart calls only gc resume, and the heartbeat resumes.
    # ------------------------------------------------------------------
    def test_restart_only_calls_gc_resume(self):
        clock = FakeClock()
        store = InMemoryStateStore()
        fake = FakeGcCity(sessions=[{"session_id": "s1", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}])
        driver = new_driver(fake, clock, store)
        driver.request_stop()
        fake.end_session("s1")
        driver.tick()

        fake.calls = []  # only care about what resume() itself triggers
        driver.resume()
        self.assertEqual(["resume"], fake.calls)
        self.assertEqual([], fake.forbidden_calls)
        self.assertTrue(set(fake.calls).issubset(ALLOWED_GC_CALLS))

    def _fresh_read_model(self, clock):
        read_model = ReadModel(clock, validity_seconds={"gc": 120, "beads": 120})
        for name in ("gc", "beads"):
            read_model.register(name)
            read_model.ingest(name, {"ok": True}, at=clock.now())
        return read_model

    def test_heartbeat_resumes_once_restart_reaches_reprise_verifiee(self):
        clock = FakeClock()
        store = InMemoryStateStore()
        fake = FakeGcCity(sessions=[{"session_id": "s1", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}])
        driver = new_driver(fake, clock, store)
        read_model = self._fresh_read_model(clock)
        emitter = HeartbeatEmitter(
            read_model, clock, secret_loader=lambda: "https://hc-ping.com/x",
            ping=lambda url: None, state_provider=driver.state,
        )

        driver.request_stop()
        fake.end_session("s1")
        driver.tick()
        self.assertEqual(ARRETEE_PROPREMENT, driver.state())
        clock.advance(300)
        for name in ("gc", "beads"):
            read_model.ingest(name, {"ok": True}, at=clock.now())
        self.assertEqual("paused", emitter.tick())

        driver.resume()
        fake.sessions = [{"session_id": "s2", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}]
        self.assertEqual(REPRISE_VERIFIEE, driver.tick())

        clock.advance(300)
        for name in ("gc", "beads"):
            read_model.ingest(name, {"ok": True}, at=clock.now())
        self.assertEqual("pinged", emitter.tick())  # heartbeat resumed

    # ------------------------------------------------------------------
    # AC3 -- the stop button renders in trial mode until a trace of a
    # successful real trial exists, then as a normal button; the 7 states
    # all render.
    # ------------------------------------------------------------------
    def test_stop_button_is_in_essai_mode_without_a_successful_trial(self):
        clock = FakeClock()
        store = InMemoryStateStore()
        fake = FakeGcCity(sessions=[])
        driver = new_driver(fake, clock, store)

        html_out = render_stop_section(driver)
        self.assertIn('data-mode="essai"', html_out)
        self.assertIn(ESCAPED_ESSAI_TEXT, html_out)
        self.assertNotIn("hidden", html_out)

    def test_stop_button_becomes_normal_after_a_successful_trial(self):
        clock = FakeClock()
        store = InMemoryStateStore()
        fake = FakeGcCity(sessions=[{"session_id": "s1", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}])
        driver = new_driver(fake, clock, store)

        driver.request_stop()
        fake.end_session("s1")
        driver.tick()
        driver.resume()
        fake.sessions = [{"session_id": "s2", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}]
        self.assertEqual(REPRISE_VERIFIEE, driver.tick())
        self.assertTrue(driver.essai_reussi())

        html_out = render_stop_section(driver)
        self.assertNotIn('data-mode="essai"', html_out)
        self.assertNotIn(ESCAPED_ESSAI_TEXT, html_out)

        # The trace persists across a cockpit restart.
        driver2 = new_driver(fake, clock, store)
        self.assertTrue(driver2.essai_reussi())
        self.assertNotIn('data-mode="essai"', render_stop_section(driver2))

    def test_reprise_avec_ecarts_never_marks_the_trial_successful(self):
        clock = FakeClock()
        store = InMemoryStateStore()
        fake = FakeGcCity(sessions=[{"session_id": "s1", "bead_id": "af-1", "assignee": "w1", "last_event_at": clock.now()}])
        driver = new_driver(fake, clock, store)
        driver.request_stop()
        fake.end_session("s1")
        driver.tick()
        driver.resume()
        fake.sessions = [{"session_id": "s2", "bead_id": "af-1", "assignee": "w2", "last_event_at": clock.now()}]
        self.assertEqual(REPRISE_AVEC_ECARTS, driver.tick())
        self.assertFalse(driver.essai_reussi())
        self.assertIn('data-mode="essai"', render_stop_section(driver))

    def test_restart_button_shown_only_when_a_restart_is_possible(self):
        clock = FakeClock()
        store = InMemoryStateStore()
        fake = FakeGcCity(sessions=[])
        driver = new_driver(fake, clock, store)

        self.assertNotIn('data-action="request-resume"', render_stop_section(driver))

        driver.request_stop()
        driver.tick()
        self.assertEqual(ARRETEE_PROPREMENT, driver.state())
        self.assertIn('data-action="request-resume"', render_stop_section(driver))

    def test_all_seven_states_render_without_error(self):
        clock = FakeClock()
        store = InMemoryStateStore()

        for state in ALL_STATES:
            fake = FakeGcCity(sessions=[])
            store2 = InMemoryStateStore()
            store2.save({"state": state, "perdu": ["af-9"] if state == ARRET_FORCE else [], "ecarts": ["af-9"] if state == REPRISE_AVEC_ECARTS else []})
            driver = new_driver(fake, clock, store2)
            self.assertEqual(state, driver.state())
            html_out = render_stop_section(driver)
            self.assertIn('data-state="%s"' % state, html_out)


if __name__ == "__main__":
    unittest.main()
