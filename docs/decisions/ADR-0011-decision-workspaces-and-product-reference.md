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
  agents/GitHub belong to the secondary Factory views.
- A product reference moves through conversation, visual structuring, human
  validation, durable documentation, ordered Factory delivery and evidence.
- Reference sources and section targets are explicit schema-v2 configuration.
  Only configured repository Markdown is parsed, and it becomes inert structured
  blocks rather than injected HTML. Stable anchors, contents, search, source path,
  file time and hash make the durable material readable and auditable.
- Capability, journey, roadmap, decision and source relationships are configured
  once, validated for dangling targets and projected bidirectionally.
- Navigation prioritizes Today, Product, Roadmap, Decisions, PO and Board.
  Enterprise decisions are secondary and collapsed; local ignore preferences are
  reversible and cannot edit, close or resolve the decision log.
- The Roadmap joins durable outcome structure with GitHub delivery proof, immutable
  active work, the live Beads candidate queue, decision gates and a separately
  labeled Factory campaign. Its write surface is RECORD-only and delegates six
  allowlisted actions to `bin/saymyname-product-queue`; materialization and other
  execution controls are absent.
- Preview controls call the existing guarded `bin/saymyname-preview` wrapper;
  they do not implement a second process or Git policy.

## Consequences

The cockpit becomes a durable navigation layer, not a second source of truth.
Codex deep links are convenience links; thread IDs remain copyable as a robust
fallback. Product truth stays in versioned documents and delivery truth stays
in Beads, Git and CI. Reference or queue source failures remain explicit rather
than being replaced with guessed content or order. Queue mutations immediately
reread Beads and refresh every local projection without model calls.
