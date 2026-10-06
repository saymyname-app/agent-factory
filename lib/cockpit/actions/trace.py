"""Traces an Operator Action at its source (spec af-oohx2x §"Actions
opérateur", GLOSSARY.md "Operator Action"; T13 AC2, AC6).

Every Operator Action writes a comment plus the same fields as metadata
on the bead it acted on -- so the Factory, the PC, and the iPhone read
the same state from the trace and the cockpit keeps no copy of its own
(spec: "aucune copie locale de l'état des actions"). A source with no
bead of its own gets a bead journal (:func:`ensure_journal_bead`)
instead of a write with nowhere to live.

A failed write raises :class:`TraceError` rather than being swallowed:
spec .36 ("une erreur se corrige par une nouvelle action tracée, jamais
par un effacement") only holds if a half-done write is never mistaken
for a successful one.
"""
import json
import subprocess
from datetime import datetime, timezone

JOURNAL_KEY = "gc.cockpit_journal_for"


class TraceError(Exception):
    pass


def now_iso(clock):
    return datetime.fromtimestamp(clock.now(), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_from_epoch(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_trace(bd_bin, bead_id, quoi, sur_quoi, option_ou_raison, quand_iso, acteur, extra_metadata=None, timeout=10):
    """Writes the trace (spec .35: quoi, sur quoi, option ou raison,
    quand, acteur) as one comment plus matching metadata keys on
    ``bead_id``. ``extra_metadata``: action-specific fields (e.g.
    acquitter's ``gc.cockpit_ack``, reporter's ``gc.cockpit_defer_until``)
    written alongside the common trace fields, not instead of them."""
    metadata = {
        "gc.cockpit_action_quoi": quoi,
        "gc.cockpit_action_sur_quoi": sur_quoi,
        "gc.cockpit_action_detail": option_ou_raison or "",
        "gc.cockpit_action_quand": quand_iso,
        "gc.cockpit_action_acteur": acteur,
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    note = "Cockpit: %s sur %s (%s) — %s, par %s" % (
        quoi,
        sur_quoi,
        option_ou_raison or "-",
        quand_iso,
        acteur,
    )
    args = [bd_bin, "update", bead_id, "--append-notes", note]
    for key, value in metadata.items():
        args.extend(["--set-metadata", "%s=%s" % (key, value)])
    completed = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if completed.returncode != 0:
        raise TraceError("bd update failed for %s: %s" % (bead_id, completed.stderr.strip()))
    return True


def ensure_journal_bead(bd_bin, source_key, title=None, timeout=10):
    """Finds the existing bead journal for ``source_key`` (spec: "pour une
    source sans bead, un bead journal"), or creates one the first time an
    Operator Action ever targets that source. Never creates a duplicate:
    every journal bead carries :data:`JOURNAL_KEY` = ``source_key``."""
    list_args = [bd_bin, "list", "--has-metadata-key", JOURNAL_KEY, "--json"]
    completed = subprocess.run(list_args, capture_output=True, text=True, timeout=timeout)
    if completed.returncode == 0 and completed.stdout.strip():
        try:
            beads = json.loads(completed.stdout)
        except ValueError:
            beads = []
        if isinstance(beads, dict):
            beads = [beads]
        for bead in beads:
            metadata = bead.get("metadata") or {}
            if metadata.get(JOURNAL_KEY) == source_key:
                return bead.get("id")

    create_args = [
        bd_bin,
        "create",
        title or ("Journal cockpit — %s" % source_key),
        "--metadata",
        json.dumps({JOURNAL_KEY: source_key}),
        "--silent",
    ]
    completed = subprocess.run(create_args, capture_output=True, text=True, timeout=timeout)
    if completed.returncode != 0:
        raise TraceError("could not create journal bead for %s: %s" % (source_key, completed.stderr.strip()))
    new_id = completed.stdout.strip()
    if not new_id:
        raise TraceError("journal bead creation for %s returned no id" % source_key)
    return new_id
