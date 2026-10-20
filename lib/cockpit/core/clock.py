"""The cockpit's only source of "now" — real in production, fake in tests.

Every other cockpit-core module takes a clock object (anything with a
``now()`` method returning epoch seconds) instead of calling ``time.time()``
directly, so a test can move time forward deterministically (af-0b6ffa,
Testing Decisions: "fresh -> stale -> unknown au fil de l'horloge").
"""
import time


class SystemClock:
    """The real wall clock."""

    def now(self):
        return time.time()


class StartedClock:
    """A clock that starts at a given instant and runs from there at the
    pace of the wall clock: the fixed time of a synthetic dataset
    (``generated_at``) is the cockpit's « now » when it starts, and the
    freshness of its sources still moves with time."""

    def __init__(self, start):
        self._offset = start - time.time()

    def now(self):
        return time.time() + self._offset
