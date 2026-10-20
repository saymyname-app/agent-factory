"""The checks of the sections of the destination Usine (G1, af-wrxrmg; Spec
af-fgcw0d, user stories 63 and 65).

    checks = SectionChecks({"machine": read_machine, ...}, clock)
    checks.get("machine")      -> {"at": <epoch>, "value": ...}
    checks.recheck("machine")  -> the same, read again now

A section of the page shows what was read the last time it was checked, and
when: reading the page again does not read its section again, so two
sections never contradict each other's time, and « Revérifier » reads one
section, and only that one. A section never checked is checked the first
time it is asked for; a check older than ``max_age_seconds`` is done again
the next time it is asked for, so a page left open is not stuck on an old
reading. What a reader raises is not caught: a reader says itself what it
could not read.
"""
import threading

MAX_AGE_SECONDS = 300.0


class SectionChecks:
    def __init__(self, readers, clock, max_age_seconds=MAX_AGE_SECONDS):
        self._readers = dict(readers)
        self._clock = clock
        self._max_age = max_age_seconds
        self._checks = {}
        self._lock = threading.Lock()

    def get(self, name):
        with self._lock:
            check = self._checks.get(name)
        if check is None or self._clock() - check["at"] > self._max_age:
            return self.recheck(name)
        return check

    def recheck(self, name):
        value = self._readers[name]()
        check = {"at": self._clock(), "value": value}
        with self._lock:
            self._checks[name] = check
        return check
