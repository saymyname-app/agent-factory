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


class ShiftedClock:
    """A clock that starts at ``start`` (epoch seconds) when it is made,
    then runs at the pace of the wall clock: the isolated cockpit shows a
    frozen state at the moment it was frozen, and what is open in it goes
    on lasting (C1, af-lzti7w; Spec af-fgcw0d, « Fixtures et horloge sont
    synthétiques »)."""

    def __init__(self, start):
        self._offset = start - time.time()

    def now(self):
        return time.time() + self._offset
