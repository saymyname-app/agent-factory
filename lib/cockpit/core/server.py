"""The cockpit HTTP process — pure code, 127.0.0.1 only (spec .9, AC4).

Binding anywhere else is refused outright rather than merely discouraged by
config: a local process already has every power on this host (spec .9
threat model), but the cockpit is still not allowed to become reachable
from the tailnet or LAN by an operator mistake in a config file.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cockpit.access.guard import session_cookie_header
from cockpit.actions.registry import ActionError
from cockpit.core.freshness import UNKNOWN
from cockpit.health import collectors
from cockpit.health.engine import (
    FACTORY_STALLED_AFTER_SECONDS,
    SUPERVISOR_UNREACHABLE_AFTER_SECONDS,
    compute_health,
)
from cockpit.requests.builder import build_requests
from cockpit.requests.defects import DefectCounter
from cockpit.ui.base.page import render_home
from cockpit.ui.health.page import render_health_zone
from cockpit.ui.health.tokens import CSS as HEALTH_CSS
from cockpit.ui.home.page import render_requests_section

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
            self._send_json(self._requests_payload(read_model.snapshot()))
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
        if self.path == "/":
            snapshot = read_model.snapshot()
            stale_names = read_model.stale_or_unknown()
            stale_rows = [
                {"display_name": snapshot[name]["display_name"], "freshness": snapshot[name]["freshness"]}
                for name in stale_names
            ]
            requests_section_html = self._render_requests_section(snapshot)
            health = self._compute_health(read_model)
            checked_at = _latest_read_at(snapshot, ("beads", "git"))
            health_html = render_health_zone(health, checked_at=checked_at)
            body = render_home(
                read_model.headline(),
                stale_rows,
                requests_section_html=requests_section_html,
                extra_sections_html=health_html,
                extra_css=HEALTH_CSS,
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
            self.send_response(303)
            self.send_header("Location", "/")
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

    def _render_requests_section(self, snapshot):
        """"Ce qui t'attend" (T12, af-is5e97): built from the beads source
        already in the read model — no direct read of any source here, per
        the model in :mod:`cockpit.core.readmodel`."""
        beads_row = snapshot.get("beads")
        if beads_row is None or beads_row["freshness"] == UNKNOWN:
            last_known_at = beads_row["read_at"] if beads_row else None
            return render_requests_section([], source_unknown=True, last_known_at=last_known_at)
        requests = build_requests(
            beads_row["value"], verifie_a=beads_row["read_at"], defects=self.server.defect_counter
        )
        return render_requests_section(requests, verified_at=beads_row["read_at"])

    def _requests_payload(self, snapshot):
        """JSON twin of :meth:`_render_requests_section` (T12, af-is5e97):
        lets a test assert on structured fields and the producer-defect
        count without scraping the rendered HTML."""
        beads_row = snapshot.get("beads")
        if beads_row is None or beads_row["freshness"] == UNKNOWN:
            return {
                "state": "unknown",
                "requests": [],
                "defect_count": self.server.defect_counter.count,
            }
        requests = build_requests(
            beads_row["value"], verifie_a=beads_row["read_at"], defects=self.server.defect_counter
        )
        return {
            "state": "filled" if requests else "empty",
            "verified_at": beads_row["read_at"],
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
            last_progress_at=gc_value.get("last_progress_at"),
            delivery_ready=bool(gc_value.get("delivery_ready")),
            mayor_first_since=collectors.mayor_first_since_list(beads),
            loops=collectors.loop_items(beads),
            order_failures=collectors.order_failure_items(beads),
            red_ci=collectors.red_ci_items(beads),
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
    return server


class _AlwaysRefuseGuard:
    def check(self, method, headers):
        from cockpit.access.guard import GuardResult, REFUSED_SESSION

        return GuardResult(False, REFUSED_SESSION)
