"""The cockpit HTTP process — pure code, 127.0.0.1 only (spec .9, AC4).

Binding anywhere else is refused outright rather than merely discouraged by
config: a local process already has every power on this host (spec .9
threat model), but the cockpit is still not allowed to become reachable
from the tailnet or LAN by an operator mistake in a config file.
"""
import logging
import subprocess
import time
import threading
import json
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cockpit.access.guard import session_cookie_header
from cockpit.actions.registry import ActionError, ActionUncertain, expired
from cockpit.actions.uncertain import UncertainOutcomes
from cockpit.core.freshness import FRESH, UNKNOWN
from cockpit.core.readmodel import PARIS
from cockpit.health import collectors
from cockpit.health.engine import (
    FACTORY_STALLED_AFTER_SECONDS,
    SUPERVISOR_UNREACHABLE_AFTER_SECONDS,
    compute_health,
)
from cockpit.projects import anomalies as project_anomalies
from cockpit.projects.depots import apply_to_projects
from cockpit.projects.descriptors import load_descriptors
from cockpit.projects.source import from_value as projects_from_value
from cockpit.projects.source import project_page_data
from cockpit.requests.assemble import assemble_from_snapshot
from cockpit.requests.defects import DefectCounter
from cockpit.requests.journal import entries_from_value as journal_entries_from_value
from cockpit.requests.sources.readability import ILLISIBLE_THRESHOLD_SECONDS
from cockpit.runs.derive import runs_from_beads
from cockpit.ui.analyses.page import CSS as ANALYSES_CSS, render_analyses
from cockpit.ui.base.page import render_document, render_fresh, render_home_zones
from cockpit.ui.health.page import render_health_zone, render_status_line
from cockpit.ui.access.page import render_access_zone
from cockpit.ui.factory.page import CSS as FACTORY_PAGE_CSS, read_machine, render_factory_page
from cockpit.ui.home.overview import CSS as OVERVIEW_CSS
from cockpit.ui.home.overview import overview_view, render_overview
from cockpit.ui.panorama.shell import CSS as PANORAMA_CSS
from cockpit.ui.panorama.shell import HOME, NAVIGATION, render_not_folded, render_shell
from cockpit.ui.stop.render import render_stop_section
from cockpit.ui.journal.panorama import CSS as JOURNAL_PANORAMA_CSS, journal_items, render_journal_panorama
from cockpit.ui.journal.render import CSS as JOURNAL_CSS
from cockpit.ui.journal.render import render_journal_unknown
from cockpit.ui.notify.render import render_envois_section
from cockpit.ui.runs.page import CSS as RUNS_PAGE_CSS, render_run_page, render_runs_page
from cockpit.ui.projects.page import (
    render_historique_section,
    render_projects_section,
    render_projects_unknown,
)
from cockpit.ui.projects.panorama import CSS as PROJECTS_PANORAMA_CSS, render_projects_list
from cockpit.ui.projects.fold import CSS as PROJECT_FOLD_CSS, project_view, render_project_fold
from cockpit.ui.projects.project_page import render_project_page, render_project_unknown
from cockpit.ui.projects.tokens import CSS as PROJECT_PAGE_CSS
from cockpit.ui.rituals.page import CSS as RITUALS_CSS, read_rituals, render_rituals

ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
# The destinations of Panorama whose Prototype Fold is not done yet: their
# address answers, in the shell, that they are not served here yet.
NOT_FOLDED = {
    href: (key, label) for key, label, href in NAVIGATION if key not in (HOME, "projets", "journal", "runs", "usine", "rituels", "analyses")
}
NOT_FOLDED.update({"/runs/job": ("runs", "Runs")})



# Actions that write nothing on a bead (a prompt to copy, a test push): no
# re-read after them.
# What a gesture that failed in an unforeseen way answers: nothing is said
# done, and the request is to be read again before anything else.
UNEXPECTED_ACTION_ERROR = ("Le cockpit n’a pas pu faire ce geste à cause d’une erreur interne. Rien n’est confirmé : "
                           "relis la demande avant de réessayer.")
