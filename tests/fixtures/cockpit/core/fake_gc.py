"""A fake gc supervisor HTTP API, for the cockpit seam tests.

Answers like gc does on the live host (1.4.1 on 2026-10-06, 1.5.0 on
2026-10-11;
``tests/cockpit-fake-gc-contract-test.py`` re-checks it against the
installed supervisor): ``/events`` and ``/status`` are the HTML dashboard,
the API lives under ``/v0``, the per-city stream sends ``event: event``
frames plus ``event: heartbeat`` frames, an unknown city is a 404
``application/problem+json``. Controllable so a test can make it go down
(simulating a dead supervisor) or silence its stream without killing the
cockpit process under test.

It takes the two writes a clean stop uses, as the installed supervisor
publishes them (``/openapi.json``, read on 2026-10-27; af-npz9v1.21):
``PATCH /v0/city/<city>`` with ``{"suspended": true|false}`` suspends or
resumes the city, ``POST /v0/city/<city>/session/<id>/stop`` stops one
session; each answers ``{"status": "ok"}``. Every write it receives is kept
in ``writes``, any other one too (``kill``, a session ``suspend``...) and
answered 404: a test sees what a cockpit asked, a complete stop included.

Its journal, ``GET /v0/city/<city>/events``, keeps every event it emitted
and gives it by pages as gc 1.5.0 does (``/openapi.json`` and the installed
supervisor, read on 2026-11-10; af-yxxa68): newest first, ``limit`` items
(omitted or 0: 100; above 1000 or not a number: 422 ``validation-failed``),
``next_cursor`` only on a truncated page, ``cursor`` passed back gives the
next page, an unknown cursor is a 400 ``invalid-cursor``; ``type`` and
``actor`` filter. ``/sessions`` takes the same ``limit`` and ``cursor``, in
the order ``set_sessions`` gave. The blocking reads (``index``, ``wait``)
and ``since`` are not played: they answer a 400 ``not-in-fake`` rather than
a page that ignores them.
"""
import base64
import json
import queue
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

DEFAULT_LIMIT = 100
MAX_LIMIT = 1000

CITY = "fake-city"
DASHBOARD_HTML = b"<!doctype html><html><head><title>Gas City</title></head><body></body></html>"
DASHBOARD_PATHS = ("/", "/events", "/status", "/v0")


