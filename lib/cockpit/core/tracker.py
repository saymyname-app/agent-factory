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

from cockpit.core.beads_source import NEEDS_BENJAMIN_KEY, READ_TIMEOUT_SECONDS, flagged_args, read_beads_json

HISTORY_DAYS = 28
# The beads still carrying gc.needs_benjamin whatever their status are read
# whole this often; in between, the open beads and the history keep them
# current (a bead that gains or loses the key is updated, so read again).
# Measured 19/11/2026: that read alone takes 22 s on factory-vm; once every
# 30 s it kept one bd running at all times and `escalation-door list`, which
# makes the same read, failed.
FLAGGED_SECONDS = 600.0
# The ended sessions (kept apart by the tracker, read with
# --include-ephemeral, a heavy read) are read on that same rhythm: they only
# name the agents of finished runs.
# While the history is first read, the open beads wait for it, but never
# longer than this: on 19/11/2026 the first reading took 11 min under a load
# of 20 and the tickets went stale meanwhile.
BACKFILL_OPEN_HOLD_SECONDS = 60.0
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

    def __init__(self, open_beads, flagged, history=None, sessions=None, children=None, flagged_read_last=False):
        self._open = list(open_beads)
        # On equal dates, the copy read last wins: the whole read of the
        # beads asking Benjamin, or the history, whichever came after.
        self._flagged_read_last = flagged_read_last
        self._flagged = list(flagged)
        self._history = dict(history or {})
        self._sessions = dict(sessions or {})
        self._children = dict(children or {})

    def open(self):
        return list(self._open)

    def flagged(self):
        """Every bead whose freshest copy still carries ``gc.needs_benjamin``."""
        return self.with_key(NEEDS_BENJAMIN_KEY)

    def with_key(self, key, ephemeral=False):
        """Every bead carrying ``key``, open or closed (within the history
        window), the freshest copy of each -- the open list's, else the
        latest written; with ``ephemeral``, the ended sessions too."""
        freshest = {bead["id"]: bead for bead in self._open}
        history = list(self._history.values())
        rows = [*history, *self._flagged] if self._flagged_read_last else [*self._flagged, *history]
        if ephemeral:
            rows += list(self._sessions.values())
        opened = set(freshest)
        for bead in rows:
            known = freshest.get(bead["id"])
            if known is None or (bead["id"] not in opened
                                 and (bead.get("updated_at") or "") >= (known.get("updated_at") or "")):
                freshest[bead["id"]] = bead
        return [bead for bead in freshest.values() if key in (bead.get("metadata") or {})]

    def children(self, bead_id):
        return list(self._children.get(bead_id) or [])


