#!/usr/bin/env python3
"""Watchdog assessments: aged human gates, stuck PRs, false-success workflow closes.

Incident 2026-09-16 (silent campaign stall) found three gaps the campaign-liveness
check (retired since) did not cover, because liveness only asks "is the campaign progressing" -- never
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
             metadata (incident gap 6). A failure whose new-flow ticket
             already carries a stop or a resume is code's, not paged
             (af-it6qbk).
  gh-auth    `gh auth status` failing (expired/invalid token) is invisible to
             every one of the ten gh-dependent scripts, each of which just
             fails its own way with no shared signal (Incident 2026-09-18).
  quarantine  a control step quarantined (gc:control-quarantined,
             gc.failure_reason=<reason>) reads as a normal per-step failure
             unless something aggregates it -- 126 quarantines (backend 67,
             frontend 59) over 8 days with the same failure_reason raised zero
             signal until a human review looked (af-uxz57, af-1maov). Groups
             by (rig, failure_reason) over a rolling window so one root cause
             pages once, not once per bead.
  tickets    a started ticket of a marked convoy that nobody moves: no live
             session holds it, no launch of it is open, no request of it or
             of its convoy is on Benjamin's list, and nothing was recorded
             for it within the threshold. Twice in two days a ticket sat so
             for hours -- T02R (#673), T02R2 (#687) -- and only an operator's
             own watcher noticed (af-1fvzns).

Each assessor is a pure function over already-fetched JSON, so it is
unit-testable without gc/gh. bin/factory-watchdog does the fetching, paging,
and throttled mail/bead side effects. This module only observes -- ADR-0016
section 7: a local reason may never produce a global stop, and nothing here
is allowed to resolve a gate, merge/close a PR, or reopen a workflow itself.

CLI: one subcommand per assessor, each reads a JSON array on stdin (the raw
`gc bd gate list --json` / `gh pr list --json` / `gc bd list --json` output)
and prints one line per actionable item: "<id>\\t<code>\\t<message>". An item
that is not (yet) actionable prints nothing -- silence is the expected steady
state.
"""
from __future__ import annotations

import json
from pathlib import Path
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Iterable

GATE_AGE_MINUTES_DEFAULT = 30
PR_STUCK_MINUTES_DEFAULT = 30
QUARANTINE_WINDOW_HOURS_DEFAULT = 24
TICKET_STALL_MINUTES_DEFAULT = 30
# The gates a closed or withdrawn ticket carries (lib/convoy_state.py).
CLOSING_GATES = ("ticket_end", "withdrawn")


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


DELIVERY_FLOW_CONFIG = Path(__file__).resolve().parents[1] / "config" / "delivery-flow.json"


def code_read_formulas(config: Path = DELIVERY_FLOW_CONFIG) -> frozenset[str]:
    """The formulas of the new delivery flow, as config/delivery-flow.json
    names them: bin/convoy-advance and its gates start each of their
    workflows and read its outcome themselves (docs/CONVOY_ADVANCE.md).
    An unreadable file names none: the watchdog then pages as before."""
    try:
        settings = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return frozenset()
    if not isinstance(settings, dict):
        return frozenset()
    return frozenset(
        str(value["formula"]) for value in settings.values()
        if isinstance(value, dict) and value.get("formula")
    )


