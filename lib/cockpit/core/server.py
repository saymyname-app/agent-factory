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
from pathlib import Path
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cockpit.access.guard import session_cookie_header
from cockpit.actions.registry import DOOR_TIMEOUT_SECONDS, ActionError, ActionUncertain, expired
from cockpit.actions.uncertain import UncertainOutcomes
from cockpit.core.freshness import FRESH, STALE, UNKNOWN
from cockpit.core.readmodel import PARIS
from cockpit.factory.checks import VALIDITY_SECONDS as CHECK_VALIDITY_SECONDS
from cockpit.factory.checks import SectionChecks
from cockpit.factory.configuration import ROOT as FACTORY_ROOT
from cockpit.factory.configuration import read_configuration
from cockpit.factory import cleanup, settings
from cockpit.text.validate import operator_language
from cockpit.health import collectors
from cockpit.health.engine import (
    FACTORY_STALLED_AFTER_SECONDS,
    SUPERVISOR_UNREACHABLE_AFTER_SECONDS,
    compute_health,
)
from cockpit.projects import anomalies as project_anomalies
from cockpit.projects.decisions import chantier_decisions
from cockpit.projects.depots import apply_to_projects
from cockpit.projects.descriptors import load_descriptors
from cockpit.projects.source import from_value as projects_from_value
from cockpit.projects.source import project_page_data
from cockpit.requests.assemble import assemble_from_snapshot
from cockpit.requests.defects import DefectCounter
from cockpit.requests.journal import entries_from_value as journal_entries_from_value
from cockpit.requests.journal import sources_from_value as journal_sources_from_value
from cockpit.requests.sources.readability import ILLISIBLE_THRESHOLD_SECONDS
from cockpit.runs.derive import runs_from_beads
from cockpit.runs.workflows import waiting_on, workflow_runs
from cockpit.ui.analyses.page import CSS as ANALYSES_CSS, render_analyses
from cockpit.ui.base.page import render_document, render_fresh, render_home_zones
from cockpit.ui.health.page import render_health_zone, render_status_line
from cockpit.ui.access.page import PROCEDURE_PATH, render_access_zone
from cockpit.ui.access.procedure import CSS as PROCEDURE_CSS, render_procedure
from cockpit.stop.driver import RESUMABLE_STATES, STOPPABLE_STATES
from cockpit.stop.gc_city import StopUncertain
from cockpit.ui.factory.page import CSS as FACTORY_PAGE_CSS, read_machine, read_stop_procedure, render_factory_page
from cockpit.ui.home.overview import CSS as OVERVIEW_CSS
from cockpit.ui.home.overview import overview_view, render_overview
from cockpit.ui.panorama.shell import CSS as PANORAMA_CSS
from cockpit.ui.panorama.shell import HOME, NAVIGATION, render_not_folded, render_shell
from cockpit.ui.stop.render import render_stop_section
from cockpit.ui.journal.panorama import CSS as JOURNAL_PANORAMA_CSS, journal_items, journal_view, render_journal_panorama
from cockpit.ui.journal.render import CSS as JOURNAL_CSS
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



# Actions that write nothing on a bead (a prompt to copy, a test push): no
# re-read after them.
# What a gesture that failed in an unforeseen way answers: nothing is said
# done, and the request is to be read again before anything else.
UNEXPECTED_ACTION_ERROR = ("Le cockpit n’a pas pu faire ce geste à cause d’une erreur interne. Rien n’est confirmé : "
                           "relis la demande avant de réessayer.")
# What a member of the tailnet who is not the operator reads (I, af-cp4fzd):
# nothing of the cockpit.
READER_REFUSED_TEXT = ("Accès refusé : ce cockpit est réservé à l’opérateur de l’usine. "
                       "Ton identité Tailscale n’y est pas autorisée.\n")
