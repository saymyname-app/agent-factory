"""Beads read, on its own rhythm (spec .3, Validity window 5 min).

A thin wrapper around the ``bd`` CLI so a test can point ``bd_bin`` at a
fake bd fixture (Testing Decisions: "faux bd") instead of the live Beads
store. Authority: bead state, never mail (AGENTS.md Invariants).
"""
import json
import subprocess

NEEDS_BENJAMIN_KEY = "gc.needs_benjamin"


def read_beads_json(args, bd_bin="bd", timeout=10):
    """Run ``bd <args> --json`` and return the parsed payload."""
    completed = subprocess.run(
        [bd_bin, *args, "--json"],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )
    return json.loads(completed.stdout)


def read_operator_beads(bd_bin="bd", timeout=10):
    """The beads the cockpit's source keeps: every non-closed bead (plain
    ``bd list``), plus every bead still carrying ``gc.needs_benjamin``
    whatever its status — closing the work does not answer the question
    (af-1al0t1, same rule as ``escalation-door list``). The second read is
    filtered by bd itself, not a full ``list --all``; merged by id."""
    beads = read_beads_json(["list"], bd_bin=bd_bin, timeout=timeout)
    flagged = read_beads_json(
        ["list", "--all", "--limit", "0", "--has-metadata-key", NEEDS_BENJAMIN_KEY],
        bd_bin=bd_bin,
        timeout=timeout,
    )
    seen = {b.get("id") for b in beads if isinstance(b, dict)}
    return beads + [b for b in flagged if isinstance(b, dict) and b.get("id") not in seen]
