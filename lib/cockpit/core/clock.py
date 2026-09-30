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
