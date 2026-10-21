"""The Outcome of a chantier, read from the records of the D01 flow (A1,
af-c662qx; Spec af-fgcw0d, user stories 8, 40, 44, 47, 108, 111, 117,
118, 119, 120, 121, 123 and 136; decision « État D01 commun aux vues »).

    outcome = read_outcome(convoy, spec_title, pack)
    sections = read_pack_sections(folder)

:func:`read_outcome` is the one reader, in the cockpit, of the Outcome of a
convoy that carries the new-flow mark. It reads the records the flow wrote
on it -- the Delivered Outcome, its Evidence Pack, the acceptance, the
answers of the owner, the proof of the merge and the closing -- through
``convoy_state.outcome_records_of``, the reader of ``bin/convoy-state``
(``docs/CONVOY_STATE.md``: the only reader of the state of a convoy of the
new flow), and makes of them one issue, its words and its history, as plain
data. The home page, the page of the project, its details and its history
all show that record, so no screen says another state than the records.
The screens say « résultat » for it, the word of the interface.

- An Outcome delivered on an open convoy is to judge, never blocked
  because the convoy is still open: it closes only after the judgement.
- A closed ticket is no merge: only a recorded promotion is.
- Accepted, merge pending, merge under way and merge confirmed are told
  apart; an abandon merged nothing, legitimately, and keeps its reason.
- A record that cannot be read leaves the Outcome unknown: never a known
  state, never a guess from the others.
- An issue its proofs contradict is said as an inconsistency: closed as
  accepted with no proof of merge, a merge with no acceptance, an answer
  or a merge whose commit or dossier fingerprint is not the one of the
  Delivered Outcome.

A convoy with none of these records yet is in delivery: :func:`read_outcome`
answers None and the stage of its tickets stands. No I/O but
:func:`read_pack_sections`, which reads the page of a dossier.
"""
import html
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from convoy_state import outcome_records_of

PARIS = ZoneInfo("Europe/Paris")
REQUEST_KEY = "gc.needs_benjamin"
REQUEST_WHY_KEY = "gc.escalation_pourquoi"
SPEC_KEY = "gc.spec_id"
# The page of an Evidence Pack, in its folder (bin/evidence-pack).
PACK_PAGE = "index.html"

# The issues of an Outcome, each with the stage the screens show and what
# the panel of the result says of it.
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
# Issues where the Outcome is the one to judge now: Essai and Avis belong there.
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
# The contradictions between an issue and its proofs, as the screens say them.
CLOSED_WITHOUT_MERGE = "Fermé comme accepté, sans preuve de fusion enregistrée."
ABANDONED_MERGED = "Abandonné alors qu’un commit est enregistré comme fusionné."
MERGE_WITHOUT_ACCEPTANCE = "Un commit est enregistré comme fusionné sans acceptation en cours."
ANSWER_NOT_DELIVERED = ("La réponse enregistrée ne porte pas sur la version livrée : son commit ou l’empreinte "
                        "de son dossier diffère du résultat Delivered.")
MERGE_NOT_JUDGED = "Le commit fusionné ne vient pas du résultat jugé : le commit jugé diffère de la réponse enregistrée."


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


def pack_folder(convoy):
    """The folder of the Evidence Pack recorded on ``convoy`` (a bead), or
    None when it records none, or none that can be read."""
    records = outcome_records_of(convoy) or {}
    pack = records.get("evidence_pack")
    return pack["path"] if isinstance(pack, dict) and "unruled" not in pack else None


