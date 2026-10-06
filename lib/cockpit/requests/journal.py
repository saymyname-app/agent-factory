"""The journal's one read (spec af-oohx2x .18, §"Actions opérateur":
"Aucune copie locale : la page journal relit ces traces"): every bead that
ever carried an Operator Request, and what its notes say resolved it.

The doors and the cockpit's own actions leave their trace in the bead's
**notes** (``bd update --append-notes``: ``bin/escalation-door``,
``bin/proposal-door``, :mod:`cockpit.actions.trace`), which ``bd list
--json`` returns — checked on the live tracker, 2026-10-06. Three keyed
reads find those beads whatever their status; the value kept in the read
model is the parsed entries as plain data, not the beads.
"""
from dataclasses import asdict

from cockpit.core.beads_source import read_beads_json
from cockpit.ui.journal.entries import JournalEntry, journal_from_beads

# A bead carries one of these from the day it bears a request or a trace.
TRACE_KEYS = ("gc.needs_benjamin", "gc.proposal_state", "gc.cockpit_action_quoi")


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
    return {"entries": [asdict(entry) for entry in journal_from_beads(by_id.values())]}


def entries_from_value(value):
    return [JournalEntry(**raw) for raw in (value or {}).get("entries") or []]
