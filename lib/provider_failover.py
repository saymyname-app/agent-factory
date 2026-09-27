#!/usr/bin/env python3
"""Automatic model-provider failover -- pure logic (ADR-0018, af-ogyq).

Until 2026-09-16 a quota wall was handled by a human: city.toml carried
"REVERT TO provider = codex WHEN THE CODEX QUOTA RESETS", and whoever noticed
the exhaustion edited the file by hand, then had to remember to edit it back.

This module decides, from three inputs, which provider every target should run:

  policy  config/provider-policy.json -- versioned defaults: pools, providers,
          and one ordered fallback chain per target.
  state   .gc/provider-state.json -- host-local runtime: what was detected,
          what Benjamin marked or disabled via `provider-failover set`, chain overrides.
  now     wall-clock time, injected so every rule is testable.

A *pool* is what a quota applies to. Every Claude profile shares one Anthropic
account, so one "session limit" exhausts claude, claude-standard and
claude-cheap together. Codex's standard pool and the Spark allocation are
separate. Exhaustion is tracked per pool, never per provider.

The only side effect is producing text: the generated `city.provider.toml`
overlay. bin/provider-failover owns the I/O.
"""
from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

POLICY_CONTRACT = "agent-factory-provider-policy/v1"
STATE_CONTRACT = "agent-factory-provider-state/v1"
WORKSPACE = "workspace"
HISTORY_LIMIT = 30
# af-zdiln (2026-09-20 incident): a credential problem (category="auth") is a
# fixed fault, not a rate limit -- growing its hold with accumulated strikes
# only delays recovery once the login is fixed. Every OTHER provider_error
# category keeps the exponential backoff below unchanged.
AUTH_HOLD_MINUTES = 10


class PolicyError(ValueError):
    pass


# --------------------------------------------------------------------------
# policy
# --------------------------------------------------------------------------

_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


def validate_policy(policy: Any) -> dict[str, Any]:
    if not isinstance(policy, dict) or policy.get("contract") != POLICY_CONTRACT:
        raise PolicyError(f"provider policy must declare contract {POLICY_CONTRACT}")
    pools = policy.get("pools")
    providers = policy.get("providers")
    targets = policy.get("targets")
    if not isinstance(pools, dict) or not pools:
        raise PolicyError("policy.pools must be a non-empty object")
    if not isinstance(providers, dict) or not providers:
        raise PolicyError("policy.providers must be a non-empty object")
    if not isinstance(targets, dict) or WORKSPACE not in targets:
        raise PolicyError("policy.targets must include 'workspace'")
    for name, pool in pools.items():
        if not _NAME.match(name) or not isinstance(pool, dict) or not pool.get("label"):
            raise PolicyError(f"invalid pool {name!r}")
    for name, provider in providers.items():
        if not _NAME.match(name) or not isinstance(provider, dict):
            raise PolicyError(f"invalid provider {name!r}")
        if provider.get("pool") not in pools:
            raise PolicyError(f"provider {name!r} names an unknown pool")
        if not provider.get("label"):
            raise PolicyError(f"provider {name!r} needs a label")
    for name, target in targets.items():
        if not _NAME.match(name) or not isinstance(target, dict) or not target.get("label"):
            raise PolicyError(f"invalid target {name!r}")
        chain = target.get("chain")
        if not isinstance(chain, list) or not chain:
            raise PolicyError(f"target {name!r} needs a non-empty chain")
        unknown = [p for p in chain if p not in providers]
        if unknown:
            raise PolicyError(f"target {name!r} chain names unknown providers {unknown}")
        if len(set(chain)) != len(chain):
            raise PolicyError(f"target {name!r} chain repeats a provider")
    for key in ("unknown_reset_minutes", "low_percent", "low_hold_minutes"):
        value = policy.get(key)
        if not isinstance(value, int) or value <= 0:
            raise PolicyError(f"policy.{key} must be a positive integer")
    # af-zdiln: optional, not required -- record_detection falls back to
    # AUTH_HOLD_MINUTES when absent, so older or minimal policy fixtures
    # (e.g. a test's stand-in policy) stay valid.
    if "auth_hold_minutes" in policy:
        value = policy["auth_hold_minutes"]
        if not isinstance(value, int) or value <= 0:
            raise PolicyError("policy.auth_hold_minutes must be a positive integer")
    return policy


