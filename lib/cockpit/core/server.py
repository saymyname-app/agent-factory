"""The cockpit HTTP process — pure code, 127.0.0.1 only (spec .9, AC4).

Binding anywhere else is refused outright rather than merely discouraged by
config: a local process already has every power on this host (spec .9
threat model), but the cockpit is still not allowed to become reachable
from the tailnet or LAN by an operator mistake in a config file.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cockpit.core.freshness import UNKNOWN
from cockpit.requests.builder import build_requests
from cockpit.requests.defects import DefectCounter
from cockpit.ui.base.page import render_home
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
        if self.path == "/":
            snapshot = read_model.snapshot()
            stale_names = read_model.stale_or_unknown()
            stale_rows = [
                {"display_name": snapshot[name]["display_name"], "freshness": snapshot[name]["freshness"]}
                for name in stale_names
            ]
            requests_section_html = self._render_requests_section(snapshot)
            body = render_home(read_model.headline(), stale_rows, requests_section_html).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

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
                }
                for r in requests
            ],
            "defect_count": self.server.defect_counter.count,
        }

    def _send_json(self, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def make_server(read_model, host="127.0.0.1", port=0):
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
    return server
