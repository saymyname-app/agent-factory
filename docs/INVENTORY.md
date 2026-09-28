# Factory inventory — "nothing forgotten" (roadmap A4)

Snapshot of 2026-09-27 at `f591937` (after legacy PR 5b). Every tracked file
outside `legacy/` has one verdict; every finding has one disposition. A later
change does not update this file: the next inventory replaces it.

**Verdicts.** `kernel` — refactor-born, project-agnostic core (Planning Run
flow, graph execution). `ops` — live operations machinery, coherent today,
reviewed in the Planning Run "Factory operations v2" (A5). `legacy` — serves
only retired concepts, should leave. `to-redo` — live but wrong (stale text,
retired concepts, project-specific content, drift); its finding says what.

**Dispositions.** `FIXED` (PR merged or open) · `A4-DOCS` (wording-only fix,
next A4 PR) · `A5` (input for the Planning Run "Factory operations v2": it
changes behavior or design) · `BENJAMIN` (his call: destructive, host-local,
or his own data).

Method: three read-only reviewers (code · config+docs · tests), findings kept
only when verified in the code; live checks for runtime state.

## Counts

| Verdict | Files |
|---|---|
| kernel | 76 |
| ops | 91 |
| to-redo | 46 |
| legacy | 1 |
| **total** | **214** (fixture directories counted once each) |

## Findings

| ID | Sev | Where | Problem | Disposition |
|---|---|---|---|---|
| F01 | med | `bin/`, `lib/`, `tests/`, `config/` | 15 comments/diagnostics named `legacy/` paths | FIXED #251 + `tests/legacy-isolation-test.sh` |
| F02 | high | `bin/campaign-pointer` | `escalate` marks any bead, `clear-decision` only cleared `af-1vr4`: a work-bead escalation could never be cleared through the door (live: af-y2jgr, af-3pt18) | FIXED #252 |
| F03 | med | `docs/DELIVERY.md` | says claude defaults to `plan`/`claude-sonnet-5`; `city.toml` sets `unrestricted`/`sonnet-5` and the guard treats `plan` as broken; says "no Actions workflows" though `ci.yml` exists; points at `DESIGN_GOVERNANCE.md` (legacy only) | A4-DOCS |
| F04 | med | `AGENTS.md`, `README.md`, `docs/OPERATOR_BRIDGE.md`, `docs/OPERATIONS.md` | "campaign liveness" invariant; product status/preview "configured"; examples route to the product queue; `derive_delivery()` exists only in legacy; "off-box backup not configured" (live: `jsonl-export` every 15 min to the private archive repo) | A4-DOCS |
| F05 | low | `AGENTS.md`, `city.toml`, `config/provider-policy.json`, `config/model-catalog.json`, `bin/provider-failover` (help + generated header) | "change providers from the cockpit"; only `provider-failover set` exists | A4-DOCS |
| F06 | low | `orders/provider-failover.toml`, `orders/factory-watchdog.toml`, `orders/pr-autopilot.toml`, `formulas/mol-*`, `bin/factory-boot`, `bin/factory-delivery-guard`, `bin/pr-autopilot`, `bin/factory-observe` | descriptions still cite the campaign (parking, liveness, idle ladder, `gc.campaign_progress_at`, "for the dashboard"); pr-autopilot "never touches PRs targeting main" is false (Factory `main` is armed); "for the SayMyName rigs" | A4-DOCS |
| F07 | low | `docs/FACTORY_OBSERVE.md`, `docs/ADAPTATION_REGISTER.md`, `docs/PLANNING_RUN_RESUME_PROTOTYPE.md`, `docs/GETTING_STARTED.md`, `docs/FACTORY_TOOLS.md` | legacy improvement-axes cited as a live pattern; `bin/factory-cockpit` cited; "C01 reservation" (active one is factory-operations-v2); "5 providers" checked (loop checks 4) | A4-DOCS |
| F08 | low | `lib/factory_watchdog.py:263`, `lib/provider_failover.py:93`, 5 test comments, `tests/coordination-pointer-doors-test.sh` | comments point at deleted tests / retired `product-queue`, `gc.queue_state` | A4-DOCS |
| F09 | low | `agents/mayor/prompt.template.md` | says `build-basic` "comes from the pack" (a local fork in `formulas/` overrides it) | A4-DOCS |
| F10 | med | `docs/decisions/ADR-0026-*.md`, `docs/DELIVERY.md:188` | rely on the retired `mayor-campaign` readiness lane; needs the same dated amendment ADR-0025 got | A4-DOCS |
| F11 | med | `lib/protected_rigs.sh`, `bin/deliver-close:127-139`, `bin/factory-guard:384`, `bin/factory-delivery-guard:84`, `bin/factory-watchdog:58`, `city.toml` (`[[patches.agent]] dir=saymyname-*`, `/home/benja` paths), `.githooks/post-checkout:20`, `pr-autopilot-*`/watchdog/failover test fixtures | SayMyName and host paths hardcoded in a project-agnostic Factory; `deliver-close` duplicates the "single source"; a new project's rig gets no guard coverage and no warning | A5 (per-project rig config) |
| F12 | med | `bin/factory-waiting-guard`, `bin/factory-guard` §11 + tests | only reader of `gc.waiting_on` was the retired idle ladder (verdict `legacy`) | A5 (retire or re-justify) |
| F13 | med | `bin/campaign-pointer` start/finish, Mayor prompt 283-286 | write `gc.current`, `gc.current_jit`, `gc.last_delivered`, `gc.campaign_progress_at` that nothing outside legacy reads; lock named after the campaign | FIXED (O06, af-sau1a): `campaign-pointer` retired entirely, its dead fields no longer written anywhere |
| F14 | med | `formulas/mol-scoped-work.formula.toml` | prints "refuses base=main" then pushes/opens a PR against `main` (default base); escalation goes to `/dev/null \|\| true` (silent failure) | PARTIALLY FIXED (O06, af-sau1a): `notify-failure` now calls `escalation-door mayor` and `exit 1`s if it fails; the base=main misprint is untouched |
| F15 | low | `formulas/mol-scoped-work`, `formulas/mol-polecat-commit`, `agents/claude-reviewer`, `bin/factory-observe`, `bin/factory-resources`, `bin/goal-delivery-pairs`, 5 prototype/oracle scripts | no runtime caller (only tests/docs); `mol-polecat-commit` refuses base `main` so cannot run on the Factory repo | A5 (keep, route, or retire each) |
| F16 | low | Mayor prompt, `bin/factory-work-dispatch` | GUARDED Factory work goes to `build-basic` but no target is named, and `factory-work-dispatch` accepts only `mol-do-work` | FIXED (O03, af-ui0ua): `bin/dispatch-door` resolves target and validates formula for every rig (`build-basic` included) from `config/projects/*.toml`; `factory-work-dispatch` wraps it; `bin/dispatch-door-guard` reports any dispatch that bypasses it |
| F17 | med | `.githooks/`, `docs/GETTING_STARTED.md` | a fresh clone runs without PII guard, main gate or live-root hooks: `core.hooksPath` is only in the live `.git/config` | A5 |
| F18 | med | `bin/planning-run-router:130-149` | `clear_reservation` rewrites tracked `config/planning-run-reservation.json` in the live root (dirty tree, guard snapshots, drift from `main`) | A5 |
| F19 | low | `bin/factory-guard:138`, `city.toml`, provider policy, model catalog | `claude-fable` defined in `city.toml`, checked nowhere, absent from policy and catalog | A5 |
| F20 | low | `config/factory-observe*.schema.json` | no code loads either schema (validation hand-written); the doc says the policy is validated against it | A5 |
| F21 | low | `tests/build-basic-fail-fast-runtime-test.sh`, `tests/factory-watchdog-order-test.sh` | local-only tests run nowhere automatically; the second hardcodes `/home/benja/agent-factory` | PARTIALLY FIXED (O13): new `local-only-tests` order (`orders/local-only-tests.toml`, `bin/local-only-tests`) runs both nightly and pages the Mayor on failure. The hardcoded path in `factory-watchdog-order-test.sh` is untouched -- it matches the live root by design, which is what this order runs against. |
| F22 | med | `docs/DELIVERY.md:558-577`, `docs/OPERATIONS.md:389-506` | SayMyName-only rig contracts and operations; `gc bd create --rig saymyname-*` contradicts "new work enters through the Planning Run router" | A5 (move to the product repos) |
| F23 | low | planning-run fixtures (15 files), watchdog / planning-exception-guard tests, `provider-failover-test.py` | operator's first name and GitHub login as signer; SayMyName backend test output as fixture | A5 (synthetic operator id) |
| F24 | low | off-box backup | archive repo last pushed 18:42Z while `jsonl-export` completes every 15 min: no freshness signal says whether pushes still happen | FIXED (O13): new `backup-freshness` order (`orders/backup-freshness.toml`, `bin/backup-freshness`) pages the Mayor when the archive hasn't been pushed in 24h while beads kept changing. |
| F25 | low | `.gc/runtime/factory-watchdog-signals.json` | written by three scripts, no reader | FIXED (O06, af-sau1a): none of the three writers touches the file any more; `merge_signals`/`merge-signals` removed from `lib/factory_watchdog.py` |

