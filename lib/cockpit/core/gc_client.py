"""Reads the gc supervisor (127.0.0.1:8372, spec .3) the way it really answers.

Three reads of the supervisor's own HTTP API, checked against gc 1.4.1 on
the live host (2026-10-06) — ``/events`` and ``/status`` are its HTML
dashboard, not an API:

- ``GET /v0/cities`` names the city when none is configured.
- ``GET /v0/city/<city>/events/stream`` is the SSE stream: ``event: event``
  frames carrying ``{"seq", "type", "ts", "actor", "subject", "payload"}``,
  and an ``event: heartbeat`` frame about every 15 s. It proves the
  supervisor is alive and dates the factory's last progress.
- ``GET /v0/city/<city>/status`` and ``.../beads/ready`` give the values
  shown (suspended, agents at work, delivery work ready).

The ``gc`` source is a complete read only while the stream is alive *and*
the status answered. A status carrying ``partial: true`` still delivers the
fields read here; what gc could not read is kept in ``partial_errors`` for
the health zone instead of hiding every value (spec .14: "ce n'est pas une
source toujours complète").

Two daemon threads. A dropped or refused connection, or gc simply being
gone, never crashes the cockpit process (af-0b6ffa AC4): the stream
reconnects with backoff and the read model ages ``gc`` toward
stale/unknown on its own in the meantime.
"""
import json
import threading
import urllib.error
import urllib.parse
import urllib.request

RECONNECT_SECONDS = 1.0
MAX_RECONNECT_SECONDS = 15.0
STATUS_POLL_SECONDS = 30.0
# Three missed heartbeats (gc sends one about every 15 s).
STREAM_SILENCE_SECONDS = 45.0

CITIES_PATH = "/v0/cities"
STREAM_PATH = "/v0/city/%s/events/stream"
STATUS_PATH = "/v0/city/%s/status"
READY_PATH = "/v0/city/%s/beads/ready"

# Spec .68 "rien n'a progressé" (commit, étape fermée, événement de session).
PROGRESS_EVENT_TYPES = ("bead.closed",)
PROGRESS_EVENT_PREFIXES = ("session.",)
# Events after which the status is worth re-reading at once.
STATUS_EVENT_PREFIXES = ("session.", "city.")

DELIVERY_PLANE = "delivery"