ACTIONS_WITHOUT_WRITE = frozenset({"continuer", "pas_bon_vers_agent", "notifier_test"})
# What "Ce qui t'attend", the projects and the journal are built from.
SOURCES_REREAD_AFTER_ACTION = frozenset({"beads", "projets", "journal"})
REREAD_AFTER_ACTION_SECONDS = 8.0


# How long GET / waits for the first reading of the projects, once the
# tracker is read (A1): the first page after a start shows them.
FIRST_READING_WAIT_SECONDS = 5

class CockpitRequestHandler(BaseHTTPRequestHandler):
    server_version = "cockpit/1"

    def log_message(self, fmt, *args):  # quiet by default; tests read the body
        pass

    def do_GET(self):
        read_model = self.server.read_model
        # A page is the path of its address: a query (« /runs? », which a
        # button of the navigation sends) names the same page.
        path = urllib.parse.urlsplit(self.path).path
        if path == "/api/status":
            self._send_json(read_model.snapshot())
            return
        if path == "/api/requests":
            self._send_json(self._requests_payload(read_model.snapshot(), read_model.now()))
            return
        if path == "/api/notifications":
            notify = self.server.notify
            self._send_json(
                {
                    "configured": bool(notify and notify.configured()),
                    "entries": notify.journal_entries() if notify else [],
                    "undelivered": sorted(self._undelivered()),
                }
            )
            return
        if path == "/api/journal":
            self._send_json(self._journal_payload(read_model.snapshot()))
            return
        if path == "/journal":
            self._send_journal_page(read_model)
            return
        if path == "/api/projects":
            self._send_json(self._projects_payload(read_model.snapshot()))
            return
        if path == "/api/health":
            self._send_json(self._compute_health(read_model))
            return
        if path.startswith("/api/actions/"):
            # T13, af-cx20q9 AC1: an action in GET is refused the same
            # way as any other guard failure, not a bare 404 — the guard
            # itself rejects on method before anything else is checked.
            guard_result = self.server.action_guard.check("GET", self.headers)
            self._send_json({"error": guard_result.reason}, status=403)
            return
        if path == "/projets":
            self._send_projects_page(read_model)
            return
        if path.startswith("/projet/"):
            self._send_project_page(read_model)
            return
        if path == "/analyses":
            self._send_analyses_page(read_model)
            return
        if path == "/usine":
            self._send_factory_page(read_model)
            return
        if path == "/rituels":
            rituals = read_rituals(self.server.rituals_file)
            self._send_page(read_model, "rituels", lambda anchors: render_rituals(rituals, anchors),
                            extra_css=RITUALS_CSS)
            return
        if path == "/runs":
            self._send_runs_page(read_model)
            return
        if path == "/runs/run":
            self._send_run_page(read_model)
            return
        if path == "/":
            self._send_home(read_model)
            return
        if path in NOT_FOLDED:
            key, label = NOT_FOLDED[path]
            self._send_page(read_model, key, render_not_folded(label))
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        """Operator Actions (T13, af-cx20q9; spec af-oohx2x §"Actions
        opérateur"). Every write goes through the access guard first —
        refused, nothing downstream (Beads included) is ever touched."""
        if self.path == "/api/health/recheck":
            for poller in getattr(self.server, "pollers", ()):
                poll_now = getattr(poller, "poll_now", None)
                if poll_now is not None:
                    poll_now()
            # Back to the page the button was on: the home screen, or a
            # project's page.
            referer_path = urllib.parse.urlsplit(self.headers.get("Referer") or "").path
            location = "/"
            if referer_path.startswith("/projet/") or referer_path in ("/projets", "/journal"):
                location = urllib.parse.quote(urllib.parse.unquote(referer_path), safe="/-_.~")
            self.send_response(303)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if not self.path.startswith("/api/actions/"):
            self.send_response(404)
            self.end_headers()
            return
        action = self.path[len("/api/actions/"):]
        guard_result = self.server.action_guard.check("POST", self.headers)
        if not guard_result.allowed:
            self._send_json({"error": guard_result.reason}, status=403)
            return
        handler = self.server.action_handlers.get(action)
        if handler is None:
            self._send_json({"error": "unknown_action"}, status=404)
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except ValueError:
            self._send_json({"error": "bad_json"}, status=400)
            return
        writes = action not in ACTIONS_WITHOUT_WRITE
        target = (payload.get("bead_id") or payload.get("source_key")) if isinstance(payload, dict) else None
        if writes and target:
            # After an uncertain outcome, not again before the source was
            # read again, nor once it shows the gesture done (af-fksj2c).
            refusal = self._uncertain_refusal(target)
            if refusal:
                self._send_json({"error": refusal, "incertain": True}, status=409)
                return
        try:
            result = handler(payload)
        except (ActionUncertain, subprocess.TimeoutExpired) as exc:
            # The command expired: it may have done its work. Said as it
            # is, and the source read again at once.
            if isinstance(exc, subprocess.TimeoutExpired):
                exc = expired(exc.timeout)
            self.server.uncertain.record(target, self.server.read_model.now())
            self._send_json({"error": str(exc), "incertain": True, "rafraichi": self._reread_after_action()},
                            status=504)
            return
        except ActionError as exc:
            self._send_json({"error": str(exc)}, status=400)
            return
        except Exception:
            logging.getLogger(__name__).exception("action %s failed", action)
            self._send_json({"error": UNEXPECTED_ACTION_ERROR}, status=500)
            return
        if writes and isinstance(result, dict):
            result["rafraichi"] = self._reread_after_action()
        self._send_json(result)

    def _uncertain_refusal(self, target):
        read_model = self.server.read_model
        snapshot = read_model.snapshot()
        requests, beads_row, _ = self._assemble_requests(snapshot, read_model.now())
        read_at = beads_row["read_at"] if beads_row else None
        return self.server.uncertain.refusal(target, read_at, {request.id for request in requests})

    def _first_reading(self, read_model, knowledge=False):
        """The snapshot, once the projects had their first reading if the
        tracker had its own -- and, with ``knowledge``, once the projects
        and their repositories were read or failed, so that the page of a
        project tells a reading under way from one that failed (E) --
        waiting at most
        :data:`FIRST_READING_WAIT_SECONDS`: a page served the instant the
        cockpit started would show no project, and no result, of a source
        simply not read yet (A1)."""
        deadline = time.monotonic() + FIRST_READING_WAIT_SECONDS
        while True:
            snapshot = read_model.snapshot()
            beads, projets, depots = snapshot.get("beads"), snapshot.get("projets"), snapshot.get("depots")
            pending = (beads is not None and beads["read_at"] is not None and projets is not None
                       and projets["read_at"] is None and projets.get("failed_at") is None)
            pending = pending or knowledge and any(
                row is not None and row["read_at"] is None and row.get("failed_at") is None for row in (projets, depots))
            if not pending or time.monotonic() >= deadline:
                return snapshot
            time.sleep(0.1)

    def _send_home(self, read_model):
        """GET /: the destination « Vue d’ensemble » of Panorama (T02,
        af-0gonc9), with the zones of the cockpit no destination of
        Panorama holds yet folded under it."""
        snapshot = self._first_reading(read_model)
        now = read_model.now()
        requests, _, _ = self._assemble_requests(snapshot, now)
        health = self._compute_health(read_model)
        # « Ce qui t’attend » is « Pour moi » of the overview itself (B,
        # af-4uzgzm): the zones folded under it no longer hold it.
        zones_html = render_home_zones(
            read_model.headline(),
            read_model.stale_or_unknown(),
            extra_sections_html=(
                self._render_projects_zone(snapshot)
                + self._render_stop_zone(snapshot)
                + render_access_zone(self.server.benjamin_login, snapshot.get("tailscale"), now)
                + render_health_zone(health, checked_at=_latest_read_at(snapshot, ("beads", "git")))
            ),
            status_html=render_status_line(snapshot.get("gc"), health),
        )
        driver = getattr(self.server, "stop_driver", None)
        view = overview_view(snapshot, requests, now=now, undelivered=self._undelivered(),
                             stop_trial_passed=bool(driver is not None and driver.essai_reussi()))
        # T13, af-cx20q9: the SameSite=Strict cookie an action POST must
        # echo back -- a cross-site POST never carries it, so its presence
        # alone proves this request came from a page the cockpit itself
        # served (cockpit.access.guard.ActionGuard).
        self._send_page(read_model, HOME, lambda anchors: render_overview(view, anchors, zones_html),
                        extra_css=OVERVIEW_CSS,
                        headers={"Set-Cookie": session_cookie_header(self.server.session_token)},
                        snapshot=snapshot)

    def _send_page(self, read_model, destination, main, extra_css="", status=200, headers=None, snapshot=None):
        """One page of Panorama: the navigation B with ``destination`` open,
        how many requests wait and the state of the factory, ``main`` beside
        it (its HTML, or a function that draws it with the anchors of the
        page, numbered after the shell's) -- read from ``snapshot`` when the
        page was drawn from one, so the page says one count."""
        snapshot = snapshot or read_model.snapshot()
        requests, _, beads_known = self._assemble_requests(snapshot, read_model.now())
        body = render_document(
            render_shell(destination, main, waiting=len(requests) if beads_known else None,
                         live=_live_line(snapshot.get("gc"))),
            extra_css=PANORAMA_CSS + extra_css,
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _reread_after_action(self):
        """An action just wrote on a bead; the page reads the read model,
        which would only see it at the next poll (20 s for Beads, 30 s for
        the projects) -- until then the request stayed listed, unchanged
        and clickable again (2026-10-07: a chantier accepted twice). Read
        the bead-backed sources again now, before answering, so the page
        the browser reloads on this answer shows the request gone or in
        its new state. True only if every one of them was read in time;
        the browser then reloads, otherwise it keeps the request marked
        as handled until the next regular read."""
        pollers = [
            poller for poller in getattr(self.server, "pollers", ())
            if getattr(poller, "source", None) in SOURCES_REREAD_AFTER_ACTION
        ]
        if not pollers:
            return False
        results = {}

        def reread(poller):
            results[poller.source] = bool(poller.poll_now())

        threads = [threading.Thread(target=reread, args=(poller,), daemon=True) for poller in pollers]
        for thread in threads:
            thread.start()
        deadline = time.monotonic() + REREAD_AFTER_ACTION_SECONDS
        for thread in threads:
            thread.join(timeout=max(0.0, deadline - time.monotonic()))
        return len(results) == len(pollers) and all(results.values())

    def _assemble_requests(self, snapshot, now):
        """"Ce qui t'attend" (spec §"Demandes opérateur"): every kind of
        request, built only from what the read model already holds -- no
        direct read of any source here."""
        return assemble_from_snapshot(
            snapshot, now, self.server.defect_counter, self.server.illisible_after_seconds,
            extra_requests=self.server.extra_requests(snapshot, now),
        )

    def _undelivered(self):
        """Ids whose push could not be delivered yet (spec .59)."""
        notify = self.server.notify
        return notify.undelivered() if notify is not None else set()

    def _requests_payload(self, snapshot, now):
        """JSON twin of « Ce qui t’attend » (T12, af-is5e97):
        lets a test assert on structured fields and the producer-defect
        count without scraping the rendered HTML. ``state`` is "unknown"
        whenever Beads is: the list is then not the whole list."""
        requests, beads_row, beads_known = self._assemble_requests(snapshot, now)
        payload = {
            "state": "unknown" if not beads_known else ("filled" if requests else "empty"),
            "requests": [
                {
                    "id": r.id,
                    "type": r.type,
                    "niveau": r.niveau,
                    "quoi": r.quoi,
                    "pourquoi": r.pourquoi,
                    "que_faire": r.que_faire,
                    "projet": r.projet,
                    "depuis_quand": r.depuis_quand,
                    "verifie_a": r.verifie_a,
                    "incomplete": r.incomplete,
                    "missing_fields": r.missing_fields,
                    "motifs": r.motifs,
                    "texte_origine": r.texte_origine,
                    "precisions": r.precisions,
                    "acquittee": r.acquittee,
                    "reportee": r.reportee,
                }
                for r in requests
            ],
            "defect_count": self.server.defect_counter.count,
        }
        if beads_known:
            payload["verified_at"] = beads_row["read_at"]
        return payload

    def _project_health_lines(self, snapshot):
        """Chantier anomalies (spec .47, .48): a closed chantier with a
        ticket not merged; a roadmap step marked done with a chantier still
        open, or a chantier aiming at a step still to do. Only from values
        that were read: an unknown source raises no anomaly."""
        projets = snapshot.get("projets")
        if projets is None or projets["value"] is None or projets["freshness"] == UNKNOWN:
            return []
        projects, sans_projet = projects_from_value(projets["value"])
        chantiers = [c for p in projects for c in p.chantiers] + sans_projet
        depots = snapshot.get("depots")
        steps = {}
        if depots is not None and depots["value"] is not None and depots["freshness"] != UNKNOWN:
            steps = depots["value"].get("steps") or {}
        return project_anomalies.health_lines(
            projets["value"].get("anomalies") or [],
            project_anomalies.roadmap_incoherences(chantiers, steps),
        )

    def _render_stop_zone(self, snapshot):
        """« Arrêt propre de l'usine »: the driver's state and the work a
        stop would wait for (spec .81, .82). No stop control is rendered:
        nothing in the cockpit can stop the factory until Benjamin's real
        trial (spec .91)."""
        driver = self.server.stop_driver
        if driver is None:
            return ""
        row = snapshot.get("sessions")
        known = row is not None and row["value"] is not None and row["freshness"] != UNKNOWN
        titles = {
            bead.get("id"): bead.get("title")
            for bead in ((snapshot.get("beads") or {}).get("value") or [])
            if isinstance(bead, dict)
        }
        work = {
            "known": known,
            "sessions": [
                {"titre": titles.get(s.get("bead_id")), "last_event_at": s.get("last_event_at")}
                for s in (row["value"]["sessions"] if known else [])
            ],
        }
        gc_row = snapshot.get("gc") or {}
        gc_value = gc_row.get("value")
        if not gc_value or gc_row.get("freshness") == UNKNOWN:
            factory = ("info", "État de l'usine inconnu — le superviseur ne répond pas")
        elif gc_value.get("suspended"):
            factory = ("normal", "Suspendue, sans arrêt demandé depuis le cockpit")
        else:
            factory = ("ok", "En marche")
        return render_stop_section(driver, enabled=False, work=work, factory=factory)

    def _render_projects_zone(self, snapshot):
        """"Projets", from the read model's own "projets" value -- absent
        when the process reads no Beads at all, unknown (never an empty
        list) when its read never succeeded or is failing."""
        row = snapshot.get("projets")
        if row is None:
            return ""
        if row["value"] is None or row["freshness"] == UNKNOWN:
            return render_projects_unknown(row["read_at"])
        projects, sans_projet = projects_from_value(row["value"])
        apply_to_projects(projects, snapshot.get("depots"))
        return render_projects_section(
            projects,
            sans_projet,
            stale_since=None if row["freshness"] == FRESH else row["read_at"],
        )

    def _send_projects_page(self, read_model):
        """GET /projets: a card per declared project (Panorama), its open
        chantiers, its runs merged in 7 days and in progress."""
        snapshot = read_model.snapshot()
        row = snapshot.get("projets")
        if row is None or row["value"] is None or row["freshness"] == UNKNOWN:
            inner = '<div class="pn-head"><h1>Projets</h1></div>' + render_projects_unknown(row["read_at"] if row else None)
        else:
            projects, _ = projects_from_value(row["value"])
            runs, _, checked = self._runs(read_model)
            inner = render_projects_list(projects, runs, read_model.now(), checked=checked)
        self._send_page(read_model, "projets", inner, extra_css=PROJECT_PAGE_CSS + PROJECTS_PANORAMA_CSS,
                        snapshot=snapshot)

    def _send_project_page(self, read_model):
        """GET /projet/<id> (spec .49; E, af-8rbceu): the Prototype Fold of
        the reference « Projet, release et historique » -- the release plan
        and the roadmap of the project read in its knowledge repository,
        then its chantiers by stage, its travail hors chantier and its
        historique. A project declared whose chantiers are not read yet, or
        no longer, is drawn with what is known and says so. An id no
        descriptor declares is a 404 that says so."""
        project_id = urllib.parse.unquote(self.path.split("?", 1)[0][len("/projet/"):])
        snapshot = self._first_reading(read_model, knowledge=True)
        fresh_html = render_fresh(read_model.headline(), not read_model.stale_or_unknown())
        row = snapshot.get("projets")
        descriptor = next((d for d in load_descriptors(self.server.descriptors_dir) if d["project_id"] == project_id),
                          None) if self.server.descriptors_dir else None
        runs, _, _ = self._runs(read_model)
        now = read_model.now()
        status = 200
        if row is None or row["value"] is None or row["freshness"] == UNKNOWN:
            if descriptor is None:
                inner = render_project_unknown(fresh_html) + render_projects_unknown(row["read_at"] if row else None)
            else:
                state = "failed" if row is not None and row.get("failed_at") is not None else "loading"
                below = '<div class="cockpit-pp-fresh">%s</div>' % fresh_html
                if state == "failed":
                    below += render_projects_unknown(row["read_at"])
                inner = render_project_fold(project_view(descriptor, None, state, snapshot.get("depots"), {}, runs, now,
                                                         [], below))
        else:
            data = project_page_data(row["value"], project_id)
            if data is None:
                status = 404
                inner = render_project_unknown(fresh_html, unknown_project=True)
            else:
                project, hors_chantier, historique = data
                apply_to_projects([project], snapshot.get("depots"))
                below = render_project_page(project, hors_chantier=hors_chantier,
                                            historique_html=render_historique_section([historique]),
                                            fresh_html=fresh_html, topbar=False)
                targets = (row["value"].get("roadmap_chantiers") or {}).get(project_id) or {}
                inner = render_project_fold(project_view(
                    descriptor or {"project_id": project.project_id, "display_name": project.display_name},
                    project, "read", snapshot.get("depots"), targets, runs, now, historique.chantiers, below))
        self._send_page(read_model, "projets", inner,
                        extra_css=PROJECT_PAGE_CSS + PROJECTS_PANORAMA_CSS + RUNS_PAGE_CSS + PROJECT_FOLD_CSS,
                        status=status, snapshot=snapshot)

    def _runs(self, read_model):
        """The runs the cockpit reads (cockpit.runs), most recent first:
        (runs or None while unread, read failed, HH:MM of the reading)."""
        row = read_model.snapshot().get("runs")
        if row is None or row["value"] is None:
            return None, bool(row and row.get("failed_at") is not None), None
        checked = datetime.fromtimestamp(row["read_at"], tz=PARIS).strftime("%H:%M") if row["read_at"] else None
        return runs_from_beads(row["value"], read_model.now()), False, checked

    def _send_analyses_page(self, read_model):
        """GET /analyses?vue=&periode=: the numbers of the runs, by day."""
        runs, _, checked = self._runs(read_model)
        row = read_model.snapshot().get("journal")
        entries = (journal_entries_from_value(row["value"])
                   if row and row["value"] is not None and row["freshness"] != UNKNOWN else [])
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        main = render_analyses(runs or [], journal_items(entries, []), read_model.now(),
                               (query.get("vue") or ["resultats"])[0], (query.get("periode") or ["7"])[0], checked=checked)
        self._send_page(read_model, "analyses", main, extra_css=ANALYSES_CSS)

    def _send_factory_page(self, read_model):
        """GET /usine: the machine, the sources, the agents seen at work,
        then the health and the zones that change the factory."""
        snapshot = read_model.snapshot()
        now = read_model.now()
        runs, _, _ = self._runs(read_model)
        health = self._compute_health(read_model)
        notify = self.server.notify
        actions_html = self._render_stop_zone(snapshot) + render_access_zone(
            self.server.benjamin_login, snapshot.get("tailscale"), now)
        main = render_factory_page(
            read_machine(), snapshot, runs, bool(notify and notify.configured()),
            render_health_zone(health, checked_at=_latest_read_at(snapshot, ("beads", "git"))), actions_html, now)
        self._send_page(read_model, "usine", main, extra_css=FACTORY_PAGE_CSS,
                        headers={"Set-Cookie": session_cookie_header(self.server.session_token)}, snapshot=snapshot)

    def _send_runs_page(self, read_model):
        """GET /runs: the runs, filtered by ?filtre=tous|en-cours|termines."""
        runs, failed, checked = self._runs(read_model)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        filtre = (query.get("filtre") or ["tous"])[0]
        self._send_page(read_model, "runs", render_runs_page(runs, filtre, checked=checked, error=failed),
                        extra_css=RUNS_PAGE_CSS)

    def _send_run_page(self, read_model):
        """GET /runs/run?id=<bead>: one run, its frise and its events."""
        runs, _, _ = self._runs(read_model)
        wanted = (urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("id") or [""])[0]
        run = next((r for r in runs or [] if r["id"] == wanted), None)
        self._send_page(read_model, "runs", render_run_page(run), extra_css=RUNS_PAGE_CSS,
                        status=200 if run else 404)

    def _send_journal_page(self, read_model):
        """GET /journal (spec .18): what changed, day by day -- the requests
        answered or cleared, re-read from the traces on the beads (the
        cockpit keeps no copy of its own), and the deliveries merged or
        stopped; filtered by ?filtre=."""
        row = read_model.snapshot().get("journal")
        runs, _, _ = self._runs(read_model)
        unknown_html, checked = "", None
        if row is None or row["value"] is None or row["freshness"] == UNKNOWN:
            items = journal_items([], runs)
            unknown_html = render_journal_unknown(row["read_at"] if row else None)
        else:
            items = journal_items(journal_entries_from_value(row["value"]), runs)
            checked = datetime.fromtimestamp(row["read_at"], tz=PARIS).strftime("%H:%M")
        notify = self.server.notify
        envois = render_envois_section(notify.journal_entries(), notify.configured()) if notify is not None else ""
        filtre = (urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("filtre") or ["utiles"])[0]
        self._send_page(read_model, "journal",
                        render_journal_panorama(items, filtre, read_model.now(), checked=checked, envois_html=envois,
                                                unknown_html=unknown_html),
                        extra_css=PROJECT_PAGE_CSS + JOURNAL_CSS + JOURNAL_PANORAMA_CSS)

    def _journal_payload(self, snapshot):
        """JSON twin of the journal page, for tests."""
        row = snapshot.get("journal")
        if row is None or row["value"] is None or row["freshness"] == UNKNOWN:
            return {"state": "unknown", "entries": []}
        return {"state": "filled", "verified_at": row["read_at"], "entries": row["value"]["entries"]}

    def _projects_payload(self, snapshot):
        """JSON twin of :meth:`_render_projects_zone`, for tests."""
        row = snapshot.get("projets")
        if row is None or row["value"] is None or row["freshness"] == UNKNOWN:
            return {"state": "unknown", "projects": [], "sans_projet": []}
        return {
            "state": "filled",
            "freshness": row["freshness"],
            "verified_at": row["read_at"],
            "projects": row["value"]["projects"],
            "sans_projet": row["value"]["sans_projet"],
        }

    def _compute_health(self, read_model):
        now = read_model.now()
        snapshot = read_model.snapshot()
        beads = (snapshot.get("beads") or {}).get("value") or []
        gc_row = snapshot.get("gc") or {}
        gc_value = gc_row.get("value") or {}
        return compute_health(
            now,
            commits_behind=(snapshot.get("git") or {}).get("value"),
            supervisor_unreachable_since=gc_row.get("read_at"),
            supervisor_partial_errors=gc_value.get("partial_errors"),
            last_progress_at=gc_value.get("last_progress_at"),
            delivery_ready=bool(gc_value.get("delivery_ready")),
            mayor_first_since=collectors.mayor_first_since_list(beads),
            loops=collectors.loop_items(beads),
            order_failures=collectors.order_failure_items(beads),
            red_ci=collectors.red_ci_items(beads),
            maintenance_proposals=collectors.maintenance_proposal_items(beads),
            proposals_sans_champs=collectors.proposal_sans_champs_items(beads),
            extra_lines=self._project_health_lines(snapshot)
            + [
                line
                for part in (self.server.notify, self.server.heartbeat)
                if part is not None
                for line in part.health_lines()
            ],
            supervisor_unreachable_after_seconds=self.server.supervisor_unreachable_after_seconds,
            factory_stalled_after_seconds=self.server.factory_stalled_after_seconds,
        )

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _live_line(gc_row):
    """The state of the factory under the brand: running and how many
    agents, suspended, or unknown when the supervisor's reading is not
    current."""
    value = (gc_row or {}).get("value")
    if not value or gc_row.get("freshness") != FRESH:
        return "● État actuel inconnu"
    if value.get("suspended"):
        return "● Suspendue"
    agents = int(value.get("agents_running") or 0)
    return "● En marche · %d agent%s" % (agents, "s" if agents > 1 else "")


def _latest_read_at(snapshot, names):
    read_ats = [snapshot[name]["read_at"] for name in names if snapshot.get(name) and snapshot[name]["read_at"] is not None]
    return max(read_ats) if read_ats else None


def make_server(
    read_model,
    host="127.0.0.1",
    port=0,
    action_guard=None,
    action_handlers=None,
    session_token="",
    pollers=None,
    supervisor_unreachable_after_seconds=None,
    factory_stalled_after_seconds=None,
    illisible_after_seconds=None,
):
    if host not in ALLOWED_HOSTS:
        raise ValueError(
            "cockpit refuses to listen on %r — only 127.0.0.1/localhost "
            "are allowed (spec .9)" % (host,)
        )
    # ThreadingHTTPServer resolves "localhost" itself; pin the actual bind
    # address so a DNS/hosts-file trick can't widen it past loopback.
    bind_host = "127.0.0.1"
    server = ThreadingHTTPServer((bind_host, port), CockpitRequestHandler)
    sockname = server.socket.getsockname()
    if sockname[0] not in ("127.0.0.1",):
        server.server_close()
        raise ValueError("cockpit bound to %r, not 127.0.0.1 — refusing" % (sockname[0],))
    server.read_model = read_model
    server.uncertain = UncertainOutcomes()
    server.defect_counter = DefectCounter()
    # T13, af-cx20q9: no guard supplied (a caller that only wants GET /,
    # e.g. an older test) means every action is refused rather than left
    # unchecked -- fail closed, never fail open on a write path.
    server.action_guard = action_guard or _AlwaysRefuseGuard()
    server.action_handlers = action_handlers or {}
    server.session_token = session_token
    server.pollers = pollers or ()
    server.supervisor_unreachable_after_seconds = (
        SUPERVISOR_UNREACHABLE_AFTER_SECONDS
        if supervisor_unreachable_after_seconds is None
        else supervisor_unreachable_after_seconds
    )
    server.factory_stalled_after_seconds = (
        FACTORY_STALLED_AFTER_SECONDS
        if factory_stalled_after_seconds is None
        else factory_stalled_after_seconds
    )
    # Set by cockpit.core.process once the services exist; a server built
    # without them (a narrow test) simply has no notifications to show.
    server.notify = None
    server.heartbeat = None
    server.stop_driver = None
    server.benjamin_login = ""
    # The rituals file of the Factory (« Rituels »): unset, nothing read.
    server.rituals_file = None
    # Where the projects are declared (cockpit.projects.descriptors): the
    # page of a project names it from there while its chantiers are unread.
    server.descriptors_dir = None
    server.extra_requests = lambda snapshot, now: []
    server.illisible_after_seconds = (
        ILLISIBLE_THRESHOLD_SECONDS if illisible_after_seconds is None else illisible_after_seconds
    )
    return server


class _AlwaysRefuseGuard:
    def check(self, method, headers):
        from cockpit.access.guard import GuardResult, REFUSED_SESSION

        return GuardResult(False, REFUSED_SESSION)
