# ADR-0008: Product operations cockpit and token observability

## Status

Accepted — 2026-09-14

## Context

The first human cockpit made current Factory activity understandable, but it did
not connect execution to the complete product direction. Benjamin also needed to
inspect useful agent activity and token consumption without reading Gas City
internals or asking a model to summarize every refresh.

## Decision

Extend the loopback cockpit with six human views: Today, Roadmap, Decisions,
Work, Agents, and Tokens. Product intent is projected deterministically from the
versioned SayMyName strategy and decision log. Live work remains projected from
Beads, Gas City, Git and GitHub signals. Product cards and active agents expose
bounded, on-demand details; obvious credentials are redacted and private hidden
reasoning is never exposed.

Token counters are also read on demand. Codex usage comes from the latest local
provider token record for the correlated session. Claude usage comes from its
correlated local session log when possible and otherwise from the provider's
rounded live display. The UI labels scope and confidence and does not infer euro
cost. Its monitoring path still makes zero model calls.

The cockpit remains a projection and a bounded human-to-Mayor channel. It does
not dispatch, interrupt, retry, merge, recover or replace the SayMyName PO. The
Mayor remains the only Factory orchestrator.

## Consequences

- The operator can move from product direction to execution evidence without
  interpreting internal workflow noise.
- Durable product memory is reviewable in Git and survives chat history.
- Detailed transcripts and token scans happen only when requested, keeping the
  default refresh light.
- Token totals describe provider accounting, including cached input; they are
  not a bill or a normalized cross-provider cost.

