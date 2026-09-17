#!/usr/bin/env python3
"""Pure logic for the Factory's named improvement axes and maintain-alive switch.

docs/FACTORY_CONTINUITY.md sec1/sec4, ADR-0016 sec7. Mirrors the split already
proven by lib/provider_failover.py: policy (config/factory-improvement-axes.json)
is versioned and human-edited -- axis names, scope boundaries, defaults. State
(.gc/runtime/factory-improvement-axes-state.json) is host-local and
cockpit/CLI-mutable -- which axes are currently on/off and whether
maintain-alive itself is on, overriding the policy defaults. No I/O here; the
caller (bin/factory-improvement-axes, bin/mayor-campaign) owns file reads,
writes and locking.

The master switch answers "the release-target queue is empty, now what". When
on (the required default), an empty queue draws from a bounded, named axis
instead of idling. When off, the whole idle ladder beyond the release target
stays quiet and the campaign goes idle *by switch*, not by stall -- a
distinct, cockpit-visible reason, never silence (see factory_campaign.plan_idle_ladder).

Each axis independently gates whether it may be selected at all. A
`draft_only` axis is for a scope boundary that is itself a reserved-class
decision (ADR-0015 sec3 / ADR-0016 sec8, e.g. a new auth provider): it is
still selectable, but the caller must only ever turn it into a
human-reviewable proposal, never dispatched executable work. That contract is
enforced by `select_improvement_axis` returning `action: "propose"` for it,
never `"dispatch"`.
"""

from __future__ import annotations

from typing import Any

AXES_POLICY_CONTRACT = "factory-improvement-axes/v1"
REQUIRED_AXIS_FIELDS = {
    "name", "description", "scope_boundary", "default_enabled", "draft_only", "mechanism",
}


class AxesPolicyError(ValueError):
    pass


def validate_policy(value: Any) -> dict[str, Any]:
    """Validate config/factory-improvement-axes.json against its documented contract."""
    if not isinstance(value, dict) or value.get("contract") != AXES_POLICY_CONTRACT:
        raise AxesPolicyError(f"improvement-axes policy must declare contract {AXES_POLICY_CONTRACT!r}")
    if not isinstance(value.get("maintain_alive_default"), bool):
        raise AxesPolicyError("maintain_alive_default must be a boolean")
    axes = value.get("axes")
    if not isinstance(axes, list) or not axes:
        raise AxesPolicyError("axes must be a non-empty array")
    names: set[str] = set()
    for axis in axes:
        if not isinstance(axis, dict):
            raise AxesPolicyError("each axis must be an object")
        missing = REQUIRED_AXIS_FIELDS - axis.keys()
        if missing:
            raise AxesPolicyError(f"axis missing fields: {sorted(missing)}")
        name = axis["name"]
        if not isinstance(name, str) or not name.strip():
            raise AxesPolicyError("axis name must be non-empty text")
        if name in names:
            raise AxesPolicyError(f"duplicate axis name: {name}")
        names.add(name)
        for field in ("description", "scope_boundary"):
            if not isinstance(axis[field], str) or not axis[field].strip():
                raise AxesPolicyError(f"{name}: {field} must be non-empty text")
        for field in ("default_enabled", "draft_only"):
            if not isinstance(axis[field], bool):
                raise AxesPolicyError(f"{name}: {field} must be a boolean")
        mechanism = axis["mechanism"]
        if not isinstance(mechanism, dict) or mechanism.get("status") not in {"wired", "not_implemented"}:
            raise AxesPolicyError(f"{name}: mechanism.status must be 'wired' or 'not_implemented'")
        if mechanism["status"] == "wired" and not str(mechanism.get("ref") or "").strip():
            raise AxesPolicyError(f"{name}: a wired mechanism requires 'ref'")
    return value


def empty_state(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract": "factory-improvement-axes-state/v1",
        "maintain_alive": policy["maintain_alive_default"],
        "axes": {axis["name"]: axis["default_enabled"] for axis in policy["axes"]},
        "history": [],
    }


def normalize_state(raw: Any, policy: dict[str, Any]) -> dict[str, Any]:
    """Merge persisted live overrides with policy defaults.

    Never raises: a missing or damaged state file degrades to policy defaults,
    exactly like provider_failover.normalize_state -- a corrupt toggle file
    must not itself stop the campaign.
    """
    raw = raw if isinstance(raw, dict) else {}
    maintain_alive = raw.get("maintain_alive")
    if not isinstance(maintain_alive, bool):
        maintain_alive = policy["maintain_alive_default"]
    overrides = raw.get("axes") if isinstance(raw.get("axes"), dict) else {}
    axes = {}
    for axis in policy["axes"]:
        name = axis["name"]
        enabled = overrides.get(name)
        axes[name] = enabled if isinstance(enabled, bool) else axis["default_enabled"]
    history = raw.get("history")
    return {
        "contract": "factory-improvement-axes-state/v1",
        "maintain_alive": maintain_alive,
        "axes": axes,
        "history": list(history) if isinstance(history, list) else [],
    }


def select_improvement_axis(policy: dict[str, Any], state: dict[str, Any]) -> dict[str, Any] | None:
    """Pick the next axis to act on, in policy order.

    None when maintain-alive is off, or no enabled axis has anything to do
    this tick (every enabled axis is a `not_implemented`, non-draft stub --
    a no-op the caller need not report, matching the existing generative
    rungs' "if nothing merits it, create nothing").

    Returns ``{"name", "action", "scope_boundary", "mechanism"}`` where
    ``action`` is ``"propose"`` for a draft_only axis (never dispatched as
    executable work -- only a human-reviewable proposal bead) or
    ``"dispatch"`` for a wired, non-draft axis.
    """
    if not state.get("maintain_alive", False):
        return None
    axes_state = state.get("axes") or {}
    for axis in policy["axes"]:
        name = axis["name"]
        if not axes_state.get(name):
            continue
        if axis["draft_only"]:
            return {
                "name": name, "action": "propose",
                "scope_boundary": axis["scope_boundary"], "mechanism": axis["mechanism"],
            }
        if axis["mechanism"]["status"] == "wired":
            return {
                "name": name, "action": "dispatch",
                "scope_boundary": axis["scope_boundary"], "mechanism": axis["mechanism"],
            }
        # Enabled, non-draft, not yet implemented: a deliberate no-op for this
        # axis, not a stall -- try the next enabled axis in policy order.
        continue
    return None


def apply_control(state: dict[str, Any], policy: dict[str, Any], action: str,
                   args: dict[str, Any], by: str, at: str) -> str:
    """Mutate state for one validated human/cockpit action; return a summary."""
    names = {axis["name"] for axis in policy["axes"]}
    if action == "maintain-alive":
        state["maintain_alive"] = bool(args.get("enabled"))
        summary = "maintain-alive " + ("on" if state["maintain_alive"] else "off")
    elif action in {"enable", "disable"}:
        name = str(args.get("axis") or "")
        if name not in names:
            raise AxesPolicyError(f"unknown axis: {name!r}")
        state.setdefault("axes", {})[name] = action == "enable"
        summary = f"{name} " + ("enabled" if action == "enable" else "disabled")
    else:
        raise AxesPolicyError(f"unknown action: {action!r}")
    history = state.setdefault("history", [])
    history.append({"action": action, "args": args, "by": by, "at": at, "summary": summary})
    state["history"] = history[-15:]
    return summary
