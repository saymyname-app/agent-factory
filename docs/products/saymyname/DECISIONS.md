# SayMyName product decisions

This is the concise durable decision log for the PO cockpit. Record accepted
product/operating decisions here; keep implementation progress and evidence in
Beads and GitHub.

## Accepted

### 2026-09-14 — Single PO cockpit

Benjamin's normal SayMyName entrance is the Codex local project rooted at
`C:\Dev\Projects\SayMyName`. The assistant in that project acts as the sole
product-facing PO and uses the Mayor for Factory execution.

### 2026-09-14 — Native desktop/mobile bridge

Codex desktop/CLI on BenForge plus Codex Remote on the phone is the accepted
control bridge. A custom plugin, MCP server or public dashboard is deferred until
a concrete missing capability is demonstrated.

### 2026-09-14 — One execution system

Gas City and the Mayor coordinate work, Beads stores executable outcomes and
dependencies, and GitHub proves delivery. Linear is historical reference only.

### 2026-09-14 — Full access with bounded authority

The SayMyName cockpit may be configured with full host access so it can reach the
Windows repos, local database helpers and WSL Factory. This capability never
implies permission to reveal secrets, expose services publicly, mutate production,
spend money, reboot the host or perform irreversible/destructive actions.

### 2026-09-14 — Safe database posture

Agent database inspection is read-only. Flyway owns schema migrations; persistent
migration execution needs explicit authorization and tests use isolated databases.

## Open

- Which precise onboarding outcome should be the next JIT slice.
- Primary customer/profile, business model and product success metric.
- V1 production/cloud launch criteria.

## Update rule

Add or amend an entry only after Benjamin approves or explicitly asks to record a
decision. If a new decision supersedes an old one, mark the old entry superseded
and link the replacement rather than silently rewriting history.