def empty_state() -> dict[str, Any]:
    return {
        "contract": STATE_CONTRACT,
        "auto": True,
        "pools": {},        # pool -> {status, until, source, evidence, at, by, strikes}
        "disabled": {},     # provider -> {reason, at, by}
        "forced": {},       # target -> provider
        "chains": {},       # target -> [providers]   (set --action chain)
        "effective": {},    # target -> provider       (last applied)
        "parked": False,    # this tool parked the campaign and owes a resume
        "sessions": [],     # live model sessions, as seen by the last tick
        "sessions_at": None,
        "model_staleness": {},  # {checked_at, signature, bead} -- af-a1t44, daily, not per-tick
        "history": [],
    }


def normalize_state(state: Any, policy: dict[str, Any]) -> dict[str, Any]:
    """Accept any older or damaged state; never let it break resolution."""
    base = empty_state()
    if not isinstance(state, dict):
        return base
    base["auto"] = bool(state.get("auto", True))
    for key in ("pools", "disabled", "forced", "chains", "effective", "model_staleness"):
        if isinstance(state.get(key), dict):
            base[key] = deepcopy(state[key])
    if isinstance(state.get("history"), list):
        base["history"] = state["history"][-HISTORY_LIMIT:]
    base["parked"] = bool(state.get("parked", False))
    if isinstance(state.get("sessions"), list):
        base["sessions"] = [x for x in state["sessions"] if isinstance(x, dict)][:50]
    base["sessions_at"] = state.get("sessions_at")
    providers = policy["providers"]
    # Drop anything the policy no longer knows, rather than failing on it.
    base["pools"] = {k: v for k, v in base["pools"].items()
                     if k in policy["pools"] and isinstance(v, dict)}
    base["disabled"] = {k: v for k, v in base["disabled"].items() if k in providers}
    base["forced"] = {k: v for k, v in base["forced"].items()
                      if k in policy["targets"] and v in providers}
    chains = {}
    for target, chain in base["chains"].items():
        if (target in policy["targets"] and isinstance(chain, list)
                and chain and all(p in providers for p in chain)
                and len(set(chain)) == len(chain)):
            chains[target] = list(chain)
    base["chains"] = chains
    return base


# --------------------------------------------------------------------------
# detection -- patterns copied from messages actually observed on this host
# --------------------------------------------------------------------------
#
# Codex, hard (2026-09-15):
#   "You've hit your usage limit. Visit https://chatgpt.com/codex/settings/usage
#    to purchase more credits or try again at Sep 21st, 2026 7:22 AM."
# Codex, soft:
#   "Heads up, you have less than 5% of your weekly limit left."
# Claude, hard (2026-09-15):
#   "You've hit your session limit · resets 6:50pm (Europe/Paris)"

