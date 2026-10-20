"""The result of a chantier, read from the records of the D01 flow (A1,
af-c662qx; Spec af-fgcw0d, user stories 8, 40, 44, 47, 108, 111, 117,
118, 119, 120, 121, 123 and 136; decision « État D01 commun aux vues »).

    result = read_result(convoy, spec_title, pack)
    sections = read_pack_sections(path)

:func:`read_result` is the one reader of the result of a convoy that
carries the new-flow mark: what the flow recorded on it -- the result
delivered (``gc.flow.delivered``), the dossier (``gc.flow.evidence_pack``),
the request of the acceptance (``gc.flow.acceptance``), the answers of the
owner (``gc.flow.judgement``), the proof of the merge
(``gc.flow.promotion``) and the closing (``gc.flow.closed``), as
``bin/convoy-state`` writes them (``docs/CONVOY_STATE.md``) -- becomes one
issue, its words and its history, as plain data. The home page, the page of
the project, its details and its history all show that record, so no
screen says another state than the records.

- A result delivered on an open convoy is to judge, never blocked because
  the convoy is still open: it closes only after the judgement.
- A closed ticket is no merge: only a recorded promotion is.
- Accepted, merge pending, merge under way and merge confirmed are told
  apart; an abandon merged nothing, legitimately, and keeps its reason.
- A record that cannot be read leaves the result unknown: never a known
  state, never a guess from the others.
- An issue its proofs contradict (closed as accepted with no proof of
  merge, a merge with no acceptance) is said as an inconsistency.

A convoy with none of these records yet is in delivery: :func:`read_result`
answers None and the stage of its tickets stands. No I/O but
:func:`read_pack_sections`, which reads the page of a dossier.
"""
import html
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
NEW_FLOW_MARK_KEY = "gc.flow.mark"
DELIVERED_KEY = "gc.flow.delivered"
PACK_KEY = "gc.flow.evidence_pack"
ACCEPTANCE_KEY = "gc.flow.acceptance"
JUDGEMENT_KEY = "gc.flow.judgement"
PROMOTION_KEY = "gc.flow.promotion"
CLOSED_KEY = "gc.flow.closed"
RECORD_KEYS = (DELIVERED_KEY, PACK_KEY, ACCEPTANCE_KEY, JUDGEMENT_KEY, PROMOTION_KEY, CLOSED_KEY)
REQUEST_KEY = "gc.needs_benjamin"
REQUEST_WHY_KEY = "gc.escalation_pourquoi"
SPEC_KEY = "gc.spec_id"

# The issues of a result, each with the stage the screens show and what the
# result panel says of it.
TO_JUDGE = "to_judge"
OUTDATED = "outdated"
OUTAGE = "outage"
RETURNED = "returned"
ACCEPTED = "accepted"
VOIDED = "voided"
MERGING = "merging"
MERGED = "merged"
ABANDONED = "abandoned"
UNKNOWN = "unknown"
INCONSISTENT = "inconsistent"
# Issues where the result is the one to judge now: Essai and Avis belong there.
JUDGED_NOW = (TO_JUDGE, OUTDATED, OUTAGE)

LABELS = {
    TO_JUDGE: "À juger",
    OUTDATED: "Dossier périmé",
    OUTAGE: "Essai en panne",
    RETURNED: "Constats rendus",
    ACCEPTED: "Accepté",
    VOIDED: "Acceptation annulée",
    MERGING: "Fusion en cours",
    MERGED: "Fusionné",
    ABANDONED: "Abandonné",
    UNKNOWN: "Inconnu",
    INCONSISTENT: "Incohérence",
}
SENTENCES = {
    TO_JUDGE: "Le résultat attend ton jugement.",
    OUTDATED: "Dossier périmé : il ne correspond plus à la version livrée. Il ne peut plus être accepté "
              "ni essayé comme s’il était courant ; un nouveau dossier doit être préparé.",
    OUTAGE: "L’essai n’a pas pu démarrer : c’est une panne de lancement, pas un jugement sur le produit.",
    RETURNED: "Tu as rendu tes constats. L’usine reprend le résultat ; un nouveau dossier te sera présenté.",
    ACCEPTED: "Tu as accepté. La fusion est en attente.",
    VOIDED: "Ton acceptation est annulée : la version a changé depuis. Un nouveau jugement sera nécessaire.",
    MERGING: "La fusion est en cours.",
    MERGED: "La fusion est confirmée.",
    ABANDONED: "Chantier abandonné. Rien n’a été fusionné.",
    UNKNOWN: "État du résultat inconnu : un enregistrement du flux est illisible.",
}
VOID_CAUSES = {"conflict": "conflit avec la branche protégée", "regression": "vérification rouge",
               "fidelity": "fidélité non tenue", "start": "le produit ne démarre plus"}
