"""A generic periodically-polled source (Beads, GitHub, rituals, git clone).

Each of these reads at its own rhythm (spec .3), unlike gc which pushes over
SSE. ``read_fn`` is a zero-argument callable returning the value to ingest;
it runs in a background daemon thread and any exception it raises is caught
so one failing source never takes down the cockpit process or the other
sources (af-0b6ffa AC4).
"""
import threading


class PollingSource:
    def __init__(self, read_model, source, read_fn, interval_seconds):
        self._read_model = read_model
        self._source = source
        self._read_fn = read_fn
        self._interval = interval_seconds
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
        while not self._stop.is_set():
            self._poll_once()
            self._stop.wait(self._interval)

    def poll_now(self):
        """Force an immediate read, bypassing the interval wait (spec .65:
        the health zone's "revérifier maintenant" button, T16)."""
        self._poll_once()

    def _poll_once(self):
        try:
            value = self._read_fn()
        except Exception:
            return
        self._read_model.ingest(self._source, value)
