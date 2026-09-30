"""Builds the subprocess argv for "relancer" (spec af-oohx2x §"Actions
opérateur"; T14, af-peh3yy): Benjamin relaunches a session or an order the
factory-session-loop-guard paused, from the cockpit, without opening an
agent session.

Pure function -- :mod:`cockpit.actions.registry` owns actually running the
command and tracing the result. Unlike escalation-door/proposal-door, a
session or an order has no door of its own that already traces its
relaunch, so the cockpit action handler traces it itself (same as
acquitter/reporter do today).
"""

TARGET_SESSION = "session"
TARGET_ORDER = "order"
VALID_TARGET_TYPES = (TARGET_SESSION, TARGET_ORDER)


class RelanceError(Exception):
    pass


def build_relance_command(target_type, loop_guard_bin, gc_bin, session_id=None, order_name=None):
    """Returns the argv to run for ``target_type`` -- ``session`` dispatches
    to the loop-guard's own ``resume <id>`` (the one place a paused session
    is ever resumed from, spec .9's single-door discipline mirrored for
    this safety net); ``order`` dispatches to ``<gc_bin> order run
    <name>`` -- there is no dedicated order-pause/order-resume door yet."""
    if target_type == TARGET_SESSION:
        if not session_id:
            raise RelanceError("champ manquant : session_id")
        return [loop_guard_bin, "resume", session_id]
    if target_type == TARGET_ORDER:
        if not order_name:
            raise RelanceError("champ manquant : order_name")
        return [gc_bin, "order", "run", order_name]
    raise RelanceError("target_type inconnu : %s" % target_type)


def relance_target_label(target_type, session_id=None, order_name=None):
    """The human-readable "sur quoi" for the trace -- the session id or the
    order name, whichever this relaunch targeted."""
    return session_id if target_type == TARGET_SESSION else order_name
