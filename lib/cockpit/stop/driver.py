"""Clean stop / restart driver (T23, af-s5e3yo -- Spec af-oohx2x §"Arrêt
propre et redémarrage").

Clean stop = suspending the city (gc API, ``suspended=true``) -- never
``gc stop`` and never ``gc stop --force`` (spec: "gc stop complet reste au
runbook, jamais dans le cockpit"). Restart = ``gc resume``, rien d'autre.
Both go through ``gc_client``, a small seam (see
``tests/fixtures/cockpit/stop`` for the fake used in the seam test) so a
test can prove the driver never even has a way to call the forbidden
commands.

Seven states, same string constants the T18 heartbeat emitter's test
already pins down (``tests/cockpit-heartbeat-test.py``): ``en_marche``,
``arret_en_cours``, ``arretee_proprement`` (``CLEANLY_STOPPED``, imported
from :mod:`cockpit.heartbeat.emitter` rather than redefined, since that is
the exact value the heartbeat pauses on), ``redemarrage``,
``reprise_verifiee``, ``reprise_avec_ecarts``, ``arret_force``,
``arret_interrompu``.

``essai_reussi()`` (T24, af-j2mkpa -- spec "Bouton masqué tant que ... qu'un
essai réel déclenché par Benjamin n'a pas réussi") is the persisted trace
the stop button's render checks to switch from "essai" mode to a normal
button: it flips to ``True`` the first time a resume reaches
``reprise_verifiee`` and, like every other field here, is carried by
``state_store`` so a cockpit restart never forgets a trial already proven
successful.

State is persisted through ``state_store`` (same
:class:`~cockpit.notify.state_store.JsonFileStateStore` /
``InMemoryStateStore`` seam as the notify engine) after every transition,
so a cockpit restart mid-stop resumes the same state instead of forgetting
it happened (spec: "l'état persistant après un redémarrage du cockpit").
A restart discovered while ``arret_en_cours`` is itself meaningful: if the
first tick after that restart finds the city still not suspended, nothing
could have kept advancing the stop while the cockpit was down -- a PC
reboot cut the stop short, i.e. "Arrêt interrompu" (spec: "un redémarrage
du PC pendant l'arrêt donne « Arrêt interrompu » avec les écarts").

``tick()``/``request_stop()``/``force_stop()``/``resume()`` are the whole
public interface; process wiring (poller thread, the (hidden) button, the
"Ce qui t'attend" feed) is a later ticket's job, same precedent as T18/T17.
``view()`` (H, af-69qhlk) is what the page Usine draws: each work a stop waits
for, the point of resuming observed for it, what the comparison found -- all
read from the supervisor and the tickets, nothing from a timer.

A confirmation rests on a reading of the tickets begun after the last session
left (``read_at`` of the photo): the one before would say a lost ticket is
there. A resume waits ``resume_grace_seconds`` for the sessions to come back
before it calls one that did not a gap.
"""
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from cockpit.heartbeat.emitter import CLEANLY_STOPPED
from cockpit.stop.requests import build_ecarts_request, build_no_progress_request

PARIS = ZoneInfo("Europe/Paris")

EN_MARCHE = "en_marche"
ARRET_EN_COURS = "arret_en_cours"
ARRETEE_PROPREMENT = CLEANLY_STOPPED  # "arretee_proprement"
REDEMARRAGE = "redemarrage"
REPRISE_VERIFIEE = "reprise_verifiee"
REPRISE_AVEC_ECARTS = "reprise_avec_ecarts"
ARRET_FORCE = "arret_force"
ARRET_INTERROMPU = "arret_interrompu"

NO_PROGRESS_THRESHOLD_SECONDS = 30 * 60
# A stop may be asked again once the last one has resumed.
STOPPABLE_STATES = (EN_MARCHE, REPRISE_VERIFIEE, REPRISE_AVEC_ECARTS)
RESUMABLE_STATES = (ARRETEE_PROPREMENT, ARRET_FORCE, ARRET_INTERROMPU)


def _hhmm(epoch):
    if epoch is None:
        return "??:??"
    return datetime.fromtimestamp(epoch, tz=PARIS).strftime("%H:%M")


def _open_in_progress_beads(snapshot):
    return {
        bead_id: info
        for bead_id, info in (snapshot.get("beads") or {}).items()
        if info.get("status") in ("open", "in_progress")
    }


