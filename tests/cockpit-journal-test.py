"""The journal des demandes résolues, through the running process
(af-mjfvwx; spec af-oohx2x .18, .19).

T15 built the journal's parsing and rendering and tested them on Beads
comments; the doors and the cockpit write their traces in a bead's
**notes** (``bd update --append-notes``), and no route served the journal.
The beads here carry notes and metadata exactly as the escalation door,
the proposal door and :mod:`cockpit.actions.trace` leave them. The test
starts the real ``bin/cockpit`` on faked sources and reads only ``GET
/journal``, ``GET /api/journal``, ``GET /`` and ``POST /api/actions/*``.
"""
import json
import os
import re
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


def bead(bead_id, notes, status="closed", labels=(), **metadata):
    return {
        "id": bead_id, "title": "titre " + bead_id, "status": status, "issue_type": "task",
        "labels": list(labels), "notes": "\n".join(notes), "metadata": metadata,
    }


def beads():
    return [
        # Answered through escalation-door: the note, and the answer's date in metadata.
        bead(
            "af-rep1",
            ["NEEDS BENJAMIN: l'étape 1 est livrée, la suite attend ton accord", "RÉPONSE: a — lever la barrière"],
            **{
                "gc.needs_benjamin": "none", "gc.escalation_response_option": "a",
                "gc.escalation_response_at": "2026-10-06T11:08:55Z", "gc.escalation_response_actor": "benjamin",
            },
        ),
        # Cleared without an answer: escalation-door stamps no date.
        bead(
            "af-clr1",
            ["NEEDS BENJAMIN: une question restée ouverte", "DECISION CLEARED: escalation reset to none"],
            **{"gc.needs_benjamin": "none"},
        ),
        # Cleared since the door dates its clearance (gc.escalation_cleared_at).
        bead(
            "af-clr2",
            ["NEEDS BENJAMIN: une autre question", "DECISION CLEARED: escalation reset to none"],
            **{"gc.needs_benjamin": "none", "gc.escalation_cleared_at": "2026-10-05T12:00:00Z"},
        ),
        # A proposal rejected with its reason.
        bead(
            "af-prop1",
            ["PROPOSITION: regrouper deux rituels", "PROPOSITION REJETÉE par benjamin — déjà couvert ailleurs"],
            status="open", labels=["proposal"],
            **{
                "gc.proposal_state": "rejetee", "gc.proposal_quoi": "regrouper deux rituels",
                "gc.proposal_response_at": "2026-10-05T09:00:00Z", "gc.proposal_response_actor": "benjamin",
            },
        ),
        # Asked, answered, asked again, answered again: two resolutions (spec .19).
        bead(
            "af-twice",
            [
                "NEEDS BENJAMIN: premier choix à faire", "RÉPONSE: b — attendre",
                "NEEDS BENJAMIN: second choix à faire", "RÉPONSE: a — continuer",
            ],
            **{
                "gc.needs_benjamin": "none", "gc.escalation_response_option": "a",
                "gc.escalation_response_at": "2026-10-04T08:00:00Z", "gc.escalation_response_actor": "benjamin",
            },
        ),
        # A request whose text may not be main text (internal words, an identifier).
        bead(
            "af-raw1",
            ["NEEDS BENJAMIN: Escalade Mayor-first non résolue : 'pr-autopilot' failed 7 times", "DECISION CLEARED: escalation reset to none"],
            **{"gc.needs_benjamin": "none"},
        ),
        # Still waiting: a live request, not a journal entry.
        bead(
            "af-open1", ["NEEDS BENJAMIN: une demande encore ouverte"], status="open",
            **{
                "gc.needs_benjamin": "une demande encore ouverte", "gc.escalation_pourquoi": "elle attend toujours",
                "gc.escalation_que_faire": json.dumps([{"lettre": "a", "option": "répondre", "consequence": "le travail reprend"}]),
                "gc.escalation_horodatage": "2026-10-06T08:00:00Z", "gc.escalation_bloquant": "false",
            },
        ),
        # A delivered chantier, to be accepted from the cockpit during the test.
        {
            "id": "af-conv-b", "title": "Page d'accueil publique", "status": "closed", "issue_type": "convoy",
            "labels": ["approved-ticket-graph"], "notes": "", "metadata": {"gc.graph_digest": "sha256:b"},
        },
        {
            "id": "af-tk-b1", "title": "ticket", "status": "closed", "issue_type": "task",
            "labels": ["approved-ticket-graph", "delivery-plane"], "notes": "",
            "metadata": {"gc.graph_digest": "sha256:b", "gc.dispatch_rig": "agent-factory"},
        },
    ]


