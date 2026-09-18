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

gc.campaign_progress_at is only refreshed for the transition reasons
bin/mayor-campaign's planner recognizes (active_delivery, automatic_dependency,
ladder_active) -- a phase of the current result outside that set (af-ooob8: a
review sub-session after delivery) can advance for hours without ever
touching it. Before calling that a stall, `assess` also takes the in-flight
result bead itself (`current_result`) and checks its own gc.last_heartbeat_at
/ updated_at: recent activity there is ground truth the campaign is not
stuck, independent of whether the sentinel's bookkeeping caught it.

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

# af-umyad / af-9ur0s: "the factory is up but not advancing" is true but
# useless -- on 2026-09-18 03:21Z-08:30Z it hid that no provider was
# available for the Mayor target, then that the Mayor session itself could
# not start. Both causes are readable for free from state already gathered
# elsewhere (provider-failover status, gc session list); state the first one
# that is provable before falling back to "cause unknown".
MAYOR_TARGET = "mayor"
SUSPECT_DETECTION_HOURS = 2
# creating/failed-create is already its own alert (af-jj9u7, section 7b) at a
# 15-min threshold; naming it here too would start a second, uncoordinated
# escalation timer for the same underlying event. asleep/quarantine(d) have
# no such mechanism yet, so only those page from here.
MAYOR_DOWN_STATES = frozenset({"asleep", "quarantine", "quarantined", "creating", "failed-create"})
MAYOR_PAGE_STATES = frozenset({"asleep", "quarantine", "quarantined"})
MAYOR_PAGE_MINUTES = 10


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


def _provider_cause(provider_status: dict[str, Any] | None, now: float) -> str | None:
    """None unless provider-failover proves no provider is available for the
    Mayor target. Also flags a DETECTED (not manual) exhaustion mark as
    suspect once it has stood, with no stated reset, for over two hours --
    the exact shape of the 2026-09-18 incident, where a stale mark was
    mistaken for a real quota wall."""
    if not isinstance(provider_status, dict):
        return None
    targets = provider_status.get("targets")
    target = targets.get(MAYOR_TARGET) if isinstance(targets, dict) else None
    if not isinstance(target, dict) or target.get("reason") != "all_unavailable":
        return None
    reset = _epoch(target.get("next_reset"))
    reset_txt = _hhmm(reset) if reset is not None else "reprise inconnue"
    cause = f"aucun fournisseur disponible jusqu'à {reset_txt}"
    for entry in target.get("chain") or []:
        if not (entry.get("source") == "detected" and entry.get("state") in {"exhausted", "error"}
                and entry.get("reset_known") is False):
            continue
        at = _epoch(entry.get("at"))
        if at is None or (now - at) / 3600 <= SUSPECT_DETECTION_HOURS:
            continue
        age_h = (now - at) / 3600
        evidence = str(entry.get("evidence") or "").strip() or "aucune preuve textuelle"
        cause += (
            f" — marque suspecte : {entry.get('provider')} détecté épuisé il y a {age_h:.1f} h "
            f"sans reprise connue (preuve : {evidence})"
        )
        break
    return cause


def _mayor_session_cause(mayor_session: dict[str, Any] | None) -> str | None:
    """None unless the named mayor session is provably not active."""
    if not isinstance(mayor_session, dict):
        return None
    state = str(mayor_session.get("state") or "").strip()
    if state not in MAYOR_DOWN_STATES:
        return None
    reason = str(mayor_session.get("state_reason") or "").strip()
    detail = f" ({reason})" if reason else ""
    return f"le Mayor ne démarre pas — session « {state} »{detail}"


def identify_cause(
    provider_status: dict[str, Any] | None,
    mayor_session: dict[str, Any] | None,
    now: float,
) -> str:
    """The first cause factory-guard can prove, in order (af-9ur0s): no
    provider available for the Mayor target, then the Mayor session itself
    not active, else 'cause unknown'."""
    return (
        _provider_cause(provider_status, now)
        or _mayor_session_cause(mayor_session)
        or "cause inconnue"
    )