_HARD = re.compile(
    r"you['’]?ve hit your (?:usage|session|weekly|5-hour|daily|opus|sonnet)? ?limit"
    r"|usage limit reached|limit reached\|\d{10}"
    r"|credit balance is too low|insufficient_quota",
    re.I,
)
_TRANSIENT = re.compile(r"continuing shortly|retrying in \\d+|will retry", re.I)
_SOFT = re.compile(r"less than (\d{1,2})% of your (?:weekly|daily|session|5-hour)? ?limit left", re.I)
# af-s6fqv (Factory audit): a provider going unavailable for a reason other
# than quota used to be invisible -- ADR-0018 states its own known limit
# ("a provider that fails silently ... is not detected here") and it
# degraded into a generic liveness stall, indistinguishable from a dispatcher
# bug. These are additive to _HARD/_SOFT, checked only when neither matches,
# and labelled distinctly (kind="provider_error") so a human/PO reading the
# state can tell "will resolve itself at a known reset time" (quota) apart
# from "genuinely broken, needs investigation" (this).
#
# The pane also shows whatever the agent is RUNNING. A worker on the backend
# auth tests prints "401 Unauthorized", "expected:<403>", "HTTP 500",
# "Connection refused: localhost:5432" as ordinary program output, and a bare
# match on those used to mark the whole pool `error` and reset a healthy
# worker. So the category patterns below only count on a line the agent CLI
# itself wrote: one that STARTS (after its bullet/box glyphs) with the CLI's
# own error phrasing (_CLI_ERROR), or carries a phrase only the CLI/model API
# emits (_CLI_PHRASE). Deliberately conservative: a missed provider_error is
# still caught by the liveness watchdog, a false one costs a working session.
#
# Claude Code: "⎿ API Error: 401 {"type":"error","error":{"type":"authentication_error",..."
#              "API Error (Connection error.) · Retrying in 5 seconds… (attempt 3/10)"
#              "Invalid API key · Please run /login"
# Codex:       "⚠ stream error: unexpected status 503 Service Unavailable; retrying 2/5"
#              "■ stream disconnected before completion: error sending request for url"
_CLI_ERROR = re.compile(
    r"^\W{0,6}(?:API Error\b|Agent terminated\b|stream (?:error|disconnected)\b"
    r"|unexpected status \d{3}\b|exceeded retry limit\b)",
    re.I,
)
_CLI_PHRASE = (
    ("auth", re.compile(r"please run /login|oauth token has expired|invalid x-api-key", re.I)),
    ("server", re.compile(r"overloaded_error", re.I)),
    # af-88za4 (2026-09-18): a model id configured for a provider that the
    # signed-in account cannot actually use returns this hard 400 instead of
    # a quota wall -- e.g. gpt-5.3-codex-spark under a ChatGPT Plus/Pro
    # account, not an API-key org account. Previously invisible to detection,
    # so the chain kept "choosing" a provider that fails every single time,
    # looping a named session through creation forever instead of falling
    # through to the next chain entry.
    ("config", re.compile(r"invalid_request_error|model .{0,60}not supported .{0,40}account", re.I)),
)
_AUTH_ERROR = re.compile(
    r"\b40[13]\b|unauthorized|invalid api key|invalid_api_key|authentication failed"
    r"|authentication_error|api key not found|permission denied.{0,30}\bapi\b",
    re.I,
)
_NETWORK_ERROR = re.compile(
    r"connection refused|econnrefused|enotfound|getaddrinfo|dns lookup failed"
    r"|network error|could not connect|connection reset|connection timed out"
    r"|connection error|error sending request|stream disconnected",
    re.I,
)
_SERVER_ERROR = re.compile(
    r"\b5(?:0[0-9]|2[0-9])\b|internal server error|bad gateway|service unavailable"
    r"|gateway timeout|overloaded_error|\boverloaded\b",
    re.I,
)
_CODEX_AT = re.compile(
    r"try again at ([A-Z][a-z]{2})[a-z]* (\d{1,2})(?:st|nd|rd|th)?,? (\d{4}),? "
    r"(\d{1,2}):(\d{2})\s*([AP]M)", re.I)
_TRY_IN = re.compile(r"try again in (\d+)\s*(hours?|hrs?|h|minutes?|mins?|m)\b", re.I)
_CLAUDE_RESETS = re.compile(
    r"resets\s+(?:(?:on\s+)?([A-Z][a-z]{2})[a-z]*\s+(\d{1,2}),?\s+(?:at\s+)?)?"
    r"(\d{1,2})(?::(\d{2}))?\s*([ap]m)(?:\s*\(([^)]+)\))?", re.I)
_EPOCH = re.compile(r"limit reached\|(\d{10})", re.I)
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

TAIL_LINES = 25


def _zone(name: str | None, default: str) -> ZoneInfo:
    for candidate in (name, default, "UTC"):
        if not candidate:
            continue
        try:
            return ZoneInfo(candidate)
        except (ZoneInfoNotFoundError, ValueError):
            continue
    return ZoneInfo("UTC")


def _hour24(hour: int, meridiem: str) -> int:
    hour %= 12
    return hour + 12 if meridiem.lower() == "pm" else hour


def parse_reset(line: str, now: float, local_tz: str) -> float | None:
    """Best-effort reset time from one limit message; None when not stated."""
    m = _EPOCH.search(line)
    if m:
        return float(m.group(1))
    m = _CODEX_AT.search(line)
    if m:
        month = _MONTHS.get(m.group(1)[:3].lower())
        if month:
            tz = _zone(None, local_tz)
            dt = datetime(int(m.group(3)), month, int(m.group(2)),
                          _hour24(int(m.group(4)), m.group(6)), int(m.group(5)), tzinfo=tz)
            return dt.timestamp()
    m = _TRY_IN.search(line)
    if m:
        amount = int(m.group(1))
        unit = m.group(2).lower()
        return now + amount * (3600 if unit.startswith("h") else 60)
    m = _CLAUDE_RESETS.search(line)
    if m:
        tz = _zone(m.group(6), local_tz)
        today = datetime.fromtimestamp(now, tz)
        hour = _hour24(int(m.group(3)), m.group(5))
        minute = int(m.group(4) or 0)
        if m.group(1):
            month = _MONTHS.get(m.group(1)[:3].lower())
            if not month:
                return None
            dt = datetime(today.year, month, int(m.group(2)), hour, minute, tzinfo=tz)
            if dt.timestamp() < now - 86400:
                dt = dt.replace(year=today.year + 1)
        else:
            dt = today.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if dt.timestamp() <= now:
                dt += timedelta(days=1)
        return dt.timestamp()
    return None


