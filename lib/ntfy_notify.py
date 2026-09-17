#!/usr/bin/env python3
"""Turn a factory-cockpit snapshot into ntfy.sh phone-push alerts.

Wave 0-bis (2026-09-17 audit, docs/FACTORY_AUDIT_2026-09-17.md, finding C1):
"no code path can reach a human". Benjamin chose ntfy.sh as the phone push
channel. This module is the pure, testable half -- it reads a cockpit
snapshot (the same JSON `bin/factory-cockpit snapshot` already produces) and
decides which findings are alert-worthy, each with a stable key so the
caller can dedupe/throttle instead of re-notifying every cooldown tick.

It never talks to the network -- see `bin/ntfy-notify` for the thin CLI that
runs the snapshot, calls `compute_alerts`, and POSTs to ntfy.sh.
"""
from __future__ import annotations

from typing import Any


def compute_alerts(snapshot: dict[str, Any]) -> list[dict[str, str]]:
    """Return the alert-worthy findings in a cockpit snapshot.

    Each alert is {"key", "title", "message", "priority"} with priority one
    of "urgent" or "default". An empty list means the factory needs nothing
    from Benjamin right now.
    """
    alerts: list[dict[str, str]] = []
    human = snapshot.get("human_state") or {}

    needs = human.get("needs_benjamin") or snapshot.get("needs_benjamin")
    if needs:
        alerts.append({
            "key": "needs_benjamin",
            "title": "Decision requise",
            "message": str(needs),
            "priority": "urgent",
        })

    resume = human.get("resume") or {}
    if resume.get("required"):
        alerts.append({
            "key": f"resume:{resume.get('mode') or 'unknown'}",
            "title": "Action requise pour reprendre",
            "message": str(
                resume.get("prompt") or resume.get("action") or "La Factory attend une action."
            ),
            "priority": "urgent",
        })

    campaign = human.get("campaign") or {}
    if campaign.get("blocked"):
        kind = str(campaign.get("blocker_kind") or "inconnu")
        cause = str(campaign.get("cause") or "sans cause precisee")
        alerts.append({
            "key": f"campaign_blocked:{kind}",
            "title": f"Campagne bloquee ({kind})",
            "message": cause,
            # A deliberate admin pause or an exhausted provider quota is not
            # an emergency; anything else stalls delivery silently otherwise.
            "priority": "default" if kind in {"admin", "limit"} else "urgent",
        })

    for warning in snapshot.get("warnings") or []:
        text = warning if isinstance(warning, str) else str(
            warning.get("message") if isinstance(warning, dict) else warning
        )
        alerts.append({
            "key": f"warning:{text[:80]}",
            "title": "Avertissement Factory",
            "message": text,
            "priority": "default",
        })

    return alerts


def diff_alerts(
    alerts: list[dict[str, str]],
    state: dict[str, float],
    now: float,
    remind_seconds: int = 3600,
) -> tuple[list[dict[str, str]], list[str]]:
    """Split alerts into (due, resolved_keys) against previously-sent state.

    `state` maps alert key -> epoch seconds of the last notification for that
    key. An alert is due the first time its key appears, or again once
    `remind_seconds` has passed while it is still active -- a stuck decision
    keeps paging instead of going silent, the exact gap the audit found
    ("the sentinel sends at most 3 reminders then silence"). `resolved_keys`
    are state entries that no longer appear in `alerts`, for a one-time
    "back to normal" notice.
    """
    active_keys = {a["key"] for a in alerts}
    due = [
        a for a in alerts
        if a["key"] not in state or now - state[a["key"]] >= remind_seconds
    ]
    resolved = [key for key in state if key not in active_keys]
    return due, resolved
