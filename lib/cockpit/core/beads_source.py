"""Beads read, on its own rhythm (spec .3, Validity window 5 min).

A thin wrapper around the ``bd`` CLI so a test can point ``bd_bin`` at a
fake bd fixture (Testing Decisions: "faux bd") instead of the live Beads
store. Authority: bead state, never mail (AGENTS.md Invariants).
"""
import json
import subprocess


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
