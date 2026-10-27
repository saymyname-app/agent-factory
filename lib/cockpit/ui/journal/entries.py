"""Journal des demandes résolues (T15, af-icxjc4 — Spec af-oohx2x .18,
.19: "un journal des demandes résolues (quoi, quand, par qui ou quelle
voie)" ; "qu'une demande qui revient après résolution soit une nouvelle
demande").

Where the traces really are (af-mjfvwx): see :func:`journal_from_beads`
at the end of this module — the doors append them to the bead's notes;
the comment-reading described just below was never what they wrote.

"Relu depuis les traces": the journal keeps no state of its own — it is
rebuilt every time from the resolution comments the doors and Operator
Actions already write on the bead they resolved (spec: "aucune copie
locale"), read via ``bd comments <id> --json``. Three note bodies exist
in the codebase today and this module recognises all three:

  * ``cockpit.actions.trace.write_trace``'s own fixed format — used by
    acquitter/reporter/relancer (T13/T14): ``"Cockpit: %s sur %s (%s) —
    %s, par %s"`` (quoi, sur_quoi, detail, quand, acteur). Of these three
    only relancer resolves anything the way this module cares about
    (acquitter/reporter never close a request at the source — they are
    filtered out below).
  * ``bin/escalation-door``'s ``repondre``: ``"RÉPONSE: %s — %s"``
    (lettre, option_texte) — always resolves the NEEDS BENJAMIN it
    answers.
  * ``bin/proposal-door``'s ``accepter``/``rejeter``/``resoudre``:
    ``"PROPOSITION ACCEPTÉE par %s — passe à planifier"`` /
    ``"PROPOSITION REJETÉE par %s — %s"`` / ``"PROPOSITION RÉSOLUE par %s
    — %s"`` (acteur[, raison | preuve]) — all three resolve the proposal;
    the third is the one a merged delivery writes, with its proof.

A bead accumulates one comment per action over its lifetime (Beads
comments are append-only), so a bead resolved, reopened (a new NEEDS
BENJAMIN, a new proposal) and resolved again carries two matching
comments — :func:`build_journal` yields two distinct entries, which is
exactly spec .19's "une demande qui revient après résolution est une
nouvelle demande": the live request list (``requests/builder.py``, out
of this ticket's scope) already shows it again the moment the source
reopens; this module only has to not collapse its two resolutions into
one journal row.

Known gap, left for the wiring ticket: the T15 source types built in
``requests/sources/`` (Spec/graphe à approuver, ticket HITL, rituel dû)
resolve through tools that do not yet write a matching comment
(``bin/spec-approve``, ``bin/ticket-graph-publish``) — :func:`parse_trace_note`
simply does not match their output today, so they are silently absent
from the journal until those tools gain one, rather than this module
guessing at a format that does not exist yet.
"""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from cockpit.text.redact import redact

REPONSE_RE = re.compile(r"^RÉPONSE: (?P<lettre>.+?) — (?P<texte>.*)$")
PROPOSITION_ACCEPTEE_RE = re.compile(r"^PROPOSITION ACCEPTÉE par (?P<acteur>.+?) — passe à planifier$")
PROPOSITION_REJETEE_RE = re.compile(r"^PROPOSITION REJETÉE par (?P<acteur>.+?) — (?P<raison>.*)$")
PROPOSITION_RESOLUE_RE = re.compile(r"^PROPOSITION RÉSOLUE par (?P<acteur>.+?) — (?P<preuve>.*)$")
# ADR-0029: a maintenance proposal taken over by the factory (the door
# files its bug bead and routes it to the Mayor), and a maintenance bead
# reconverted into a decision because it touched what the operator sees.
PROPOSITION_PRISE_EN_CHARGE_RE = re.compile(
    r"^PROPOSITION PRISE EN CHARGE par (?P<acteur>.+?) — ticket (?P<ticket>\S+)$"
)
PROPOSITION_RECONVERTIE_RE = re.compile(
    r"^PROPOSITION RECONVERTIE en décision par (?P<acteur>.+?) — (?P<raison>.*)$"
)
COCKPIT_TRACE_RE = re.compile(
    r"^Cockpit: (?P<quoi>.+?) sur (?P<sur_quoi>.+?) \((?P<detail>.*?)\) — (?P<quand>.+?), par (?P<acteur>.+)$"
)

