""""Ce qui t'attend" seam test (T12, af-is5e97 — Spec af-oohx2x Testing
Decisions).

Drives the same main seam T11 established (cockpit-core-test.py): the
process started on faked sources (fake gc with API + SSE, fake bd — here a
controllable one, tests/fixtures/cockpit/requests/fake-bd, so a test can
grow/close a NEEDS BENJAMIN or a proposal across polls). Every assertion
reads what GET / and GET /api/requests hand back — never an internal
function.

The control of the main text (``TextContractSeamTest``) is read the same
way: what GET /api/requests replaced, never ``cockpit.text.validate``
itself (B, af-4uzgzm: the test went through that function before).
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

sys.path.insert(0, str(CORE_FIXTURES))

from fake_gc import FakeGc  # noqa: E402



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


def proposal_bead(bead_id, quoi, pourquoi, que_faire, horodatage, state="ouverte", project=None, classe=None):
    metadata = {
        "gc.proposal_quoi": quoi,
        "gc.proposal_pourquoi": pourquoi,
        "gc.proposal_que_faire": json.dumps(que_faire),
        "gc.proposal_state": state,
        "gc.proposal_horodatage": horodatage,
    }
    if project:
        metadata["gc.project_id"] = project
    if classe:
        metadata["gc.proposal_classe"] = classe
    return {"id": bead_id, "status": "open", "labels": ["proposal"], "notes": "", "metadata": metadata}


SOME_OPTIONS = [
    {"option": "répondre a", "consequence": "le travail reprend avec l'option a", "recommande": True, "raison": "c'est le choix le plus sûr"},
    {"option": "répondre b", "consequence": "le travail reprend avec l'option b"},
]


class CockpitOnFakes(unittest.TestCase):
    """The cockpit process started on faked sources."""

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
                "COCKPIT_PROJECTS_POLL_SECONDS": "0.2",
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



class RequestsSeamTest(CockpitOnFakes):
    """« Ce qui t'attend » on the process — AC1-AC6 of T12."""

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
        # A request shows its project's displayed name, not its key (spec .73).
        wait_until(lambda: self.requests_payload()["requests"][1]["projet"] == "Usine")
        proposal = requests[2]
        self.assertEqual(
            "Usine", self.requests_payload()["requests"][2]["projet"], "no project named: the factory's own"
        )
        self.assertEqual("proposal", proposal["type"])

        body = self.home_body()
        self.assertIn("Ce qui t’attend", body)
        self.assertIn("usine est muette", body)
        self.assertIn("Recommandé", body)

    # ------------------------------------------------------------------
    # af-mjfvwx — the home screen is the validated variant D: one status
    # line, a short list, one detail per request, and the answer /
    # accept / refuse controls where the prototype puts them. Since B
    # (af-4uzgzm) the list and its details are « Pour moi » of the
    # overview: one line per request, each request opened in its article.
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
        body = wait_until(lambda: self.home_body() if "Tout est à jour à <time>" in self.home_body() else None)
        self.assertIn('action="/api/health/recheck"', body)

        # One line and one opened article per request; the first is open.
        self.assertEqual(3, body.count('<button type="button" class="pn-request"'))
        self.assertEqual(3, body.count('<article class="pn-panel pn-result pn-open-request cockpit-request"'))
        self.assertEqual(2, body.count('data-open="af-cccc" data-level="info" hidden')
                         + body.count('data-open="af-dddd" data-level="normal" hidden'))
        opening = body[body.index('id="d-af-aaaa"'):]
        self.assertNotIn(" hidden", opening[:opening.index(">")], "the first request is not the one open")
        self.assertIn('aria-current="true" data-request="af-aaaa"', body)
        # A request from another day never shows a bare hour.
        self.assertIn("depuis 30/09 ", body)

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

    def test_proposal_without_fields_is_a_health_anomaly_not_a_request(self):
        # ADR-0029 point 4: a proposal no door wrote (no gc.proposal_*
        # field) leaves « Ce qui t'attend » and is said in the health zone
        # as « à reformuler par la porte ». Before, it rendered as an
        # incomplete request with every field replaced by a repli.
        self.start_cockpit()
        self.write_beads(
            [
                {"id": "af-legacy1", "status": "open", "labels": ["proposal"], "notes": "", "metadata": {}},
            ]
        )
        health = wait_until(
            lambda: next(
                (h for h in [http_get_json(self.port, "/api/health")]
                 if any("reformuler par la porte" in l["text"] for l in h["lines"])),
                None,
            )
        )
        line = next(l for l in health["lines"] if "reformuler par la porte" in l["text"])
        self.assertEqual("warn", line["kind"])
        self.assertNotIn("af-legacy1", line["text"])
        self.assertFalse(health["ok"])
        payload = self.requests_payload()
        self.assertEqual([], [r["id"] for r in payload["requests"]])
        self.assertIn("reformuler par la porte", self.home_body())

    def test_only_decision_class_proposals_wait_on_the_operator(self):
        # ADR-0029 points 2-3: a `maintenance` proposal never enters « Ce
        # qui t'attend » (it is the health zone's « l'usine corrige seule »);
        # a `decision` one does; a proposal the door wrote before the class
        # existed (fields, no class) is still the operator's to treat.
        self.start_cockpit()
        self.write_beads(
            [
                proposal_bead("af-maint1", "filtrer les pages mortes", "trois pages périmées", SOME_OPTIONS,
                              "2026-10-07T08:00:00Z", state="prise_en_charge", classe="maintenance"),
                proposal_bead("af-deci1", "changer ce que tu vois", "nouvelle zone", SOME_OPTIONS,
                              "2026-10-07T08:00:00Z", classe="decision"),
                proposal_bead("af-avant1", "proposition d'avant la classe", "écrite par la porte", SOME_OPTIONS,
                              "2026-10-06T08:00:00Z"),
            ]
        )
        payload = self.wait_for_requests(lambda p: len(p["requests"]) == 2)
        self.assertEqual(["af-avant1", "af-deci1"], sorted(r["id"] for r in payload["requests"]))
        for req in payload["requests"]:
            self.assertEqual("Quand tu veux", req["niveau"])
            self.assertFalse(req["incomplete"])
        health = wait_until(
            lambda: next(
                (h for h in [http_get_json(self.port, "/api/health")]
                 if any("corrige seule" in l["text"] for l in h["lines"])),
                None,
            )
        )
        line = next(l for l in health["lines"] if "corrige seule" in l["text"])
        self.assertEqual("ok", line["kind"])
        self.assertIn("1 défaut", line["text"])
        self.assertNotIn("af-maint1", line["text"])
        self.assertNotIn("Mayor", line["text"])
        self.assertNotIn("filtrer les pages mortes", self.home_body().split("Santé de l")[0])

        # The maintenance proposal closed by its delivery leaves the health zone.
        self.write_beads(
            [
                proposal_bead("af-maint1", "filtrer les pages mortes", "trois pages périmées", SOME_OPTIONS,
                              "2026-10-07T08:00:00Z", state="resolue", classe="maintenance"),
            ]
        )
        wait_until(
            lambda: True
            if not any("corrige seule" in l["text"] for l in http_get_json(self.port, "/api/health")["lines"])
            else None
        )

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