def assess_workflow(
    bead: dict[str, Any], code_read: frozenset[str] | None = None,
) -> tuple[str, str, str] | None:
    """A CLOSED workflow bead whose own outcome was not a real success.

    `status: closed` alone reads as "done". Only `metadata["gc.outcome"]`
    tells the difference between a completed workflow and one that hit
    on_fail=abort_scope and skipped every downstream step -- incident gap 6.

    A workflow of a new-flow formula is out of scope: its failed outcome is
    not hidden, code reads it and resumes, relaunches or stops the ticket.
    Paging the Mayor for it asked an agent to confirm what code had already
    done on a convoy it may not touch (4 pages in 42 hours, each cleared
    untouched, 2026-10-13, af-yzo8fo.2).
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
    if code_read is None:
        code_read = code_read_formulas()
    if str(metadata.get("gc.formula_name") or "") in code_read:
        return None
    bead_id = str(bead.get("id") or "?")
    title = _truncate(bead.get("title") or "")
    return "false_success_close", (
        f"{bead_id} closed CLOSED but gc.outcome={outcome} ({title}) -- "
        f"looks identical to a real success unless metadata is read"
    )


def convoy_ticket_id(convoy: dict[str, Any]) -> str | None:
    """The new-flow ticket a workflow's input convoy works for: the tracked
    bead itself when it carries the new-flow mark (an author run), otherwise
    the `ticket: <id>` line its launcher wrote in the tracked bead's
    description (a review or evaluation launch)."""
    for dep in convoy.get("dependencies") or []:
        if not isinstance(dep, dict) or dep.get("dependency_type") != "tracks":
            continue
        metadata = dep.get("metadata") or {}
        if isinstance(metadata, dict) and metadata.get("gc.flow.mark"):
            return str(dep.get("id") or "") or None
        for line in str(dep.get("description") or "").splitlines():
            if line.startswith("ticket: ") and line[len("ticket: "):].strip():
                return line[len("ticket: "):].strip()
    return None


def _flow_record(raw: Any) -> Any:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return None
    return raw


def ticket_handled(ticket: dict[str, Any]) -> str | None:
    """Why a failed workflow of this ticket is already in code's hands: the
    ticket carries a stop (gc.flow.stop) or a resume (gc.flow.resume), both
    written by bin/convoy-state once code has read the failure and raised or
    acted on it. Paging the Mayor for it asked an agent to confirm what code
    had already done: 7 pages on mol-test-review, mol-ticket-author and
    mol-ticket-evaluation roots, the last two after ADR-0030 L7 retired
    mol-test-review from config/delivery-flow.json (af-it6qbk). A ticket
    with neither is still paged: that failure may be a real false success."""
    metadata = ticket.get("metadata") or {}
    if not isinstance(metadata, dict) or not metadata.get("gc.flow.mark"):
        return None
    stop = _flow_record(metadata.get("gc.flow.stop"))
    if isinstance(stop, dict) and stop.get("reason"):
        return f"stopped ({stop['reason']})"
    resume = _flow_record(metadata.get("gc.flow.resume"))
    entries = resume.get("entries") if isinstance(resume, dict) else None
    if isinstance(entries, list) and entries:
        return f"resumed ({len(entries)} resume(s))"
    return None


def _records(value: Any) -> Iterable[tuple[str, Any]]:
    """Every (key, value) pair of a convoy-state ticket record, nested ones included."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield key, item
            yield from _records(item)
    elif isinstance(value, list):
        for item in value:
            yield from _records(item)


def _launch_beads(ticket: dict[str, Any]) -> list[str]:
    """The beads code launched for the ticket: correction, resume, evaluation, review."""
    return [str(entry["bead"]) for key, launches in _records(ticket) if key == "launches" and isinstance(launches, list)
            for entry in launches if isinstance(entry, dict) and entry.get("bead")]


def _at_stake(ticket: dict[str, Any]) -> bool:
    """Started through the dispatch door, and neither closed nor withdrawn."""
    gates = ticket.get("gates") or {}
    return ticket.get("status") != "closed" and "dispatch" in gates and not any(g in gates for g in CLOSING_GATES)


def stalled_lookups(show: dict[str, Any]) -> list[str]:
    """The beads bin/factory-watchdog reads before assess_ticket: the convoy,
    then each ticket at stake followed by its launches."""
    ids = [str((show.get("convoy") or {}).get("id") or "")]
    for ticket in show.get("tickets") or []:
        if isinstance(ticket, dict) and _at_stake(ticket):
            ids += [str(ticket.get("id") or ""), *_launch_beads(ticket)]
    return [bead_id for bead_id in ids if bead_id]


