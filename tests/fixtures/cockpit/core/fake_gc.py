"""A fake gc supervisor HTTP API, for the cockpit seam tests.

Answers like gc 1.4.1 does on the live host (checked 2026-10-06;
``tests/cockpit-fake-gc-contract-test.py`` re-checks it against the
installed supervisor): ``/events`` and ``/status`` are the HTML dashboard,
the API lives under ``/v0``, the per-city stream sends ``event: event``
frames plus ``event: heartbeat`` frames, an unknown city is a 404
``application/problem+json``. Controllable so a test can make it go down
(simulating a dead supervisor) or silence its stream without killing the
cockpit process under test.
"""
import json
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CITY = "fake-city"
DASHBOARD_HTML = b"<!doctype html><html><head><title>Gas City</title></head><body></body></html>"
DASHBOARD_PATHS = ("/", "/events", "/status", "/v0")


class FakeGc:
    def __init__(self, heartbeat_seconds=0.1):
        self._lock = threading.Lock()
        self._heartbeat_seconds = heartbeat_seconds
        self._status = {
            "name": CITY,
            "path": "/fake/" + CITY,
            "version": "1.4.1",
            "uptime_sec": 1,
            "suspended": False,
            "agent_count": 2,
            "rig_count": 1,
            "running": 0,
            "agents": {"total": 2, "running": 0, "suspended": 0, "quarantined": 0},
            "rigs": {"total": 1, "suspended": 0},
            "work": {"in_progress": 0, "ready": 0, "open": 0},
            "mail": {"unread": 0, "total": 0},
        }
        self._ready = []
        self._subscribers = []
        self._down = False
        self._stream_muted = False
        self._seq = 0
        gc = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass

            def do_GET(self):
                if gc._down:
                    # A dead supervisor: drop the connection, answer nothing.
                    self.connection.close()
                    return
                path = self.path.split("?", 1)[0]
                if path in DASHBOARD_PATHS:
                    self._send(200, "text/html; charset=utf-8", DASHBOARD_HTML)
                    return
                if path == "/v0/cities":
                    self._send_json({"items": [{"name": CITY, "path": "/fake/" + CITY, "running": True}], "total": 1})
                    return
                if path.startswith("/v0/city/"):
                    city, _, rest = path[len("/v0/city/"):].partition("/")
                    if city != CITY:
                        self._send_json(
                            {
                                "type": "urn:gascity:error:city-not-found",
                                "title": "City Not Found",
                                "status": 404,
                                "detail": "not_found: city not found or not running: " + city,
                                "code": "city-not-found",
                            },
                            status=404,
                            content_type="application/problem+json",
                        )
                        return
                    if rest == "status":
                        with gc._lock:
                            payload = dict(gc._status)
                        self._send_json(payload)
                        return
                    if rest == "beads/ready":
                        with gc._lock:
                            items = list(gc._ready)
                        self._send_json({"items": items, "total": len(items)})
                        return
                    if rest == "events/stream":
                        self._stream_events()
                        return
                self._send(404, "text/plain; charset=utf-8", b"404 page not found\n")

            def _send(self, status, content_type, body):
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_json(self, payload, status=200, content_type="application/json"):
                self._send(status, content_type, json.dumps(payload).encode("utf-8"))

            def _stream_events(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                q = queue.Queue()
                gc._register(q)
                try:
                    while True:
                        if gc._down:
                            return
                        try:
                            event = q.get(timeout=gc._heartbeat_seconds)
                        except queue.Empty:
                            if gc._stream_muted:
                                continue
                            stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                            chunk = 'event: heartbeat\ndata: {"timestamp":"%s"}\n\n' % stamp
                        else:
                            if event is None:
                                return
                            if gc._stream_muted:
                                continue
                            chunk = "id: %d\nevent: event\ndata: %s\n\n" % (event["seq"], json.dumps(event))
                        self.wfile.write(chunk.encode("utf-8"))
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    return
                finally:
                    gc._unregister(q)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self):
        host, port = self._server.server_address
        return "http://%s:%d" % (host, port)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self.go_down()
        self._server.shutdown()
        self._server.server_close()

    def go_down(self):
        """The supervisor dies: every request is dropped, streams end."""
        with self._lock:
            self._down = True
            subscribers = list(self._subscribers)
        for q in subscribers:
            q.put(None)

    def go_up(self):
        with self._lock:
            self._down = False

    def mute_stream(self):
        """Keep answering the API but send nothing more on open streams —
        a supervisor whose event stream hangs."""
        with self._lock:
            self._stream_muted = True

    def set_status(self, suspended=None, agents_running=None, partial_errors=None):
        with self._lock:
            if suspended is not None:
                self._status["suspended"] = suspended
            if agents_running is not None:
                self._status["agents"]["running"] = agents_running
                self._status["running"] = agents_running
            if partial_errors is not None:
                if partial_errors:
                    self._status["partial"] = True
                    self._status["partial_errors"] = list(partial_errors)
                else:
                    self._status.pop("partial", None)
                    self._status.pop("partial_errors", None)

    def set_ready(self, items):
        """``items``: ready beads as ``/beads/ready`` lists them (id, title,
        status, metadata, ...)."""
        with self._lock:
            self._ready = list(items)
            self._status["work"]["ready"] = len(self._ready)

    def emit(self, event_type, subject="", payload=None):
        """Send one city event to every open stream, e.g. ``bead.closed``."""
        with self._lock:
            self._seq += 1
            event = {
                "seq": self._seq,
                "type": event_type,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
                "actor": "controller",
                "subject": subject,
                "payload": payload or {},
            }
            subscribers = list(self._subscribers)
        for q in subscribers:
            q.put(event)

    def _register(self, q):
        with self._lock:
            self._subscribers.append(q)

    def _unregister(self, q):
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)