class TrackerReader:
    """One thread, one ``bd`` at a time. ``add`` declares a view derived from
    each snapshot; the returned :class:`TrackerSource` is what the process
    lists among its pollers."""

    def __init__(self, read_model, bd_bin="bd", timeout=READ_TIMEOUT_SECONDS, open_seconds=30.0,
                 history_seconds=120.0, history_days=HISTORY_DAYS, slice_days=SLICE_DAYS,
                 flagged_seconds=FLAGGED_SECONDS,
                 read=read_beads_json, wall=None, mono=time.monotonic):
        self._read_model = read_model
        self._bd_bin = bd_bin
        self._timeout = timeout
        self._open_seconds = open_seconds
        self._history_seconds = history_seconds
        self._flagged_seconds = flagged_seconds
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
        self._failures = {"open": 0, "flagged": 0, "history": 0}
        # What changed since the views were last derived: a view whose beads
        # are the same is not derived again, only dated anew.
        self._open_version = self._history_version = 0
        self._derived_from = {}
        self._dirty = False
        # Called once, the first time the open beads are published.
        self.on_first_open = None
        # Open reads.
        self._open = self._open_at = self._open_latency = None
        self._flagged = self._flagged_at = None
        self._next_open = self._next_flagged = 0.0
        # History mirror.
        self._history, self._sessions, self._children = {}, {}, {}
        self._history_at = None
        self._slices = self._cursor = self._sessions_cursor = None
        self._next_sessions = 0.0
        self._next_history = 0.0

    # --- declaration and life ------------------------------------------------

    def add(self, name, derive, history=False, refresh_seconds=None):
        """``derive(snapshot)`` -> the value of source ``name``; ``history``:
        it needs the mirror, so it is published only once that is read.
        A view is derived again when its beads changed, or, with
        ``refresh_seconds``, when its last derivation is that old (Projets
        also reads the clones of the projects)."""
        self._derived.append((name, derive, history, refresh_seconds))
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
                self._cursor = self._sessions_cursor = start - OVERLAP_SECONDS
                count = max(1, math.ceil(self._history_days / self._slice_days))
                span = self._slice_days * 86400
                self._slices = [(start - (k + 1) * span, start - k * span) for k in range(count)]
            forced = bool(waiters)
            # While the history is first read, the open beads already read
            # wait for it (unless asked): the views that need it are not
            # published before, and a page waits for them.
            backfilling = (bool(self._slices) and self._open is not None
                           and self._mono() - self._open_at < BACKFILL_OPEN_HOLD_SECONDS)
            if forced or (self._mono() >= self._next_open and not backfilling):
                self._step_open()
            if not self._stop.is_set() and self._open is not None and (
                    self._flagged is None or self._mono() >= self._next_flagged):
                self._step_flagged()
            if not self._stop.is_set() and self._mono() >= self._next_history:
                self._step_history()
            # Asked before the history was ever whole: finish it, so that
            # the views it feeds are published by the cycle asked for.
            while forced and self._history_at is None and not self._stop.is_set():
                if not self._step_history():
                    break
            # Once per cycle, whatever was read in it.
            if self._dirty:
                self._dirty = False
                self._publish()
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
        except Exception:
            self._next_open = self._mono() + self._retry("open", self._open_seconds)
            for name, *_ in self._derived:
                self._read_model.fail(name)
                self.results[name] = False
            return
        self._failures["open"] = 0
        if open_beads != self._open:
            self._open_version += 1
        self._open, self._open_at = open_beads, started
        self._open_latency = self._mono() - started
        self._next_open = self._mono() + self._open_seconds
        self._dirty = True

    def _step_flagged(self):
        started = self._mono()
        try:
            flagged = _beads(self._read(flagged_args()))
        except Exception:
            self._next_flagged = self._mono() + self._retry("flagged", self._flagged_seconds)
            if self._flagged is None:
                for name, *_ in self._derived:
                    self._read_model.fail(name)
                    self.results[name] = False
            return
        self._failures["flagged"] = 0
        if flagged != self._flagged:
            self._open_version += 1
        self._flagged, self._flagged_at = flagged, started
        # Until the history is whole it cannot keep this set current: read
        # it whole on the rhythm of the open beads meanwhile (19/11/2026:
        # a first reading of 14 min left the tickets « périmé »).
        self._next_flagged = self._mono() + (
            self._flagged_seconds if self._history_at is not None else self._open_seconds)
        self._dirty = True

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
            sessions = None
            if self._mono() >= self._next_sessions:
                sessions = self._read(["list", "--all", "--limit", "0", "--include-ephemeral", "--updated-after",
                                       _iso(self._sessions_cursor), "--has-metadata-key", SESSION_AGENT_KEY])
            children = {
                bead["id"]: _beads(self._read(["children", bead["id"]]))
                for bead in self._open or []
                if MAP_LABEL in (bead.get("labels") or []) and bead.get("status") != "closed"
            }
        except Exception:
            self._next_history = self._mono() + self._retry("history", self._history_seconds)
            if self._history_at is None:
                for name, _, history, _ in self._derived:
                    if history:
                        self._read_model.fail(name)
                        self.results[name] = False
            return False
        self._failures["history"] = 0
        self._merge(changed)
        before = dict(self._sessions)
        if sessions is not None:
            self._sessions.update((b["id"], b) for b in _beads(sessions) if b.get("issue_type") == SESSION_TYPE)
            self._sessions_cursor = wall_started - OVERLAP_SECONDS
            self._next_sessions = self._mono() + self._flagged_seconds
        if self._sessions != before or children != self._children:
            self._history_version += 1
        self._children = children
        self._cursor = wall_started - OVERLAP_SECONDS
        if self._history_at is None and self._flagged_at is not None:
            # The history now keeps that set current: back to its own rhythm.
            self._next_flagged = self._flagged_at + self._flagged_seconds
        self._history_at = started
        self._next_history = self._mono() + self._history_seconds
        self._dirty = True
        return True

    def _retry(self, step, interval):
        """The wait before ``step`` is read again after one more failure."""
        self._failures[step] += 1
        return min(interval, RETRY_SECONDS, RETRY_FIRST_SECONDS * 2 ** (self._failures[step] - 1))

    def _merge(self, payload):
        for bead in _beads(payload):
            if bead.get("issue_type") != SESSION_TYPE and self._history.get(bead["id"]) != bead:
                self._history[bead["id"]] = bead
                self._history_version += 1

    def _publish(self):
        if self._open is None or self._flagged is None:
            return
        # What is known of the beads still asking Benjamin: as of their last
        # whole read, or of the last read of the history since, which
        # brings every bead written after it.
        flagged_known = max(self._flagged_at, self._history_at) if self._history_at is not None else self._flagged_at
        snapshot = None
        for name, derive, history, refresh_seconds in self._derived:
            if history and self._history_at is None:
                continue
            oldest = min(self._open_at, flagged_known, *((self._history_at,) if history else ()))
            # The open beads, and the history (it keeps the beads asking
            # Benjamin current between their whole reads).
            inputs = (self._open_version, self._history_version)
            last = self._derived_from.get(name)
            if (last is not None and last[0] == inputs
                    and (refresh_seconds is None or self._mono() - last[1] < refresh_seconds)):
                value = last[2]
            else:
                if snapshot is None:
                    snapshot = TrackerSnapshot(
                        self._open, self._flagged, self._history, self._sessions, self._children,
                        flagged_read_last=self._history_at is None or self._flagged_at > self._history_at)
                try:
                    value = derive(snapshot)
                except Exception:
                    self._derived_from.pop(name, None)
                    self._read_model.fail(name)
                    self.results[name] = False
                    continue
                self._derived_from[name] = (inputs, self._mono(), value)
            at = self._read_model.now() - (self._mono() - oldest)
            self._read_model.ingest(name, value, at=at, latency=self._open_latency)
            self.results[name] = True
        first, self.on_first_open = self.on_first_open, None
        if first is not None:
            first()


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
