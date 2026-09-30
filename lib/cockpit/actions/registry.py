"""Wires the T13 Operator Actions (acquitter, reporter, continuer) into
HTTP-callable handlers (spec af-oohx2x §"Actions opérateur").

Each handler takes the parsed JSON POST body and returns the JSON
payload to send back, or raises :class:`ActionError` with a message safe
to show the operator. Nothing here talks HTTP -- :mod:`cockpit.core.server`
owns the access guard and the wire format; this module only owns what an
action *does*.
"""
from cockpit.actions import trace
from cockpit.actions.continuer import build_prompt
from cockpit.actions.defer import compute_defer_until

DEFAULT_ACTOR = "benjamin"


class ActionError(Exception):
    pass


def _require(payload, field):
    value = payload.get(field)
    if not value:
        raise ActionError("champ manquant : %s" % field)
    return value


def _resolve_target(bd_bin, payload):
    """An action targets either an existing bead (``bead_id``) or a
    source with none of its own (``source_key``) -- never both missing
    (spec: "pour une source sans bead, un bead journal")."""
    bead_id = payload.get("bead_id")
    if bead_id:
        return bead_id
    source_key = payload.get("source_key")
    if not source_key:
        raise ActionError("champ manquant : bead_id ou source_key")
    try:
        return trace.ensure_journal_bead(bd_bin, source_key)
    except trace.TraceError as exc:
        raise ActionError(str(exc))


def build_action_handlers(bd_bin, clock, acteur=DEFAULT_ACTOR):
    def handle_acquitter(payload):
        target_id = _resolve_target(bd_bin, payload)
        quand = trace.now_iso(clock)
        try:
            trace.write_trace(
                bd_bin,
                target_id,
                quoi="acquitter",
                sur_quoi=target_id,
                option_ou_raison="",
                quand_iso=quand,
                acteur=acteur,
                extra_metadata={"gc.cockpit_ack": "true", "gc.cockpit_ack_at": quand},
            )
        except trace.TraceError as exc:
            raise ActionError(str(exc))
        return {"ok": True, "bead_id": target_id, "quand": quand}

    def handle_reporter(payload):
        target_id = _resolve_target(bd_bin, payload)
        option = _require(payload, "option")
        custom_epoch = payload.get("custom_epoch")
        try:
            defer_until = compute_defer_until(option, clock, custom_epoch=custom_epoch)
        except ValueError as exc:
            raise ActionError(str(exc))
        quand = trace.now_iso(clock)
        defer_iso = trace.iso_from_epoch(defer_until)
        try:
            trace.write_trace(
                bd_bin,
                target_id,
                quoi="reporter",
                sur_quoi=target_id,
                option_ou_raison=option,
                quand_iso=quand,
                acteur=acteur,
                extra_metadata={"gc.cockpit_defer_until": defer_iso},
            )
        except trace.TraceError as exc:
            raise ActionError(str(exc))
        return {"ok": True, "bead_id": target_id, "defer_until": defer_iso}

    def handle_continuer(payload):
        bead_id = _require(payload, "bead_id")
        quoi = payload.get("quoi") or ""
        dossier = payload.get("dossier") or None
        prompt = build_prompt(bead_id, quoi, dossier=dossier)
        return {"ok": True, "prompt": prompt}

    return {
        "acquitter": handle_acquitter,
        "reporter": handle_reporter,
        "continuer": handle_continuer,
    }
