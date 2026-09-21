# Context index

Use progressive disclosure. Do not read every document by default.

| Need | Read |
|---|---|
| Factory invariants / agent bootstrap | `../AGENTS.md` |
| Comment fonctionne l'usine, de bout en bout, en français, pour Benjamin | `COMMENT_FONCTIONNE_USINE.md` |
| Codex desktop, CLI, remote/mobile protocol and authority | `OPERATOR_BRIDGE.md` |
| Human Factory cockpit, product roadmap/decisions/board, state/resume contract, agent drill-down, token usage, Mayor channel | `FACTORY_WORKSPACE_AGENTS.md`, `OPERATIONS.md`, `decisions/ADR-0012-human-state-and-resume-contract.md` |
| Integrated product PO, project/context graphs, reusable cockpit products | `PRODUCT_COCKPIT_TEMPLATE.md`, `ADD_A_PRODUCT.md`, `config/product-cockpit.schema.json`, `config/cockpit.json` |
| SayMyName product vision, priorities, unknowns | `products/saymyname/PRODUCT_CONTEXT.md` |
| SayMyName durable product decisions | `products/saymyname/DECISIONS.md` |
| SayMyName reviewed views/features and UI/UX governance | `products/saymyname/PROJECT_INVENTORY.md`, `products/saymyname/DESIGN_GOVERNANCE.md` |
| SayMyName PO cockpit instructions and Codex config | `products/saymyname/PO_WORKSPACE_AGENTS.md`, `products/saymyname/CODEX_PROJECT.toml` |
| Ordered product candidates and Mayor materialization | `PRODUCT_QUEUE.md` |
| Versioned product release contract, states, and graph-aware campaign selection | `OPERATIONS.md` (Versioned product release contract), `config/product-release.schema.json`, `decisions/ADR-0014-versioned-product-release-contract.md` |
| Project intake gate, declared autonomy, and the draft-first/confirm-by-exception protocol | `decisions/ADR-0015-project-intake-and-target-contract.md` (Intake protocol v2 section; v1 kept for its dry-run record) |
| Existing-code review tiers for takeover projects (existant/cible reconciliation) | `decisions/ADR-0021-existing-code-review-tiers.md`, `INTAKE_REVIEW_TIERS.md` |
| Full brick-by-brick audit (2026-09-17), corrected diagnoses, target design, wave plan, why the factory stalls | `FACTORY_AUDIT_2026-09-17.md`, `FACTORY_CONTINUITY.md`, `INCIDENT_2026-09-16-silent-campaign-stall.md` |
| Durable target architecture | `TARGET_ARCHITECTURE.md` |
| Current migration state, cutover and rollback | `MIGRATION.md` |
| Install/start/stop/doctor/backup/restore/recovery | `OPERATIONS.md` |
| Stopping and restarting the whole factory, and proving nothing was lost | `RUNBOOK_STOP_AND_RESTART.md` |
| A middle-of-the-night alert or a factory check with no PO session open (French) | `RUNBOOK_4H_DU_MATIN.md` |
| What `factory-guard`, `factory-resources`, `factory-doctor`, `provider-failover` and `mayor-campaign` do, and when to run them | `FACTORY_TOOLS.md` |
| Why formula exec checks are materialised inside every rig, how missing/stale managed copies self-heal after a rig re-clone or pack re-pin, and how to check them without writing | `FACTORY_TOOLS.md` (`build-gates`), `DELIVERY.md` (GUARDED build gates), `./bin/factory-build-gates` |
| Which model provider each target runs, quota walls, fallback chains, cockpit controls | `FACTORY_TOOLS.md`, `decisions/ADR-0018-automatic-provider-failover.md`, `config/provider-policy.json` |
| What the campaign does when no product work is eligible (idle ladder), liveness, wake reminders | `FACTORY_TOOLS.md`, `decisions/ADR-0016-standing-delegation-and-non-stop-campaign.md` |
| The exact standing allowlist of routine ops that no longer count as ADMIN (restart dispatcher/preview, prune merged branches, clean worktrees, rotate logs, reload city config) | `../AGENTS.md` (Standing ADMIN allowlist), `decisions/ADR-0016-standing-delegation-and-non-stop-campaign.md` (§7 row 4) |
| Named improvement axes and the maintain-alive master switch (rung 5 of the idle ladder), cockpit toggles | `FACTORY_CONTINUITY.md` (sec1/sec4), `config/factory-improvement-axes.json`, `config/factory-improvement-axes.schema.json` |
| A filed liveness defect, an aged human gate, a stuck/conflicting PR, or a CLOSED workflow hiding a non-pass outcome not getting paged | `FACTORY_TOOLS.md` (`./bin/factory-watchdog`), `INCIDENT_2026-09-16-silent-campaign-stall.md` |
| Is anything wrong that we can actually fix (vs upstream noise) | run `./bin/factory-doctor`; see `FACTORY_TOOLS.md` |
| The four conditions every factory improvement must meet | `decisions/ADR-0017-four-conditions-for-factory-improvements.md` |
| Operator dashboard, SayMyName status, and preview | `OPERATIONS.md` |
| FAST / STANDARD / GUARDED delivery contracts and gates | `DELIVERY.md` |
| Is a schema change undoable; migration declarations; what pr-autopilot holds | `DELIVERY.md` (Réversibilité par défaut), `decisions/ADR-0019-reversibility-by-default.md`, `./bin/reversibility-check` |
| Why a `git push` to `main` can be refused, and why `pr-autopilot` is unaffected | `DELIVERY.md` (Main-landing gate), `decisions/ADR-0020-main-landing-gate.md`, `./bin/factory-main-gate` |
| Why a commit/checkout/reset/merge in the live root is refused or reverted, why `bin/` executable bits self-heal, and how `mol-do-work` isolates HQ dispatches in a worktree | `decisions/ADR-0022-live-root-worktree-enforcement.md`, `.githooks/reference-transaction`, `.githooks/post-checkout`, `./bin/factory-do-work-workspace` |
| Why a real identifier can block a push, or a CI build fail on an unmarked fixture (dev-DB PII containment) | `DELIVERY.md` (Real-PII leak guard), `./bin/factory-pii-guard`, `./bin/factory-provenance-guard` |
| External Evidence Gate and reusable research format | `DELIVERY.md`, `RESEARCH_BRIEF.md` |
| A goal ships as more than one PR across rigs; the goal bead's own six proof fields aren't the whole picture | `DELIVERY.md` (Multi-repo / cross-rig delivery proof), `./bin/goal-delivery-pairs` |
| Trust boundaries, secrets, and concurrency | `SECURITY.md` |
| Structural decisions | `decisions/ADR-0001-foundation.md` through `decisions/ADR-0023-coordination-state-write-door.md` |
| Why coordination state (root pointers, semantic labels, proof fields) is written only through a door script (`product-queue`, `mayor-campaign`, `deliver-close`, `campaign-pointer`), never with `--set-metadata`, and why readers degrade instead of dying | `decisions/ADR-0023-coordination-state-write-door.md` |
| Token-efficient multi-provider orchestration proposal (routing matrix, Mayor session budget) | `PROPOSAL-token-efficient-orchestration-2026-09-15.md` |

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
- Host capacity, unsaved work, or "is the factory safe to touch": run `./bin/factory-guard --check-only` and `./bin/factory-resources`; see `FACTORY_TOOLS.md`.
- Health triage: run `./bin/factory-doctor` rather than reading raw `gc doctor` — it separates what we can fix from upstream and advisory noise.
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
