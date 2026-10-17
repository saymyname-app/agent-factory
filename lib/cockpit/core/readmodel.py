"""The cockpit's one held-up-to-date copy (spec af-oohx2x, "Modèle de lecture").

The page never reads a source directly; it reads this copy. Every value
carries its own value, read time, source and Freshness. A gc response
carrying ``partial: true`` is ingested (so a stale attempt is recorded) but
never promoted to a complete, fresh reading (spec .14) — see
:mod:`cockpit.core.freshness`.
"""
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from cockpit.core.freshness import FRESH, STALE, UNKNOWN, VALIDITY_WINDOWS_SECONDS, classify

PARIS = ZoneInfo("Europe/Paris")

_STATE_LABELS = {STALE: "périmé", UNKNOWN: "inconnu"}


class _Source:
    __slots__ = ("display_name", "value", "read_at", "last_attempt_at", "registered_at", "failed_at")

    def __init__(self, display_name, registered_at=None):
        self.display_name = display_name
        self.registered_at = registered_at
        self.value = None
        self.read_at = None
        self.last_attempt_at = None
        self.failed_at = None


class ReadModel:
    """Thread-safe: poller threads ingest, the HTTP handler thread reads."""

    def __init__(self, clock, validity_seconds=None):
        self._clock = clock
        self._lock = threading.Lock()
        self._sources = {}
        self._validity_seconds = (
            dict(VALIDITY_WINDOWS_SECONDS) if validity_seconds is None else dict(validity_seconds)
        )

    def now(self):
        """The cockpit's clock, exposed so a caller building on the model
        (T12, af-is5e97: the requests section) never reaches for a second
        clock of its own."""
        return self._clock.now()

    def register(self, name, display_name=None):
        with self._lock:
            if name not in self._sources:
                self._sources[name] = _Source(display_name or name, registered_at=self._clock.now())

    def ingest(self, name, value, at=None, complete=True):
        """Record a read. ``complete=False`` marks a gc ``partial: true``."""
        now = self._clock.now() if at is None else at
        with self._lock:
            source = self._sources.setdefault(name, _Source(name, registered_at=now))
            source.last_attempt_at = now
            if complete:
                source.value = value
                source.read_at = now
            source.failed_at = None

    def fail(self, name, at=None):
        """Record a read that failed: the source did not answer, or answered
        nothing a reading can be made of. The value already held is kept."""
        now = self._clock.now() if at is None else at
        with self._lock:
            source = self._sources.setdefault(name, _Source(name, registered_at=now))
            source.last_attempt_at = now
            source.failed_at = now

    def snapshot(self, now=None):
        """{"gc": {"value": ..., "read_at": ..., "freshness": "fresh"}, ...}"""
        now = self._clock.now() if now is None else now
        out = {}
        with self._lock:
            items = list(self._sources.items())
        for name, source in items:
            try:
                validity_seconds = self._validity_seconds[name]
            except KeyError:
                raise ValueError(
                    "cockpit: no Validity window declared for source %r — "
                    "pass one in validity_seconds instead of guessing" % (name,)
                )
            out[name] = {
                "display_name": source.display_name,
                "value": source.value,
                "read_at": source.read_at,
                # Since when the cockpit has been trying to read it: dates a
                # source that never answered (spec .17).
                "registered_at": source.registered_at,
                # When its last read failed, None once a read succeeds: a
                # source never read whose read failed is unreadable, one
                # whose read has not ended yet is still being read.
                "failed_at": source.failed_at,
                "freshness": classify(source.read_at, now, validity_seconds),
            }
        return out

    def all_fresh(self, now=None):
        snap = self.snapshot(now)
        return bool(snap) and all(
            row["freshness"] == FRESH for row in snap.values()
        )

    def stale_or_unknown(self, now=None):
        """Names (sorted, deterministic) not currently fresh."""
        snap = self.snapshot(now)
        return sorted(
            name for name, row in snap.items() if row["freshness"] != FRESH
        )

    def headline(self, now=None):
        """"Tout est à jour à HH:MM (Paris)", or the sources that are not."""
        now = self._clock.now() if now is None else now
        snap = self.snapshot(now)
        stale = [
            name
            for name in sorted(snap)
            if snap[name]["freshness"] != FRESH
        ]
        when = datetime.fromtimestamp(now, tz=PARIS).strftime("%H:%M")
        if not stale:
            return "Tout est à jour à %s (Paris)" % when
        names = ", ".join(
            "%s (%s)" % (snap[name]["display_name"], _STATE_LABELS[snap[name]["freshness"]])
            for name in stale
        )
        return "%d source%s pas à jour : %s" % (len(stale), "s" if len(stale) > 1 else "", names)
