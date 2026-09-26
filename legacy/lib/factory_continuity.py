#!/usr/bin/env python3
"""Pure zero-token projection of the Factory's continuity state (docs/FACTORY_CONTINUITY.md sec5).

Takes the already-validated `agent-factory-human-state/v1` contract
(`factory_state.project_human_state`) and classifies it into exactly one of
a small, closed set of states -- no new I/O, no model call, no source this
module reads itself. This mirrors `product_release.project_release`: a pure
projection over data another zero-token layer already assembled.

docs/FACTORY_CONTINUITY.md sec5 sketched nine states from one night's
incidents. Two adjustments, both because the bead asked to "adjust to what's
actually derivable" rather than invent new instrumentation:

  - AWAITING_REVIEW and MERGING need a PR-level fact (review pending vs. CI
    green) that no work bead carries today -- pr-autopilot's own comments
    confirm no live PR state is written back onto the bead that owns the
    work (only `merge_result=merged`, once merged). Both stay in
    CONTINUITY_STATES for forward-compatibility; nothing here can reach them
    yet, which is honest, not a bug. Wiring pr-autopilot to write a live PR
    state onto the work bead is separate, future work.
  - BLOCKED_STALLED is added: `human_state.campaign.blocked` (any kind other
    than a human decision, which is AWAITING_GATE) and the bare
    `resume.mode == "blocked"` result-level stall are both real,
    already-encoded "something concrete is stuck" conditions that fit none
    of the original nine without conflating them with a human gate or an
    external failure. This is exactly the acceptance criteria's own
    "a blocked/stalled state."

The one open gap this module cannot yet close: docs/FACTORY_CONTINUITY.md
sec1 itself notes that "the release queue ran out of eligible work" (D) and
"a human turned maintain-alive off" (B) look identical without a persisted
maintain-alive toggle. That toggle now exists (`af-xe30d`:
`.gc/runtime/factory-improvement-axes-state.json` via
`bin/factory-improvement-axes status --json`, `lib/factory_improvement_axes.py`)
but is not yet read here -- this module's own contract is a pure projection
of the already-computed `human_state`, and the toggle lives one layer below
that, in the ladder's own tick (`factory_campaign.plan_idle_ladder`'s
`maintain_alive` parameter). Wiring `maintain_alive` into `human_state` (or
into this projection directly) so STOPPED_HUMAN can widen to cover it is
separate, follow-on work. STOPPED_HUMAN is therefore still kept narrow here
to the two concrete signals that already exist and are unambiguous: a
persisted `admin` campaign block (a deliberate maintenance window,
factory_state.py's own `persisted_admin_window` case) and
`campaign.state == "completed"` (every release criterion proven, nothing
left to select). Anything else that looks idle falls through to IDLE_LADDER,
matching ADR-0016 sec7's "no state in which the correct action is to do
nothing."
"""

from __future__ import annotations

from typing import Any


HUMAN_STATE_CONTRACT = "agent-factory-human-state/v1"

CONTINUITY_STATES = (
    "IDLE_RELEASE_QUEUE",
    "MATERIALIZING",
    "DISPATCHING",
    "AWAITING_REVIEW",
    "AWAITING_GATE",
    "MERGING",
    "BLOCKED_STALLED",
    "IDLE_LADDER",
    "STOPPED_HUMAN",
    "BLOCKED_EXTERNAL",
)

_LABELS = {
    "IDLE_RELEASE_QUEUE": "File de release éligible",
    "MATERIALIZING": "Mayor matérialise un candidat",
    "DISPATCHING": "Travail en cours de réalisation",
    "AWAITING_REVIEW": "Pull request ouverte, revue en attente",
    "AWAITING_GATE": "Porte humaine ouverte",
    "MERGING": "CI verte, fusion automatique en attente",
    "BLOCKED_STALLED": "Bloqué",
    "IDLE_LADDER": "Échelle d'amélioration",
    "STOPPED_HUMAN": "Arrêt confirmé",
    "BLOCKED_EXTERNAL": "Infrastructure indisponible",
}

