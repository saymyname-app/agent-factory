#!/usr/bin/env python3
"""Pure logic for B09: deterministic, zero-idle-call observation of Planning
Runs, delivery progress and adaptation measures (docs/FACTORY_OBSERVE.md).

Mirrors the policy/state split lib/factory_improvement_axes.py already
proved: policy (config/factory-observe-policy.json) is versioned and
human-edited -- which roles qualify for which observed area, and which
evidence conditions gate an exemption/handoff. State
(.gc/runtime/factory-observe-state.json) is host-local and CLI-mutable -- the
last-observed snapshot per area/id and the current exemption activation. No
I/O here; the caller (bin/factory-observe) owns file reads, writes and
locking.

`observe()` is the single seam: given the previous snapshot, the current
snapshot, and evidence for each declared exemption, it computes a
structural diff, wakes the smallest qualified role once per newly actionable
fact (never a rung a bigger role would also satisfy), and updates exemption
activation only under its own declared evidence -- restoring the moment that
evidence regresses. Called twice with an unchanged snapshot and unchanged
evidence, it reports zero wakes and zero exemption transitions both times:
that is the acceptance proof for "repeated observation of unchanged state
makes zero model calls" (the caller never invokes a model when `wakes` is
empty).
"""

from __future__ import annotations

import copy
from typing import Any

POLICY_CONTRACT = "agent-factory-observe-policy/v1"
STATE_CONTRACT = "agent-factory-observe-state/v1"

REQUIRED_ROLE_FIELDS = {"name", "areas", "rank", "model", "effort"}
REQUIRED_EXEMPTION_FIELDS = {"name", "requires"}
FORBIDDEN_MODEL_TOKENS = ("astra", "fable")
ALLOWED_EFFORTS = (None, "none", "low", "medium")

NEW = "new"
CHANGED = "changed"
REMOVED = "removed"


class ObservePolicyError(ValueError):
    pass


# --- policy ------------------------------------------------------------------


def validate_policy(value: Any) -> dict[str, Any]:
    """Validate config/factory-observe-policy.json against its contract."""
    if not isinstance(value, dict) or value.get("contract") != POLICY_CONTRACT:
        raise ObservePolicyError(f"observe policy must declare contract {POLICY_CONTRACT!r}")

    roles = value.get("roles")
    if not isinstance(roles, list) or not roles:
        raise ObservePolicyError("roles must be a non-empty array")
    names: set[str] = set()
    for role in roles:
        if not isinstance(role, dict):
            raise ObservePolicyError("each role must be an object")
        missing = REQUIRED_ROLE_FIELDS - role.keys()
        if missing:
            raise ObservePolicyError(f"role missing fields: {sorted(missing)}")
        name = role["name"]
        if not isinstance(name, str) or not name.strip():
            raise ObservePolicyError("role name must be non-empty text")
        if name in names:
            raise ObservePolicyError(f"duplicate role name: {name}")
        names.add(name)
        areas = role["areas"]
        if not isinstance(areas, list) or not areas or not all(isinstance(a, str) and a for a in areas):
            raise ObservePolicyError(f"{name}: areas must be a non-empty array of non-empty strings")
        if not isinstance(role["rank"], (int, float)) or isinstance(role["rank"], bool):
            raise ObservePolicyError(f"{name}: rank must be a number (smaller = smaller/cheaper role)")
        model = role["model"]
        if model is not None and not isinstance(model, str):
            raise ObservePolicyError(f"{name}: model must be a string or null")
        if model:
            lowered = model.lower()
            for token in FORBIDDEN_MODEL_TOKENS:
                if token in lowered:
                    raise ObservePolicyError(f"{name}: model {model!r} violates the no-{token} contract")
        if role["effort"] not in ALLOWED_EFFORTS:
            raise ObservePolicyError(f"{name}: effort must be one of {ALLOWED_EFFORTS}")

    exemptions = value.get("exemptions")
    if not isinstance(exemptions, list):
        raise ObservePolicyError("exemptions must be an array")
    ex_names: set[str] = set()
    for entry in exemptions:
        if not isinstance(entry, dict):
            raise ObservePolicyError("each exemption must be an object")
        missing = REQUIRED_EXEMPTION_FIELDS - entry.keys()
        if missing:
            raise ObservePolicyError(f"exemption missing fields: {sorted(missing)}")
        name = entry["name"]
        if not isinstance(name, str) or not name.strip():
            raise ObservePolicyError("exemption name must be non-empty text")
        if name in ex_names:
            raise ObservePolicyError(f"duplicate exemption name: {name}")
        ex_names.add(name)
        requires = entry["requires"]
        if not isinstance(requires, list) or not requires or not all(isinstance(s, str) and s for s in requires):
            raise ObservePolicyError(f"{name}: requires must be a non-empty array of non-empty strings")

    return value


