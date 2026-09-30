"""Subscribes to the gc supervisor's SSE stream (127.0.0.1:8372, spec .3).

Runs in its own daemon thread. A dropped connection, a refused connection,
or gc simply being gone (suspended city, stopped controller) never crashes
the cockpit process (af-0b6ffa AC4: "survit à une suspension et à un arrêt
de la cité simulés") — it reconnects with backoff, and the read model ages
the ``gc`` source toward stale/unknown on its own in the meantime. A
``partial: true`` event is ingested but never marked a complete read
(spec .14).
"""
import json
import threading
import urllib.error
import urllib.request

RECONNECT_SECONDS = 1.0
MAX_RECONNECT_SECONDS = 15.0


class GcSsePoller:
    def __init__(self, read_model, base_url, source="gc", events_path="/events"):
        self._read_model = read_model
        self._base_url = base_url.rstrip("/")
        self._source = source
        self._events_url = self._base_url + events_path
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        backoff = RECONNECT_SECONDS
        while not self._stop.is_set():
            try:
                self._consume_once()
                backoff = RECONNECT_SECONDS
            except (urllib.error.URLError, OSError, ValueError):
                pass
            if self._stop.is_set():
                return
            self._stop.wait(backoff)
            backoff = min(backoff * 2, MAX_RECONNECT_SECONDS)

    def _consume_once(self):
        req = urllib.request.Request(self._events_url, headers={"Accept": "text/event-stream"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data_lines = []
            for raw_line in resp:
                if self._stop.is_set():
                    return
                line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                if line == "":
                    if data_lines:
                        self._ingest_event("\n".join(data_lines))
                        data_lines = []
                    continue
                if line.startswith("data:"):
                    data_lines.append(line[len("data:"):].lstrip())

    def _ingest_event(self, raw_data):
        try:
            payload = json.loads(raw_data)
        except ValueError:
            return
        complete = not bool(payload.get("partial", False))
        self._read_model.ingest(self._source, payload, complete=complete)
