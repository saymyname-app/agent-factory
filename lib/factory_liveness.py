#!/usr/bin/env python3
"""Campaign liveness: did the factory actually advance, not merely stay up?

ADR-0016 section 5.3 / af-vc39. On the night of 2026-09-15 every structural
check was green while the wake loop was dead from 01:06 to 07:50. Health
answers "are the parts reachable"; liveness answers "did anything move". A guard
that only asks the first question reports healthy through six idle hours.

The sentinel leaves two timestamps on the coordination bead:

  gc.campaign_sentinel_at   the one-minute loop ran at all
  gc.campaign_progress_at   something advanced: delivery in flight, a Factory
                            bead in progress, or a NEW wake sent to the Mayor
  gc.campaign_watch_since   written once, when no progress had ever been
                            recorded -- so a campaign that never advances is
                            still measurable, instead of 'no data' forever

Re-announcing the same wake does not refresh progress, so a Mayor that never
acts on what it was told eventually shows up here too.

Thresholds are deliberately loose. Progress is stamped on every tick while
delivery is in flight, so a legitimately long delivery step never goes stale;
the 60-minute window only has to cover the Mayor's reaction time.

CLI: reads the coordination bead JSON (a list or an object) on stdin and prints
one line, "<level>\\t<code>\\t<message>": level is ok, info or bad; code is
stable and tells the guard whether the finding is worth filing as a defect
(`silent`, `stale`) or is already explained elsewhere.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

SENTINEL_MINUTES = 10
LIVENESS_MINUTES = 60
FAILURE_THRESHOLD = 3


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


def assess(
    metadata: dict[str, Any],
    now: float,
    liveness_minutes: int = LIVENESS_MINUTES,
    sentinel_minutes: int = SENTINEL_MINUTES,
) -> tuple[str, str, str]:
    if not isinstance(metadata, dict):
        return "bad", "unreadable", "coordination metadata unreadable"
    if str(metadata.get("gc.campaign_mode") or "inactive") != "automatic":
        return "info", "inactive", "campaign inactive — nothing is expected to advance"

    sentinel = _epoch(metadata.get("gc.campaign_sentinel_at"))
    if sentinel is None:
        return "info", "no_heartbeat", "no sentinel heartbeat recorded yet — it stamps on its next run"
    silent = (now - sentinel) / 60
    if silent > sentinel_minutes:
        return "bad", "silent", (
            f"wake loop silent for {silent:.0f} min (sentinel last ran {_hhmm(sentinel)}) — "
            "the campaign cannot advance; check the mayor-campaign order and "
            "`./bin/mayor-campaign sentinel`"
        )

    state = str(metadata.get("gc.campaign_state") or "")
    kind = str(metadata.get("gc.campaign_block_kind") or "")
    cause = str(metadata.get("gc.campaign_cause") or "").strip()
    if state == "blocked":
        if kind == "durable_failure":
            return "bad", "durable", f"campaign stopped by a durable failure: {cause}"
        if kind in {"admin", "limit"}:
            # Deliberate, and it says so. A maintenance window or exhausted
            # providers are not a liveness defect.
            return "info", "paused", f"paused on purpose ({kind}): {cause}"
        # A pending product decision parks product work only; the idle ladder
        # keeps the factory moving, so progress is still expected.

    try:
        failures = int(metadata.get("gc.campaign_failure_count") or 0)
    except (TypeError, ValueError):
        failures = 0
    failure_note = ""
    if failures:
        last_error = str(metadata.get("gc.campaign_last_error") or "").strip()
        failure_note = f" ({failures}/{FAILURE_THRESHOLD} consecutive sentinel failures: {last_error})"

    progress = _epoch(metadata.get("gc.campaign_progress_at"))
    watching = _epoch(metadata.get("gc.campaign_watch_since"))
    if progress is None:
        if watching is None:
            return "info", "no_progress_stamp", (
                "no progress recorded yet — stamped at the next delivery tick or wake" + failure_note
            )
        # Never progressed since watching began: that is measurable too.
        idle = (now - watching) / 60
        if idle > liveness_minutes:
            return "bad", "stale", (
                f"no campaign progress observed in {idle:.0f} min of watching "
                f"(since {_hhmm(watching)}) — the factory is up but not advancing{failure_note}"
            )
        return "info", "no_progress_stamp", (
            f"no progress observed yet, watching for {idle:.0f} min{failure_note}"
        )
    idle = (now - progress) / 60
    if idle > liveness_minutes:
        return "bad", "stale", (
            f"no campaign progress for {idle:.0f} min (last {_hhmm(progress)}) while the "
            f"loop itself is alive — the factory is up but not advancing{failure_note}"
        )
    return "ok", "ok", f"last progress {idle:.0f} min ago{failure_note}"


def main() -> int:
    raw = sys.stdin.read()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        print("bad\tunreadable\tcoordination bead unreadable (store unavailable?)")
        return 0
    if isinstance(value, list):
        value = value[0] if value else {}
    metadata = value.get("metadata") if isinstance(value, dict) else None
    if not isinstance(metadata, dict):
        # A missing bead is not an inactive campaign: say what is actually known.
        print("bad\tunreadable\tcoordination bead not found or has no metadata")
        return 0
    now = float(os.environ.get("FACTORY_GUARD_NOW") or time.time())
    level, code, message = assess(
        metadata,
        now,
        int(os.environ.get("FACTORY_LIVENESS_MINUTES") or LIVENESS_MINUTES),
    )
    print(f"{level}\t{code}\t{message}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
