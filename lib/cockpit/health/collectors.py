"""Turns already-polled cockpit-core sources (beads list) into the plain
inputs :func:`cockpit.health.engine.compute_health` takes. No I/O here — the
beads list itself is read once by the existing ``beads`` PollingSource
(:mod:`cockpit.core.beads_source`); this module only interprets it.

Bead metadata contract this ticket (T16) defines for the four "zone santé
only" signals (spec af-oohx2x, Étapes d'un chantier: "le silence seul n'est
jamais un blocage", Further Notes). No other producer sets these keys yet —
the same incremental pattern T11 used for ``gc``/``beads`` (core/process.py
"a later ticket wires the producer"):

  gc.mayor_first_since   epoch seconds a Mayor-first self-correction
                         attempt began. Cleared, or gc.needs_benjamin set
                         to something other than "none", once promoted to
                         a Benjamin-facing Operator Request — at that point
                         it belongs in "Ce qui t'attend", not here.
  gc.loop_detected       "true" while factory-session-loop-guard judges a
                         session/order to be looping; gc.loop_since epoch.
  gc.order_failed        "true" while a scheduled order has failed;
                         gc.order_failed_at epoch.
  gc.ci_status           "red" while a ticket's CI is red; gc.ci_red_since
                         epoch.
"""


def _float_or_none(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def mayor_first_since_list(beads):
    out = []
    for bead in beads or ():
        meta = bead.get("metadata") or {}
        since = _float_or_none(meta.get("gc.mayor_first_since"))
        if since is None:
            continue
        needs = meta.get("gc.needs_benjamin")
        if needs and needs != "none":
            continue  # promoted -- surfaces in "Ce qui t'attend" instead
        out.append(since)
    return out


def _metadata_flag_items(beads, flag_key, since_key):
    out = []
    for bead in beads or ():
        meta = bead.get("metadata") or {}
        if str(meta.get(flag_key, "")).lower() == "true":
            out.append({"since": _float_or_none(meta.get(since_key))})
    return out


def loop_items(beads):
    return _metadata_flag_items(beads, "gc.loop_detected", "gc.loop_since")


def order_failure_items(beads):
    return _metadata_flag_items(beads, "gc.order_failed", "gc.order_failed_at")


def red_ci_items(beads):
    out = []
    for bead in beads or ():
        meta = bead.get("metadata") or {}
        if str(meta.get("gc.ci_status", "")).lower() == "red":
            out.append({"since": _float_or_none(meta.get("gc.ci_red_since"))})
    return out
