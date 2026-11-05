"""What the Clean stop driver may ask of the real gc supervisor
(af-mjfvwx, slice 7a; its writes, H af-69qhlk).

:class:`~cockpit.stop.driver.StopDriver` was built against a Python object
(``tests/fixtures/cockpit/stop/fake_gc_city.py``), never against gc's HTTP
API. This reader gives it the shape it expects from what gc 1.4.1 really
serves (checked on the live host, 2026-10-06):

- ``GET /v0/city/<city>/status``: ``suspended``;
- ``GET /v0/city/<city>/sessions``: one item per agent session, with
  ``id``, ``template``, ``session_name`` and ``last_active``;
- for the trace of the sessions (cockpit.runs.trace; 1.5.0 on the live
  host, 2026-10-22): ``GET /v0/city/<city>/session/<id>``, one session as
  the list gives it, kept once it stopped and is no longer listed;
  ``…/session/<id>/transcript?format=raw``, what its provider recorded
  (``messages``), kept likewise; ``GET
  /v0/city/<city>/events?type=session.woke`` (and ``session.stopped``),
  when the supervisor woke and stopped each session, and
  ``execution.step_started``, each bead a session took (its ``subject``)
  -- the only record of the bead a session worked once it stopped: the
  session it keeps then says no ``active_bead`` (2026-10-28), and the
  bead keeps one ``gc.session_name`` of all the sessions that took it --,
  the latest first,
  ``limit`` at a time, the next page at ``cursor=<next_cursor>``. Each
  page further back costs more (under load on the live host, 2026-10-22:
  0.9 s, 1.5 s, then 3 s for pages of 50, and 8 s for ``since=10m``), so
  a first reading takes the latest page only and ``since`` is not used.

Which ticket a session is on is NOT in that list: on the live host
(2026-10-07) a worker delivering a ticket had no ``active_bead`` there.
The ticket says it: an ``in_progress`` bead carries ``gc.session_id`` (and
``gc.session_name``). The first version of this reader trusted
``active_bead`` alone and showed « Aucun travail en vol » over a worker
at work; ``held_work`` is the join that was missing.

Its writes are the three gc 1.5.0 publishes (``/openapi.json`` of the live
host, read 2026-10-31), each carrying the anti-CSRF header ``X-GC-Request``
it requires: ``PATCH /v0/city/<city>`` ``{"suspended": true|false}`` suspends
or resumes the city, ``POST /v0/city/<city>/session/<id>/stop`` stops one
session. There is no other: no complete stop, no power-off. The real trial
is Benjamin's ADMIN window, after Delivered (Spec af-fgcw0d, Testing
Decision 4): until then no write of this module met the installed supervisor.
"""
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


# What the trace reads of the log of the supervisor: the moments it woke
# and stopped a session, and each step a session took -- on a first reading,
# the latest page of each; then back to the last one read, at most that many
# pages.
STEP_STARTED = "execution.step_started"
SESSION_EVENT_TYPES = ("session.woke", "session.stopped", STEP_STARTED)
SESSION_EVENTS_PAGE = 50
SESSION_EVENTS_PAGES = 10


class StopUncertain(RuntimeError):
    """A write got no answer: it may have been applied. The source says."""


