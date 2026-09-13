# ADR-0002 — Local preview and tailnet dashboard access

- Status: Accepted
- Date: 2026-09-14
- Scope: Factory-owned SayMyName preview and Gas City operator access

## Context

Operators need a repeatable way to inspect the latest merged SayMyName
Backend and Frontend together without turning the retired project-specific
runner into a new platform. They also need remote access to Gas City's existing
loopback-only dashboard without making its operational data public.

## Decisions

1. The Factory owns a thin preview lifecycle wrapper; application repositories
   remain authoritative for application build and runtime behavior.
2. Preview source is limited to clean canonical `dev` clones exactly at, or
   safely fast-forwardable to, `origin/dev`. The wrapper fails closed when Git,
   worktree, or active-writer ownership is ambiguous.
3. Preview state is disposable. Every start creates generated synthetic
   configuration and a pinned MySQL container whose data directory is `tmpfs`;
   no persistent or production database and no production secret is accepted.
4. Application listeners and the database port stay on loopback. Cleanup acts
   only on processes, state, and a container whose exact run ownership is
   proven.
5. Remote dashboard access uses Tailscale Serve to proxy HTTPS within the
   authenticated tailnet to the unchanged Gas City loopback listener.
   Tailscale Funnel and direct non-loopback publication are prohibited.

## Consequences

- The preview is intentionally optimized for deterministic inspection, not
  production fidelity or durable local data.
- Dirty or independently developed application clones must be resolved by the
  operator; the wrapper will not stash, reset, force-update, or delete them.
- Tailnet availability depends on both Gas City and Tailscale. Recovery restores
  and verifies the loopback service before the Serve mapping.
- Changes that introduce persistent data, real credentials, public ingress, or
  a second application writer require a new security and architecture review.
