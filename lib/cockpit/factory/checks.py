"""The checks of the sections of the destination Usine (G1, af-wrxrmg; Spec
af-fgcw0d, user stories 63 and 65).

    checks = SectionChecks({"machine": read_machine, ...}, clock)
    checks.get("machine")      -> {"at": <epoch>, "value": ..., "stale": False}
    checks.recheck("machine")  -> the same, read again now

A section of the page shows what was read the last time it was checked, and
when: reading the page again never reads a section again, so two sections
never contradict each other's time, and « Revérifier » reads one section,
and only that one, however long ago the others were checked. A section never
checked is checked the first time it is asked for. A check older than
``validity_seconds`` is kept, and said ``stale``: the page greys it with its
age, it does not pass it off as current nor read it again in silence. What a
reader raises is not caught: a reader says itself what it could not read.
"""
import threading

VALIDITY_SECONDS = 300.0


class SectionChecks:
    def __init__(self, readers, clock, validity_seconds=VALIDITY_SECONDS):
        self._readers = dict(readers)
        self._clock = clock
        self._validity = validity_seconds
        self._checks = {}
        self._lock = threading.Lock()

    def get(self, name):
        with self._lock:
            check = self._checks.get(name)
        if check is None:
            return self.recheck(name)
        return dict(check, stale=self._clock() - check["at"] > self._validity)

    def recheck(self, name):
        value = self._readers[name]()
        check = {"at": self._clock(), "value": value}
        with self._lock:
            self._checks[name] = check
        return dict(check, stale=False)
