"""A fake gc city client for the Clean stop driver's seam test (T23,
af-s5e3yo -- Spec af-oohx2x Testing Decisions: "Sur un faux gc...").

Only exposes the four gestures the driver is allowed to use: ``status``
(GET), ``suspend`` (the PATCH ``suspended=true``), ``resume`` (``gc
resume``), ``force_stop_sessions`` (stops sessions, keeps their bead/work
assigned). ``stop`` and ``stop_force`` exist purely so a test can prove the
driver never calls them -- calling either raises, and the AC4 test asserts
``forbidden_calls`` stays empty for the whole scenario instead of just
happening not to fail.
"""


class FakeGcCity:
    def __init__(self, sessions=None, suspended=False):
        self.calls = []
        self.suspended = suspended
        self.sessions = sessions if sessions is not None else []
        self.beads = {
            s["bead_id"]: {"status": "in_progress", "assignee": s.get("assignee")}
            for s in self.sessions
            if s.get("bead_id")
        }
        self.closed_steps_count = 0
        self.forbidden_calls = []

    # -- allowed gestures ---------------------------------------------------
    def status(self):
        self.calls.append("status")
        return {
            "suspended": self.suspended,
            "sessions": [dict(s) for s in self.sessions],
            "closed_steps_count": self.closed_steps_count,
        }

    def suspend(self):
        self.calls.append("suspend")
        self.suspended = True

    def resume(self):
        self.calls.append("resume")
        self.suspended = False

    def force_stop_sessions(self, session_ids):
        self.calls.append("force_stop_sessions")
        ids = set(session_ids or [])
        self.sessions = [s for s in self.sessions if s.get("session_id") not in ids]

    # -- forbidden gestures ---------------------------------------------------
    def stop(self, *a, **k):
        self.forbidden_calls.append("stop")
        raise AssertionError("StopDriver must never call gc stop")

    def stop_force(self, *a, **k):
        self.forbidden_calls.append("stop_force")
        raise AssertionError("StopDriver must never call gc stop --force")

    # -- test helpers -----------------------------------------------------------
    def end_session(self, session_id):
        """A session that finishes its current ticket normally (spec
        "point d'arrêt"): the session goes away, its bead is closed --
        never "perdu"."""
        for s in self.sessions:
            if s.get("session_id") == session_id and s.get("bead_id") in self.beads:
                self.beads[s["bead_id"]]["status"] = "closed"
        self.sessions = [s for s in self.sessions if s.get("session_id") != session_id]

    def lose_bead(self, bead_id):
        """Simulated data loss: the bead disappears entirely, unlike a
        normal completion which merely closes it."""
        self.beads.pop(bead_id, None)

    def touch_session(self, session_id, last_event_at):
        for s in self.sessions:
            if s.get("session_id") == session_id:
                s["last_event_at"] = last_event_at

    def reassign(self, bead_id, assignee):
        for s in self.sessions:
            if s.get("bead_id") == bead_id:
                s["assignee"] = assignee
        if bead_id in self.beads:
            self.beads[bead_id]["assignee"] = assignee