## Host-local state (not versioned; checked live 2026-09-27)

| What | Size | Reader | Disposition |
|---|---|---|---|
| `.gc/runtime/factory-cockpit-*` (4 files), `factory-continuity-history.json` | < 100 KB | none (Cockpit V1 retired) | BENJAMIN: delete |
| `.gc/runtime/saymyname-{backend,frontend}--core.control-dispatcher-trace.log` | 27 MB | none; last write 09-25 | BENJAMIN: delete |
| `.gc/runtime/session-reconciler-trace/`, `core.control-dispatcher-trace.log` | 608 MB + 62 MB, growing | Gas City (upstream traces) | A5: rotation order ("rotate logs" is standing-allowlisted) |
| `rigs/*/worktrees/` (35 worktrees) | 2.4 GB | none since 09-25; all clean; 31 hold 1-5 commits on no remote branch (likely squash-merged, not provable cheaply) | BENJAMIN: `git bundle` then remove |
| rig untracked reports (`requirements.md`, `review-report.md`, `artifacts/`, `plans/`, `docs/build-artifacts/` …), a 2024 `.deb` and an empty `CLAUDE.md` (created 2026-09-27) in the frontend rig | < 1 MB | none | BENJAMIN: delete |

Guard §3b (#248) keeps rig checkouts on their base branch but does not clean
untracked residue: once cleaned, whether runs should write it there at all is
an A5 input.

## Every file

| Path | Verdict | Used by | Reason |
|---|---|---|---|
| `.beads/identity.toml` | ops | gc/bd; .gitignore whitelist | canonical Beads project id |
| `.githooks/post-checkout` | ops | git (core.hooksPath in .git/config); tests/factory-live-root-guard-test.sh | reverts branch switch in live root (ADR-0022 mechanism) |
| `.githooks/pre-push` | ops | git; pre-push-ci-registration, factory-main-gate, pii-guard tests | PII guard + CI registration + main gate |
| `.githooks/reference-transaction` | ops | git; tests/factory-live-root-guard-test.sh | refuses commit/reset/merge in live root |
| `.github/workflows/ci.yml` | ops | GitHub Actions; tests/ci-registration-test.sh | runs kernel + ops suites; escalation-door test replaces the retired campaign-pointer test (O06, af-sau1a) |
| `.gitignore` | ops | git; factory-guard work-tree check | coherent (city.provider.toml, *.before-*) |
| `AGENTS.md` | to-redo | all agents (CLAUDE.md, mayor prompt, operator-context test) | invariants still cite campaign liveness, cockpit, SayMyName runner, preview |
| `CLAUDE.md` | ops | Claude Code | @AGENTS.md include |
| `CONTEXT.md` | kernel | ADR-0028, refactor spec | project-agnostic domain glossary |
| `README.md` | to-redo | entry point | says product status and preview are configured while also retired (F04) |
| `agents/claude-reviewer/agent.toml` | ops | city.toml patch (max 1), config/provider-policy.json, docs/DELIVERY.md | On-demand reviewer pool; no prompt/formula ever dispatches it (see findings) |
| `agents/claude-reviewer/prompt.template.md` | ops | claude-reviewer agent | Generic read-only reviewer prompt, coherent; no dispatcher names it |
| `agents/factory-worker/agent.toml` | kernel | bin/factory-work-dispatch, city.toml, mayor prompt, tests/factory-work-dispatch-test.sh | The HQ implementation role every approved-graph af-* bead goes to |
| `agents/factory-worker/prompt.template.md` | kernel | factory-worker sessions | Generic graph.v2 claim/close protocol; no drift found vs gc hook/bd usage |
| `agents/mayor/agent.toml` | kernel | pack.toml named_session mayor | Mayor provider pin |
| `agents/mayor/prompt.template.md` | to-redo | Mayor named session (pack.toml) | Escalation door is now `escalation-door` (O06, af-sau1a); build-basic "from the pack" is wrong, GUARDED HQ dispatch path undefined |
| `agents/ux-reviewer/agent.toml` | kernel | mayor prompt UX gate, provider-policy.json, tests | On-demand UX role named by the Mayor's UI/UX gate |
| `agents/ux-reviewer/prompt.template.md` | kernel | ux-reviewer sessions | Project-agnostic (reads target project's governance); coherent |
| `assets/workflows/build-basic/cleanup-shared-worktree.md` | ops | formulas/build-basic.formula.toml | delivery formula step prompt; no retired/project refs |
| `assets/workflows/build-basic/decompose.md` | ops | formulas/build-basic.formula.toml | delivery formula step prompt; no retired/project refs |
| `assets/workflows/build-basic/finalize.md` | ops | formulas/build-basic.formula.toml | delivery formula step prompt; no retired/project refs |
| `assets/workflows/build-basic/implement-same-session.md` | ops | formulas/build-basic.formula.toml | delivery formula step prompt; no retired/project refs |
| `assets/workflows/build-basic/implement.md` | ops | formulas/build-basic.formula.toml | delivery formula step prompt; no retired/project refs |
| `assets/workflows/build-basic/plan-review.md` | ops | formulas/build-basic.formula.toml | delivery formula step prompt; no retired/project refs |
| `assets/workflows/build-basic/plan.md` | ops | formulas/build-basic.formula.toml | delivery formula step prompt; no retired/project refs |
| `assets/workflows/build-basic/prepare-shared-worktree.md` | ops | formulas/build-basic.formula.toml | delivery formula step prompt; no retired/project refs |
| `assets/workflows/build-basic/prepare.md` | ops | formulas/build-basic.formula.toml | delivery formula step prompt; no retired/project refs |
| `assets/workflows/build-basic/publish.md` | ops | formulas/build-basic.formula.toml; tests/build-basic-publish-overlap-followup-test.sh | delivery formula step prompt; no retired/project refs |
| `assets/workflows/build-basic/requirements.md` | ops | formulas/build-basic.formula.toml | delivery formula step prompt; no retired/project refs |
| `assets/workflows/build-basic/review.md` | ops | formulas/build-basic(-review-scoped).formula.toml | delivery formula step prompt; no retired/project refs |
| `assets/workflows/build-basic/summarize-implementation.md` | ops | formulas/build-basic.formula.toml | delivery formula step prompt; no retired/project refs |
| `bin/deliver-close` | to-redo | mol-do-work, pr-autopilot, factory-delivery-guard, planning-exception-guard, CI | Live delivery door (ADR-0009/0016/0028) but hardcodes SayMyName repo->workflow map duplicating lib/protected_rigs.sh |
| `bin/escalation-door` | ops | mayor prompt (`benjamin`/`mayor`), mol-scoped-work notify-failure, CI test tests/escalation-door-test.sh, coordination-pointer-doors-test.sh | O06 (af-sau1a): the one escalation door; retired `bin/campaign-pointer` (`escalate`/`start`/`finish`/`clear-decision` and its dead `af-1vr4` fields) |
| `bin/factory-boot` | ops | Windows logon task (external), docs/RUNBOOK_STOP_AND_RESTART.md | Restart restore; one stale "campaign" log string |
| `bin/factory-build-gates` | ops | factory-boot, factory-guard, CI test | CLI wrapper for lib/factory_build_gates.py (materialises pack check scripts) |
| `bin/factory-delivery-guard` | to-redo | factory-guard, CI test | Live proof-field backfill, but RIGS hardcoded to saymyname-backend/frontend and rationale cites mayor-campaign/product-status readers |
| `bin/dispatch-door` | kernel | mayor prompt, factory-work-dispatch, CI test | O03 (af-ui0ua): the one door for every rig/formula, validated from config/projects/*.toml |
| `bin/dispatch-door-guard` | ops | factory-guard §10b, CI test | O03 (af-ui0ua): reports (does not repair) a raw gc sling that bypassed bin/dispatch-door |
| `bin/factory-dispatch-guard` | ops | factory-guard, CI test | Self-heals sling without --reassign (af-33a4e); coherent with Mayor prompt |
| `bin/factory-do-work-workspace` | ops | mol-do-work (enter/finish), pr-autopilot, factory-watchdog, CI test | Worktree isolation for protected branches via lib/protected_rigs.sh |
| `bin/factory-doctor` | ops | operator tool (docs), CI test | Classifies gc doctor output ACTIONABLE/UPSTREAM; no order |
| `bin/factory-gh-rollup` | ops | pr-autopilot, factory-watchdog, mayor prompt, CI test | Rebuilds statusCheckRollup for fine-grained PAT; usage matches prompt |
| `bin/factory-guard` | to-redo | orders/factory-guard.toml (5m), git hooks, factory-boot | Core live guard, but §5 hardcodes SayMyName rigs, §7/7b store dedup on campaign bead af-1vr4, §11 serves the retired idle ladder |
| `bin/factory-main-gate` | ops | .githooks/pre-push, factory-watchdog, CI tests | Pre-push main landing gate (ADR-0020); header cites legacy incident only as history |
| `bin/factory-observe` | kernel | CI test, docs/FACTORY_OBSERVE.md | B09 observe/wake kernel; no order or script calls it at runtime (see findings) |
| `bin/factory-pii-guard` | ops | .githooks/pre-push, factory-guard §3c, CI test | Layer A real-PII guard |
| `bin/factory-planning-exception-guard` | kernel | factory-guard §12, deliver-close, CI test | Detection net for ADR-0028 semantic/topology closes |
| `bin/factory-provenance-guard` | ops | Backend/Frontend CI workflows (backend-ci.yml, frontend-ci.yml), CI test | Layer B PII provenance guard run by product-repo CI |
| `bin/factory-resources` | ops | operator tool (docs/RUNBOOK_STOP_AND_RESTART.md) only | Host RAM/swap headroom check; no order, no test |
| `bin/factory-shared-drain-workspace` | ops | assets/workflows/build-basic/{prepare-shared-worktree,publish,cleanup-shared-worktree}.md, CI test | Shared-drain worktree adapter for build-basic same-session |
| `bin/factory-waiting-guard` | legacy | factory-guard §11, CI test | Maintains gc.waiting_on, whose only consumer was the retired idle ladder (legacy/lib/factory_campaign.py) |
| `bin/factory-watchdog` | to-redo | orders/factory-watchdog.toml, CI tests | Live paging (§1-4,7); FIXED (O06, af-sau1a): the reader-less cockpit signal file is no longer written; some header/comments still describe campaign/cockpit |
| `bin/factory-work-dispatch` | kernel | mayor prompt, CI test | The HQ convenience wrapper (factory-worker, mol-do-work, --reassign) around bin/dispatch-door (O03) |
| `bin/fixture-city-oracle` | kernel | CI test, project-isolation-oracle, docs | Fixture-city oracle (ADR-0027 legacy_path fences) |
| `bin/goal-delivery-pairs` | ops | docs/DELIVERY.md, CI test | Read-only multi-rig delivery-pair query; no runtime caller |
| `bin/on-order-failed` | ops | orders/on-order-failed.toml, CI test | Pages Mayor on repeated order failure; FIXED (O06, af-sau1a): no longer writes the reader-less signal file |
| `bin/on-session-stranded` | ops | orders/on-session-stranded.toml, CI test | Reopens orphaned beads + pages; FIXED (O06, af-sau1a): no longer writes the reader-less signal file |
| `bin/planning-allocation-prototype` | kernel | CI test, config/planning-allocation-prototype.json, docs | P02 synthetic allocation proof; no runtime caller (prototype evidence) |
| `bin/planning-exception` | kernel | mayor prompt, deliver-close, factory-guard, planning-exception-guard, CI | ADR-0028 Planning Exception register; subcommands match docs |
| `bin/planning-map-concurrency-prototype` | kernel | CI test, wayfinding-run (docstring), docs | Synthetic concurrency proof; no runtime caller |
| `bin/planning-run-resume-oracle` | kernel | CI test, docs | P04 resume oracle; no runtime caller |
| `bin/planning-run-router` | kernel | AGENTS.md, docs/GETTING_STARTED.md, CI test | Planning Run entry point; legacy paths only as fence names |
| `bin/planning-run-to-spec-oracle` | kernel | planning-run-router, spec-approve, CI test | Session -> Spec stage |
| `bin/pr-autopilot` | ops | orders/pr-autopilot.toml (3m), CI tests | Arms/finalizes PRs from lib/protected_rigs.sh; header "for the SayMyName rigs" stale |
| `bin/project-isolation-oracle` | kernel | CI test, docs | Project isolation oracle |
| `bin/project-planning-profile` | kernel | docs/GETTING_STARTED.md, CI test | Per-project planning profile validator (rejects SayMyName-specific fields by design) |
| `bin/provider-failover` | to-redo | orders provider-failover + model-staleness-check, factory-boot, factory-guard | Live failover, but help/status/set text is written for the retired cockpit |
| `bin/reversibility-check` | ops | pr-autopilot, factory-watchdog, CI test | ADR-0019 reversibility gate CLI |
| `bin/role-qualification-oracle` | kernel | CI test, docs | P06 role qualification oracle; no runtime caller |
| `bin/spec-approve` | kernel | planning-run-router, CI test | Spec approval stage |
| `bin/ticket-graph-publish` | kernel | mayor prompt (patch), planning-run-router, planning-exception, CI | validate/publish/patch; `patch` exists as the prompt says |
| `bin/wayfinding-run` | kernel | planning-run-router, spec-approve, planning-exception, CI | Wayfinding stage |
| `city.toml` | to-redo | gc; factory-guard; provider-failover; build-gates | live, but comments route provider changes via retired cockpit; SayMyName rigs/patches + /home/benja paths |
| `config/factory-observe-measures.schema.json` | kernel | docs only (bin/factory-observe docstring, FACTORY_OBSERVE.md); no code loads it | B09 measures contract; validation hand-coded in lib/factory_measures.py |
| `config/factory-observe-policy.json` | kernel | bin/factory-observe, lib/factory_observe.py, test | B09 policy |
| `config/factory-observe-policy.schema.json` | to-redo | nobody (0 references) | orphan schema; policy validated by hand-coded lib/factory_observe.validate_policy |
| `config/fixture-city-bwrap.apparmor` | kernel | ci.yml, bin/project-isolation-oracle, test | P05 sandbox profile for CI |
| `config/model-catalog.json` | ops | bin/provider-failover check-models, orders/model-staleness-check.toml | coherent; omits claude-fable (skipped by design); description quotes cockpit |
| `config/planning-allocation-prototype.json` | kernel | bin/planning-allocation-prototype, test (CI) | P02 oracle input |
| `config/planning-map-concurrency-prototype.json` | kernel | bin/planning-map-concurrency-prototype, test (CI) | P03 oracle input |
| `config/planning-run-reservation.json` | kernel | bin/planning-run-router (reads AND rewrites) | B12 AC#5 reservation: factory-operations-v2 then C01 |
| `config/planning-run-resume-prototype.json` | kernel | bin/planning-run-resume-oracle, test (CI) | P04 synthetic input (names a factory-cockpit surface) |
| `config/provider-policy.json` | to-redo | bin/provider-failover, lib/provider_failover.py | chains live and correct, but description says settings are made from the retired cockpit |
| `config/role-qualification-prototype.json` | kernel | bin/role-qualification-oracle, test (CI) | P06 oracle input |
| `docs/ADAPTATION_REGISTER.md` | to-redo | CONTEXT_INDEX, planning-exception guard, tests | kernel register but AR-004 cites legacy lib/factory_improvement_axes.py + schema as live proven pattern |
| `docs/CONTEXT_INDEX.md` | ops | AGENTS.md, README, mayor prompt, operator-context test | updated for legacy split; all cited paths exist |
| `docs/DELIVERY.md` | to-redo | CONTEXT_INDEX, pr-autopilot, reversibility | provider facts contradict city.toml; "no Actions workflows"; missing DESIGN_GOVERNANCE.md; nonexistent scoped Mayor lane; SayMyName rig contracts |
| `docs/FACTORY_OBSERVE.md` | to-redo | CONTEXT_INDEX, bin/factory-observe | kernel doc; cites legacy lib/factory_improvement_axes.py; claims schema validation the code does not do |
| `docs/FACTORY_TOOLS.md` | to-redo | CONTEXT_INDEX, ADR-0025 | mostly current; "5 providers" (4 checked); SayMyName example commands |
| `docs/FIXTURE_CITY_ORACLE.md` | kernel | CONTEXT_INDEX, ADR-0027 | fixture oracle contract; cockpit refs are the quarantine fence |
| `docs/GETTING_STARTED.md` | to-redo | README, CONTEXT_INDEX | claims clean city.toml after rig removal (false); no core.hooksPath step |
| `docs/OPERATIONS.md` | to-redo | README, CONTEXT_INDEX, RUNBOOK | SayMyName rig ops/cutover/M6 rollback; gc bd create new-work procedure; dangling derive_delivery(); stale off-box backup claim |
| `docs/OPERATOR_BRIDGE.md` | to-redo | AGENTS.md, README, operator-context test | example intents target the retired product queue |
| `docs/PLANNING_ALLOCATION_PROTOTYPE.md` | kernel | CONTEXT_INDEX | P02 doc |
| `docs/PLANNING_EXCEPTION.md` | kernel | CONTEXT_INDEX, planning-exception guard | B08 doc |
| `docs/PLANNING_MAP_CONCURRENCY_PROTOTYPE.md` | kernel | CONTEXT_INDEX, ADAPTATION_REGISTER | P03 doc |
| `docs/PLANNING_RUN_RESUME_PROTOTYPE.md` | to-redo | CONTEXT_INDEX | P04 doc cites legacy bin/factory-cockpit and an AGENTS.md assertion that no longer exists |
| `docs/PLANNING_RUN_ROUTER.md` | kernel | CONTEXT_INDEX, GETTING_STARTED | consistent with bin/planning-run-router (reservation sequence) |
| `docs/PLANNING_RUN_TO_SPEC_PROTOTYPE.md` | kernel | CONTEXT_INDEX | B03 doc |
| `docs/PROJECT_ISOLATION_PROTOTYPE.md` | kernel | CONTEXT_INDEX | P05 doc |
| `docs/PROJECT_PLANNING_PROFILE.md` | kernel | CONTEXT_INDEX, GETTING_STARTED, OPERATOR_BRIDGE | B02 doc; SayMyName mentions are the rejection rule |
| `docs/RESEARCH_BRIEF.md` | ops | CONTEXT_INDEX, DELIVERY | External Evidence Gate template |
| `docs/ROLE_QUALIFICATION_PROTOTYPE.md` | kernel | CONTEXT_INDEX | P06 doc |
| `docs/RUNBOOK_STOP_AND_RESTART.md` | ops | AGENTS.md, bin/factory-boot, CONTEXT_INDEX | commands verified; minor hardcoded SayMyName rig loop (:42) |
| `docs/SECURITY.md` | ops | CONTEXT_INDEX, OPERATOR_BRIDGE | generic trust boundaries |
| `docs/SPEC_APPROVE.md` | kernel | CONTEXT_INDEX | B05 doc; subcommands match |
| `docs/WAYFINDING_RUN.md` | kernel | CONTEXT_INDEX, GETTING_STARTED | B04 doc; subcommands match |
| `docs/decisions/ADR-0025-approved-graph-bootstrap-scope.md` | kernel | CONTEXT_INDEX | amended 2026-09-26 for campaign removal |
| `docs/decisions/ADR-0026-structural-delivery-completion-gate.md` | to-redo | CONTEXT_INDEX | point 5 and reversal still rely on mayor-campaign scoped readiness (legacy); no amendment |
| `docs/decisions/ADR-0027-legacy-planning-and-cockpit-v1-quarantine.md` | kernel | CONTEXT_INDEX, B12 note | quarantine fence; legacy paths intentional |
| `docs/decisions/ADR-0028-planning-exception-routing.md` | kernel | CONTEXT_INDEX | B08 ADR |
| `docs/planning/B12-redecomposition-planning-run-router.md` | kernel | CONTEXT_INDEX, reservation config, router doc | status updated; activation-switch paths explicitly not built |
| `docs/planning/agent-factory-project-agnostic-refactor-spec.md` | kernel | ADR-0027 | approved refactor Spec |
| `docs/planning/agent-factory-project-agnostic-refactor-ticket-graph-draft.yaml` | kernel | tests/ticket-graph-publish-test.py, B12 note | refactor ticket graph; test input |
| `docs/research/2026-09-22-agent-factory-refactor-grilling-checkpoint.md` | kernel | ADR-0028 | dated refactor design checkpoint |
| `docs/research/2026-09-22-agentic-factory-autonomy-frontier.md` | kernel | grilling checkpoint | dated research input (SayMyName-framed, historical) |
| `docs/research/2026-09-23-agentic-tdd-review-workflow.md` | kernel | none (unreferenced) | dated research for Q47-Q48; orphan but harmless |
| `formulas/build-basic-review-scoped.formula.toml` | kernel | build-basic (expand), tests/build-basic-fail-fast-test.py | GUARDED-tier review expansion (local fail-fast fork) |
| `formulas/build-basic.formula.toml` | kernel | mayor prompt GUARDED tier, assets/workflows/build-basic, CI | Local fork overriding the pack's build-basic |
| `formulas/mol-do-work.formula.toml` | to-redo | factory-work-dispatch (only formula allowed), mayor prompt default, CI contract test | Core writer formula, but description says "for demos" and claim rationale cites idle ladder/campaign_progress_at |
| `formulas/mol-polecat-commit.formula.toml` | to-redo | mayor prompt (optional), factory-delivery-guard, CI contract test | No routing path selects it; refuses main so unusable on HQ; rationale cites idle ladder |
| `formulas/mol-scoped-work.formula.toml` | to-redo | CI contract test, factory-watchdog test only | No routing path selects it; "refuses base=main" but proceeds; FIXED (O06, af-sau1a): escalates through `escalation-door mayor`, `exit 1`s if it fails |
| `lib/factory_build_gates.py` | ops | bin/factory-build-gates | Build-gate wiring check |
| `lib/factory_delivery_proof.py` | ops | factory-delivery-guard, factory-guard, factory-waiting-guard, pr-autopilot, CI | Proof-field rules; comments cite cockpit as label origin (history) |
| `lib/factory_measures.py` | kernel | bin/factory-observe, CI | Measures validation for B09 |
| `lib/factory_observe.py` | kernel | bin/factory-observe, CI | B09 pure logic; docstring cites legacy factory_improvement_axes as precedent |
| `lib/factory_session_boot.py` | ops | factory-guard §7/§7b, CI | Mayor session-down/boot rules |
| `lib/factory_watchdog.py` | ops | factory-watchdog, on-order-failed, on-session-stranded, CI | Watchdog logic; FIXED (O06, af-sau1a): `merge_signals`/`merge-signals` (the signal-file writer) removed |
| `lib/protected_rigs.sh` | to-redo | pr-autopilot, factory-do-work-workspace, mol-do-work (doc) | "Single source of truth" hardcoding SayMyName repos in the Factory; bypassed by deliver-close/delivery-guard/guard |
| `lib/provider_failover.py` | to-redo | bin/provider-failover, CI | Dead `parked` state field; generated overlay header tells readers to use the cockpit |
| `lib/reversibility.py` | ops | reversibility-check, pr-autopilot, factory-watchdog, CI | ADR-0019 rules |
| `orders/convoy-parent-sweep.toml` | ops | gc order scheduler | Runs builtin `gc convoy check --json` every 15m |
| `orders/factory-guard.toml` | ops | gc order scheduler | 5m factory-guard --quiet |
| `orders/factory-watchdog.toml` | to-redo | gc order scheduler | Description lists a campaign-liveness check the watchdog no longer has; omits §4/§7 |
| `orders/model-staleness-check.toml` | ops | gc order scheduler | Daily provider-failover check-models (subcommand exists) |
| `orders/on-order-failed.toml` | ops | gc event order.failed | Event hook |
| `orders/on-session-stranded.toml` | ops | gc event session.stranded | Event hook |
| `orders/pr-autopilot.toml` | to-redo | gc order scheduler | Description "Never touches PRs targeting main" is false for the Factory repo |
| `orders/provider-failover.toml` | to-redo | gc order scheduler | Description still says it parks/resumes the campaign |
| `pack.toml` | ops | gc | pack imports pinned |
| `packs.lock` | ops | gc; bin/factory-dispatch-guard | pack pins |
| `tests/build-basic-fail-fast-runtime-test.sh` | to-redo | build-basic fail-fast on a real gc/bd city; fixture build-basic-fail-fast | not in ci.yml; declared "# ci: local-only" so ci-registration passes, but nothing runs it automatically |
| `tests/build-basic-fail-fast-test.py` | ops | build-basic formula fail-fast (static) | in CI (ci.yml:152) |
| `tests/build-basic-publish-overlap-followup-test.sh` | ops | build-basic publish follow-up bead on overlapping worktree | in CI (ci.yml:105) |
| `tests/ci-registration-test.sh` | ops | meta: every tests/*.sh\|py named in ci.yml or marked local-only | in CI (ci.yml:236); header cites retired tests (product-queue, saymyname-*) as history only |
| `tests/coordination-pointer-doors-test.sh` | ops | ADR-0023 rule 6 scan of Mayor prompt, OPERATIONS.md, formulas | in CI (ci.yml:111); header/FIELDS still name legacy bin/product-queue and gc.queue_state |
| `tests/deliver-close-test.sh` | ops | bin/deliver-close (ADR-0026 delivery proof door); fixture deliver-close | in CI (ci.yml:99) |
| `tests/delivery-formula-contract-test.sh` | ops | mol-do-work/mol-scoped-work/mol-polecat-commit wiring to deliver-close/pr-autopilot | in CI (ci.yml:102) |
| `tests/dispatch-door-guard-test.sh` | ops | bin/dispatch-door-guard (O03 raw-sling bypass detection) | in CI (ci.yml, "O03 dispatch-door-guard...") |
| `tests/dispatch-door-test.sh` | ops | bin/dispatch-door (O03 dispatch door: target/formula/--reassign for every rig) | in CI (ci.yml, "O03 dispatch-door validates...") |
| `tests/escalation-door-test.sh` | ops | bin/escalation-door (O06 escalation write door + routing rules); fixture escalation-door | in CI (ci.yml:110); replaces the retired campaign-pointer-test.sh |
| `tests/factory-build-gates-test.py` | ops | bin/factory-build-gates (installs .gc/scripts gates into rigs) | in CI (ci.yml:149); scripts/validate_build_artifact.py etc. are generated/copied in temp, not missing |
| `tests/factory-delivery-guard-test.sh` | ops | bin/factory-delivery-guard | in CI (ci.yml:191) |
| `tests/factory-delivery-proof-test.py` | ops | lib/factory_delivery_proof.py | in CI (ci.yml:188); docstring line 118 cites retired lib/factory_cockpit.py |
| `tests/factory-dispatch-guard-test.sh` | ops | bin/factory-dispatch-guard | in CI (ci.yml:197) |
| `tests/factory-do-work-workspace-test.sh` | ops | bin/factory-do-work-workspace + lib/protected_rigs.sh | in CI (ci.yml:233) |
| `tests/factory-doctor-test.py` | ops | factory-doctor classification | in CI (ci.yml:128); one example path rigs/saymyname-frontend (cosmetic) |
| `tests/factory-gh-rollup-test.py` | ops | gh status rollup helper | in CI (ci.yml:185) |
| `tests/factory-guard-dirty-tree-test.sh` | ops | bin/factory-guard dirty-tree check | in CI (ci.yml:119) |
| `tests/factory-guard-exec-bit-test.sh` | ops | bin/factory-guard exec-bit check | in CI (ci.yml:227) |
| `tests/factory-guard-live-root-sync-test.sh` | ops | bin/factory-guard live-root sync | in CI (ci.yml:122) |
| `tests/factory-guard-provider-overlay-test.sh` | ops | bin/factory-guard provider overlay | in CI (ci.yml:146); comment line 40 still mentions campaign liveness (section removed per legacy/README.md:32) |
| `tests/factory-guard-session-boot-test.sh` | ops | bin/factory-guard session-boot alert | in CI (ci.yml:134); header contrasts with retired campaign-progress liveness |
| `tests/factory-guard-worktree-test.sh` | ops | bin/factory-guard worktree check | in CI (ci.yml:96) |
| `tests/factory-live-root-guard-test.sh` | ops | .githooks post-checkout/reference-transaction live-root guard | in CI (ci.yml:230) |
| `tests/factory-main-gate-test.sh` | ops | bin/factory-main-gate + .githooks/pre-push | in CI (ci.yml:209); header cites legacy factory-cockpit-test.py as the incident |
| `tests/factory-observe-test.py` | kernel | factory-observe | in CI (ci.yml:56) |
| `tests/factory-pii-guard-test.sh` | ops | bin/factory-pii-guard | in CI (ci.yml:215); uses synthetic example.com identity |
| `tests/factory-planning-exception-guard-test.sh` | kernel | bin/factory-planning-exception-guard + bin/planning-exception | in CI (ci.yml:206) |
| `tests/factory-provenance-guard-test.sh` | ops | bin/factory-provenance-guard | in CI (ci.yml:218) |
| `tests/factory-session-boot-test.py` | ops | lib/factory_session_boot.py | in CI (ci.yml:131) |
| `tests/factory-shared-drain-workspace-test.sh` | ops | bin/factory-shared-drain-workspace; fixture shared-drain | in CI (ci.yml:155) |
| `tests/factory-waiting-guard-test.sh` | to-redo | bin/factory-waiting-guard (clears gc.waiting_on) | in CI (ci.yml:203) but the guard's stated purpose is re-admitting beads to the idle ladder of legacy/lib/factory_campaign.py (retired) |
| `tests/factory-watchdog-order-test.sh` | to-redo | orders/factory-watchdog.toml via live gc | not in ci.yml; "# ci: local-only"; hardcodes /home/benja/agent-factory exec path |
| `tests/factory-watchdog-test.py` | to-redo | lib/factory_watchdog.py | in CI (ci.yml:137); quarantine fixtures use rig "saymyname-backend" (SayMyName-specific fixture) |
| `tests/factory-watchdog-test.sh` | to-redo | bin/factory-watchdog | in CI (ci.yml:140); rig list + repo saymyname-*; comment mentions cockpit signal file / campaign liveness |
| `tests/factory-work-dispatch-test.sh` | ops | bin/factory-work-dispatch | in CI (ci.yml:200) |
| `tests/fixture-city-oracle-test.py` | kernel | Fixture City oracle; fixture fixture-city | in CI (ci.yml:75); legacy-* cases assert retired paths fail closed (correct) |
| `tests/fixtures/build-basic-fail-fast` | to-redo | build-basic-fail-fast-runtime-test.sh only | used only by a local-only test that never runs automatically |
| `tests/fixtures/deliver-close` | ops | deliver-close-test.sh | fake gc/gh for deliver-close |
| `tests/fixtures/escalation-door` | ops | escalation-door-test.sh | fake gc for the live escalation door |
| `tests/fixtures/fixture-city` | kernel | fixture-city-oracle-test.py | synthetic fixture-* rigs; legacy-*.json are fail-closed probes |
| `tests/fixtures/planning-exception` | kernel | planning-exception-test.py | graph + fake ticket-graph-publish |
| `tests/fixtures/planning-run-router` | to-redo | planning-run-router-test.py | session fixtures sign "confirmed_by": "Benjamin" (real operator name) 20x |
| `tests/fixtures/planning-run-to-spec` | to-redo | planning-run-to-spec-oracle-test.py | session fixtures sign "confirmed_by": "Benjamin" (real operator name) in all 12 sessions |
| `tests/fixtures/project-isolation` | kernel | project-isolation-oracle-test.py | synthetic project-a/b secrets and scenarios |
| `tests/fixtures/project-planning-profile` | kernel | project-planning-profile-test.py | invalid-saymyname.json is a deliberate negative case (SMN-42 fake key) |
| `tests/fixtures/shared-drain` | ops | factory-shared-drain-workspace-test.sh | fake gc/gh |
| `tests/fixtures/spec-approve` | kernel | spec-approve-test.py | synthetic spec drafts |
| `tests/fixtures/ticket-graph-publish` | kernel | ticket-graph-publish-test.py, planning-run-router-test.py, planning-exception-test.py | fake bd |
| `tests/fixtures/wayfinding-run` | kernel | wayfinding-run-test.py | synthetic requests |
| `tests/goal-delivery-pairs-test.sh` | ops | bin/goal-delivery-pairs | in CI (ci.yml:194) |
| `tests/on-order-failed-test.sh` | ops | bin/on-order-failed | in CI (ci.yml:221); comment cites legacy factory-cockpit-chaos-test.py |
| `tests/on-session-stranded-test.sh` | ops | bin/on-session-stranded | in CI (ci.yml:224); comment cites legacy factory-cockpit-chaos-test.py |
| `tests/operator-context-test.sh` | ops | AGENTS.md/Mayor prompt/OPERATOR_BRIDGE free of retired commands | in CI (ci.yml:125); asserts absence of cockpit/product-queue/saymyname (correct) |
| `tests/planning-allocation-prototype-test.py` | kernel | planning allocation prototype | in CI (ci.yml:78) |
| `tests/planning-exception-test.py` | kernel | planning-exception; fixtures planning-exception + ticket-graph-publish | in CI (ci.yml:50) |
| `tests/planning-map-concurrency-prototype-test.py` | kernel | planning map concurrency prototype | in CI (ci.yml:90) |
| `tests/planning-run-resume-oracle-test.py` | kernel | Planning Run resume oracle | in CI (ci.yml:81) |
| `tests/planning-run-router-test.py` | kernel | planning-run-router; fixtures planning-run-router + ticket-graph-publish | in CI (ci.yml:53); legacy_path rejection + "ntfy" as C01 reservation requirement are intended |
| `tests/planning-run-to-spec-oracle-test.py` | kernel | Planning Run to Spec oracle; fixture planning-run-to-spec | in CI (ci.yml:84) |
| `tests/pr-autopilot-candidate-duplicate-test.sh` | to-redo | bin/pr-autopilot | in CI (ci.yml:182); fixture rigs saymyname-backend/frontend mirror hardcoded lib/protected_rigs.sh |
| `tests/pr-autopilot-ci-failure-test.sh` | to-redo | bin/pr-autopilot | in CI (ci.yml:167); same SayMyName rig fixture |
| `tests/pr-autopilot-reconcile-cache-test.sh` | to-redo | bin/pr-autopilot | in CI (ci.yml:176); asserts saymyname-app/Say-my-name-back#61 |
| `tests/pr-autopilot-reversibility-test.sh` | to-redo | bin/pr-autopilot + orders/pr-autopilot.toml | in CI (ci.yml:161); asserts saymyname-app/Say-my-name-back + "Backend CI" |
| `tests/pr-autopilot-stale-snapshot-test.sh` | to-redo | bin/pr-autopilot | in CI (ci.yml:173); same SayMyName rig fixture |
| `tests/pr-autopilot-step-wisp-collision-test.sh` | to-redo | bin/pr-autopilot | in CI (ci.yml:179); same SayMyName rig fixture |
| `tests/pr-autopilot-stuck-test.sh` | to-redo | bin/pr-autopilot | in CI (ci.yml:164); asserts saymyname-app/Say-my-name-back |
| `tests/pr-autopilot-transient-retry-test.sh` | to-redo | bin/pr-autopilot | in CI (ci.yml:170); asserts saymyname-app/Say-my-name-back |
| `tests/pre-push-ci-registration-test.sh` | ops | .githooks/pre-push runs ci-registration | in CI (ci.yml:212) |
| `tests/project-isolation-oracle-test.py` | kernel | project isolation oracle; fixture project-isolation | in CI (ci.yml:93) |
| `tests/project-planning-profile-test.py` | kernel | project-planning-profile; fixture project-planning-profile | in CI (ci.yml:41); rejects SayMyName-specific fields (correct) |
| `tests/provider-failover-test.py` | to-redo | bin/provider-failover | in CI (ci.yml:143); fixtures carry SayMyName backend output + saymyname-backend sessions + inert gc.campaign_* metadata |
| `tests/reversibility-test.py` | ops | reversibility classifier (pr-autopilot) | in CI (ci.yml:158) |
| `tests/role-qualification-oracle-test.py` | kernel | role qualification oracle | in CI (ci.yml:87) |
| `tests/spec-approve-test.py` | kernel | spec-approve; fixture spec-approve | in CI (ci.yml:47) |
| `tests/ticket-graph-publish-test.py` | kernel | ticket-graph-publish; fixture ticket-graph-publish | in CI (ci.yml:38) |
| `tests/wayfinding-run-test.py` | kernel | wayfinding-run; fixture wayfinding-run | in CI (ci.yml:44) |