class GcSsePoller:
    def __init__(
        self,
        read_model,
        base_url,
        source="gc",
        city=None,
        status_poll_seconds=STATUS_POLL_SECONDS,
        stream_silence_seconds=STREAM_SILENCE_SECONDS,
        reconnect_seconds=RECONNECT_SECONDS,
    ):
        self._read_model = read_model
        self._base_url = base_url.rstrip("/")
        self._source = source
        self._city = city or None
        self._status_poll_seconds = status_poll_seconds
        self._stream_silence_seconds = stream_silence_seconds
        self._reconnect_seconds = reconnect_seconds
        self._lock = threading.Lock()
        self._stream_seen_at = None
        self._last_progress_at = None
        self._response = None
        self._stop = threading.Event()
        self._status_wake = threading.Event()
        self._threads = []

    def start(self):
        self._threads = [
            threading.Thread(target=self._run_stream, daemon=True),
            threading.Thread(target=self._run_status, daemon=True),
        ]
        for thread in self._threads:
            thread.start()
        return self

    def stop(self):
        self._stop.set()
        self._status_wake.set()
        response = self._response
        if response is not None:
            try:
                response.close()
            except OSError:
                pass
        for thread in self._threads:
            thread.join(timeout=5)

    def poll_now(self):
        """Force an immediate status read ("revérifier maintenant", spec .65)."""
        self._refresh_status()

    # -- stream ---------------------------------------------------------
    def _run_stream(self):
        backoff = self._reconnect_seconds
        while not self._stop.is_set():
            try:
                self._consume_stream()
                backoff = self._reconnect_seconds
            except (urllib.error.URLError, OSError, ValueError):
                pass
            if self._stop.is_set():
                return
            self._stop.wait(backoff)
            backoff = min(backoff * 2, MAX_RECONNECT_SECONDS)

    def _consume_stream(self):
        city = self._resolve_city()
        req = urllib.request.Request(
            self._base_url + STREAM_PATH % urllib.parse.quote(city, safe=""),
            headers={"Accept": "text/event-stream"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if not content_type.startswith("text/event-stream"):
                raise ValueError("gc answered %r, not an event stream" % content_type)
            self._response = resp
            self._stream_alive(first=True)
            event_name, data_lines = "", []
            for raw_line in resp:
                if self._stop.is_set():
                    return
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                if line == "":
                    if event_name or data_lines:
                        self._on_frame(event_name, "\n".join(data_lines))
                    event_name, data_lines = "", []
                elif line.startswith("event:"):
                    event_name = line[len("event:"):].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[len("data:"):].lstrip())

    def _stream_alive(self, first=False):
        now = self._read_model.now()
        with self._lock:
            was_silent = self._stream_seen_at is None or (
                now - self._stream_seen_at > self._stream_silence_seconds
            )
            self._stream_seen_at = now
            if first and self._last_progress_at is None:
                # Nothing witnessed yet: count "no progress" from the
                # moment the cockpit started watching, never from zero.
                self._last_progress_at = now
        if first or was_silent:
            self._status_wake.set()

    def _on_frame(self, event_name, raw_data):
        self._stream_alive()
        if event_name == "heartbeat":
            return
        try:
            event_type = str(json.loads(raw_data).get("type") or "")
        except (ValueError, AttributeError):
            return
        if event_type in PROGRESS_EVENT_TYPES or event_type.startswith(PROGRESS_EVENT_PREFIXES):
            with self._lock:
                self._last_progress_at = self._read_model.now()
            self._status_wake.set()
        elif event_type.startswith(STATUS_EVENT_PREFIXES):
            self._status_wake.set()

    # -- status ---------------------------------------------------------
    def _run_status(self):
        while not self._stop.is_set():
            self._status_wake.wait(self._status_poll_seconds)
            self._status_wake.clear()
            if self._stop.is_set():
                return
            self._refresh_status()

    def _refresh_status(self):
        try:
            city = self._resolve_city()
            status = self._get_json(STATUS_PATH % urllib.parse.quote(city, safe=""))
            value = {
                "city": city,
                "suspended": bool(status["suspended"]),
                "agents_running": int(status["agents"]["running"]),
                "work": dict(status["work"]),
                "partial_errors": list(status.get("partial_errors") or []) if status.get("partial") else [],
            }
        except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError):
            return
        value["delivery_ready"] = self._read_delivery_ready(city)
        now = self._read_model.now()
        with self._lock:
            value["last_progress_at"] = self._last_progress_at
            stream_alive = self._stream_seen_at is not None and (
                now - self._stream_seen_at <= self._stream_silence_seconds
            )
        self._read_model.ingest(self._source, value, complete=stream_alive)

    def _read_delivery_ready(self, city):
        """True when a delivery-plane ticket is ready; None when unreadable
        (never a guessed False, spec .63)."""
        try:
            ready = self._get_json(READY_PATH % urllib.parse.quote(city, safe=""))
            return any(
                (item.get("metadata") or {}).get("gc.plane") == DELIVERY_PLANE
                for item in ready["items"]
            )
        except (urllib.error.URLError, OSError, ValueError, KeyError, TypeError, AttributeError):
            return None

    # -- shared ---------------------------------------------------------
    def _resolve_city(self):
        if self._city:
            return self._city
        try:
            cities = self._get_json(CITIES_PATH)["items"]
            running = [c for c in cities if c.get("running")]
            chosen = (running or cities)[0]["name"]
        except (KeyError, IndexError, TypeError, AttributeError):
            raise ValueError("gc lists no city")
        self._city = chosen
        return chosen

    def _get_json(self, path):
        req = urllib.request.Request(self._base_url + path, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if not content_type.startswith("application/json"):
                raise ValueError("gc answered %r on %s, not JSON" % (content_type, path))
            return json.loads(resp.read().decode("utf-8"))