def _current_result_activity(current_result: dict[str, Any] | None) -> float | None:
    """Most recent activity timestamp on the in-flight result itself (af-ooob8).

    gc.campaign_progress_at is only stamped for the three PROGRESS_REASONS
    the sentinel's transition planner recognizes (bin/mayor-campaign);
    a long-running phase outside that set -- a review sub-session, for
    instance -- can advance for hours without ever refreshing it. Before
    calling that silence a stall, check the result bead's own heartbeat.

    Prefer gc.last_heartbeat_at whenever it has ever been stamped for this
    result: it is a deliberate signal, written only by the code that knows
    real work happened. Only fall back to the bead's generic `updated_at`
    when no heartbeat has ever been recorded at all -- af-i64cb: `updated_at`
    moves on ANY write to the bead (a nudge, an unrelated metadata backfill,
    a label change from another script), so once heartbeats are wired for a
    result, trusting a bare `updated_at` bump on top of them can mask a
    genuine stall behind bookkeeping noise that has nothing to do with
    progress. A result that has literally never sent a heartbeat still needs
    the `updated_at` fallback, or af-ooob8's original gap reopens.
    """
    if not isinstance(current_result, dict):
        return None
    metadata = current_result.get("metadata") if isinstance(current_result.get("metadata"), dict) else {}
    heartbeat = _epoch(metadata.get("gc.last_heartbeat_at"))
    if heartbeat is not None:
        return heartbeat
    return _epoch(current_result.get("updated_at"))


def mayor_page_since(
    mayor_session: dict[str, Any] | None,
    now: float,
    threshold_minutes: int = MAYOR_PAGE_MINUTES,
) -> str | None:
    """The mayor session's `last_active` timestamp, iff it has been sitting in
    asleep/quarantine(d) for longer than the grace window -- factory-guard
    dedupes paging on this value, so a session that flaps back to active and
    down again pages again, but a still-down session does not repeat. Never
    fires for creating/failed-create: that streak already has its own alert
    (af-jj9u7, section 7b), and starting a second one here would race it
    (see MAYOR_DOWN_STATES vs. MAYOR_PAGE_STATES above)."""
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


def assess(
    metadata: dict[str, Any],
    now: float,
    liveness_minutes: int = LIVENESS_MINUTES,
    sentinel_minutes: int = SENTINEL_MINUTES,
    provider_status: dict[str, Any] | None = None,
    mayor_session: dict[str, Any] | None = None,
    current_result: dict[str, Any] | None = None,
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

    result_activity = _current_result_activity(current_result)

    def _result_active_note(age_min: float) -> tuple[str, str, str] | None:
        if result_activity is None:
            return None
        result_idle = (now - result_activity) / 60
        if result_idle > liveness_minutes:
            return None
        return "ok", "active_result", (
            f"campaign progress stamp is {age_min:.0f} min old, but the current result "
            f"was active {result_idle:.0f} min ago{failure_note}"
        )

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
            active = _result_active_note(idle)
            if active is not None:
                return active
            cause = identify_cause(provider_status, mayor_session, now)
            return "bad", "stale", (
                f"no campaign progress observed in {idle:.0f} min of watching "
                f"(since {_hhmm(watching)}) — {cause}{failure_note}"
            )
        return "info", "no_progress_stamp", (
            f"no progress observed yet, watching for {idle:.0f} min{failure_note}"
        )
    idle = (now - progress) / 60
    if idle > liveness_minutes:
        active = _result_active_note(idle)
        if active is not None:
            return active
        cause = identify_cause(provider_status, mayor_session, now)
        return "bad", "stale", (
            f"no campaign progress for {idle:.0f} min (last {_hhmm(progress)}) while the "
            f"loop itself is alive — {cause}{failure_note}"
        )
    return "ok", "ok", f"last progress {idle:.0f} min ago{failure_note}"


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--mayor-page-check":
        # Separate from the coordination-bead verdict below: factory-guard
        # needs a bare "since" value or nothing here, not a tab-separated
        # verdict line, so it can dedupe paging without parsing prose.
        now = float(os.environ.get("FACTORY_GUARD_NOW") or time.time())
        try:
            mayor_session = json.loads(os.environ.get("FACTORY_LIVENESS_MAYOR_SESSION_JSON") or "null")
        except json.JSONDecodeError:
            mayor_session = None
        since = mayor_page_since(mayor_session if isinstance(mayor_session, dict) else None, now)
        if since:
            print(since)
        return 0
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

    def _env_json(name: str) -> dict[str, Any] | None:
        raw_value = os.environ.get(name) or ""
        if not raw_value.strip():
            return None
        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    level, code, message = assess(
        metadata,
        now,
        int(os.environ.get("FACTORY_LIVENESS_MINUTES") or LIVENESS_MINUTES),
        provider_status=_env_json("FACTORY_LIVENESS_PROVIDER_STATUS_JSON"),
        mayor_session=_env_json("FACTORY_LIVENESS_MAYOR_SESSION_JSON"),
        current_result=_env_json("FACTORY_LIVENESS_CURRENT_RESULT_JSON"),
    )
    print(f"{level}\t{code}\t{message}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