def _get_json(base_url, path, timeout):
    req = urllib.request.Request(base_url + path, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if not resp.headers.get("Content-Type", "").startswith("application/json"):
            raise ValueError("gc answered %r on %s, not JSON" % (resp.headers.get("Content-Type"), path))
        return json.loads(resp.read().decode("utf-8"))


def _epoch(iso_value):
    if not iso_value or not isinstance(iso_value, str):
        return None
    text = iso_value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


class GcCityReader:
    def __init__(self, base_url, city=None, timeout=10, held_work=None, observer=None):
        """``held_work``: a callable returning ``{session_id: bead_id}``
        from the tickets as last read, or ``None`` while they are not
        read -- the work in flight is then unknown, never empty.
        ``observer``: called with the sessions as listed and this reader
        (its :meth:`session_events`, :meth:`session` and
        :meth:`transcript`) at each reading of them (the trace of the
        sessions); what it raises does not fail the reading."""
        self._held_work = held_work
        self._observer = observer
        self._base_url = base_url.rstrip("/")
        self._city = city or None
        self._timeout = timeout

    def _city_path(self, suffix):
        if not self._city:
            cities = _get_json(self._base_url, "/v0/cities", self._timeout)["items"]
            running = [c for c in cities if c.get("running")]
            self._city = (running or cities)[0]["name"]
        return "/v0/city/%s/%s" % (urllib.parse.quote(self._city, safe=""), suffix)

    def status(self):
        """``{"suspended", "sessions": [...], "closed_steps_count",
        "agents": [...]}``, the driver's shape and who each session is. A session is listed only while it holds a ticket:
        that is the work a stop waits for. Raises when gc cannot be read --
        the caller keeps the last value and lets it age."""
        held = {}
        if self._held_work is not None:
            held = self._held_work()
            if held is None:
                raise ValueError("tickets non lus : travail en vol inconnu")
        try:
            status = _get_json(self._base_url, self._city_path("status"), self._timeout)
            sessions = _get_json(self._base_url, self._city_path("sessions"), self._timeout)["items"]
            if self._observer is not None:
                try:
                    self._observer(sessions, self)
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            return {
                "suspended": bool(status["suspended"]),
                "sessions": [
                    {
                        "session_id": item["id"],
                        "bead_id": held.get(item["id"]) or item["active_bead"],
                        "assignee": item.get("session_name") or item.get("template"),
                        "template": item.get("template"),
                        "last_event_at": _epoch(item.get("last_active")),
                    }
                    for item in sessions
                    if item.get("running") and (held.get(item["id"]) or item.get("active_bead"))
                ],
                # gc exposes no count of closed steps; progress is read from
                # each session's last sign of life alone.
                "closed_steps_count": 0,
                # Who each session is, running or not: the lanes of Runs
                # are the agents (cockpit.runs.workflows).
                "agents": [
                    {key: item.get(key) for key in ("name", "session_name", "agent_name", "template", "provider")}
                    for item in sessions if isinstance(item, dict)
                ],
            }
        except (urllib.error.URLError, OSError, KeyError, IndexError, TypeError) as exc:
            raise ValueError("gc illisible : %s" % exc)

    def session_events(self, after=None):
        """The moments the supervisor woke and stopped a session, or a
        session took a step, after its event ``after`` (a ``seq``; None, the
        latest SESSION_EVENTS_PAGE of each), the oldest first: each
        ``{"seq", "type", "ts", "session_id"}``, and the ``bead`` taken for
        a step."""
        found = {}
        for kind in SESSION_EVENT_TYPES:
            query = {"type": kind, "limit": str(SESSION_EVENTS_PAGE)}
            for _ in range(SESSION_EVENTS_PAGES if after is not None else 1):
                answer = _get_json(self._base_url, self._city_path("events?" + urllib.parse.urlencode(query)),
                                   self._timeout)
                items = [item for item in (answer.get("items") or []) if isinstance(item, dict)
                         and isinstance(item.get("seq"), int) and item.get("type") == kind]
                fresh = [item for item in items if after is None or item["seq"] > after]
                for item in fresh:
                    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
                    session_id = item.get("session_id") or payload.get("session_id")
                    if session_id and isinstance(item.get("ts"), str):
                        found[item["seq"]] = {"seq": item["seq"], "type": kind, "ts": item["ts"],
                                              "session_id": str(session_id)}
                        if kind == STEP_STARTED:
                            found[item["seq"]]["bead"] = item.get("subject") or None
                if len(fresh) < len(items) or not items or not answer.get("next_cursor"):
                    break
                query["cursor"] = answer["next_cursor"]
        return [found[seq] for seq in sorted(found)]

    def session(self, session_id):
        """The session ``session_id`` as the supervisor keeps it; None when
        it keeps nothing of it."""
        path = self._city_path("session/%s" % urllib.parse.quote(str(session_id), safe=""))
        try:
            answer = _get_json(self._base_url, path, self._timeout)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise OSError("session %s illisible : %s" % (session_id, exc))
        return answer if isinstance(answer, dict) else None

    def transcript(self, session_id):
        """The records the provider wrote of the session ``session_id``, as
        the supervisor keeps them; None when it keeps none."""
        path = self._city_path("session/%s/transcript?format=raw" % urllib.parse.quote(str(session_id), safe=""))
        try:
            answer = _get_json(self._base_url, path, self._timeout)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise OSError("transcript de %s illisible : %s" % (session_id, exc))
        messages = answer.get("messages") if isinstance(answer, dict) else None
        return messages if isinstance(messages, list) else None

    def _write(self, method, path, body=None):
        """One write. Refused: ValueError with what gc said. No answer:
        StopUncertain."""
        data = b"" if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self._base_url + path, data=data, method=method,
                                     headers={"Content-Type": "application/json", "X-GC-Request": "cockpit"})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout):
                return
        except urllib.error.HTTPError as exc:
            raise ValueError("le superviseur a refusé la commande (%s)" % exc.code)
        except OSError as exc:
            raise StopUncertain("le superviseur n'a pas répondu : %s" % exc)

    def suspend(self):
        self._write("PATCH", self._city_path("").rstrip("/"), {"suspended": True})

    def resume(self):
        self._write("PATCH", self._city_path("").rstrip("/"), {"suspended": False})

    def force_stop_sessions(self, session_ids):
        for session_id in session_ids:
            self._write("POST", self._city_path("session/%s/stop" % urllib.parse.quote(str(session_id), safe="")))