class FakeGc:
    def __init__(self, heartbeat_seconds=0.1, city=CITY):
        """``city``: the name of the one city this supervisor runs."""
        self._lock = threading.Lock()
        self.city = city
        self._heartbeat_seconds = heartbeat_seconds
        self._status = {
            "name": city,
            "path": "/fake/" + city,
            "version": "1.5.0",
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
        self._sessions = []
        self._subscribers = []
        self._journal = []
        self._down = False
        self._stream_muted = False
        self._seq = 0
        self.writes = []
        gc = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass

            def do_GET(self):
                if gc._down:
                    # A dead supervisor: drop the connection, answer nothing.
                    self.connection.close()
                    return
                path, _, query = self.path.partition("?")
                if path in DASHBOARD_PATHS:
                    self._send(200, "text/html; charset=utf-8", DASHBOARD_HTML)
                    return
                if path == "/v0/cities":
                    self._send_json({"items": [{"name": gc.city, "path": "/fake/" + gc.city, "running": True}], "total": 1})
                    return
                if path.startswith("/v0/city/"):
                    city, _, rest = path[len("/v0/city/"):].partition("/")
                    if city != gc.city:
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
                    if rest == "sessions":
                        with gc._lock:
                            items = [dict(item) for item in gc._sessions]
                        self._send_page(query, "ss", items, key=lambda index, item: index)
                        return
                    if rest == "events":
                        params = parse_qs(query)
                        unplayed = sorted({"index", "wait", "since"} & set(params))
                        if unplayed:
                            self._problem(400, "not-in-fake", "the fake gc does not play " + ", ".join(unplayed))
                            return
                        with gc._lock:
                            items = [dict(event) for event in reversed(gc._journal)]
                        for name in ("type", "actor"):
                            if params.get(name):
                                items = [event for event in items if event[name] == params[name][-1]]
                        self._send_page(query, "sq", items, key=lambda index, event: event["seq"])
                        return
                    if rest == "events/stream":
                        self._stream_events()
                        return
                self._send(404, "text/plain; charset=utf-8", b"404 page not found\n")

            def _city_write(self, method):
                """A write under /v0/city/<city>: (city, rest, body), or
                None once it is answered."""
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                path = self.path.split("?", 1)[0]
                try:
                    body = json.loads(raw.decode("utf-8")) if raw else {}
                except ValueError:
                    body = None
                with gc._lock:
                    gc.writes.append({"method": method, "path": path, "body": body})
                if gc._down:
                    self.connection.close()
                    return None
                if not path.startswith("/v0/city/"):
                    self._send(404, "text/plain; charset=utf-8", b"404 page not found\n")
                    return None
                city, _, rest = path[len("/v0/city/"):].partition("/")
                if city != gc.city:
                    self._problem(404, "city-not-found", "not_found: city not found or not running: " + city)
                    return None
                return rest, body

            def _problem(self, status, code, detail, title=None):
                self._send_json({"type": "urn:gascity:error:" + code, "title": title or code, "status": status,
                                 "detail": detail, "code": code}, status=status,
                                content_type="application/problem+json")

            def do_PATCH(self):
                answer = self._city_write("PATCH")
                if answer is None:
                    return
                rest, body = answer
                if rest or not isinstance(body, dict) or not isinstance(body.get("suspended"), bool):
                    self._problem(422, "invalid", "a city is patched with {\"suspended\": true|false}")
                    return
                gc.set_status(suspended=body["suspended"])
                self._send_json({"status": "ok"})

            def do_POST(self):
                answer = self._city_write("POST")
                if answer is None:
                    return
                rest, _ = answer
                parts = rest.split("/")
                if len(parts) != 3 or parts[0] != "session" or parts[2] != "stop":
                    self._send(404, "text/plain; charset=utf-8", b"404 page not found\n")
                    return
                with gc._lock:
                    found = [s for s in gc._sessions if s.get("id") == parts[1]]
                    for session in found:
                        session["running"] = False
                if not found:
                    self._problem(404, "session-not-found", "not_found: session " + parts[1])
                    return
                self._send_json({"id": parts[1], "status": "ok"})

            def _send_page(self, query, kind, items, key):
                """One page of ``items`` as gc 1.5.0 lists them: ``key``
                (of the position and the item) decreases along the list,
                the cursor names the key of the last item given."""
                params = parse_qs(query)
                raw = params.get("limit", [""])[-1]
                try:
                    limit = int(raw) if raw != "" else 0
                except ValueError:
                    return self._invalid_limit("invalid integer", raw)
                if limit < 0:
                    return self._invalid_limit("expected number >= 0", limit)
                if limit > MAX_LIMIT:
                    return self._invalid_limit("expected number <= %d" % MAX_LIMIT, limit)
                limit = limit or DEFAULT_LIMIT
                keyed = [(key(index, item), item) for index, item in enumerate(items)]
                if kind == "ss":
                    # Positions grow along the list: walk it with the key negated.
                    keyed = [(-k, item) for k, item in keyed]
                if params.get("cursor"):
                    after = _read_cursor(params["cursor"][-1], kind)
                    if after is None:
                        self._problem(400, "invalid-cursor",
                                      "cursor is not a valid pagination token; re-fetch the first page",
                                      title="Invalid Cursor")
                        return
                    keyed = [(k, item) for k, item in keyed if k < after]
                page = keyed[:limit]
                payload = {"items": [item for _, item in page], "total": len(items)}
                if len(keyed) > limit:
                    payload["next_cursor"] = _cursor(kind, page[-1][0])
                self._send_json(payload)

            def _invalid_limit(self, message, value):
                self._send_json({"type": "urn:gascity:error:validation-failed", "title": "Validation Failed",
                                 "status": 422, "detail": "validation failed",
                                 "errors": [{"message": message, "location": "query.limit", "value": value}],
                                 "code": "validation-failed"},
                                status=422, content_type="application/problem+json")

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

    def set_sessions(self, items):
        """``items``: agent sessions as ``/sessions`` lists them (id,
        template, session_name, running, last_active, and active_bead for
        the ones on a ticket)."""
        with self._lock:
            self._sessions = [dict(item) for item in items]

    def emit(self, event_type, subject="", payload=None, ts=None, actor="controller", **fields):
        """Log one city event in the journal and send it to every open
        stream, e.g. ``bead.closed``. ``ts`` (now when omitted) and
        ``actor`` as gc writes them; ``fields``, the keys gc adds to some
        events (``session_id``, ``run_id``, ``step_id``...)."""
        with self._lock:
            self._seq += 1
            event = dict(fields)
            event.update({
                "seq": self._seq,
                "type": event_type,
                "ts": ts or time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
                "actor": actor,
                "subject": subject,
                "payload": payload or {},
            })
            self._journal.append(event)
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


def _cursor(kind, key):
    """``v1:`` and the unpadded base64 of ``{"k": kind, "s": key}``, the
    form gc 1.5.0 gives its journal (``v1:eyJrIjoic3EiLCJzIjoxMzk2MzkyfQ``)."""
    raw = json.dumps({"k": kind, "s": key}, separators=(",", ":")).encode("utf-8")
    return "v1:" + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _read_cursor(token, kind):
    """The key a cursor of ``kind`` names, or None when it is not one."""
    if not token.startswith("v1:"):
        return None
    body = token[len("v1:"):]
    try:
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("k") != kind or type(data.get("s")) is not int:
        return None
    return data["s"]