class UnknownSignalSeamTest(CockpitOnFakes):
    """A signal of a type the cockpit does not know (spec af-fgcw0d user
    story 76, B af-4uzgzm): « Signal non reconnu venant de … », its raw
    text in the folded details only -- the cockpit never invents a
    meaning, and never drops it."""

    RAW_TITLE = "Disk quota at 92% on /var"
    RAW_TEXT = "backup volume nearly full, nothing rotated since Monday"

    def test_a_signal_of_an_unknown_producer_is_shown_with_its_raw_text_folded(self):
        self.start_cockpit()
        self.write_beads([
            {"id": "af-sig1", "status": "open", "labels": [], "notes": "", "title": self.RAW_TITLE,
             "description": self.RAW_TEXT, "created_at": "2026-09-30T08:00:00Z",
             "metadata": {"gc.source": "disk-watch"}},
            # Known: a producer that paged the Mayor first (spec .9), and a
            # session the Factory paused.
            {"id": "af-sig2", "status": "open", "labels": [], "notes": "", "title": "order failing",
             "description": "", "metadata": {"gc.source": "on-order-failed",
                                              "gc.escalation_mayor_paged_at": "2026-09-30T08:00:00Z"}},
            {"id": "af-sig3", "status": "open", "labels": [], "notes": "", "title": "[session-loop] s-1",
             "description": "", "metadata": {"gc.source": "factory-session-loop-guard", "gc.session_id": "s-1",
                                              "gc.escalation_mayor_paged_at": "2026-09-30T08:00:00Z"}},
            # Closed: it signals nothing any more.
            {"id": "af-sig4", "status": "closed", "labels": [], "notes": "", "title": "old", "description": "",
             "metadata": {"gc.source": "disk-watch"}},
        ])
        payload = self.wait_for_requests(lambda p: any(r["id"] == "af-sig1" for r in p["requests"]))
        by_id = {r["id"]: r for r in payload["requests"]}
        self.assertEqual(["af-sig1", "af-sig3"], sorted(by_id))
        signal = by_id["af-sig1"]
        self.assertEqual("Signal non reconnu venant de disk-watch", signal["quoi"])
        self.assertEqual("Quand tu veux", signal["niveau"])
        self.assertEqual("session_en_pause", by_id["af-sig3"]["type"])

        body = self.home_body()
        start = body.index('id="d-af-sig1"')
        article = body[start:body.index("</article>", start)]
        main, details = article.split('<details class="more pn-request-details">', 1)
        self.assertIn("Signal non reconnu venant de disk-watch", main)
        self.assertNotIn(self.RAW_TITLE, main, "the raw text is shown as main text")
        self.assertNotIn("backup volume", main, "the raw text is shown as main text")
        self.assertIn("Texte brut", details)
        self.assertIn(self.RAW_TITLE, details)
        self.assertIn(self.RAW_TEXT, details)

    def test_an_order_paused_by_its_door_waits_on_the_operator_with_its_relaunch(self):
        # As bin/order-pause (pause) records it (af-npz9v1.15); BR af-eyc5ah.
        self.start_cockpit()
        pause = {"gc.order_pause": "convoy-advance", "gc.order_pause_by": "mayor",
                 "gc.order_pause_words": "pause : intégration rouge", "gc.order_pause_at": "2026-09-30T08:00:00Z",
                 "gc.order_pause_reason": ""}
        self.write_beads([
            {"id": "af-ord1", "status": "open", "labels": ["order-pause"], "notes": "",
             "title": "Ordre en pause : convoy-advance", "description": "", "metadata": pause},
            # Resumed: its door closed the record.
            {"id": "af-ord2", "status": "closed", "labels": ["order-pause"], "notes": "",
             "title": "Ordre en pause : factory-guard", "description": "",
             "metadata": {**pause, "gc.order_pause": "factory-guard"}},
        ])
        payload = self.wait_for_requests(lambda p: any(r["id"] == "af-ord1" for r in p["requests"]))
        self.assertEqual(["af-ord1"], [r["id"] for r in payload["requests"]])
        [request] = payload["requests"]
        self.assertEqual("Un ordre de l’usine est en pause", request["quoi"])
        self.assertEqual("À faire", request["niveau"])
        self.assertEqual("ordre_en_pause", request["type"])

        body = self.home_body()
        start = body.index('id="d-af-ord1"')
        article = body[start:body.index("</article>", start)]
        main, details = article.split('<details class="more pn-request-details">', 1)
        self.assertNotIn("convoy-advance", main, "the name of the order is shown as main text")
        self.assertIn("convoy-advance", details)
        self.assertIn('data-action="relancer"', article)
        self.assertIn('data-target-type="order" data-order-name="convoy-advance"', article)


