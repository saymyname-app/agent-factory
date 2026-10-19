"""Wires the Operator Actions into HTTP-callable handlers (spec af-oohx2x
§"Actions opérateur").

T13 (af-cx20q9) built acquitter/reporter/continuer. T14 (af-peh3yy) adds
répondre (escalation-door), accepter/rejeter/reporter une proposition
(proposal-door), and relancer (loop-guard/order) -- the gestures that let
Benjamin unblock the factory from the cockpit without opening an agent
session. Every one of those five requires a two-step ("deux temps")
confirmation: the JSON body must carry ``confirm: true`` literally, or the
handler raises :class:`ActionError` before touching anything -- no
subprocess call, no trace write. A real first tap in the UI never sends
this flag (see :mod:`cockpit.ui.actions.render`'s ``SCRIPT``); only a
second, explicit confirmation does.

Each handler takes the parsed JSON POST body and returns the JSON
payload to send back, or raises :class:`ActionError` with a message safe
to show the operator. Nothing here talks HTTP -- :mod:`cockpit.core.server`
owns the access guard and the wire format; this module only owns what an
action *does*.
"""
import subprocess
from datetime import datetime

from cockpit.actions import relancer, trace
from cockpit.actions.continuer import build_prompt
from cockpit.actions.defer import compute_defer_until
from cockpit.core.readmodel import PARIS
from cockpit.projects.actions import AccepterError, accepter_chantier, pas_bon_vers_agent

DEFAULT_ACTOR = "benjamin"
DOOR_TIMEOUT_SECONDS = 15


class ActionError(Exception):
    pass


def _require(payload, field):
    value = payload.get(field)
    if not value:
        raise ActionError("champ manquant : %s" % field)
    return value


def _require_confirm(payload):
    """The "deux temps" contract shared by répondre, accepter/rejeter/
    reporter une proposition, and relancer: a POST missing ``confirm:
    true`` (the first tap) is refused before anything else runs -- no
    subprocess call, no trace, nothing touched (spec: "deux temps")."""
    if payload.get("confirm") is not True:
        raise ActionError("confirmation requise")


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


def _run_door(args, timeout=DOOR_TIMEOUT_SECONDS):
    """Shells out to a door binary (escalation-door, proposal-door, the
    loop-guard, or the order runner) the same way :mod:`cockpit.actions.
    trace` shells out to ``bd`` -- a non-zero exit becomes an
    :class:`ActionError` carrying the door's own refusal message, never
    swallowed."""
    try:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except OSError as exc:
        raise ActionError("commande introuvable : %s" % exc)
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "échec de la commande").strip()
        raise ActionError(message)
    return completed.stdout


def _show_bead(bd_bin, bead_id, timeout=DOOR_TIMEOUT_SECONDS):
    import json

    completed = subprocess.run(
        [bd_bin, "show", bead_id, "--json"], capture_output=True, text=True, timeout=timeout
    )
    if completed.returncode != 0:
        raise ActionError((completed.stderr or "bead introuvable : %s" % bead_id).strip())
    try:
        data = json.loads(completed.stdout)
    except ValueError:
        raise ActionError("réponse illisible pour %s" % bead_id)
    if isinstance(data, list):
        data = data[0] if data else {}
    return data or {}


def _hhmm_paris(iso_value):
    if not iso_value:
        return None
    text = iso_value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt.astimezone(PARIS).strftime("%H:%M")


