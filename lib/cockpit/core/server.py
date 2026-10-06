"""The cockpit HTTP process — pure code, 127.0.0.1 only (spec .9, AC4).

Binding anywhere else is refused outright rather than merely discouraged by
config: a local process already has every power on this host (spec .9
threat model), but the cockpit is still not allowed to become reachable
from the tailnet or LAN by an operator mistake in a config file.
"""
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cockpit.access.guard import session_cookie_header
from cockpit.actions.registry import ActionError
from cockpit.core.freshness import FRESH, UNKNOWN
from cockpit.health import collectors
from cockpit.health.engine import (
    FACTORY_STALLED_AFTER_SECONDS,
    SUPERVISOR_UNREACHABLE_AFTER_SECONDS,
    compute_health,
)
from cockpit.projects.source import from_value as projects_from_value
from cockpit.projects.source import project_page_data
from cockpit.requests.assemble import assemble_from_snapshot
from cockpit.requests.defects import DefectCounter
from cockpit.requests.journal import entries_from_value as journal_entries_from_value
from cockpit.requests.sources.readability import ILLISIBLE_THRESHOLD_SECONDS
from cockpit.ui.base.page import render_document, render_fresh, render_home
from cockpit.ui.health.page import render_health_zone, render_status_line
from cockpit.ui.home.page import render_requests_section
from cockpit.ui.journal.render import CSS as JOURNAL_CSS
from cockpit.ui.journal.render import render_journal_page, render_journal_section, render_journal_unknown
from cockpit.ui.notify.render import render_envois_section
from cockpit.ui.projects.page import (
    render_historique_section,
    render_projects_section,
    render_projects_unknown,
)
from cockpit.ui.projects.project_page import render_project_page, render_project_unknown
from cockpit.ui.projects.tokens import CSS as PROJECT_PAGE_CSS

ALLOWED_HOSTS = {"127.0.0.1", "localhost"}


