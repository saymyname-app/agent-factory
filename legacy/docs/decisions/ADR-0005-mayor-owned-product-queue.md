# ADR-0005: Mayor-owned product candidate queue

- Status: Accepted
- Date: 2026-09-14

## Context

Benjamin needs to capture more than one future product outcome, inspect a clean
ordered view, and revise that order without reading issues, worker sessions, or
logs. Directly making every idea executable would pollute `bd ready`, encourage
the PO to orchestrate workers, and compete with the Mayor.

## Decision

Represent product candidates as deferred Beads with explicit product, state,
rank, urgency, and goal metadata. Expose them through the generic
`bin/product-queue` projection and product wrappers. The PO may manage candidate
intent and order under RECORD authority. Only the Mayor may convert the first
eligible candidate into a separate executable Bead, and the Mayor remains owner
of dependencies, dispatch, recovery, delivery, and closure.

Exact order and urgency are separate. Paused candidates retain their positions
but are skipped. Reordering affects only unmaterialized candidates and never
interrupts active delivery.

## Consequences

- Benjamin gets a concise, durable queue usable from desktop or phone.
- Beads remains the single durable work store; there is no second scheduler.
- Candidates cannot become worker-ready before Mayor materialization.
- Product ordering stays separate from implementation dependencies and runtime
  priority.
- The queue can be adapted to another product with a thin wrapper and goal ID.
- Mayor consumption is deliberately explicit rather than a hidden polling loop.
