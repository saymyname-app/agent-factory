# ADR-0013: Continuous campaign owned by the sole Mayor

- Status: Accepted
- Date: 2026-09-15

## Context

One-shot delivery is safe, but it can leave a healthy Factory silently idle after
an authorized result is delivered. Benjamin authorized a bounded SayMyName
campaign: continue in approved candidate order while no limit, human decision,
ADMIN action, or durable failure prevents it. Product queue candidates must still
remain non-worker-ready and neither the PO nor the cockpit may become an
orchestrator.

## Decision

Campaign authority and state are stored on coordination Bead `af-1vr4`. The only
delivery orchestrator remains the existing Mayor. `bin/mayor-campaign` is the
guarded deterministic lifecycle command for `activate`, `block`, `resume`, and
`complete`; every lifecycle command requires `--mayor`. Activation also requires
that the `goal=none` campaign candidate has already been materialized by the
Mayor into its execution Bead.

The city-local `orders/mayor-campaign.toml` cooldown Order runs the `sentinel`
command once per minute. The sentinel performs zero model calls. It reads the
canonical SayMyName status once and may only:

- maintain retry and notification idempotency metadata;
- send one durable `gc mail send mayor --notify` instruction for the exact next
  authorized transition;
- persist a fail-closed `durable_failure` blocker after three consecutive
  deterministic failures.

It cannot create or materialize a candidate, dispatch an agent, merge a PR,
close product work, reorder the queue, or make a product/design decision. A mail
left `pending` by a restart is safely resent with the same key; duplicate delivery
is harmless because queue and lifecycle guards remain authoritative. A sent key
suppresses repeats until the observed result transition changes.

The persistent metadata contract is:

| Field | Meaning |
|---|---|
| `gc.campaign_mode` | `automatic` while the authorization remains effective |
| `gc.campaign_state` | `active`, `blocked`, or `completed` (derived human state may also be awaiting/running) |
| `gc.campaign_candidate` | materialized Factory campaign candidate authorizing the mode |
| `gc.campaign_condition` | exact deterministic continuation condition |
| `gc.campaign_owner` / `gc.campaign_action` | owner and exact recovery action |
| `gc.campaign_block_kind` / `gc.campaign_cause` | typed blocker and understandable cause |
| `gc.campaign_wake_key` / `gc.campaign_wake_state` | restart-safe `none|pending|sent` notification marker |
| `gc.campaign_failure_count` / `gc.campaign_last_error` | consecutive sentinel failure evidence |

`gc.resume_mode=automatic_campaign` and `gc.resume_condition` remain the shared
resume policy. Their absence or disagreement with campaign metadata fails closed.
`NEEDS BENJAMIN` remains exclusive to an effective product/design decision. An
ADMIN or durable technical blocker can name Benjamin or the Mayor as owner
without being mislabeled as a decision.

The active queue has two ordering lanes: product (`gc.queue_goal != none`) and
Factory campaign (`gc.queue_goal=none`). Materialization remains strictly limited
to the first eligible candidate in the selected lane. This lets the Mayor
materialize the campaign authorization without moving or bypassing the approved
product order; `next` remains strictly the first eligible product result.

## Consequences

- At most one product result is materialized or delivered at a time because a
  current result suppresses the next-candidate transition.
- Restart recovery is based on Beads plus durable Mayor mail, not process memory.
- A transient read/lock failure is visibly retrying; the third consecutive
  failure becomes a persistent `BLOQUÉ` state with Mayor-owned recovery.
- The global cockpit menu and Today surface render the same cause, owner, and
  exact action from `agent-factory-human-state/v1`.
- The Order adds no public listener, database, model polling, or control plane.