def _work_map(snapshot):
    """{bead_id: assignee} for every open/in_progress bead in a photo."""
    return {bead_id: info.get("assignee") for bead_id, info in _open_in_progress_beads(snapshot).items()}


def _titled(bead_id, snapshot):
    """What a person reads of a ticket of the photo: its title."""
    info = ((snapshot or {}).get("beads") or {}).get(bead_id) or {}
    return info.get("title") or bead_id


def _progress_token(status):
    """A stable fingerprint of "has anything moved" (spec: "commit, étape
    fermée, événement de session"): each session's last event time, plus
    how many steps have been closed since the stop was requested. Any
    change here resets the 30-min no-progress clock."""
    sessions = status.get("sessions") or []
    fingerprint = sorted([s.get("session_id"), s.get("last_event_at")] for s in sessions)
    # Lists: what the state file gives back compares equal.
    return [fingerprint, status.get("closed_steps_count", 0)]


def _lost_beads(before_snapshot, after_snapshot):
    """Bead ids the photo held as open/in_progress that have vanished
    entirely by the time the city reached "Arrêtée proprement" -- the "0
    perte" check. A bead that simply closed in the meantime (a session
    finishing its ticket normally, spec "point d'arrêt") is not "perdu":
    ``after_snapshot`` carries every bead regardless of status, so a
    present-but-closed id does not count as lost, only a fully absent one
    does."""
    before_ids = set(_open_in_progress_beads(before_snapshot or {}))
    after_ids = set((after_snapshot or {}).get("beads") or {})
    return sorted(before_ids - after_ids)


def _diff_sessions(before_snapshot, after_status):
    """Bead ids whose assignment does not match the photo -- used both for
    "Arrêt interrompu" écarts (photo vs. the status seen right after an
    unplanned restart) and reused by nothing else."""
    before_map = _work_map(before_snapshot or {})
    after_map = {
        s.get("bead_id"): s.get("assignee")
        for s in (after_status or {}).get("sessions", [])
        if s.get("bead_id")
    }
    return sorted(
        bead_id for bead_id, assignee in before_map.items() if after_map.get(bead_id) != assignee
    )


