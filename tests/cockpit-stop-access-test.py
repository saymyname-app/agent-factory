"""The stop zone (read-only) and the access zone, through the running
process (af-mjfvwx, slice 7a; spec af-oohx2x §"Arrêt propre et
redémarrage", §"Accès et sécurité").

T23/T24 built the Clean stop driver and its zone against a Python object;
T25 the Tailscale key reader. Nothing served them. Benjamin, 2026-10-06:
the stop goes in two steps -- here, nothing in the cockpit can stop the
factory: the zone shows the state and the work in flight, and no stop
action exists. The test starts the real ``bin/cockpit`` on faked sources
and reads only ``GET /``, the JSON twins and ``POST /api/actions/*``.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "core"
NOTIFY_FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "notify"
ACTIONS_FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "actions"
ACCESS_FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "access"
DESCRIPTORS = ROOT / "tests" / "fixtures" / "cockpit" / "projects" / "descriptors"
COCKPIT_BIN = ROOT / "bin" / "cockpit"

sys.path.insert(0, str(CORE_FIXTURES))
sys.path.insert(0, str(NOTIFY_FIXTURES))

from fake_gc import FakeGc  # noqa: E402
from fake_pushover import FakePushover  # noqa: E402

BENJAMIN_LOGIN = "benjamin@example.ts.net"
WAIT_SECONDS = 30


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_port(host, port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError("nothing listening on %s:%d after %ss" % (host, port, timeout))


def wait_until(predicate, timeout=WAIT_SECONDS, interval=0.1):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError("condition not met within %ss (last=%r)" % (timeout, last))


def iso_in(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def session(session_id, template, active_bead=None, running=True):
    """One item as gc's ``/sessions`` lists it."""
    item = {
        "id": session_id, "kind": "agent", "template": template, "state": "active", "title": template,
        "session_name": template, "running": running, "last_active": "2026-10-06T15:07:21+02:00",
    }
    if active_bead:
        item["active_bead"] = active_bead
    return item


