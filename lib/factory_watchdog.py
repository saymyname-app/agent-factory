#!/usr/bin/env python3
"""Watchdog assessments: aged human gates, stuck PRs, false-success workflow closes.

Incident 2026-09-16 (docs/INCIDENT_2026-09-16-silent-campaign-stall.md) found
three gaps the existing campaign-liveness check (lib/factory_liveness.py) does
not cover, because liveness only asks "is the campaign progressing" -- never
"is something else sitting silently waiting on a human, a PR, or hiding a
failure behind a CLOSED status":

  gates      a "Gate: human" issue open past a bounded threshold gets no
             re-notification and no cockpit surfacing (incident gap 2).
  prs        a Factory-repo PR that is CONFLICTING, or has never triggered a
             CI check, is indistinguishable from one quietly waiting its turn
             (incident gap 4).
  workflows  a molecule/workflow bead can close CLOSED while gc.outcome=fail
             (downstream steps skipped by on_fail=abort_scope) and look
             identical to a real success unless something reads the nested
             metadata (incident gap 6).

Each assessor is a pure function over already-fetched JSON, so it is
unit-testable without gc/gh. bin/factory-watchdog does the fetching, paging,
and throttled mail/bead side effects. This module only observes -- ADR-0016
section 7: a local reason may never produce a global stop, and nothing here
is allowed to resolve a gate, merge/close a PR, or reopen a workflow itself.

CLI: one subcommand per assessor, each reads a JSON array on stdin (the raw
`gc bd gate list --json` / `gh pr list --json` / `gc bd list --json` output)
and prints one line per actionable item: "<id>\\t<code>\\t<message>". An item
that is not (yet) actionable prints nothing -- silence is the expected steady
state, exactly like lib/factory_liveness.py.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Iterable

GATE_AGE_MINUTES_DEFAULT = 30
PR_STUCK_MINUTES_DEFAULT = 30


def _epoch(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _hhmm(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%MZ")


def _truncate(text: str, limit: int = 160) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def assess_gate(
    gate: dict[str, Any], now: float, threshold_minutes: int = GATE_AGE_MINUTES_DEFAULT
) -> tuple[str, str, str] | None:
    """An open 'human' gate past the threshold -> (code, message); else None."""
    if str(gate.get("status") or "") != "open":
        return None
    if str(gate.get("await_type") or "") != "human":
        return None
    gate_id = str(gate.get("id") or "?")
    created = _epoch(gate.get("created_at"))
    if created is None:
        return "unreadable", f"gate {gate_id} has no readable created_at"
    age = (now - created) / 60
    if age < threshold_minutes:
        return None
    reason = _truncate(gate.get("description") or gate.get("title") or "")
    return "aged_human_gate", (
        f"gate {gate_id} open {age:.0f} min (since {_hhmm(created)}), "
        f"no human close yet -- {reason}"
    )


def assess_gates(
    gates: Iterable[dict[str, Any]], now: float, threshold_minutes: int = GATE_AGE_MINUTES_DEFAULT
) -> list[tuple[str, str, str]]:
    out = []
    for gate in gates:
        verdict = assess_gate(gate, now, threshold_minutes)
        if verdict is not None:
            out.append((str(gate.get("id") or "?"), verdict[0], verdict[1]))
    return out


def assess_pr(
    pr: dict[str, Any], now: float, threshold_minutes: int = PR_STUCK_MINUTES_DEFAULT
) -> tuple[str, str, str] | None:
    """An open, non-draft PR that can never self-merge as-is -> (code, message); else None.

    mergeStateStatus == "CONFLICTING" or an empty statusCheckRollup are both
    states pr-autopilot's "merge on green CI" assumption never resolves on its
    own -- see incident gap 4 (PR #57: conflicting, statusCheckRollup: []).
    """
    if bool(pr.get("isDraft")):
        return None
    number = pr.get("number")
    created = _epoch(pr.get("createdAt"))
    if created is None:
        return None
    age = (now - created) / 60
    if age < threshold_minutes:
        return None
    state = str(pr.get("mergeStateStatus") or "")
    checks = pr.get("statusCheckRollup")
    never_ran = isinstance(checks, list) and len(checks) == 0
    if state == "CONFLICTING":
        return "pr_conflicting", (
            f"PR #{number} has a merge conflict, open {age:.0f} min "
            f"(since {_hhmm(created)}) -- pr-autopilot cannot arm this"
        )
    if never_ran:
        return "pr_no_ci", (
            f"PR #{number} has never triggered a CI check, open {age:.0f} min "
            f"(since {_hhmm(created)}) -- indistinguishable from 'waiting its turn' "
            f"without this check"
        )
    return None


def assess_prs(
    prs: Iterable[dict[str, Any]], now: float, threshold_minutes: int = PR_STUCK_MINUTES_DEFAULT
) -> list[tuple[str, str, str]]:
    out = []
    for pr in prs:
        verdict = assess_pr(pr, now, threshold_minutes)
        if verdict is not None:
            out.append((str(pr.get("number") or "?"), verdict[0], verdict[1]))
    return out


def assess_workflow(bead: dict[str, Any]) -> tuple[str, str, str] | None:
    """A CLOSED workflow bead whose own outcome was not a real success.

    `status: closed` alone reads as "done". Only `metadata["gc.outcome"]`
    tells the difference between a completed workflow and one that hit
    on_fail=abort_scope and skipped every downstream step -- incident gap 6.
    """
    if str(bead.get("status") or "") != "closed":
        return None
    metadata = bead.get("metadata") or {}
    if not isinstance(metadata, dict):
        return None
    if str(metadata.get("gc.kind") or "") != "workflow":
        return None
    outcome = str(metadata.get("gc.outcome") or "")
    if outcome in {"pass", "no-op", "noop"}:
        return None
    if not outcome:
        return None
    bead_id = str(bead.get("id") or "?")
    title = _truncate(bead.get("title") or "")
    return "false_success_close", (
        f"{bead_id} closed CLOSED but gc.outcome={outcome} ({title}) -- "
        f"looks identical to a real success unless metadata is read"
    )


def assess_workflows(beads: Iterable[dict[str, Any]]) -> list[tuple[str, str, str]]:
    out = []
    for bead in beads:
        verdict = assess_workflow(bead)
        if verdict is not None:
            out.append((str(bead.get("id") or "?"), verdict[0], verdict[1]))
    return out


_ASSESSORS = {
    "gates": (assess_gates, GATE_AGE_MINUTES_DEFAULT, "FACTORY_WATCHDOG_GATE_MINUTES"),
    "prs": (assess_prs, PR_STUCK_MINUTES_DEFAULT, "FACTORY_WATCHDOG_PR_MINUTES"),
    "workflows": (None, None, None),
}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("gates", "prs", "workflows"):
        print("usage: factory_watchdog.py <gates|prs|workflows>  (reads JSON array on stdin)", file=sys.stderr)
        return 2
    subcommand = sys.argv[1]
    raw = sys.stdin.read()
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        print("unreadable\tunreadable\tinput is not valid JSON", file=sys.stderr)
        return 0
    if not isinstance(items, list):
        items = [items] if isinstance(items, dict) else []

    now = float(os.environ.get("FACTORY_GUARD_NOW") or time.time())
    if subcommand == "workflows":
        results = assess_workflows(items)
    else:
        fn, default_minutes, env_key = _ASSESSORS[subcommand]
        threshold = int(os.environ.get(env_key) or default_minutes)
        results = fn(items, now, threshold)

    for item_id, code, message in results:
        print(f"{item_id}\t{code}\t{message}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