# --- state ---------------------------------------------------------------


def empty_state() -> dict[str, Any]:
    return {
        "contract": STATE_CONTRACT,
        "snapshot": {},
        "exemptions": {},
        "history": [],
        "live": {
            "snapshot": {},
            "exemptions": {},
            "history": [],
            "window": {},
            "events": [],
            "pending": [],
            "routes": [],
        },
    }


def normalize_state(raw: Any) -> dict[str, Any]:
    """Never raises: a missing or damaged state file degrades to empty state."""
    raw = raw if isinstance(raw, dict) else {}
    snapshot = raw.get("snapshot")
    exemptions = raw.get("exemptions")
    history = raw.get("history")
    normalized = {
        "contract": STATE_CONTRACT,
        "snapshot": copy.deepcopy(snapshot) if isinstance(snapshot, dict) else {},
        "exemptions": dict(exemptions) if isinstance(exemptions, dict) else {},
        "history": list(history) if isinstance(history, list) else [],
    }
    live = raw.get("live") if isinstance(raw.get("live"), dict) else {}
    normalized["live"] = {
        "snapshot": copy.deepcopy(live.get("snapshot")) if isinstance(live.get("snapshot"), dict) else {},
        "exemptions": dict(live.get("exemptions")) if isinstance(live.get("exemptions"), dict) else {},
        "history": list(live.get("history")) if isinstance(live.get("history"), list) else [],
        "window": copy.deepcopy(live.get("window")) if isinstance(live.get("window"), dict) else {},
        "events": copy.deepcopy(live.get("events")) if isinstance(live.get("events"), list) else [],
        "pending": copy.deepcopy(live.get("pending")) if isinstance(live.get("pending"), list) else [],
        "routes": copy.deepcopy(live.get("routes")) if isinstance(live.get("routes"), list) else [],
    }
    return normalized


# --- diff ------------------------------------------------------------------


