"""The other kinds of Operator Request in "Ce qui t'attend", through the
running process (af-mjfvwx).

T15 and T20 built them as pure functions with their own unit tests
(tests/cockpit-more-requests-test.py, tests/cockpit-chantiers-test.py);
nothing merged them into the list a browser gets. This test starts the
real ``bin/cockpit`` on faked sources and reads only ``GET /``,
``GET /api/requests`` and ``POST /api/actions/*``.
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
DESCRIPTORS = ROOT / "tests" / "fixtures" / "cockpit" / "projects" / "descriptors"
COCKPIT_BIN = ROOT / "bin" / "cockpit"

sys.path.insert(0, str(CORE_FIXTURES))

from fake_gc import FakeGc  # noqa: E402

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


def beads():
    return [
        {
            "id": "af-spec1", "title": "Rappels de rituels", "status": "open", "issue_type": "task",
            "labels": [], "notes": "", "created_at": "2026-09-30T08:00:00Z",
            "metadata": {"spec_state": "DRAFT_SPEC", "gc.project_id": "agent-factory"},
        },
        {
            "id": "af-graph1", "title": "Recherche par pseudonyme", "status": "open", "issue_type": "task",
            "labels": ["ticket-graph-draft"], "notes": "", "created_at": "2026-09-30T09:00:00Z",
            "metadata": {"gc.project_id": "saymyname"},
        },
        {
            "id": "af-hitl1", "title": "Prototype de la page projet", "status": "open", "issue_type": "task",
            "labels": [], "notes": "", "created_at": "2026-09-30T07:00:00Z",
            "metadata": {"gc.ticket_kind": "hitl_card"},
        },
        # A delivered chantier, not accepted: placed under Usine by its tickets' rig.
        {
            "id": "af-conv-b", "title": "Page d'accueil publique", "status": "closed", "issue_type": "convoy",
            "labels": ["approved-ticket-graph"], "notes": "",
            "metadata": {"gc.graph_digest": "sha256:b", "gc.flow.mark": "new-flow/v1"},
        },
        {
            "id": "af-tk-b1", "title": "ticket", "status": "closed", "issue_type": "task",
            "labels": ["approved-ticket-graph", "delivery-plane"], "notes": "",
            "metadata": {"gc.graph_digest": "sha256:b", "gc.dispatch_rig": "agent-factory"},
        },
    ]


class OtherRequestsTest(unittest.TestCase):
    def setUp(self):
        self.fake_gc = FakeGc().start()
        self.tmp = tempfile.TemporaryDirectory()
        self.state_file = os.path.join(self.tmp.name, "beads.json")
        self.fail_flag_file = os.path.join(self.tmp.name, "fail")
        self.port = free_port()
        self.origin = "http://127.0.0.1:%d" % self.port
        self.proc = None
        self.write_beads(beads())

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

    def write_beads(self, value):
        tmp = self.state_file + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(value, fh)
        os.replace(tmp, self.state_file)

    def read_beads(self):
        with open(self.state_file) as fh:
            return {bead["id"]: bead for bead in json.load(fh)}

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
                "COCKPIT_PID_FILE": os.path.join(self.tmp.name, "cockpit.pid"),
                "COCKPIT_BEADS_POLL_SECONDS": "0.2",
                "COCKPIT_PROJECTS_POLL_SECONDS": "0.2",
                "COCKPIT_DESCRIPTORS_DIR": str(DESCRIPTORS),
                "COCKPIT_BENJAMIN_LOGIN": BENJAMIN_LOGIN,
                "COCKPIT_ALLOWED_ORIGIN": self.origin,
                "FAKE_BD_STATE_FILE": self.state_file,
                "FAKE_BD_CALLS_FILE": os.path.join(self.tmp.name, "calls.jsonl"),
                "FAKE_BD_FAIL_FLAG_FILE": self.fail_flag_file,
            }
        )
        env.update(extra_env or {})
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

    def requests_by_id(self):
        return {r["id"]: r for r in self.get("/api/requests")["requests"]}

    def detail(self, body, request_id):
        start = body.index('id="d-%s"' % request_id)
        return body[start:body.index("</article>", start)]

    # ------------------------------------------------------------------
    def test_every_kind_is_in_the_one_list_with_its_level(self):
        self.start_cockpit()
        wait_until(lambda: len(self.requests_by_id()) == 4)
        payload = self.get("/api/requests")
        by_id = {r["id"]: r for r in payload["requests"]}

        self.assertEqual("spec_a_approuver", by_id["af-spec1"]["type"])
        self.assertEqual("À faire", by_id["af-spec1"]["niveau"])
        self.assertEqual("graphe_a_approuver", by_id["af-graph1"]["type"])
        self.assertEqual("À faire", by_id["af-graph1"]["niveau"])
        self.assertEqual("hitl_pret_non_lance", by_id["af-hitl1"]["type"])
        self.assertEqual("Quand tu veux", by_id["af-hitl1"]["niveau"])
        self.assertEqual("chantier_livre_non_accepte", by_id["af-conv-b"]["type"])
        self.assertEqual("Quand tu veux", by_id["af-conv-b"]["niveau"])
        # À faire before Quand tu veux, oldest first within a level.
        self.assertEqual(["af-spec1", "af-graph1"], [r["id"] for r in payload["requests"]][:2])
        # The project's displayed name, never its key.
        self.assertEqual("Usine", by_id["af-spec1"]["projet"])
        self.assertEqual("SayMyName", by_id["af-graph1"]["projet"])
        self.assertEqual("Usine", by_id["af-conv-b"]["projet"])
        self.assertEqual("Usine", by_id["af-hitl1"]["projet"], "no project named: the factory's own")

        body = self.get("/")
        self.assertIn("Une Spec attend ton approbation : Rappels de rituels", body)
        self.assertIn("Un graphe de tickets attend ton approbation : Recherche par pseudonyme", body)
        # Approving stays outside the cockpit (spec .37): a prompt to copy, never an approve control.
        for request_id in ("af-spec1", "af-graph1"):
            detail = self.detail(body, request_id)
            self.assertIn('data-action="continuer"', detail)
            self.assertNotIn("approuver_", detail)
            self.assertNotIn('data-action="repondre"', detail)
            self.assertIn('data-action="reporter_ouvrir"', detail)
        # A delivered chantier: its two options are the controls themselves.
        chantier = self.detail(body, "af-conv-b")
        self.assertIn('class="btn opt cockpit-option" data-action="accepter_chantier" data-bead-id="af-conv-b"', chantier)
        self.assertIn('data-action="pas_bon_vers_agent" data-bead-id="af-conv-b" data-titre="Page d&#x27;accueil publique"', chantier)
        self.assertNotIn("reporter_ouvrir", chantier, "nothing would hide it: no Reporter offered")
        self.assertNotIn("Recommandé", chantier, "the cockpit cannot know the delivery is good")
        self.assertNotIn("??:??", chantier, "no date known is not a date missing by defect")
        self.assertNotIn("Benjamin", body, "the screen speaks to Benjamin, never about him")

    def test_reporter_hides_a_spec_to_approve_and_accepting_removes_the_chantier(self):
        self.start_cockpit()
        wait_until(lambda: len(self.requests_by_id()) == 4)

        status, payload = self.post_action("reporter", {"bead_id": "af-spec1", "option": "1h"})
        self.assertEqual(200, status, payload)
        wait_until(lambda: "af-spec1" not in self.requests_by_id())
        self.assertIn("af-graph1", self.requests_by_id())

        status, payload = self.post_action("accepter_chantier", {"bead_id": "af-conv-b", "confirm": True})
        self.assertEqual(200, status, payload)
        wait_until(lambda: "af-conv-b" not in self.requests_by_id())

    def test_approving_at_the_source_removes_the_request(self):
        self.start_cockpit()
        wait_until(lambda: len(self.requests_by_id()) == 4)
        current = beads()
        current[0]["metadata"]["spec_state"] = "APPROVED_SPEC"
        current[1]["labels"].append("approved-ticket-graph")
        current[2]["assignee"] = "po-agent/session"
        self.write_beads(current)
        wait_until(lambda: list(self.requests_by_id()) == ["af-conv-b"])

    # ------------------------------------------------------------------
    def test_a_source_unreadable_for_long_becomes_a_request(self):
        self.fake_gc.go_down()
        self.start_cockpit({"COCKPIT_ILLISIBLE_SECONDS": "1"})
        request = wait_until(lambda: self.requests_by_id().get("source:gc"))
        self.assertEqual("source_illisible", request["type"])
        self.assertEqual("À faire", request["niveau"])
        self.assertEqual("Une source ne répond plus : superviseur", request["quoi"])
        body = self.get("/")
        detail = self.detail(body, "source:gc")
        self.assertIn('<form method="post" action="/api/health/recheck"', detail)
        self.assertIn("Revérifier maintenant", detail)
        self.assertNotIn("reporter_ouvrir", detail)

        self.fake_gc.go_up()
        wait_until(lambda: "source:gc" not in self.requests_by_id())

    def test_dead_beads_source_still_shows_what_does_not_come_from_beads(self):
        Path(self.fail_flag_file).write_text("fail")
        self.start_cockpit({"COCKPIT_ILLISIBLE_SECONDS": "1"})
        wait_until(lambda: "source:beads" in self.requests_by_id())
        payload = self.get("/api/requests")
        self.assertEqual("unknown", payload["state"], "the list is not complete: said so")
        body = self.get("/")
        self.assertIn("Inconnu : illisible depuis", body)
        self.assertIn("Une source ne répond plus : tickets", body)
        self.assertNotIn("Rien ne t", body)


if __name__ == "__main__":
    unittest.main()
