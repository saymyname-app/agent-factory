"""The cockpit's one reader of Beads (af-q55qqx.9).

Measured on factory-vm, 19/11/2026 09:50 Paris: four pollers each ran their
own ``bd`` reads -- about twenty per cycle, the six of Runs side by side, a
failed one asked again after 2 s, and every page's « revérifier » started
more. Seven to ten ``bd list`` ran at all times, Dolt sat at 285 % CPU and
the load at 17 on 8 cores; one ``bd list`` took 12 s instead of 4, the
cockpit's 10 s reads failed (« illisible », « tracker injoignable »), and
``bin/escalation-door list`` failed too. Every ``bd list --all
--has-metadata-key`` (history of Projets, Journal, Runs) ran into the
driver's own i/o timeout: those pages could never fill.

One thread now runs every read of the running cockpit, one ``bd`` at a time:

- each ``open_seconds``: ``bd list`` (the open beads) and the beads still
  carrying ``gc.needs_benjamin`` -- the ``beads`` source;
- the history the other views need (closed convoys, traces, workflow steps)
  is a mirror of every bead updated within ``history_days``: read once in
  slices of ``slice_days`` (``--updated-after``/``--updated-before``), then
  kept up to date each ``history_seconds`` by one ``--updated-after`` read
  (and one for the ended sessions, which the tracker keeps apart), plus
  ``bd children`` of each open Planning Map.

Every view is derived from what the reader holds (:class:`TrackerSnapshot`,
the same interface as :class:`cockpit.core.beads_source.DirectTracker`).
A page never runs ``bd``: ``poll_now`` asks the reader for a cycle of the
open reads and waits for it; requests made together share one cycle. A
derived value is dated by the oldest read it was made from, so a page says
« périmé » from that time, never fresher than it is.
"""
import math
import threading
import time
from datetime import datetime, timezone

from cockpit.core.beads_source import READ_TIMEOUT_SECONDS, flagged_args, read_beads_json

HISTORY_DAYS = 28
SLICE_DAYS = 7
# A failed read is asked again after RETRY_FIRST_SECONDS, then twice as
# long each time it fails again, up to RETRY_SECONDS: a source not ready at
# start is read again soon, one that keeps failing is not asked every 2 s
# (with reads failing on Dolt's own timeout, that was the storm).
RETRY_FIRST_SECONDS = 2.0
RETRY_SECONDS = 15.0
# Each incremental read starts this long before the previous one did: a
# bead written while it ran is read again, never missed.
OVERLAP_SECONDS = 120
# How long ``poll_now`` waits for the cycle it asked for.
POLL_NOW_WAIT_SECONDS = 90.0
# A ``poll_now`` within this long of the end of a cycle asked for takes its
# result: « revérifier » asks every source in turn, one cycle serves them.
COALESCE_SECONDS = 2.0

MAP_LABEL = "wayfinder:map"
SESSION_TYPE, SESSION_AGENT_KEY = "session", "agent_name"


