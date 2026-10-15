# Context index

Read one matching contract, then its references as needed. This is a router,
not a summary of every rule. Add short needs in `docs/context-index/entries/`
and regenerate with `bin/generate-docs-catalogue`; never edit this output.
Table paths are relative to `docs/`. ADR-0001..0024 describe pre-refactor
mechanisms: consult `decisions/PRE_REFACTOR.md` before relying on them.

| Need | Read |
|---|---|
| Factory invariants and bootstrap | `../AGENTS.md` |
| Pre-refactor code/docs: historical, untrusted | `decisions/PRE_REFACTOR.md` |
| Kernel/ops inventory and open findings | `INVENTORY.md` |
| Desktop, CLI and remote authority | `OPERATOR_BRIDGE.md` |
| Installation, backup and recovery | `OPERATIONS.md` |
| Install an independent Factory and register its first project | `GETTING_STARTED.md` |
| Stop/restart the Factory without losing work | `RUNBOOK_STOP_AND_RESTART.md` |
| Guard, resources, doctor and provider tools | `FACTORY_TOOLS.md` |
| Dispatch HQ work to the Factory worker | `FACTORY_TOOLS.md` |
| Materialise/repair rig build gates | `FACTORY_TOOLS.md` (build-gates), `DELIVERY.md` |
| Providers, quotas and failover | `FACTORY_TOOLS.md` |
| Claude account plugin skills and context cost | `../.claude/settings.json` |
| B12 blocked cutover and replacement slices | `planning/B12-redecomposition-planning-run-router.md` |
| Planning Run: charter, No-fog, approval, graph publication | `PLANNING_RUN.md` |
| Factory versus Direct Delivery | `PLANNING_RUN.md` |
| Standing ADMIN upkeep allowlist | `../AGENTS.md` (Standing ADMIN allowlist) |
| Wake the Mayor after publication; missed-wake safety net | `../bin/ticket-graph-publish` (notify_mayor), `../bin/idle-ready-work-wake` |
| Watchdog: stale gates, stuck PRs, hidden failed workflows | `FACTORY_TOOLS.md` |
| Health triage: actionable failures versus upstream | `FACTORY_TOOLS.md` (factory-doctor) |
| Four conditions for a Factory improvement | `decisions/ADR-0017-four-conditions-for-factory-improvements.md` |
| FAST / STANDARD / GUARDED delivery | `DELIVERY.md` |
| Migration reversibility and PR holds | `DELIVERY.md` |
| Main-landing gate and pr-autopilot | `DELIVERY.md` |
| Live-root protections and worktree isolation | `decisions/ADR-0022-live-root-worktree-enforcement.md` |
| Shared-drain worktree, publication and cleanup | `decisions/ADR-0024-shared-drain-worktree-lifecycle.md` |
| Fixture PII containment | `DELIVERY.md` |
| External evidence and research format | `DELIVERY.md`, `RESEARCH_BRIEF.md` |
| Multi-repo delivery proof | `DELIVERY.md` |
| Secrets, trust boundaries and concurrency | `SECURITY.md` |
| Structural decisions and historical ADR status | `decisions/ADR-0009-integrated-po-and-product-map.md` through `decisions/ADR-0030-lightened-delivery-flow.md`; `decisions/PRE_REFACTOR.md` |
| Decision versus maintenance proposals | `decisions/ADR-0029-proposal-classes.md` |
| Why the D01 delivery flow was lightened (one review, regression before handoff, resumes per cause, model evaluation for interface tickets only) | `decisions/ADR-0030-lightened-delivery-flow.md` |
| Delivery-proof writes through doors | `../bin/deliver-close`, `decisions/ADR-0023-coordination-state-write-door.md` (delivery-proof half) |
| Escalation door, Mayor-first and human notification | `../bin/escalation-door`, `../tests/escalation-door-test.sh` |
| Proposal resolution from merge proof | `COCKPIT.md` |
| Atomic graph publication from a planning Bead | `PLANNING_RUN.md` (graph publication), `../bin/ticket-graph-publish` |
| Closure needs merged code and CI, not an open PR | `decisions/ADR-0026-structural-delivery-completion-gate.md` |
| Fixture City: intent through Delivered/Accepted | `FIXTURE_CITY_ORACLE.md` |
| Quarantine legacy planning and Cockpit V1 | `decisions/ADR-0027-legacy-planning-and-cockpit-v1-quarantine.md` |
| Assembled-diff review, rejection routing and sensitive effects | `FIXTURE_CITY_ORACLE.md` |
| Project isolation and declared cross-project access | `PROJECT_ISOLATION_PROTOTYPE.md` |
| Project Planning Profile and registration | `PROJECT_PLANNING_PROFILE.md` |
| Planning maps, overflow and concurrent decision sessions | `PLANNING_MAP.md`, `PLANNING_RUN.md` |
| Spec digest approval, freeze and semantic revisions | `SPEC_APPROVE.md` |
| Planning Exceptions and affected-subgraph repair | `PLANNING_EXCEPTION.md` |
| Observe changes without redundant wakes | `FACTORY_OBSERVE.md` |
| Add/regenerate catalogue entries | `context-index/entries/`, `factory-tools/entries/`, `../bin/generate-docs-catalogue` |
| Ticket file scopes and hot-path serialization | `../bin/ticket-graph-publish` (ticket_scope_paths), `../config/hot-paths.json` |
| Launch exact commit, isolated port and synthetic dataset | `PROJECT_PLANNING_PROFILE.md` |
| Validated Prototype freeze and conformance | `VALIDATED_PROTOTYPE.md` |
| Convoy state, verdict fingerprints and mutation doors | `CONVOY_STATE.md` |
| Delivery roles, skill scope and sandbox adoption | `FACTORY_TOOLS.md` (role-adoption-trial), `../config/delivery-roles.json` |
| Pinned design skills, upstream copy proof and engine-free adaptation | `DESIGN_SKILLS.md` |
| Start ready tickets: frontier, dependencies and capacity | `CONVOY_ADVANCE.md` |
| Unknown convoy states and Mayor hands-off boundary | `CONVOY_ADVANCE.md` |
| New-flow entry contract and ticket kinds | `ENTRY_CONTRACT.md` |
| Independent graph review and bounded passes | `GRAPH_REVIEW.md` |
| Spec-story coverage and operator needs before publication | `ENTRY_CONTRACT.md` (coverage) |
| Interface tickets and Prototype Fold | `ENTRY_CONTRACT.md` (Prototype Fold) |
| Repair/Owner Finding citations and their validation | `ENTRY_CONTRACT.md` (citations), `OWNER_ANSWER.md` |
| Tool-captured evidence and demonstration records | `EVIDENCE_STORE.md` |
| TDD: red, criterion coverage, freeze and green proof | `TDD_STEP.md` |
| Ticket Exits, handoffs and parked descendants | `TICKET_EXIT.md` |
| Spec integration branch, serial merges and invalidation | `SPEC_INTEGRATION.md` |
| Author session, worktree and ticket sequence | `TICKET_AUTHOR.md` |
| Independent criterion-test review before freeze | `TEST_REVIEW.md` |
| Code review before ticket merge | `CODE_REVIEW.md` |
| Evaluate the launched product before ticket merge | `TICKET_EVALUATION.md` |
| Screen-to-prototype fidelity, anchors and evidence | `PROTOTYPE_FIDELITY.md` |
| False no-match under pipefail / grep early exit | `../tests/pipefail-early-exit-check-test.sh` |
| Bounded correction after code/evaluation refusal | `CORRECTION_ROUND.md` |
| Ticket-end gate on the merged tip | `TICKET_END.md` |
| Same delivery flow for another language / non-web product | `PROJECT_PLANNING_PROFILE.md`, `FIXTURE_CITY_ORACLE.md` |
| Cockpit process start, stop and restart | `COCKPIT.md` |
| CI quota, duration, shards and merge-group runs | `OPERATIONS.md` |
| Recover from an unrequested supervisor stop | `FACTORY_TOOLS.md` |
| Manual convoy lifecycle and planning-artifact closure | `CONVOY_ADVANCE.md`, `../bin/planning-artifacts-close` |
| Host battery queue and NOT RUN / exit 75 | `DELIVERY.md` |
| Ticket resumes, bounds and grouped requests | `CONVOY_ADVANCE.md` |
| When long CI tests can be omitted | `OPERATIONS.md` |
| Convoy stops: red integration or planning exceptions | `CONVOY_ADVANCE.md` |
| Spec-end mechanical gates and tracked items | `SPEC_END.md` |
| Outcome Evaluation and out-of-ticket findings | `OUTCOME_EVALUATION.md` |
| Required local checks before a Factory PR | `DELIVERY.md` |
| End review of the assembled Spec diff | `SPEC_END_REVIEW.md` |
| CI runner location; historical self-hosted lifecycle | `OPERATIONS.md`, `SECURITY.md` (CI runner) |
| Generate and validate the Evidence Pack | `EVIDENCE_PACK.md` |
| End repair bounds, non-conforme stop and Delivered | `CONVOY_ADVANCE.md` |
| Acceptance Request and Acceptance Session | `ACCEPTANCE_SESSION.md` |
| Owner answer, findings and routing | `OWNER_ANSWER.md` |
| Promotion after acceptance/abandonment and convoy closure | `OUTCOME_PROMOTE.md` |
| Requirement-to-mechanism proof and adaptation checks | `REQUIREMENT_TABLE.md` |
| Fresh test/code/evaluation sessions and author capacity | `TEST_REVIEW.md` (fresh sessions), `CODE_REVIEW.md`, `TICKET_EVALUATION.md` |
| CI syntax-check failures | `../.github/workflows/ci.yml` |
| D01 accepted limits and final verification | `verification/D01-verification-finale.md` (§6, 7, 10, 12); `bd comments af-m23wru` |
| Preserve cases/assertions when optimizing tests | `FACTORY_TOOLS.md` (test-cases-compare) |
| Test-writing guideline and test-file ceilings | `TEST_GUIDELINE.md` |
| Claude MCP/tool profiles and context floor | `../city.toml` ([providers.claude]) |
| Launch the cockpit isolated at a commit on a named synthetic dataset: recipe, datasets, screens, seams, regression command | `COCKPIT.md` (« Isolated launch »), `PROJECT_PLANNING_PROFILE.md` (« Launch declarations »), `../config/project-descriptors/agent-factory.json` (`launch`), `../bin/cockpit-isolated`, `../lib/synthetic_city.py` |

## Authority and minimal retrieval

Observed Gas City/Beads/Git/GitHub > versioned Factory/project contracts >
current official upstream documentation > historical Plan directeur V2 >
chats/model memory. Report conflicts and repair the owning durable source
within scope. Refresh live evidence before mutation.

- Project: nearest project `AGENTS.md`, project knowledge, relevant Beads/GitHub.
- Factory activity: `gc status`, then relevant Beads/GitHub.
- Health: `OPERATOR_BRIDGE.md` and its read-only check; triage with
  `bin/factory-doctor`. Host capacity/unsaved work: `bin/factory-guard
  --check-only` and `bin/factory-resources` (`FACTORY_TOOLS.md`).
- Change: root/nearest instructions, named Bead and affected contract only.
  Architecture/policy changes also read/update the relevant ADR.

Stable contracts belong in Git; work and coordination in Beads. Observe
processes, sessions, branches, PRs and CI live. Keep volatile SHAs, PIDs and
backlogs out of this index. The Plan directeur V2 (2026-09-12) is historical
conceptual context; verified operational contracts take precedence.
