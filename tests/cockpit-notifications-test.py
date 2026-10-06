"""Notifications and heartbeat, through the running process (af-mjfvwx;
spec af-oohx2x §"Notifications", §"Heartbeat et usine muette").

T17 and T18 tested the policy engine and the emitter with fake clocks and
a fake adapter; nothing ticked them, and the real Pushover adapter was
never exercised (its encryption was not the API's). Here the real
``bin/cockpit`` runs with its real adapter and emitter pointed at a fake
Pushover / heartbeat server (tests/fixtures/cockpit/notify/fake_pushover.py)
that answers as the API documents and decrypts with the documented scheme.
Secrets are throwaway values made up per test: nothing here can reach
Pushover or Healthchecks.io.
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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "core"
NOTIFY_FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "notify"
ACTIONS_FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "actions"
DESCRIPTORS = ROOT / "tests" / "fixtures" / "cockpit" / "projects" / "descriptors"
COCKPIT_BIN = ROOT / "bin" / "cockpit"

sys.path.insert(0, str(CORE_FIXTURES))
sys.path.insert(0, str(NOTIFY_FIXTURES))

from fake_gc import FakeGc  # noqa: E402
from fake_pushover import FakePushover  # noqa: E402

BENJAMIN_LOGIN = "benjamin@example.ts.net"
WAIT_SECONDS = 30
# Throwaway values in the shapes the API documents (30 alphanumerics, a
# 64-character hex key): not secrets of anything.
FAKE_TOKEN = "a" * 30
FAKE_USER = "u" * 30
FAKE_E2E_KEY = "0123456789abcdef" * 4


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


def escalation(bead_id, quoi, bloquant):
    return {
        "id": bead_id, "title": "titre", "status": "open", "issue_type": "task", "labels": [], "notes": "",
        "metadata": {
            "gc.needs_benjamin": quoi,
            "gc.escalation_pourquoi": "le détail qui ne doit jamais partir dans un push",
            "gc.escalation_que_faire": json.dumps([{"lettre": "a", "option": "répondre", "consequence": "le travail reprend"}]),
            "gc.escalation_bloquant": "true" if bloquant else "false",
            "gc.escalation_horodatage": "2026-10-06T08:00:00Z",
            "gc.project_id": "saymyname",
        },
    }


def beads():
    return [
        escalation("af-urg1", "une livraison est bloquée par ton choix", bloquant=True),
        escalation("af-afa1", "une décision attend ton accord", bloquant=False),
        {
            "id": "af-prop1", "title": "titre", "status": "open", "issue_type": "task", "labels": ["proposal"], "notes": "",
            "metadata": {
                "gc.proposal_quoi": "regrouper deux rituels", "gc.proposal_pourquoi": "ils se recoupent",
                "gc.proposal_que_faire": json.dumps([{"lettre": "a", "option": "accepter", "consequence": "à planifier"}]),
                "gc.proposal_state": "ouverte", "gc.proposal_horodatage": "2026-10-06T07:00:00Z",
            },
        },
    ]


class NotificationsTest(unittest.TestCase):
    def setUp(self):
        self.fake_gc = FakeGc().start()
        self.pushover = FakePushover(e2e_key=FAKE_E2E_KEY).start()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.state_file = str(self.dir / "beads.json")
        self.secrets_file = self.dir / "pushover.json"
        self.heartbeat_file = self.dir / "heartbeat-url.txt"
        self.port = free_port()
        self.origin = "http://127.0.0.1:%d" % self.port
        self.proc = None
        self.write_beads(beads())
        self.secrets_file.write_text(json.dumps({"token": FAKE_TOKEN, "user_key": FAKE_USER, "e2e_key": FAKE_E2E_KEY}))
        self.heartbeat_file.write_text(self.pushover.ping_url + "\n")

    def tearDown(self):
        self.stop_cockpit()
        self.fake_gc.stop()
        self.pushover.stop()
        self.tmp.cleanup()

    def write_beads(self, value):
        tmp = self.state_file + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(value, fh)
        os.replace(tmp, self.state_file)

    def start_cockpit(self, extra_env=None):
        env = dict(os.environ)
        env.update(
            {
                "COCKPIT_HOST": "127.0.0.1",
                "COCKPIT_PORT": str(self.port),
                "COCKPIT_GC_BASE_URL": self.fake_gc.base_url,
                "COCKPIT_GC_STATUS_POLL_SECONDS": "0.1",
                "COCKPIT_GC_RECONNECT_SECONDS": "0.1",
                "COCKPIT_BD_BIN": str(ACTIONS_FIXTURES / "fake-bd"),
                "COCKPIT_PID_FILE": str(self.dir / "cockpit.pid"),
                "COCKPIT_BEADS_POLL_SECONDS": "0.2",
                "COCKPIT_PROJECTS_POLL_SECONDS": "0.2",
                "COCKPIT_JOURNAL_POLL_SECONDS": "0.2",
                "COCKPIT_DESCRIPTORS_DIR": str(DESCRIPTORS),
                "COCKPIT_BENJAMIN_LOGIN": BENJAMIN_LOGIN,
                "COCKPIT_ALLOWED_ORIGIN": self.origin,
                "COCKPIT_PUBLIC_URL": "https://cockpit.example.ts.net",
                "COCKPIT_PUSHOVER_URL": self.pushover.messages_url,
                "COCKPIT_PUSHOVER_SECRETS_FILE": str(self.secrets_file),
                "COCKPIT_NOTIFY_STATE_FILE": str(self.dir / "notify-state.json"),
                "COCKPIT_NOTIFY_TICK_SECONDS": "0.2",
                "COCKPIT_HEARTBEAT_URL_FILE": str(self.heartbeat_file),
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
        self.proc = subprocess.Popen(
            [sys.executable, str(COCKPIT_BIN), "run"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        wait_for_port("127.0.0.1", self.port)
        with urllib.request.urlopen("http://127.0.0.1:%d/" % self.port, timeout=5) as resp:
            resp.read()
            self.session_cookie = resp.headers.get("Set-Cookie", "").split(";", 1)[0]

    def stop_cockpit(self):
        if self.proc is None:
            return
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        self.proc.stdout.close()
        self.proc.stderr.close()
        self.proc = None

    def get(self, path):
        with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path), timeout=5) as resp:
            raw = resp.read().decode("utf-8")
            if resp.headers.get("Content-Type", "").startswith("application/json"):
                return json.loads(raw)
            return raw

    def post_action(self, action, body, login=BENJAMIN_LOGIN):
        headers = {"Content-Type": "application/json", "Origin": self.origin, "Cookie": self.session_cookie}
        if login:
            headers["Tailscale-User-Login"] = login
        req = urllib.request.Request(
            "http://127.0.0.1:%d/api/actions/%s" % (self.port, action),
            data=json.dumps(body).encode("utf-8"), headers=headers, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def health_texts(self):
        return [line["text"] for line in self.get("/api/health")["lines"]]

    def settle(self, seconds=1.5):
        """Several notify ticks' worth of time: what would be sent, is."""
        time.sleep(seconds)

    # ------------------------------------------------------------------
    def test_one_push_per_request_at_its_priority_encrypted_as_the_api_documents(self):
        self.start_cockpit()
        wait_until(lambda: len(self.pushover.sent()) >= 2)
        self.settle()
        sent = self.pushover.sent()
        self.assertEqual(2, len(sent), "one push per Urgent / À faire request, none for Quand tu veux, no duplicate")
        by_priority = {m["priority"]: m for m in sent}
        self.assertEqual({0, 1}, set(by_priority), "Urgent is priority 1, À faire priority 0, never 2")

        urgent = by_priority[1]
        # The wire carries what the API documents for end-to-end encryption.
        self.assertTrue(urgent["encrypted"])
        self.assertEqual(["encrypted", "message", "priority", "title", "token", "user"], urgent["fields"])
        self.assertNotIn("bloquée", urgent["raw_message"])
        # What the phone decrypts: the fixed phrase, the project, the "quoi", a link back.
        self.assertEqual("Une décision bloque une livraison en cours", urgent["title"])
        self.assertIn("une livraison est bloquée par ton choix", urgent["message"])
        self.assertIn("SayMyName", urgent["message"])
        self.assertIn("https://cockpit.example.ts.net/#d-af-urg1", urgent["message"])
        self.assertEqual("Une décision t'attend", by_priority[0]["title"])
        for message in sent:
            self.assertNotIn("ne doit jamais partir", message["message"], "never the pourquoi")

        # Journal des envois: demande, niveau, heure, accepté.
        payload = self.get("/api/notifications")
        self.assertTrue(payload["configured"])
        self.assertEqual(2, len(payload["entries"]))
        self.assertTrue(all(e["ok"] for e in payload["entries"]))
        page = self.get("/journal")
        self.assertIn("Journal des envois", page)
        self.assertIn("une livraison est bloquée par ton choix", page)
        self.assertIn('<span class="chip ack">accepté</span>', page)
        self.assertIn('data-action="notifier_test"', page)
        self.assertEqual([], [t for t in self.health_texts() if "Notification" in t or "notification" in t])

        # A restart sends nothing again (spec .52): the sent state is on disk.
        self.stop_cockpit()
        self.start_cockpit()
        wait_until(lambda: self.get("/api/requests")["state"] == "filled")
        self.settle()
        self.assertEqual(2, len(self.pushover.sent()), "a cockpit restart must not send a duplicate")

        # The Urgent is resolved at its source: one end push, none for the À faire.
        current = beads()
        current[0]["metadata"]["gc.needs_benjamin"] = "none"
        current[1]["metadata"]["gc.needs_benjamin"] = "none"
        self.write_beads(current)
        wait_until(lambda: len(self.pushover.sent()) >= 3)
        self.settle()
        sent = self.pushover.sent()
        self.assertEqual(3, len(sent))
        self.assertEqual("Urgent résolue", sent[2]["title"])
        self.assertEqual(1, sent[2]["priority"])

    def test_unreadable_tickets_are_never_taken_for_resolved_requests(self):
        self.start_cockpit({"COCKPIT_VALIDITY_BEADS_SECONDS": "1"})
        wait_until(lambda: len(self.pushover.sent()) >= 2)
        (self.dir / "fail").write_text("fail")
        wait_until(lambda: self.get("/api/requests")["state"] == "unknown")
        self.settle(2.5)
        self.assertEqual(2, len(self.pushover.sent()), "a dead tickets source must not send « Urgent résolue »")

    def test_without_the_secrets_file_nothing_is_sent_and_health_says_so(self):
        self.secrets_file.unlink()
        self.start_cockpit()
        wait_until(lambda: self.get("/api/requests")["state"] == "filled")
        self.settle()
        self.assertEqual([], self.pushover.sent())
        self.assertIn(
            "Notifications iPhone inactives : le fichier de secrets est absent ou invalide.", self.health_texts()
        )
        payload = self.get("/api/notifications")
        self.assertFalse(payload["configured"])
        self.assertEqual([], payload["entries"], "nothing attempted, so nothing failed")
        page = self.get("/journal")
        self.assertIn("Notifications inactives", page)
        self.assertNotIn('data-action="notifier_test"', page, "no button that could only fail")
        status, payload = self.post_action("notifier_test", {})
        self.assertEqual(400, status)
        self.assertIn("notifications inactives", payload["error"])

    def test_a_refused_send_is_retried_and_shown_on_the_request(self):
        self.pushover.fail_with(500)
        self.start_cockpit()
        wait_until(lambda: len(self.get("/api/notifications")["undelivered"]) == 2)
        self.assertEqual([], self.pushover.sent())
        self.assertIn("notification non livrée", self.get("/"))
        self.assertIn('<span class="chip bloque">échec</span>', self.get("/journal"))

        self.pushover.fail_with(None)
        wait_until(lambda: len(self.pushover.sent()) == 2)
        wait_until(lambda: self.get("/api/notifications")["undelivered"] == [])
        self.assertNotIn("notification non livrée", self.get("/"))

    def test_test_notification_needs_benjamin_and_reaches_the_channel(self):
        self.write_beads([])
        self.start_cockpit()
        status, _ = self.post_action("notifier_test", {}, login=None)
        self.assertEqual(403, status)
        self.assertEqual([], self.pushover.sent())

        status, payload = self.post_action("notifier_test", {})
        self.assertEqual(200, status, payload)
        self.assertEqual("Notification de test envoyée", payload["display"])
        sent = self.pushover.sent()
        self.assertEqual(1, len(sent))
        self.assertEqual("Notification de test", sent[0]["title"])
        self.assertEqual(0, sent[0]["priority"])

    def test_secret_locations_come_from_the_local_settings_file(self):
        """Benjamin, 2026-10-06: the secret files live under his Windows
        profile and a local, unversioned file tells the cockpit where."""
        (self.dir / "cockpit-local.json").write_text(json.dumps({
            "pushover_secrets_file": str(self.secrets_file),
            "heartbeat_url_file": str(self.heartbeat_file),
            "public_url": "https://cockpit.from-local-file.ts.net",
            "benjamin_login": BENJAMIN_LOGIN,
            "une_cle_inconnue": "ignorée",
        }))
        self.start_cockpit({
            "COCKPIT_PUSHOVER_SECRETS_FILE": None, "COCKPIT_HEARTBEAT_URL_FILE": None,
            "COCKPIT_PUBLIC_URL": None, "COCKPIT_BENJAMIN_LOGIN": None,
        })
        wait_until(lambda: len(self.pushover.sent()) >= 2)
        wait_until(lambda: self.pushover.ping_count() >= 1)
        self.assertTrue(any("https://cockpit.from-local-file.ts.net/#d-af-urg1" in m["message"] for m in self.pushover.sent()))
        self.assertEqual([], [t for t in self.health_texts() if "inactive" in t])
        # The login in the file is the identity an action needs.
        status, payload = self.post_action("notifier_test", {})
        self.assertEqual(200, status, payload)

    def test_a_malformed_local_settings_file_leaves_everything_inactive(self):
        (self.dir / "cockpit-local.json").write_text("{ pas du JSON")
        self.start_cockpit({"COCKPIT_PUSHOVER_SECRETS_FILE": None, "COCKPIT_HEARTBEAT_URL_FILE": None})
        wait_until(lambda: self.get("/api/requests")["state"] == "filled")
        self.settle()
        self.assertEqual([], self.pushover.sent())
        self.assertEqual(0, self.pushover.ping_count())
        self.assertEqual(2, len([t for t in self.health_texts() if "inactive" in t]))

    # ------------------------------------------------------------------
    def test_heartbeat_pings_only_while_the_main_sources_are_read(self):
        self.write_beads([])
        # A 1 s Validity window for the supervisor: its death shows within the test.
        self.start_cockpit({"COCKPIT_VALIDITY_GC_SECONDS": "1"})
        wait_until(lambda: self.pushover.ping_count() >= 2)
        self.assertEqual([], [t for t in self.health_texts() if "Usine muette" in t])

        # The supervisor dies: the cockpit must stop saying the factory is alive.
        self.fake_gc.go_down()
        wait_until(lambda: self.get("/api/status")["gc"]["freshness"] != "fresh")
        time.sleep(0.5)
        count = self.pushover.ping_count()
        time.sleep(1.2)
        self.assertEqual(count, self.pushover.ping_count(), "no ping while a main source is not fresh")

        self.fake_gc.go_up()
        wait_until(lambda: self.pushover.ping_count() > count)

    def test_heartbeat_without_its_address_or_refused_is_a_health_line(self):
        self.write_beads([])
        self.heartbeat_file.unlink()
        self.start_cockpit()
        wait_until(
            lambda: "Alerte « Usine muette » inactive : son adresse n'est pas configurée." in self.health_texts()
        )
        self.assertEqual(0, self.pushover.ping_count())

        self.pushover.fail_with(500)
        self.heartbeat_file.write_text(self.pushover.ping_url + "\n")
        wait_until(
            lambda: "Alerte « Usine muette » : le signal de vie n'a pas pu être envoyé." in self.health_texts()
        )
        self.pushover.fail_with(None)
        wait_until(lambda: not [t for t in self.health_texts() if "Usine muette" in t])


if __name__ == "__main__":
    unittest.main()
