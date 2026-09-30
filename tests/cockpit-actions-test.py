"""Operator Actions seam test (T13, af-cx20q9 — Spec af-oohx2x Testing
Decisions, §"Actions opérateur").

Drives the same main seam T11/T12 established: the cockpit process
started on faked sources (fake gc, a controllable fake bd —
tests/fixtures/cockpit/actions/fake-bd, which also understands `update`
and `create` so a test can see what an Operator Action wrote). Every
assertion reads what GET /, GET /api/requests and POST /api/actions/*
hand back, or what the fake bd's call log recorded — never an internal
function.
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
ACTIONS_FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "actions"
COCKPIT_BIN = ROOT / "bin" / "cockpit"

sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(CORE_FIXTURES))

from fake_gc import FakeGc  # noqa: E402

BENJAMIN_LOGIN = "benjamin@example.ts.net"
SOME_OPTIONS = [
    {"option": "répondre a", "consequence": "le travail reprend avec l'option a", "recommande": True, "raison": "c'est le choix le plus sûr"},
    {"option": "répondre b", "consequence": "le travail reprend avec l'option b"},
]


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_port(host, port, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise TimeoutError("nothing listening on %s:%d after %ss" % (host, port, timeout))


def wait_until(predicate, timeout=5, interval=0.05):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError("condition not met within %ss (last=%r)" % (timeout, last))


def escalation_bead(bead_id, quoi, pourquoi, que_faire, horodatage, bloquant=False, project=None, extra_metadata=None):
    metadata = {
        "gc.needs_benjamin": quoi,
        "gc.escalation_pourquoi": pourquoi,
        "gc.escalation_que_faire": json.dumps(que_faire),
        "gc.escalation_bloquant": "true" if bloquant else "false",
        "gc.escalation_horodatage": horodatage,
    }
    if project:
        metadata["gc.project_id"] = project
    if extra_metadata:
        metadata.update(extra_metadata)
    return {"id": bead_id, "status": "open", "labels": [], "notes": "", "metadata": metadata}


class ActionsSeamTest(unittest.TestCase):
    def setUp(self):
        self.fake_gc = FakeGc().start()
        self.tmp = tempfile.TemporaryDirectory()
        self.pid_file = os.path.join(self.tmp.name, "cockpit.pid")
        self.state_file = os.path.join(self.tmp.name, "beads.json")
        self.calls_file = os.path.join(self.tmp.name, "calls.jsonl")
        self.fail_flag_file = os.path.join(self.tmp.name, "fail")
        self.port = free_port()
        self.origin = "http://127.0.0.1:%d" % self.port
        self.proc = None
        self.session_cookie = None
        self.write_beads([])

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
        self.tmp.cleanup()

    def write_beads(self, beads):
        with open(self.state_file, "w") as fh:
            json.dump(beads, fh)

    def read_beads(self):
        with open(self.state_file) as fh:
            return json.load(fh)

    def read_calls(self):
        if not os.path.exists(self.calls_file):
            return []
        with open(self.calls_file) as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def start_cockpit(self, extra_env=None):
        env = dict(os.environ)
        env.update(
            {
                "COCKPIT_HOST": "127.0.0.1",
                "COCKPIT_PORT": str(self.port),
                "COCKPIT_GC_BASE_URL": self.fake_gc.base_url,
                "COCKPIT_BD_BIN": str(ACTIONS_FIXTURES / "fake-bd"),
                "COCKPIT_PID_FILE": self.pid_file,
                "COCKPIT_BEADS_POLL_SECONDS": "0.1",
                "COCKPIT_BENJAMIN_LOGIN": BENJAMIN_LOGIN,
                "COCKPIT_ALLOWED_ORIGIN": self.origin,
                "FAKE_BD_STATE_FILE": self.state_file,
                "FAKE_BD_CALLS_FILE": self.calls_file,
                "FAKE_BD_FAIL_FLAG_FILE": self.fail_flag_file,
            }
        )
        if extra_env:
            env.update(extra_env)
        proc = subprocess.Popen(
            [sys.executable, str(COCKPIT_BIN), "run"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.proc = proc
        wait_for_port("127.0.0.1", self.port)
        self.fake_gc.push_event({"running": True, "partial": False})
        self._capture_session_cookie()
        return proc

    def _capture_session_cookie(self):
        req = urllib.request.Request("http://127.0.0.1:%d/" % self.port)
        with urllib.request.urlopen(req, timeout=3) as resp:
            resp.read()
            set_cookie = resp.headers.get("Set-Cookie", "")
        # "cockpit_session=<token>; Path=/; SameSite=Strict; HttpOnly"
        self.session_cookie = set_cookie.split(";", 1)[0]

    def requests_payload(self):
        req = urllib.request.Request("http://127.0.0.1:%d/api/requests" % self.port)
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def home_body(self):
        req = urllib.request.Request("http://127.0.0.1:%d/" % self.port)
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.read().decode("utf-8")

    def wait_for_requests(self, predicate, timeout=5):
        return wait_until(lambda: self._try(predicate), timeout=timeout)

    def _try(self, predicate):
        payload = self.requests_payload()
        return payload if predicate(payload) else None

    def post_action(self, action, body, method="POST", origin="__default__", login="__default__", cookie="__default__"):
        url = "http://127.0.0.1:%d/api/actions/%s" % (self.port, action)
        headers = {"Content-Type": "application/json"}
        if origin == "__default__":
            origin = self.origin
        if origin is not None:
            headers["Origin"] = origin
        if login == "__default__":
            login = BENJAMIN_LOGIN
        if login is not None:
            headers["Tailscale-User-Login"] = login
        if cookie == "__default__":
            cookie = self.session_cookie
        if cookie is not None:
            headers["Cookie"] = cookie
        data = json.dumps(body).encode("utf-8")
        if method == "GET":
            # GET never carries a body in this API -- simulate the
            # refusal path by hitting the action URL with GET.
            req = urllib.request.Request(url, headers=headers, method="GET")
        else:
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode("utf-8")
            try:
                payload = json.loads(payload)
            except ValueError:
                pass
            return exc.code, payload

    # ------------------------------------------------------------------
    # AC1 — refused without the header, with another login, in GET, or
    # with a bad Origin; writes nothing; the page stays readable.
    # ------------------------------------------------------------------
    def test_action_without_header_is_refused_and_writes_nothing(self):
        self.write_beads([escalation_bead("af-aaaa", "l'usine est muette", "rien ne répond", SOME_OPTIONS, "2026-09-30T08:00:00Z", bloquant=True)])
        self.start_cockpit()
        self.wait_for_requests(lambda p: len(p["requests"]) == 1)

        status, payload = self.post_action("acquitter", {"bead_id": "af-aaaa"}, login=None)
        self.assertEqual(403, status)
        self.assertEqual("identity", payload["error"])
        bead = next(b for b in self.read_beads() if b["id"] == "af-aaaa")
        self.assertNotIn("gc.cockpit_ack", bead["metadata"])
        self.assertIn("Cockpit</title>", self.home_body())

    def test_action_with_another_login_is_refused_and_writes_nothing(self):
        self.write_beads([escalation_bead("af-bbbb", "l'usine est muette", "rien ne répond", SOME_OPTIONS, "2026-09-30T08:00:00Z", bloquant=True)])
        self.start_cockpit()
        self.wait_for_requests(lambda p: len(p["requests"]) == 1)

        status, payload = self.post_action("acquitter", {"bead_id": "af-bbbb"}, login="quelquun.dautre@example.ts.net")
        self.assertEqual(403, status)
        self.assertEqual("identity", payload["error"])
        bead = next(b for b in self.read_beads() if b["id"] == "af-bbbb")
        self.assertNotIn("gc.cockpit_ack", bead["metadata"])

    def test_action_in_get_is_refused_and_writes_nothing(self):
        self.write_beads([escalation_bead("af-cccc", "l'usine est muette", "rien ne répond", SOME_OPTIONS, "2026-09-30T08:00:00Z", bloquant=True)])
        self.start_cockpit()
        self.wait_for_requests(lambda p: len(p["requests"]) == 1)

        status, payload = self.post_action("acquitter", {"bead_id": "af-cccc"}, method="GET")
        self.assertEqual(403, status)
        self.assertEqual("method", payload["error"])
        bead = next(b for b in self.read_beads() if b["id"] == "af-cccc")
        self.assertNotIn("gc.cockpit_ack", bead["metadata"])

    def test_action_with_bad_origin_is_refused_and_writes_nothing(self):
        self.write_beads([escalation_bead("af-dddd", "l'usine est muette", "rien ne répond", SOME_OPTIONS, "2026-09-30T08:00:00Z", bloquant=True)])
        self.start_cockpit()
        self.wait_for_requests(lambda p: len(p["requests"]) == 1)

        status, payload = self.post_action("acquitter", {"bead_id": "af-dddd"}, origin="https://evil.example.com")
        self.assertEqual(403, status)
        self.assertEqual("origin", payload["error"])
        bead = next(b for b in self.read_beads() if b["id"] == "af-dddd")
        self.assertNotIn("gc.cockpit_ack", bead["metadata"])

    def test_action_without_cookie_is_refused_and_writes_nothing(self):
        self.write_beads([escalation_bead("af-eeee", "l'usine est muette", "rien ne répond", SOME_OPTIONS, "2026-09-30T08:00:00Z", bloquant=True)])
        self.start_cockpit()
        self.wait_for_requests(lambda p: len(p["requests"]) == 1)

        status, payload = self.post_action("acquitter", {"bead_id": "af-eeee"}, cookie=None)
        self.assertEqual(403, status)
        self.assertEqual("session", payload["error"])
        bead = next(b for b in self.read_beads() if b["id"] == "af-eeee")
        self.assertNotIn("gc.cockpit_ack", bead["metadata"])

    # ------------------------------------------------------------------
    # AC2 — acquitter and reporter leave a comment + metadata on the
    # source bead; a source without one gets a bead journal.
    # ------------------------------------------------------------------
    def test_acquitter_traces_comment_and_metadata_on_the_source_bead(self):
        self.write_beads([escalation_bead("af-ffff", "l'usine est muette", "rien ne répond", SOME_OPTIONS, "2026-09-30T08:00:00Z", bloquant=True)])
        self.start_cockpit()
        self.wait_for_requests(lambda p: len(p["requests"]) == 1)

        status, payload = self.post_action("acquitter", {"bead_id": "af-ffff"})
        self.assertEqual(200, status)
        self.assertTrue(payload["ok"])

        bead = next(b for b in self.read_beads() if b["id"] == "af-ffff")
        self.assertEqual("true", bead["metadata"]["gc.cockpit_ack"])
        self.assertEqual("acquitter", bead["metadata"]["gc.cockpit_action_quoi"])
        self.assertEqual("benjamin", bead["metadata"]["gc.cockpit_action_acteur"])
        self.assertIn("gc.cockpit_action_quand", bead["metadata"])
        self.assertIn("Cockpit: acquitter", bead["notes"])

        payload = self.wait_for_requests(lambda p: len(p["requests"]) == 1 and p["requests"][0]["acquittee"])
        self.assertTrue(payload["requests"][0]["acquittee"])
        # Acquitter never removes the request from the list (spec .21).
        self.assertEqual("af-ffff", payload["requests"][0]["id"])

    def test_reporter_traces_option_as_metadata_and_comment(self):
        self.write_beads([escalation_bead("af-gggg", "une Spec attend ton accord", "elle change la portée", SOME_OPTIONS, "2026-09-30T08:00:00Z")])
        self.start_cockpit()
        self.wait_for_requests(lambda p: len(p["requests"]) == 1)

        status, payload = self.post_action("reporter", {"bead_id": "af-gggg", "option": "1h"})
        self.assertEqual(200, status)
        self.assertTrue(payload["ok"])
        self.assertIn("defer_until", payload)

        bead = next(b for b in self.read_beads() if b["id"] == "af-gggg")
        self.assertEqual("reporter", bead["metadata"]["gc.cockpit_action_quoi"])
        self.assertEqual("1h", bead["metadata"]["gc.cockpit_action_detail"])
        self.assertIn("gc.cockpit_defer_until", bead["metadata"])

    def test_source_without_bead_receives_a_bead_journal(self):
        self.start_cockpit()
        status, payload = self.post_action("acquitter", {"source_key": "usine-muette"})
        self.assertEqual(200, status)
        self.assertTrue(payload["ok"])
        journal_id = payload["bead_id"]
        self.assertTrue(journal_id)

        beads = self.read_beads()
        journal = next(b for b in beads if b["id"] == journal_id)
        self.assertEqual("usine-muette", journal["metadata"]["gc.cockpit_journal_for"])
        self.assertEqual("true", journal["metadata"]["gc.cockpit_ack"])

        # A second action against the same source reuses the journal
        # bead rather than creating a duplicate.
        status2, payload2 = self.post_action("reporter", {"source_key": "usine-muette", "option": "1h"})
        self.assertEqual(200, status2)
        self.assertEqual(journal_id, payload2["bead_id"])
        beads_after = self.read_beads()
        self.assertEqual(1, sum(1 for b in beads_after if b["metadata"].get("gc.cockpit_journal_for") == "usine-muette"))

    # ------------------------------------------------------------------
    # AC3 — a reported request returns at its deadline; an Urgent
    # deferred request stays visible, greyed; not calling the action
    # (the "Annuler" window) writes nothing.
    # ------------------------------------------------------------------
    def test_a_faire_reported_hides_then_returns_at_deadline(self):
        self.write_beads([escalation_bead("af-hhhh", "une Spec attend ton accord", "elle change la portée", SOME_OPTIONS, "2026-09-30T08:00:00Z")])
        self.start_cockpit()
        self.wait_for_requests(lambda p: len(p["requests"]) == 1)

        status, _ = self.post_action("reporter", {"bead_id": "af-hhhh", "option": "libre", "custom_epoch": time.time() + 1.0})
        self.assertEqual(200, status)

        self.wait_for_requests(lambda p: len(p["requests"]) == 0)
        self.wait_for_requests(lambda p: len(p["requests"]) == 1, timeout=5)

    def test_urgent_reported_stays_visible_greyed(self):
        self.write_beads([escalation_bead("af-iiii", "l'usine est muette", "rien ne répond", SOME_OPTIONS, "2026-09-30T08:00:00Z", bloquant=True)])
        self.start_cockpit()
        self.wait_for_requests(lambda p: len(p["requests"]) == 1)

        status, _ = self.post_action("reporter", {"bead_id": "af-iiii", "option": "4h"})
        self.assertEqual(200, status)

        payload = self.wait_for_requests(lambda p: len(p["requests"]) == 1 and p["requests"][0]["reportee"])
        self.assertEqual("Urgent", payload["requests"][0]["niveau"])
        self.assertTrue(payload["requests"][0]["reportee"])
        body = self.home_body()
        self.assertIn('data-reportee="true"', body)

    def test_cancel_within_ten_seconds_writes_nothing(self):
        # The "Annuler" window (spec .33) is purely client-side: not
        # calling the endpoint is the cancel. This proves the handler is
        # inert until invoked -- no speculative write happens on render.
        self.write_beads([escalation_bead("af-jjjj", "l'usine est muette", "rien ne répond", SOME_OPTIONS, "2026-09-30T08:00:00Z", bloquant=True)])
        self.start_cockpit()
        self.wait_for_requests(lambda p: len(p["requests"]) == 1)
        # Deliberately do not call post_action here.
        bead = next(b for b in self.read_beads() if b["id"] == "af-jjjj")
        self.assertNotIn("gc.cockpit_ack", bead["metadata"])
        self.assertEqual("", bead.get("notes", ""))

    # ------------------------------------------------------------------
    # AC4 — the fixed phrase explaining Acquitter/Reporter is displayed.
    # ------------------------------------------------------------------
    def test_fixed_explanation_phrase_is_displayed(self):
        self.write_beads([escalation_bead("af-kkkk", "l'usine est muette", "rien ne répond", SOME_OPTIONS, "2026-09-30T08:00:00Z", bloquant=True)])
        self.start_cockpit()
        self.wait_for_requests(lambda p: len(p["requests"]) == 1)
        body = self.home_body()
        # The page HTML-escapes apostrophes (html.escape); match the
        # rendered form rather than the literal French sentence.
        self.assertIn(
            "Acquitter : plus aucun rappel, la demande reste ici. "
            "Reporter : cachée jusqu&#x27;à l&#x27;heure choisie, puis elle revient. "
            "Aucun des deux ne change rien dans l&#x27;usine.",
            body,
        )

    # ------------------------------------------------------------------
    # AC5 — the copied prompt contains quoi, identifiants, question,
    # dossier, commande de départ; no provider, no cost figure.
    # ------------------------------------------------------------------
    def test_continuer_prompt_has_required_fields_and_no_provider_or_cost(self):
        self.write_beads([escalation_bead("af-llll", "une Spec attend ton accord", "elle change la portée", SOME_OPTIONS, "2026-09-30T08:00:00Z")])
        self.start_cockpit()
        self.wait_for_requests(lambda p: len(p["requests"]) == 1)

        status, payload = self.post_action("continuer", {"bead_id": "af-llll", "quoi": "une Spec attend ton accord"})
        self.assertEqual(200, status)
        prompt = payload["prompt"]
        self.assertIn("Quoi :", prompt)
        self.assertIn("af-llll", prompt)
        self.assertIn("Question :", prompt)
        self.assertIn("Dossier :", prompt)
        self.assertIn("Commande de départ :", prompt)
        for forbidden in ("anthropic", "openai", "claude-opus", "gpt-", "$", "€", "token" + "s coûtent"):
            self.assertNotIn(forbidden, prompt.lower())

        # "continuer" never writes to Beads -- it only formats text.
        bead = next(b for b in self.read_beads() if b["id"] == "af-llll")
        self.assertNotIn("gc.cockpit_action_quoi", bead["metadata"])

    # ------------------------------------------------------------------
    # AC6 — an error is corrected by a new traced action, never an
    # erasure; the cockpit itself keeps no local copy of action state.
    # ------------------------------------------------------------------
    def test_correction_is_a_new_traced_action_not_an_erasure(self):
        self.write_beads([escalation_bead("af-mmmm", "l'usine est muette", "rien ne répond", SOME_OPTIONS, "2026-09-30T08:00:00Z", bloquant=True)])
        self.start_cockpit()
        self.wait_for_requests(lambda p: len(p["requests"]) == 1)

        self.post_action("reporter", {"bead_id": "af-mmmm", "option": "1h"})
        bead_after_first = next(b for b in self.read_beads() if b["id"] == "af-mmmm")
        first_notes = bead_after_first["notes"]
        self.assertIn("Cockpit: reporter", first_notes)

        # Correcting the report (e.g. wrong option chosen) is a second
        # traced call, not a metadata overwrite that erases the first.
        self.post_action("reporter", {"bead_id": "af-mmmm", "option": "4h"})
        bead_after_second = next(b for b in self.read_beads() if b["id"] == "af-mmmm")
        self.assertIn(first_notes, bead_after_second["notes"])
        self.assertEqual(2, bead_after_second["notes"].count("Cockpit: reporter"))

        calls = self.read_calls()
        update_calls = [c for c in calls if c and c[0] == "update"]
        self.assertGreaterEqual(len(update_calls), 2)


if __name__ == "__main__":
    unittest.main()