def diff_snapshot(previous: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    """Structural diff between two `{area: {id: fact}}` snapshots.

    Deterministic and order-independent: iterates in sorted (area, id) order
    so two calls over the same inputs always produce identically ordered
    output. A fact identical to its previous value (by `==`, i.e. structural
    equality of already-parsed JSON) produces nothing -- that is what makes
    an unchanged snapshot diff to an empty list.
    """
    facts: list[dict[str, Any]] = []
    areas = sorted(set(previous) | set(current))
    for area in areas:
        prev_area = previous.get(area) or {}
        cur_area = current.get(area) or {}
        if not isinstance(prev_area, dict):
            prev_area = {}
        if not isinstance(cur_area, dict):
            cur_area = {}
        ids = sorted(set(prev_area) | set(cur_area))
        for fact_id in ids:
            before = prev_area.get(fact_id)
            after = cur_area.get(fact_id)
            if fact_id not in prev_area:
                kind = NEW
            elif fact_id not in cur_area:
                kind = REMOVED
            elif before == after:
                continue
            else:
                kind = CHANGED
            facts.append({"area": area, "id": fact_id, "kind": kind, "before": before, "after": after})
    return facts


# --- role qualification ---------------------------------------------------


def select_smallest_qualified_role(policy: dict[str, Any], area: str) -> dict[str, Any] | None:
    """The smallest (lowest-rank) role whose declared areas cover `area`.

    None when no role qualifies -- the caller must not invent a fallback
    role; an unqualified area is a policy gap to fix, not a silent escalation.
    """
    qualifying = [role for role in policy["roles"] if area in role["areas"]]
    if not qualifying:
        return None
    return min(qualifying, key=lambda role: (role["rank"], role["name"]))


def plan_wakes(facts: list[dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    """One wake per fact: the smallest qualified role plus a preserved
    evidence pointer (the fact itself, verbatim -- before/after/area/id).
    """
    wakes = []
    for fact in facts:
        role = select_smallest_qualified_role(policy, fact["area"])
        wakes.append({
            "area": fact["area"],
            "id": fact["id"],
            "kind": fact["kind"],
            "role": role["name"] if role else None,
            "evidence": {
                "area": fact["area"], "id": fact["id"], "kind": fact["kind"],
                "before": fact["before"], "after": fact["after"],
            },
        })
    return wakes


# --- exemptions / automatic handoffs --------------------------------------


def evaluate_exemption(entry: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    """Whether one exemption/handoff's declared evidence conditions hold.

    `evidence` maps signal name -> truthy/falsy. Activation requires every
    `requires` signal to be true; any missing or false signal keeps it (or
    returns it to) inactive -- this is the regression/restore path.
    """
    missing = [signal for signal in entry["requires"] if not evidence.get(signal)]
    return {"active": not missing, "missing": missing}


def apply_exemptions(
    state: dict[str, Any], policy: dict[str, Any], evidence: dict[str, Any], at: str,
) -> list[dict[str, Any]]:
    """Mutate `state["exemptions"]` in place; return only the transitions
    (activated/restored) that happened this call -- an exemption that stays
    in the same state produces no event, exactly like an unchanged fact
    produces no wake.
    """
    exemptions_state = state.setdefault("exemptions", {})
    history = state.setdefault("history", [])
    transitions: list[dict[str, Any]] = []
    for entry in policy.get("exemptions", []):
        name = entry["name"]
        result = evaluate_exemption(entry, evidence.get(name, {}) if isinstance(evidence.get(name), dict) else {})
        was_active = bool(exemptions_state.get(name, False))
        now_active = result["active"]
        if now_active != was_active:
            event = "activated" if now_active else "restored"
            transition = {"event": event, "exemption": name, "at": at, "missing": result["missing"]}
            transitions.append(transition)
            history.append(transition)
        exemptions_state[name] = now_active
    state["exemptions"] = exemptions_state
    state["history"] = history[-40:]
    return transitions


# --- the one observation seam ---------------------------------------------


def observe(
    state: dict[str, Any], policy: dict[str, Any], current_areas: dict[str, Any],
    evidence: dict[str, Any], at: str,
) -> dict[str, Any]:
    """Diff, wake, and re-evaluate exemptions in one deterministic pass.

    Mutates `state` (snapshot advances to `current_areas`, exemptions and
    history update) and returns the observable result. Calling this twice in
    a row with the same `current_areas` and `evidence` (feeding the first
    call's mutated `state` into the second) yields `wakes == []` and
    `exemption_transitions == []` both times -- the deterministic,
    idempotent-under-no-change property acceptance criterion 1 requires.
    """
    previous_areas = state.get("snapshot") or {}
    facts = diff_snapshot(previous_areas, current_areas)
    wakes = plan_wakes(facts, policy)
    transitions = apply_exemptions(state, policy, evidence, at)

    state["snapshot"] = copy.deepcopy(current_areas)
    history = state.setdefault("history", [])
    if facts:
        history.append({
            "event": "observed", "at": at, "fact_count": len(facts),
            "areas": sorted({fact["area"] for fact in facts}),
        })
    state["history"] = history[-40:]

    return {
        "action": "wake" if wakes else "none",
        "wakes": wakes,
        "exemption_transitions": transitions,
        "exemptions": dict(state.get("exemptions") or {}),
    }
