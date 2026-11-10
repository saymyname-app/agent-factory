"""Heartbeat emitter (spec af-oohx2x, Implementation Decisions: "Émetteur
de heartbeat"; ticket T18, af-a57xhe).

Every 5 min the cockpit sends an empty ping to an external service
(Healthchecks.io's "Usine muette" check) so Benjamin is alerted if the
cockpit goes silent — PC off included. The ping only goes out once the
cockpit's main sources (:class:`~cockpit.core.readmodel.ReadModel`) have
read fresh: a heartbeat that pings regardless of what it can actually see
would lie about the factory being alive. A missing secret or a failing
ping never crashes the emitter — it becomes a health issue instead (spec
.62-64: never silent about a broken part), same contract as
:class:`~cockpit.core.polling_source.PollingSource`.

The heartbeat pauses only for ``CLEANLY_STOPPED`` — Clean stop, requested
by Benjamin from the cockpit (spec "Heartbeat et usine muette": "jamais à
l'arrêt de Windows"). ``state_provider`` is a plain callable so this
module does not need to know about the Clean stop driver (T23) to be
tested; it only compares whatever state it is given against this one
constant.
"""

CLEANLY_STOPPED = "arretee_proprement"

MISSING_SECRET = "missing_secret"
PING_FAILED = "ping_failed"

_HEALTH_MESSAGES = {
    MISSING_SECRET: "secret heartbeat manquant",
    PING_FAILED: "heartbeat : ping en échec",
}


def read_url_from_file(path):
    """Read the Healthchecks.io ping URL from the out-of-repo secret file
    (spec .13: "l'URL du check vient du fichier hors dépôt côté Windows").

    Never raises: an absent, empty, or unreadable file returns ``None`` so
    a missing secret surfaces as a health issue (AC2) instead of crashing
    the emitter.
    """
    if not path:
        return None
    try:
        with open(path) as fh:
            url = fh.read().strip()
    except OSError:
        return None
    return url or None


def default_ping(url, timeout=5):
    """Send the empty ping Healthchecks.io expects. Raises on failure —
    the caller records that as ``PING_FAILED``."""
    import urllib.request

    with urllib.request.urlopen(url, timeout=timeout) as resp:
        resp.read()


class HeartbeatEmitter:
    """Ticked periodically — a poller thread in production, a test with a
    fake clock here. ``tick()`` is the whole public interface; it never
    raises."""

    def __init__(
        self,
        read_model,
        clock,
        secret_loader,
        ping=default_ping,
        state_provider=lambda: None,
        interval_seconds=300,
    ):
        self._read_model = read_model
        self._clock = clock
        self._secret_loader = secret_loader
        self._ping = ping
        self._state_provider = state_provider
        self._interval = interval_seconds
        self._last_ping_at = None
        self._last_issue = None

    def tick(self):
        """Send a ping if one is due. Returns one of: ``"paused"``,
        ``"waiting"``, ``"sources-not-fresh"``, ``"missing-secret"``,
        ``"ping-failed"``, ``"pinged"`` — for tests and logging."""
        now = self._clock.now()

        if self._state_provider() == CLEANLY_STOPPED:
            return "paused"

        if self._last_ping_at is not None and (now - self._last_ping_at) < self._interval:
            return "waiting"

        if not self._read_model.all_fresh(now):
            return "sources-not-fresh"

        url = self._secret_loader()
        if not url:
            self._last_issue = MISSING_SECRET
            return "missing-secret"

        try:
            self._ping(url)
        except Exception:
            self._last_issue = PING_FAILED
            return "ping-failed"

        self._last_issue = None
        self._last_ping_at = now
        return "pinged"

    def health_issues(self):
        """Fixed French phrases for the health zone (spec .62-64). Empty
        when the last attempted ping (if any) succeeded."""
        message = _HEALTH_MESSAGES.get(self._last_issue)
        return [message] if message else []
