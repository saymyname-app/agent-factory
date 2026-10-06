"""The running half of notifications and of the heartbeat (spec af-oohx2x
§"Notifications", §"Heartbeat et usine muette"; af-mjfvwx).

T17 and T18 built :class:`~cockpit.notify.engine.NotificationEngine` and
:class:`~cockpit.heartbeat.emitter.HeartbeatEmitter` with ``tick()`` as
their whole interface and left "a poller thread ticks it" to a later
ticket. This is that caller: :class:`Ticker` is the thread,
:class:`NotifyService` and :class:`HeartbeatService` what it ticks and
what the server asks for health lines, the journal des envois and the
test notification.

Nothing is ever sent, and nothing is pinged, without the out-of-repo
secret file: an absent or invalid one is a health line (spec .98), never
an attempt.
"""
import threading

from cockpit.actions.registry import ActionError
from cockpit.health.engine import BAD, WARN
from cockpit.heartbeat.emitter import HeartbeatEmitter, read_url_from_file
from cockpit.notify.engine import NotificationEngine
from cockpit.notify.pushover import PUSHOVER_URL, PushoverAdapter
from cockpit.notify.secrets import read_secrets_from_file
from cockpit.notify.state_store import JsonFileStateStore

NOTIFY_INACTIVE_TEXT = "Notifications iPhone inactives : le fichier de secrets est absent ou invalide."
NOTIFY_DOWN_TEXT = "Canal de notification en panne depuis plus de 15 min."
HEARTBEAT_INACTIVE_TEXT = "Alerte « Usine muette » inactive : son adresse n'est pas configurée."
HEARTBEAT_FAILED_TEXT = "Alerte « Usine muette » : le signal de vie n'a pas pu être envoyé."
TEST_SENT_TEXT = "Notification de test envoyée"
TEST_REFUSED_TEXT = "notification de test non envoyée : le canal a refusé"
TEST_INACTIVE_TEXT = "notifications inactives : le fichier de secrets est absent ou invalide"

# Journal des envois kept in memory: enough to prove the channel works
# (spec .60) without growing for the life of the process.
JOURNAL_KEPT = 200


class Ticker:
    """Calls ``fn`` every ``interval_seconds`` on a daemon thread; an
    exception in one call never ends the thread (af-0b6ffa AC4: one failing
    part never takes the cockpit down)."""

    def __init__(self, fn, interval_seconds):
        self._fn = fn
        self._interval = interval_seconds
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        while not self._stop.is_set():
            try:
                self._fn()
            except Exception:
                pass
            self._stop.wait(self._interval)


class NotifyService:
    def __init__(self, secrets_file, state_file, clock, public_url, requests_fn, pushover_url=PUSHOVER_URL):
        """``requests_fn``: returns ``(requests, complete)`` -- the current
        Operator Requests and whether that list is whole. ``public_url``:
        the address a push links back to."""
        self._secrets_loader = lambda: read_secrets_from_file(secrets_file)
        self._requests_fn = requests_fn
        self._journal = []
        base = public_url.rstrip("/")
        self._engine = NotificationEngine(
            PushoverAdapter(self._secrets_loader, url=pushover_url),
            JsonFileStateStore(state_file),
            clock,
            lambda request_id: "%s/#d-%s" % (base, request_id) if request_id else base + "/",
            journal=self._journal,
        )
        self._lock = threading.Lock()

    def configured(self):
        return self._secrets_loader() is not None

    def tick(self):
        """One pass of the policy. Skipped without secrets, and while the
        request list is not whole: a request merely unreadable must never
        be taken for a resolved one (it would send "Urgent résolue")."""
        with self._lock:
            if not self.configured():
                return "inactive"
            requests, complete = self._requests_fn()
            if not complete:
                return "requests-unknown"
            self._engine.tick(requests)
            del self._journal[:-JOURNAL_KEPT]
            return "ticked"

    def send_test(self):
        with self._lock:
            if not self.configured():
                raise ActionError(TEST_INACTIVE_TEXT)
            if not self._engine.send_test():
                raise ActionError(TEST_REFUSED_TEXT)
        return {"ok": True, "display": TEST_SENT_TEXT}

    def journal_entries(self):
        """Newest first."""
        with self._lock:
            return list(reversed(self._journal))

    def undelivered(self):
        with self._lock:
            return self._engine.undelivered()

    def health_lines(self):
        if not self.configured():
            return [{"kind": WARN, "text": NOTIFY_INACTIVE_TEXT}]
        with self._lock:
            down = bool(self._engine.health_issues())
        return [{"kind": BAD, "text": NOTIFY_DOWN_TEXT}] if down else []


class _MainSources:
    """What "ses sources principales" means for the heartbeat (spec
    "Heartbeat et usine muette"): the supervisor and the tickets -- not
    every value the page shows."""

    def __init__(self, read_model, names):
        self._read_model = read_model
        self._names = names

    def all_fresh(self, now=None):
        snapshot = self._read_model.snapshot(now)
        return all(name in snapshot and snapshot[name]["freshness"] == "fresh" for name in self._names)


class HeartbeatService:
    def __init__(
        self, read_model, clock, url_file, interval_seconds, main_sources=("gc", "beads"),
        state_provider=lambda: None,
    ):
        """``state_provider``: the Clean stop driver's state -- the emitter
        pauses only while it says the factory was stopped cleanly from the
        cockpit, never for a Windows shutdown (spec .88)."""
        self._url_loader = lambda: read_url_from_file(url_file)
        self._emitter = HeartbeatEmitter(
            _MainSources(read_model, main_sources),
            clock,
            self._url_loader,
            state_provider=state_provider,
            interval_seconds=interval_seconds,
        )

    def tick(self):
        return self._emitter.tick()

    def health_lines(self):
        if not self._url_loader():
            return [{"kind": WARN, "text": HEARTBEAT_INACTIVE_TEXT}]
        # The emitter keeps a failed ping as its issue until one succeeds.
        if self._emitter.health_issues():
            return [{"kind": BAD, "text": HEARTBEAT_FAILED_TEXT}]
        return []
