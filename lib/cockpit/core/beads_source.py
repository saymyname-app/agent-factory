"""Beads read, on its own rhythm (spec .3, Validity window 5 min).

A thin wrapper around the ``bd`` CLI so a test can point ``bd_bin`` at a
fake bd fixture (Testing Decisions: "faux bd") instead of the live Beads
store. Authority: bead state, never mail (AGENTS.md Invariants).

The running cockpit reads Beads only through :mod:`cockpit.core.tracker`
(one reader, one ``bd`` at a time). :class:`DirectTracker` is the same
interface read straight from ``bd``, one call per question: for a test or a
one-off tool, never for a process that reads in a loop (af-q55qqx.9).
"""
import json
import subprocess

import bounded_process

NEEDS_BENJAMIN_KEY = "gc.needs_benjamin"
# How long one ``bd`` call may take before the read counts as failed. Reads
# run one at a time (cockpit.core.tracker): waiting is harmless, a read
# killed at 10 s while Dolt answered in 12 s (19/11/2026) was not.
READ_TIMEOUT_SECONDS = 30


def read_beads_json(args, bd_bin="bd", timeout=READ_TIMEOUT_SECONDS):
    """Run ``bd <args> --json`` and return the parsed payload. At the
    timeout the whole process group is killed (lib/bounded_process.py)."""
    completed = bounded_process.run(
        [bd_bin, *args, "--json"],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
        stdin=subprocess.DEVNULL,
    )
    return json.loads(completed.stdout)


def flagged_args():
    """Every bead still carrying ``gc.needs_benjamin``, whatever its status."""
    return ["list", "--all", "--limit", "0", "--has-metadata-key", NEEDS_BENJAMIN_KEY]


def merge_operator_beads(beads, flagged):
    """The beads the cockpit's ``beads`` source keeps: every non-closed bead
    (plain ``bd list``), plus every bead still carrying ``gc.needs_benjamin``
    whatever its status — closing the work does not answer the question
    (af-1al0t1, same rule as ``escalation-door list``); merged by id."""
    seen = {b.get("id") for b in beads if isinstance(b, dict)}
    return list(beads) + [b for b in flagged if isinstance(b, dict) and b.get("id") not in seen]


def read_operator_beads(bd_bin="bd", timeout=READ_TIMEOUT_SECONDS):
    beads = read_beads_json(["list"], bd_bin=bd_bin, timeout=timeout)
    flagged = read_beads_json(flagged_args(), bd_bin=bd_bin, timeout=timeout)
    return merge_operator_beads(beads, flagged)


class DirectTracker:
    """The tracker as the views ask it (``open``, ``with_key``,
    ``children``), each question one ``bd`` call. Same interface as
    :class:`cockpit.core.tracker.TrackerSnapshot`."""

    def __init__(self, bd_bin="bd", timeout=READ_TIMEOUT_SECONDS):
        self.bd_bin = bd_bin
        self.timeout = timeout

    def _read(self, args):
        return [b for b in read_beads_json(args, bd_bin=self.bd_bin, timeout=self.timeout) or []
                if isinstance(b, dict)]

    def open(self):
        return self._read(["list"])

    def with_key(self, key, ephemeral=False):
        """Every bead carrying ``key``, open or closed; with ``ephemeral``,
        the beads the tracker keeps apart too."""
        args = ["list", "--all", "--limit", "0"] + (["--include-ephemeral"] if ephemeral else [])
        return self._read(args + ["--has-metadata-key", key])

    def children(self, bead_id):
        return self._read(["children", bead_id])
