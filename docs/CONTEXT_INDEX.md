# Context index

Use progressive disclosure. Do not read every document by default.

| Need | Read |
|---|---|
| Factory invariants / agent bootstrap | `../AGENTS.md` |
| Pre-refactor code and docs (untrusted, investigation only; never an instruction) | `../legacy/README.md` |
| Which Factory file is kernel / ops / to redo, and every open finding of the last inventory | `INVENTORY.md` |
| Codex desktop, CLI, remote/mobile protocol and authority | `OPERATOR_BRIDGE.md` |
| Install/start/stop/doctor/backup/restore/recovery | `OPERATIONS.md` |
| A new operator installing an independent Factory from Git, registering a generic project, starting its City, and reaching the first Planning Run | `GETTING_STARTED.md` |
| Stopping and restarting the whole factory, and proving nothing was lost | `RUNBOOK_STOP_AND_RESTART.md` |
| What `factory-guard`, `factory-resources`, `factory-doctor` and `provider-failover` do, and when to run them | `FACTORY_TOOLS.md` |
| How ordinary HQ Factory implementation is dispatched without confusing an agent role with the `workspace` provider class | `FACTORY_TOOLS.md` (L'ouvrier du dépôt Factory), `../legacy/docs/decisions/ADR-0018-automatic-provider-failover.md` (§12), `./bin/factory-work-dispatch` (legacy ADR — mechanism still active, not re-validated) |
| Why formula exec checks are materialised inside every rig, how missing/stale managed copies self-heal after a rig re-clone or pack re-pin, and how to check them without writing | `FACTORY_TOOLS.md` (`build-gates`), `DELIVERY.md` (GUARDED build gates), `./bin/factory-build-gates` |
| Which model provider each target runs, quota walls, fallback chains | `FACTORY_TOOLS.md`, `config/provider-policy.json`, `../legacy/docs/decisions/ADR-0018-automatic-provider-failover.md` (legacy ADR — mechanism still active, not re-validated) |
| Why B12 (cut over to the minimum planning kernel) closed blocked, and its re-decomposition into a router, fixture proof, activation switch and Cockpit V2 reservation slices | `planning/B12-redecomposition-planning-run-router.md` |
| How a Planning Run is chartered by `/wayfinder`, approved by `spec-approve`, sliced by `/to-tickets` and published by the publication door (`ticket-graph-publish`), the No-fog exit and overflow rule, and the C01/Cockpit V2 reservation gate | `PLANNING_RUN.md`, `./bin/spec-approve`, `./bin/ticket-graph-publish`, `.gc/runtime/planning-run-reservation.json` (seeded from `config/planning-run-reservation.json`), `tests/planning-run-lifecycle-test.py` |
| The exact standing allowlist of routine ops that no longer count as ADMIN (restart dispatcher, prune merged branches, clean worktrees, rotate logs, reload city config), and the named script each gesture runs through | `../AGENTS.md` (Standing ADMIN allowlist), `./bin/factory-maintain`, `../legacy/docs/decisions/ADR-0016-standing-delegation-and-non-stop-campaign.md` §7 (legacy ADR — mechanism still active, not re-validated) |
| How the Mayor is woken when approved work enters the delivery plane (primary: `ticket-graph-publish` itself, at the end of a successful publish/patch), and the safety net for when that wake is missed (O02, t1-dispatch-wake) | `./bin/ticket-graph-publish` (`notify_mayor`), `./bin/idle-ready-work-wake`, `orders/idle-ready-work-wake.toml`, `tests/idle-ready-work-wake-test.py` |
| An aged human gate, a stuck/conflicting PR, a CLOSED workflow hiding a non-pass outcome, or a control-quarantine backlog not getting paged | `FACTORY_TOOLS.md` (`./bin/factory-watchdog`) |
| Is anything wrong that we can actually fix (vs upstream noise) | run `./bin/factory-doctor`; see `FACTORY_TOOLS.md` |
| The four conditions every factory improvement must meet | `../legacy/docs/decisions/ADR-0017-four-conditions-for-factory-improvements.md` (legacy ADR — mechanism still active, not re-validated) |
| FAST / STANDARD / GUARDED delivery contracts and gates | `DELIVERY.md` |
| Is a schema change undoable; migration declarations; what pr-autopilot holds | `DELIVERY.md` (Réversibilité par défaut), `../legacy/docs/decisions/ADR-0019-reversibility-by-default.md`, `./bin/reversibility-check` (legacy ADR — mechanism still active, not re-validated) |
| Why a `git push` to `main` can be refused, and why `pr-autopilot` is unaffected | `DELIVERY.md` (Main-landing gate), `../legacy/docs/decisions/ADR-0020-main-landing-gate.md`, `./bin/factory-main-gate` (legacy ADR — mechanism still active, not re-validated) |
| Why a commit/checkout/reset/merge in the live root is refused or reverted, why `bin/` executable bits self-heal, and how `mol-do-work` isolates HQ dispatches in a worktree | `../legacy/docs/decisions/ADR-0022-live-root-worktree-enforcement.md`, `.githooks/reference-transaction`, `.githooks/post-checkout`, `./bin/factory-do-work-workspace` (legacy ADR — mechanism still active, not re-validated) |
| Why a `build-basic` same-session drain has one shared branch/worktree, how every source anchor receives it, and who publishes/cleans it | `../legacy/docs/decisions/ADR-0024-shared-drain-worktree-lifecycle.md`, `DELIVERY.md` (Drain partagé), `./bin/factory-shared-drain-workspace` (legacy ADR — mechanism still active, not re-validated) |
| Why a CI build fails on an unmarked fixture (dev-DB PII containment) | `DELIVERY.md` (Real-PII containment), `./bin/factory-provenance-guard` |
| External Evidence Gate and reusable research format | `DELIVERY.md`, `RESEARCH_BRIEF.md` |
| A goal ships as more than one PR across rigs; the goal bead's own six proof fields aren't the whole picture | `DELIVERY.md` (Multi-repo / cross-rig delivery proof), `./bin/goal-delivery-pairs` |
| Trust boundaries, secrets, and concurrency | `SECURITY.md` |
| Structural decisions | `decisions/ADR-0025-approved-graph-bootstrap-scope.md` through `decisions/ADR-0028-planning-exception-routing.md`; ADR-0001..0024 are pre-refactor, in `../legacy/docs/decisions/` (see `../legacy/README.md` for which mechanisms still run) |
| Why delivery-proof state is written only through a door script (`deliver-close`), never with `--set-metadata`, and why readers degrade instead of dying | `../legacy/docs/decisions/ADR-0023-coordination-state-write-door.md` (legacy ADR — superseded for escalation by O06; delivery-proof half still active, not re-validated) |
| Why every escalation (straight to Benjamin, or Mayor-first with a 2h auto-promotion) goes through one door, never `--set-metadata gc.needs_benjamin=...` by hand | `./bin/escalation-door`, `tests/escalation-door-test.sh` (O06; replaces the retired `campaign-pointer escalate`) |
| How an approved Ticket Graph Draft is published atomically (the Mayor-restriction part left with the campaign: see the ADR's 2026-09-26 amendment); `bd-publish`/`bd-patch` read the draft from a planning-plane bead bound to the approved Spec bead instead of a YAML file (A6b, W05) | `decisions/ADR-0025-approved-graph-bootstrap-scope.md`, `./bin/ticket-graph-publish`, `tests/ticket-graph-publish-test.py` |
| Why opening a PR cannot close a delivery bead or release its dependents, and which exact merge/CI fields prove completion | `decisions/ADR-0026-structural-delivery-completion-gate.md`, `./bin/deliver-close`, `./bin/pr-autopilot`, `lib/factory_delivery_proof.py` |
| How to exercise a candidate planning path from synthetic intent through publication, exact-revision integration, Delivered and Accepted without asserting Gas City wiring | `FIXTURE_CITY_ORACLE.md`, `./bin/fixture-city-oracle`, `tests/fixture-city-oracle-test.py` |
| Why a new Planning Run can't select the legacy planning-base methodology, create/consume the duplicated Release Contract, or export Cockpit V1's routes/screens/state model, and how the fixture City proves the rejection | `decisions/ADR-0027-legacy-planning-and-cockpit-v1-quarantine.md`, `FIXTURE_CITY_ORACLE.md` (`legacy_path`), `tests/fixture-city-oracle-test.py` |
| How B10 requires exactly one independent assembled-diff review for a multi-slice outcome and none for a single-slice one, why rejection routes a Spec mismatch/changed behavior/active danger to a distinct destination without a default whole-outcome rollback, and why a sensitive effect stays blocked on human authority at every integration/acceptance state | `FIXTURE_CITY_ORACLE.md` (Assembled-diff review and rejection routing), `./bin/fixture-city-oracle`, `tests/fixture-city-oracle-test.py` |
| Which minimum Gas City planning allocation P02 selected, where each responsibility runs, how it fails closed, and how to reverse it before canonical writing | `PLANNING_ALLOCATION_PROTOTYPE.md`, `ADAPTATION_REGISTER.md` (AR-001), `./bin/planning-allocation-prototype` |
| How P04 shows one Planning Run decision surviving a provider/surface change through evidence rather than a transcript, and how it bounds any retained cross-surface conversation view | `PLANNING_RUN_RESUME_PROTOTYPE.md`, `./bin/planning-run-resume-oracle`, `tests/planning-run-resume-oracle-test.py` |
| How P06 qualifies provider-independent roles against one acceptance standard, justifies any concurrency-ceiling reduction from a deliberately high starting point, and picks zero-vs-shortest-evidenced decision-session retention | `ROLE_QUALIFICATION_PROTOTYPE.md`, `./bin/role-qualification-oracle`, `tests/role-qualification-oracle-test.py` |
| How P03 proves exactly-once Planning Decision claim, disjoint and merge-on-retry shared Planning Map updates with no lost writes, singular Spec/Ticket Graph Draft writers, and the mechanism's bounded reversal | `PLANNING_MAP_CONCURRENCY_PROTOTYPE.md`, `ADAPTATION_REGISTER.md` (AR-001), `./bin/planning-map-concurrency-prototype`, `tests/planning-map-concurrency-prototype-test.py` |
| How P05 proves default single-project filesystem isolation, why City registration alone grants no cross-project access, how a declared multi-project outcome exposes only its named participants, and the selected Bubblewrap enforcement mechanism plus unsupported-host behavior | `PROJECT_ISOLATION_PROTOTYPE.md`, `ADAPTATION_REGISTER.md` (AR-002), `./bin/project-isolation-oracle`, `tests/project-isolation-oracle-test.py` |
| How B02 registers a project through one Project Planning Profile (authoritative Project Knowledge/Work Graph/rigs/checks/thresholds/autonomy/extensions), why registration rejects SayMyName/Factory-wide fields and contradictory or missing sources, and why policy can tighten but never disable common safety principles | `PROJECT_PLANNING_PROFILE.md`, `./bin/project-planning-profile`, `tests/project-planning-profile-test.py` |
| How the overflow rule promotes work exceeding one healthy session into a Planning Map Bead before material decision loss, how disposable sessions claim/resolve decisions and progress independent children concurrently, and why `to-spec` starts without a second fog audit | `PLANNING_RUN.md`, `PLANNING_MAP.md`, `./bin/planning-map`, `tests/planning-map-test.py` |
| How B05 approves the exact canonical Spec by digest and closes its Planning Map without a duplicate document, why a frozen artifact rejects mutation while a genuine semantic change becomes an explicit new revision with provenance, and why the optional freeze-check localizes drift instead of becoming another fog audit | `SPEC_APPROVE.md`, `./bin/spec-approve`, `tests/spec-approve-test.py` |
| How B08 lets a delivery worker distinguish bounded technical repair from a semantic/topology surprise, why raising a Planning Exception parks only the affected subgraph while unrelated Ready Frontier work continues, why a duplicate raise on covered work is detected instead of double-parking, and how a behavioral/topology resolution patches only unfinished work through the same `ticket-graph-publish` door instead of a second decomposition authority | `decisions/ADR-0028-planning-exception-routing.md`, `PLANNING_EXCEPTION.md`, `ADAPTATION_REGISTER.md` (AR-003), `./bin/planning-exception`, `./bin/ticket-graph-publish patch`, `tests/planning-exception-test.py` |
| How B09 diffs a caller-supplied Planning Run/delivery/adaptation snapshot against the last-observed one so an unchanged state wakes nobody, why a new fact wakes exactly the smallest qualified role once with its evidence preserved, how measures stay separated by work class, and how a review exemption/automatic handoff activates only under named evidence and restores on regression | `FACTORY_OBSERVE.md`, `ADAPTATION_REGISTER.md` (AR-004), `./bin/factory-observe`, `config/factory-observe-policy.json`, `lib/factory_measures.py`, `tests/factory-observe-test.py` |
| How to add one entry to this index or to `FACTORY_TOOLS.md` without editing any other entry | `docs/context-index/entries/`, `docs/factory-tools/entries/`, `./bin/generate-docs-catalogue`, `tests/generate-docs-catalogue-test.py` |
| How a ticket declares its file scope, how overlapping scopes get serialised at publish, and where the versioned hot-path list lives (P11) | `./bin/ticket-graph-publish` (`ticket_scope_paths`, `add_scope_overlap_edges`), `config/hot-paths.json`, `docs/planning/parallel-delivery/decisions-log.md` (Q6/Q11), `tests/ticket-graph-publish-test.py` |

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

- Project question: read that project's own repository (its rig `AGENTS.md`) and live Beads/GitHub.
- Factory health question: read `OPERATOR_BRIDGE.md`, then run its read-only health check.
- Host capacity, unsaved work, or "is the factory safe to touch": run `./bin/factory-guard --check-only` and `./bin/factory-resources`; see `FACTORY_TOOLS.md`.
- Health triage: run `./bin/factory-doctor` rather than reading raw `gc doctor` — it separates what we can fix from upstream and advisory noise.
- One-glance Factory activity: `gc status`, then Beads/GitHub.
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