def assess_ticket(
    ticket: dict[str, Any], convoy_id: str, now: float, alive: set[str], open_beads: set[str],
    listed: set[str], minutes: int = TICKET_STALL_MINUTES_DEFAULT,
) -> tuple[str, str] | None:
    """A ticket at stake that nobody moves (af-1fvzns): no live session holds
    it, no launch of it is open, neither it nor its convoy has a request on
    Benjamin's list, it does not wait for its blockers, and its last record is
    older than `minutes`. The record times are those convoy-state writes
    (`at`, `raised`): the pass acts within minutes of any of them."""
    if not _at_stake(ticket):
        return None
    ticket_id = str(ticket.get("id") or "")
    if ticket_id in listed or convoy_id in listed:
        return None
    if (ticket.get("session") or {}).get("name") in alive:
        return None
    if any(bead in open_beads for bead in _launch_beads(ticket)):
        return None
    exit_name = (ticket.get("exit") or {}).get("exit")
    if exit_name == "technically_blocked":
        return None
    times = [t for key, value in _records(ticket) if key in ("at", "raised") for t in [_epoch(value)] if t]
    latest = max(times) if times else None
    if latest is not None and now - latest < minutes * 60:
        return None
    stop = (ticket.get("stop") or {}).get("reason")
    state = f"arrêt {stop}" if stop else f"sortie {exit_name}" if exit_name else str(ticket.get("status") or "?")
    since = _hhmm(latest) if latest is not None else "toujours"
    return ("stalled_ticket", _truncate(
        f"{ticket_id} ({ticket.get('title') or '?'}) du convoi {convoy_id} : sans suite depuis {since} ({state}) "
        "-- aucune session, aucun lancement ouvert, aucune demande", 300))


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


def assess_workflows(beads: Iterable[dict[str, Any]]) -> list[tuple[str, str, str]]:
    out = []
    code_read = code_read_formulas()
    for bead in beads:
        verdict = assess_workflow(bead, code_read)
        if verdict is not None:
            out.append((str(bead.get("id") or "?"), verdict[0], verdict[1]))
    return out


def assess_quarantine(
    beads: Iterable[dict[str, Any]],
    rig: str,
    now: float,
    window_hours: int = QUARANTINE_WINDOW_HOURS_DEFAULT,
) -> list[tuple[str, str, str]]:
    """Group one rig's control-quarantined beads by failure_reason over a
    rolling window -> one verdict per group.

    af-uxz57: 67 backend + 59 frontend control-step beads quarantined
    (gc:control-quarantined, gc.failure_reason=control_dispatch_error) over
    8 days raised zero signal -- alerting per bead would have been 126 pages
    for one root cause. This groups by (rig, failure_reason) instead, keyed
    on gc.control_quarantined_at so the group clears itself the moment
    nothing new lands in the window; bin/factory-watchdog re-derives "still
    active" from the same query every tick, exactly like
    gh-auth does.
    """
    cutoff = now - window_hours * 3600
    groups: dict[str, list[dict[str, Any]]] = {}
    for bead in beads:
        metadata = bead.get("metadata") or {}
        if not isinstance(metadata, dict):
            continue
        if str(metadata.get("gc.control_quarantined") or "").strip().lower() != "true":
            continue
        quarantined_at = _epoch(metadata.get("gc.control_quarantined_at"))
        if quarantined_at is None or quarantined_at < cutoff:
            continue
        reason = str(metadata.get("gc.failure_reason") or "unknown")
        groups.setdefault(reason, []).append(bead)
    out = []
    for reason, items in groups.items():
        items.sort(key=lambda b: _epoch((b.get("metadata") or {}).get("gc.control_quarantined_at")) or 0)
        first_metadata = items[0].get("metadata") or {}
        first_error = _truncate(first_metadata.get("gc.controller_error") or "")
        count = len(items)
        message = (
            f"{count} control step(s) quarantined in {rig} with failure_reason={reason} "
            f"in the last {window_hours}h -- first error: {first_error}"
        )
        out.append((reason, "control_quarantined", message))
    return out


_ASSESSORS = {
    "gates": (assess_gates, GATE_AGE_MINUTES_DEFAULT, "FACTORY_WATCHDOG_GATE_MINUTES"),
    "prs": (assess_prs, PR_STUCK_MINUTES_DEFAULT, "FACTORY_WATCHDOG_PR_MINUTES"),
    "workflows": (None, None, None),
}


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


