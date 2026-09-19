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
  gh-auth    `gh auth status` failing (expired/invalid token) is invisible to
             every one of the ten gh-dependent scripts, each of which just
             fails its own way with no shared signal (Incident 2026-09-18).
  stall-frequency  a single BLOCKED_STALLED transition (lib/factory_continuity.py,
             docs/FACTORY_CONTINUITY.md sec5) gets a diagnosis, but a recurring
             pattern of stalls -- the campaign stalling over and over, even if
             each one is individually resolved -- has no aggregate signal of
             its own (observability audit finding C3, 2026-09-18).

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

import fcntl
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

GATE_AGE_MINUTES_DEFAULT = 30
PR_STUCK_MINUTES_DEFAULT = 30
STALL_WINDOW_HOURS_DEFAULT = 24
STALL_THRESHOLD_DEFAULT = 5


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


def assess_gh_auth(returncode: int, output: str) -> tuple[str, str] | None:
    """`gh auth status` exiting nonzero -> every gh-dependent script fails the
    same silent way (Incident 2026-09-18: WSL's gh token expired; pr-autopilot
    ticked every 3 min with errors=3 forever on all 3 repos with zero visible
    signal until Benjamin noticed a PR never got auto-armed). Only a human can
    re-authenticate -- this only detects the gap, it never fixes it.
    """
    if returncode == 0:
        return None
    return "gh_auth_unreachable", f"gh auth status failed (exit {returncode}): {_truncate(output)}"


def stall_frequency(
    history: Iterable[dict[str, Any]],
    now: float,
    window_hours: int = STALL_WINDOW_HOURS_DEFAULT,
) -> dict[str, Any]:
    """Rolling-window count of BLOCKED_STALLED entries in continuity history.

    `history` is lib/factory_continuity.py's own `record_transition` list --
    one entry per *change* of continuity state (not one per tick), each
    `{"state": ..., "since": <iso>}`. For every BLOCKED_STALLED entry inside
    the window, the preceding entry's state (the state the campaign stalled
    *from*) is looked up positionally; the first entry in the whole recorded
    history has no predecessor, so its `preceding_state` is None -- callers
    must render that as "cause unknown" per the bead's acceptance criteria
    rather than guess.
    """
    history = list(history)
    cutoff = now - window_hours * 3600
    stalls: list[dict[str, Any]] = []
    for index, entry in enumerate(history):
        if not isinstance(entry, dict) or str(entry.get("state") or "") != "BLOCKED_STALLED":
            continue
        since = _epoch(entry.get("since"))
        if since is None or since < cutoff:
            continue
        preceding_state = None
        if index > 0 and isinstance(history[index - 1], dict):
            preceding_state = str(history[index - 1].get("state") or "") or None
        stalls.append({"since": entry.get("since"), "preceding_state": preceding_state})
    return {"count": len(stalls), "window_hours": window_hours, "stalls": stalls}


