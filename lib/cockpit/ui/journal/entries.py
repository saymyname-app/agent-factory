"""Journal des demandes résolues (T15, af-icxjc4 — Spec af-oohx2x .18,
.19: "un journal des demandes résolues (quoi, quand, par qui ou quelle
voie)" ; "qu'une demande qui revient après résolution soit une nouvelle
demande").

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
  * ``bin/proposal-door``'s ``accepter``/``rejeter``: ``"PROPOSITION
    ACCEPTÉE par %s — passe à planifier"`` / ``"PROPOSITION REJETÉE par
    %s — %s"`` (acteur[, raison]) — both resolve the proposal.

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
import re
from dataclasses import dataclass

REPONSE_RE = re.compile(r"^RÉPONSE: (?P<lettre>.+?) — (?P<texte>.*)$")
PROPOSITION_ACCEPTEE_RE = re.compile(r"^PROPOSITION ACCEPTÉE par (?P<acteur>.+?) — passe à planifier$")
PROPOSITION_REJETEE_RE = re.compile(r"^PROPOSITION REJETÉE par (?P<acteur>.+?) — (?P<raison>.*)$")
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
