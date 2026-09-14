# ADR-0009: Integrated PO console, project map and private mobile access

## Status

Accepted — 2026-09-14

## Context

Benjamin needs one product-facing surface for understanding SayMyName, answering
open decisions and discussing them with the PO. The cockpit must also explain
the boundary between durable product context and the narrower execution context
seen by the Mayor and workers. The pattern must be reusable for future products
and safely reachable from a phone.

## Decision

Add a persistent Codex PO console to the cockpit. A human send creates or resumes
one local Codex thread rooted in the configured PO workspace, with the Factory as
an additional directory and full host capability. DISCUSS is non-mutating;
RECORD is an explicit instruction to persist the selected human decision. A new
discussion archives the local cockpit history without deleting the underlying
Codex thread. The PO does not dispatch workers or replace the Mayor.

Add a configuration-driven product capability graph and a context/authority
graph. Product strategy and decisions are the superior context owned by Benjamin
and the PO. The Mayor receives an authorized outcome and acceptance boundary;
agents receive only their bounded task and relevant repository context.

Keep the HTTP listener on loopback. Optional phone access uses Windows Tailscale
Serve on a dedicated HTTPS port inside the authenticated tailnet. Funnel and
direct LAN/public listeners remain prohibited.

## Consequences

- Model usage occurs only after an explicit PO or Mayor send; monitoring remains
  deterministic and zero-token.
- The PO console is powerful and therefore protected by loopback or tailnet
  identity, same-origin checks and an explicit cockpit header.
- New products reuse the schema and template rather than forking the UI.
- Conversation history is not elevated above Git, Beads, Gas City or GitHub.
