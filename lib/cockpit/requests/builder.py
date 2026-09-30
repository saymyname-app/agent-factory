"""Turns a beads snapshot into Operator Requests (spec af-oohx2x §"Moteur
des Demandes opérateur", §"Demandes opérateur : types, niveaux, sortie").

Only two kinds of bead ever become a request here:
  * an open/in_progress bead carrying ``gc.needs_benjamin`` (not "none") —
    an escalation-door NEEDS BENJAMIN (T06). Its level is Urgent when
    ``gc.escalation_bloquant`` is "true", otherwise À faire (spec .5).
  * an open bead labelled ``proposal`` whose ``gc.proposal_state`` is not
    yet ``a_planifier``/``rejetee`` — an open proposal-door proposal (T07),
    always Quand tu veux.

A bead with only ``gc.escalation_mayor_paged_at`` set (a Mayor-first
escalation not yet promoted) carries no ``gc.needs_benjamin`` and is never
looked at here — CONTEXT.md's Operator Request definition excludes it by
construction, not by a special case (spec .9).

Exit is at-source only: a request appears here exactly when its condition
is open on the bead; it stops appearing the moment the same bead no longer
matches (needs_benjamin cleared, proposal state moved on) — never because
the operator acknowledged or deferred it (spec .15, .19).
"""
import json
from datetime import datetime, timezone

from cockpit.requests.model import (
    A_FAIRE,
    DEFAULT_PROJECT,
    OperatorRequest,
    QUAND_TU_VEUX,
    TYPE_ESCALATION,
    TYPE_PROPOSAL,
    URGENT,
)
from cockpit.text import fallback
from cockpit.text.validate import violations as text_violations

NEEDS_BENJAMIN_KEY = "gc.needs_benjamin"
PROPOSAL_LABEL = "proposal"
_CLOSED_PROPOSAL_STATES = {"a_planifier", "rejetee"}


def _parse_iso(value):
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _parse_json_field(raw):
    """Beads metadata values are always strings (Beads is a flat key/value
    store); escalation-door and proposal-door write ``que_faire`` as a JSON
    array *encoded into that string* (both doors' own consumers, e.g.
    escalation-door's ``repondre``, re-parse it the same way with ``jq``).
    A bead built straight from a fixture/test may already hand this
    function a real list — accepted unchanged so a test is not forced to
    double-encode it."""
    if isinstance(raw, (list, dict)):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except ValueError:
            return None
    return None


def _parse_que_faire(raw):
    """Returns (options, ok) — ``ok`` False if ``raw`` is missing, not a
    non-empty list, or any option fails the main-text control."""
    raw = _parse_json_field(raw)
    if not isinstance(raw, list) or not raw:
        return [], False
    options = []
    for item in raw:
        if not isinstance(item, dict):
            return [], False
        option = item.get("option")
        consequence = item.get("consequence")
        if text_violations("option", option) or text_violations("conséquence", consequence):
            return [], False
        options.append(
            {
                "lettre": item.get("lettre", ""),
                "option": option,
                "consequence": consequence,
                "recommande": bool(item.get("recommande", False)),
                "raison": item.get("raison") or "",
            }
        )
    recommended = [o for o in options if o["recommande"]]
    if len(recommended) > 1:
        return [], False
    for option in recommended:
        if text_violations("raison de la recommandation", option["raison"]):
            return [], False
    return options, True


def _is_escalation(bead):
    metadata = bead.get("metadata") or {}
    value = metadata.get(NEEDS_BENJAMIN_KEY)
    return bool(value) and value != "none"


def _is_open_proposal(bead):
    labels = bead.get("labels") or []
    if PROPOSAL_LABEL not in labels:
        return False
    metadata = bead.get("metadata") or {}
    state = metadata.get("gc.proposal_state") or "ouverte"
    return state not in _CLOSED_PROPOSAL_STATES


def _build_one(bead, verifie_a, defects):
    metadata = bead.get("metadata") or {}
    bead_id = bead.get("id") or ""
    missing = []

    if _is_escalation(bead):
        req_type = TYPE_ESCALATION
        quoi = metadata.get(NEEDS_BENJAMIN_KEY)
        pourquoi = metadata.get("gc.escalation_pourquoi")
        que_faire_raw = metadata.get("gc.escalation_que_faire") or []
        depuis_iso = metadata.get("gc.escalation_horodatage")
        niveau = URGENT if str(metadata.get("gc.escalation_bloquant")).lower() == "true" else A_FAIRE
    else:
        req_type = TYPE_PROPOSAL
        quoi = metadata.get("gc.proposal_quoi")
        pourquoi = metadata.get("gc.proposal_pourquoi")
        que_faire_raw = metadata.get("gc.proposal_que_faire") or []
        depuis_iso = metadata.get("gc.proposal_horodatage")
        niveau = QUAND_TU_VEUX

    if text_violations("quoi", quoi):
        missing.append("quoi")
        quoi = fallback.incomplete_label("quoi")

    if text_violations("pourquoi", pourquoi):
        missing.append("pourquoi")
        pourquoi = fallback.FALLBACK_POURQUOI

    que_faire, que_faire_ok = _parse_que_faire(que_faire_raw)
    if not que_faire_ok:
        missing.append("que_faire")
        que_faire = fallback.fallback_que_faire()

    depuis_quand = _parse_iso(depuis_iso)
    if depuis_quand is None:
        missing.append("depuis_quand")

    projet = metadata.get("gc.project_id") or DEFAULT_PROJECT

    incomplete = bool(missing)
    defect_key = None
    if incomplete:
        defect_key = (bead_id, tuple(sorted(missing)))
        defects.record_once(
            defect_key,
            "%s: champ(s) manquant(s) ou invalide(s) — %s" % (bead_id, ", ".join(missing)),
        )

    recommande_absent = not any(o.get("recommande") for o in que_faire)

    request = OperatorRequest(
        id=bead_id,
        type=req_type,
        niveau=niveau,
        quoi=quoi,
        pourquoi=pourquoi,
        que_faire=que_faire,
        projet=projet,
        depuis_quand=depuis_quand,
        verifie_a=verifie_a,
        lien=bead_id,
        incomplete=incomplete,
        missing_fields=missing,
        recommande_absent=recommande_absent,
    )
    return request, defect_key


def build_requests(beads, verifie_a=None, defects=None):
    """``beads``: the raw list the beads source last read (spec .3's read
    model value for "beads"). ``defects`` is optional — pass a
    :class:`~cockpit.requests.defects.DefectCounter` to count producer
    defects; omitted, a throwaway counter is used so callers that only
    want the list are not forced to wire one up."""
    from cockpit.requests.defects import DefectCounter

    defects = defects if defects is not None else DefectCounter()
    beads = beads or []
    requests = []
    live_defect_keys = []
    for bead in beads:
        if not isinstance(bead, dict):
            continue
        if _is_escalation(bead) or _is_open_proposal(bead):
            request, defect_key = _build_one(bead, verifie_a, defects)
            requests.append(request)
            if defect_key is not None:
                live_defect_keys.append(defect_key)
    defects.forget_all_except(live_defect_keys)
    requests.sort(key=lambda r: r.sort_key())
    return requests