class TextContractSeamTest(CockpitOnFakes):
    """The control of the main text (spec af-oohx2x « Compréhensible sans
    IA », af-fgcw0d user story 73), read where the operator meets it: a
    request whose producer wrote a field outside the contract is listed by
    GET /api/requests with that field replaced by its repli
    (``missing_fields``), one written within it as written. AC5's "test"
    half."""

    def replaced(self, cases):
        """``{bead id: the fields of its request that were replaced}`` for
        escalations whose ``quoi`` and ``pourquoi`` are ``cases[id]``."""
        self.start_cockpit()
        self.write_beads([escalation_bead(bead_id, quoi, pourquoi, SOME_OPTIONS, "2026-09-30T08:00:00Z")
                          for bead_id, (quoi, pourquoi) in cases.items()])
        payload = self.wait_for_requests(lambda p: len(p["requests"]) == len(cases))
        return {r["id"]: [f for f in r["missing_fields"] if f in ("quoi", "pourquoi")] for r in payload["requests"]}

    def test_a_clean_field_is_shown_as_written(self):
        self.assertEqual({"af-ok01": []}, self.replaced({"af-ok01": ("une Spec attend ton accord", "elle change la portée")}))

    def test_a_missing_field_is_replaced(self):
        self.assertEqual({"af-mi01": ["pourquoi"]}, self.replaced({"af-mi01": ("une Spec attend ton accord", "")}))

    def test_an_identifier_is_replaced(self):
        self.assertEqual(
            {"af-id01": ["quoi"], "af-id02": ["quoi"]},
            self.replaced({"af-id01": ("voir af-is5e97 pour la suite", "elle change la portée"),
                           "af-id02": ("cf. #300 pour le contexte", "elle change la portée")}))

    def test_an_internal_term_outside_the_lexicon_is_replaced(self):
        self.assertEqual(
            {"af-te01": ["quoi"], "af-te02": ["quoi"], "af-te03": ["quoi"]},
            self.replaced({"af-te01": ("le bead est bloqué", "elle change la portée"),
                           "af-te02": ("un convoi est ouvert", "elle change la portée"),
                           "af-te03": ("le Mayor a redémarré", "elle change la portée")}))

    def test_a_line_over_140_characters_is_replaced(self):
        self.assertEqual({"af-lo01": ["quoi"], "af-lo02": []},
                         self.replaced({"af-lo01": ("x" * 141, "elle change la portée"),
                                        "af-lo02": ("x" * 140, "elle change la portée")}))

    def test_a_field_that_is_not_french_is_replaced(self):
        # User story 73: the main text is in the operator's language. A
        # sentence in English with neither an identifier nor an internal
        # term is not French either.
        self.assertEqual(
            {"af-en01": ["quoi"], "af-en02": ["pourquoi"], "af-fr01": []},
            self.replaced({
                "af-en01": ("The export format is waiting for your choice", "le projet attend ton choix"),
                "af-en02": ("Choisir le format d’export", "Readers want to keep their notes outside the project"),
                "af-fr01": ("Ajouter un export des notes en CSV", "Plusieurs lecteurs le demandent"),
            }))


if __name__ == "__main__":
    unittest.main()