_DETAILS = {
    "IDLE_RELEASE_QUEUE": "Un candidat éligible attend d'être matérialisé.",
    "MATERIALIZING": "Un candidat a été choisi ; le Mayor est réveillé pour le matérialiser.",
    "DISPATCHING": "Un résultat est en cours de réalisation.",
    "AWAITING_REVIEW": "Une pull request est ouverte, revue en attente.",
    "AWAITING_GATE": "Une décision humaine bloque la suite.",
    "MERGING": "La CI est verte ; fusion automatique attendue.",
    "BLOCKED_STALLED": "Quelque chose de concret est bloqué et attend un diagnostic.",
    "IDLE_LADDER": "Aucun travail de release éligible ; l'échelle d'amélioration prend le relais.",
    "STOPPED_HUMAN": "Arrêt volontaire ou release cible prouvée ; aucune action attendue.",
    "BLOCKED_EXTERNAL": "Infrastructure non démarrée ou non fiable.",
}


class ContinuityContractError(ValueError):
    """The human-state contract cannot support a safe continuity projection."""


def project_continuity_state(human_state: dict[str, Any]) -> dict[str, Any]:
    """Classify an already-validated human-state contract into one continuity state."""
    if not isinstance(human_state, dict) or human_state.get("contract") != HUMAN_STATE_CONTRACT:
        raise ContinuityContractError("L'état humain fourni n'est pas un contrat v1 valide.")
    health = human_state.get("health")
    campaign = human_state.get("campaign")
    resume = human_state.get("resume")
    result = human_state.get("result")
    if not isinstance(health, dict) or health.get("state") not in {"available", "degraded", "unavailable"}:
        raise ContinuityContractError("État de santé invalide.")
    if not isinstance(campaign, dict) or not isinstance(campaign.get("enabled"), bool):
        raise ContinuityContractError("État de campagne invalide.")
    if not isinstance(resume, dict) or not resume.get("mode"):
        raise ContinuityContractError("État de reprise invalide.")
    if not isinstance(result, dict) or not result.get("state"):
        raise ContinuityContractError("État de résultat invalide.")
    result_stage = result.get("stage") or "none"

    blocker_kind = campaign.get("blocker_kind")

    if health["state"] == "unavailable":
        state = "STOPPED_HUMAN" if campaign["enabled"] and blocker_kind == "admin" else "BLOCKED_EXTERNAL"
    elif resume["mode"] == "blocking_decision":
        state = "AWAITING_GATE"
    elif campaign.get("blocked"):
        state = "STOPPED_HUMAN" if blocker_kind == "admin" else "BLOCKED_STALLED"
    elif resume["mode"] == "blocked":
        state = "BLOCKED_STALLED"
    elif campaign["enabled"] and campaign.get("state") == "completed":
        state = "STOPPED_HUMAN"
    elif campaign["enabled"] and campaign.get("state") == "awaiting_mayor":
        state = "MATERIALIZING"
    elif (
        campaign.get("state") == "running"
        or result_stage in {"active", "finalizing", "waiting_dependency", "materialized"}
        or resume["mode"] == "materialized_without_agent"
    ):
        state = "DISPATCHING"
    elif campaign["enabled"] and campaign.get("state") == "active":
        state = "IDLE_RELEASE_QUEUE"
    elif resume["mode"] == "manual" and human_state.get("next_candidate"):
        state = "IDLE_RELEASE_QUEUE"
    else:
        state = "IDLE_LADDER"

    return {
        "state": state,
        "state_label": _LABELS[state],
        "detail": _DETAILS[state],
        "states": list(CONTINUITY_STATES),
        "model_calls": 0,
    }


def record_transition(
    history: list[dict[str, Any]], state: str, timestamp: str, *, limit: int = 20,
) -> list[dict[str, Any]]:
    """Append a transition only when the state actually changed; cap the tail length."""
    if state not in CONTINUITY_STATES:
        raise ContinuityContractError(f"État de continuité inconnu: {state}.")
    if not isinstance(timestamp, str) or not timestamp.strip():
        raise ContinuityContractError("L'horodatage de transition doit être un texte non vide.")
    if not isinstance(history, list) or not all(isinstance(item, dict) for item in history):
        raise ContinuityContractError("L'historique de continuité doit être une liste d'objets.")
    if history and history[-1].get("state") == state:
        return list(history)
    updated = list(history) + [{"state": state, "since": timestamp}]
    return updated[-limit:] if limit > 0 else updated
