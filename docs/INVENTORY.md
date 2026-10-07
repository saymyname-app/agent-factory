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
| kernel | 75 |
| ops | 99 |
| to-redo | 37 |
| legacy | 0 |
| **total** | **211** (fixture directories counted once each; O14/af-8l3ea moved 6 files to `legacy/`, re-verdicted 4, and added 3 new files — `bin/factory-setup`, `config/operator.toml`, `tests/factory-setup-test.sh` — see F12, F15, F17, F19, F20, F23 and the PII-guard row; P21/af-k91yx re-verdicted 5 more — `bin/factory-watchdog`, `orders/factory-watchdog.toml`, `orders/pr-autopilot.toml`, `tests/factory-watchdog-test.{py,sh}` — from `to-redo` to `ops`) |

## Findings

| ID | Sev | Where | Problem | Disposition |
|---|---|---|---|---|
| F01 | med | `bin/`, `lib/`, `tests/`, `config/` | 15 comments/diagnostics named `legacy/` paths | FIXED #251 + `tests/legacy-isolation-test.sh` |
| F02 | high | `bin/campaign-pointer` | `escalate` marks any bead, `clear-decision` only cleared `af-1vr4`: a work-bead escalation could never be cleared through the door (live: af-y2jgr, af-3pt18) | FIXED #252 |
| F03 | med | `docs/DELIVERY.md` | says claude defaults to `plan`/`claude-sonnet-5`; `city.toml` sets `unrestricted`/`sonnet-5` and the guard treats `plan` as broken; says "no Actions workflows" though `ci.yml` exists; points at `DESIGN_GOVERNANCE.md` (legacy only) | A4-DOCS |
| F04 | med | `AGENTS.md`, `README.md`, `docs/OPERATOR_BRIDGE.md`, `docs/OPERATIONS.md` | "campaign liveness" invariant; product status/preview "configured"; examples route to the product queue; `derive_delivery()` exists only in legacy; "off-box backup not configured" (live: `jsonl-export` every 15 min to the private archive repo) | A4-DOCS |
| F05 | low | `AGENTS.md`, `city.toml`, `config/provider-policy.json`, `config/model-catalog.json`, `bin/provider-failover` (help + generated header) | "change providers from the cockpit"; only `provider-failover set` exists | A4-DOCS |
| F06 | low | `orders/provider-failover.toml`, `formulas/mol-*`, `bin/factory-boot`, `bin/pr-autopilot`, `bin/factory-observe` | descriptions still cite the campaign (parking, liveness, idle ladder, `gc.campaign_progress_at`, "for the dashboard"); pr-autopilot "never touches PRs targeting main" is false (Factory `main` is armed) | A4-DOCS (P24 already removed `bin/factory-delivery-guard`'s "for the SayMyName rigs"/campaign wording; P21, af-k91yx: `orders/factory-watchdog.toml` and `orders/pr-autopilot.toml` FIXED and split out of this row's file list — see their own rows below; remaining files unchanged) |
| F07 | low | `docs/FACTORY_OBSERVE.md`, `docs/ADAPTATION_REGISTER.md`, `docs/GETTING_STARTED.md`, `docs/FACTORY_TOOLS.md` | legacy improvement-axes cited as a live pattern; `bin/factory-cockpit` cited; "C01 reservation" (active one is factory-operations-v2); "5 providers" checked (loop checks 4); `docs/PLANNING_RUN_RESUME_PROTOTYPE.md` retired with P04 (W12, af-eyxetw) |
| F08 | low | `lib/factory_watchdog.py:263`, `lib/provider_failover.py:93`, 5 test comments, `tests/coordination-pointer-doors-test.sh` | comments point at deleted tests / retired `product-queue`, `gc.queue_state` | A4-DOCS |
| F09 | low | `agents/mayor/prompt.template.md` | says `build-basic` "comes from the pack" (a local fork in `formulas/` overrides it) | A4-DOCS |
| F10 | med | `docs/decisions/ADR-0026-*.md`, `docs/DELIVERY.md:188` | rely on the retired `mayor-campaign` readiness lane; needs the same dated amendment ADR-0025 got | A4-DOCS |
| F11 | med | `lib/protected_rigs.sh`, `bin/deliver-close:127-139`, `bin/factory-guard:384`, `bin/factory-delivery-guard:84`, `bin/factory-watchdog:58`, `city.toml` (`[[patches.agent]] dir=saymyname-*`, `/home/benja` paths), `.githooks/post-checkout:20`, `pr-autopilot-*`/watchdog/failover test fixtures | SayMyName and host paths hardcoded in a project-agnostic Factory; `deliver-close` duplicates the "single source"; a new project's rig gets no guard coverage and no warning | FIXED (O01, af-vsevn): `config/projects/<project>.toml` (one file per project, `config/projects/agent-factory.toml` plus the two SayMyName rigs) is now the single source; `lib/protected_rigs.sh`, `bin/factory-guard`, `bin/factory-delivery-guard` and `bin/deliver-close` all read it through the shared project-registry loader instead of a hardcoded rig list |
| F12 | med | `bin/factory-waiting-guard`, `bin/factory-guard` §11 + tests | only reader of `gc.waiting_on` was the retired idle ladder (verdict `legacy`) | RE-JUSTIFIED (O14, af-8l3ea): `bin/pr-autopilot`'s `active_waiters_for` reads `gc.waiting_on` to decide whether a reconciled merge outside its wake window still needs to wake the Mayor; a stale value would corrupt that live check, so the guard that keeps it accurate stays in service |
| F13 | med | `bin/campaign-pointer` start/finish, Mayor prompt 283-286 | write `gc.current`, `gc.current_jit`, `gc.last_delivered`, `gc.campaign_progress_at` that nothing outside legacy reads; lock named after the campaign | FIXED (O06, af-sau1a): `campaign-pointer` retired entirely, its dead fields no longer written anywhere |
| F14 | med | `formulas/mol-scoped-work.formula.toml` | prints "refuses base=main" then pushes/opens a PR against `main` (default base); escalation goes to `/dev/null \|\| true` (silent failure) | PARTIALLY FIXED (O06, af-sau1a): `notify-failure` now calls `escalation-door mayor` and `exit 1`s if it fails; the base=main misprint is untouched |
| F15 | low | `formulas/mol-scoped-work`, `formulas/mol-polecat-commit`, `agents/claude-reviewer`, `bin/factory-observe`, `bin/factory-resources`, `bin/goal-delivery-pairs`, 5 prototype/oracle scripts | no runtime caller (only tests/docs); `mol-polecat-commit` refuses base `main` so cannot run on the Factory repo | RESOLVED per-item (O14, af-8l3ea): `mol-scoped-work`/`mol-polecat-commit` are wired — `bin/dispatch-door` validates and routes both against `config/projects/saymyname-{backend,frontend}.toml`'s `formulas` list (O03, af-ui0ua landed after this finding was written; nothing dispatches them yet, but the door accepts them for the theme that needs worktree isolation on those rigs). `claude-reviewer` retired — no prompt or formula ever dispatched it, and the dispatch door has no path for an ad-hoc named reviewer session outside a rig's fixed `sling_target`; moved to `legacy/agents/`. `factory-observe`, `factory-resources`, `goal-delivery-pairs` and the 5 prototype/oracle scripts keep their existing `kernel`/`ops` verdicts unchanged: each is a deliberate, documented capability (B09 kernel foundation; manual operator tools; one-time Planning Run proofs) whose lack of a runtime caller is by design, not drift |
| F16 | low | Mayor prompt, `bin/factory-work-dispatch` | GUARDED Factory work goes to `build-basic` but no target is named, and `factory-work-dispatch` accepts only `mol-do-work` | FIXED (O03, af-ui0ua): `bin/dispatch-door` resolves target and validates formula for every rig (`build-basic` included) from `config/projects/*.toml`; `factory-work-dispatch` wraps it; `bin/dispatch-door-guard` reports any dispatch that bypasses it |
| F17 | med | `.githooks/`, `docs/GETTING_STARTED.md` | a fresh clone runs without PII guard, main gate or live-root hooks: `core.hooksPath` is only in the live `.git/config` | FIXED (O14, af-8l3ea): `bin/factory-setup` runs `git config core.hooksPath .githooks` (idempotent) so a fresh clone plus the setup script has the hooks active |
| F18 | med | `bin/planning-run-router:130-149` (deleted, A6b W10) | `clear_reservation` rewrites tracked `config/planning-run-reservation.json` in the live root (dirty tree, guard snapshots, drift from `main`) | OPEN, tracked: `clear_reservation`/`set_reservation` still `Path.write_text` the tracked file directly (verified live 2026-09-28); no O-ticket touched this write path. Follow-up bead af-1hvva. Addendum (A6b, W10, 2026-09-30): the cited router is deleted; `config/planning-run-reservation.json` is now read by `bin/spec-approve bd-approve` and advanced by `bin/ticket-graph-publish bd-publish` (`bin/planning-run-reservation` itself), neither of which reproduces this direct-write pattern -- af-1hvva should be re-checked for continued relevance against the current writers |
| F19 | low | `bin/factory-guard:138`, `city.toml`, provider policy, model catalog | `claude-fable` defined in `city.toml`, checked nowhere, absent from policy and catalog | FIXED (O14, af-8l3ea): no agent, order or formula ever names `claude-fable`, so it is commented out of `city.toml` (same treatment as the unused `claude-opus` tier already there) instead of checked by the guard |
| F20 | low | `config/factory-observe*.schema.json` | no code loads either schema (validation hand-written); the doc says the policy is validated against it | FIXED (O14, af-8l3ea): both schema files moved to `legacy/config/` (neither had a reader); `docs/FACTORY_OBSERVE.md`, `docs/CONTEXT_INDEX.md` and `bin/factory-observe`'s docstring now point at the hand-written validators (`lib/factory_observe.py`, `lib/factory_measures.py`) instead of a schema file nothing loads |
| F21 | low | `tests/build-basic-fail-fast-runtime-test.sh`, `tests/factory-watchdog-order-test.sh` | local-only tests run nowhere automatically; the second hardcodes `/home/benja/agent-factory` | PARTIALLY FIXED (O13): new `local-only-tests` order (`orders/local-only-tests.toml`, `bin/local-only-tests`) runs both nightly and pages the Mayor on failure. The hardcoded path in `factory-watchdog-order-test.sh` is untouched -- it matches the live root by design, which is what this order runs against. |
| F22 | med | `docs/DELIVERY.md:558-577`, `docs/OPERATIONS.md:389-506` | SayMyName-only rig contracts and operations; `gc bd create --rig saymyname-*` contradicts "new work enters through the Planning Run router" | FIXED (O15, af-rse7p): SayMyName rig contracts moved out of `docs/DELIVERY.md`/`docs/OPERATIONS.md` into each product repo's own file; remaining Factory-doc mentions are either the Factory's own GitHub repo slug (`saymyname-app/agent-factory`) or pointers into `legacy/docs/products/saymyname/`, not a live SayMyName-only section |
| F23 | low | planning-run fixtures (15 files), watchdog / planning-exception-guard tests, `provider-failover-test.py` | operator's first name and GitHub login as signer; SayMyName backend test output as fixture | FIXED (O14, af-8l3ea): `tests/provider-failover-test.py`, `tests/factory-watchdog-test.{sh,py}` and `tests/factory-planning-exception-guard-test.sh` now use the synthetic `operator-1` instead of the operator's real name or GitHub login. Runtime messages: `bin/escalation-door`'s mail/printed text now names the operator from `config/operator.toml` (`GC_OPERATOR_NAME` override, defaulting to that file's `name`) instead of a hardcoded string; the `gc.needs_benjamin` metadata field, the `benjamin` subcommand and the "NEEDS BENJAMIN" list name are a separate, stable schema/concept and are unchanged (renaming those is topology, not this ticket's repair). No "SayMyName backend test output as fixture" was found under `tests/fixtures/` to replace — the only SayMyName-named fixture (`tests/fixtures/project-planning-profile/profiles/invalid-saymyname.json`) is deliberate rejection-rule test data, not captured backend output. Addendum (O16, af-dqhwo, 2026-09-29): the "planning-run fixtures (15 files)" half of this finding was still open — `confirmed_by`/`statement` fields in 16 files under `tests/fixtures/planning-run-to-spec/`, `tests/fixtures/planning-run-router/` and `tests/fixtures/spec-approve/` still carried the operator's real first name. Replaced with the same synthetic `operator-1` (`draft-spec.json`'s `content_digest` recomputed to match); the `escalation-door benjamin` subcommand fixture is unchanged, same rationale as above. `tests/spec-approve-test.py`, `tests/planning-run-router-test.py` and `tests/planning-run-to-spec-oracle-test.py` stay green | Addendum (P23, 2026-09-29): re-verified `tests/fixtures/planning-run-router`/`tests/fixtures/planning-run-to-spec` carry no real operator name (the O16 fix above already covers them; those two INVENTORY rows were stale). Found and fixed a separate hardcoded-name spot the earlier passes missed: `bin/pr-autopilot`'s test-4 irreversibility escalation mail hardcoded "Benjamin" in its message text — now reads `OPERATOR_NAME` from `config/operator.toml` (`GC_OPERATOR_NAME` override), same pattern as `bin/escalation-door`. Also replaced the six `tests/pr-autopilot-*-test.sh` files' hardcoded SayMyName rig names with a synthetic `tests/fixtures/pr-autopilot-projects/` project fixture, loaded via a new `PROTECTED_RIGS_CONFIG_DIR` override in `lib/protected_rigs.sh` (default unchanged, so production dispatch/pr-autopilot behavior is untouched) |
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
| `GLOSSARY.md` | kernel | ADR-0028, refactor spec | project-agnostic domain glossary |
| `README.md` | ops | entry point | FIXED (A4 wording fixes, #254): "Current status" separates what is configured from what is retired (product status/preview); no longer contradicts itself |
| `agents/factory-worker/agent.toml` | kernel | bin/factory-work-dispatch, city.toml, mayor prompt, tests/factory-work-dispatch-test.sh | The HQ implementation role every approved-graph af-* bead goes to |
| `agents/factory-worker/prompt.template.md` | kernel | factory-worker sessions | Generic graph.v2 claim/close protocol; no drift found vs gc hook/bd usage |
| `agents/mayor/agent.toml` | kernel | pack.toml named_session mayor | Mayor provider pin |
| `agents/mayor/prompt.template.md` | kernel | Mayor named session (pack.toml) | FIXED (P17, af-puf4p): already cites `escalation-door` correctly (O06, af-sau1a); the GUARDED HQ dispatch gap is now stated explicitly (`agent-factory`'s project file allows only `mol-do-work`, so a GUARDED HQ bead escalates instead of routing to `build-basic`) |
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
| `bin/deliver-close` | ops | mol-do-work, pr-autopilot, factory-delivery-guard, planning-exception-guard, CI | Live delivery door (ADR-0009/0016/0028); FIXED (O01/P24): required-workflow lookup reads config/projects/*.toml via project_registry_ci_for_repo instead of a hardcoded repo map; tests/deliver-close-test.sh covers a repo named only in a project file |
| `bin/escalation-door` | ops | mayor prompt (`benjamin`/`mayor`), mol-scoped-work notify-failure, CI test tests/escalation-door-test.sh, coordination-pointer-doors-test.sh | O06 (af-sau1a): the one escalation door; retired `bin/campaign-pointer` (`escalate`/`start`/`finish`/`clear-decision` and its dead `af-1vr4` fields) |
| `bin/evidence-capture` | kernel | docs/EVIDENCE_STORE.md, CI test; the gates and the author/Evaluator formulas of D01 (to come) | NEW (T09, af-pvcg6t): captures an Evidence Record (command run by the tool, or screenshot of the launched product) into the evidence store outside Git, fingerprint written through bin/convoy-state; `verify`, `purge --spec`; T10 (af-j8jo02): `command --expect-exit` files the piece only on the expected exit code |
| `bin/factory-boot` | ops | Windows logon task (external), docs/RUNBOOK_STOP_AND_RESTART.md | Restart restore; one stale "campaign" log string |
| `bin/factory-build-gates` | ops | factory-boot, factory-guard, CI test | CLI wrapper for lib/factory_build_gates.py (materialises pack check scripts) |
| `bin/factory-delivery-guard` | ops | factory-guard, CI test | Live proof-field backfill; FIXED (O01/P24): RIGS built from project_registry_rig_names(config/projects/*.toml) instead of a hardcoded list, and the header comment's stale retired-campaign/product-status rationale is removed; tests/factory-delivery-guard-test.sh covers a rig named only in a project file |
| `bin/dispatch-door` | kernel | mayor prompt, factory-work-dispatch, CI test | O03 (af-ui0ua): the one door for every rig/formula, validated from config/projects/*.toml |
| `bin/dispatch-door-guard` | ops | factory-guard §10b, CI test | O03 (af-ui0ua): reports (does not repair) a raw gc sling that bypassed bin/dispatch-door |
| `bin/factory-dispatch-guard` | ops | factory-guard, CI test | Self-heals sling without --reassign (af-33a4e); coherent with Mayor prompt |
| `bin/factory-do-work-workspace` | ops | mol-do-work (enter/finish), pr-autopilot, factory-watchdog, CI test | Worktree isolation for protected branches via lib/protected_rigs.sh |
| `bin/factory-doctor` | ops | operator tool (docs), CI test | Classifies gc doctor output ACTIONABLE/UPSTREAM; no order |
| `bin/factory-gh-rollup` | ops | pr-autopilot, factory-watchdog, mayor prompt, CI test | Rebuilds statusCheckRollup for fine-grained PAT; usage matches prompt |
| `bin/factory-guard` | to-redo | orders/factory-guard.toml (5m), git hooks, factory-boot | Core live guard, but §5 hardcodes SayMyName rigs, §7/7b store dedup on campaign bead af-1vr4, §11 serves the retired idle ladder |
| `bin/factory-main-gate` | ops | .githooks/pre-push, factory-watchdog, CI tests | Pre-push main landing gate (ADR-0020); header cites legacy incident only as history |
| `bin/factory-observe` | kernel | CI test, docs/FACTORY_OBSERVE.md | B09 observe/wake kernel; no order or script calls it at runtime (see findings) |
| `bin/factory-planning-exception-guard` | kernel | factory-guard §12, deliver-close, CI test | Detection net for ADR-0028 semantic/topology closes |
| `bin/factory-provenance-guard` | ops | Backend/Frontend CI workflows (backend-ci.yml, frontend-ci.yml), CI test | Layer B PII provenance guard run by product-repo CI |
| `bin/factory-resources` | ops | operator tool (docs/RUNBOOK_STOP_AND_RESTART.md) only | Host RAM/swap headroom check; no order, no test |
| `bin/factory-setup` | ops | docs/GETTING_STARTED.md, CI test | NEW (O14, F17): one-time fresh-clone bootstrap — sets `core.hooksPath=.githooks`, restores the executable bit if a clone drops it |
| `bin/factory-shared-drain-workspace` | ops | assets/workflows/build-basic/{prepare-shared-worktree,publish,cleanup-shared-worktree}.md, CI test | Shared-drain worktree adapter for build-basic same-session |
| `bin/factory-waiting-guard` | ops | factory-guard §11, CI test | RE-JUSTIFIED (O14, F12): maintains `gc.waiting_on`, which `bin/pr-autopilot`'s `active_waiters_for` now reads live to decide whether a reconciled merge still needs to wake the Mayor |
| `bin/factory-watchdog` | ops | orders/factory-watchdog.toml, CI tests | Live paging (§1-4,7); FIXED (O06, af-sau1a): the reader-less cockpit signal file is no longer written. FIXED (P21, af-k91yx): remaining campaign/cockpit mentions in the header are explicitly marked retired/historical (incident context, retired checks), except "blocks the campaign" which described current behavior in present tense — reworded to "halts the Factory" |
| `bin/factory-work-dispatch` | kernel | mayor prompt, CI test | The HQ convenience wrapper (factory-worker, mol-do-work, --reassign) around bin/dispatch-door (O03) |
| `bin/graph-review` | kernel | /to-tickets session (`review`, `remaining`, `decide`), mol-graph-review (`brief`, `record`), ticket-graph-publish (`check`), CI test | NEW (T08, af-n575g4): graph reviewer before Benjamin's approval; only reader and writer of `gc.graph_review.*` on a Ticket Graph Draft bead (`docs/GRAPH_REVIEW.md`) |
| `bin/fixture-city-oracle` | kernel | CI test, project-isolation-oracle, docs | Fixture-city oracle (ADR-0027 legacy_path fences) |
| `bin/goal-delivery-pairs` | ops | docs/DELIVERY.md, CI test | Read-only multi-rig delivery-pair query; no runtime caller |
| `bin/on-order-failed` | ops | orders/on-order-failed.toml, CI test | Pages Mayor on repeated order failure; FIXED (O06, af-sau1a): no longer writes the reader-less signal file |
| `bin/on-session-stranded` | ops | orders/on-session-stranded.toml, CI test | Reopens orphaned beads + pages; FIXED (O06, af-sau1a): no longer writes the reader-less signal file |
| `bin/planning-exception` | kernel | mayor prompt, deliver-close, factory-guard, planning-exception-guard, CI | ADR-0028 Planning Exception register; subcommands match docs |
| `bin/pr-autopilot` | ops | orders/pr-autopilot.toml (3m), CI tests | Arms/finalizes PRs from lib/protected_rigs.sh; header "for the SayMyName rigs" stale |
| `bin/project-isolation-oracle` | kernel | CI test, docs | Project isolation oracle |
| `bin/project-launch` | kernel | docs/PROJECT_PLANNING_PROFILE.md, CI test | NEW (T01, af-m8m1kc): `start`/`stop` a declared project's product at an exact commit, on an isolated port, against a named synthetic dataset -- clean `git worktree` checkout, never the caller's working tree; T10 (af-j8jo02): `--repo-root` launches a product that lives in another repository than the Factory, the profile tool being loaded from the launcher's own directory |
| `bin/project-planning-profile` | kernel | docs/GETTING_STARTED.md, docs/PROJECT_PLANNING_PROFILE.md, CI test | Per-project planning profile validator (rejects SayMyName-specific fields by design); `describe`'s optional `launch` block (T01, af-m8m1kc) is `bin/project-launch`'s input; T10 (af-j8jo02): optional `launch.red_error_types` and `launch.import_rule`, read by bin/tdd-step |
| `bin/prototype-conformance` | kernel | bin/spec-approve bd-approve, docs/VALIDATED_PROTOTYPE.md, CI test | NEW (T07, af-tvda3w): `check` a Validated Prototype directory against its six properties, one record per property |
| `bin/provider-failover` | ops | orders provider-failover + model-staleness-check, factory-boot, factory-guard | FIXED (P20, af-r48pb): help/status/set text names no cockpit or campaign; live failover unchanged |
| `bin/reversibility-check` | ops | pr-autopilot, factory-watchdog, CI test | ADR-0019 reversibility gate CLI |
| `bin/spec-approve` | kernel | CI test | Spec approval stage; bead mode only (`bd-approve`/`bd-status`) since A6b W10 retired the file-Spec mode with the router; FIXED (T07, af-tvda3w): also refuses a Spec without numbered user stories, or with an interface story and no complete reference, state inventory or conformant Validated Prototype on the remote repository; T06 (af-cgauf8): `outline` prints the numbered user stories and Testing Decisions of a Spec text read on stdin, for the publication door |
| `bin/spec-integration` | kernel | docs/SPEC_INTEGRATION.md, CI test; ticket-graph-publish (`open`), convoy-advance (`merge`) | NEW (T18, af-gmz9s1): the integration branch of a marked convoy's Spec and the serial merge of its tickets -- `open` (branch `integration/<spec id>` at the tip of the protected branch, recorded on the convoy), `merge` (finished tickets one at a time in a work tree of its own, the protected branch taken up first, the profile's regression command run on each merged result by bin/evidence-capture as piece `merged_tests`, a conflict or a red returned to the author, a verdict outdated by a newer commit invalidated with one resume); state written by bin/convoy-state `set-integration` / `set-merge` / `invalidate-verdicts` |
| `bin/tdd-step` | kernel | docs/TDD_STEP.md, CI test; formulas/mol-ticket-author (through bin/ticket-author) | NEW (T10, af-j8jo02): proves the TDD of a ticket of a marked convoy -- `red` (test perimeter, criterion -> test table, healthy product, one assertion failure per criterion test at the start commit, proof of the seam), `freeze` (registry of fingerprints in the evidence store), `green` (frozen files unchanged, k runs), `amend` (once per ticket), `prefactoring` (regression command before and after); each check sealed by bin/evidence-capture, each step written by bin/convoy-state `set-tdd` / `stop-ticket` |
| `bin/ticket-exit` | kernel | docs/TICKET_EXIT.md, CI test; formulas/mol-ticket-author (through bin/ticket-author) | NEW (T11, af-egkabn): the structured end of an author's work on a ticket of a marked convoy -- `exit` (finished: refused without a valid Ticket Handoff or on an undeclared deferral marker; planning_exception / operator_request: bin/escalation-door then parking of the ticket and its descendants; technically_blocked: a `repair` drafted by code and published by bin/ticket-graph-publish bd-patch; interrupted: branch pushed, partial Handoff), `read` (the ticket with the Handoff of its closed direct blockers; a session ended without an exit read as interrupted), `deferral` (the detector alone); records sealed by bin/evidence-capture (`handoff_records`), state written by bin/convoy-state `set-handoff` / `park` / `set-exit` |
| `bin/ticket-author` | kernel | docs/TICKET_AUTHOR.md, CI test; formulas/mol-ticket-author (each step), `.gc/scripts/checks/ticket-author-check.sh` (the exec check of each step) | NEW (T12, af-i3q5a5): what the author formula runs and what its checks read -- `start` (work tree and branch `ticket/<id>` from the tip of the Spec's integration branch, session recorded by bin/convoy-state `set-session`), `demonstrate` (launches the product at the head commit with bin/project-launch and seals the capture of the demonstration line with bin/evidence-capture, piece `demonstration`), `gate --step workspace\|red\|code\|demonstration\|exit` (reads the tracker, the evidence store and the branch tip, never a statement of the session), `check` (the same gate for the step Gas City is closing), `locate`, `release` |
| `bin/test-review` | kernel | docs/TEST_REVIEW.md, CI test; formulas/mol-ticket-author (red step: `review`), formulas/mol-test-review (`brief`, `record`), bin/convoy-advance (`settle`) | NEW (T13, af-nkpjpr): the review of a ticket's criterion tests between red and freeze -- `review` opens it on the fingerprints the freeze seals, routes a review bead through `bin/dispatch-door --role reviewer` and waits for the verdict (0 favorable, 2 returned to the author, 5 ticket stopped, 6 pending); `settle` launches once more a review left without result, stops the ticket after that and raises the stop once through `bin/escalation-door`; state through `bin/convoy-state` only |
| `bin/code-review` | kernel | docs/CODE_REVIEW.md, CI test; bin/convoy-advance (`settle`), formulas/mol-code-review (`brief`, `record`) | NEW (T14, af-96cusm): the code review of a finished ticket before its merge -- `settle` opens the round due at the tip (a review, or the judgement of the answers to its Blocking Findings), routes a review bead through `bin/dispatch-door --role reviewer`, launches once more a review left without result, stops the ticket after that and raises the stop once through `bin/escalation-door`; `brief` is what the reviewer is given (no Handoff, no prose of the author); `record` checks each citation against its source and hands the result to `bin/convoy-state`, which computes the verdict; `respond` records « corrigé » / « contesté »; `bin/spec-integration` merges nothing without a favorable verdict at the tip |
| `bin/ticket-evaluation` | kernel | docs/TICKET_EVALUATION.md, CI test; bin/convoy-advance (`settle`), formulas/mol-ticket-evaluation (`brief`, `record`) | NEW (T15, af-higj9z): the Ticket Evaluation of a finished ticket on the launched product before its merge -- `settle` launches the product from a clean copy of the tip through bin/project-launch (once per dataset), opens the evaluation, routes it to the Evaluator role through bin/dispatch-door, relaunches one left without result then stops the ticket, runs the startup control of a prefactoring without a session, parks a ticket whose criterion cannot be observed (Planning Exception on the operator's list), and stops the products once the states are in; `brief` (demonstration line and frozen criteria, no Handoff, no diff); `record` (one state per criterion, each on a piece captured on a launched product; no verdict from the Evaluator); `verdict` (computed from the tracker, the store and the tip); state through bin/convoy-state only |
| `bin/ticket-graph-publish` | kernel | mayor prompt (bd-patch), planning-exception, CI | `bd-publish`/`bd-patch` only since A6b W10 retired the file-draft mode with the router; T05 (af-c8n7ep): a draft declaring `flow_contract: new-flow/v1` is held to the entry contract and its convoy marked through bin/convoy-state (`docs/ENTRY_CONTRACT.md`); T06 (af-cgauf8): coverage of the Spec's user stories, operator needs (`lift-need`), launch recipe, pointers posed in each ticket, and the same contract on `bd-patch` (repair added without approval, ticket withdrawn on a resolved Planning Exception); T08 (af-n575g4): such a draft is refused by `bd-publish` without a graph review that holds for its digest (`bin/graph-review check`, `docs/GRAPH_REVIEW.md`) |
| `city.toml` | to-redo | gc; factory-guard; provider-failover; build-gates | live, but comments route provider changes via retired cockpit; SayMyName rigs/patches + /home/benja paths |
| `config/factory-observe-policy.json` | kernel | bin/factory-observe, lib/factory_observe.py, test | B09 policy |
| `config/fixture-city-bwrap.apparmor` | kernel | ci.yml, bin/project-isolation-oracle, test | P05 sandbox profile for CI |
| `config/model-catalog.json` | ops | bin/provider-failover check-models, orders/model-staleness-check.toml | coherent; omits claude-fable (skipped by design); description quotes cockpit |
| `config/operator.toml` | ops | bin/escalation-door | NEW (O14, F23): operator display name for runtime messages, read instead of a hardcoded string; `GC_OPERATOR_NAME` overrides |
| `config/planning-run-reservation.json` | kernel | bin/spec-approve bd-approve (checks), bin/ticket-graph-publish bd-publish (advances) | B12 AC#5 reservation: factory-operations-v2 then C01 |
| `config/provider-policy.json` | ops | bin/provider-failover, lib/provider_failover.py | FIXED (P20, af-r48pb): chains live and correct; description points to `bin/provider-failover set`, not the retired cockpit |
| `docs/ADAPTATION_REGISTER.md` | kernel | CONTEXT_INDEX, planning-exception guard, tests | FIXED (P19, af-5l657): AR-004 now cites the pre-refactor improvement-axes register as retired to `legacy/`, not a live pattern |
| `docs/CONTEXT_INDEX.md` | ops | AGENTS.md, README, mayor prompt, operator-context test | updated for legacy split; all cited paths exist |
| `docs/DELIVERY.md` | to-redo | CONTEXT_INDEX, pr-autopilot, reversibility | provider facts contradict city.toml; "no Actions workflows"; missing DESIGN_GOVERNANCE.md; nonexistent scoped Mayor lane; SayMyName rig contracts |
| `docs/FACTORY_OBSERVE.md` | kernel | CONTEXT_INDEX, bin/factory-observe | FIXED (P19, af-5l657): cites the improvement-axes register and its moved JSON Schema as retired to `legacy/`; policy/measures validation text now states plainly it is hand-written with no JSON Schema file backing it |
| `docs/FACTORY_TOOLS.md` | to-redo | CONTEXT_INDEX, ADR-0025 | mostly current; "5 providers" (4 checked); SayMyName example commands |
| `docs/FIXTURE_CITY_ORACLE.md` | kernel | CONTEXT_INDEX, ADR-0027 | fixture oracle contract; cockpit refs are the quarantine fence |
| `docs/GETTING_STARTED.md` | ops | README, CONTEXT_INDEX | FIXED (O14, af-8l3ea; P18, af-stdt7): step 1 has the `bin/factory-setup`/`core.hooksPath` step; step 2's post-removal claim is scoped to the `[[rigs]]` entry and now names the inert `[[patches.agent]]` leftovers `gc rig remove` does not touch |
| `docs/OPERATIONS.md` | ops | README, CONTEXT_INDEX, RUNBOOK | FIXED (P19, af-5l657): SayMyName cutover/M6 rollback retired to `legacy/docs/products/saymyname/CUTOVER_AND_M6_ROLLBACK.md`; no `gc bd create` new-work section, no `derive_delivery()` reference, and off-box backup now accurately describes the live `core/jsonl-archive` order |
| `docs/OPERATOR_BRIDGE.md` | ops | AGENTS.md, README, operator-context test | FIXED (legacy PR 5b/5, #250): the "Product candidate queue" section and its example intents were purged with the rest of the retired product queue; current examples route through the Mayor/Planning Run flow |
| `docs/PLANNING_EXCEPTION.md` | kernel | CONTEXT_INDEX, planning-exception guard | B08 doc |
| `docs/PLANNING_RUN.md` | kernel | CONTEXT_INDEX, GETTING_STARTED, issue-tracker | A6b, W09: the wired chain (`/wayfinder`, `/to-spec`, `spec-approve`, `/to-tickets`, `ticket-graph-publish`), No-fog exit, overflow rule |
| `docs/PLANNING_RUN_ROUTER.md` | kernel | PLANNING_RUN | A6b, W09: reduced to a one-line pointer to PLANNING_RUN.md; retiring in W10 |
| `docs/PLANNING_RUN_TO_SPEC_PROTOTYPE.md` | kernel | CONTEXT_INDEX | B03 doc |
| `docs/PROJECT_ISOLATION_PROTOTYPE.md` | kernel | CONTEXT_INDEX | P05 doc |
| `docs/PROJECT_PLANNING_PROFILE.md` | kernel | CONTEXT_INDEX, GETTING_STARTED, OPERATOR_BRIDGE | B02 doc; SayMyName mentions are the rejection rule |
| `docs/RESEARCH_BRIEF.md` | ops | CONTEXT_INDEX, DELIVERY | External Evidence Gate template |
| `docs/RUNBOOK_STOP_AND_RESTART.md` | ops | AGENTS.md, bin/factory-boot, CONTEXT_INDEX | commands verified; minor hardcoded SayMyName rig loop (:42) |
| `docs/SECURITY.md` | ops | CONTEXT_INDEX, OPERATOR_BRIDGE | generic trust boundaries |
| `docs/SPEC_APPROVE.md` | kernel | CONTEXT_INDEX | B05 doc; subcommands match |
| `docs/WAYFINDING_RUN.md` | kernel | PLANNING_RUN | A6b, W09: reduced to a one-line pointer to PLANNING_RUN.md; retired in W11 |
| `docs/decisions/ADR-0025-approved-graph-bootstrap-scope.md` | kernel | CONTEXT_INDEX | amended 2026-09-26 for campaign removal |
| `docs/decisions/ADR-0026-structural-delivery-completion-gate.md` | to-redo | CONTEXT_INDEX | point 5 and reversal still rely on mayor-campaign scoped readiness (legacy); no amendment |
| `docs/decisions/ADR-0027-legacy-planning-and-cockpit-v1-quarantine.md` | kernel | CONTEXT_INDEX, B12 note | quarantine fence; legacy paths intentional |
| `docs/decisions/ADR-0028-planning-exception-routing.md` | kernel | CONTEXT_INDEX | B08 ADR |
| `docs/planning/B12-redecomposition-planning-run-router.md` | kernel | CONTEXT_INDEX, reservation config | status updated; activation-switch paths explicitly not built; the router it named is deleted (A6b, W10) -- archived planning record, not rewritten |
| `docs/planning/agent-factory-project-agnostic-refactor-spec.md` | kernel | ADR-0027 | approved refactor Spec |
| `docs/planning/agent-factory-project-agnostic-refactor-ticket-graph-draft.yaml` | kernel | tests/ticket-graph-publish-test.py, B12 note | refactor ticket graph; test input |
| `docs/research/2026-09-22-agent-factory-refactor-grilling-checkpoint.md` | kernel | ADR-0028 | dated refactor design checkpoint |
| `docs/research/2026-09-22-agentic-factory-autonomy-frontier.md` | kernel | grilling checkpoint | dated research input (SayMyName-framed, historical) |
| `docs/research/2026-09-23-agentic-tdd-review-workflow.md` | kernel | none (unreferenced) | dated research for Q47-Q48; orphan but harmless |
| `formulas/build-basic-review-scoped.formula.toml` | kernel | build-basic (expand), tests/build-basic-fail-fast-test.py | GUARDED-tier review expansion (local fail-fast fork) |
| `formulas/build-basic.formula.toml` | kernel | mayor prompt GUARDED tier, assets/workflows/build-basic, CI | Local fork overriding the pack's build-basic |
| `formulas/mol-do-work.formula.toml` | kernel | factory-work-dispatch (only formula allowed), mayor prompt default, CI contract test | FIXED (af-jz4zb, P08): description no longer says "for demos" or cites idle ladder/campaign_progress_at — it documents the current workspace-setup/do-work/push-and-pr/drain lifecycle, including the locked, fresh-origin, fail-loud worktree isolation `bin/factory-do-work-workspace enter` now provides |
| `formulas/mol-graph-review.formula.toml` | kernel | bin/graph-review (through `bin/dispatch-door --role reviewer`), `config/projects/agent-factory.toml` (`formulas`) | NEW (T08, af-n575g4): one step, claimed by a read-only session of the reviewer role; never dispatched by the Mayor |
| `formulas/mol-ticket-author.formula.toml` | kernel | bin/convoy-advance (through `bin/dispatch-door --role author`; `config/delivery-flow.json` `start.formula`), `config/projects/agent-factory.toml` (`formulas`) | NEW (T12, af-i3q5a5): the sequence of a ticket of a marked convoy -- workspace, red, code, demonstration, exit -- each step closed only when its exec check (`bin/ticket-author check`) passes; claimed by a fresh session of the author role; never dispatched by the Mayor |
| `formulas/mol-test-review.formula.toml` | kernel | bin/test-review (through `bin/dispatch-door --role reviewer`; `config/delivery-flow.json` `test_review.formula`), `config/projects/agent-factory.toml` (`formulas`) | NEW (T13, af-nkpjpr): one step, claimed by a read-only session of the reviewer role -- the brief, one answer per criterion test, `bin/test-review record`; never dispatched by the Mayor |
| `formulas/mol-code-review.formula.toml` | kernel | bin/code-review (through `bin/dispatch-door --role reviewer`; `config/delivery-flow.json` `code_review.formula`), `config/projects/agent-factory.toml` (`formulas`) | NEW (T14, af-96cusm): one step, claimed by a read-only session of the reviewer role -- the brief, Matt's `code-review` skill called unchanged on the fixed point of the brief, the findings with their citations and one answer per closed question (or one state per Blocking Finding for a judgement), `bin/code-review record`; never dispatched by the Mayor |
| `formulas/mol-ticket-evaluation.formula.toml` | kernel | bin/ticket-evaluation (through `bin/dispatch-door --role evaluator`; `config/delivery-flow.json` `evaluation.formula`), `config/projects/agent-factory.toml` (`formulas`) | NEW (T15, af-higj9z): one step, claimed by a read-only session of the Evaluator role -- the brief, the launched product used as a black box, one captured piece and one state per criterion and for the demonstration line, handed to `ticket-evaluation record`; never dispatched by the Mayor |
| `formulas/mol-polecat-commit.formula.toml` | ops | mayor prompt (optional), factory-delivery-guard, `config/projects/saymyname-{backend,frontend}.toml` (`formulas`), CI contract test | RE-VERDICTED (O14, F15): `bin/dispatch-door` (O03, af-ui0ua) validates and routes it for both SayMyName rigs; refuses base `main` so still unusable on HQ, which is correct since HQ's project file does not list it |
| `formulas/mol-scoped-work.formula.toml` | ops | `config/projects/saymyname-{backend,frontend}.toml` (`formulas`), CI contract test, factory-watchdog test | RE-VERDICTED (O14, F15): `bin/dispatch-door` (O03, af-ui0ua) validates and routes it for both SayMyName rigs; "refuses base=main" but proceeds — FIXED (O06, af-sau1a): escalates through `escalation-door mayor`, `exit 1`s if it fails |
| `lib/factory_build_gates.py` | ops | bin/factory-build-gates | Build-gate wiring check |
| `lib/factory_delivery_proof.py` | ops | factory-delivery-guard, factory-guard, factory-waiting-guard, pr-autopilot, CI | Proof-field rules; comments cite cockpit as label origin (history) |
| `lib/factory_measures.py` | kernel | bin/factory-observe, CI | Measures validation for B09 |
| `lib/factory_observe.py` | kernel | bin/factory-observe, CI | B09 pure logic; docstring cites legacy factory_improvement_axes as precedent |
| `lib/factory_session_boot.py` | ops | factory-guard §7/§7b, CI | Mayor session-down/boot rules |
| `lib/factory_watchdog.py` | ops | factory-watchdog, on-order-failed, on-session-stranded, CI | Watchdog logic; FIXED (O06, af-sau1a): `merge_signals`/`merge-signals` (the signal-file writer) removed |
| `lib/protected_rigs.sh` | to-redo | pr-autopilot, factory-do-work-workspace, mol-do-work (doc) | "Single source of truth" hardcoding SayMyName repos in the Factory; bypassed by deliver-close/delivery-guard/guard |
| `lib/provider_failover.py` | ops | bin/provider-failover, CI | FIXED (P20, af-r48pb): dead `parked` state field removed; generated overlay header points to `bin/provider-failover set`, not the cockpit |
| `lib/delivery_role_identity.py` | kernel | bin/code-review, bin/ticket-author, bin/ticket-evaluation | T15 (af-higj9z): `role_supplier` / `supplier_of`, who supplies a provider (its `pool` in `config/provider-policy.json`) and which suppliers the chain of a role declares. NEW (T14, af-96cusm): the agent, provider and model a delivery role runs on, as configured (`config/delivery-roles.json`, `bin/provider-failover status --json`, `city.toml`, `config/model-catalog.json`); what is recorded on a ticket for its author and its reviewer |
| `lib/reversibility.py` | ops | reversibility-check, pr-autopilot, factory-watchdog, CI | ADR-0019 rules |
| `orders/convoy-parent-sweep.toml` | ops | gc order scheduler | Runs builtin `gc convoy check --json` every 15m |
| `orders/factory-guard.toml` | ops | gc order scheduler | 5m factory-guard --quiet |
| `orders/factory-watchdog.toml` | ops | gc order scheduler | FIXED (P21, af-k91yx): description now lists all 5 live checks (aged gate, stuck PR, false-success close, gh auth, control-quarantine backlog) and cites no campaign-liveness check |
| `orders/model-staleness-check.toml` | ops | gc order scheduler | Daily provider-failover check-models (subcommand exists) |
| `orders/on-order-failed.toml` | ops | gc event order.failed | Event hook |
| `orders/on-session-stranded.toml` | ops | gc event session.stranded | Event hook |
| `orders/pr-autopilot.toml` | ops | gc order scheduler | FIXED (P21, af-k91yx): description no longer claims PRs targeting main are never touched — it says only "never arms a PR targeting any other branch" than each repo's protected branch, which correctly covers the Factory repo's `main` being armed |
| `orders/provider-failover.toml` | ops | gc order scheduler | FIXED (P20, af-r48pb): description describes zero-token failover behavior only, no campaign park/resume wording |
| `pack.toml` | ops | gc | pack imports pinned |
| `packs.lock` | ops | gc; bin/factory-dispatch-guard | pack pins |
| `tests/build-basic-fail-fast-runtime-test.sh` | to-redo | build-basic fail-fast on a real gc/bd city; fixture build-basic-fail-fast | not in ci.yml; declared "# ci: local-only" so ci-registration passes, but nothing runs it automatically |
| `tests/build-basic-fail-fast-test.py` | ops | build-basic formula fail-fast (static) | in CI (ci.yml:152) |
| `tests/build-basic-publish-overlap-followup-test.sh` | ops | build-basic publish follow-up bead on overlapping worktree | in CI (ci.yml:105) |
| `tests/ci-registration-test.sh` | ops | meta: every tests/*.sh\|py named in ci.yml or marked local-only | in CI (ci.yml:236); header cites retired tests (product-queue, saymyname-*) as history only |
| `tests/ci-run-tests-host-lock-test.sh` | ops | bin/ci-run-tests | NEW (af-wnj692): auto-discovered by bin/ci-run-tests; proves the runner gives each test a throwaway `XDG_RUNTIME_DIR` and fails one that still reaches bin/escalation-door's default lock file |
| `tests/coordination-pointer-doors-test.sh` | ops | ADR-0023 rule 6 scan of Mayor prompt, OPERATIONS.md, formulas | in CI (ci.yml:111); header/FIELDS still name legacy bin/product-queue and gc.queue_state |
| `tests/deliver-close-test.sh` | ops | bin/deliver-close (ADR-0026 delivery proof door); fixture deliver-close | in CI (ci.yml:99) |
| `tests/delivery-formula-contract-test.sh` | ops | mol-do-work/mol-scoped-work/mol-polecat-commit wiring to deliver-close/pr-autopilot | in CI (ci.yml:102) |
| `tests/dispatch-door-guard-test.sh` | ops | bin/dispatch-door-guard (O03 raw-sling bypass detection) | in CI (ci.yml, "O03 dispatch-door-guard...") |
| `tests/dispatch-door-test.sh` | ops | bin/dispatch-door (O03 dispatch door: target/formula/--reassign for every rig) | in CI (ci.yml, "O03 dispatch-door validates...") |
| `tests/escalation-door-test.sh` | ops | bin/escalation-door (O06 escalation write door + routing rules); fixture escalation-door | in CI (ci.yml:110); replaces the retired campaign-pointer-test.sh; af-wnj692: also proves a long-lived child left behind by one call (the nudge poller of `gc mail send --notify`) does not inherit the door's lock and cannot block the next call |
| `tests/evidence-capture-demonstration-test.sh` | kernel | evidence-capture, convoy-state, project-launch; real gc/bd in a disposable city, real Chromium | NEW (T09, af-pvcg6t): local-only; the demonstration line on the real tracker and the real browser |
| `tests/evidence-capture-test.py` | kernel | evidence-capture, convoy-state, project-launch; fixtures convoy-state, evidence-capture, delivery-fixture-city | NEW (T09, af-pvcg6t): auto-discovered by bin/ci-run-tests; one test per pass and per refusal, each refusal re-reading the tracker and the store |
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
| `tests/factory-planning-exception-guard-test.sh` | kernel | bin/factory-planning-exception-guard + bin/planning-exception | in CI (ci.yml:206) |
| `tests/factory-provenance-guard-test.sh` | ops | bin/factory-provenance-guard | in CI (ci.yml:218) |
| `tests/factory-session-boot-test.py` | ops | lib/factory_session_boot.py | in CI (ci.yml:131) |
| `tests/factory-setup-test.sh` | ops | bin/factory-setup | NEW (O14, F17); in CI |
| `tests/factory-shared-drain-workspace-test.sh` | ops | bin/factory-shared-drain-workspace; fixture shared-drain | in CI (ci.yml:155) |
| `tests/factory-waiting-guard-test.sh` | ops | bin/factory-waiting-guard (clears gc.waiting_on) | in CI (ci.yml:203); RE-VERDICTED (O14, F12) with the guard it tests — `gc.waiting_on` now serves `pr-autopilot`'s live wake-window check, not the retired idle ladder |
| `tests/factory-watchdog-order-test.sh` | to-redo | orders/factory-watchdog.toml via live gc | not in ci.yml; "# ci: local-only"; hardcodes /home/benja/agent-factory exec path |
| `tests/factory-watchdog-test.py` | ops | lib/factory_watchdog.py | in CI (ci.yml:137); FIXED (P21, af-k91yx): quarantine fixtures now use synthetic rig "acme-backend" and bead ids "acme-q*" |
| `tests/factory-watchdog-test.sh` | ops | bin/factory-watchdog | in CI (ci.yml:140); FIXED (P21, af-k91yx): rig list + repo now use synthetic "acme-backend" / "acme/factory-hq"; the remaining cockpit/campaign mentions are incident history (2026-09-16/af-nf8en), not a claim about current behavior |
| `tests/factory-work-dispatch-test.sh` | ops | bin/factory-work-dispatch | in CI (ci.yml:200) |
| `tests/fixture-city-oracle-test.py` | kernel | Fixture City oracle; fixture fixture-city | in CI (ci.yml:75); legacy-* cases assert retired paths fail closed (correct) |
| `tests/fixtures/build-basic-fail-fast` | to-redo | build-basic-fail-fast-runtime-test.sh only | used only by a local-only test that never runs automatically |
| `tests/fixtures/deliver-close` | ops | deliver-close-test.sh | fake gc/gh for deliver-close |
| `tests/fixtures/evidence-capture` | kernel | evidence-capture-test.py | NEW (T09, af-pvcg6t): fake headless browser that fetches the page it is given and writes a PNG |
| `tests/fixtures/escalation-door` | ops | escalation-door-test.sh | fake gc for the live escalation door |
| `tests/fixtures/fixture-city` | kernel | fixture-city-oracle-test.py | synthetic fixture-* rigs; legacy-*.json are fail-closed probes |
| `tests/fixtures/planning-exception` | kernel | planning-exception-test.py | graph + fake ticket-graph-publish |
| `tests/fixtures/project-isolation` | kernel | project-isolation-oracle-test.py | synthetic project-a/b secrets and scenarios |
| `tests/fixtures/delivery-fixture-city` | kernel | project-launch-test.py; descriptor.json read by project-planning-profile-test.py; prototype/ and spec.md read by prototype-conformance-test.py and spec-approve-test.py | NEW (T01, af-m8m1kc): the Delivery Fixture City's synthetic launchable product -- stdlib-only `app.py` (`/`, `/health`), two named datasets, a descriptor declaring the launch recipe; (T07, af-tvda3w) its frozen Validated Prototype (`prototype/`) and the Spec that names it (`spec.md`); (T10, af-j8jo02) `tests/harness.py`, the per-test test command writing a JUnit XML report, and a real `tests/regression.py` |
| `tests/fixtures/project-planning-profile` | kernel | project-planning-profile-test.py | invalid-saymyname.json is a deliberate negative case (SMN-42 fake key); invalid-launch-missing-field.json (T01, af-m8m1kc) is a deliberate negative case for a partial `launch` block |
| `tests/fixtures/pr-autopilot-projects` | ops | the six `tests/pr-autopilot-*-test.sh` files, via `PROTECTED_RIGS_CONFIG_DIR` | new (P23): synthetic `config/projects/*.toml`-shaped rows (`example-backend`/`example-frontend`) so pr-autopilot tests exercise the real project-registry loading path without asserting on the real SayMyName rig names |
| `tests/fixtures/shared-drain` | ops | factory-shared-drain-workspace-test.sh | fake gc/gh |
| `tests/fixtures/spec-approve` | kernel | spec-approve-test.py | synthetic spec drafts |
| `tests/fixtures/ticket-graph-publish` | kernel | ticket-graph-publish-test.py, ticket-graph-publish-entry-contract-test.py, planning-exception-test.py | fake bd; fake gc (Mayor mail, and the tracker calls of bin/convoy-state on the same store); T05: conformant Fixture City draft, frozen copy of the Cockpit V2 draft (af-i67vl0), golden of a publication before T05; T06: the conformant draft cites the user stories of the Fixture City Spec, the fake bd stores a status and the convoy's `tracks` edge of an added ticket |
| `tests/fixtures/graph-review` | kernel | graph-review-test.py, graph-review-isolated-city-test.sh (draft only) | NEW (T08, af-n575g4): Fixture City draft in which one ticket is not demonstrable alone; fake provider-failover; `reviewer` stands in for the dispatch door and the reviewer session |
| `tests/fixtures/test-review` | kernel | test-review-test.py, ticket-author-test.py, convoy-advance-test.py | NEW (T13, af-nkpjpr): `reviewer` stands in for the dispatch door and the reviewer session (favorable, refusals per test, silent, bead closed without a verdict, door refusing or deferring), one behaviour per launch |
| `tests/fixtures/code-review` | kernel | code-review-test.py, convoy-advance-test.py | NEW (T14, af-96cusm): `reviewer` stands in for the dispatch door and the reviewer sessions (favorable, given findings, « non » to closed questions, unfavorable judgements, silent, bead closed without a verdict, door refusing or deferring), one behaviour per launch; each brief it was handed is kept |
| `tests/fixtures/ticket-evaluation` | kernel | ticket-evaluation-test.py, convoy-advance-test.py | NEW (T15, af-higj9z): `evaluator` stands in for the dispatch door and the Evaluator sessions (observes the launched product through the real bin/evidence-capture, given states, silent, bead closed without states, door refusing or deferring), one behaviour per launch |
| `tests/goal-delivery-pairs-test.sh` | ops | bin/goal-delivery-pairs | in CI (ci.yml:194) |
| `tests/on-order-failed-test.sh` | ops | bin/on-order-failed | in CI (ci.yml:221); comment cites legacy factory-cockpit-chaos-test.py |
| `tests/on-session-stranded-test.sh` | ops | bin/on-session-stranded | in CI (ci.yml:224); comment cites legacy factory-cockpit-chaos-test.py |
| `tests/operator-context-test.sh` | ops | AGENTS.md/Mayor prompt/OPERATOR_BRIDGE free of retired commands | in CI (ci.yml:125); asserts absence of cockpit/product-queue/saymyname (correct) |
| `tests/planning-exception-test.py` | kernel | planning-exception; fixtures planning-exception + ticket-graph-publish | in CI (ci.yml:50) |
| `tests/pr-autopilot-candidate-duplicate-test.sh` | kernel | bin/pr-autopilot | FIXED (P23): drives pr-autopilot with `PROTECTED_RIGS_CONFIG_DIR` pointed at the new `tests/fixtures/pr-autopilot-projects/` synthetic project fixture (rigs `example-backend`/`example-frontend`, repo `example-corp/example-backend`) instead of the real SayMyName rigs; in CI (ci.yml:182) |
| `tests/pr-autopilot-ci-failure-test.sh` | kernel | bin/pr-autopilot | FIXED (P23): same synthetic project fixture as candidate-duplicate; in CI (ci.yml:167) |
| `tests/pr-autopilot-reconcile-cache-test.sh` | kernel | bin/pr-autopilot | FIXED (P23): same synthetic project fixture; asserts `example-corp/example-backend#61` instead of the real repo |
| `tests/pr-autopilot-reversibility-test.sh` | kernel | bin/pr-autopilot + orders/pr-autopilot.toml | FIXED (P23): same synthetic project fixture, plus `GC_OPERATOR_NAME=operator-1` for the test-4 escalation mail; `bin/pr-autopilot`'s ESCALADE message now reads the operator's name from `config/operator.toml` (`GC_OPERATOR_NAME` override, same pattern as `bin/escalation-door`, F23) instead of hardcoding "Benjamin" — declared-scope note: this repair also touched `bin/pr-autopilot` and `lib/protected_rigs.sh` (new `PROTECTED_RIGS_CONFIG_DIR` override, default unchanged) to make the synthetic fixture possible; in CI (ci.yml:161) |
| `tests/pr-autopilot-stale-snapshot-test.sh` | kernel | bin/pr-autopilot | FIXED (P23): same synthetic project fixture; in CI (ci.yml:173) |
| `tests/pr-autopilot-step-wisp-collision-test.sh` | kernel | bin/pr-autopilot | FIXED (P23): same synthetic project fixture; in CI (ci.yml:179) |
| `tests/pr-autopilot-stuck-test.sh` | to-redo | bin/pr-autopilot | in CI (ci.yml:164); asserts saymyname-app/Say-my-name-back |
| `tests/pr-autopilot-transient-retry-test.sh` | to-redo | bin/pr-autopilot | in CI (ci.yml:170); asserts saymyname-app/Say-my-name-back |
| `tests/pre-push-ci-registration-test.sh` | ops | .githooks/pre-push runs ci-registration | in CI (ci.yml:212) |
| `tests/project-isolation-oracle-test.py` | kernel | project isolation oracle; fixture project-isolation | in CI (ci.yml:93) |
| `tests/project-launch-test.py` | kernel | bin/project-launch; fixture delivery-fixture-city | NEW (T01, af-m8m1kc): auto-discovered by bin/ci-run-tests; covers launch-at-named-commit, clean-checkout-not-cwd, named-dataset determinism, two concurrent launches on distinct ports, and refusal with no launch recipe declared |
| `tests/project-planning-profile-test.py` | kernel | project-planning-profile; fixture project-planning-profile | in CI (ci.yml:41); rejects SayMyName-specific fields (correct); FIXED (T01, af-m8m1kc): also covers the optional `launch` block (renders when present, null when absent, rejected when partial) |
| `tests/prototype-conformance-test.py` | kernel | bin/prototype-conformance; fixture delivery-fixture-city | NEW (T07, af-tvda3w): auto-discovered by bin/ci-run-tests; the fixture prototype passes, one refusal per property on an edited copy |
| `tests/provider-failover-test.py` | to-redo | bin/provider-failover | in CI (ci.yml:143); fixtures carry SayMyName backend output + saymyname-backend sessions + inert gc.campaign_* metadata |
| `tests/reversibility-test.py` | ops | reversibility classifier (pr-autopilot) | in CI (ci.yml:158) |
| `tests/spec-approve-test.py` | kernel | spec-approve; fixtures spec-approve, delivery-fixture-city; tests/lib/fixture_prototype.py | in CI (ci.yml:47); FIXED (T07, af-tvda3w): entry-contract refusals and passages against a local bare remote carrying the fixture's prototype branch |
| `tests/spec-integration-demonstration-test.sh` | kernel | spec-integration, convoy-state, evidence-capture; real gc/bd in a disposable city; fixture delivery-fixture-city | NEW (T18, af-gmz9s1): local-only; the demonstration line on the real tracker -- two finished tickets merged one after the other with a test record on each merged result, a commit after a verdict refused |
| `tests/spec-integration-test.py` | kernel | spec-integration, convoy-state, evidence-capture, project-planning-profile; fixtures convoy-state, delivery-fixture-city | NEW (T18, af-gmz9s1): auto-discovered by bin/ci-run-tests; one test per pass and per refusal of `open` and `merge`, each refusal re-reading the tracker, the evidence store and every branch of the remote |
| `tests/tdd-step-test.py` | kernel | tdd-step, convoy-state, evidence-capture, project-launch; fixtures convoy-state, delivery-fixture-city | NEW (T10, af-j8jo02): auto-discovered by bin/ci-run-tests; one test per pass and per refusal of each step, each refusal re-reading the tracker and the evidence store |
| `tests/ticket-exit-test.py` | kernel | ticket-exit, convoy-state, convoy-advance, evidence-capture, escalation-door, ticket-graph-publish; fixtures convoy-state, ticket-graph-publish, delivery-fixture-city | NEW (T11, af-egkabn): auto-discovered by bin/ci-run-tests; one test per pass and per refusal of each Ticket Exit, of the Handoff and of the deferral detector, each refusal re-reading the tracker, the evidence store and the remote |
| `tests/ticket-author-test.py` | kernel | ticket-author, convoy-state, tdd-step, ticket-exit, evidence-capture, project-launch; fixtures convoy-state, delivery-fixture-city | NEW (T12, af-i3q5a5): auto-discovered by bin/ci-run-tests; one test per pass and per refusal of each command and of each gate, each refusal re-reading the tracker and the evidence store |
| `tests/author-subagent-guard-test.py` | kernel | agents/delivery-author/overlay/.claude/guards/author-subagent-guard | NEW (T12, af-i3q5a5): auto-discovered by bin/ci-run-tests; the guard call by call -- read-only sub-agent types pass, any other type, a call with no type and a workflow are blocked |
| `tests/ticket-graph-publish-test.py` | kernel | ticket-graph-publish; fixture ticket-graph-publish | in CI (ci.yml:38) |
| `tests/ticket-graph-publish-entry-contract-test.py` | kernel | ticket-graph-publish, convoy-state; fixture ticket-graph-publish | NEW (T05, af-c8n7ep): auto-discovered by bin/ci-run-tests; one test per refusal and per pass of the new-flow entry contract, each refusal re-reading the tracker |
| `tests/ticket-graph-publish-integration-branch-test.py` | kernel | ticket-graph-publish, spec-integration, convoy-state; harness of ticket-graph-publish-coverage-test.py; fixtures ticket-graph-publish, spec-approve, delivery-fixture-city | NEW (T18, af-gmz9s1): auto-discovered by bin/ci-run-tests; the integration branch opened when a marked convoy is published, none for a convoy without the mark, each refusal re-reading the tracker and the branches |
| `tests/ticket-graph-publish-new-flow-real-tracker-test.sh` | kernel | ticket-graph-publish, convoy-state, planning-exception; real gc/bd in a disposable city | NEW (T05, af-c8n7ep): local-only adoption trial of the same contract on the real tracker; T06 (af-cgauf8): pointers, orphan story, operator need, repair added by patch without approval, withdrawal; T36 (af-2nmcxw): Prototype Fold refusals, reference shown by `gc bd show`, `bd ready` among the interface tickets |
| `tests/ticket-graph-publish-prototype-fold-test.py` | kernel | ticket-graph-publish, convoy-state, spec-approve; harness of ticket-graph-publish-coverage-test.py; fixtures ticket-graph-publish, delivery-fixture-city | NEW (T36, af-2nmcxw): auto-discovered by bin/ci-run-tests; one test per refusal and per pass of the Prototype Fold rules and of the Validated Prototype reference posed in interface tickets, on both doors, each refusal re-reading the tracker |
| `tests/ticket-graph-publish-coverage-test.py` | kernel | ticket-graph-publish, convoy-state, spec-approve, planning-exception; fixtures ticket-graph-publish, delivery-fixture-city | NEW (T06, af-cgauf8): auto-discovered by bin/ci-run-tests; one test per refusal and per pass of coverage, operator needs, launch recipe, pointers and the patch door, each refusal re-reading the tracker |
| `tests/graph-review-test.py` | kernel | graph-review, ticket-graph-publish; fixtures graph-review, ticket-graph-publish | NEW (T08, af-n575g4): auto-discovered by bin/ci-run-tests; one test per pass and per refusal, each refusal re-reading the tracker |
| `tests/graph-review-isolated-city-test.sh` | kernel | graph-review, ticket-graph-publish, dispatch-door; real gc/bd in a disposable city | NEW (T08, af-n575g4): local-only adoption trial on the real tracker; with `GRAPH_REVIEW_TRIAL_SESSION=1`, one real reviewer session |
| `tests/ticket-author-isolated-city-test.sh` | kernel | mol-ticket-author, ticket-author, convoy-advance, dispatch-door, factory-build-gates, tdd-step, ticket-exit; real gc/bd in a disposable city | NEW (T12, af-i3q5a5): local-only adoption trial of the author formula on a real controller, started by the city's own order, with a scripted author: one ticket walks the sequence to « terminé », one skips the red and is stopped by the check, one leaves by Planning Exception and is parked |
| `tests/test-review-test.py` | kernel | test-review, tdd-step, convoy-state, evidence-capture, escalation-door, project-launch; fixtures convoy-state, test-review, delivery-fixture-city | NEW (T13, af-nkpjpr): auto-discovered by bin/ci-run-tests; one test per pass and per refusal of `review`, `settle`, `brief` and `record`, each refusal re-reading the tracker; the stop read back from the escalation door's list |
| `tests/test-review-isolated-city-test.sh` | kernel | mol-test-review, mol-ticket-author, test-review, convoy-advance, dispatch-door, tdd-step, escalation-door; real gc/bd in a disposable city | NEW (T13, af-nkpjpr): local-only adoption trial on a real controller, with the real dispatch door and a scripted author and reviewer: a status-only test refused then corrected and frozen, a second refusal that stops the ticket, a review without result relaunched once then stopped; each stopped ticket once on the operator's list |
| `tests/code-review-test.py` | kernel | code-review, convoy-state, spec-integration, escalation-door, evidence-capture; fixtures convoy-state, code-review, delivery-fixture-city | NEW (T14, af-96cusm): auto-discovered by bin/ci-run-tests; one test per pass and per refusal of `settle`, `brief`, `record`, `respond` and `show`, each refusal re-reading the tracker; the merge control is the real `bin/spec-integration`, the stop is read back from the escalation door's list |
| `tests/code-review-isolated-city-test.sh` | kernel | mol-code-review, code-review, convoy-advance, dispatch-door, spec-integration, escalation-door; real gc/bd in a disposable city | NEW (T14, af-96cusm): local-only adoption trial on a real controller, with the real order, the real dispatch door and merge command, and a scripted reviewer: a diff that contradicts the Spec gets a cited Blocking Finding and is not merged, then is fixed, judged by a second session and merged; a finding of taste is recorded without blocking; a review without output is relaunched once, then the ticket is stopped and never merged |
| `tests/ticket-evaluation-test.py` | kernel | ticket-evaluation, convoy-state, project-launch, evidence-capture, spec-integration, escalation-door; fixtures convoy-state, ticket-evaluation, delivery-fixture-city | NEW (T15, af-higj9z): auto-discovered by bin/ci-run-tests; one test per pass and per refusal of `settle`, `brief`, `record`, `verdict` and `show`, each refusal re-reading the tracker; the product is really launched and observed |
| `tests/ticket-evaluation-isolated-city-test.sh` | kernel | mol-ticket-evaluation, ticket-evaluation, convoy-advance, dispatch-door, project-launch, evidence-capture, spec-integration, delivery-role-sandbox; real gc/bd in a disposable city | NEW (T15, af-higj9z): local-only adoption trial on a real controller, with the real order, dispatch door, launcher and merge command, and a scripted Evaluator inside the real read-only sandbox: an unrealized criterion is « non observé » and not merged, the corrected ticket is observed and merged, a prefactoring is checked without a session |

## O16 closeout — orders, Mayor manual operations, 24 h clean (added 2026-09-29, af-dqhwo)

A4/A5 findings above are a frozen 2026-09-27 snapshot; this section is a
dated addendum that closes out the last O16 acceptance criteria without
rewriting the snapshot. It does not re-verdict any file already covered
above.

### The 28 live orders (`gc order list`, checked 2026-09-28)

Four pack orders are skipped in `city.toml` (`dolt-remotes-patrol`,
`nudge-mail-sweep`, `prune-branches`, `cross-rig-deps`, see the `[orders]
skip` comment there for why) and so do not appear in the live list or here.

| Order | Verdict | Note |
|---|---|---|
| `dolt-health` | ops | pack order; interval tuned to 2m (O13) |
| `beads-health` | ops | pack order; interval tuned to 2m (O13) |
| `mol-dog-backup` | ops | pack order; kept on its own clock (O13 review) |
| `mol-dog-compactor` | ops | pack order; kept (O13 review; duplicates Dolt auto-GC but harmless) |
| `mol-dog-doctor` | ops | pack order; kept |
| `mol-dog-phantom-db` | ops | pack order; kept |
| `mol-dog-stale-db` | ops | pack order; kept |
| `cascade-nudge-on-blocker-close` | ops | pack order; event-driven, kept |
| `gate-sweep` | ops | pack order; retriggered on `condition` (open gates > 0) instead of a 30s poll (O13) |
| `jsonl-export` | ops | pack order; off-box backup export, kept |
| `nudge-on-route` | ops | pack order; event-driven, kept |
| `order-tracking-sweep` | ops | pack order; interval tuned to 10m (O13) |
| `orphan-sweep` | ops | pack order; kept |
| `reaper` | ops | pack order; kept |
| `spawn-storm-detect` | ops | pack order; kept |
| `wisp-compact` | ops | pack order; kept |
| `orders/backup-freshness.toml` | ops | new (O13, F24 FIXED): pages the Mayor when the archive repo hasn't been pushed in 24h |
| `orders/convoy-parent-sweep.toml` | ops | unchanged, see "Every file" above |
| `orders/escalation-door-sweep.toml` | ops | new (O06, af-sau1a): sweeps unresolved Mayor-first escalations to Benjamin after 2h |
| `orders/factory-guard.toml` | ops | unchanged, see "Every file" above |
| `orders/factory-watchdog.toml` | ops | FIXED (P21, af-k91yx), see "Every file" above |
| `orders/idle-ready-work-wake.toml` | ops | new (O02, af-mbpt1): re-wakes the Mayor when ready work sits idle |
| `orders/local-only-tests.toml` | ops | new (O13, F21 PARTIALLY FIXED): runs the local-only battery nightly, pages on failure |
| `orders/model-staleness-check.toml` | ops | unchanged, see "Every file" above |
| `orders/on-order-failed.toml` | ops | unchanged, see "Every file" above |
| `orders/on-session-stranded.toml` | ops | unchanged, see "Every file" above |
| `orders/pr-autopilot.toml` | ops | FIXED (P21, af-k91yx), see "Every file" above |
| `orders/provider-failover.toml` | ops | FIXED (P20, af-r48pb): description text drift resolved, see `docs/INVENTORY.md` row above |

Count: 28 verdicts (28 `ops`, 0 `to-redo` carried from F06 — both wording
fixes now landed).

### Mayor manual operations (`bin/factory-maintain`, ADR-0016 §7 standing allowlist)

| Gesture | Verdict | Note |
|---|---|---|
| `restart-service` | ops | O12 (af-1lofk): wraps `gc service restart <name>`, refuses an unknown service name |
| `prune-merged-branches` | ops | O12: refuses anything unmerged, unpushed, current, or a rig's protected branch |
| `clean-worktrees` | ops | O12: refuses anything with unmerged or unpushed work |
| `rotate-logs` | ops | O12: gzip-archives over a size threshold, never deletes a log outright |
| `reload-city-config` | ops | O12: wraps `gc reload`, logged like every other gesture |

All five gestures log to `var/factory-maintain.log`, checked in
`tests/factory-maintain-test.sh` (CI, ci.yml). No manual upkeep gesture
outside this named-script set is in scope per AGENTS.md's standing ADMIN
allowlist.

### 24 h clean (`gc events --type order.failed`)

The last merge among this graph's 17 tickets (O01-O17) landed at
**2026-09-28T21:32:51Z** (O14, af-8l3ea, PR merge). As of this ticket's own
work (2026-09-28T22:42Z, about 1h10m later), `gc events --type order.failed
--since 24h` shows:

- 14 `order.failed` events between 2026-09-28T12:09Z and 2026-09-28T15:51Z
  UTC (subjects `factory-guard`, `pr-autopilot`, `escalation-door-sweep`),
  all landing *before* O14's merge, during the graph's own active
  dispatch/merge window.
- **Zero** `order.failed` events since 2026-09-28T15:51:45Z UTC — i.e. zero
  in the ~7h that includes the last merge and everything after it, as
  observed at close time.

The full 24h-after-last-merge window (to 2026-09-29T21:32:51Z) had not yet
elapsed when this ticket closed. `orders/on-order-failed.toml` (ops, pages
the Mayor on every `order.failed`) and `orders/escalation-door-sweep.toml`
(ops) continue to enforce this after close: an escalation fires
immediately if the window is not in fact clean, rather than requiring a
worker session to sit and wait. No `gc.needs_benjamin` page fired for an
order failure in this window as of close.