# Only these cockpit.actions.trace "quoi" values ever resolve a request
# at its source — acquitter and reporter keep it listed (acquitter) or
# merely hide it until due (reporter), so they are not journalled here.
RESOLVING_COCKPIT_ACTIONS = {"relancer"}


@dataclass
class JournalEntry:
    bead_id: str
    quoi: str
    quand: str
    par: str
    voie: str
    # The request this resolved, in its producer's words (spec .18
    # "quoi"): the journal says what was asked, not only what was done.
    demande: str = ""
    # An event (F, af-njwz8v): what its producer said of it -- its
    # consequence or meaning (``texte``, its lines), the link it offers
    # (``lien``, « Voir le projet »), what it holds folded (``plie``: its
    # detail and source, or its raw event as received) and its project
    # (``projet``, a key). Secrets and private reasoning are removed as it
    # is read (cockpit.text.redact).
    texte: list = field(default_factory=list)
    lien: str = ""
    plie: list = field(default_factory=list)
    projet: str = ""


def _field(comment, *names):
    for name in names:
        value = comment.get(name)
        if value:
            return value
    return None


def _as_comment_dict(comment):
    """A raw comment is either a plain string body (a test's shorthand)
    or the dict ``bd comments --json`` returns — normalised to
    ``{"body": str, "created_at": str or None, "author": str or None}``
    either way."""
    if isinstance(comment, str):
        return {"body": comment, "created_at": None, "author": None}
    if isinstance(comment, dict):
        return {
            "body": _field(comment, "body", "text", "note") or "",
            "created_at": _field(comment, "created_at", "quand", "timestamp"),
            "author": _field(comment, "author", "acteur", "actor"),
        }
    return {"body": "", "created_at": None, "author": None}


def parse_trace_note(bead_id, comment):
    """``comment``: a plain comment body string, or a ``bd comments
    --json`` comment dict. Returns a :class:`JournalEntry` if it is a
    resolution note this module recognises, else ``None`` (the comment
    is either unrelated bead chatter or an action that does not resolve
    a request). The comment's own ``created_at``/``author`` win over
    whatever the note text carries when both are present — a comment's
    own metadata is Beads' own record, the text is a human-readable
    echo of it."""
    parsed = _as_comment_dict(comment)
    text = parsed["body"]
    if not text:
        return None

    match = REPONSE_RE.match(text)
    if match:
        return JournalEntry(
            bead_id=bead_id,
            quoi="répondu %s — %s" % (match.group("lettre"), match.group("texte")),
            quand=parsed["created_at"] or "",
            par=parsed["author"] or "benjamin",
            voie="escalation-door",
        )

    match = PROPOSITION_ACCEPTEE_RE.match(text)
    if match:
        return JournalEntry(
            bead_id=bead_id,
            quoi="proposition acceptée — passe à planifier",
            quand=parsed["created_at"] or "",
            par=parsed["author"] or match.group("acteur"),
            voie="proposal-door",
        )

    match = PROPOSITION_REJETEE_RE.match(text)
    if match:
        return JournalEntry(
            bead_id=bead_id,
            quoi="proposition rejetée — %s" % match.group("raison"),
            quand=parsed["created_at"] or "",
            par=parsed["author"] or match.group("acteur"),
            voie="proposal-door",
        )

    match = PROPOSITION_RESOLUE_RE.match(text)
    if match:
        return JournalEntry(
            bead_id=bead_id,
            quoi="proposition résolue par une livraison — %s" % match.group("preuve"),
            quand=parsed["created_at"] or "",
            par=parsed["author"] or match.group("acteur"),
            voie="proposal-door",
        )

    match = PROPOSITION_PRISE_EN_CHARGE_RE.match(text)
    if match:
        return JournalEntry(
            bead_id=bead_id,
            quoi="proposition de maintenance prise en charge par l'usine",
            quand=parsed["created_at"] or "",
            par=parsed["author"] or match.group("acteur"),
            voie="proposal-door",
        )

    match = PROPOSITION_RECONVERTIE_RE.match(text)
    if match:
        return JournalEntry(
            bead_id=bead_id,
            quoi="proposition reconvertie en décision — %s" % match.group("raison"),
            quand=parsed["created_at"] or "",
            par=parsed["author"] or match.group("acteur"),
            voie="proposal-door",
        )

    match = COCKPIT_TRACE_RE.match(text)
    if match and match.group("quoi") in RESOLVING_COCKPIT_ACTIONS:
        return JournalEntry(
            bead_id=bead_id,
            quoi="%s — %s" % (match.group("quoi"), match.group("sur_quoi")),
            quand=parsed["created_at"] or match.group("quand"),
            par=parsed["author"] or match.group("acteur"),
            voie="cockpit",
        )

    return None


