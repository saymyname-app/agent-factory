#!/usr/bin/env python3
"""Pure logic for P16: the append-only overlap/conflict measurement log and
the undeclared-conflict threshold that gates filing the "dynamic leases"
proposal.

bin/ticket-graph-publish (P11) already serialises tickets whose declared
`scope.paths` overlap; bin/pr-autopilot (P06) already returns a ticket-owned
PR that goes DIRTY to the pool. Neither previously left evidence behind. This
module builds the log entries both record and answers the one question the
"dynamic leases" proposal needs: how many PR conflicts, between tickets whose
declared scopes did NOT overlap, landed in the trailing window. No I/O here
beyond the two small read/write helpers -- the caller (bin/overlap-conflict-log)
owns subprocess/gc/bd concerns and file paths.
"""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any

CONTRACT = "agent-factory-overlap-conflict-log/v1"
UNDECLARED_CONFLICT_THRESHOLD = 3
UNDECLARED_CONFLICT_WINDOW_SECONDS = 7 * 24 * 3600


def parse_scope(spec: str | None) -> list[str]:
    """A comma-separated scope-paths string (the shape of
    bin/ticket-graph-publish's `gc.scope_paths` metadata) to a clean list, or
    [] for a ticket with no declared scope."""
    if not spec:
        return []
    return [part.strip() for part in spec.split(",") if part.strip()]


def scopes_overlap(a_paths: list[str], b_paths: list[str]) -> bool:
    """Two glob lists overlap if any pattern from one could match a path the
    other pattern could also match -- the same cross-match
    bin/ticket-graph-publish's `scopes_overlap` uses to serialise overlapping
    tickets at publish time (P11), reused here so a recorded conflict's
    `declared_overlap` flag means the same thing there and here."""
    for pattern_a in a_paths:
        for pattern_b in b_paths:
            if pattern_a == pattern_b:
                return True
            if fnmatch.fnmatch(pattern_a, pattern_b) or fnmatch.fnmatch(pattern_b, pattern_a):
                return True
    return False


def _ordered_pair(
    ticket_a: str, scope_a: list[str], ticket_b: str, scope_b: list[str]
) -> tuple[str, list[str], str, list[str]]:
    """Canonicalise a ticket pair (sorted by id) so the same two tickets
    always produce the same entry regardless of which side called first."""
    if ticket_b < ticket_a:
        return ticket_b, scope_b, ticket_a, scope_a
    return ticket_a, scope_a, ticket_b, scope_b


def make_overlap_entry(
    *, ticket_a: str, scope_a: list[str], ticket_b: str, scope_b: list[str],
    digest: str, rig: str, now: float,
) -> dict[str, Any]:
    ta, sa, tb, sb = _ordered_pair(ticket_a, scope_a, ticket_b, scope_b)
    return {
        "contract": CONTRACT,
        "kind": "overlap",
        "ts": now,
        "rig": rig,
        "ticket_a": ta,
        "scope_a": sa,
        "ticket_b": tb,
        "scope_b": sb,
        "declared_overlap": True,
        "digest": digest,
    }


def make_conflict_entry(
    *, ticket_a: str, scope_a: list[str], ticket_b: str, scope_b: list[str],
    sha: str, rig: str, now: float,
) -> dict[str, Any]:
    ta, sa, tb, sb = _ordered_pair(ticket_a, scope_a, ticket_b, scope_b)
    return {
        "contract": CONTRACT,
        "kind": "conflict",
        "ts": now,
        "rig": rig,
        "ticket_a": ta,
        "scope_a": sa,
        "ticket_b": tb,
        "scope_b": sb,
        "declared_overlap": scopes_overlap(sa, sb),
        "sha": sha,
    }


def append_entry(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def load_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def has_overlap_entry(entries: list[dict[str, Any]], ticket_a: str, ticket_b: str, digest: str) -> bool:
    ta, tb = sorted((ticket_a, ticket_b))
    return any(
        entry.get("kind") == "overlap"
        and entry.get("ticket_a") == ta
        and entry.get("ticket_b") == tb
        and entry.get("digest") == digest
        for entry in entries
    )


def undeclared_conflict_count(
    entries: list[dict[str, Any]], *, now: float,
    window_seconds: int = UNDECLARED_CONFLICT_WINDOW_SECONDS,
) -> int:
    cutoff = now - window_seconds
    return sum(
        1
        for entry in entries
        if entry.get("kind") == "conflict"
        and entry.get("declared_overlap") is False
        and isinstance(entry.get("ts"), (int, float))
        and entry["ts"] >= cutoff
    )


def lease_proposal_due(
    entries: list[dict[str, Any]], *, now: float,
    threshold: int = UNDECLARED_CONFLICT_THRESHOLD,
    window_seconds: int = UNDECLARED_CONFLICT_WINDOW_SECONDS,
) -> bool:
    return undeclared_conflict_count(entries, now=now, window_seconds=window_seconds) >= threshold