class CockpitRequestHandler(BaseHTTPRequestHandler):
    server_version = "cockpit/1"

    def log_message(self, fmt, *args):  # quiet by default; tests read the body
        pass

    def do_GET(self):
        read_model = self.server.read_model
        if self.path == "/api/status":
            self._send_json(read_model.snapshot())
            return
        if self.path == "/api/requests":
            self._send_json(self._requests_payload(read_model.snapshot(), read_model.now()))
            return
        if self.path == "/api/notifications":
            notify = self.server.notify
            self._send_json(
                {
                    "configured": bool(notify and notify.configured()),
                    "entries": notify.journal_entries() if notify else [],
                    "undelivered": sorted(self._undelivered()),
                }
            )
            return
        if self.path == "/api/journal":
            self._send_json(self._journal_payload(read_model.snapshot()))
            return
        if self.path == "/journal":
            self._send_journal_page(read_model)
            return
        if self.path == "/api/projects":
            self._send_json(self._projects_payload(read_model.snapshot()))
            return
        if self.path == "/api/health":
            self._send_json(self._compute_health(read_model))
            return
        if self.path.startswith("/api/actions/"):
            # T13, af-cx20q9 AC1: an action in GET is refused the same
            # way as any other guard failure, not a bare 404 — the guard
            # itself rejects on method before anything else is checked.
            guard_result = self.server.action_guard.check("GET", self.headers)
            self._send_json({"error": guard_result.reason}, status=403)
            return
        if self.path.startswith("/projet/"):
            self._send_project_page(read_model)
            return
        if self.path == "/":
            snapshot = read_model.snapshot()
            stale_names = read_model.stale_or_unknown()
            stale_rows = [
                {"display_name": snapshot[name]["display_name"], "freshness": snapshot[name]["freshness"]}
                for name in stale_names
            ]
            requests_section_html = self._render_requests_section(snapshot, read_model.now())
            health = self._compute_health(read_model)
            checked_at = _latest_read_at(snapshot, ("beads", "git"))
            health_html = render_health_zone(health, checked_at=checked_at)
            body = render_home(
                read_model.headline(),
                stale_rows,
                requests_section_html=requests_section_html,
                extra_sections_html=self._render_projects_zone(snapshot) + health_html,
                status_html=render_status_line(snapshot.get("gc"), health),
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            # T13, af-cx20q9: the SameSite=Strict cookie an action POST
            # must echo back — a cross-site POST never carries it, so its
            # presence alone proves this request came from a page the
            # cockpit itself served (cockpit.access.guard.ActionGuard).
            self.send_header("Set-Cookie", session_cookie_header(self.server.session_token))
            self.end_headers()
            self.wfile.write(body)
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
            if referer_path.startswith("/projet/") or referer_path == "/journal":
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
        try:
            result = handler(payload)
        except ActionError as exc:
            self._send_json({"error": str(exc)}, status=400)
            return
        self._send_json(result)

    def _assemble_requests(self, snapshot, now):
        """"Ce qui t'attend" (spec §"Demandes opérateur"): every kind of
        request, built only from what the read model already holds -- no
        direct read of any source here."""
        return assemble_from_snapshot(
            snapshot, now, self.server.defect_counter, self.server.illisible_after_seconds
        )

    def _undelivered(self):
        """Ids whose push could not be delivered yet (spec .59)."""
        notify = self.server.notify
        return notify.undelivered() if notify is not None else set()

    def _render_requests_section(self, snapshot, now):
        requests, beads_row, beads_known = self._assemble_requests(snapshot, now)
        if not beads_known:
            last_known_at = beads_row["read_at"] if beads_row else None
            return render_requests_section(
                requests, verified_at=now, source_unknown=True, last_known_at=last_known_at,
                undelivered=self._undelivered(),
            )
        return render_requests_section(
            requests, verified_at=beads_row["read_at"], undelivered=self._undelivered()
        )

    def _requests_payload(self, snapshot, now):
        """JSON twin of :meth:`_render_requests_section` (T12, af-is5e97):
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
        return render_projects_section(
            projects,
            sans_projet,
            stale_since=None if row["freshness"] == FRESH else row["read_at"],
        )

    def _send_project_page(self, read_model):
        """GET /projet/<id> (spec .49): one declared project's chantiers by
        stage, its travail hors chantier and its historique. An id no
        descriptor declares is a 404 that says so."""
        project_id = urllib.parse.unquote(self.path.split("?", 1)[0][len("/projet/"):])
        fresh_html = render_fresh(read_model.headline(), not read_model.stale_or_unknown())
        row = read_model.snapshot().get("projets")
        status = 200
        if row is None or row["value"] is None or row["freshness"] == UNKNOWN:
            inner = render_project_unknown(fresh_html) + render_projects_unknown(row["read_at"] if row else None)
        else:
            data = project_page_data(row["value"], project_id)
            if data is None:
                status = 404
                inner = render_project_unknown(fresh_html, unknown_project=True)
            else:
                project, hors_chantier, historique = data
                inner = render_project_page(
                    project,
                    hors_chantier=hors_chantier,
                    historique_html=render_historique_section([historique]),
                    fresh_html=fresh_html,
                )
        body = render_document(inner, extra_css=PROJECT_PAGE_CSS).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_journal_page(self, read_model):
        """GET /journal (spec .18): the resolved requests, re-read from the
        traces on the beads -- the cockpit keeps no copy of its own."""
        fresh_html = render_fresh(read_model.headline(), not read_model.stale_or_unknown())
        row = read_model.snapshot().get("journal")
        if row is None or row["value"] is None or row["freshness"] == UNKNOWN:
            section = render_journal_unknown(row["read_at"] if row else None)
        else:
            section = render_journal_section(journal_entries_from_value(row["value"]))
        notify = self.server.notify
        if notify is not None:
            # Journal des envois and the test notification (spec .60).
            section += render_envois_section(notify.journal_entries(), notify.configured())
        body = render_document(
            render_journal_page(section, fresh_html=fresh_html), extra_css=PROJECT_PAGE_CSS + JOURNAL_CSS
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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
            extra_lines=[
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
    server.illisible_after_seconds = (
        ILLISIBLE_THRESHOLD_SECONDS if illisible_after_seconds is None else illisible_after_seconds
    )
    return server


class _AlwaysRefuseGuard:
    def check(self, method, headers):
        from cockpit.access.guard import GuardResult, REFUSED_SESSION

        return GuardResult(False, REFUSED_SESSION)