# The gestures of the page Usine (G2, af-f8nlhr), served by
# CockpitRequestHandler._usine_action, each through its door.
USINE_ACTIONS = frozenset({"regler", "preparer_reglage", "nettoyer"})
# The gestures of the clean stop (H, af-69qhlk), served by _stop_action.
STOP_ACTIONS = frozenset({"arreter", "forcer_arret", "redemarrer"})
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

    def _refuse_reader(self):
        """A member of the tailnet who is not the operator: nothing of the
        cockpit is read or served to them (I, af-cp4fzd). True when the
        request was refused."""
        if self.server.action_guard.check_reader(self.headers):
            return False
        body = READER_REFUSED_TEXT.encode("utf-8")
        self.send_response(403)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        return True

    def do_GET(self):
        if self._refuse_reader():
            return
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
        if path == PROCEDURE_PATH:
            self._send_page(read_model, "usine", render_procedure(self.server.procedure_settings()),
                            extra_css=PROCEDURE_CSS)
            return
        if path == "/rituels":
            rituals = read_rituals(self.server.rituals_file)
            self._send_page(read_model, "rituels", lambda anchors: render_rituals(rituals, anchors),
                            extra_css=RITUALS_CSS)
            return
        if path == "/runs":
            self._send_runs_page(read_model)
            return
        if path in ("/runs/run", "/runs/job"):
            self._send_run_page(read_model, job=path == "/runs/job")
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
        if self.path in ("/api/usine/reverifier", "/api/health/recheck"):
            guard_result = self.server.action_guard.check_page_post("POST", self.headers)
            if not guard_result.allowed:
                self._send_json({"error": guard_result.reason}, status=403)
                return
        if self.path == "/api/usine/reverifier":
            self._recheck_factory_section()
            return
        if self.path == "/api/health/recheck":
            for poller in getattr(self.server, "pollers", ()):
                poll_now = getattr(poller, "poll_now", None)
                if poll_now is not None:
                    poll_now()
            # Back to the page the button was on: the home screen, or a
            # project's page.
            referer_path = urllib.parse.urlsplit(self.headers.get("Referer") or "").path
            location = "/"
            if referer_path.startswith("/projet/") or referer_path in ("/projets", "/journal", "/usine"):
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
        if action in USINE_ACTIONS or action in STOP_ACTIONS:
            length = int(self.headers.get("Content-Length", "0") or "0")
            try:
                payload = json.loads((self.rfile.read(length) if length else b"{}").decode("utf-8") or "{}")
            except ValueError:
                payload = None
            if not isinstance(payload, dict):
                self._send_json({"error": "bad_json"}, status=400)
                return
            answer = self._stop_action if action in STOP_ACTIONS else self._usine_action
            status, body = answer(action, payload)
            self._send_json(body, status=status)
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
            # The command expired, or did its work and what follows it
            # failed: said as it is, and the source read again at once.
            if isinstance(exc, subprocess.TimeoutExpired):
                exc = expired(exc.timeout)
            self.server.uncertain.record(target, self.server.read_model.now())
            self._send_json({"error": str(exc), "incertain": True, "rafraichi": self._reread_after_action()},
                            status=exc.status)
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

    def _first_reading(self, read_model, knowledge=False, agents=False):
        """The snapshot, once the projects had their first reading if the
        tracker had its own -- and, with ``knowledge``, once the projects
        and their repositories were read or failed, so that the page of a
        project tells a reading under way from one that failed (E); with
        ``agents``, once the sessions were tried after the tracker was read
        (they are refused while it is not), so that a run names its agents
        on the first page (C1) --
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
            sessions = snapshot.get("sessions")
            pending = pending or agents and sessions is not None and sessions["read_at"] is None and (
                sessions.get("failed_at") is None or beads is None or beads["read_at"] is None
                or sessions["failed_at"] <= beads["read_at"])
            if not pending or time.monotonic() >= deadline:
                return snapshot
            time.sleep(0.1)

    def _send_home(self, read_model):
        """GET /: the destination « Vue d’ensemble » of Panorama (T02,
        af-0gonc9), with the zones of the cockpit no destination of
        Panorama holds yet folded under it."""
        snapshot = self._first_reading(read_model)
        now = read_model.now()
        requests, beads_row, _ = self._assemble_requests(snapshot, now)
        # A gesture whose outcome is uncertain is drawn unavailable for as
        # long as a POST on it would be refused (af-fksj2c).
        uncertain = self.server.uncertain.pending(beads_row["read_at"] if beads_row else None,
                                                  {request.id for request in requests})
        health = self._compute_health(read_model)
        # « Ce qui t’attend » is « Pour moi » of the overview itself (B,
        # af-4uzgzm): the zones folded under it no longer hold it.
        zones_html = render_home_zones(
            read_model.headline(),
            read_model.stale_or_unknown(),
            extra_sections_html=(
                self._render_projects_zone(snapshot)
                + self._render_stop_zone(snapshot)
                + render_access_zone(self.server.benjamin_login, snapshot.get("tailscale"), now,
                                   public_url=self.server.public_url)
                + render_health_zone(health, checked_at=_latest_read_at(snapshot, ("beads", "git")))
            ),
            status_html=render_status_line(snapshot.get("gc"), health),
        )
        driver = getattr(self.server, "stop_driver", None)
        view = overview_view(snapshot, requests, now=now, undelivered=self._undelivered(), uncertain=uncertain,
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

    def _chantier_decisions(self, snapshot, now):
        """The open decisions of each chantier
        (cockpit.projects.decisions), counted on the requests the home
        counts: ``{chantier id: count}``, or None while the tracker or the
        chantiers are not known -- an unknown count is never 0."""
        requests, _, beads_known = self._assemble_requests(snapshot, now)
        row = snapshot.get("projets")
        if not beads_known or row is None or row["value"] is None or row["freshness"] == UNKNOWN:
            return None
        projects, sans_projet = projects_from_value(row["value"])
        return chantier_decisions([c for p in projects for c in p.chantiers] + sans_projet, requests)

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
            inner = render_projects_list(projects, runs, read_model.now(),
                                         self._chantier_decisions(snapshot, read_model.now()), checked=checked)
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
                    project, "read", snapshot.get("depots"), targets, runs, now, historique.chantiers, below,
                    self._chantier_decisions(snapshot, now)))
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
        """GET /usine?role=: the machine, the connections and the roles,
        each as its section was last checked, the role ``role`` open (the
        author by default), then the health and the zones that change the
        factory."""
        # The sessions: what a stop would wait for, on the first page too.
        snapshot = self._first_reading(read_model, agents=True)
        now = read_model.now()
        checks = self.server.factory_checks
        health = self._compute_health(read_model)
        notify = self.server.notify
        actions_html = render_access_zone(
            self.server.benjamin_login, snapshot.get("tailscale"), now, public_url=self.server.public_url)
        agents = checks.get("agents")
        wanted = (urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("role") or [""])[0]
        keys = [role["key"] for role in agents["value"]["configuration"]["roles"]]
        setting, cleaning = self._usine_views(urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query), agents,
                                              wanted if wanted in keys else (keys[0] if keys else ""))
        main = render_factory_page({
            "setting": setting, "cleanup": cleaning, "stop": self._stop_view(snapshot),
            "machine": checks.get("machine"), "connections": checks.get("connexions"),
            "providers": checks.get("fournisseurs"), "agents": agents,
            "live": snapshot, "now": now, "notify_configured": bool(notify and notify.configured()),
            "selected": wanted if wanted in keys else (keys[0] if keys else ""),
            "health_html": render_health_zone(health, checked_at=_latest_read_at(snapshot, ("beads", "git"))),
            "actions_html": actions_html,
        })
        self._send_page(read_model, "usine", main, extra_css=FACTORY_PAGE_CSS,
                        headers={"Set-Cookie": session_cookie_header(self.server.session_token)}, snapshot=snapshot)

    def _stop_view(self, snapshot):
        """What the panel of the stop draws: the driver's view, the work a
        stop would wait for now, and what the address opens
        (``arret=confirmer|machine``). No driver: nothing to draw from."""
        driver = self.server.stop_driver
        if driver is None:
            return None
        row = snapshot.get("sessions")
        known = row is not None and row["value"] is not None and row["freshness"] != UNKNOWN
        titles = {bead.get("id"): bead.get("title") for bead in ((snapshot.get("beads") or {}).get("value") or [])
                  if isinstance(bead, dict)}
        gc_row = snapshot.get("gc") or {}
        gc_value = gc_row.get("value")
        factory = ("Départs autorisés", "En marche")
        if not gc_value or gc_row.get("freshness") == UNKNOWN:
            factory = ("État de l’usine inconnu", "inconnu — le superviseur ne répond pas")
        elif gc_value.get("suspended"):
            factory = ("Suspendue, sans arrêt demandé depuis le cockpit", "Suspendue")
        return {
            "view": driver.view(), "mode": (urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get("arret")
                                            or [""])[0],
            "blocked": self._stop_blocked(snapshot), "stoppable": driver.state() in STOPPABLE_STATES,
            "resumable": driver.state() in RESUMABLE_STATES, "essai": not driver.essai_reussi(), "factory": factory,
            "work": [{"title": titles.get(s.get("bead_id")) or "ticket dont le titre n’a pas été lu",
                      "template": s.get("template")} for s in (row["value"]["sessions"] if known else [])],
            "procedure": read_stop_procedure(self.server.stop_procedure_file),
        }

    def _setting_blocked(self, agents, role_key):
        """Why the setting of ``role_key`` may not be made now, or None: the
        configuration read is unreadable or stale, or the last setting of
        the role had an uncertain outcome the configuration was not read
        again since (that reading lifts it)."""
        configuration = agents["value"]["configuration"]
        if configuration["unreadable"]:
            return ("Réglage indisponible : la configuration est illisible (%s) ; revérifie-la une fois les "
                    "fichiers rétablis." % ", ".join(configuration["unreadable"]))
        if agents.get("stale"):
            return "Réglage indisponible : la configuration lue est périmée ; revérifie-la avant de régler."
        mark = self.server.setting_uncertain.get(role_key)
        if mark is not None:
            if agents["at"] > mark:
                self.server.setting_uncertain.pop(role_key, None)
            else:
                return ("Réglage indisponible : la dernière commande de réglage a une issue incertaine ; "
                        "revérifie la configuration avant de réessayer.")
        return None

    def _proposal_blocked(self, role_key):
        """Why a proposal for ``role_key`` may not be prepared now, or None.
        Its source is what waits for the operator, the tracker -- not the
        configuration. After an uncertain outcome, nothing goes before a
        read of the tracker the cockpit started after it ended
        (:meth:`_reread_proposals`): a read that ends later but began
        before may not hold what the door wrote. A proposal with the same
        words seen waiting was recorded, and is never prepared twice; one a
        read started after the outcome does not show lifts the mark."""
        server = self.server
        with server.proposal_lock:
            mark = server.proposal_uncertain.get(role_key)
        if mark is None:
            return None
        read_model = server.read_model
        requests, _, _ = self._assemble_requests(read_model.snapshot(), read_model.now())
        with server.proposal_lock:
            if any(request.quoi == mark["quoi"] for request in requests):
                mark["verdict"] = "recorded"
            verdict = mark["verdict"]
            if verdict == "absent":
                server.proposal_uncertain.pop(role_key, None)
                return None
        if verdict == "recorded":
            return ("Proposition déjà enregistrée : « %s » attend ta décision dans Pour moi. Rien n’a été envoyé "
                    "de nouveau." % mark["quoi"])
        self._reread_proposals(role_key)
        return ("Proposition indisponible : la dernière préparation a une issue incertaine ; le cockpit relit "
                "ce qui t’attend avant tout nouvel essai.")

    def _reread_proposals(self, role_key):
        """Reads the tracker again in the background, once at a time per
        role, and says from that read whether the proposal of the uncertain
        outcome of ``role_key`` waits (``recorded``) or not (``absent``).
        A read that failed, or that another read ended after, says nothing:
        the next gesture starts another."""
        server = self.server
        with server.proposal_lock:
            mark = server.proposal_uncertain.get(role_key)
            if mark is None or mark["rereading"]:
                return
            mark["rereading"] = True
        poller = next((p for p in getattr(server, "pollers", ()) if getattr(p, "source", None) == "beads"), None)

        def reread():
            started = server.read_model.now()
            verdict = None
            try:
                if poller is not None and poller.poll_now():
                    read_model = server.read_model
                    requests, beads_row, _ = self._assemble_requests(read_model.snapshot(), read_model.now())
                    if beads_row and beads_row["read_at"] is not None and beads_row["read_at"] >= started:
                        verdict = ("recorded" if any(r.quoi == mark["quoi"] for r in requests) else "absent")
            finally:
                with server.proposal_lock:
                    if verdict is not None and mark["verdict"] != "recorded":
                        mark["verdict"] = verdict
                    mark["rereading"] = False

        threading.Thread(target=reread, daemon=True).start()

    def _cleanup_blocked(self):
        """Why the cleaning may not be confirmed now, or None: no preview of
        its scope was read, the one read is stale, or the last cleaning had
        an uncertain outcome no preview was read since."""
        server = self.server
        previewed = server.cleanup_previewed_at
        if previewed is None:
            return ("Nettoyage indisponible : aucun aperçu du périmètre n’a été lu ; examine le périmètre avant de "
                    "le confirmer.")
        mark = server.cleanup_uncertain
        if mark is not None:
            if previewed <= mark:
                return ("Nettoyage indisponible : le dernier nettoyage a une issue incertaine ; examine de nouveau "
                        "le périmètre avant de confirmer.")
            server.cleanup_uncertain = None
        if server.read_model.now() - previewed > server.cleanup_validity_seconds:
            return ("Nettoyage indisponible : l’aperçu du périmètre est périmé ; examine-le de nouveau avant de "
                    "confirmer.")
        return None

    def _stop_blocked(self, snapshot):
        """Why a stop may not be asked now, or None."""
        driver = self.server.stop_driver
        if driver is None or driver.state() not in STOPPABLE_STATES:
            return "Une suspension est déjà en cours : suis-la ici."
        sessions, beads = snapshot.get("sessions"), snapshot.get("beads")
        if any(row is None or row["value"] is None or row["freshness"] != FRESH for row in (sessions, beads)):
            return "Suspension indisponible : travail en vol inconnu, la source ne répond pas. Revérifie les connexions."
        return None

    def _stop_action(self, action, payload):
        """POST /api/actions/arreter, forcer_arret, redemarrer (H,
        af-69qhlk): (status, body). What the moment does not allow is
        refused first, then a gesture without its confirmation; only then
        does the supervisor hear of it. No answer from it leaves the
        outcome to the next reading of the page."""
        driver = self.server.stop_driver
        blocked = None
        if action == "arreter":
            blocked = self._stop_blocked(self.server.read_model.snapshot())
        elif action == "forcer_arret" and (driver is None or not driver.force_offered()):
            blocked = "L’arrêt forcé n’est proposé qu’après 30 min sans progrès : rien n’a été envoyé."
        elif action == "redemarrer" and (driver is None or driver.state() not in RESUMABLE_STATES):
            blocked = "Rien à redémarrer : aucun arrêt n’est terminé."
        if blocked:
            return 409, {"error": blocked}
        if payload.get("confirm") is not True:
            return 400, {"error": "Confirmation requise : rien n’a été envoyé."}
        gesture = {"arreter": driver.request_stop, "forcer_arret": driver.force_stop,
                   "redemarrer": driver.resume}[action]
        try:
            gesture()
        except StopUncertain:
            self._poll_soon()
            return 504, {"error": "Le superviseur n’a pas répondu : l’issue est incertaine. Relis cette page avant "
                                  "de réessayer.", "incertain": True}
        except ValueError as exc:
            return 409, {"error": "Commande refusée : %s." % exc}
        self._poll_soon()
        return 200, {"ok": True}

    def _usine_action(self, action, payload):
        """POST /api/actions/regler, preparer_reglage, nettoyer (G2,
        af-f8nlhr): (status, body). Each goes through its door; a door
        that does not answer leaves an uncertain outcome, and the same
        gesture waits for a new reading of its source: the configuration
        for a setting, what waits for the operator for a proposal, the
        scope for a cleaning."""
        server = self.server
        if payload.get("confirm") is not True:
            return 400, {"error": "Confirmation requise : rien n’a été envoyé."}
        if action == "nettoyer":
            blocked = self._cleanup_blocked()
            if blocked:
                return 409, {"error": blocked, "incertain": server.cleanup_uncertain is not None}
            try:
                elements = cleanup.clean(server.factory_maintain_bin, payload.get("perimetre"), server.door_timeout)
            except cleanup.ScopeChanged as exc:
                server.cleanup_previewed_at = server.read_model.now()
                return 409, {"error": str(exc), "perimetre": exc.scope["candidates"]}
            except ActionUncertain as exc:
                server.cleanup_uncertain = server.read_model.now()
                return exc.status, {"error": str(exc), "incertain": True}
            except ActionError as exc:
                return 400, {"error": str(exc)}
            server.cleanup_result = {"at": datetime.fromtimestamp(server.read_model.now(), tz=PARIS)
                                     .strftime("%d/%m à %H:%M:%S"), "elements": elements}
            return 200, {"ok": True, "elements": elements}
        role_key = payload.get("role") or ""
        agents = server.factory_checks.get("agents")
        blocked = self._setting_blocked(agents, role_key) if action == "regler" else (
            self._configuration_blocked(agents) or self._proposal_blocked(role_key))
        if blocked:
            uncertain = server.setting_uncertain if action == "regler" else server.proposal_uncertain
            return 409, {"error": blocked, "incertain": role_key in uncertain}
        configuration = agents["value"]["configuration"]
        try:
            planned = settings.plan(configuration, role_key, payload.get("principal") or "",
                                    payload.get("effort") or "", payload.get("secours") or "")
            if action == "regler":
                read_back = settings.apply(server.provider_failover_bin, planned, server.door_timeout)
            else:
                if planned["supported"]:
                    raise ActionError("Ce changement se règle par sa porte : applique-le au lieu d’en faire une "
                                      "proposition.")
                quoi = settings.propose(server.proposal_door_bin, planned, operator_language(), server.door_timeout)
        except ActionUncertain as exc:
            if action == "regler":
                server.setting_uncertain[role_key] = server.read_model.now()
            else:
                with server.proposal_lock:
                    server.proposal_uncertain[role_key] = {"at": server.read_model.now(), "quoi": planned["quoi"],
                                                           "verdict": None, "rereading": False}
                self._reread_proposals(role_key)
            return exc.status, {"error": str(exc), "incertain": True}
        except ActionError as exc:
            return 400, {"error": str(exc)}
        if action == "regler":
            server.factory_checks.recheck("agents")
            provider = configuration["providers"].get(read_back["provider"]) or {}
            server.setting_outcomes[role_key] = (
                "Réglage appliqué et relu par la porte à %s : les prochaines sessions du rôle %s démarrent sur %s ; "
                "les sessions ouvertes gardent le leur." % (
                    datetime.fromtimestamp(server.read_model.now(), tz=PARIS).strftime("%H:%M:%S"),
                    planned["label"].lower(), provider.get("label") or read_back["provider"]))
            return 200, {"ok": True, "lu": read_back}
        server.setting_outcomes[("proposition", role_key)] = (
            "Proposition préparée : « %s ». Elle attend ta décision dans Pour moi ; rien n’a changé pour ce rôle."
            % quoi)
        self._poll_soon()
        return 200, {"ok": True, "quoi": quoi}

    def _configuration_blocked(self, agents):
        """Why nothing may be planned on the configuration read, or None:
        unreadable or stale."""
        configuration = agents["value"]["configuration"]
        if configuration["unreadable"] or agents.get("stale"):
            return self._setting_blocked(agents, None)
        return None

    def _poll_soon(self):
        """Reads the sources of the cockpit again, in the background: what
        waits for the operator shows a proposal just written."""
        for poller in getattr(self.server, "pollers", ()):
            poll_now = getattr(poller, "poll_now", None)
            if poll_now is not None:
                threading.Thread(target=poll_now, daemon=True).start()

    def _usine_views(self, query, agents, selected):
        """What the role panel and the cleaning panel of the page show,
        from the address: ``reglage=modifier|portee|fait|propose``
        (``principal=``, ``effort=``, ``secours=`` for the scope),
        ``nettoyage=apercu|fait``."""
        server = self.server
        mode = (query.get("reglage") or [""])[0]
        configuration = agents["value"]["configuration"]
        setting = {"mode": "role", "blocked": self._setting_blocked(agents, selected) if selected else None,
                   "outcome": server.setting_outcomes.get(selected)}
        try:
            if mode == "modifier":
                setting.update(mode="modifier", offered=settings.offered(configuration, selected))
            elif mode == "portee":
                planned = settings.plan(configuration, selected, *((query.get(name) or [""])[0]
                                                                   for name in ("principal", "effort", "secours")))
                blocked = self._setting_blocked(agents, selected) if planned["supported"] else (
                    self._configuration_blocked(agents) or self._proposal_blocked(selected))
                setting.update(mode="portee", plan=planned, blocked=blocked)
            elif mode == "propose":
                setting.update(mode="propose", outcome=server.setting_outcomes.get(("proposition", selected)))
        except ActionError as exc:
            setting.update(mode="role", outcome=str(exc))
        cleaning = {"result": server.cleanup_result, "blocked": None,
                    "validity_seconds": server.cleanup_validity_seconds}
        if (query.get("nettoyage") or [""])[0] == "apercu":
            cleaning["mode"] = "apercu"
            try:
                cleaning["preview"] = cleanup.preview(server.factory_maintain_bin, server.door_timeout)
                server.cleanup_previewed_at = server.read_model.now()
                cleaning["blocked"] = self._cleanup_blocked()
            except ActionError as exc:
                cleaning.update(preview=None, error=str(exc))
        return setting, cleaning

    def _recheck_factory_section(self):
        """POST /api/usine/reverifier (section=machine|connexions|fournisseurs|agents,
        role=): reads that section of the page Usine again -- the
        connections after every source was read again now -- and only that
        one, then back to the page with the same role open. It writes
        nothing."""
        length = int(self.headers.get("Content-Length", "0") or "0")
        form = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8") if length else "")
        section = (form.get("section") or [""])[0]
        role = (form.get("role") or [""])[0]
        if section not in ("machine", "connexions", "fournisseurs", "agents"):
            self.send_response(400)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if section == "connexions":
            for poller in getattr(self.server, "pollers", ()):
                poll_now = getattr(poller, "poll_now", None)
                if poll_now is not None:
                    poll_now()
        self.server.factory_checks.recheck(section)
        self.send_response(303)
        self.send_header("Location", "/usine" + ("?" + urllib.parse.urlencode({"role": role}) if role else ""))
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _workflow_runs(self, read_model, snapshot):
        """The runs of the destination Runs (cockpit.runs.workflows), one
        per complete workflow, most recent first: (runs or None while
        unread, read failed, HH:MM of the reading)."""
        row = snapshot.get("runs")
        if row is None or row["value"] is None:
            return None, bool(row and row.get("failed_at") is not None), None
        checked = datetime.fromtimestamp(row["read_at"], tz=PARIS).strftime("%H:%M") if row["read_at"] else None
        sessions = (snapshot.get("sessions") or {}).get("value") or {}
        trace = self.server.session_trace.read() if self.server.session_trace is not None else None
        runs = workflow_runs(row["value"], sessions.get("agents"), read_model.now(), trace)
        return waiting_on(runs, self._chantier_decisions(snapshot, read_model.now())), False, checked

    def _query(self):
        return urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)

    def _send_runs_page(self, read_model):
        """GET /runs: the runs, filtered by ?filtre=tous|en-cours|termines
        (by default, the filter the frozen state selects, else Tous)."""
        snapshot = self._first_reading(read_model, agents=True)
        runs, failed, checked = self._workflow_runs(read_model, snapshot)
        filtre = (self._query().get("filtre") or [self.server.runs_view.get("filter") or "tous"])[0]
        self._send_page(read_model, "runs",
                        render_runs_page(runs, filtre, checked=checked, error=failed, now=read_model.now()),
                        extra_css=RUNS_PAGE_CSS, snapshot=snapshot)

    def _send_run_page(self, read_model, job=False):
        """GET /runs/run?id=<run>: one run and its frise; GET
        /runs/job?run=<run>&job=<job>&event=<n>: the same, with the detail
        of a job under the frise and one of its events open. An address
        that names nothing opens what the frozen state selects. A reading
        of a source the run is drawn from no longer current is said, with
        when it was."""
        snapshot = self._first_reading(read_model, agents=True)
        runs, _, _ = self._workflow_runs(read_model, snapshot)
        query, view = self._query(), self.server.runs_view
        wanted = (query.get("run" if job else "id") or [view.get("run") or ""])[0]
        run = next((r for r in runs or [] if r["id"] == wanted), None)
        job_id = (query.get("job") or [view.get("job") or ""])[0] if job else None
        event = (query.get("event") or [str(view.get("event") or "")])[0] if job else ""
        # What the detail opens: what the address says, else -- an address
        # that names no job -- what the frozen state shows.
        named = "job" in query
        shown = {} if named else VIEW_DETAILS.get(view.get("detail") or "", {})
        opened = _listed(query, "ouvert", shown.get("open", ()))
        raw = _listed(query, "brut", shown.get("raw", ()))
        session = (query.get("session") or [""])[0] or None
        stale_at = _stale_at(snapshot, RUN_SOURCES)
        main = render_run_page(run, now=read_model.now(), stale_at=stale_at, job_id=job_id,
                               event=int(event) if event.isdigit() else None, session=session, opened=opened, raw=raw)
        self._send_page(read_model, "runs", main, extra_css=RUNS_PAGE_CSS, status=200 if run else 404,
                        snapshot=snapshot)

    def _send_journal_page(self, read_model):
        """GET /journal?vue=&categorie=&source=&q= (spec .18; F, af-njwz8v):
        the useful events day by day -- the requests answered or cleared,
        re-read from the traces on the beads (the cockpit keeps no copy of
        its own), the deliveries of the runs, the events held for the
        journal --, the technical logs, and the coverage of their sources."""
        snapshot = read_model.snapshot()
        row = snapshot.get("journal")
        runs, _, _ = self._runs(read_model)
        known = row is not None and row["value"] is not None and row["freshness"] != UNKNOWN
        projects = {}
        projets = snapshot.get("projets")
        if projets is not None and projets["value"] is not None:
            projects = {p.project_id: p.display_name for p in projects_from_value(projets["value"])[0]}
        view = journal_view(row, journal_entries_from_value(row["value"]) if known else [], runs, projects,
                            snapshot.get("gc"), journal_sources_from_value(row["value"]) if known else ())
        notify = self.server.notify
        envois = render_envois_section(notify.journal_entries(), notify.configured()) if notify is not None else ""
        query = {key: values[0] for key, values in urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).items()}
        self._send_page(read_model, "journal",
                        lambda anchors: render_journal_panorama(view, query, read_model.now(), anchors, envois_html=envois),
                        extra_css=PROJECT_PAGE_CSS + JOURNAL_CSS + JOURNAL_PANORAMA_CSS, snapshot=snapshot)

    def _journal_payload(self, snapshot):
        """JSON twin of the journal page, for tests."""
        row = snapshot.get("journal")
        if row is None or row["value"] is None or row["freshness"] == UNKNOWN:
            return {"state": "unknown", "entries": []}
        return {"state": "filled", "verified_at": row["read_at"], "entries": row["value"]["entries"],
                "sources": journal_sources_from_value(row["value"])}

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


# What the detail of a job opens in each frozen state of a job (the prototype
# Runs): its sections and the prompts it shows raw.
VIEW_DETAILS = {
    "job-configuration": {"open": ("configuration",)},
    "job-system-prompt": {"open": ("prompts", "system")},
    "job-user-prompt-rendered": {"open": ("prompts", "user")},
    "job-user-prompt-raw": {"open": ("prompts", "user"), "raw": ("user",)},
}


def _listed(query, name, default):
    """The comma-separated values of `name` in the address, else `default`."""
    if name not in query:
        return tuple(default)
    return tuple(value for value in query[name][0].split(",") if value)


# The sources a run is drawn from: its workflow beads, and the sessions the
# supervisor lists for its agents.
RUN_SOURCES = ("runs", "sessions")


def _stale_at(snapshot, names):
    """When the sources ``names`` no longer current were last read (the
    oldest of them); None while each is current or was never read."""
    read_ats = [snapshot[name]["read_at"] for name in names
                if snapshot.get(name) and snapshot[name].get("freshness") in (STALE, UNKNOWN)
                and snapshot[name].get("read_at") is not None]
    return min(read_ats) if read_ats else None


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
    factory_root=None,
    factory_check_validity_seconds=None,
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
    # What a Runs state selects when the address names nothing (the
    # isolated cockpit of a frozen state; empty in service).
    server.runs_view = {}
    # The settings and the upkeep of the page Usine (G2, af-f8nlhr): their
    # doors (unset: refused as unknown commands), and what the page keeps
    # between two readings -- the last outcome of a role's setting, the
    # moment a setting, a proposal (with its words) or a cleaning had an
    # uncertain outcome, the last cleaning and the last preview of its scope.
    server.provider_failover_bin = None
    server.factory_maintain_bin = None
    server.proposal_door_bin = None
    server.door_timeout = DOOR_TIMEOUT_SECONDS
    server.setting_outcomes = {}
    server.setting_uncertain = {}
    server.proposal_uncertain = {}
    server.proposal_lock = threading.Lock()
    server.cleanup_result = None
    server.cleanup_uncertain = None
    server.cleanup_previewed_at = None
    server.session_trace = None
    server.stop_driver = None
    server.benjamin_login = ""
    # The address the operator opens the cockpit at: the HTTPS address of
    # the node behind Tailscale Serve once it is set (I, af-cp4fzd).
    server.public_url = ""
    server.procedure_settings = dict
    # The rituals file of the Factory (« Rituels »): unset, nothing read.
    server.rituals_file = None
    # Where the projects are declared (cockpit.projects.descriptors): the
    # page of a project names it from there while its chantiers are unread.
    server.descriptors_dir = None
    server.extra_requests = lambda snapshot, now: []
    # The sections of the page Usine, each as it was last checked
    # (cockpit.factory.checks): the machine, the connections as the read
    # model held them, the providers and what the failover observed of
    # them, the configuration of the roles with the sessions observed at
    # work -- read in the Factory's files at ``factory_root``.
    root = FACTORY_ROOT if factory_root is None else factory_root
    server.stop_procedure_file = Path(root) / "docs" / "RUNBOOK_STOP_AND_RESTART.md"
    server.factory_checks = SectionChecks({
        "machine": read_machine,
        "connexions": lambda: read_model.snapshot(),
        "fournisseurs": lambda: read_configuration(root, read_model.now()),
        "agents": lambda: {"configuration": read_configuration(root, read_model.now()),
                           "sessions": read_model.snapshot().get("sessions")},
    }, read_model.now, CHECK_VALIDITY_SECONDS if factory_check_validity_seconds is None
        else factory_check_validity_seconds)
    # A preview of the scope of the cleaning stays current as long as a
    # check of a section of the page does.
    server.cleanup_validity_seconds = (CHECK_VALIDITY_SECONDS if factory_check_validity_seconds is None
                                       else factory_check_validity_seconds)
    server.illisible_after_seconds = (
        ILLISIBLE_THRESHOLD_SECONDS if illisible_after_seconds is None else illisible_after_seconds
    )
    return server


class _AlwaysRefuseGuard:
    def check(self, method, headers):
        from cockpit.access.guard import GuardResult, REFUSED_SESSION

        return GuardResult(False, REFUSED_SESSION)

    def check_page_post(self, method, headers):
        return self.check(method, headers)

    def check_reader(self, headers):
        """No identity configured: nothing to tell a reader from another."""
        from cockpit.access.guard import GuardResult

        return GuardResult(True, "")
