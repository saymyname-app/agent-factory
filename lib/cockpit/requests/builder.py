"""Turns a beads snapshot into Operator Requests (spec af-oohx2x §"Moteur
des Demandes opérateur", §"Demandes opérateur : types, niveaux, sortie").

Only two kinds of bead ever become a request here:
  * a bead carrying ``gc.needs_benjamin`` (not "none"), whatever its
    status — a closed bead's question is still open until answered
    (af-1al0t1; the beads source reads those too) — an escalation-door
    NEEDS BENJAMIN (T06). Its level is Urgent when
    ``gc.escalation_bloquant`` is "true", otherwise À faire (spec .5).
  * an open bead labelled ``proposal`` of class ``decision`` whose
    ``gc.proposal_state`` is not yet ``a_planifier``/``rejetee``/``resolue``
    — an open proposal-door proposal (T07), always Quand tu veux.
    ``resolue`` is the door's ``resoudre`` transition: the delivery that
    answered the proposal merged (proof on the bead,
    ``gc.proposal_resolved_by``), so nothing waits on the operator any
    more. Which proposal is a ``decision`` is
    :mod:`cockpit.requests.proposals` (ADR-0029): a ``maintenance``
    proposal and a proposal no door wrote (no ``gc.proposal_*`` field)
    never become a request here — they are health-zone lines.

A bead with only ``gc.escalation_mayor_paged_at`` set (a Mayor-first
escalation not yet promoted) carries no ``gc.needs_benjamin`` and is never
looked at here — GLOSSARY.md's Operator Request definition excludes it by
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
from cockpit.requests.proposals import is_open_decision
from cockpit.text import fallback
from cockpit.text.validate import request_violations

NEEDS_BENJAMIN_KEY = "gc.needs_benjamin"


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


def _normalise_que_faire(options):
    """The option list as the page renders it, from a list
    :func:`cockpit.text.validate.request_violations` already accepted."""
    return [
        {
            "lettre": item.get("lettre", ""),
            "option": item.get("option"),
            "consequence": item.get("consequence"),
            "recommande": bool(item.get("recommande", False)),
            "raison": item.get("raison") or "",
        }
        for item in options
    ]


def _origin_text(field, value):
    """What the producer actually wrote for ``field``, for the folded
    details (spec .75) -- None when it wrote nothing."""
    if field == "que_faire":
        if isinstance(value, str):
            return value if value.strip() else None
        if isinstance(value, (list, dict)) and value:
            return json.dumps(value, ensure_ascii=False)
        return None
    if isinstance(value, str) and value.strip():
        return value
    return None


def _is_escalation(bead):
    metadata = bead.get("metadata") or {}
    value = metadata.get(NEEDS_BENJAMIN_KEY)
    return bool(value) and value != "none"


def _is_open_proposal(bead):
    # ADR-0029: only a pending proposal of class ``decision`` waits on the
    # operator (cockpit.requests.proposals holds the one reading).
    return is_open_decision(bead)


def _build_one(bead, verifie_a, defects):
    metadata = bead.get("metadata") or {}
    bead_id = bead.get("id") or ""
    missing = []

    precisions = ""
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
        precisions = metadata.get("gc.proposal_details") or ""

    # The same control the doors run before writing (bin/operator-text-check
    # -> cockpit.text.validate.request_violations): a field that fails it is
    # shown as its fixed repli, with the reason and the producer's own text
    # kept for the folded details.
    que_faire_parsed = _parse_json_field(que_faire_raw)
    failures = request_violations(quoi, pourquoi, que_faire_parsed)
    if que_faire_parsed is None and isinstance(que_faire_raw, str) and que_faire_raw.strip():
        failures["que_faire"] = ["champ « que faire » illisible (JSON invalide)"]
    motifs = {}
    texte_origine = {}
    for field_name, raw_value in (("quoi", quoi), ("pourquoi", pourquoi), ("que_faire", que_faire_raw)):
        if field_name not in failures:
            continue
        missing.append(field_name)
        motifs[field_name] = failures[field_name]
        origin = _origin_text(field_name, raw_value)
        if origin is not None:
            texte_origine[field_name] = origin
    if "quoi" in failures:
        quoi = fallback.incomplete_label("quoi")
    if "pourquoi" in failures:
        pourquoi = fallback.FALLBACK_POURQUOI
    if "que_faire" in failures:
        que_faire = fallback.fallback_que_faire()
    else:
        que_faire = _normalise_que_faire(que_faire_parsed)

    depuis_quand = _parse_iso(depuis_iso)
    if depuis_quand is None:
        missing.append("depuis_quand")

    projet = metadata.get("gc.project_id") or DEFAULT_PROJECT

    incomplete = bool(missing)
    defect_key = None
    if incomplete:
        defect_key = (bead_id, tuple(sorted(missing)))
        reasons = [reason for field_name in missing for reason in motifs.get(field_name, [])]
        defects.record_once(
            defect_key,
            "%s: champ(s) manquant(s) ou invalide(s) — %s%s"
            % (bead_id, ", ".join(missing), (" — " + " ; ".join(reasons)) if reasons else ""),
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
        motifs=motifs,
        texte_origine=texte_origine,
        precisions=precisions if isinstance(precisions, str) else "",
    )
    return request, defect_key


def _parse_ack_and_defer(bead):
    """Out-of-scope touch (T13, af-cx20q9 — declared scope lib/cockpit/
    actions/**): reads the trace Acquitter/Reporter leave on the bead
    (cockpit.actions.trace) so the list reflects them — the cockpit keeps
    no copy of its own (spec: "aucune copie locale de l'état des
    actions")."""
    metadata = bead.get("metadata") or {}
    acquittee = str(metadata.get("gc.cockpit_ack", "")).lower() == "true"
    defer_until = _parse_iso(metadata.get("gc.cockpit_defer_until"))
    return acquittee, defer_until


# The same trace hides a deferred request of any bead-borne kind
# (:mod:`cockpit.requests.assemble`).
parse_ack_and_defer = _parse_ack_and_defer


def build_requests(beads, verifie_a=None, defects=None):
    """``beads``: the raw list the beads source last read (spec .3's read
    model value for "beads"). ``defects`` is optional — pass a
    :class:`~cockpit.requests.defects.DefectCounter` to count producer
    defects; omitted, a throwaway counter is used so callers that only
    want the list are not forced to wire one up.

    A request deferred by Reporter (T13) is hidden until its deadline,
    except an Urgent one, which stays listed and flagged ``reportee``
    (rendered greyed — spec .23 "une Urgent reportée reste visible
    grisée"). ``verifie_a`` doubles as "now" for this comparison: it is
    already the read model's own clock-derived read time, refreshed on
    every poll, so no separate clock needs threading through here."""
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
            acquittee, defer_until = _parse_ack_and_defer(bead)
            request.acquittee = acquittee
            still_deferred = (
                defer_until is not None and verifie_a is not None and defer_until > verifie_a
            )
            if still_deferred and request.niveau != URGENT:
                continue
            request.reportee = bool(still_deferred and request.niveau == URGENT)
            requests.append(request)
            if defect_key is not None:
                live_defect_keys.append(defect_key)
    defects.forget_all_except(live_defect_keys)
    requests.sort(key=lambda r: r.sort_key())
    return requests
