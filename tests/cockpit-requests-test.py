""""Ce qui t'attend" seam test (T12, af-is5e97 — Spec af-oohx2x Testing
Decisions).

Drives the same main seam T11 established (cockpit-core-test.py): the
process started on faked sources (fake gc with API + SSE, fake bd — here a
controllable one, tests/fixtures/cockpit/requests/fake-bd, so a test can
grow/close a NEEDS BENJAMIN or a proposal across polls). Every assertion
reads what GET / and GET /api/requests hand back — never an internal
function.

The one exception (matching cockpit-heartbeat-test.py's own precedent):
``cockpit.text.validate`` has no CLI or HTTP surface of its own — its
whole public interface is ``violations()`` — so ``TextValidateTest`` drives
that function directly. The runtime half of the same acceptance criterion
("a validation failure produces the fallback plus a counted defect") is
still proven end to end through the HTTP seam in
``RequestsSeamTest.test_validation_failure_falls_back_and_counts_a_defect``.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "core"
REQUESTS_FIXTURES = ROOT / "tests" / "fixtures" / "cockpit" / "requests"
COCKPIT_BIN = ROOT / "bin" / "cockpit"

sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(CORE_FIXTURES))

from fake_gc import FakeGc  # noqa: E402

from cockpit.text import validate  # noqa: E402


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


def http_get_json(port, path, timeout=3):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path))
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get_text(port, path, timeout=3):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path))
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def wait_until(predicate, timeout=5, interval=0.05):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError("condition not met within %ss (last=%r)" % (timeout, last))


def escalation_bead(bead_id, quoi, pourquoi, que_faire, horodatage, bloquant=False, project=None):
    metadata = {
        "gc.needs_benjamin": quoi,
        "gc.escalation_pourquoi": pourquoi,
        "gc.escalation_que_faire": json.dumps(que_faire),
        "gc.escalation_bloquant": "true" if bloquant else "false",
        "gc.escalation_horodatage": horodatage,
    }
    if project:
        metadata["gc.project_id"] = project
    return {"id": bead_id, "status": "open", "labels": [], "notes": "", "metadata": metadata}


def proposal_bead(bead_id, quoi, pourquoi, que_faire, horodatage, state="ouverte", project=None):
    metadata = {
        "gc.proposal_quoi": quoi,
        "gc.proposal_pourquoi": pourquoi,
        "gc.proposal_que_faire": json.dumps(que_faire),
        "gc.proposal_state": state,
        "gc.proposal_horodatage": horodatage,
    }
    if project:
        metadata["gc.project_id"] = project
    return {"id": bead_id, "status": "open", "labels": ["proposal"], "notes": "", "metadata": metadata}


SOME_OPTIONS = [
    {"option": "répondre a", "consequence": "le travail reprend avec l'option a", "recommande": True, "raison": "c'est le choix le plus sûr"},
    {"option": "répondre b", "consequence": "le travail reprend avec l'option b"},
]


class RequestsSeamTest(unittest.TestCase):
    """The cockpit process started on faked sources — AC1-AC6 of T12."""

    def setUp(self):
        self.fake_gc = FakeGc().start()
        self.tmp = tempfile.TemporaryDirectory()
        self.pid_file = os.path.join(self.tmp.name, "cockpit.pid")
        self.state_file = os.path.join(self.tmp.name, "beads.json")
        self.fail_flag_file = os.path.join(self.tmp.name, "fail")
        self.port = free_port()
        self.proc = None
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

    def start_cockpit(self, extra_env=None):
        env = dict(os.environ)
        env.update(
            {
                "COCKPIT_HOST": "127.0.0.1",
                "COCKPIT_PORT": str(self.port),
                "COCKPIT_GC_BASE_URL": self.fake_gc.base_url,
                "COCKPIT_GC_STATUS_POLL_SECONDS": "0.1",
                "COCKPIT_GC_RECONNECT_SECONDS": "0.1",
                "COCKPIT_BD_BIN": str(REQUESTS_FIXTURES / "fake-bd"),
                "COCKPIT_PID_FILE": self.pid_file,
                "COCKPIT_BEADS_POLL_SECONDS": "0.1",
                "FAKE_BD_STATE_FILE": self.state_file,
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
        return proc

    def requests_payload(self):
        return http_get_json(self.port, "/api/requests")

    def home_body(self):
        return http_get_text(self.port, "/")

    def wait_for_requests(self, predicate, timeout=5):
        return wait_until(lambda: self._try(predicate), timeout=timeout)

    def _try(self, predicate):
        payload = self.requests_payload()
        return payload if predicate(payload) else None

    # ------------------------------------------------------------------
    # AC1 — levels, sort order, fields, project fallback, depuis quand,
    # vérifié à.
    # ------------------------------------------------------------------
    def test_levels_sort_order_fields_project_fallback_and_times(self):
        self.start_cockpit()
        self.write_beads(
            [
                escalation_bead(
                    "af-aaaa", "une Spec attend ton accord", "elle change la portée du travail livré",
                    SOME_OPTIONS, "2026-09-30T08:00:00Z", bloquant=False, project="agent-factory",
                ),
                escalation_bead(
                    "af-bbbb", "l'usine est muette", "plus rien ne répond depuis 20 minutes",
                    SOME_OPTIONS, "2026-09-30T09:00:00Z", bloquant=True,
                ),
                proposal_bead(
                    "af-cccc", "regrouper deux rituels", "ils se recoupent",
                    SOME_OPTIONS, "2026-09-30T07:00:00Z",
                ),
            ]
        )
        payload = self.wait_for_requests(lambda p: len(p["requests"]) == 3)
        requests = payload["requests"]

        # Urgent first, regardless of it being the youngest.
        self.assertEqual(["af-bbbb", "af-aaaa", "af-cccc"], [r["id"] for r in requests])
        self.assertEqual("Urgent", requests[0]["niveau"])
        self.assertEqual("À faire", requests[1]["niveau"])
        self.assertEqual("Quand tu veux", requests[2]["niveau"])

        urgent = requests[0]
        self.assertEqual("l'usine est muette", urgent["quoi"])
        self.assertEqual("plus rien ne répond depuis 20 minutes", urgent["pourquoi"])
        self.assertEqual(2, len(urgent["que_faire"]))
        self.assertTrue(urgent["que_faire"][0]["recommande"])
        self.assertEqual("le travail reprend avec l'option a", urgent["que_faire"][0]["consequence"])
        self.assertIsNotNone(urgent["depuis_quand"])
        self.assertIsNotNone(urgent["verifie_a"])

        a_faire = requests[1]
        self.assertEqual("agent-factory", a_faire["projet"])
        proposal = requests[2]
        self.assertEqual("usine", proposal["projet"], "unknown project falls back to usine")
        self.assertEqual("proposal", proposal["type"])

        body = self.home_body()
        self.assertIn("Ce qui t&#x27;attend", body)
        self.assertIn("usine est muette", body)
        self.assertIn("Recommandé", body)

    # ------------------------------------------------------------------
    # af-mjfvwx — the home screen is the validated variant D: one status
    # line, a short list, one detail per request, and the answer /
    # accept / refuse controls where the prototype puts them.
    # ------------------------------------------------------------------
    def test_home_is_the_variant_d_inbox(self):
        lettered = [dict(option, lettre=lettre) for option, lettre in zip(SOME_OPTIONS, "ab")]
        self.fake_gc.set_status(agents_running=2)
        self.start_cockpit()
        self.write_beads(
            [
                escalation_bead(
                    "af-aaaa", "une Spec attend ton accord", "elle change la portée du travail livré",
                    lettered, "2026-09-30T08:00:00Z",
                ),
                proposal_bead(
                    "af-cccc", "regrouper deux rituels", "ils se recoupent",
                    lettered, "2026-09-30T07:00:00Z",
                ),
                {"id": "af-dddd", "status": "open", "labels": [], "notes": "",
                 "metadata": {"gc.needs_benjamin": "une décision attend"}},
            ]
        )
        self.wait_for_requests(lambda p: len(p["requests"]) == 3)
        body = wait_until(lambda: self.home_body() if "2 agents au travail" in self.home_body() else None)

        self.assertIn("Atkinson+Hyperlegible+Next", body)  # the prototype's font is loaded, not only named
        self.assertIn('<span class="lvl ok"><i></i>En marche</span>', body)
        self.assertIn("Tout est à jour à <time>", body)
        self.assertIn('action="/api/health/recheck"', body)

        # One list row and one detail per request; the first is selected.
        self.assertEqual(3, body.count('<a class="li"'))
        self.assertEqual(3, body.count('<article class="detail'))
        self.assertEqual(1, body.count('<article class="detail zone-body cockpit-request on"'))
        self.assertIn('href="#d-af-aaaa" data-id="af-aaaa" aria-current="true"', body)
        self.assertIn("Retour à la liste", body)
        # A request from another day never shows a bare hour.
        self.assertIn("<time>30/09 ", body)

        def detail(bead_id):
            start = body.index('id="d-%s"' % bead_id)
            return body[start:body.index("</article>", start)]

        # A NEEDS BENJAMIN with prepared options: each option is the answer button.
        self.assertIn('data-action="repondre" data-bead-id="af-aaaa" data-lettre="a"', detail("af-aaaa"))
        self.assertIn('data-action="repondre" data-bead-id="af-aaaa" data-lettre="b"', detail("af-aaaa"))
        self.assertIn("Pourquoi recommandé :", detail("af-aaaa"))
        self.assertNotIn("accepter_proposition", detail("af-aaaa"))
        # A proposal: accept, or refuse with a reason; its options are read-only.
        self.assertIn('data-action="accepter_proposition" data-bead-id="af-cccc"', detail("af-cccc"))
        self.assertIn('data-action="rejeter_proposition" data-bead-id="af-cccc"', detail("af-cccc"))
        self.assertIn('class="field cockpit-rejeter-raison" data-bead-id="af-cccc"', detail("af-cccc"))
        self.assertNotIn('data-action="repondre"', detail("af-cccc"))
        # The fixed fallback option is never an answer button.
        self.assertNotIn('data-action="repondre"', detail("af-dddd"))
        self.assertIn("incomplète : champ pourquoi manquant", detail("af-dddd"))
        # Reporter opens a menu: one button per fixed delay, then a free date and time.
        self.assertNotIn("<select", body)
        self.assertIn('data-action="reporter_ouvrir" data-bead-id="af-aaaa"', detail("af-aaaa"))
        self.assertIn('class="snoozemenu cockpit-report-menu" data-bead-id="af-aaaa" hidden', detail("af-aaaa"))
        for option in ("1h", "4h", "demain_09h", "libre"):
            self.assertIn(
                'data-action="reporter" data-bead-id="af-aaaa" data-option="%s"' % option, detail("af-aaaa")
            )
        self.assertIn('type="datetime-local" class="field cockpit-report-libre"', detail("af-aaaa"))
        for bead_id in ("af-aaaa", "af-cccc", "af-dddd"):
            self.assertIn('data-action="continuer"', detail(bead_id))
            self.assertIn("utilise un agent (consomme des tokens)", detail(bead_id))

    def test_status_line_never_guesses_the_factory_state(self):
        self.fake_gc.go_down()
        self.start_cockpit()
        body = self.home_body()
        self.assertIn("État de l'usine inconnu", body)
        self.assertNotIn("En marche", body)
        self.assertNotIn("agent au travail", body)
        self.assertIn("pas à jour", body)

        self.fake_gc.go_up()
        self.fake_gc.set_status(suspended=True)
        body = wait_until(lambda: self.home_body() if "Suspendue" in self.home_body() else None, timeout=10)
        self.assertNotIn("En marche", body)

    # ------------------------------------------------------------------
    # AC2 — a request missing a field: "incomplète : champ X manquant",
    # the fixed repli phrases, "continuer avec un agent", and a counted
    # producer defect. Existing proposals with no fields render this way
    # too.
    # ------------------------------------------------------------------
    def test_incomplete_request_falls_back_and_counts_a_defect(self):
        self.start_cockpit()
        self.write_beads(
            [
                {
                    "id": "af-dddd",
                    "status": "open",
                    "labels": [],
                    "notes": "",
                    "metadata": {
                        "gc.needs_benjamin": "une décision attend",
                        # pourquoi, que_faire, horodatage all missing.
                    },
                },
            ]
        )
        payload = self.wait_for_requests(lambda p: len(p["requests"]) == 1)
        req = payload["requests"][0]
        self.assertTrue(req["incomplete"])
        self.assertIn("pourquoi", req["missing_fields"])
        self.assertIn("que_faire", req["missing_fields"])
        self.assertIn("depuis_quand", req["missing_fields"])
        self.assertEqual("continuer avec un agent", req["que_faire"][0]["option"])
        self.assertGreaterEqual(payload["defect_count"], 1)

        body = self.home_body()
        self.assertIn("continuer avec un agent", body)
        self.assertIn("Conséquence non fournie par l", body)

    def test_existing_proposal_without_fields_still_renders_with_fallback(self):
        self.start_cockpit()
        self.write_beads(
            [
                {"id": "af-legacy1", "status": "open", "labels": ["proposal"], "notes": "", "metadata": {}},
            ]
        )
        payload = self.wait_for_requests(lambda p: len(p["requests"]) == 1)
        req = payload["requests"][0]
        self.assertTrue(req["incomplete"])
        self.assertEqual("Quand tu veux", req["niveau"])
        self.assertIn("quoi", req["missing_fields"])
        self.assertTrue(req["quoi"].startswith("incomplète : champ"))

    # ------------------------------------------------------------------
    # AC3 — "Rien ne t'attend — vérifié à HH:MM" when empty; "Inconnu :
    # illisible depuis HH:MM" when the source does not respond.
    # ------------------------------------------------------------------
    def test_empty_list_message(self):
        self.start_cockpit()
        self.write_beads([])
        payload = self.wait_for_requests(lambda p: p["state"] == "empty")
        self.assertEqual([], payload["requests"])
        body = wait_until(lambda: self.home_body() if "Rien ne t" in self.home_body() else None)
        self.assertIn("Rien ne t", body)
        self.assertIn("vérifié à", body)

    def test_unknown_source_message(self):
        # Make the fake bd fail every poll from the very first read.
        Path(self.fail_flag_file).write_text("1")
        self.start_cockpit()
        body = wait_until(lambda: self.home_body() if "Inconnu" in self.home_body() else None)
        self.assertIn("Inconnu", body)
        self.assertIn("illisible", body)
        payload = self.requests_payload()
        self.assertEqual("unknown", payload["state"])

    # ------------------------------------------------------------------
    # AC4 — a request only disappears once its source condition closes.
    # ------------------------------------------------------------------
    def test_request_disappears_only_when_source_closes(self):
        self.start_cockpit()
        open_bead = escalation_bead(
            "af-eeee", "réponds à ceci", "ça bloque la suite",
            SOME_OPTIONS, "2026-09-30T08:00:00Z",
        )
        self.write_beads([open_bead])
        self.wait_for_requests(lambda p: len(p["requests"]) == 1)

        # An unrelated metadata change on the same bead must not hide it.
        open_bead["metadata"]["gc.escalation_pourquoi"] = "toujours bloqué, raison précisée"
        self.write_beads([open_bead])
        self.wait_for_requests(
            lambda p: len(p["requests"]) == 1
            and p["requests"][0]["pourquoi"] == "toujours bloqué, raison précisée"
        )

        # Closing the condition at the source (needs_benjamin cleared, as
        # escalation-door's `repondre`/`clear` would do) removes it.
        closed_bead = dict(open_bead)
        closed_bead["metadata"] = dict(open_bead["metadata"])
        closed_bead["metadata"]["gc.needs_benjamin"] = "none"
        self.write_beads([closed_bead])
        self.wait_for_requests(lambda p: len(p["requests"]) == 0)

    # ------------------------------------------------------------------
    # af-1al0t1 — closing the work does not answer the question: a bead
    # closed while its NEEDS BENJAMIN is still set stays a request (plain
    # `bd list` hides closed beads), listed once, until it is answered.
    # ------------------------------------------------------------------
    def test_open_question_on_a_closed_bead_stays_a_request(self):
        self.start_cockpit()
        closed_question = escalation_bead(
            "af-hhhh", "une question reste sans réponse", "le travail a été fermé avant ta réponse",
            SOME_OPTIONS, "2026-09-30T08:00:00Z",
        )
        closed_question["status"] = "closed"
        closed_answered = escalation_bead(
            "af-iiii", "une question déjà tranchée", "tu as déjà répondu",
            SOME_OPTIONS, "2026-09-30T08:00:00Z",
        )
        closed_answered["status"] = "closed"
        closed_answered["metadata"]["gc.needs_benjamin"] = "none"
        open_question = escalation_bead(
            "af-jjjj", "une autre question", "elle attend aussi",
            SOME_OPTIONS, "2026-09-30T09:00:00Z",
        )
        self.write_beads([closed_question, closed_answered, open_question])
        payload = self.wait_for_requests(lambda p: len(p["requests"]) >= 2)
        self.assertEqual(["af-hhhh", "af-jjjj"], sorted(r["id"] for r in payload["requests"]))
        self.assertIn("une question reste sans réponse", self.home_body())

        closed_question["metadata"]["gc.needs_benjamin"] = "none"
        self.write_beads([closed_question, closed_answered, open_question])
        payload = self.wait_for_requests(lambda p: len(p["requests"]) == 1)
        self.assertEqual("af-jjjj", payload["requests"][0]["id"])

    # ------------------------------------------------------------------
    # AC5 (runtime half) — a main-text validation failure (here: an
    # identifier in "quoi") produces the fallback and a counted defect,
    # even though the field was technically present.
    # ------------------------------------------------------------------
    def test_validation_failure_falls_back_and_counts_a_defect(self):
        self.start_cockpit()
        self.write_beads(
            [
                escalation_bead(
                    "af-ffff", "voir af-xyz123 pour la suite", "un agent l'a référencé par id",
                    SOME_OPTIONS, "2026-09-30T08:00:00Z",
                ),
            ]
        )
        payload = self.wait_for_requests(lambda p: len(p["requests"]) == 1)
        req = payload["requests"][0]
        self.assertTrue(req["incomplete"])
        self.assertIn("quoi", req["missing_fields"])
        self.assertTrue(req["quoi"].startswith("incomplète : champ"))
        self.assertGreaterEqual(payload["defect_count"], 1)

    # ------------------------------------------------------------------
    # AC6 — a Mayor-first escalation not yet promoted never appears.
    # ------------------------------------------------------------------
    def test_non_promoted_mayor_first_escalation_is_absent(self):
        self.start_cockpit()
        self.write_beads(
            [
                {
                    "id": "af-gggg",
                    "status": "open",
                    "labels": [],
                    "notes": "",
                    "metadata": {
                        "gc.escalation_mayor_paged_at": "2026-09-30T08:00:00Z",
                        "gc.escalation_mayor_reason": "repeated order failure",
                        # No gc.needs_benjamin: not promoted yet.
                    },
                },
            ]
        )
        # Give the poller a few cycles to have definitely picked this up,
        # then assert it never produced a request.
        time.sleep(0.5)
        payload = self.requests_payload()
        self.assertEqual([], payload["requests"])
        body = self.home_body()
        self.assertNotIn("repeated order failure", body)


class TextValidateTest(unittest.TestCase):
    """cockpit.text.validate's whole public interface is ``violations()``
    (no CLI/HTTP of its own — same precedent as cockpit-heartbeat-test.py
    driving HeartbeatEmitter directly). AC5's "test" half."""

    def test_accepts_a_clean_field(self):
        self.assertEqual([], validate.violations("quoi", "une Spec attend ton accord"))

    def test_rejects_missing_field(self):
        self.assertTrue(validate.violations("quoi", ""))
        self.assertTrue(validate.violations("quoi", None))

    def test_rejects_an_identifier(self):
        self.assertTrue(validate.violations("quoi", "voir af-is5e97 pour la suite"))
        self.assertTrue(validate.violations("quoi", "cf. #300 pour le contexte"))

    def test_rejects_an_internal_term_outside_the_lexicon(self):
        self.assertTrue(validate.violations("quoi", "le bead est bloqué"))
        self.assertTrue(validate.violations("quoi", "un convoi est ouvert"))
        self.assertTrue(validate.violations("quoi", "le Mayor a redémarré"))

    def test_rejects_a_line_over_140_characters(self):
        long_text = "x" * 141
        self.assertTrue(validate.violations("quoi", long_text))
        self.assertEqual([], validate.violations("quoi", "x" * 140))


if __name__ == "__main__":
    unittest.main()
