"""What the cockpit does after a gesture whose command expired (af-fksj2c;
Spec af-fgcw0d, user story 122, Implementation Decision 6: « une issue
incertaine impose une relecture de la source avant tout nouvel essai, sans
masquer un succès enregistré »).

A command that did not answer in time may have done its work: the gesture
cannot be sent again blindly. Its target is marked uncertain. A new gesture
on it is refused until the tracker was read again after the mark; then, if
what it targeted no longer waits -- the command had done its work, and the
reading shows it --, the gesture is refused for good and the success read
stays what the page shows; if it still waits, the mark is lifted and the
gesture goes.

    outcomes = UncertainOutcomes()
    outcomes.record(target, at=now)
    refusal = outcomes.refusal(target, read_at, waiting)   # None: it may go

One instance per cockpit process; thread-safe.
"""
import threading

REREAD_PENDING = ("Le geste précédent sur cette demande a une issue incertaine : le cockpit relit la source. "
                  "Réessaie une fois la demande relue.")
ALREADY_DONE = ("Le geste précédent a été enregistré à la source : cette demande n’attend plus rien. "
                "Rien n’a été envoyé de nouveau.")


class UncertainOutcomes:
    def __init__(self):
        self._lock = threading.Lock()
        self._since = {}

    def record(self, target, at):
        """The gesture on ``target`` had an uncertain outcome at ``at``."""
        if target:
            with self._lock:
                self._since[target] = at

    def refusal(self, target, read_at, waiting):
        """Why a new gesture on ``target`` may not go, or ``None``.
        ``read_at``: when the tracker was last read (``None``: never);
        ``waiting``: the ids of the requests that reading lists."""
        with self._lock:
            since = self._since.get(target)
            if since is None:
                return None
            if read_at is None or read_at <= since:
                return REREAD_PENDING
            if target not in waiting:
                return ALREADY_DONE
            del self._since[target]
            return None
