#!/usr/bin/env python3
"""Session-boot liveness: can the named orchestrator start at all?

af-jj9u7 / af-88za4. On 2026-09-18 the Mayor session could not boot for
hours: provider-failover resolved it to a provider that hard-rejected every
attempt with an error shape the detection regexes did not recognise, so the
pool was never marked unavailable and the named session cycled
creating -> failed-create -> creating forever. Campaign-progress liveness
(legacy/lib/factory_liveness.py, ADR-0016 s5.3) never caught it: that check only
asks "is the campaign advancing", which is a question the Mayor cannot even
begin to answer while it cannot boot. Those are different failure modes and
need a different signal.

A named, always-on identity (`configured_named_mode = "always"`, e.g.
"mayor") is modelled as a chain of session beads (`issue_type = "session"`):
each boot attempt gets its own bead id, and a failed attempt CLOSES its bead
(`state = "failed-create"`) before a fresh one is created for the retry. So
"stuck" is not a property of any single bead -- it is a property of the
identity's unbroken run of creating/failed-create states, however many bead
ids that spans. This module walks the identity's session-lifecycle events
(as emitted by `gc events`, oldest first) and measures how long that streak
has been running.

CLI: reads newline-delimited `gc events` JSON objects on stdin (the shape
`gc events --payload-match bead.metadata.configured_named_mode=always`
already emits: `{"type", "ts", "payload": {"bead": {"metadata": {...}}}}`)
and prints one line per identity observed: "<identity>\\t<level>\\t<code>\\t
<message>". level is ok, info or bad; code "session-boot-stuck" is the one
factory-guard should act on.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Iterable

STUCK_STATES = frozenset({"creating", "failed-create"})
THRESHOLD_MINUTES = 15


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


def extract_record(event: dict[str, Any]) -> dict[str, Any] | None:
    """Pull the one lifecycle record this module cares about out of a raw
    `gc events` object, or None if it is not a named-always session event."""
    if not isinstance(event, dict):
        return None
    bead = (event.get("payload") or {}).get("bead")
    if not isinstance(bead, dict):
        return None
    metadata = bead.get("metadata")
    if not isinstance(metadata, dict):
        return None
    if str(metadata.get("configured_named_mode") or "") != "always":
        return None
    identity = str(metadata.get("configured_named_identity") or metadata.get("agent_name") or "").strip()
    state = str(metadata.get("state") or "").strip()
    ts = _epoch(event.get("ts"))
    if not identity or not state or ts is None:
        return None
    return {
        "identity": identity,
        "ts": ts,
        "state": state,
        "state_reason": str(metadata.get("state_reason") or "").strip(),
        "close_reason": str(metadata.get("close_reason") or "").strip(),
        "command": str(metadata.get("command") or "").strip(),
        "provider": str(metadata.get("provider") or "").strip(),
    }


def group_by_identity(events: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        record = extract_record(event)
        if record is None:
            continue
        groups.setdefault(record["identity"], []).append(record)
    for records in groups.values():
        records.sort(key=lambda r: r["ts"])
    return groups


def assess_identity(
    records: list[dict[str, Any]],
    now: float,
    threshold_minutes: int = THRESHOLD_MINUTES,
) -> tuple[str, str, str]:
    if not records:
        return "info", "no_data", "no session-lifecycle events observed for this identity"

    latest = records[-1]
    if latest["state"] not in STUCK_STATES:
        return "ok", "ok", f"{latest['identity']} is {latest['state']}"

    # Walk backward from the latest event to find where the unbroken
    # creating/failed-create streak began -- it may span several bead ids.
    streak_start = latest["ts"]
    for record in reversed(records[:-1]):
        if record["state"] not in STUCK_STATES:
            break
        streak_start = record["ts"]

    stuck_minutes = (now - streak_start) / 60
    reason = latest["state_reason"] or latest["close_reason"] or "no reason recorded"
    detail = (
        f"{latest['identity']} stuck in '{latest['state']}' for {stuck_minutes:.0f} min "
        f"(since {_hhmm(streak_start)}) -- provider={latest['provider'] or 'unknown'} "
        f"command={latest['command'] or 'unknown'} last_state_reason={reason}"
    )
    if stuck_minutes > threshold_minutes:
        return "bad", "session-boot-stuck", detail
    return "info", "booting", detail + f" (within the {threshold_minutes}-min grace window)"


# The named Mayor session sitting asleep/quarantined past this grace window is
# paged to a human (factory-guard section 7). creating/failed-create is not in
# this set: that streak already has its own alert (assess_identity above), and
# a second one here would race it.
MAYOR_PAGE_STATES = frozenset({"asleep", "quarantine", "quarantined"})
MAYOR_PAGE_MINUTES = 10


def mayor_page_since(
    mayor_session: dict[str, Any] | None,
    now: float,
    threshold_minutes: int = MAYOR_PAGE_MINUTES,
) -> str | None:
    """The mayor session's `last_active`, iff it has sat asleep/quarantined
    longer than the grace window. factory-guard dedupes paging on this value,
    so a session that flaps back to active and down again pages again, but a
    still-down session does not repeat."""
    if not isinstance(mayor_session, dict):
        return None
    state = str(mayor_session.get("state") or "").strip()
    if state not in MAYOR_PAGE_STATES:
        return None
    since = str(mayor_session.get("last_active") or "").strip()
    at = _epoch(since)
    if at is None or (now - at) / 60 <= threshold_minutes:
        return None
    return since


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--mayor-page-check":
        # factory-guard needs a bare "since" value or nothing, not a verdict line.
        now = float(os.environ.get("FACTORY_GUARD_NOW") or time.time())
        try:
            mayor_session = json.loads(os.environ.get("FACTORY_MAYOR_SESSION_JSON") or "null")
        except json.JSONDecodeError:
            mayor_session = None
        since = mayor_page_since(mayor_session if isinstance(mayor_session, dict) else None, now)
        if since:
            print(since)
        return 0
    now = float(os.environ.get("FACTORY_GUARD_NOW") or time.time())
    threshold = int(os.environ.get("FACTORY_SESSION_BOOT_MINUTES") or THRESHOLD_MINUTES)

    events: list[dict[str, Any]] = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    groups = group_by_identity(events)
    for identity in sorted(groups):
        level, code, message = assess_identity(groups[identity], now, threshold)
        print(f"{identity}\t{level}\t{code}\t{message}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
