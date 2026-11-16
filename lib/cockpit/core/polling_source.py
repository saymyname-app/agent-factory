"""A generic periodically-polled source (Beads, GitHub, rituals, git clone).

Each of these reads at its own rhythm (spec .3), unlike gc which pushes over
SSE. ``read_fn`` is a zero-argument callable returning the value to ingest;
it runs in a background daemon thread and any exception it raises is caught
so one failing source never takes down the cockpit process or the other
sources (af-0b6ffa AC4).
"""
import threading
import time

# A source whose read just failed is asked again after at most this long:
# with a 30 s or 60 s rhythm, one bad first read would otherwise leave the
# value unknown for that whole interval.
RETRY_SECONDS = 2.0


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

    def request_stop(self):
        """Ask the thread to end; never waits (process.shut_down)."""
        self._stop.set()

    def join(self, timeout):
        """True once the thread has ended, False while it is still busy."""
        if self._thread is None:
            return True
        self._thread.join(timeout=max(0.0, timeout))
        return not self._thread.is_alive()

    def stop(self):
        self.request_stop()
        self.join(5)

    def _run(self):
        while not self._stop.is_set():
            ok = self._poll_once()
            self._stop.wait(self._interval if ok else min(self._interval, RETRY_SECONDS))

    @property
    def source(self):
        return self._source

    def poll_now(self):
        """Force an immediate read, bypassing the interval wait (spec .65:
        the health zone's "revérifier maintenant" button, T16; and the
        re-read after an Operator Action). True when the read succeeded."""
        return self._poll_once()

    def _poll_once(self):
        started = time.monotonic()
        try:
            value = self._read_fn()
        except Exception:
            self._read_model.fail(self._source)
            return False
        self._read_model.ingest(self._source, value, latency=time.monotonic() - started)
        return True