class JournalTest(unittest.TestCase):
    def setUp(self):
        self.fake_gc = FakeGc().start()
        self.tmp = tempfile.TemporaryDirectory()
        self.state_file = os.path.join(self.tmp.name, "beads.json")
        self.fail_flag_file = os.path.join(self.tmp.name, "fail")
        self.port = free_port()
        self.origin = "http://127.0.0.1:%d" % self.port
        self.proc = None
        with open(self.state_file, "w") as fh:
            json.dump(beads(), fh)

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

    def start_cockpit(self, **extra_env):
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
                "COCKPIT_JOURNAL_POLL_SECONDS": "0.2",
                "COCKPIT_DESCRIPTORS_DIR": str(DESCRIPTORS),
                "COCKPIT_BENJAMIN_LOGIN": BENJAMIN_LOGIN,
                "COCKPIT_ALLOWED_ORIGIN": self.origin,
                "FAKE_BD_STATE_FILE": self.state_file,
                "FAKE_BD_CALLS_FILE": os.path.join(self.tmp.name, "calls.jsonl"),
                "FAKE_BD_FAIL_FLAG_FILE": self.fail_flag_file,
            }
        )
        env.update(extra_env)
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

    def journal(self):
        payload = self.get("/api/journal")
        return payload if payload["state"] == "filled" else None

    def entry_html(self, page, bead_id, nth=0):
        marker = '<div class="cockpit-journal-entry" data-bead-id="%s"' % bead_id
        start = -1
        for _ in range(nth + 1):
            start = page.index(marker, start + 1)
        end = page.find('<div class="cockpit-journal-entry"', start + 1)
        return page[start:end if end != -1 else len(page)]

    # ------------------------------------------------------------------
    def test_journal_is_reread_from_the_traces_on_the_beads(self):
        self.start_cockpit()
        payload = wait_until(self.journal)
        entries = payload["entries"]
        self.assertEqual(7, len(entries), entries)
        self.assertNotIn("af-open1", [e["bead_id"] for e in entries], "a request still waiting is not resolved")

        # Newest first; what no trace dates comes last.
        self.assertEqual(["af-rep1", "af-clr2", "af-prop1", "af-twice"], [e["bead_id"] for e in entries[:4]])
        self.assertTrue(all(not e["quand"] for e in entries[4:]))
        # Resolved twice: two entries, each with the question it answered (spec .19).
        twice = [e for e in entries if e["bead_id"] == "af-twice"]
        self.assertEqual(
            {("premier choix à faire", "répondu b — attendre"), ("second choix à faire", "répondu a — continuer")},
            {(e["demande"], e["quoi"]) for e in twice},
        )

        page = self.get("/journal?filtre=tout")
        # Panorama: the destination Journal, its categories (each a button
        # of a form sent by GET), a timeline by day.
        self.assertIn(">Journal</h1>", page)
        self.assertIn('name="categorie" value="decisions"', page)
        self.assertIn('class="jn-day"', page)

        answered = self.entry_html(page, "af-rep1")
        self.assertIn("l&#x27;étape 1 est livrée, la suite attend ton accord", answered)   # quoi
        self.assertIn("répondu a — lever la barrière", answered)
        self.assertIn("<time>06/10 13:08</time>", answered)                                  # quand, Paris
        self.assertIn("<span>par benjamin</span>", answered)                                 # par qui
        self.assertIn("<span>réponse à une demande</span>", answered)                        # quelle voie

        rejected = self.entry_html(page, "af-prop1")
        self.assertIn("regrouper deux rituels", rejected)
        self.assertIn("proposition rejetée — déjà couvert ailleurs", rejected)
        self.assertIn("<span>décision sur une proposition</span>", rejected)

        self.assertIn("<time>05/10 14:00</time>", self.entry_html(page, "af-clr2"))
        cleared = self.entry_html(page, "af-clr1")
        self.assertIn("Effacée sans réponse enregistrée", cleared)
        self.assertIn("date inconnue", cleared)
        # What no trace dates is listed last, under a day said unknown.
        days = re.findall(r'<h2 class="jn-day"[^>]*>([^<]*)</h2>', page)
        self.assertEqual("Date inconnue", days[-1], days)
        self.assertNotIn("<span>par ", cleared, "a trace that names nobody shows no author")

        # Benjamin, 2026-10-06: « affiche tel quel » -- the journal is a record,
        # it shows a text exactly as its producer wrote it, unlike the inbox.
        raw = self.entry_html(page, "af-raw1")
        self.assertIn("Escalade Mayor-first non résolue : &#x27;pr-autopilot&#x27; failed 7 times", raw.partition("<details")[0])
        self.assertIn("<code>af-rep1</code>", answered.partition("<details")[2])
        # The inbox keeps its control: the same kind of text there falls back.
        self.assertNotIn("Mayor", self.get("/"))

        # The home page leads to the journal: the entry « Journal » of its
        # navigation opens /journal (a button of a form sent by GET).
        self.assertIn('action="/journal"', self.get("/"))

    def test_an_action_taken_in_the_cockpit_enters_the_journal(self):
        self.start_cockpit()
        wait_until(self.journal)
        req = urllib.request.Request(
            "http://127.0.0.1:%d/api/actions/accepter_chantier" % self.port,
            data=json.dumps({"bead_id": "af-conv-b", "confirm": True}).encode("utf-8"), method="POST",
            headers={
                "Content-Type": "application/json", "Origin": self.origin,
                "Cookie": self.session_cookie, "Tailscale-User-Login": BENJAMIN_LOGIN,
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(200, resp.status)
        entry = wait_until(
            lambda: next((e for e in (self.journal() or {"entries": []})["entries"] if e["bead_id"] == "af-conv-b"), None)
        )
        self.assertEqual("Chantier accepté", entry["quoi"])
        self.assertEqual("Page d'accueil publique", entry["demande"])
        self.assertEqual("benjamin", entry["par"])
        self.assertTrue(entry["quand"])
        accepted = self.entry_html(self.get("/journal?filtre=tout"), "af-conv-b")
        self.assertIn("<span>action dans le cockpit</span>", accepted)
        self.assertNotIn("accepter_chantier", accepted.partition("<details")[0])
        # The newest entry heads the journal.
        self.assertEqual("af-conv-b", self.journal()["entries"][0]["bead_id"])

    def test_an_event_held_for_the_journal_is_an_entry_of_its_own(self):
        # Two event beads as `bd create --type event` writes them (T01R6,
        # af-ltchro): no notes, their nature under gc.journal_event, their
        # time as created_at -- written with an offset, unlike the traces.
        # 13:30+02:00 is 11:30Z, after af-rep1 (11:08:55Z); 12:00+02:00 is
        # 10:00Z, before it, though its text sorts after it.
        events = [
            {"id": "af-ev1", "title": "Release 1.4 publiée", "status": "closed", "issue_type": "event",
             "labels": ["livraison"], "notes": "", "created_at": "2026-10-06T13:30:00+02:00",
             "metadata": {"gc.journal_event": "livraison"}},
            {"id": "af-ev2", "title": "Rapport nocturne reçu", "status": "closed", "issue_type": "event",
             "labels": ["ci"], "notes": "", "created_at": "2026-10-06T12:00:00+02:00",
             "metadata": {"gc.journal_event": "ci"}},
        ]
        with open(self.state_file, "w") as fh:
            json.dump(beads() + events, fh)
        self.start_cockpit()
        entries = wait_until(self.journal)["entries"]

        self.assertEqual(9, len(entries), entries)
        self.assertEqual(["af-ev1", "af-rep1", "af-ev2", "af-clr2"], [e["bead_id"] for e in entries[:4]])
        self.assertEqual(
            {"bead_id": "af-ev1", "demande": "", "quoi": "Release 1.4 publiée",
             "quand": "2026-10-06T13:30:00+02:00", "par": "", "voie": "livraison"},
            {k: entries[0].get(k) for k in ("bead_id", "demande", "quoi", "quand", "par", "voie")},
        )

        # Both are events of technical sources (delivery, CI): logs of the
        # journal (F, af-njwz8v), each under its title and at its time.
        logs = self.get("/journal?vue=logs")
        event = logs[logs.index('data-bead-id="af-ev1"'):logs.index('data-bead-id="af-ev2"')]
        self.assertIn("Release 1.4 publiée", event)
        self.assertIn("13:30 (Paris) · Livraison", event)
        self.assertIn("12:00 (Paris) · CI", logs[logs.index('data-bead-id="af-ev2"'):])
        # An event answers no request: no request block, not even the empty one.
        self.assertNotIn("cockpit-journal-demande", event)
        self.assertNotIn("Demande sans texte enregistré", event)
        # They are not useful events: the journal of those does not list them.
        self.assertNotIn('data-bead-id="af-ev1"', self.get("/journal?filtre=tout"))
        # Words no log says: the page says which.
        self.assertIn("Aucun log ne contient « absent ».", self.get("/journal?vue=logs&q=absent"))

    def test_unreadable_journal_is_unknown_never_empty(self):
        Path(self.fail_flag_file).write_text("fail")
        self.start_cockpit()
        self.assertEqual("unknown", self.get("/api/journal")["state"])
        # Being read, then once the read failed: never an empty journal.
        self.assertNotIn("Rien à afficher ici", self.get("/journal?filtre=tout"))
        page = wait_until(lambda: (lambda p: p if "Cette vue est indisponible" in p else None)(
            self.get("/journal?filtre=tout")))
        self.assertNotIn("Aucune demande résolue", page)
        self.assertNotIn("Rien à afficher ici", page)
        # No source is said connected or absent while the journal cannot be read.
        self.assertIn("<strong>CI</strong> · inconnue — la source ne répond pas", self.get("/journal?vue=sources"))
        os.remove(self.fail_flag_file)
        wait_until(self.journal)

    def test_a_journal_read_lasts_as_long_as_the_cockpit_allows_it(self):
        # A tracker that never answers, and a cockpit that allows the journal
        # one second per read: the journal says its read failed well before
        # the twenty seconds it allows itself otherwise -- the isolated
        # recipe allows 24 hours, and a reading under way stays one.
        self.start_cockpit(COCKPIT_BD_BIN=str(ROOT / "tests" / "fixtures" / "cockpit" / "requests" / "silent-bd"),
                           COCKPIT_JOURNAL_READ_TIMEOUT_SECONDS="1")
        self.assertIn("Lecture en cours…", self.get("/journal"))
        wait_until(lambda: "Cette vue est indisponible" in self.get("/journal"), timeout=10)

    # The Journal Prototype Fold (F, af-njwz8v) -------------------------

    def write_beads(self, *extra):
        with open(self.state_file, "w") as fh:
            json.dump(beads() + list(extra), fh)

    def test_a_category_keeps_its_own_and_a_former_filter_names_its_category(self):
        self.start_cockpit()
        wait_until(self.journal)
        decisions = self.get("/journal?categorie=decisions")
        self.assertIn('aria-current="true" data-anchor="primary-2">Décisions', decisions)
        self.assertIn('data-bead-id="af-rep1"', decisions)
        self.assertNotIn('data-bead-id="af-prop1"', decisions)
        self.assertNotIn('data-bead-id="af-clr1"', decisions)
        # The filters of the journal before its tabs still open a category:
        # « Effacées » is now under « Événements ».
        cleared = self.get("/journal?filtre=effacees")
        self.assertIn('aria-current="true" data-anchor="primary-2">Événements', cleared)
        self.assertIn('data-bead-id="af-clr1"', cleared)
        self.assertNotIn('data-bead-id="af-rep1"', cleared)

    def test_a_merged_run_is_a_change_of_the_journal_that_leads_to_its_run(self):
        self.write_beads({
            "id": "af-tk-run", "title": "Une page", "status": "closed", "issue_type": "task", "labels": [],
            "notes": "", "closed_at": "2026-10-06T10:05:00Z",
            "metadata": {
                "gc.flow.models": json.dumps({"author": {"at": "2026-10-06T09:00:00Z", "model": "m"}}),
                "gc.flow.merge": json.dumps({"at": "2026-10-06T10:00:00Z", "outcome": "merged"}),
            },
        })
        self.start_cockpit()
        wait_until(self.journal)
        page = wait_until(lambda: (lambda p: p if 'data-bead-id="af-tk-run"' in p else None)(
            self.get("/journal?categorie=changements")))
        merged = page[page.index('data-bead-id="af-tk-run"'):]
        merged = merged[:merged.index("</article>")]
        self.assertIn("fusionné · Une page", merged)
        self.assertIn("12:00 (Paris) · Changement", merged)
        self.assertIn('action="/runs/run?id=af-tk-run"', merged)
        self.assertIn("Voir le run", merged)
        self.assertNotIn('data-bead-id="af-rep1"', page, "a decision is not a change")

    def test_secrets_and_private_reasoning_never_leave_a_raw_event(self):
        # Secrets of no known shape, under the names of a JSON key or of a
        # field; a private reasoning, quoted or written to the end of its line.
        raw = [
            '{"password": "hunter2-correct-horse", "job": "regression"}',
            '{"api_key":"k0123456789abcdefXYZ","exit":1}',
            'session.started role=author reasoning=je pense que la clé est dans le fichier privé',
            '{"thinking": "une pensée privée \\"citée\\" du modèle", "outcome": "failure"}',
            '{"reasoning": {"steps": ["étape privée une", "étape privée deux"]}, "kept": "visible"}',
        ]
        private = ["hunter2-correct-horse", "k0123456789abcdefXYZ", "je pense", "la clé est dans le fichier privé",
                   "une pensée privée", "citée", "étape privée"]
        self.write_beads({
            "id": "af-ev-secret", "title": "Vérification échouée", "status": "closed", "issue_type": "event",
            "labels": ["ci"], "notes": "", "created_at": "2026-10-06T13:30:00+02:00",
            "metadata": {"gc.journal_event": "ci", "gc.journal_folded": json.dumps(raw)},
        })
        self.start_cockpit()
        wait_until(lambda: any(e["bead_id"] == "af-ev-secret" for e in (self.journal() or {"entries": []})["entries"]))
        served = {"GET /journal?vue=logs": self.get("/journal?vue=logs"),
                  "GET /api/journal": json.dumps(self.get("/api/journal"), ensure_ascii=False)}
        self.assertEqual([], [(where, words) for where, body in served.items() for words in private if words in body],
                         "a secret or a private reasoning is served")
        # What the raw event says otherwise stays as received.
        logs = served["GET /journal?vue=logs"]
        for kept in ("regression", "role=author", "outcome", "failure", "kept", "visible", "exit"):
            self.assertIn(kept, logs)

    def test_a_source_declared_connected_stays_connected_while_it_is_silent(self):
        # A source the factory declares connected (a bead naming it under
        # gc.journal_source) that sent nothing yet; and CI, which sent a log.
        self.write_beads(
            {"id": "af-src-agents", "title": "Source des logs : agents", "status": "open", "issue_type": "task",
             "labels": [], "notes": "", "metadata": {"gc.journal_source": "agents"}},
            {"id": "af-ev-ci", "title": "Rapport nocturne reçu", "status": "closed", "issue_type": "event",
             "labels": ["ci"], "notes": "", "created_at": "2026-10-06T12:00:00+02:00",
             "metadata": {"gc.journal_event": "ci"}},
        )
        self.start_cockpit()
        wait_until(self.journal)
        sources = self.get("/journal?vue=sources")
        self.assertIn("<strong>CI</strong> · raccordée — 1 log lu", sources)
        self.assertIn("<strong>Agents</strong> · raccordée — aucun log reçu", sources)
        self.assertIn("<strong>Livraison</strong> · absente — aucun log reçu", sources)

    def test_no_model_is_called_to_read_or_label_the_journal(self):
        # Every way out of the cockpit to a model is recorded: the network,
        # through a proxy, the providers' own addresses, and their commands.
        recorder = Recorder().start()
        self.addCleanup(recorder.stop)
        shims = Path(self.tmp.name) / "bin"
        shims.mkdir()
        calls = Path(self.tmp.name) / "model-commands.log"
        for name in ("claude", "codex", "gemini", "llm", "ollama"):
            shim = shims / name
            shim.write_text('#!/bin/sh\necho "%s $*" >> "%s"\n' % (name, calls))
            shim.chmod(0o755)
        self.write_beads({
            "id": "af-ev-unknown", "title": "Une note étrange", "status": "closed", "issue_type": "event",
            "labels": [], "notes": "", "created_at": "2026-10-06T12:00:00+02:00",
            "metadata": {"gc.journal_event": "mystere"},
        })
        self.start_cockpit(
            HTTP_PROXY=recorder.url, HTTPS_PROXY=recorder.url, ALL_PROXY=recorder.url,
            http_proxy=recorder.url, https_proxy=recorder.url, all_proxy=recorder.url,
            NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost",
            ANTHROPIC_BASE_URL=recorder.url, OPENAI_BASE_URL=recorder.url, OPENAI_API_BASE=recorder.url,
            OLLAMA_HOST=recorder.url, PATH="%s:%s" % (shims, os.environ.get("PATH", "")),
        )
        wait_until(self.journal)
        pages = [self.get(path) for path in ("/journal", "/journal?vue=logs", "/journal?vue=sources",
                                             "/journal?categorie=evenements")]
        # The labels are the fixed ones of each type; the unknown event is
        # said by the fallback, not given a meaning.
        self.assertIn("Signal non reconnu venant d’une source inconnue", pages[0])
        self.assertIn("Événement non reconnu", pages[1])
        self.assertIn("Libellés fixes par type d’événement ; aucun appel de modèle.", pages[1])
        self.assertEqual([], recorder.requests, "the cockpit called out while it read the journal")
        self.assertFalse(calls.exists(), "the cockpit ran a model command: %s" % (
            calls.read_text() if calls.exists() else ""))


class Recorder:
    """An HTTP server that answers 503 to everything and records what it
    was asked: where the cockpit would reach a model."""

    def __init__(self):
        import http.server
        import threading

        recorded = self.requests = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def _record(self):
                recorded.append("%s %s" % (self.command, self.path))
                self.send_response(503)
                self.send_header("Content-Length", "0")
                self.end_headers()

            do_GET = do_POST = do_PUT = do_CONNECT = _record

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:%d" % self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


if __name__ == "__main__":
    unittest.main()
