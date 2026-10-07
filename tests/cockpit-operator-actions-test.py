"""Operator Actions seam test for T14 (af-peh3yy — répondre, trier les
propositions, relancer depuis le cockpit; Spec af-oohx2x Testing
Decisions, §"Actions opérateur").

Same seam as T13's tests/cockpit-actions-test.py: the real `bin/cockpit
run` process, started on faked sources (fake gc, a controllable fake
bd, and — new for T14 — controllable fake escalation-door, proposal-door,
factory-session-loop-guard, and gc binaries, all under
tests/fixtures/cockpit/operator-actions/). Every assertion reads GET /,
GET /api/requests, POST /api/actions/*, or the fakes' own call logs and
bead state file — never an internal Python function.
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
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
CORE_FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "core"
FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "operator-actions"
COCKPIT_BIN = ROOT / "bin" / "cockpit"

sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(CORE_FIXTURES))

from fake_gc import FakeGc  # noqa: E402

BENJAMIN_LOGIN = "benjamin@example.ts.net"
PARIS = ZoneInfo("Europe/Paris")

OPTIONS_WITH_LETTERS = [
    {"lettre": "a", "option": "répondre a", "consequence": "le travail reprend avec l'option a", "recommande": True, "raison": "c'est le choix le plus sûr"},
    {"lettre": "b", "option": "répondre b", "consequence": "le travail reprend avec l'option b"},
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


def proposal_bead(bead_id, quoi, pourquoi, que_faire, horodatage, extra_metadata=None):
    metadata = {
        "gc.proposal_quoi": quoi,
        "gc.proposal_pourquoi": pourquoi,
        "gc.proposal_que_faire": json.dumps(que_faire),
        "gc.proposal_horodatage": horodatage,
        "gc.proposal_state": "ouverte",
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    return {"id": bead_id, "status": "open", "labels": ["proposal"], "notes": "", "metadata": metadata}


def plain_bead(bead_id):
    return {"id": bead_id, "status": "open", "labels": [], "notes": "", "metadata": {}}


class OperatorActionsSeamTest(unittest.TestCase):
    def setUp(self):
        self.fake_gc = FakeGc().start()
        self.tmp = tempfile.TemporaryDirectory()
        self.pid_file = os.path.join(self.tmp.name, "cockpit.pid")
        self.state_file = os.path.join(self.tmp.name, "beads.json")
        self.bd_calls_file = os.path.join(self.tmp.name, "bd-calls.jsonl")
        self.bd_fail_flag_file = os.path.join(self.tmp.name, "bd-fail")
        self.escalation_calls_file = os.path.join(self.tmp.name, "escalation-calls.jsonl")
        self.escalation_fail_flag_file = os.path.join(self.tmp.name, "escalation-fail")
        self.proposal_calls_file = os.path.join(self.tmp.name, "proposal-calls.jsonl")
        self.proposal_fail_flag_file = os.path.join(self.tmp.name, "proposal-fail")
        self.loop_guard_calls_file = os.path.join(self.tmp.name, "loop-guard-calls.jsonl")
        self.loop_guard_fail_flag_file = os.path.join(self.tmp.name, "loop-guard-fail")
        self.gc_bin_calls_file = os.path.join(self.tmp.name, "gc-bin-calls.jsonl")
        self.gc_bin_fail_flag_file = os.path.join(self.tmp.name, "gc-bin-fail")
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

    def read_bead(self, bead_id):
        return next(b for b in self.read_beads() if b["id"] == bead_id)

    def read_calls(self, path):
        if not os.path.exists(path):
            return []
        with open(path) as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def start_cockpit(self, extra_env=None, fake_door_now="2026-09-30T12:05:00Z"):
        env = dict(os.environ)
        env.update(
            {
                "COCKPIT_HOST": "127.0.0.1",
                "COCKPIT_PORT": str(self.port),
                "COCKPIT_GC_BASE_URL": self.fake_gc.base_url,
                "COCKPIT_BD_BIN": str(FIXTURES / "fake-bd"),
                "COCKPIT_ESCALATION_DOOR_BIN": str(FIXTURES / "fake-escalation-door"),
                "COCKPIT_PROPOSAL_DOOR_BIN": str(FIXTURES / "fake-proposal-door"),
                "COCKPIT_LOOP_GUARD_BIN": str(FIXTURES / "fake-loop-guard"),
                "COCKPIT_GC_BIN": str(FIXTURES / "fake-gc-bin"),
                "COCKPIT_PID_FILE": self.pid_file,
                "COCKPIT_BEADS_POLL_SECONDS": "0.1",
                "COCKPIT_BENJAMIN_LOGIN": BENJAMIN_LOGIN,
                "COCKPIT_ALLOWED_ORIGIN": self.origin,
                "FAKE_BD_STATE_FILE": self.state_file,
                "FAKE_BD_CALLS_FILE": self.bd_calls_file,
                "FAKE_BD_FAIL_FLAG_FILE": self.bd_fail_flag_file,
                "FAKE_ESCALATION_DOOR_CALLS_FILE": self.escalation_calls_file,
                "FAKE_ESCALATION_DOOR_FAIL_FLAG_FILE": self.escalation_fail_flag_file,
                "FAKE_PROPOSAL_DOOR_CALLS_FILE": self.proposal_calls_file,
                "FAKE_PROPOSAL_DOOR_FAIL_FLAG_FILE": self.proposal_fail_flag_file,
                "FAKE_LOOP_GUARD_CALLS_FILE": self.loop_guard_calls_file,
                "FAKE_LOOP_GUARD_FAIL_FLAG_FILE": self.loop_guard_fail_flag_file,
                "FAKE_GC_BIN_CALLS_FILE": self.gc_bin_calls_file,
                "FAKE_GC_BIN_FAIL_FLAG_FILE": self.gc_bin_fail_flag_file,
            }
        )
        if fake_door_now:
            env["FAKE_DOOR_NOW"] = fake_door_now
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
        self._capture_session_cookie()
        return proc

    def _capture_session_cookie(self):
        req = urllib.request.Request("http://127.0.0.1:%d/" % self.port)
        with urllib.request.urlopen(req, timeout=3) as resp:
            resp.read()
            set_cookie = resp.headers.get("Set-Cookie", "")
        self.session_cookie = set_cookie.split(";", 1)[0]

    def requests_payload(self):
        req = urllib.request.Request("http://127.0.0.1:%d/api/requests" % self.port)
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def wait_for_requests(self, predicate, timeout=5):
        return wait_until(lambda: self._try(predicate), timeout=timeout)

    def _try(self, predicate):
        payload = self.requests_payload()
        return payload if predicate(payload) else None

    def post_action(self, action, body):
        url = "http://127.0.0.1:%d/api/actions/%s" % (self.port, action)
        headers = {
            "Content-Type": "application/json",
            "Origin": self.origin,
            "Tailscale-User-Login": BENJAMIN_LOGIN,
            "Cookie": self.session_cookie,
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
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
    # AC1 — répondre calls escalation-door's `repondre`, then the display
    # shows "répondu b à HH:MM, en cours de traitement par l'usine".
    # ------------------------------------------------------------------
    def test_repondre_calls_escalation_door_and_shows_repondu_display(self):
        self.write_beads([escalation_bead("af-rep1", "l'usine attend un choix", "deux chemins possibles", OPTIONS_WITH_LETTERS, "2026-09-30T08:00:00Z", bloquant=True)])
        self.start_cockpit(fake_door_now="2026-09-30T12:05:00Z")
        self.wait_for_requests(lambda p: len(p["requests"]) == 1)

        status, payload = self.post_action("repondre", {"bead_id": "af-rep1", "lettre": "b", "confirm": True})
        self.assertEqual(200, status)
        self.assertTrue(payload["ok"])
        self.assertEqual("b", payload["lettre"])

        expected_dt = datetime(2026, 9, 30, 12, 5, 0, tzinfo=timezone.utc).astimezone(PARIS)
        expected_hhmm = expected_dt.strftime("%H:%M")
        self.assertEqual(
            "répondu b à %s, en cours de traitement par l'usine" % expected_hhmm,
            payload["display"],
        )

        calls = self.read_calls(self.escalation_calls_file)
        self.assertIn(["repondre", "af-rep1", "b"], calls)

        bead = self.read_bead("af-rep1")
        self.assertEqual("none", bead["metadata"]["gc.needs_benjamin"])
        self.assertEqual("b", bead["metadata"]["gc.escalation_response_option"])

    def test_repondre_without_confirm_writes_nothing(self):
        self.write_beads([escalation_bead("af-rep2", "l'usine attend un choix", "deux chemins possibles", OPTIONS_WITH_LETTERS, "2026-09-30T08:00:00Z", bloquant=True)])
        self.start_cockpit()
        self.wait_for_requests(lambda p: len(p["requests"]) == 1)

        status, payload = self.post_action("repondre", {"bead_id": "af-rep2", "lettre": "b"})
        self.assertEqual(400, status)
        self.assertIn("confirmation", payload["error"])

        self.assertEqual([], self.read_calls(self.escalation_calls_file))
        bead = self.read_bead("af-rep2")
        self.assertNotIn("gc.escalation_response_option", bead["metadata"])
        self.assertEqual("l'usine attend un choix", bead["metadata"]["gc.needs_benjamin"])

    # ------------------------------------------------------------------
    # AC2 — accepter, rejeter (raison obligatoire), reporter une
    # proposition via proposal-door.
    # ------------------------------------------------------------------
    def test_accepter_proposition_via_proposal_door(self):
        self.write_beads([proposal_bead("af-prop1", "ajouter un filtre", "gagne du temps", OPTIONS_WITH_LETTERS, "2026-09-30T08:00:00Z")])
        self.start_cockpit()

        status, payload = self.post_action("accepter_proposition", {"bead_id": "af-prop1", "confirm": True})
        self.assertEqual(200, status)
        self.assertTrue(payload["ok"])

        bead = self.read_bead("af-prop1")
        self.assertEqual("a_planifier", bead["metadata"]["gc.proposal_state"])
        self.assertEqual("benjamin", bead["metadata"]["gc.proposal_response_actor"])

        calls = self.read_calls(self.proposal_calls_file)
        self.assertIn(["accepter", "af-prop1", "benjamin"], calls)

    # ------------------------------------------------------------------
    # After an action that wrote, the list is right at once (2026-10-07:
    # an accepted chantier stayed listed, unchanged and clickable again,
    # until the next regular read of Beads). The regular read is set far
    # away here, so only the action's own re-read can explain the list.
    # ------------------------------------------------------------------
    def test_a_handled_request_leaves_the_list_without_waiting_for_the_next_read(self):
        self.write_beads([proposal_bead("af-prop9", "ajouter un filtre", "gagne du temps", OPTIONS_WITH_LETTERS, "2026-09-30T08:00:00Z")])
        self.start_cockpit(extra_env={"COCKPIT_BEADS_POLL_SECONDS": "3600"})
        self.wait_for_requests(lambda p: [r["id"] for r in p["requests"]] == ["af-prop9"])

        status, payload = self.post_action("accepter_proposition", {"bead_id": "af-prop9", "confirm": True})
        self.assertEqual(200, status)
        self.assertTrue(payload["rafraichi"], payload)
        self.assertEqual([], self.requests_payload()["requests"])

    def test_a_refused_action_rereads_nothing(self):
        self.write_beads([proposal_bead("af-prop8", "ajouter un filtre", "gagne du temps", OPTIONS_WITH_LETTERS, "2026-09-30T08:00:00Z")])
        self.start_cockpit(extra_env={"COCKPIT_BEADS_POLL_SECONDS": "3600"})
        self.wait_for_requests(lambda p: len(p["requests"]) == 1)
        status, payload = self.post_action("accepter_proposition", {"bead_id": "af-prop8"})
        self.assertEqual(400, status)
        self.assertNotIn("rafraichi", payload)

    def test_the_page_marks_a_handled_request_and_says_a_refusal(self):
        self.write_beads([proposal_bead("af-prop7", "ajouter un filtre", "gagne du temps", OPTIONS_WITH_LETTERS, "2026-09-30T08:00:00Z")])
        self.start_cockpit()
        self.wait_for_requests(lambda p: len(p["requests"]) == 1)
        req = urllib.request.Request("http://127.0.0.1:%d/" % self.port)
        with urllib.request.urlopen(req, timeout=3) as resp:
            body = resp.read().decode("utf-8")
        # The script that handles every action's answer: result written on
        # the request, its controls removed, a refusal said, then reload.
        self.assertIn("settle(el, body.bead_id", body)
        self.assertIn("removeAttribute('data-action')", body)
        self.assertIn("Action refusée", body)
        self.assertIn("data.rafraichi", body)
        self.assertIn(".cockpit-done", body)

    def test_rejeter_proposition_requires_reason(self):
        self.write_beads([proposal_bead("af-prop2", "ajouter un filtre", "gagne du temps", OPTIONS_WITH_LETTERS, "2026-09-30T08:00:00Z")])
        self.start_cockpit()

        status, payload = self.post_action("rejeter_proposition", {"bead_id": "af-prop2", "confirm": True})
        self.assertEqual(400, status)
        self.assertIn("raison", payload["error"])
        self.assertEqual([], self.read_calls(self.proposal_calls_file))
        bead = self.read_bead("af-prop2")
        self.assertNotIn("gc.proposal_reject_reason", bead["metadata"])

        status2, payload2 = self.post_action(
            "rejeter_proposition", {"bead_id": "af-prop2", "raison": "pas prioritaire", "confirm": True}
        )
        self.assertEqual(200, status2)
        self.assertTrue(payload2["ok"])
        bead_after = self.read_bead("af-prop2")
        self.assertEqual("rejetee", bead_after["metadata"]["gc.proposal_state"])
        self.assertEqual("pas prioritaire", bead_after["metadata"]["gc.proposal_reject_reason"])

    def test_reporter_proposition_via_proposal_door(self):
        self.write_beads([proposal_bead("af-prop3", "ajouter un filtre", "gagne du temps", OPTIONS_WITH_LETTERS, "2026-09-30T08:00:00Z")])
        self.start_cockpit()

        status, payload = self.post_action(
            "reporter_proposition", {"bead_id": "af-prop3", "heure": "demain 10h", "confirm": True}
        )
        self.assertEqual(200, status)
        self.assertTrue(payload["ok"])
        bead = self.read_bead("af-prop3")
        self.assertEqual("demain 10h", bead["metadata"]["gc.proposal_report_until"])
        calls = self.read_calls(self.proposal_calls_file)
        self.assertIn(["reporter", "af-prop3", "demain 10h", "benjamin"], calls)

    def test_proposition_action_without_confirm_writes_nothing(self):
        self.write_beads([proposal_bead("af-prop4", "ajouter un filtre", "gagne du temps", OPTIONS_WITH_LETTERS, "2026-09-30T08:00:00Z")])
        self.start_cockpit()

        status, payload = self.post_action("accepter_proposition", {"bead_id": "af-prop4"})
        self.assertEqual(400, status)
        self.assertIn("confirmation", payload["error"])
        self.assertEqual([], self.read_calls(self.proposal_calls_file))
        bead = self.read_bead("af-prop4")
        self.assertEqual("ouverte", bead["metadata"]["gc.proposal_state"])

    # ------------------------------------------------------------------
    # AC3 — relancer resumes a session (loop-guard) or an order (gc).
    # ------------------------------------------------------------------
    def test_relancer_session_via_loop_guard(self):
        self.write_beads([plain_bead("af-sess1")])
        self.start_cockpit()

        status, payload = self.post_action(
            "relancer",
            {"target_type": "session", "session_id": "sess-123", "bead_id": "af-sess1", "confirm": True},
        )
        self.assertEqual(200, status)
        self.assertTrue(payload["ok"])
        self.assertEqual("session", payload["target_type"])
        self.assertEqual("sess-123", payload["target"])

        calls = self.read_calls(self.loop_guard_calls_file)
        self.assertIn(["resume", "sess-123"], calls)
        self.assertEqual([], self.read_calls(self.gc_bin_calls_file))

        bead = self.read_bead("af-sess1")
        self.assertEqual("relancer", bead["metadata"]["gc.cockpit_action_quoi"])
        self.assertEqual("session", bead["metadata"]["gc.cockpit_action_detail"])
        self.assertIn("Cockpit: relancer", bead["notes"])

    def test_relancer_order_via_loop_guard_or_gc(self):
        self.write_beads([plain_bead("af-sess2")])
        self.start_cockpit()

        status, payload = self.post_action(
            "relancer",
            {"target_type": "order", "order_name": "nightly-build", "bead_id": "af-sess2", "confirm": True},
        )
        self.assertEqual(200, status)
        self.assertTrue(payload["ok"])
        self.assertEqual("order", payload["target_type"])
        self.assertEqual("nightly-build", payload["target"])

        calls = self.read_calls(self.gc_bin_calls_file)
        self.assertIn(["order", "run", "nightly-build"], calls)
        self.assertEqual([], self.read_calls(self.loop_guard_calls_file))

        bead = self.read_bead("af-sess2")
        self.assertEqual("relancer", bead["metadata"]["gc.cockpit_action_quoi"])
        self.assertEqual("order", bead["metadata"]["gc.cockpit_action_detail"])

    def test_relancer_without_confirm_writes_nothing(self):
        self.write_beads([plain_bead("af-sess3")])
        self.start_cockpit()

        status, payload = self.post_action(
            "relancer", {"target_type": "session", "session_id": "sess-999", "bead_id": "af-sess3"}
        )
        self.assertEqual(400, status)
        self.assertIn("confirmation", payload["error"])

        self.assertEqual([], self.read_calls(self.loop_guard_calls_file))
        self.assertEqual([], self.read_calls(self.gc_bin_calls_file))
        bead = self.read_bead("af-sess3")
        self.assertNotIn("gc.cockpit_action_quoi", bead["metadata"])
        self.assertEqual("", bead.get("notes", ""))


if __name__ == "__main__":
    unittest.main()