def build_journal(comments_by_bead):
    """``comments_by_bead``: ``{bead_id: [comment, ...]}`` in
    chronological order, as ``bd comments <id> --json`` already returns
    them (each comment a string body or a dict — see
    :func:`parse_trace_note`). One :class:`JournalEntry` per recognised
    resolution comment — a bead resolved more than once yields one entry
    per resolution (spec .19), in the order its comments were given."""
    entries = []
    for bead_id, comments in (comments_by_bead or {}).items():
        for comment in comments or []:
            entry = parse_trace_note(bead_id, comment)
            if entry is not None:
                entries.append(entry)
    return entries


# ---------------------------------------------------------------------
# What the tracker really holds (af-mjfvwx, checked 2026-10-06): the doors
# and :mod:`cockpit.actions.trace` leave their trace with ``bd update
# --append-notes`` -- lines of the bead's ``notes`` field, not Beads
# comments (``bd comments`` is empty on a bead Benjamin answered). A note
# line carries no date or author of its own; the doors stamp the date of
# the *latest* answer in metadata, and ``escalation-door clear`` stamps
# none at all.
# ---------------------------------------------------------------------
NEEDS_BENJAMIN_RE = re.compile(r"^NEEDS BENJAMIN: (?P<quoi>.*)$")
PROPOSITION_RE = re.compile(r"^PROPOSITION: (?P<quoi>.*)$")
DECISION_CLEARED_RE = re.compile(r"^DECISION CLEARED: ")

VOIE_CLEAR = "clear"
CLEARED_TEXT = "Effacée sans réponse enregistrée"

# What a cockpit action reads as in the journal -- never its internal name.
COCKPIT_ACTION_TEXT = {"relancer": "Relance demandée", "accepter_chantier": "Chantier accepté"}
RESOLVING_COCKPIT_ACTIONS.update(COCKPIT_ACTION_TEXT)


# An event bead meant for the journal (`bd create --type event`) carries its
# nature or its source under this key (T01R6, af-ltchro; Spec af-2zseit),
# the link it offers under the second, and what it holds folded under the
# third: a JSON list of lines (F, af-njwz8v; Spec af-fgcw0d). Its
# description is its consequence, or what it means.
JOURNAL_EVENT_KEY = "gc.journal_event"
JOURNAL_LINK_KEY = "gc.journal_link"
JOURNAL_FOLDED_KEY = "gc.journal_folded"
# A bead that declares a technical source connected (cockpit.requests.journal).
JOURNAL_SOURCE_KEY = "gc.journal_source"
PROJECT_KEY = "gc.project_id"


