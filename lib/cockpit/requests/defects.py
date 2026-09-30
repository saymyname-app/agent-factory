"""Producer-defect counter (spec af-oohx2x .14, .78: "un défaut du
producteur est compté"). Deliberately tiny and thread-safe: the requests
builder runs on the HTTP handler thread per request, so two overlapping
reads must not race the count.
"""
import threading


class DefectCounter:
    def __init__(self):
        self._lock = threading.Lock()
        self._count = 0
        self._reasons = []
        self._seen = set()

    def record(self, reason):
        with self._lock:
            self._count += 1
            self._reasons.append(reason)

    def record_once(self, key, reason):
        """Like :meth:`record`, but a repeat ``key`` (e.g. the same bead
        still missing the same fields on the next render) is not counted
        again — the page is re-rendered far more often than a producer
        actually writes a new defect. A ``key`` that disappears and comes
        back (spec .19: a request that reappears after resolution is a new
        one) is recorded again, because it is no longer "seen"."""
        with self._lock:
            if key in self._seen:
                return
            self._seen.add(key)
            self._count += 1
            self._reasons.append(reason)

    def forget_all_except(self, keys):
        """Drop any remembered key not in ``keys`` — called with the
        current render's live defect keys so a resolved/reappearing
        request is treated as new next time (spec .19)."""
        with self._lock:
            self._seen &= set(keys)

    @property
    def count(self):
        with self._lock:
            return self._count

    def reasons(self):
        with self._lock:
            return list(self._reasons)
