#!/usr/bin/env python3
"""Wake/stop loop assessment for factory-session-loop-guard (P14, af-llc2y).

af-6675l (2026-09-28): a stale wake trigger looped one factory-worker session
~55 times in an hour (wake, do nothing useful, stop, wake again). P13 fixes
the one known cause (a stale mail-reply signal). This module is the generic
safety net Benjamin asked for on top of that fix (decisions-log.md round 2,
Q15): "whatever the cause", more than 10 wake/stop cycles on one session
within a rolling hour is itself the signal, independent of why it is
happening.

A "cycle" is one wake paired with one stop for the same session_id inside
the window -- counting session.woke alone would flag a session that woke
once and is still legitimately running a long task. Only completed cycles
(min of the two counts) indicate an actual loop.

Pure function over already-fetched JSON (the raw `gc events --since <window>`
JSON-Lines output), so it is unit-testable without gc. bin/factory-session-
loop-guard does the fetching, paging, pausing and resuming.

CLI: one subcommand, `assess`, reads JSON-Lines events on stdin and prints
one line per looping session: "<session_id>\\t<cycles>\\t<message>".
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any, Iterable

CYCLE_THRESHOLD_DEFAULT = 10
WINDOW_SECONDS_DEFAULT = 3600


def _epoch(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def assess_events(
    events: Iterable[dict[str, Any]],
    now: float,
    window_seconds: int = WINDOW_SECONDS_DEFAULT,
    threshold: int = CYCLE_THRESHOLD_DEFAULT,
) -> list[tuple[str, int, str]]:
    """Sessions whose wake/stop cycle count in the window exceeds threshold.

    Returns a list of (session_id, cycles, message) sorted by session_id,
    for every session where cycles > threshold (i.e. threshold=10 needs 11
    completed cycles to trigger, matching the acceptance criteria: "11
    wake/stop cycles in an hour trigger one alert and a pause; 10 do not").
    """
    cutoff = now - window_seconds
    wakes: dict[str, int] = {}
    stops: dict[str, int] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        ts = _epoch(event.get("ts"))
        if ts is None or ts < cutoff or ts > now:
            continue
        session_id = str(event.get("session_id") or "").strip()
        if not session_id:
            continue
        event_type = str(event.get("type") or "")
        if event_type == "session.woke":
            wakes[session_id] = wakes.get(session_id, 0) + 1
        elif event_type == "session.stopped":
            stops[session_id] = stops.get(session_id, 0) + 1

    results: list[tuple[str, int, str]] = []
    for session_id in sorted(set(wakes) | set(stops)):
        cycles = min(wakes.get(session_id, 0), stops.get(session_id, 0))
        if cycles > threshold:
            window_minutes = window_seconds // 60
            message = (
                f"session {session_id} woke and stopped {cycles} times in the "
                f"last {window_minutes}m (threshold {threshold})"
            )
            results.append((session_id, cycles, message))
    return results


def _cmd_assess(argv: list[str]) -> int:
    now = None
    window_seconds = WINDOW_SECONDS_DEFAULT
    threshold = CYCLE_THRESHOLD_DEFAULT
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--now" and i + 1 < len(argv):
            now = float(argv[i + 1]); i += 2
        elif arg == "--window-seconds" and i + 1 < len(argv):
            window_seconds = int(argv[i + 1]); i += 2
        elif arg == "--threshold" and i + 1 < len(argv):
            threshold = int(argv[i + 1]); i += 2
        else:
            print(f"assess: unknown argument: {arg}", file=sys.stderr)
            return 2
    if now is None:
        now = datetime.now(timezone.utc).timestamp()

    events: list[dict[str, Any]] = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            events.extend(item for item in parsed if isinstance(item, dict))
        elif isinstance(parsed, dict):
            events.append(parsed)

    for session_id, cycles, message in assess_events(
        events, now, window_seconds=window_seconds, threshold=threshold
    ):
        print(f"{session_id}\t{cycles}\t{message}")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] != "assess":
        print("usage: factory_session_loop.py assess [--now EPOCH] [--window-seconds N] [--threshold N]", file=sys.stderr)
        return 2
    return _cmd_assess(argv[1:])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