def detect(text: str, now: float, local_tz: str = "Europe/Paris") -> dict[str, Any] | None:
    """Classify the tail of one session's pane.

    Only the last TAIL_LINES non-empty lines count: a limit message that has
    scrolled away while the session kept working is history, not state. A
    hard limit whose stated reset is already past is ignored for the same
    reason.
    """
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    tail = lines[-TAIL_LINES:]
    joined = " ".join(tail)
    for index in range(len(tail) - 1, -1, -1):
        line = tail[index]
        if _HARD.search(line):
            # The reset clause is sometimes wrapped onto the next line.
            window = " ".join(tail[index:index + 3])
            # "Usage limit reached · continuing shortly" is Claude Code's own
            # auto-retry notice, not a quota wall: it clears by itself within
            # minutes. On 2026-09-18 it was read as a wall and locked the whole
            # anthropic pool for 8 hours while the quota was fine.
            if _TRANSIENT.search(window):
                continue
            until = parse_reset(window, now, local_tz)
            if until is not None and until <= now:
                return None
            return {"kind": "exhausted", "until": until, "evidence": window[:300]}
    m = _SOFT.search(joined)
    if m:
        return {"kind": "low", "percent": int(m.group(1)), "evidence": m.group(0)}
    for index in range(len(tail) - 1, -1, -1):
        line = tail[index]
        # Only lines the agent CLI wrote count; program output does not.
        patterns = _CLI_PHRASE
        if _CLI_ERROR.search(line):
            patterns = (
                ("auth", _AUTH_ERROR), ("network", _NETWORK_ERROR), ("server", _SERVER_ERROR),
            ) + _CLI_PHRASE
        for category, pattern in patterns:
            m = pattern.search(line)
            if m:
                return {"kind": "provider_error", "category": category, "evidence": line[:300]}
    return None


# --------------------------------------------------------------------------
# state transitions
# --------------------------------------------------------------------------

def iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def epoch(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def record_detection(state: dict[str, Any], policy: dict[str, Any], pool: str,
                     finding: dict[str, Any], now: float) -> bool:
    """Merge one detection into state. Returns True when something changed."""
    if pool not in policy["pools"]:
        return False
    current = state["pools"].get(pool) or {}
    if current.get("source") == "manual" and pool_status(state, policy, pool, now)["state"] != "available":
        return False  # a human decision outranks a detection
    if finding["kind"] == "exhausted":
        until = finding.get("until")
        strikes = int(current.get("strikes") or 0)
        if until is None:
            # No stated reset: probe again later, backing off 1h, 2h, 4h, 8h --
            # one step per EXPIRED window that finds the wall still there, never
            # one step per tick. The same banner staying on screen for four
            # 2-minute ticks used to climb straight to the 8h cap (2026-09-18).
            if (current.get("status") == "exhausted" and current.get("source") == "detected"
                    and current.get("reset_known") is False
                    and (epoch(current.get("until")) or 0) > now):
                return False
            strikes += 1
            minutes = min(policy["unknown_reset_minutes"] * 2 ** (strikes - 1), 8 * 60)
            until = now + minutes * 60
        else:
            strikes = 0
        reset_known = finding.get("until") is not None
        if (current.get("status") == "exhausted" and epoch(current.get("until")) is not None
                and abs(epoch(current.get("until")) - until) < 60):
            return False
        state["pools"][pool] = {
            "status": "exhausted", "until": iso(until), "source": "detected",
            "evidence": finding.get("evidence", ""), "at": iso(now), "strikes": strikes,
            "reset_known": reset_known,
        }
        return True
    if finding["kind"] == "low":
        if finding.get("percent", 100) > policy["low_percent"]:
            return False
        if current.get("status") == "exhausted" and pool_status(state, policy, pool, now)["state"] == "exhausted":
            return False
        state["pools"][pool] = {
            "status": "low", "until": iso(now + policy["low_hold_minutes"] * 60),
            "source": "detected", "evidence": finding.get("evidence", ""),
            "at": iso(now), "percent": finding.get("percent"),
            "strikes": int(current.get("strikes") or 0),
        }
        return True
    if finding["kind"] == "provider_error":
        category = finding.get("category")
        already_error = current.get("status") == "error" and current.get("category") == category
        strikes = int(current.get("strikes") or 0) + 1 if current.get("status") == "error" else 1
        if category == "auth":
            # af-zdiln: a credential problem is a fixed fault, not a rate
            # limit -- strikes are still counted (for the human/PO reading
            # state), but the hold never grows past a small constant. Every
            # tick that still sees the error keeps the hold rolling forward
            # by that same constant; bin/provider-failover's cheap probe
            # (credential-file fingerprint) is what clears it early once the
            # login is actually fixed, rather than this backoff shrinking.
            minutes = policy.get("auth_hold_minutes", AUTH_HOLD_MINUTES)
        else:
            # Not a quota wall with a known reset: back off the same shape as
            # an unknown-reset exhaustion (1h, 2h, 4h... capped at 8h), but
            # starting short (10min) since most of these (a network blip, a
            # transient 5xx) resolve fast; a persistent one climbs the same
            # way quota's unknown-reset case does instead of hammering the
            # provider.
            minutes = min(10 * 2 ** (strikes - 1), 8 * 60)
        until = now + minutes * 60
        if (already_error and epoch(current.get("until")) is not None
                and abs(epoch(current.get("until")) - until) < 60):
            return False
        entry = {
            "status": "error", "until": iso(until), "source": "detected",
            "evidence": finding.get("evidence", ""), "at": iso(now), "strikes": strikes,
            "category": category,
        }
        if category == "auth":
            # The fingerprint is captured once, at the FIRST detection of this
            # error episode, and kept as the baseline for the whole episode --
            # never refreshed on later re-detections of the same still-broken
            # credential, or the probe would never see it change.
            entry["auth_fingerprint"] = (current.get("auth_fingerprint") if already_error
                                         else finding.get("auth_fingerprint"))
        state["pools"][pool] = entry
        return True
    return False


def pool_status(state: dict[str, Any], policy: dict[str, Any], pool: str, now: float) -> dict[str, Any]:
    entry = state["pools"].get(pool) or {}
    status = entry.get("status")
    until = epoch(entry.get("until"))
    if status in {"exhausted", "low", "error"} and (until is None or until > now):
        if entry.get("source") == "detected" and not state.get("auto", True):
            # Manual mode: detections are shown, never acted upon.
            return {"state": "available", "detected": status, "until": entry.get("until"),
                    "source": "detected", "evidence": entry.get("evidence")}
        return {"state": status, "until": entry.get("until"),
                "source": entry.get("source", "detected"),
                "evidence": entry.get("evidence"), "by": entry.get("by"),
                "at": entry.get("at"), "reset_known": entry.get("reset_known")}
    return {"state": "available"}


def provider_status(state: dict[str, Any], policy: dict[str, Any], provider: str, now: float) -> dict[str, Any]:
    disabled = state["disabled"].get(provider)
    pool = policy["providers"][provider]["pool"]
    status = dict(pool_status(state, policy, pool, now))
    status["pool"] = pool
    if disabled:
        status.update({"state": "disabled", "reason": disabled.get("reason"),
                       "by": disabled.get("by"), "source": "manual"})
    return status


def chain_for(state: dict[str, Any], policy: dict[str, Any], target: str) -> list[str]:
    return list(state["chains"].get(target) or policy["targets"][target]["chain"])


def resolve(policy: dict[str, Any], state: dict[str, Any], now: float) -> dict[str, Any]:
    """Which provider each target should run, and why."""
    out: dict[str, Any] = {}
    for target in policy["targets"]:
        chain = chain_for(state, policy, target)
        entries = [{"provider": p, **provider_status(state, policy, p, now)} for p in chain]
        forced = state["forced"].get(target)
        if forced:
            status = provider_status(state, policy, forced, now)
            out[target] = {
                "provider": forced, "reason": "forced", "chain": entries,
                "warning": None if status["state"] in {"available", "low"}
                else f"forcé sur {forced} alors qu'il est {status['state']}",
            }
            continue
        available = [e for e in entries if e["state"] == "available"]
        low = [e for e in entries if e["state"] == "low"]
        pick = (available or low or [None])[0]
        if pick is None:
            resets = [epoch(e.get("until")) for e in entries if e["state"] in {"exhausted", "error"}]
            resets = [r for r in resets if r is not None]
            out[target] = {
                "provider": None, "reason": "all_unavailable", "chain": entries,
                "next_reset": iso(min(resets)) if resets else None,
            }
            continue
        reason = "preferred" if pick["provider"] == chain[0] else "fallback"
        out[target] = {"provider": pick["provider"], "reason": reason, "chain": entries}
    return out


def render_overlay(policy: dict[str, Any], resolution: dict[str, Any],
                   previous: dict[str, str]) -> tuple[str, dict[str, str]]:
    """TOML for city.provider.toml, plus the effective map it encodes.

    A target with nothing available keeps its previous provider: writing
    nothing would silently fall back to city.toml, which is not a decision.
    """
    effective: dict[str, str] = {}
    for target, pick in resolution.items():
        provider = pick["provider"] or previous.get(target) or policy["targets"][target]["chain"][0]
        effective[target] = provider
    lines = [
        "# GENERATED by bin/provider-failover -- do not edit by hand.",
        "# Change providers from the cockpit (Fournisseurs IA) or with",
        "# `./bin/provider-failover`. city.toml includes this file, so deleting it",
        "# breaks config loading; factory-guard regenerates it if it goes missing.",
        "",
        "[workspace]",
        f'provider = "{effective[WORKSPACE]}"',
    ]
    for target in sorted(t for t in effective if t != WORKSPACE):
        lines += ["", "[[patches.agent]]", f'name = "{target}"', f'provider = "{effective[target]}"']
    return "\n".join(lines) + "\n", effective


def note(state: dict[str, Any], now: float, event: str, detail: str, by: str = "system") -> None:
    state["history"].append({"at": iso(now), "event": event, "detail": detail, "by": by})
    state["history"] = state["history"][-HISTORY_LIMIT:]


# --------------------------------------------------------------------------
# manual controls (provider-failover set) -- every one records who and when
# --------------------------------------------------------------------------

def apply_control(state: dict[str, Any], policy: dict[str, Any], action: str,
                  args: dict[str, Any], now: float, by: str) -> str:
    """Mutate state for one validated human action; return a French summary."""
    pools, providers, targets = policy["pools"], policy["providers"], policy["targets"]

    def need(value: Any, allowed: Any, label: str) -> str:
        text = str(value or "")
        if text not in allowed:
            raise PolicyError(f"{label} inconnu : {text!r}")
        return text

    if action == "auto":
        state["auto"] = bool(args.get("enabled"))
        summary = "repli automatique " + ("activé" if state["auto"] else "désactivé (manuel)")
    elif action == "mark":
        pool = need(args.get("pool"), pools, "pool")
        until = epoch(args.get("until"))
        if until is None:
            minutes = int(args.get("minutes") or 0)
            if minutes <= 0 or minutes > 14 * 24 * 60:
                raise PolicyError("indiquer une date de reprise ou une durée entre 1 min et 14 jours")
            until = now + minutes * 60
        if until <= now:
            raise PolicyError("la date de reprise doit être dans le futur")
        state["pools"][pool] = {
            "status": "exhausted", "until": iso(until), "source": "manual",
            "evidence": str(args.get("reason") or "marqué épuisé à la main")[:300],
            "at": iso(now), "by": by, "strikes": 0,
        }
        summary = f"{pools[pool]['label']} marqué épuisé jusqu'à {iso(until)}"
    elif action == "clear":
        pool = need(args.get("pool"), pools, "pool")
        state["pools"].pop(pool, None)
        summary = f"{pools[pool]['label']} rétabli"
    elif action == "disable":
        provider = need(args.get("provider"), providers, "fournisseur")
        state["disabled"][provider] = {
            "reason": str(args.get("reason") or "désactivé à la main")[:300], "at": iso(now), "by": by,
        }
        summary = f"{providers[provider]['label']} désactivé"
    elif action == "enable":
        provider = need(args.get("provider"), providers, "fournisseur")
        state["disabled"].pop(provider, None)
        summary = f"{providers[provider]['label']} réactivé"
    elif action == "force":
        target = need(args.get("target"), targets, "cible")
        provider = str(args.get("provider") or "")
        if provider in {"", "auto"}:
            state["forced"].pop(target, None)
            summary = f"{targets[target]['label']} : retour au choix automatique"
        else:
            need(provider, providers, "fournisseur")
            state["forced"][target] = provider
            summary = f"{targets[target]['label']} forcé sur {providers[provider]['label']}"
    elif action == "chain":
        target = need(args.get("target"), targets, "cible")
        chain = args.get("chain")
        if chain in (None, "", "default"):
            state["chains"].pop(target, None)
            summary = f"{targets[target]['label']} : ordre par défaut"
        else:
            if isinstance(chain, str):
                chain = [p.strip() for p in chain.split(",") if p.strip()]
            if (not isinstance(chain, list) or not chain
                    or any(p not in providers for p in chain) or len(set(chain)) != len(chain)):
                raise PolicyError("ordre invalide : fournisseurs inconnus ou répétés")
            state["chains"][target] = list(chain)
            summary = f"{targets[target]['label']} : ordre {' → '.join(chain)}"
    else:
        raise PolicyError(f"action inconnue : {action!r}")
    note(state, now, f"manual:{action}", summary, by)
    return summary


def target_of(session: dict[str, Any], policy: dict[str, Any]) -> str | None:
    """Map a live session to the policy target that governs its provider."""
    template = str(session.get("template") or "")
    if template in policy["targets"] and template != WORKSPACE:
        return template
    if not session.get("provider"):
        return None  # deterministic helpers (control dispatchers) run no model
    return WORKSPACE


# --------------------------------------------------------------------------
# model staleness (af-s6fqv part 2 / af-a1t44) -- daily, surfaces only
# --------------------------------------------------------------------------
#
# Nothing here decides which model id is right; config/model-catalog.json
# does, and only a human edits it (same "policy is human, by commit" rule as
# provider-policy.json, ADR-0018 s1). This just compares the two and reports
# a mismatch -- it never writes city.toml, city.provider.toml, or the catalog.

CATALOG_CONTRACT = "agent-factory-model-catalog/v1"


def validate_catalog(catalog: Any) -> dict[str, Any]:
    if not isinstance(catalog, dict) or catalog.get("contract") != CATALOG_CONTRACT:
        raise PolicyError(f"model catalog must declare contract {CATALOG_CONTRACT}")
    providers = catalog.get("providers")
    if not isinstance(providers, dict) or not providers:
        raise PolicyError("catalog.providers must be a non-empty object")
    for name, entry in providers.items():
        recommended = entry.get("recommended") if isinstance(entry, dict) else None
        if (not isinstance(recommended, list) or not recommended
                or not all(isinstance(m, str) and m for m in recommended)):
            raise PolicyError(f"catalog provider {name!r} needs a non-empty 'recommended' list of strings")
    return catalog


def configured_model(provider_config: dict[str, Any]) -> str | None:
    """The model id one [providers.<name>] block in city.toml actually runs.

    Claude profiles set it as option_defaults.model; Codex profiles pass it as
    `-m <id>` inside args_append. Both shapes are read here so callers don't
    need to know which family a provider belongs to.
    """
    if not isinstance(provider_config, dict):
        return None
    defaults = provider_config.get("option_defaults")
    if isinstance(defaults, dict) and defaults.get("model"):
        return str(defaults["model"])
    args = provider_config.get("args_append")
    if isinstance(args, list):
        for index, arg in enumerate(args):
            if arg == "-m" and index + 1 < len(args):
                return str(args[index + 1])
    return None


def stale_models(configured: dict[str, str], catalog_providers: dict[str, Any]) -> list[dict[str, Any]]:
    """Configured providers whose model id is not in the catalog's recommended list.

    A provider missing from the catalog, or with no configured id, is skipped:
    this flags known drift against what a human has catalogued, it never
    invents an opinion about a provider nobody has catalogued yet.
    """
    stale = []
    for provider, model_id in configured.items():
        entry = catalog_providers.get(provider)
        if not model_id or not isinstance(entry, dict):
            continue
        recommended = entry.get("recommended") or []
        if model_id not in recommended:
            stale.append({"provider": provider, "configured": model_id, "recommended": list(recommended)})
    return sorted(stale, key=lambda e: e["provider"])
