"""The journal's one read (spec af-oohx2x .18, §"Actions opérateur":
"Aucune copie locale : la page journal relit ces traces"): every bead that
ever carried an Operator Request, and what its notes say resolved it.

The doors and the cockpit's own actions leave their trace in the bead's
**notes** (``bd update --append-notes``: ``bin/escalation-door``,
``bin/proposal-door``, :mod:`cockpit.actions.trace`), which ``bd list
--json`` returns — checked on the live tracker, 2026-10-06. Three keyed
reads find those beads whatever their status; the value kept in the read
model is the parsed entries as plain data, not the beads.

An event bead marked for the journal (``gc.journal_event``: its nature, or
the technical source it comes from) is one entry of its own, at the time it
was created (T01R6, af-ltchro; Spec af-2zseit, user story 126).

A bead naming a technical source under ``gc.journal_source`` declares that
source connected: the factory writes its events to the journal, whether it
sent one yet or not (F, af-njwz8v; user story 158).
"""
from dataclasses import asdict

from cockpit.core.beads_source import read_beads_json
from cockpit.ui.journal.entries import JOURNAL_EVENT_KEY, JOURNAL_SOURCE_KEY, JournalEntry, journal_from_beads

# A bead carries one of these from the day it bears a request or a trace;
# an event bead meant for the journal carries the last one from its creation.
TRACE_KEYS = ("gc.needs_benjamin", "gc.proposal_state", "gc.cockpit_action_quoi", JOURNAL_EVENT_KEY)


def read_journal(bd_bin="bd", timeout=20):
    """Raises on any failed ``bd`` call: a journal missing a kind of
    resolution would read as "that never happened"."""
    by_id = {}
    for key in TRACE_KEYS:
        for bead in read_beads_json(
            ["list", "--all", "--limit", "0", "--has-metadata-key", key], bd_bin=bd_bin, timeout=timeout
        ):
            if isinstance(bead, dict) and bead.get("id"):
                by_id.setdefault(bead["id"], bead)
    sources = {
        str((bead.get("metadata") or {}).get(JOURNAL_SOURCE_KEY) or "").strip()
        for bead in read_beads_json(
            ["list", "--all", "--limit", "0", "--has-metadata-key", JOURNAL_SOURCE_KEY], bd_bin=bd_bin, timeout=timeout
        )
        if isinstance(bead, dict)
    }
    return {"entries": [asdict(entry) for entry in journal_from_beads(by_id.values())],
            "sources": sorted(source for source in sources if source)}


def entries_from_value(value):
    return [JournalEntry(**raw) for raw in (value or {}).get("entries") or []]


def sources_from_value(value):
    """The technical sources declared connected, as their producers name them."""
    return list((value or {}).get("sources") or [])