def _cli_quarantine(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            "usage: factory_watchdog.py quarantine <rig>  "
            "(reads `gc bd list --label gc:control-quarantined --json` on stdin)",
            file=sys.stderr,
        )
        return 2
    rig = argv[1]
    raw = sys.stdin.read()
    try:
        items = json.loads(raw) if raw.strip() else []
    except json.JSONDecodeError:
        print("quarantine: stdin is not valid JSON", file=sys.stderr)
        return 2
    if not isinstance(items, list):
        items = [items] if isinstance(items, dict) else []
    now = float(os.environ.get("FACTORY_GUARD_NOW") or time.time())
    window_hours = int(
        os.environ.get("FACTORY_WATCHDOG_QUARANTINE_WINDOW_HOURS")
        or QUARANTINE_WINDOW_HOURS_DEFAULT
    )
    for reason, code, message in assess_quarantine(items, rig, now, window_hours):
        print(f"{reason}\t{code}\t{message}")
    return 0


def _cli_show_row(argv: list[str]) -> int:
    """ticket-of / ticket-handled: one `gc bd show <id> --json` on stdin,
    one line out or nothing (an unreadable row answers nothing, so the
    watchdog pages as before)."""
    try:
        rows = json.loads(sys.stdin.read() or "[]")
    except json.JSONDecodeError:
        return 0
    row = rows[0] if isinstance(rows, list) and rows else rows
    if not isinstance(row, dict):
        return 0
    answer = convoy_ticket_id(row) if argv[0] == "ticket-of" else ticket_handled(row)
    if answer:
        print(answer)
    return 0


def _cli_tickets(argv: list[str]) -> int:
    """tickets: {"show": convoy-state show, "alive": [...], "open": [...],
    "listed": [...]} on stdin; ticket-lookups: one convoy-state show on
    stdin, the ids to read, one per line."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0
    if argv[0] == "ticket-lookups":
        print("\n".join(stalled_lookups(payload)))
        return 0
    show = payload.get("show") or {}
    convoy_id = str((show.get("convoy") or {}).get("id") or "")
    now = float(os.environ.get("FACTORY_GUARD_NOW") or time.time())
    minutes = int(os.environ.get("FACTORY_WATCHDOG_TICKET_MINUTES") or TICKET_STALL_MINUTES_DEFAULT)
    sets = [set(map(str, payload.get(key) or [])) for key in ("alive", "open", "listed")]
    for ticket in show.get("tickets") or []:
        if isinstance(ticket, dict):
            found = assess_ticket(ticket, convoy_id, now, *sets, minutes)
            if found:
                print(f"{ticket.get('id')}\t{found[0]}\t{found[1]}")
    return 0


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] in ("tickets", "ticket-lookups"):
        return _cli_tickets(sys.argv[1:])
    if len(sys.argv) == 2 and sys.argv[1] in ("ticket-of", "ticket-handled"):
        return _cli_show_row(sys.argv[1:])
    if len(sys.argv) >= 2 and sys.argv[1] == "gh-auth":
        return _cli_gh_auth(sys.argv[1:])
    if len(sys.argv) >= 2 and sys.argv[1] == "quarantine":
        return _cli_quarantine(sys.argv[1:])
    if len(sys.argv) != 2 or sys.argv[1] not in ("gates", "prs", "workflows"):
        print(
            "usage: factory_watchdog.py <gates|prs|workflows>  (reads JSON array on stdin)\n"
            "       factory_watchdog.py gh-auth <returncode>  (reads `gh auth status` output on stdin)\n"
            "       factory_watchdog.py quarantine <rig>  (reads gc:control-quarantined bd list --json on stdin)\n"
            "       factory_watchdog.py <ticket-of|ticket-handled>  (reads one gc bd show --json on stdin)\n"
            "       factory_watchdog.py tickets  (reads {show, alive, open, listed} on stdin)\n"
            "       factory_watchdog.py ticket-lookups  (reads one convoy-state show on stdin)",
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
