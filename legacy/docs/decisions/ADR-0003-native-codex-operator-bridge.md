# ADR-0003 — Native Codex operator bridge

- Status: Accepted
- Date: 2026-09-14
- Scope: Human-to-Factory control surface and durable agent context

## Context

Benjamin needs one simple way to understand and steer several products from the
desktop or phone without reading Factory issues, sessions, logs, or Formula
steps. Codex already reaches the local WSL repository and can be resumed through
Codex Remote. Creating another custom bridge before proving a missing capability
would add a second security surface and another stateful component.

Agents also need enough durable context to operate safely without loading chat
history or the entire Factory documentation on every task. That context must
adapt to each rig and improve when stable lessons are discovered.

## Decisions

1. Desktop Codex, CLI Codex, and Codex Remote are the accepted human operator bridge.
2. The repository working directory and its `AGENTS.md` hierarchy bootstrap context; model memory and chats remain secondary.
3. The Mayor remains the sole product-work orchestrator. The bridge projects intent into existing Beads/Gas City work rather than creating a parallel queue.
4. Product status is presented through small read-only deterministic projections. Raw Factory detail is opt-in.
5. Factory-wide guidance lives in the root bootstrap and linked docs; project-specific guidance lives in the closest project `AGENTS.md` and repository docs.
6. Stable discoveries are promoted to the narrowest durable authority. Repeated failures should gain deterministic checks. Volatile state does not enter instruction files.
7. Host access is capability, not blanket authority. Remote use preserves the same approval, secret, production, public-exposure, spending, and destructive-action boundaries.
8. A proprietary plugin, MCP server, or public control plane is deferred until a concrete gap in the native path is observed and measured.

## Consequences

- The normal user protocol is conversational and product-oriented; knowledge of `gc`, `bd`, or GitHub is optional.
- BenForge and Codex must remain available for remote/mobile operation.
- Changes to `AGENTS.md` are verified in a fresh session because instructions are loaded at task/session start.
- Context stays token-light through progressive disclosure and a concise root bootstrap.
- Adding a project requires its own minimal operating contract instead of copying SayMyName or Factory-wide rules.
- Notifications can later consume verified product events, but cannot become another backlog or authority.
