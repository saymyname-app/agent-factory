# Context index

Use progressive disclosure. Do not read every document by default.

| Need | Read |
|---|---|
| Factory invariants / agent bootstrap | `../AGENTS.md` |
| Codex desktop, CLI, remote/mobile protocol and authority | `OPERATOR_BRIDGE.md` |
| Human Factory cockpit, product roadmap/decisions/board, state/resume contract, agent drill-down, token usage, Mayor channel | `FACTORY_WORKSPACE_AGENTS.md`, `OPERATIONS.md`, `decisions/ADR-0012-human-state-and-resume-contract.md` |
| Integrated product PO, project/context graphs, reusable cockpit products | `PRODUCT_COCKPIT_TEMPLATE.md`, `config/product-cockpit.schema.json` |
| SayMyName product vision, priorities, unknowns | `products/saymyname/PRODUCT_CONTEXT.md` |
| SayMyName durable product decisions | `products/saymyname/DECISIONS.md` |
| SayMyName reviewed views/features and UI/UX governance | `products/saymyname/PROJECT_INVENTORY.md`, `products/saymyname/DESIGN_GOVERNANCE.md` |
| SayMyName PO cockpit instructions and Codex config | `products/saymyname/PO_WORKSPACE_AGENTS.md`, `products/saymyname/CODEX_PROJECT.toml` |
| Ordered product candidates and Mayor materialization | `PRODUCT_QUEUE.md` |
| Versioned product release contract, states, and graph-aware campaign selection | `OPERATIONS.md` (Versioned product release contract), `config/product-release.schema.json`, `decisions/ADR-0014-versioned-product-release-contract.md` |
| Durable target architecture | `TARGET_ARCHITECTURE.md` |
| Current migration state, cutover and rollback | `MIGRATION.md` |
| Install/start/stop/doctor/backup/restore/recovery | `OPERATIONS.md` |
| Operator dashboard, SayMyName status, and preview | `OPERATIONS.md` |
| FAST / STANDARD / GUARDED delivery contracts and gates | `DELIVERY.md` |
| External Evidence Gate and reusable research format | `DELIVERY.md`, `RESEARCH_BRIEF.md` |
| Trust boundaries, secrets, and concurrency | `SECURITY.md` |
| Structural decisions | `decisions/ADR-0001-foundation.md` through `decisions/ADR-0014-versioned-product-release-contract.md` |

## Authority order

1. Observed runtime state: Gas City, Beads/Dolt, Git, and GitHub.
2. Versioned Factory documentation and the affected project repositories.
3. Current official upstream documentation and release notes.
4. Historical Plan directeur V2.
5. Chats and model memory as secondary context only.

When sources conflict, report the conflict and repair the highest durable source
within scope. A dated snapshot, chat summary, or generated status is never a
replacement for a live refresh before mutation.

## Minimal session bootstrap

- Product question: run `./bin/saymyname-product-status`; load nothing else unless a field needs recovery.
- Factory health question: read `OPERATOR_BRIDGE.md`, then run its read-only health check.
- One-glance Factory activity: run `./bin/factory-cockpit snapshot`; open the UI only when requested.
- Tracked change: read the root and nearest project `AGENTS.md`, the relevant Bead, and only the linked contract needed by the change.
- Architecture or policy change: also read the relevant ADRs and update/supersede them in the same change.

## Durable versus live context

Durable facts include architectural decisions, safety boundaries, commands, and
project contracts. They belong in Git. Current work, dependency state, and
coordination pointers belong in Beads. Processes, sessions, branches, commits,
PRs, and checks must be observed from their live systems. Do not embed volatile
SHAs, PIDs, open-task lists, or “currently running” claims in this index.

## Historical baseline

The DOCX *Migration Gas City + Beads — Plan directeur A à Z V2* is the approved
conceptual baseline dated 2026-09-12. It is historical/reference material now
that this repository contains verified operational documentation.

## Portable installation

For export/install use [portable installation](portable/INSTALL.md). For new or
imported project definition use [PO onboarding](portable/ONBOARDING.md).
See ADR-0012 for the isolation boundary and qualification limits.

Related operator contracts: [Codex bridge](decisions/ADR-0003-native-codex-operator-bridge.md),
[human decision center](decisions/ADR-0007-human-decision-center-and-mayor-channel.md).
[governance domains](decisions/ADR-0010-governance-domains-and-design-loop.md).