NO_MERGE_PROOF = "Aucune preuve de fusion à ce stade."
NOT_VERIFIED = "Ce qui n'a PAS été vérifié"
REPORT = "Compte rendu"


def _decode(raw):
    """A record as ``bin/convoy-state`` stores it (a JSON object, often as
    a string), or ``False`` when it cannot be read."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return False
    return raw if isinstance(raw, dict) else False


def _hhmm(at):
    """HH:MM (Paris) of a recorded instant, or None when it is not one."""
    try:
        moment = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        return None
    return moment.astimezone(PARIS).strftime("%H:%M")


def _short(commit):
    return str(commit or "")[:7]


def _at(record):
    return str((record or {}).get("at") or "")


def read_result(convoy, spec_title=None, pack=None):
    """The result of ``convoy`` (a bead) as its D01 records give it, or
    None when it carries none of them (not of the new flow, or still in
    delivery).

    ``spec_title``: the title of the Spec of the convoy, what the result
    delivers. ``pack``: the rubrics of its dossier page,
    :func:`read_pack_sections`, or None when it was not read.

    The record: ``issue`` (one of :data:`LABELS`), ``label``, ``sentence``,
    ``title`` and ``summary`` (what the request of the acceptance and the
    Spec say), ``history`` (lines, oldest first), ``reason`` (of an
    abandon), ``judged`` and ``merged`` (commits), ``commit`` and ``pack``
    (the version delivered and the fingerprint of its dossier), ``spec``,
    ``unverified`` (what the dossier says was not verified), ``reports``
    (its parts named « Compte rendu … »: label and lines), ``rubrics`` (its
    other parts), ``pack_read``, ``open``."""
    metadata = convoy.get("metadata") or {}
    if not metadata.get(NEW_FLOW_MARK_KEY):
        return None
    present = {key: _decode(metadata[key]) for key in RECORD_KEYS if metadata.get(key) not in (None, "")}
    if not present:
        return None
    is_open = convoy.get("status") != "closed"
    result = _base(convoy, metadata, spec_title, pack, is_open)
    if any(record is False for record in present.values()):
        return _issue(result, UNKNOWN)
    answers = present.get(JUDGEMENT_KEY, {}).get("answers", [])
    if not isinstance(answers, list) or not all(isinstance(answer, dict) for answer in answers):
        return _issue(result, UNKNOWN)
    delivered = present.get(DELIVERED_KEY)
    promotion = present.get(PROMOTION_KEY)
    closed = present.get(CLOSED_KEY)
    acceptance = present.get(ACCEPTANCE_KEY)
    dossier = present.get(PACK_KEY)
    last = answers[-1] if answers else None
    # An answer counts for the result delivered now when it is not older
    # than it: « constats rendus » withdraws a result, the next one is new.
    current = last if last and (delivered is None or _at(last) >= _at(delivered)) else None

    result["commit"] = (delivered or current or dossier or {}).get("commit")
    result["pack"] = (delivered or current or {}).get("pack") or (dossier or {}).get("digest")
    history = result["history"]
    ready_at = _hhmm((delivered or acceptance or {}).get("at"))
    if ready_at:
        history.append("%s · Résultat prêt" % ready_at)
    if current is not None and _hhmm(current.get("at")):
        history.append("%s · Réponse enregistrée" % _hhmm(current.get("at")))
    if promotion:
        result["judged"], result["merged"] = promotion.get("judged"), promotion.get("merged")
    response = (current or {}).get("response")
    how = (closed or {}).get("how")

    if not is_open and closed is None and promotion is None:
        # Closed outside the doors of the flow: nothing here says its issue.
        return None
    if how == "accepted" or (not is_open and promotion):
        if not promotion:
            return _issue(result, INCONSISTENT, "Fermé comme accepté, sans preuve de fusion enregistrée.")
        return _merged(result, promotion, MERGED)
    if how == "abandoned" or response == "abandoned":
        if promotion:
            return _issue(result, INCONSISTENT, "Abandonné alors qu’un commit est enregistré comme fusionné.")
        result["reason"] = (current or {}).get("reason") or (closed or {}).get("said")
        return _issue(result, ABANDONED)
    if promotion:
        if response != "accepted" or current.get("voided"):
            return _issue(result, INCONSISTENT, "Un commit est enregistré comme fusionné sans acceptation en cours.")
        return _merged(result, promotion, MERGING)
    if response == "accepted" and current.get("voided"):
        cause = (current.get("voided") or {}).get("cause")
        sentence = SENTENCES[VOIDED]
        if cause in VOID_CAUSES:
            sentence = "Ton acceptation est annulée (%s). Un nouveau jugement sera nécessaire." % VOID_CAUSES[cause]
        return _issue(result, VOIDED, sentence)
    if response == "accepted":
        return _issue(result, ACCEPTED, history_end=NO_MERGE_PROOF)
    if response == "findings":
        return _issue(result, RETURNED)
    if delivered is None:
        return None
    if (acceptance or {}).get("panne"):
        return _issue(result, OUTAGE)
    if dossier and (dossier.get("commit") != delivered.get("commit") or
                    (delivered.get("pack") and dossier.get("digest") != delivered.get("pack"))):
        return _issue(result, OUTDATED)
    return _issue(result, TO_JUDGE)


def _base(convoy, metadata, spec_title, pack, is_open):
    request = metadata.get(REQUEST_KEY)
    sections = pack or []
    return {
        "issue": None, "label": None, "sentence": None,
        "title": request if isinstance(request, str) and request not in ("", "none") else None,
        "summary": spec_title or metadata.get(REQUEST_WHY_KEY) or None,
        "history": [], "reason": None, "judged": None, "merged": None, "commit": None, "pack": None,
        "spec": metadata.get(SPEC_KEY),
        "unverified": next((lines for title, lines in sections if title == NOT_VERIFIED), []),
        "reports": [{"label": title, "said": lines} for title, lines in sections if title.startswith(REPORT)],
        "rubrics": [{"label": title, "said": lines} for title, lines in sections
                    if title != NOT_VERIFIED and not title.startswith(REPORT)],
        "pack_read": pack is not None,
        "open": is_open,
    }


def _issue(result, issue, sentence=None, history_end=None):
    result["issue"], result["label"] = issue, LABELS[issue]
    result["sentence"] = sentence or SENTENCES[issue]
    if issue == ABANDONED:
        result["history"].append("Raison : %s" % (result["reason"] or "non enregistrée"))
    if history_end:
        result["history"].append(history_end)
    return result


def _merged(result, promotion, issue):
    at = _hhmm(promotion.get("at"))
    proof = "Fusion confirmée · résultat jugé %s → commit fusionné %s" % (_short(promotion.get("judged")),
                                                                         _short(promotion.get("merged")))
    if issue == MERGING:
        # Recorded, the convoy not closed yet: the merge is under way.
        return _issue(result, MERGING, history_end=NO_MERGE_PROOF)
    return _issue(result, MERGED, history_end="%s · %s" % (at, proof) if at else proof)


# --- the page of a dossier -------------------------------------------------------

_SECTION = re.compile(r'<section id="rubrique-\d+">\s*<h2>(.*?)</h2>(.*?)</section>', re.S)
_BREAK = re.compile(r"<(?:/?(?:p|li|tr|dt|dd|h3|h4|div|figure|table|ul|ol|dl|article|pre)|br)\b[^>]*>", re.I)
_TAG = re.compile(r"<[^>]+>")
_NUMBER = re.compile(r"^\d+\.\s*")


def pack_sections(page):
    """The rubrics of the page of a dossier (``bin/evidence-pack``: one
    ``<section id="rubrique-N">`` each, under ``<h2>N. title</h2>``): a
    list of (title, lines of text)."""
    sections = []
    for title, body in _SECTION.findall(page or ""):
        text = html.unescape(_TAG.sub("", _BREAK.sub("\n", body)))
        lines = [" ".join(line.split()) for line in text.split("\n")]
        sections.append((_NUMBER.sub("", html.unescape(_TAG.sub("", title))).strip(), [l for l in lines if l]))
    return sections


def read_pack_sections(path):
    """The rubrics of the page of a dossier at ``path``, or None when the
    page cannot be read: the cockpit then says the dossier was not read,
    never that it says nothing."""
    try:
        with open(path, encoding="utf-8") as page:
            return pack_sections(page.read())
    except (OSError, UnicodeDecodeError, TypeError):
        return None