def _folded_lines(raw):
    """The folded lines an event carries: a JSON list of strings, or a
    text, one line each."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            raw = raw.split("\n")
    if not isinstance(raw, list):
        return []
    return [redact(str(line)) for line in raw if str(line).strip()]


def _entries_of(bead):
    bead_id = bead.get("id") or ""
    metadata = bead.get("metadata") or {}
    if metadata.get(JOURNAL_EVENT_KEY):
        # An event is not the resolution of a request: it is its own entry,
        # under its title, at the time it was recorded.
        lines = [redact(line.strip()) for line in (bead.get("description") or "").split("\n") if line.strip()]
        return [JournalEntry(bead_id=bead_id, quoi=redact(bead.get("title") or ""), quand=bead.get("created_at") or "",
                             par="", voie=redact(str(metadata[JOURNAL_EVENT_KEY])), texte=lines,
                             lien=str(metadata.get(JOURNAL_LINK_KEY) or ""),
                             plie=_folded_lines(metadata.get(JOURNAL_FOLDED_KEY)),
                             projet=str(metadata.get(PROJECT_KEY) or ""))]
    entries = []
    # The request a resolution answers is the last one asked before it; a
    # trace on a bead that never bore a question (a chantier accepted) is
    # about the bead itself.
    demande = metadata.get("gc.proposal_quoi") or ""
    last_reponse = last_proposal = last_cleared = None
    for line in (bead.get("notes") or "").split("\n"):
        line = line.strip()
        asked = NEEDS_BENJAMIN_RE.match(line) or PROPOSITION_RE.match(line)
        if asked:
            demande = asked.group("quoi")
            continue
        if DECISION_CLEARED_RE.match(line):
            entry = JournalEntry(bead_id=bead_id, quoi=CLEARED_TEXT, quand="", par="", voie=VOIE_CLEAR)
        else:
            entry = parse_trace_note(bead_id, line)
            if entry is None:
                continue
            cockpit = COCKPIT_TRACE_RE.match(line)
            if cockpit:
                entry.quoi = COCKPIT_ACTION_TEXT.get(cockpit.group("quoi"), entry.quoi)
        entry.demande = demande or (bead.get("title") or "")
        if entry.voie == "escalation-door":
            last_reponse = entry
        elif entry.voie == "proposal-door":
            last_proposal = entry
        elif entry.voie == VOIE_CLEAR:
            last_cleared = entry
        entries.append(entry)
    # ``escalation-door clear`` dates its latest clearance since af-mjfvwx;
    # the ones cleared before that carry no date at all.
    if last_cleared is not None:
        last_cleared.quand = metadata.get("gc.escalation_cleared_at") or ""
    if last_reponse is not None:
        last_reponse.quand = metadata.get("gc.escalation_response_at") or ""
        last_reponse.par = metadata.get("gc.escalation_response_actor") or last_reponse.par
    # proposal-door's "reporter" overwrites the same response date: with a
    # report recorded, that date is no longer the decision's.
    if last_proposal is not None and not metadata.get("gc.proposal_report_until"):
        last_proposal.quand = metadata.get("gc.proposal_response_at") or ""
    return entries


def _instant_key(quand):
    """What orders ``quand`` among the others: the instant it says, in UTC,
    whatever offset it is written with; the text itself when it is no date."""
    try:
        return datetime.fromisoformat(quand).astimezone(timezone.utc).isoformat()
    except ValueError:
        return quand


def journal_from_beads(beads):
    """Every resolution the notes of ``beads`` record, and every event they
    hold for the journal, newest first; the ones no trace dates come last,
    in the order given. A bead resolved twice yields two entries (spec .19)."""
    entries = []
    for bead in beads or []:
        if isinstance(bead, dict):
            entries.extend(_entries_of(bead))
    dated = sorted((e for e in entries if e.quand), key=lambda e: _instant_key(e.quand), reverse=True)
    return dated + [e for e in entries if not e.quand]