class StopAndAccessTest(unittest.TestCase):
    def setUp(self):
        self.fake_gc = FakeGc().start()
        self.heartbeat = FakePushover().start()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.state_file = str(self.dir / "beads.json")
        self.expiry_file = self.dir / "tailscale-expiry.txt"
        self.port = free_port()
        self.origin = "http://127.0.0.1:%d" % self.port
        self.proc = None
        with open(self.state_file, "w") as fh:
            json.dump(
                [{"id": "af-work1", "title": "Export des listes", "status": "in_progress", "issue_type": "task",
                  # As the factory records a ticket being delivered: the session is on the ticket,
                  # the session list itself names no ticket (checked on the live host).
                  "labels": [], "notes": "",
                  "metadata": {"gc.session_id": "af-s1", "gc.session_name": "factory-worker"}}],
                fh,
            )
        self.expiry_file.write_text(iso_in(200))
        self.fake_gc.set_sessions([
            session("af-s1", "factory-worker"),
            session("af-s2", "mayor"),
        ])

    def tearDown(self):
        if self.proc is not None:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=5)
            self.proc.stdout.close()
            self.proc.stderr.close()
        self.fake_gc.stop()
        self.heartbeat.stop()
        self.tmp.cleanup()

    def start_cockpit(self, extra_env=None):
        env = dict(os.environ)
        env.update(
            {
                "COCKPIT_HOST": "127.0.0.1",
                "COCKPIT_PORT": str(self.port),
                "COCKPIT_GC_BASE_URL": self.fake_gc.base_url,
                "COCKPIT_GC_STATUS_POLL_SECONDS": "0.1",
                "COCKPIT_GC_RECONNECT_SECONDS": "0.1",
                "COCKPIT_SESSIONS_POLL_SECONDS": "0.2",
                "COCKPIT_STOP_TICK_SECONDS": "0.2",
                "COCKPIT_STOP_STATE_FILE": str(self.dir / "stop-state.json"),
                "COCKPIT_BD_BIN": str(ACTIONS_FIXTURES / "fake-bd"),
                "COCKPIT_PID_FILE": str(self.dir / "cockpit.pid"),
                "COCKPIT_BEADS_POLL_SECONDS": "0.2",
                "COCKPIT_PROJECTS_POLL_SECONDS": "0.2",
                "COCKPIT_JOURNAL_POLL_SECONDS": "0.2",
                "COCKPIT_DESCRIPTORS_DIR": str(DESCRIPTORS),
                "COCKPIT_BENJAMIN_LOGIN": BENJAMIN_LOGIN,
                "COCKPIT_ALLOWED_ORIGIN": self.origin,
                "COCKPIT_TAILSCALE_BIN": str(ACCESS_FIXTURES / "fake-tailscale"),
                "COCKPIT_TAILSCALE_POLL_SECONDS": "0.3",
                "FAKE_TAILSCALE_EXPIRY_FILE": str(self.expiry_file),
                "COCKPIT_HEARTBEAT_URL_FILE": str(self.dir / "heartbeat-url.txt"),
                "COCKPIT_HEARTBEAT_TICK_SECONDS": "0.1",
                "COCKPIT_HEARTBEAT_INTERVAL_SECONDS": "0.3",
                "FAKE_BD_STATE_FILE": self.state_file,
                "FAKE_BD_CALLS_FILE": str(self.dir / "calls.jsonl"),
                "FAKE_BD_FAIL_FLAG_FILE": str(self.dir / "fail"),
            }
        )
        for name, value in (extra_env or {}).items():
            if value is None:
                env.pop(name, None)
            else:
                env[name] = value
        (self.dir / "heartbeat-url.txt").write_text(self.heartbeat.ping_url + "\n")
        self.proc = subprocess.Popen(
            [sys.executable, str(COCKPIT_BIN), "run"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        wait_for_port("127.0.0.1", self.port)
        with urllib.request.urlopen("http://127.0.0.1:%d/" % self.port, timeout=5) as resp:
            resp.read()
            self.session_cookie = resp.headers.get("Set-Cookie", "").split(";", 1)[0]

    def get(self, path):
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path), timeout=5) as resp:
            raw = resp.read().decode("utf-8")
            if resp.headers.get("Content-Type", "").startswith("application/json"):
                return json.loads(raw)
            return raw

    def post_action(self, action, body):
        req = urllib.request.Request(
            "http://127.0.0.1:%d/api/actions/%s" % (self.port, action),
            data=json.dumps(body).encode("utf-8"), method="POST",
            headers={
                "Content-Type": "application/json", "Origin": self.origin,
                "Cookie": self.session_cookie, "Tailscale-User-Login": BENJAMIN_LOGIN,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def zone(self, body, css_class):
        start = body.index('class="zone %s"' % css_class)
        return body[start:body.index("</section>", start)]

    # ------------------------------------------------------------------
    def test_stop_zone_of_the_home_page_shows_state_and_work_in_flight_and_holds_no_control(self):
        self.start_cockpit()
        # The sessions and the supervisor's state are read apart: wait for both.
        read = lambda page: "Export des listes · dernier" in page and "cockpit-stop-label\">En marche<" in page  # noqa: E731
        body = wait_until(lambda: (lambda page: page if read(page) else None)(self.get("/")))
        stop = self.zone(body, "cockpit-stop")
        self.assertIn('data-state="en_marche" data-enabled="false"', stop)
        self.assertIn('<span class="cockpit-stop-label">En marche</span>', stop)
        # What a stop would wait for: the agent on a ticket, by the ticket's title; not the idle ones.
        self.assertIn("Travail en vol : 1 agent sur un ticket.", stop)
        self.assertIn("Export des listes · dernier signe de vie <time>15:07</time>", stop)
        self.assertNotIn("mayor", stop)
        # The stop is asked on the page Usine (H, af-69qhlk): no control here.
        self.assertIn("se demande depuis la page Usine", stop)
        self.assertNotIn("request-stop", body)
        self.assertNotIn("request-resume", body)
        for action in ("request-stop", "request_stop", "request-resume", "force_stop"):
            status, payload = self.post_action(action, {"confirm": True})
            self.assertEqual(404, status, action)
            self.assertEqual("unknown_action", payload["error"])
        self.assertFalse(self.get("/api/status")["gc"]["value"]["suspended"])

        # A session that names its ticket itself is read too.
        self.fake_gc.set_sessions([session("af-s9", "factory-worker", active_bead="af-work1")])
        time.sleep(1.0)
        self.assertIn("Travail en vol : 1 agent sur un ticket.", self.get("/"))

        # No agent on a ticket any more.
        self.fake_gc.set_sessions([session("af-s2", "mayor")])
        wait_until(lambda: "Aucun travail en vol" in self.get("/"))

    def test_work_in_flight_is_unknown_when_the_supervisor_is_not_read(self):
        self.fake_gc.go_down()
        self.start_cockpit()
        stop = self.zone(self.get("/"), "cockpit-stop")
        self.assertIn("Travail en vol : inconnu", stop)
        self.assertNotIn("Aucun travail en vol", stop)
        # "No stop requested from here" is not "the factory runs".
        self.assertIn("État de l&#x27;usine inconnu", stop)
        self.assertNotIn("En marche", stop)

    def test_a_factory_suspended_elsewhere_is_not_shown_as_running(self):
        self.fake_gc.set_status(suspended=True)
        self.start_cockpit()
        wait_until(lambda: "Suspendue, sans arrêt demandé depuis le cockpit" in self.get("/"))
        self.assertNotIn("En marche", self.get("/"))

    def test_heartbeat_pauses_only_for_a_factory_stopped_cleanly(self):
        # A stop the cockpit recorded as clean (the state the 7b write side will produce).
        (self.dir / "stop-state.json").write_text(json.dumps({"state": "arretee_proprement", "stopped_at": time.time()}))
        self.start_cockpit()
        wait_until(lambda: "Arrêtée proprement à" in self.get("/"))
        wait_until(lambda: self.get("/api/status")["gc"]["freshness"] == "fresh")
        time.sleep(1.5)
        self.assertEqual(0, self.heartbeat.ping_count(), "no life signal while Benjamin stopped the factory himself")

    def test_heartbeat_runs_when_the_factory_runs(self):
        self.start_cockpit()
        wait_until(lambda: self.heartbeat.ping_count() >= 1)

    # ------------------------------------------------------------------
    def test_access_zone_says_who_may_act_and_until_when_the_key_is_valid(self):
        self.start_cockpit()
        body = wait_until(lambda: self.get("/") if "Clé Tailscale valable" in self.get("/") else None)
        access = self.zone(body, "cockpit-access")
        self.assertIn("Les actions sont réservées à %s, reconnu par Tailscale." % BENJAMIN_LOGIN, access)
        expected = (datetime.now(timezone.utc) + timedelta(days=200)).strftime("%d/%m/%Y")
        self.assertIn("Clé Tailscale valable jusqu&#x27;au %s." % expected, access)
        self.assertNotIn("tailscale-key-expiry", [r["id"] for r in self.get("/api/requests")["requests"]])

        # J-14 (spec .71): the zone warns and the request appears, À faire.
        self.expiry_file.write_text(iso_in(10))
        request = wait_until(
            lambda: next((r for r in self.get("/api/requests")["requests"] if r["id"] == "tailscale-key-expiry"), None)
        )
        self.assertEqual("À faire", request["niveau"])
        self.assertIn("La clé Tailscale expire le", request["quoi"])
        self.assertIn("à renouveler", self.zone(self.get("/"), "cockpit-access"))

        # Renewed: the request leaves by itself.
        self.expiry_file.write_text(iso_in(180))
        wait_until(lambda: "tailscale-key-expiry" not in [r["id"] for r in self.get("/api/requests")["requests"]])

    def test_tailscale_that_does_not_answer_is_unknown_not_a_valid_key(self):
        self.expiry_file.unlink()
        self.start_cockpit()
        access = self.zone(self.get("/"), "cockpit-access")
        self.assertIn("Date d&#x27;expiration de la clé Tailscale inconnue", access)
        self.assertNotIn("valable", access)

    def test_without_identity_or_tailscale_the_zone_says_read_only(self):
        self.start_cockpit({"COCKPIT_BENJAMIN_LOGIN": None, "COCKPIT_TAILSCALE_BIN": None})
        access = self.zone(self.get("/"), "cockpit-access")
        self.assertIn("Lecture seule : aucune identité n&#x27;est configurée", access)
        self.assertNotIn("Tailscale", access.split("Lecture seule")[1], "no key line for a Tailscale never read")
        self.assertNotIn("tailscale", json.dumps(self.get("/api/status")).lower())


if __name__ == "__main__":
    unittest.main()