def build_action_handlers(
    bd_bin,
    clock,
    acteur=DEFAULT_ACTOR,
    escalation_door_bin="escalation-door",
    proposal_door_bin="proposal-door",
    loop_guard_bin="factory-session-loop-guard",
    gc_bin="gc",
):
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

    def handle_repondre(payload):
        """Répondre (spec af-oohx2x §"Actions opérateur"; T14 AC1):
        Benjamin picks a prepared option on a NEEDS BENJAMIN -- the cockpit
        only calls escalation-door's own ``repondre``, which does all the
        tracing (comment + metadata) and clears gc.needs_benjamin itself;
        this handler never duplicates that write. The response carries a
        ready-to-show "répondu b à HH:MM, en cours de traitement par
        l'usine" string, read back from the bead escalation-door just
        wrote -- the display never gets ahead of the trace it depends on."""
        _require_confirm(payload)
        bead_id = _require(payload, "bead_id")
        lettre = _require(payload, "lettre")
        # The click is Benjamin's own, confirmed gesture: the door records
        # him as the one who answered (af-zkdvur).
        _run_door([escalation_door_bin, "repondre", bead_id, lettre, "--actor", "benjamin"])
        bead = _show_bead(bd_bin, bead_id)
        metadata = bead.get("metadata") or {}
        option = metadata.get("gc.escalation_response_option", lettre)
        quand_iso = metadata.get("gc.escalation_response_at")
        hhmm = _hhmm_paris(quand_iso) or "--:--"
        display = "répondu %s à %s, en cours de traitement par l'usine" % (option, hhmm)
        return {
            "ok": True,
            "bead_id": bead_id,
            "lettre": option,
            "quand": quand_iso,
            "display": display,
        }

    def handle_accepter_proposition(payload):
        """Accepter une proposition (T14 AC2): proposal-door's own
        ``accepter`` traces the acceptance on the bead; this handler only
        calls it after the two-step confirmation."""
        _require_confirm(payload)
        bead_id = _require(payload, "bead_id")
        _run_door([proposal_door_bin, "accepter", bead_id, acteur])
        return {"ok": True, "bead_id": bead_id}

    def handle_rejeter_proposition(payload):
        """Rejeter une proposition (T14 AC2): the reason is mandatory --
        missing or empty, this refuses before ever calling proposal-door
        (which would also refuse, but the cockpit checks first so no
        subprocess is even spawned)."""
        _require_confirm(payload)
        bead_id = _require(payload, "bead_id")
        raison = _require(payload, "raison")
        _run_door([proposal_door_bin, "rejeter", bead_id, raison, acteur])
        return {"ok": True, "bead_id": bead_id, "raison": raison}

    def handle_reporter_proposition(payload):
        """Reporter une proposition (T14 AC2): defers it until ``heure``
        (free text) without changing its state -- proposal-door's own
        ``reporter`` traces this."""
        _require_confirm(payload)
        bead_id = _require(payload, "bead_id")
        heure = _require(payload, "heure")
        _run_door([proposal_door_bin, "reporter", bead_id, heure, acteur])
        return {"ok": True, "bead_id": bead_id, "heure": heure}

    def handle_relancer(payload):
        """Relancer (T14 AC3): resumes a session or an order the
        factory-session-loop-guard paused. Unlike the doors above, there is
        no existing trace-writer for this -- the handler traces it itself
        on the target bead/journal, exactly like acquitter/reporter do."""
        _require_confirm(payload)
        target_type = _require(payload, "target_type")
        session_id = payload.get("session_id")
        order_name = payload.get("order_name")
        try:
            args = relancer.build_relance_command(
                target_type, loop_guard_bin, gc_bin, session_id=session_id, order_name=order_name
            )
        except relancer.RelanceError as exc:
            raise ActionError(str(exc))
        _run_door(args)
        target_id = _resolve_target(bd_bin, payload)
        label = relancer.relance_target_label(target_type, session_id=session_id, order_name=order_name)
        quand = trace.now_iso(clock)
        try:
            trace.write_trace(
                bd_bin,
                target_id,
                quoi="relancer",
                sur_quoi=label,
                option_ou_raison=target_type,
                quand_iso=quand,
                acteur=acteur,
            )
        except trace.TraceError as exc:
            raise ActionError(str(exc))
        return {"ok": True, "bead_id": target_id, "target_type": target_type, "target": label}

    def handle_accepter_chantier(payload):
        """Accepter un chantier Livré (spec .30), two-step like every
        gesture that changes the factory's state: the trace on the convoy
        is what the next stage read turns into Accepté."""
        bead_id = _require(payload, "bead_id")
        try:
            result = accepter_chantier(
                bd_bin, bead_id, clock, acteur=acteur, confirm=payload.get("confirm") is True
            )
        except AccepterError as exc:
            raise ActionError(str(exc))
        result["display"] = "Chantier accepté à %s" % (_hhmm_paris(result["quand"]) or "--:--")
        return result

    def handle_pas_bon_vers_agent(payload):
        """« Pas bon → agent » (spec .31): a prompt to copy, nothing
        written, the frozen graph untouched."""
        bead_id = _require(payload, "bead_id")
        return {"ok": True, "prompt": pas_bon_vers_agent(bead_id, payload.get("titre") or "")}

    return {
        "accepter_chantier": handle_accepter_chantier,
        "pas_bon_vers_agent": handle_pas_bon_vers_agent,
        "acquitter": handle_acquitter,
        "reporter": handle_reporter,
        "continuer": handle_continuer,
        "repondre": handle_repondre,
        "accepter_proposition": handle_accepter_proposition,
        "rejeter_proposition": handle_rejeter_proposition,
        "reporter_proposition": handle_reporter_proposition,
        "relancer": handle_relancer,
    }
