# ADR-0012: Human Factory state and resume contract

- Status: Accepted
- Date: 2026-09-15

## Context

The product status CLI, candidate queue, and web cockpit exposed overlapping but
different notions of “active”, “idle”, and “queued”. A healthy one-shot City
could therefore appear to be producing work while no delivery existed, and an
eligible candidate could be described as if it would start by itself. Historical
materialized candidates could also reappear as queued product work.

## Decision

All human surfaces use `agent-factory-human-state/v1`, documented by
`config/factory-human-status.schema.json` and projected by the pure
`lib/factory_state.py` transformer. The contract separates:

- infrastructure health: `available`, `degraded`, or `unavailable`;
- delivery activity: `working`, `waiting_automatic`, `waiting_action`, or
  `stopped`;
- result and candidate lifecycle, including eligible, paused, materialized,
  active, blocked, delivered, and cancelled states;
- resume semantics: whether it is automatic, its trigger or condition, its
  owner, its useful action, and whether human action is required.

`NEEDS BENJAMIN` remains reserved for a blocking decision. Asking to launch an
eligible but unscheduled candidate is an optional action. Automatic campaign
resume exists only when coordination metadata explicitly provides
`gc.resume_mode=automatic_campaign` and a non-empty `gc.resume_condition`.
There is no implicit campaign loop. A `goal=none` Factory campaign is never the
next product result.

Candidates remain `status=deferred` in Beads as a safety mechanism, but the
human label is “Éligible · non programmé” or “En pause”. The queue validates its
complete candidate inventory before filtering. Only these tuples are valid:

- `deferred` + `queued|paused`;
- `closed` + `materialized` with an execution Bead;
- `closed` + `cancelled`.

Any source or tuple inconsistency disables resume advice and exposes a degraded
or unavailable fail-closed state. Refresh remains read-only and zero-token.

## Consequences

- CLI text is a rendering of canonical JSON, not a separate state machine.
- The cockpit can show health and delivery activity simultaneously without
  combining them into “active/idle” wording.
- Materialized and cancelled candidates remain auditable in product history but
  cannot reappear in the active human queue.
- The existing Mayor remains the only orchestrator; no polling loop, LLM refresh,
  automatic dispatch, or second control plane is introduced.