def read_outcome(convoy, spec_title=None, pack=None):
    """The Outcome of ``convoy`` (a bead) as its D01 records give it, or
    None when it carries none of them (not of the new flow, or still in
    delivery).

    ``spec_title``: the title of the Spec of the convoy, what the Outcome
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
    records = outcome_records_of(convoy)
    if records is None:
        return None
    present = {name: record for name, record in records.items() if record is not None}
    if not present:
        return None
    metadata = convoy.get("metadata") or {}
    is_open = convoy.get("status") != "closed"
    outcome = _base(metadata, spec_title, pack, is_open)
    if any("unruled" in record for record in present.values()):
        return _issue(outcome, UNKNOWN)
    answers = present.get("judgement", {}).get("answers", [])
    delivered = present.get("delivered")
    promotion = present.get("promotion")
    closed = present.get("closed")
    acceptance = present.get("acceptance")
    dossier = present.get("evidence_pack")
    last = answers[-1] if answers else None
    # An answer counts for the Outcome delivered now when it is not older
    # than it: « constats rendus » withdraws an Outcome, the next one is new.
    current = last if last and (delivered is None or _at(last) >= _at(delivered)) else None

    outcome["commit"] = (delivered or current or dossier or {}).get("commit")
    outcome["pack"] = (delivered or current or {}).get("pack") or (dossier or {}).get("digest")
    history = outcome["history"]
    ready_at = _hhmm((delivered or acceptance or {}).get("at"))
    if ready_at:
        history.append("%s · Résultat prêt" % ready_at)
    if current is not None and _hhmm(current.get("at")):
        history.append("%s · Réponse enregistrée" % _hhmm(current.get("at")))
    if promotion:
        outcome["judged"], outcome["merged"] = promotion.get("judged"), promotion.get("merged")
    response = (current or {}).get("response")
    how = (closed or {}).get("how")

    if not is_open and closed is None and promotion is None:
        # Closed outside the doors of the flow: nothing here says its issue.
        return None
    if current is not None and response != "findings" and not current.get("in_flight") and delivered and (
            current.get("commit") != delivered["commit"] or current.get("pack") != delivered["pack"]):
        return _issue(outcome, INCONSISTENT, ANSWER_NOT_DELIVERED)
    if promotion and response == "accepted" and promotion["judged"] != current.get("commit"):
        return _issue(outcome, INCONSISTENT, MERGE_NOT_JUDGED)
    if how == "accepted" or (not is_open and promotion):
        if not promotion:
            return _issue(outcome, INCONSISTENT, CLOSED_WITHOUT_MERGE)
        if response != "accepted" or current.get("voided"):
            return _issue(outcome, INCONSISTENT, MERGE_WITHOUT_ACCEPTANCE)
        return _merged(outcome, promotion, MERGED)
    if how == "abandoned" or response == "abandoned":
        if promotion:
            return _issue(outcome, INCONSISTENT, ABANDONED_MERGED)
        outcome["reason"] = (current or {}).get("reason") or (closed or {}).get("said")
        return _issue(outcome, ABANDONED)
    if promotion:
        if response != "accepted" or current.get("voided"):
            return _issue(outcome, INCONSISTENT, MERGE_WITHOUT_ACCEPTANCE)
        return _merged(outcome, promotion, MERGING)
    if response == "accepted" and current.get("voided"):
        cause = (current.get("voided") or {}).get("cause")
        sentence = SENTENCES[VOIDED]
        if cause in VOID_CAUSES:
            sentence = "Ton acceptation est annulée (%s). Un nouveau jugement sera nécessaire." % VOID_CAUSES[cause]
        return _issue(outcome, VOIDED, sentence)
    if response == "accepted":
        return _issue(outcome, ACCEPTED, history_end=NO_MERGE_PROOF)
    if response == "findings":
        return _issue(outcome, RETURNED)
    if delivered is None:
        return None
    if (acceptance or {}).get("panne"):
        return _issue(outcome, OUTAGE)
    if dossier and (dossier["commit"] != delivered["commit"] or dossier["digest"] != delivered["pack"]):
        return _issue(outcome, OUTDATED)
    return _issue(outcome, TO_JUDGE)


def _base(metadata, spec_title, pack, is_open):
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


def _issue(outcome, issue, sentence=None, history_end=None):
    outcome["issue"], outcome["label"] = issue, LABELS[issue]
    outcome["sentence"] = sentence or SENTENCES[issue]
    if issue == ABANDONED:
        outcome["history"].append("Raison : %s" % (outcome["reason"] or "non enregistrée"))
    if history_end:
        outcome["history"].append(history_end)
    return outcome


def _merged(outcome, promotion, issue):
    at = _hhmm(promotion.get("at"))
    proof = "Fusion confirmée · résultat jugé %s → commit fusionné %s" % (_short(promotion.get("judged")),
                                                                         _short(promotion.get("merged")))
    if issue == MERGING:
        # Recorded, the convoy not closed yet: the merge is under way.
        return _issue(outcome, MERGING, history_end=NO_MERGE_PROOF)
    return _issue(outcome, MERGED, history_end="%s · %s" % (at, proof) if at else proof)


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


def read_pack_sections(folder):
    """The rubrics of the page of the dossier whose folder is ``folder``
    (its ``index.html``, as ``gc.flow.evidence_pack`` records it), or None
    when the page cannot be read: the cockpit then says the dossier was not
    read, never that it says nothing."""
    try:
        with open(os.path.join(folder, PACK_PAGE), encoding="utf-8") as page:
            return pack_sections(page.read())
    except (OSError, UnicodeDecodeError, TypeError):
        return None
