# ADR-0011 — Decision workspaces and product reference

## Status

Accepted — 2026-09-14

## Context

One shared PO chat mixed unrelated decisions, made parallel work difficult and
could create a model session before the human actually wanted help. The product
map also mixed SayMyName concepts with Factory implementation concepts.

## Decision

- Every open decision has a deterministic workspace key and exactly one Codex
  thread, created only by its first explicit human send.
- Decision threads persist locally, can run concurrently, and are reopened from
  the decision page. General PO discussions remain separate.
- Token usage is read from existing local provider journals; rendering and
  polling make zero model calls.
- The Product view contains only SayMyName reference material. PO/Mayor/Beads/
  agents/GitHub belong to the Workflow view.
- A product reference moves through conversation, visual structuring, human
  validation, durable documentation, ordered Factory delivery and evidence.
- Preview controls call the existing guarded `bin/saymyname-preview` wrapper;
  they do not implement a second process or Git policy.

## Consequences

The cockpit becomes a durable navigation layer, not a second source of truth.
Codex deep links are convenience links; thread IDs remain copyable as a robust
fallback. Product truth stays in versioned documents and delivery truth stays
in Beads, Git and CI.
