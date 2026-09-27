# ADR-0004: SayMyName PO cockpit

- Status: Accepted
- Date: 2026-09-14

## Context

Benjamin needs one product-facing interlocutor that remembers durable SayMyName
context, works from desktop or phone, and can use the existing Agent Factory
without exposing issue, agent and runtime noise. The Windows workspace already
contains the Backend and Frontend repos plus database/Flyway helpers, while the
canonical Factory runs in Ubuntu WSL.

## Decision

Use the Codex local project rooted at `C:\Dev\Projects\SayMyName` as the single PO
cockpit. Its root `AGENTS.md` is synchronized from the canonical Factory copy.
The PO owns product intent, priority, acceptance and durable decisions. It hands
one bounded outcome to the Mayor, who exclusively owns executable Beads, formulas,
dispatch, workers, recovery, branches, PR/CI/merge and operational closure. The PO
does not poll or manage those delivery steps. Explicit WSL commands bridge to
`/home/benja/agent-factory` for status and execution. Configure full host access
with on-request approvals, while retaining explicit ADMIN boundaries.

## Consequences

- Benjamin gets one concise product conversation on desktop or phone.
- Product memory is versioned and reviewable rather than trapped in chats.
- Beads/Gas City/GitHub remain the only execution truth; no second backlog exists.
- The PO cannot become a shadow Mayor; after handoff it receives product-level
  milestones instead of managing workers or delivery mechanics.
- Windows repos and local tooling stay directly usable.
- Full access increases capability and therefore requires the documented least-
  privilege behavior and explicit approval for consequential administration.
