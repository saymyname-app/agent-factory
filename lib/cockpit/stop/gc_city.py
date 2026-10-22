"""What the Clean stop driver may ask of the real gc supervisor
(af-mjfvwx, slice 7a) -- the read side only.

:class:`~cockpit.stop.driver.StopDriver` was built against a Python object
(``tests/fixtures/cockpit/stop/fake_gc_city.py``), never against gc's HTTP
API. This reader gives it the shape it expects from what gc 1.4.1 really
serves (checked on the live host, 2026-10-06):

- ``GET /v0/city/<city>/status``: ``suspended``;
- ``GET /v0/city/<city>/sessions``: one item per agent session, with
  ``id``, ``template``, ``session_name`` and ``last_active``;
- ``GET /v0/city/<city>/session/<id>/transcript?format=raw``: what the
  provider recorded of one session (``messages``), read for the trace of
  the sessions (cockpit.runs.trace; 1.5.0 on the live host, 2026-10-22).

Which ticket a session is on is NOT in that list: on the live host
(2026-10-07) a worker delivering a ticket had no ``active_bead`` there.
The ticket says it: an ``in_progress`` bead carries ``gc.session_id`` (and
``gc.session_name``). The first version of this reader trusted
``active_bead`` alone and showed « Aucun travail en vol » over a worker
at work; ``held_work`` is the join that was missing.

Suspending, resuming and force-stopping are NOT here. Benjamin, 2026-10-06:
« ok pour les deux temps » -- the write side comes with his real trial,
when no delivery is running; until then nothing in the cockpit can stop
the factory (spec .91), and a driver handed this reader refuses to try.
"""
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


class StopUnavailable(RuntimeError):
    """The cockpit cannot act on the city yet (spec .91)."""


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
        ``observer``: called with the sessions as listed and
        :meth:`transcript` at each reading of them (the trace of the
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
                    self._observer(sessions, self.transcript)
                except (OSError, ValueError, KeyError, TypeError):
                    pass
            return {
                "suspended": bool(status["suspended"]),
                "sessions": [
                    {
                        "session_id": item["id"],
                        "bead_id": held.get(item["id"]) or item["active_bead"],
                        "assignee": item.get("session_name") or item.get("template"),
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

    def suspend(self):
        raise StopUnavailable("l'arrêt depuis le cockpit attend l'essai réel de Benjamin")

    def resume(self):
        raise StopUnavailable("le redémarrage depuis le cockpit attend l'essai réel de Benjamin")

    def force_stop_sessions(self, session_ids):
        raise StopUnavailable("l'arrêt forcé n'est pas disponible : le geste gc correspondant n'est pas identifié")