def assess_stall_frequency(
    history: Iterable[dict[str, Any]],
    now: float,
    window_hours: int = STALL_WINDOW_HOURS_DEFAULT,
    threshold_count: int = STALL_THRESHOLD_DEFAULT,
) -> tuple[str, str] | None:
    """count of BLOCKED_STALLED entries in the window >= threshold -> (code, message); else None."""
    freq = stall_frequency(history, now, window_hours)
    if freq["count"] < threshold_count:
        return None
    causes = "; ".join(
        f"{stall['since']} (from {stall['preceding_state']})"
        if stall["preceding_state"]
        else f"{stall['since']} (cause unknown)"
        for stall in freq["stalls"]
    )
    return "stall_frequency_high", (
        f"{freq['count']} BLOCKED_STALLED transitions in the last {window_hours}h "
        f"(threshold {threshold_count}): {causes}"
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


def merge_signals(
    path: str,
    source: str,
    alerts: Iterable[dict[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Read-modify-write factory-watchdog-signals.json without clobbering the
    other writers' alerts (tests/factory-cockpit-chaos-test.py's header
    comment, PR #82: three independently-scheduled scripts -- factory-watchdog,
    on-order-failed, on-session-stranded -- all write this same file, and a
    wholesale overwrite from one erases whatever another just wrote).

    Every alert this writer previously contributed (matched by its own
    "source" tag) is replaced by the fresh set passed here; every alert any
    OTHER writer contributed is left untouched. An `flock` on a sibling
    `<path>.lock` file serialises concurrent writers so a read-modify-write
    race can never interleave and drop an update.

    An entry with no "source" at all (written before this tag existed) is
    dropped rather than kept forever: every current writer always tags its
    own alerts, so an untagged entry can never be matched and replaced by
    anyone again -- it would otherwise persist in the cockpit's signal file
    indefinitely even after the finding it described was independently
    fixed (2026-09-18, the C1 observability-audit finding: 7 pre-tagging
    false_success_close alerts kept re-surfacing after the bead they named
    had already been explained/closed for over a day, because they had no
    "source" for any writer's replace-my-own-slice pass to match against).
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = str(target) + ".lock"
    generated_at = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(lock_path, "a+") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        try:
            try:
                existing = json.loads(target.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                existing = {}
            if not isinstance(existing, dict):
                existing = {}
            prior = existing.get("alerts")
            if not isinstance(prior, list):
                prior = []
            kept = [
                item for item in prior
                if isinstance(item, dict) and item.get("source") and item.get("source") != source
            ]
            fresh = []
            for item in alerts:
                if not isinstance(item, dict):
                    continue
                merged_item = dict(item)
                merged_item["source"] = source
                fresh.append(merged_item)
            out = {"generated_at": generated_at, "alerts": kept + fresh}
            tmp_path = str(target) + ".next"
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(out, fh)
            os.replace(tmp_path, target)
            return out
        finally:
            fcntl.flock(lockf, fcntl.LOCK_UN)


def _cli_gh_auth(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            "usage: factory_watchdog.py gh-auth <returncode>  "
            "(reads `gh auth status` combined output on stdin)",
            file=sys.stderr,
        )
        return 2
    try:
        returncode = int(argv[1])
    except ValueError:
        print("gh-auth: <returncode> must be an integer", file=sys.stderr)
        return 2
    output = sys.stdin.read()
    verdict = assess_gh_auth(returncode, output)
    if verdict is not None:
        code, message = verdict
        print(f"{code}\t{message}")
    return 0


def _cli_stall_frequency(argv: list[str]) -> int:
    if len(argv) != 1:
        print(
            "usage: factory_watchdog.py stall-frequency  "
            "(reads factory-continuity-history.json's \"history\" array on stdin)",
            file=sys.stderr,
        )
        return 2
    raw = sys.stdin.read()
    try:
        history = json.loads(raw) if raw.strip() else []
    except json.JSONDecodeError:
        print("stall-frequency: stdin is not valid JSON", file=sys.stderr)
        return 2
    if not isinstance(history, list):
        history = []
    now = float(os.environ.get("FACTORY_GUARD_NOW") or time.time())
    window_hours = int(os.environ.get("FACTORY_WATCHDOG_STALL_WINDOW_HOURS") or STALL_WINDOW_HOURS_DEFAULT)
    threshold = int(os.environ.get("FACTORY_WATCHDOG_STALL_THRESHOLD") or STALL_THRESHOLD_DEFAULT)
    verdict = assess_stall_frequency(history, now, window_hours, threshold)
    if verdict is not None:
        code, message = verdict
        print(f"{code}\t{message}")
    return 0


def _cli_merge_signals(argv: list[str]) -> int:
    if len(argv) != 3:
        print(
            "usage: factory_watchdog.py merge-signals <path> <source>  "
            "(reads a JSON array of {kind,id,message} on stdin)",
            file=sys.stderr,
        )
        return 2
    path, source = argv[1], argv[2]
    raw = sys.stdin.read()
    try:
        alerts = json.loads(raw) if raw.strip() else []
    except json.JSONDecodeError:
        print("merge-signals: stdin is not valid JSON", file=sys.stderr)
        return 2
    if not isinstance(alerts, list):
        alerts = [alerts] if isinstance(alerts, dict) else []
    merge_signals(path, source, alerts)
    return 0


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "merge-signals":
        return _cli_merge_signals(sys.argv[1:])
    if len(sys.argv) >= 2 and sys.argv[1] == "gh-auth":
        return _cli_gh_auth(sys.argv[1:])
    if len(sys.argv) >= 2 and sys.argv[1] == "stall-frequency":
        return _cli_stall_frequency(sys.argv[1:])
    if len(sys.argv) != 2 or sys.argv[1] not in ("gates", "prs", "workflows"):
        print(
            "usage: factory_watchdog.py <gates|prs|workflows>  (reads JSON array on stdin)\n"
            "       factory_watchdog.py gh-auth <returncode>  (reads `gh auth status` output on stdin)\n"
            "       factory_watchdog.py stall-frequency  (reads continuity history \"history\" array on stdin)\n"
            "       factory_watchdog.py merge-signals <path> <source>  (reads JSON array on stdin)",
            file=sys.stderr,
        )
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