class StopDriver:
    def __init__(self, gc_client, snapshot_fn, clock, state_store, resume_grace_seconds=0):
        self._lock = threading.RLock()
        self._resume_grace_seconds = resume_grace_seconds
        self._gc = gc_client
        self._snapshot_fn = snapshot_fn
        self._clock = clock
        self._state_store = state_store

        saved = state_store.load()
        self._state = saved.get("state", EN_MARCHE)
        self._started_at = saved.get("started_at")
        self._stopped_at = saved.get("stopped_at")
        self._redemarrage_started_at = saved.get("redemarrage_started_at")
        self._resumed_at = saved.get("resumed_at")
        self._snapshot = saved.get("snapshot")
        self._last_progress_at = saved.get("last_progress_at")
        self._last_progress_token = saved.get("last_progress_token")
        self._no_progress_flagged = saved.get("no_progress_flagged", False)
        self._perdu = saved.get("perdu", [])
        self._ecarts = saved.get("ecarts", [])
        self._essai_reussi = saved.get("essai_reussi", False)
        self._held = saved.get("held", [])
        self._saved_sessions = saved.get("saved_sessions", [])
        self._suspended_seen = saved.get("suspended_seen", False)
        self._drained_at = saved.get("drained_at")
        # Only the very first tick after a process restart can discover an
        # "Arrêt interrompu" -- every later tick behaves exactly like an
        # uninterrupted arret_en_cours.
        self._pending_restart_check = self._state == ARRET_EN_COURS

    # -- persistence -------------------------------------------------------
    def _save(self):
        self._state_store.save(
            {
                "state": self._state,
                "started_at": self._started_at,
                "stopped_at": self._stopped_at,
                "redemarrage_started_at": self._redemarrage_started_at,
                "resumed_at": self._resumed_at,
                "snapshot": self._snapshot,
                "last_progress_at": self._last_progress_at,
                "last_progress_token": self._last_progress_token,
                "no_progress_flagged": self._no_progress_flagged,
                "perdu": self._perdu,
                "ecarts": self._ecarts,
                "essai_reussi": self._essai_reussi,
                "held": self._held,
                "saved_sessions": self._saved_sessions,
                "suspended_seen": self._suspended_seen,
                "drained_at": self._drained_at,
            }
        )

    # -- read side -----------------------------------------------------------
    def state(self):
        return self._state

    def bilan(self):
        """0 perte -> []; else the bead ids a clean stop lost."""
        return list(self._perdu)

    def ecarts(self):
        return list(self._ecarts)

    def essai_reussi(self):
        """spec: le bouton d'arrêt devient normal seulement quand une trace
        d'essai réel réussi (arrêt propre puis reprise vérifiée) existe."""
        return self._essai_reussi

    def label(self):
        if self._state == EN_MARCHE:
            return "En marche"
        if self._state == ARRET_EN_COURS:
            return "Arrêt en cours depuis %s" % _hhmm(self._started_at)
        if self._state == ARRETEE_PROPREMENT:
            return "Arrêtée proprement à %s" % _hhmm(self._stopped_at)
        if self._state == REDEMARRAGE:
            return "Redémarrage depuis %s" % _hhmm(self._redemarrage_started_at)
        if self._state == REPRISE_VERIFIEE:
            return "Reprise vérifiée à %s" % _hhmm(self._resumed_at)
        if self._state == REPRISE_AVEC_ECARTS:
            return "Reprise avec écarts"
        if self._state == ARRET_FORCE:
            perdu = ", ".join(_titled(bead_id, self._snapshot) for bead_id in self._perdu) or "rien"
            return "Arrêt forcé à %s (perdu : %s)" % (_hhmm(self._stopped_at), perdu)
        if self._state == ARRET_INTERROMPU:
            return "Arrêt interrompu"
        return self._state

    def source_label(self):
        """spec: pendant un arrêt demandé, les sources affichent « usine
        arrêtée par toi à HH:MM » au lieu d'une fausse alerte de panne
        (source illisible / usine muette)."""
        if self._state == ARRET_EN_COURS:
            return "usine arrêtée par toi à %s" % _hhmm(self._started_at)
        if self._state == ARRETEE_PROPREMENT:
            return "usine arrêtée par toi à %s" % _hhmm(self._stopped_at)
        return None

    def pending_requests(self):
        requests = []
        if self._state == ARRET_EN_COURS and self._no_progress_flagged:
            requests.append(build_no_progress_request(self._started_at, self._perdu_preview()))
        if self._state == REPRISE_AVEC_ECARTS:
            requests.append(build_ecarts_request(self._titles(self._ecarts), self._resumed_at))
        return requests

    def _titles(self, bead_ids):
        return [_titled(bead_id, self._snapshot) for bead_id in bead_ids]

    def _perdu_preview(self):
        """The title of each work still being saved: what a forced stop
        puts at risk."""
        return sorted(_titled(held.get("bead_id"), self._snapshot) for held in self._held
                      if held.get("session_id") not in self._saved_sessions)

    def force_offered(self):
        return self._state == ARRET_EN_COURS and self._no_progress_flagged

    def view(self):
        """What the page draws of the stop (H, af-69qhlk): only what was
        observed."""
        return {
            "state": self._state,
            "label": self.label(),
            "blocked": self.force_offered(),
            "started_at": self._started_at,
            "stopped_at": self._stopped_at,
            "resumed_at": self._resumed_at,
            "suspended_seen": self._suspended_seen,
            "work": [
                {"title": _titled(held.get("bead_id"), self._snapshot), "template": held.get("template"),
                 "saved": held.get("session_id") in self._saved_sessions}
                for held in self._held
            ],
            "lost": self._titles(self._perdu),
            "ecarts": self._titles(self._ecarts),
        }

    # -- actions ---------------------------------------------------------------
    def request_stop(self, now=None):
        with self._lock:
            self._request_stop(now)

    def _request_stop(self, now):
        if self._state not in STOPPABLE_STATES:
            raise ValueError("clean stop already requested (state=%s)" % self._state)
        now = self._clock.now() if now is None else now
        snapshot = self._snapshot_fn()
        initial_status = self._gc.status()
        # First: refused or unanswered, no stop was asked here.
        self._gc.suspend()
        self._snapshot = snapshot
        self._held = [
            {key: session.get(key) for key in ("session_id", "bead_id", "assignee", "template")}
            for session in initial_status.get("sessions") or []
        ]
        self._saved_sessions = []
        self._suspended_seen = False
        self._drained_at = None
        self._stopped_at = None
        self._resumed_at = None
        self._started_at = now
        self._last_progress_at = now
        self._last_progress_token = _progress_token(initial_status)
        self._no_progress_flagged = False
        self._perdu = []
        self._ecarts = []
        self._state = ARRET_EN_COURS
        self._save()

    def tick(self, now=None):
        with self._lock:
            now = self._clock.now() if now is None else now
            if self._state == ARRET_EN_COURS:
                self._tick_arret_en_cours(now)
            elif self._state == REDEMARRAGE:
                self._tick_redemarrage(now)
            return self._state

    def _tick_arret_en_cours(self, now):
        status = self._gc.status()

        if self._pending_restart_check:
            self._pending_restart_check = False
            if not status.get("suspended"):
                self._ecarts = _diff_sessions(self._snapshot, status)
                self._state = ARRET_INTERROMPU
                self._save()
                return

        live = {s.get("session_id") for s in status.get("sessions") or []}
        self._saved_sessions = [held.get("session_id") for held in self._held if held.get("session_id") not in live]
        if status.get("suspended"):
            self._suspended_seen = True
            if not status.get("sessions"):
                if self._drained_at is None:
                    self._drained_at = now
                current = self._snapshot_fn()
                if current.get("beads") is None or current.get("read_at", now) < self._drained_at:
                    # No conclusion on tickets read before the last session left.
                    self._save()
                    return
                self._perdu = _lost_beads(self._snapshot, current)
                self._stopped_at = now
                self._state = ARRETEE_PROPREMENT
                self._save()
                return
            # Suspended, but sessions are still draining their current
            # ticket (spec "point d'arrêt") -- progress is still tracked.

        token = _progress_token(status)
        if self._last_progress_token is None:
            self._last_progress_token = token
        if token != self._last_progress_token:
            self._last_progress_token = token
            self._last_progress_at = now
            self._no_progress_flagged = False
        elif now - self._last_progress_at >= NO_PROGRESS_THRESHOLD_SECONDS:
            # Never an automatic switch to forced stop -- only offering the
            # request (spec: "jamais de bascule automatique").
            self._no_progress_flagged = True
        self._save()

    def force_stop(self, now=None):
        with self._lock:
            self._force_stop(now)

    def _force_stop(self, now):
        if self._state != ARRET_EN_COURS:
            raise ValueError("force stop only applies while a stop is in progress")
        if not self._no_progress_flagged:
            raise ValueError("force stop is only offered after 30 min without progress")
        now = self._clock.now() if now is None else now
        status = self._gc.status()
        sessions = status.get("sessions") or []
        self._gc.force_stop_sessions([s.get("session_id") for s in sessions])
        # Sessions are stopped, their bead and work stay assigned (spec:
        # "arrête les sessions en gardant leur bead et leur travail
        # assigné") -- what's "perdu" is the work they were mid-ticket on.
        self._perdu = sorted({s.get("bead_id") for s in sessions if s.get("bead_id")})
        self._stopped_at = now
        self._state = ARRET_FORCE
        self._save()

    def resume(self, now=None):
        with self._lock:
            self._resume(now)

    def _resume(self, now):
        if self._state not in (ARRETEE_PROPREMENT, ARRET_FORCE, ARRET_INTERROMPU):
            raise ValueError("resume only applies after a stop (state=%s)" % self._state)
        now = self._clock.now() if now is None else now
        self._gc.resume()
        self._redemarrage_started_at = now
        self._ecarts = []
        self._state = REDEMARRAGE
        self._save()

    def _tick_redemarrage(self, now):
        status = self._gc.status()
        expected = _work_map(self._snapshot or {})
        current = {
            s.get("bead_id"): s.get("assignee")
            for s in status.get("sessions", [])
            if s.get("bead_id")
        }
        gaps = sorted(
            bead_id for bead_id, assignee in expected.items() if current.get(bead_id) != assignee
        )
        if gaps and now - (self._redemarrage_started_at or now) < self._resume_grace_seconds:
            return
        self._resumed_at = now
        if gaps:
            self._ecarts = gaps
            self._state = REPRISE_AVEC_ECARTS
        else:
            self._ecarts = []
            self._state = REPRISE_VERIFIEE
            self._essai_reussi = True
        self._save()
