"""Builds the subprocess argv for "relancer" (spec af-oohx2x §"Actions
opérateur"; T14, af-peh3yy): Benjamin relaunches a session or an order the
factory-session-loop-guard paused, from the cockpit, without opening an
agent session.

Pure function -- :mod:`cockpit.actions.registry` owns actually running the
command and tracing the result. Unlike escalation-door/proposal-door, a
session or an order has no door of its own that already traces its
relaunch, so the cockpit action handler traces it itself (same as
acquitter/reporter do today). An order is resumed by its own door,
``bin/order-pause resume`` (af-npz9v1.15, for BR af-eyc5ah), which closes
the record of its pause and writes who resumed it, when and in what words.
"""

TARGET_SESSION = "session"
TARGET_ORDER = "order"
VALID_TARGET_TYPES = (TARGET_SESSION, TARGET_ORDER)


class RelanceError(Exception):
    pass


# The words the door of an order records with its resume: the gesture's.
ORDER_RESUME_WORDS = "relance depuis le cockpit"


def build_relance_command(target_type, loop_guard_bin, order_pause_bin, session_id=None, order_name=None,
                          acteur="benjamin"):
    """Returns the argv to run for ``target_type`` -- ``session`` dispatches
    to the loop-guard's own ``resume <id>`` (the one place a paused session
    is ever resumed from, spec .9's single-door discipline mirrored for
    this safety net); ``order`` dispatches to the door of pause and resume
    of an order, ``<order_pause_bin> resume <name> --by <acteur> --words
    …``: the one place a paused order is resumed from, never a run of it
    out of its schedule."""
    if target_type == TARGET_SESSION:
        if not session_id:
            raise RelanceError("champ manquant : session_id")
        return [loop_guard_bin, "resume", session_id]
    if target_type == TARGET_ORDER:
        if not order_name:
            raise RelanceError("champ manquant : order_name")
        return [order_pause_bin, "resume", order_name, "--by", acteur, "--words", ORDER_RESUME_WORDS]
    raise RelanceError("target_type inconnu : %s" % target_type)


def relance_target_label(target_type, session_id=None, order_name=None):
    """The human-readable "sur quoi" for the trace -- the session id or the
    order name, whichever this relaunch targeted."""
    return session_id if target_type == TARGET_SESSION else order_name