def _iso(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _beads(payload):
    return [b for b in payload or [] if isinstance(b, dict) and b.get("id")]


class TrackerSnapshot:
    """What the reader holds at one moment, as the views ask it."""

    # The ended sessions are known from the reader's start only.
    sessions_complete = False

    def __init__(self, open_beads, flagged, history=None, sessions=None, children=None):
        self._open = list(open_beads)
        self._flagged = list(flagged)
        self._history = dict(history or {})
        self._sessions = dict(sessions or {})
        self._children = dict(children or {})

    def open(self):
        return list(self._open)

    def flagged(self):
        return list(self._flagged)

    def with_key(self, key, ephemeral=False):
        """Every bead carrying ``key``, open or closed (within the history
        window), the freshest copy of each; with ``ephemeral``, the ended
        sessions too."""
        rows = [*self._open, *self._flagged, *self._history.values()]
        if ephemeral:
            rows += list(self._sessions.values())
        out = {}
        for bead in rows:
            if key in (bead.get("metadata") or {}):
                out.setdefault(bead["id"], bead)
        return list(out.values())

    def children(self, bead_id):
        return list(self._children.get(bead_id) or [])


class TrackerReader:
    """One thread, one ``bd`` at a time. ``add`` declares a view derived from
    each snapshot; the returned :class:`TrackerSource` is what the process
    lists among its pollers."""

    def __init__(self, read_model, bd_bin="bd", timeout=READ_TIMEOUT_SECONDS, open_seconds=30.0,
                 history_seconds=120.0, history_days=HISTORY_DAYS, slice_days=SLICE_DAYS,
                 read=read_beads_json, wall=None, mono=time.monotonic):
        self._read_model = read_model
        self._bd_bin = bd_bin
        self._timeout = timeout
        self._open_seconds = open_seconds
        self._history_seconds = history_seconds
        self._history_days = history_days
        self._slice_days = slice_days
        self._read_fn = read
        # The history window and its cursor follow the cockpit's clock (a
        # shifted one in an isolated run on a dated dataset).
        self._wall = wall or read_model.now
        self._mono = mono
        self._derived = []
        self._lock = threading.Lock()
        self._cycle_lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        self._pending = []
        self._last_forced_end = None
        self.results = {}
        self.calls = 0
        self._failures = {"open": 0, "history": 0}
        # Open reads.
        self._open = self._flagged = self._open_at = self._open_latency = None
        self._next_open = 0.0
        # History mirror.
        self._history, self._sessions, self._children = {}, {}, {}
        self._history_at = None
        self._slices = self._cursor = None
        self._next_history = 0.0

    # --- declaration and life ------------------------------------------------

    def add(self, name, derive, history=False):
        """``derive(snapshot)`` -> the value of source ``name``; ``history``:
        it needs the mirror, so it is published only once that is read."""
        self._derived.append((name, derive, history))
        return TrackerSource(self, name)

    def start(self):
        with self._lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, daemon=True, name="cockpit-tracker")
                self._thread.start()
        return self

    def request_stop(self):
        self._stop.set()
        self._wake.set()

    def join(self, timeout):
        if self._thread is None:
            return True
        self._thread.join(timeout=max(0.0, timeout))
        return not self._thread.is_alive()

    def poll_now(self, name, wait_seconds=POLL_NOW_WAIT_SECONDS):
        """A cycle of the open reads, asked and waited for; True when
        ``name`` was published from it. Never runs ``bd`` on the caller's
        thread while the reader runs: requests made together share one
        cycle, one made just after a cycle takes its result."""
        with self._lock:
            ended = self._last_forced_end
            if ended is not None and self._mono() - ended <= COALESCE_SECONDS:
                return bool(self.results.get(name))
            running = self._thread is not None and self._thread.is_alive()
            if running:
                done = threading.Event()
                self._pending.append(done)
                self._wake.set()
        if not running:
            self._cycle([None])
            return bool(self.results.get(name))
        return done.wait(wait_seconds) and bool(self.results.get(name))

    # --- the loop ------------------------------------------------------------

    def _run(self):
        while not self._stop.is_set():
            with self._lock:
                waiters, self._pending = self._pending, []
            self._cycle(waiters)
            delay = max(0.0, min(self._next_open, self._next_history) - self._mono())
            with self._lock:
                if self._pending:
                    continue
            self._wake.wait(delay)
            self._wake.clear()

    def _cycle(self, waiters):
        with self._cycle_lock:
            if self._slices is None:
                start = self._wall()
                self._cursor = start - OVERLAP_SECONDS
                count = max(1, math.ceil(self._history_days / self._slice_days))
                span = self._slice_days * 86400
                self._slices = [(start - (k + 1) * span, start - k * span) for k in range(count)]
            forced = bool(waiters)
            # While the history is first read, the open beads already read
            # wait for it (unless asked): the views that need it are not
            # published before, and a page waits for them.
            backfilling = bool(self._slices) and self._open is not None
            if forced or (self._mono() >= self._next_open and not backfilling):
                self._step_open()
            if not self._stop.is_set() and self._mono() >= self._next_history:
                self._step_history()
            # Asked before the history was ever whole: finish it, so that
            # the views it feeds are published by the cycle asked for.
            while forced and self._history_at is None and not self._stop.is_set():
                if not self._step_history():
                    break
            if forced:
                with self._lock:
                    self._last_forced_end = self._mono()
                for done in waiters:
                    if done is not None:
                        done.set()

    def _read(self, args):
        self.calls += 1
        return self._read_fn(args, bd_bin=self._bd_bin, timeout=self._timeout)

    def _step_open(self):
        started = self._mono()
        try:
            open_beads = _beads(self._read(["list"]))
            flagged = _beads(self._read(flagged_args()))
        except Exception:
            self._next_open = self._mono() + self._retry("open", self._open_seconds)
            for name, _, _ in self._derived:
                self._read_model.fail(name)
                self.results[name] = False
            return
        self._failures["open"] = 0
        self._open, self._flagged, self._open_at = open_beads, flagged, started
        self._open_latency = self._mono() - started
        self._next_open = self._mono() + self._open_seconds
        self._publish()

    def _step_history(self):
        started, wall_started = self._mono(), self._wall()
        try:
            if self._slices:
                after, before = self._slices[0]
                self._merge(self._read(["list", "--all", "--limit", "0", "--updated-after", _iso(after),
                                        "--updated-before", _iso(before)]))
                self._slices.pop(0)
                self._failures["history"] = 0
                # The next slice right after: the open reads still come
                # first when they are due.
                self._next_history = self._mono()
                return True
            since = _iso(self._cursor)
            changed = self._read(["list", "--all", "--limit", "0", "--updated-after", since])
            sessions = self._read(["list", "--all", "--limit", "0", "--include-ephemeral", "--updated-after", since,
                                   "--has-metadata-key", SESSION_AGENT_KEY])
            children = {
                bead["id"]: _beads(self._read(["children", bead["id"]]))
                for bead in self._open or []
                if MAP_LABEL in (bead.get("labels") or []) and bead.get("status") != "closed"
            }
        except Exception:
            self._next_history = self._mono() + self._retry("history", self._history_seconds)
            if self._history_at is None:
                for name, _, history in self._derived:
                    if history:
                        self._read_model.fail(name)
                        self.results[name] = False
            return False
        self._failures["history"] = 0
        self._merge(changed)
        self._sessions.update((b["id"], b) for b in _beads(sessions) if b.get("issue_type") == SESSION_TYPE)
        self._children = children
        self._cursor = wall_started - OVERLAP_SECONDS
        self._history_at = started
        self._next_history = self._mono() + self._history_seconds
        self._publish()
        return True

    def _retry(self, step, interval):
        """The wait before ``step`` is read again after one more failure."""
        self._failures[step] += 1
        return min(interval, RETRY_SECONDS, RETRY_FIRST_SECONDS * 2 ** (self._failures[step] - 1))

    def _merge(self, payload):
        for bead in _beads(payload):
            if bead.get("issue_type") != SESSION_TYPE:
                self._history[bead["id"]] = bead

    def _publish(self):
        if self._open is None:
            return
        snapshot = TrackerSnapshot(self._open, self._flagged, self._history, self._sessions, self._children)
        for name, derive, history in self._derived:
            if history and self._history_at is None:
                continue
            oldest = min(self._open_at, self._history_at) if history else self._open_at
            try:
                value = derive(snapshot)
            except Exception:
                self._read_model.fail(name)
                self.results[name] = False
                continue
            at = self._read_model.now() - (self._mono() - oldest)
            self._read_model.ingest(name, value, at=at, latency=self._open_latency)
            self.results[name] = True


class TrackerSource:
    """One view of the reader, as the process and the server see a poller:
    ``source``, ``poll_now``, and the reader's life."""

    def __init__(self, reader, name):
        self._reader = reader
        self._name = name

    @property
    def source(self):
        return self._name

    def start(self):
        self._reader.start()
        return self

    def request_stop(self):
        self._reader.request_stop()

    def join(self, timeout):
        return self._reader.join(timeout)

    def stop(self):
        self.request_stop()
        self.join(5)

    def poll_now(self):
        return self._reader.poll_now(self._name)
