"""Home screen "Projets" zone, through the running process (af-mjfvwx).

T19/T20 built the projects and chantiers modules and tested their pure
functions; nothing served them. This test starts the real ``bin/cockpit``
on faked sources (fake gc, the controllable fake bd of the actions seam
test) and reads only what a browser gets: ``GET /``, ``GET /projets``,
``GET /projet/<id>``, ``GET /api/projects``,
``POST /api/actions/*``, and what the fake bd recorded.
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
WAIT_SECONDS = 30  # CI runners spawn the fake bd slowly; see cockpit-health-test.py


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


def convoy(bead_id, title, status, digest=None, project=None):
    metadata = {}
    if digest:
        metadata["gc.graph_digest"] = digest
        # Delivered, it waits for an acceptance by the cockpit's click: it
        # says what to look at (one without a note asks nothing; one of the
        # Delivery Workflow is accepted by bin/owner-answer, never by the
        # click -- cockpit-chantiers-test).
        metadata["gc.cockpit_acceptance_note"] = "Vérifier le résultat livré avant d'accepter"
    if project:
        metadata["gc.project_id"] = project
    return {
        "id": bead_id, "title": title, "status": status, "issue_type": "convoy",
        "labels": ["approved-ticket-graph"] if digest else [], "notes": "", "metadata": metadata,
    }


def ticket(bead_id, digest, status, rig="agent-factory", **metadata):
    metadata["gc.graph_digest"] = digest
    if rig:
        metadata["gc.dispatch_rig"] = rig
    return {
        "id": bead_id, "title": "ticket " + bead_id, "status": status, "issue_type": "task",
        "labels": ["approved-ticket-graph", "delivery-plane"], "notes": "", "metadata": metadata,
    }


def beads():
    question = {
        "gc.needs_benjamin": "les tests automatiques échouent pour la troisième fois",
        "gc.escalation_pourquoi": "l'usine a essayé seule pendant deux heures",
        "gc.escalation_que_faire": json.dumps([
            {"lettre": "a", "option": "relancer", "consequence": "le ticket reste dans le graphe"},
            {"lettre": "b", "option": "retirer ce ticket", "consequence": "le chantier se termine sans lui"},
        ]),
        "gc.escalation_bloquant": "true",
        "gc.escalation_horodatage": "2026-09-30T08:00:00Z",
    }
    return [
        # SayMyName, by its project key: in delivery, one ticket asks Benjamin.
        convoy("af-conv-a", "Export des listes", "open", "sha256:a", project="saymyname"),
        ticket("af-tk-a1", "sha256:a", "closed", rig="saymyname-backend"),
        ticket("af-tk-a2", "sha256:a", "in_progress", rig="saymyname-backend"),
        ticket("af-tk-a3", "sha256:a", "in_progress", rig="saymyname-backend", **{"gc.delivery_status": "waiting"}),
        ticket("af-tk-a4", "sha256:a", "open", rig="saymyname-backend", **question),
        # No project key: the rig of its tickets places it under Usine. Delivered, not accepted.
        convoy("af-conv-b", "Page d'accueil publique", "closed", "sha256:b"),
        ticket("af-tk-b1", "sha256:b", "closed"),
        ticket("af-tk-b2", "sha256:b", "closed"),
        # gc's own input convoy: a convoy bead, never a chantier.
        convoy("af-conv-c", "input convoy for af-zzzz", "open"),
        # Neither key nor rig: "Sans projet", a counted producer defect.
        convoy("af-conv-d", "Ancien chantier sans rattachement", "closed", "sha256:d"),
        ticket("af-tk-d1", "sha256:d", "closed", rig=None),
        # Work outside any chantier: no stage, shown on the project's page only.
        {
            "id": "af-bug1", "title": "Le bouton Recommencer ne répond plus", "status": "open",
            "issue_type": "bug", "labels": [], "notes": "", "metadata": {"gc.project_id": "agent-factory"},
        },
    ]


class HomeProjectsZoneTest(unittest.TestCase):
    def setUp(self):
        self.fake_gc = FakeGc().start()
        self.tmp = tempfile.TemporaryDirectory()
        self.state_file = os.path.join(self.tmp.name, "beads.json")
        self.calls_file = os.path.join(self.tmp.name, "calls.jsonl")
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

    def start_cockpit(self, descriptors=DESCRIPTORS):
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
                "COCKPIT_DESCRIPTORS_DIR": str(descriptors),
                "COCKPIT_BENJAMIN_LOGIN": BENJAMIN_LOGIN,
                "COCKPIT_ALLOWED_ORIGIN": self.origin,
                "FAKE_BD_STATE_FILE": self.state_file,
                "FAKE_BD_CALLS_FILE": self.calls_file,
                "FAKE_BD_FAIL_FLAG_FILE": self.fail_flag_file,
            }
        )
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

    def post_action(self, action, body, login=BENJAMIN_LOGIN):
        headers = {"Content-Type": "application/json", "Origin": self.origin, "Cookie": self.session_cookie}
        if login:
            headers["Tailscale-User-Login"] = login
        req = urllib.request.Request(
            "http://127.0.0.1:%d/api/actions/%s" % (self.port, action),
            data=json.dumps(body).encode("utf-8"), headers=headers, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def get_status(self, path):
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d%s" % (self.port, path), timeout=5) as resp:
                return resp.status, resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8")

    def projects(self):
        payload = self.get("/api/projects")
        return payload if payload["state"] == "filled" else None

    def chantiers(self, payload, project_id):
        project = next(p for p in payload["projects"] if p["project_id"] == project_id)
        return {c["id"]: c for c in project["chantiers"]}

    # ------------------------------------------------------------------
    def test_declared_projects_and_their_chantiers_are_served(self):
        self.start_cockpit()
        payload = wait_until(self.projects)

        self.assertEqual(["agent-factory", "saymyname"], [p["project_id"] for p in payload["projects"]])
        saymyname = self.chantiers(payload, "saymyname")
        self.assertEqual(["af-conv-a"], list(saymyname))
        self.assertEqual("Livraison", saymyname["af-conv-a"]["stage"])
        self.assertEqual("1/4 tickets mergés · 1 en cours · 1 en PR", saymyname["af-conv-a"]["detail"])
        self.assertEqual("probleme_remonte", saymyname["af-conv-a"]["etat"])
        self.assertEqual("af-tk-a4", saymyname["af-conv-a"]["etat_cible"])

        usine = self.chantiers(payload, "agent-factory")
        self.assertEqual(["af-conv-b"], list(usine), "a convoy with no project key follows its tickets' rig")
        self.assertEqual("Livré", usine["af-conv-b"]["stage"])
        self.assertEqual("a_toi_de_jouer", usine["af-conv-b"]["etat"])

        self.assertEqual(["af-conv-d"], [c["id"] for c in payload["sans_projet"]])
        everything = json.dumps(payload)
        self.assertNotIn("af-conv-c", everything, "gc's input convoy is not a chantier")

        body = wait_until(lambda: self.get("/") if 'id="d-af-tk-a4"' in self.get("/") else None)
        self.assertIn('<section class="zone cockpit-projects" data-state="filled">', body)
        self.assertIn("<h3>SayMyName</h3>", body)
        self.assertIn("<h3>Usine</h3>", body)
        self.assertIn("Livraison · 1/4 tickets mergés · 1 en cours · 1 en PR", body)
        self.assertIn("Livré : 2/2 tickets mergés", body)
        self.assertIn('class="stepper cockpit-stepper"', body)
        # "Problème remonté" leads in one click to the request that carries the question.
        self.assertIn('href="#d-af-tk-a4" data-goto="af-tk-a4"', body)
        self.assertIn("Problème remonté</a>", body)
        self.assertIn('<a class="li" href="#d-af-tk-a4" data-id="af-tk-a4"', body)
        # "À toi de jouer" on a delivered chantier opens its acceptance panel in place.
        self.assertIn('data-acc-open="af-conv-b"', body)
        self.assertIn('<div class="accpanel cockpit-chantier-actions" id="acc-af-conv-b" hidden>', body)
        self.assertIn('data-action="accepter_chantier" data-bead-id="af-conv-b"', body)
        self.assertIn('data-action="pas_bon_vers_agent" data-bead-id="af-conv-b"', body)
        self.assertIn("Sans projet", body)
        self.assertIn("1 défaut producteur", body)
        self.assertIn('href="/projet/agent-factory"', body)
        self.assertIn('href="/projet/saymyname"', body)
        wait_until(lambda: "Tout est à jour à" in self.get("/"))

    # ------------------------------------------------------------------
    def test_accepting_a_delivered_chantier_takes_two_steps_and_is_traced(self):
        self.start_cockpit()
        wait_until(self.projects)

        status, payload = self.post_action("accepter_chantier", {"bead_id": "af-conv-b", "confirm": True}, login=None)
        self.assertEqual(403, status)
        status, payload = self.post_action("accepter_chantier", {"bead_id": "af-conv-b"})
        self.assertEqual(400, status)
        self.assertEqual("confirmation requise", payload["error"])
        self.assertNotIn("gc.cockpit_chantier_accepted", self.read_beads()["af-conv-b"]["metadata"])

        status, payload = self.post_action("accepter_chantier", {"bead_id": "af-conv-b", "confirm": True})
        self.assertEqual(200, status, payload)
        self.assertIn("Chantier accepté à ", payload["display"])
        accepted = self.read_beads()["af-conv-b"]
        self.assertEqual("true", accepted["metadata"]["gc.cockpit_chantier_accepted"])
        self.assertEqual("benjamin", accepted["metadata"]["gc.cockpit_action_acteur"])
        self.assertIn("Cockpit: accepter_chantier", accepted["notes"])

        # Accepted is this chantier's last stage (no promotion branch): it leaves the active list.
        wait_until(lambda: self.projects() and "af-conv-b" not in self.chantiers(self.projects(), "agent-factory"))
        self.assertNotIn('id="ch-af-conv-b"', self.get("/"))

    def test_pas_bon_gives_a_prompt_and_writes_nothing(self):
        self.start_cockpit()
        wait_until(self.projects)
        before = self.read_beads()
        status, payload = self.post_action(
            "pas_bon_vers_agent", {"bead_id": "af-conv-b", "titre": "Page d'accueil publique"}
        )
        self.assertEqual(200, status, payload)
        self.assertIn("af-conv-b", payload["prompt"])
        self.assertIn("Page d'accueil publique", payload["prompt"])
        self.assertIn("consomme des tokens", payload["prompt"])
        self.assertEqual(before, self.read_beads())

    # ------------------------------------------------------------------
    # The project page (spec .49): Benjamin chose a selector between the
    # prototype's "Tableau" and "Bande" (af-1al0t1, 2026-09-30).
    # ------------------------------------------------------------------
    def test_project_page_is_served_with_both_views(self):
        self.start_cockpit()
        wait_until(self.projects)

        status, page = self.get_status("/projet/saymyname")
        self.assertEqual(200, status)
        self.assertIn("Atkinson+Hyperlegible+Next", page)
        # The head of the page is the reference's (E, af-8rbceu): the way
        # back to « Projets », then the name of the project.
        self.assertRegex(page, r'<div class="pf-crumb" data-anchor="crumb-1">.*?← Projets</button>')
        self.assertRegex(page, r'<h1 data-anchor="h1-1">SayMyName</h1>')
        self.assertIn("<b>1</b> chantier actif</span>", page)
        self.assertIn('<span class="chip probleme">1 problème remonté</span>', page)
        self.assertIn('href="#cockpit-pp-historique">Historique du projet →</a>', page)
        # Both views are in the page; the selector only picks which one shows.
        self.assertIn('data-view-choice="tableau">Tableau</button>', page)
        self.assertIn('data-view-choice="bande">Bande</button>', page)
        self.assertIn('<div class="cockpit-pp-view cockpit-pp-view-tableau"><div class="v1">', page)
        self.assertIn('<div class="cockpit-pp-view cockpit-pp-view-bande"><div class="v3">', page)
        # Tableau: one column per stage, Promu included for a project with a promotion branch.
        self.assertIn('style="--n:7"', page)
        self.assertIn('<div class="bh cockpit-pp-col-h" data-stage="Promu">', page)
        self.assertIn('<div class="card cockpit-pp-card" data-chantier="af-conv-a">', page)
        # Bande: the chantier with its own stepper and stage names.
        self.assertIn('<div class="s-item cockpit-pp-strip-item" data-chantier="af-conv-a" data-stage="Livraison">', page)
        self.assertIn('<span class="on">Livraison</span>', page)
        # A chip leads to the home screen, where the request lives.
        self.assertIn('href="/#d-af-tk-a4"', page)
        wait_until(lambda: "Tout est à jour à" in self.get("/projet/saymyname"))

        status, usine = self.get_status("/projet/agent-factory")
        self.assertEqual(200, status)
        self.assertIn('style="--n:6"', usine)
        self.assertNotIn('data-stage="Promu"', usine, "no Promu for a project with no promotion branch")
        self.assertNotIn(">Promu</span>", usine)
        self.assertIn('href="/#acc-af-conv-b"', usine)
        self.assertIn("Travail hors chantier", usine)
        self.assertIn('data-kind="Bug" data-chantier="af-bug1" data-stage=""', usine)
        self.assertIn("Le bouton Recommencer ne répond plus", usine)
        self.assertIn("Aucun chantier terminé ou abandonné.", usine)
        self.assertNotIn("af-conv-a", usine, "another project's chantier never shows here")


    # ------------------------------------------------------------------
    # The destination Projets of Panorama (E, af-8rbceu): a card per
    # project, the whole card the link to its page, its counts.
    # ------------------------------------------------------------------
    def test_a_project_card_is_one_link_counting_what_waits_what_is_open_and_its_runs(self):
        now = time.time()

        def at(seconds_ago):
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - seconds_ago))

        def run(bead_id, rig, seconds_ago, merged=False):
            """A ticket a delivery author was launched on `seconds_ago`, at
            work still, or closed and merged then."""
            metadata = {"gc.ticket_id": bead_id.upper(), "gc.dispatch_rig": rig,
                        "gc.flow.gate.dispatch": json.dumps({"at": at(seconds_ago)}),
                        "gc.flow.models": json.dumps({"author": {"agent": "delivery-author", "at": at(seconds_ago),
                                                                 "model": "claude-opus-5-5"}})}
            bead = {"id": bead_id, "title": "%s — Une page" % bead_id.upper(), "status": "in_progress",
                    "issue_type": "task", "labels": [], "notes": "", "metadata": metadata,
                    "updated_at": at(seconds_ago)}
            if merged:
                metadata["gc.flow.merge"] = json.dumps({"at": at(seconds_ago - 60), "outcome": "merged"})
                bead.update(status="closed", closed_at=at(seconds_ago - 60))
            return bead

        self.write_beads(beads() + [
            run("af-run-live", "agent-factory", 600),
            run("af-run-merged", "agent-factory", 3600, merged=True),
            run("af-run-old", "agent-factory", 8 * 86400, merged=True),
            # A run of a rig named as another project: that project's.
            run("af-run-other", "saymyname", 300, merged=True),
        ])
        self.start_cockpit()
        wait_until(self.projects)
        page = wait_until(lambda: (lambda body: body if "Runs ouverts" in body and "Dernier run" in body else None)(
            self.get("/projets")))
        cards = re.findall(r'<a class="pj-card".*?</a>', page, re.S)
        self.assertEqual(2, len(cards), "not one card per declared project")
        usine = next(card for card in cards if 'href="/projet/agent-factory"' in card)
        # The whole card is the one link to the page of the project, named
        # by what it says.
        self.assertRegex(usine, r'^<a class="pj-card" href="/projet/agent-factory" aria-label="Page projet Usine · '
                                r'À toi de jouer · 1 · ')
        self.assertEqual(1, usine.count("<a "), "a link inside the card")
        self.assertIn("<dt>Chantiers ouverts</dt><dd>1</dd>", usine)
        # Its runs only: merged within 7 days, and at work.
        self.assertIn("<dt>Runs fusionnés · 7 j</dt><dd>1</dd>", usine)
        self.assertIn("<dt>Runs ouverts</dt><dd>1</dd>", usine)
        self.assertIn("Dernier run : AF-RUN-LIVE · En cours", usine)
        saymyname = next(card for card in cards if 'href="/projet/saymyname"' in card)
        self.assertIn("<dt>Runs fusionnés · 7 j</dt><dd>1</dd>", saymyname)
        self.assertIn("<dt>Runs ouverts</dt><dd>0</dd>", saymyname)

    def test_a_project_without_run_says_so(self):
        self.start_cockpit()
        wait_until(self.projects)
        page = wait_until(lambda: (lambda body: body if '<a class="pj-card"' in body else None)(self.get("/projets")))
        self.assertIn("Aucun run lu pour ce projet", page)

    def test_no_project_declared_is_said(self):
        empty = os.path.join(self.tmp.name, "descriptors")
        os.mkdir(empty)
        self.start_cockpit(descriptors=empty)
        page = wait_until(lambda: (lambda body: body if "Aucun projet déclaré" in body else None)(self.get("/projets")))
        self.assertNotIn('<a class="pj-card"', page)

    def test_each_section_of_the_project_page_is_reached_by_its_heading(self):
        # E, af-8rbceu: the label of each section, written small as the
        # reference draws it, is a heading -- a navigation by headings
        # reaches the current chantier and the roadmap.
        self.start_cockpit()
        wait_until(self.projects)
        _, page = self.get_status("/projet/saymyname")
        headings = [" ".join(re.sub(r"<[^>]+>", " ", inner).split())
                    for _, inner in re.findall(r"<h([1-6])\b[^>]*>(.*?)</h\1>", page, re.S)]
        for label in ("CHANTIER ACTUEL", "ROADMAP"):
            self.assertIn(label, headings, "a section of the page of the project is not a heading")
    def test_accepted_chantier_moves_to_its_project_history(self):
        self.start_cockpit()
        wait_until(self.projects)
        status, payload = self.post_action("accepter_chantier", {"bead_id": "af-conv-b", "confirm": True})
        self.assertEqual(200, status, payload)
        page = wait_until(
            lambda: self.get("/projet/agent-factory")
            if 'class="cockpit-historique-row"' in self.get("/projet/agent-factory")
            else None
        )
        self.assertIn('data-kind="termine" data-stage="Accepté"', page)
        self.assertIn("Page d&#x27;accueil publique", page)
        self.assertIn("<b>0</b> chantier actif</span>", page)

    def test_unknown_project_is_a_404_that_says_so(self):
        self.start_cockpit()
        wait_until(self.projects)
        status, page = self.get_status("/projet/nimporte-quoi")
        self.assertEqual(404, status)
        self.assertIn("Projet inconnu", page)
        self.assertIn('href="/">← Accueil</a>', page)

    def test_recheck_from_a_project_page_returns_to_it(self):
        self.start_cockpit()
        wait_until(self.projects)

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None

        opener = urllib.request.build_opener(NoRedirect)
        req = urllib.request.Request(
            "http://127.0.0.1:%d/api/health/recheck" % self.port, data=b"", method="POST",
            headers={"Referer": self.origin + "/projet/saymyname"},
        )
        try:
            opener.open(req, timeout=20)
            self.fail("expected a 303")
        except urllib.error.HTTPError as exc:
            self.assertEqual(303, exc.code)
            self.assertEqual("/projet/saymyname", exc.headers["Location"])

    # ------------------------------------------------------------------
    def test_unreadable_projects_are_unknown_never_an_empty_list(self):
        Path(self.fail_flag_file).write_text("fail")
        self.start_cockpit()
        payload = self.get("/api/projects")
        self.assertEqual("unknown", payload["state"])
        self.assertEqual([], payload["projects"])
        body = self.get("/")
        self.assertIn('<section class="zone cockpit-projects" data-state="unknown">', body)
        self.assertIn("Inconnu : projets illisibles", body)
        self.assertNotIn("Aucun chantier actif", body)
        self.assertNotIn("Tout est à jour à", body)
        self.assertIn("projets (inconnu)", body)
        status, page = self.get_status("/projet/saymyname")
        self.assertEqual(200, status)
        self.assertIn("Inconnu : projets illisibles", page)
        self.assertNotIn("Projet inconnu", page, "an unreadable source is not an unknown project")

        os.remove(self.fail_flag_file)
        wait_until(self.projects)
        wait_until(lambda: "Tout est à jour à" in self.get("/"))


if __name__ == "__main__":
    unittest.main()
