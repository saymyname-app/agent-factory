"""Heartbeat emitter tests (bead af-a57xhe, T18 — Spec af-oohx2x).

``HeartbeatEmitter.tick()``/``health_issues()`` are the module's whole
public interface — it has no CLI or HTTP surface of its own (that wiring,
if any, is a later ticket's job), so this test drives it directly, with a
fake clock and a fake pinger standing in for Healthchecks.io. This is
exactly what ``cockpit.core.clock.SystemClock``'s docstring describes an
injected clock for: moving time forward deterministically instead of
sleeping through real 5-minute intervals.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib"))

from cockpit.core.readmodel import ReadModel  # noqa: E402
from cockpit.heartbeat.emitter import (  # noqa: E402
    CLEANLY_STOPPED,
    HeartbeatEmitter,
    read_url_from_file,
)

SECRET_URL = "https://hc-ping.com/test-check"


class FakeClock:
    """A clock a test can move forward by hand (see clock.py's docstring)."""

    def __init__(self, start=0.0):
        self._now = start

    def now(self):
        return self._now

    def advance(self, seconds):
        self._now += seconds


class FakePinger:
    """Records every ping it receives; can be told to fail the next one(s)."""

    def __init__(self):
        self.calls = []
        self.fail_next = 0

    def __call__(self, url):
        self.calls.append(url)
        if self.fail_next > 0:
            self.fail_next -= 1
            raise OSError("simulated ping failure")


def fresh_read_model(clock, sources=("gc", "beads"), validity_seconds=120):
    """A ReadModel with every main source freshly read at the clock's
    current time — the "sources principales répondent" precondition."""
    read_model = ReadModel(clock, validity_seconds={name: validity_seconds for name in sources})
    for name in sources:
        read_model.register(name)
        read_model.ingest(name, {"ok": True}, at=clock.now())
    return read_model


class HeartbeatEmitterTest(unittest.TestCase):
    # ------------------------------------------------------------------
    # AC1 — a ping every 5 min while main sources respond, none while one
    # of them fails.
    # ------------------------------------------------------------------
    def test_pings_every_five_minutes_while_main_sources_are_fresh(self):
        clock = FakeClock()
        read_model = fresh_read_model(clock)
        pinger = FakePinger()
        emitter = HeartbeatEmitter(read_model, clock, secret_loader=lambda: SECRET_URL, ping=pinger)

        self.assertEqual("pinged", emitter.tick())
        self.assertEqual([SECRET_URL], pinger.calls)

        # Immediately again: too soon for a second ping.
        self.assertEqual("waiting", emitter.tick())
        self.assertEqual(1, len(pinger.calls))

        clock.advance(299)
        for name in ("gc", "beads"):
            read_model.ingest(name, {"ok": True}, at=clock.now())
        self.assertEqual("waiting", emitter.tick())
        self.assertEqual(1, len(pinger.calls))

        clock.advance(1)  # exactly 300s since the last ping
        for name in ("gc", "beads"):
            read_model.ingest(name, {"ok": True}, at=clock.now())
        self.assertEqual("pinged", emitter.tick())
        self.assertEqual(2, len(pinger.calls))

    def test_no_ping_when_a_main_source_fails(self):
        clock = FakeClock()
        read_model = fresh_read_model(clock, validity_seconds=60)
        pinger = FakePinger()
        emitter = HeartbeatEmitter(read_model, clock, secret_loader=lambda: SECRET_URL, ping=pinger)

        # gc goes quiet — its Validity window passes without a new read —
        # while beads keeps reading fine.
        clock.advance(120)
        read_model.ingest("beads", {"ok": True}, at=clock.now())

        self.assertEqual("sources-not-fresh", emitter.tick())
        self.assertEqual([], pinger.calls)

    # ------------------------------------------------------------------
    # AC2 — a missing secret and a failed ping both surface as a health
    # issue.
    # ------------------------------------------------------------------
    def test_missing_secret_shows_up_as_a_health_issue(self):
        clock = FakeClock()
        read_model = fresh_read_model(clock)
        pinger = FakePinger()
        emitter = HeartbeatEmitter(read_model, clock, secret_loader=lambda: None, ping=pinger)

        self.assertEqual("missing-secret", emitter.tick())
        self.assertEqual([], pinger.calls)
        self.assertIn("secret heartbeat manquant", emitter.health_issues())

    def test_failed_ping_shows_up_as_a_health_issue(self):
        clock = FakeClock()
        read_model = fresh_read_model(clock)
        pinger = FakePinger()
        pinger.fail_next = 1
        emitter = HeartbeatEmitter(read_model, clock, secret_loader=lambda: SECRET_URL, ping=pinger)

        self.assertEqual("ping-failed", emitter.tick())
        self.assertIn("heartbeat : ping en échec", emitter.health_issues())

        # A later successful ping clears the health issue — never a
        # retroactive erasure, just a new, better reading (spec .36).
        clock.advance(300)
        for name in ("gc", "beads"):
            read_model.ingest(name, {"ok": True}, at=clock.now())
        self.assertEqual("pinged", emitter.tick())
        self.assertEqual([], emitter.health_issues())

    def test_secret_file_missing_or_empty_reads_as_none_not_a_crash(self):
        self.assertIsNone(read_url_from_file("/nonexistent/path/should-not-exist"))
        self.assertIsNone(read_url_from_file(None))
        self.assertIsNone(read_url_from_file(""))

    def test_secret_file_present_is_read_and_stripped(self):
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write(SECRET_URL + "\n")
            path = fh.name
        try:
            self.assertEqual(SECRET_URL, read_url_from_file(path))
        finally:
            Path(path).unlink()

    # ------------------------------------------------------------------
    # AC3 — the heartbeat pauses in no state other than Clean stop
    # ("Arrêtée proprement").
    # ------------------------------------------------------------------
    def test_pauses_only_when_cleanly_stopped(self):
        clock = FakeClock()
        read_model = fresh_read_model(clock)
        pinger = FakePinger()
        state = {"value": "en_marche"}
        emitter = HeartbeatEmitter(
            read_model,
            clock,
            secret_loader=lambda: SECRET_URL,
            ping=pinger,
            state_provider=lambda: state["value"],
        )

        non_pausing_states = [
            "en_marche",
            "arret_en_cours",
            "redemarrage",
            "reprise_verifiee",
            "reprise_avec_ecarts",
            "arret_force",
            "arret_interrompu",
            None,  # T23 not wired yet: an unknown state must not pause either.
        ]
        for value in non_pausing_states:
            state["value"] = value
            self.assertEqual(
                "pinged", emitter.tick(), "must not pause in state %r" % (value,)
            )
            clock.advance(300)
            for name in ("gc", "beads"):
                read_model.ingest(name, {"ok": True}, at=clock.now())

        state["value"] = CLEANLY_STOPPED
        before = len(pinger.calls)
        self.assertEqual("paused", emitter.tick())
        self.assertEqual(before, len(pinger.calls))

        # Still paused even once a ping would otherwise be due again.
        clock.advance(300)
        self.assertEqual("paused", emitter.tick())
        self.assertEqual(before, len(pinger.calls))


if __name__ == "__main__":
    unittest.main()
