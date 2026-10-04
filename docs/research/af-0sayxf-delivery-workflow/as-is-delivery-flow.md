# AS-IS delivery flow — Agent Factory (read 2026-10-01, HEAD `112c286`)

Paths are relative to `/home/benja/agent-factory` unless absolute. Read-only: only cat/grep/git/`bd show|list|comments`/`gh pr view`/`gh api` GET were run. Times are Paris.

## 1. Pipeline, step by step

| Step | Actor | Model | Mechanism (evidence) |
|---|---|---|---|
| Publish | `bin/ticket-graph-publish bd-publish` (deterministic) | none | Refuses unless draft approver/digest and Spec `APPROVED_SPEC`+digest match (`:799-845`), refuses `kind: prototype` (`:143-164`), adds serialisation edges for overlapping `scope.paths` (`:183-225`), creates convoy + one delivery bead per ticket in one `bd create --graph` (`:457-468`), mails the Mayor (`:671-720`). |
| Dispatch | Mayor (always-on named session, `pack.toml:16-18`) | `claude-standard` = `sonnet-5`, effort medium (`city.provider.toml:9-11`, `city.toml:44-57`) | Prompt: dispatch ready beads of the convoy in dependency order up to pool cap (`agents/mayor/prompt.template.md:49-57`) via `bin/factory-work-dispatch` -> `bin/dispatch-door`. For the HQ rig the formula is hard-pinned to `mol-do-work` (`bin/factory-work-dispatch:16,60-61`; `config/projects/agent-factory.toml:24-25`). Safety net: `bin/idle-ready-work-wake`. |
| Worker session | `factory-worker`, pool max 2 (`agents/factory-worker/agent.toml`) | inherits workspace provider. C01 window: 34 worker sessions, all `claude-standard / claude-sonnet-5 / --effort medium` (bd session beads; e.g. `af-76g2da` command line). `docs/DELIVERY.md:7,11-13` still says Codex/Sol is the writer: stale vs live. | `formulas/mol-do-work.formula.toml`: 4 steps `workspace-setup` (claim, worktree `do-work/<bead>`), `do-work`, `push-and-pr`, `drain`. |
| Commit/PR | same worker | — | `bin/factory-do-work-workspace finish` opens the PR; bead stays `in_progress` with `gc.delivery_status=waiting` (`mol-do-work:379-387`). Observed PR title `do-work: af-9tfjsc`, body `Closes af-9tfjsc.` (17 chars) on #380, #373, #359, #363. |
| Review | nobody | — | `mol-do-work` has no review step. `gh pr view` on #380/#373/#359/#363: `reviews: []`, `reviewDecision: ""`. |
| CI | GitHub Actions `Factory CI`, job `Tests` | none | `.github/workflows/ci.yml`: `compileall`, `bash -n`, then `bin/ci-run-tests` (every `tests/*.py|*.sh` not marked local-only). |
| Merge | GitHub auto-merge armed by `bin/pr-autopilot` (order, 3 min) | none | `--auto --squash --delete-branch` on green required check (`docs/DELIVERY.md:157-162`); red after one retry reopens the ticket (`mol-do-work:75-89`). |
| Ticket close | `bin/deliver-close`, called by pr-autopilot | none | ADR-0026 proof, then atomic close (see §5). |
| Convoy close | order `convoy-parent-sweep` (`gc convoy check` on `bead.closed`) | none | C01 convoy `af-f71cgu`: `close_reason = "convoy autoclose: all children closed"`. Then `bin/planning-artifacts-close` closes Spec + Draft beads (`orders/planning-artifacts-close.toml`). |

C01 actuals: published 2026-09-30 17:55, convoy closed 2026-10-01 04:42; 25 tickets, 24 `shipped` each with its own PR to `main` (#348-#380), T21 (prototype) closed with `gc.work_outcome=blocked`.

## 2. What a worker receives

The bead description, rendered by `ticket_description()` (`bin/ticket-graph-publish:254-263`):

```
## What to build\n\n{what_it_delivers}
## Acceptance criteria\n\n- [ ] ...
## Target rigs\n\n{rigs}
## Autonomous execution contract\n\n- {key}: {value}   (the draft's global_execution_contract, copied verbatim into every ticket)
```

Plus metadata (`gc.spec_id`, `gc.ticket_id`, `gc.ticket_kind`, `gc.blocked_by`, `gc.scope_paths`, `:386-403`). Nothing else is injected:

- Spec: by reference only — the C01 contract's `context` line says to run `bd show af-oohx2x` (50,821 chars).
- Prototype: by branch name in prose only (`prototype/c01-home-screen`, folder `prototypes/c01-home-screen/`, 2 files). That folder is not on `main` (`ls prototypes` fails), so the worker must fetch another branch on its own initiative. For T22 the chosen variants were a `bd comments` entry pointing at `prototype/c01-project-page` — `mol-do-work` runs `gc bd show`, never `bd comments`.
- Sibling tickets / whole graph: not provided (only blocker ids in metadata).
- No design reference, token file or screenshot attached to the bead.

## 3. What the worker is told to do

Worker prompt `agents/factory-worker/prompt.template.md` is the generic pack "GC Role Worker" text: claim protocol and close metadata only; it even forbids loading skills or reading the repo before the claim (`:23-25`). The whole implementation instruction is `mol-do-work:207-212`:

> "Do exactly what the bead describes. Follow existing codebase conventions. Run the verification commands requested by the bead. If the bead does not name verification commands, run the smallest relevant local test/build check you can identify."

| Topic | In prompt/formula? |
|---|---|
| TDD red/green | No. Only in the per-graph contract prose (`test_method: "Petits cycles rouge puis vert sur une interface publique…"`). `grep -iE 'tdd|red[- ]green|test-first|failing test'` over live repo (excl. planning/research/legacy): 0 hits in formulas, prompts, bin. |
| Test type | Contract prose only (cockpit process on simulated sources). |
| Vertical slice | Ticket shape only (`gc.ticket_kind`, default `vertical_slice`). |
| Run the app / look at the UI | No. `visual_check` asks for PC+iPhone light/dark screenshots attached to the PR; none exist: PR bodies contain no image, `git ls-files` has zero png/jpg/webp, PR #380 touched 7 files (py + fixtures). |
| Self-review | No (`mol-scoped-work` and `mol-polecat-commit` have a `self-review` step, but HQ allows only `mol-do-work`). |
| Design/prototype fidelity | Contract prose only, delegated to a "relecteur indépendant" that does not exist. |
| Security | Contract `safety` line + `AGENTS.md` invariants. |
| Architecture conventions | "Follow existing codebase conventions"; `CLAUDE.md` = `@AGENTS.md`. |
| Escalation | Yes, precise: `deliver-close --outcome blocked --classification repair|semantic|topology`, `planning-exception raise`, `escalation-door benjamin` (`mol-do-work:278-322`). |

## 4. Review

- No independent reviewer runs on this path. `claude-reviewer` was retired 2026-09-28 because "no formula or prompt ever dispatched it" (`docs/DELIVERY.md:18-23`, `city.toml:273-276`). The Mayor routing table gives STANDARD work "none — CI is the gate" (`agents/mayor/prompt.template.md:198-202`).
- The only review pipeline, `build-basic` (plan-review + acceptance / test-evidence / simplicity reviewers + synthesizer, `formulas/build-basic-review-scoped.formula.toml`), is not allowed on the HQ rig (`config/projects/agent-factory.toml:25`; Mayor prompt `:209-214`).
- `ux-reviewer` exists on demand (`agents/ux-reviewer/prompt.template.md`); 0 sessions in the C01 window (only `factory-worker` x34 and `bd.dog` x3).
- Yet every C01 ticket carried `review: "Un relecteur indépendant vérifie pour chaque tranche la fidélité à la Spec et la qualité de conception."` and `readiness: "…une fois ses vérifications et sa revue passées…"`. Nothing enforces either sentence.
- Nothing compares the result with the Spec or the prototypes. The Spec lists "Validation visuelle des captures PC + iPhone de chaque ticket UI contre la variante D" as a Benjamin hand step; the draft then recorded his words (« les vérifications visuelles ne sont présentes que pendant la plannification… ») and moved it to "7 jours d'usage réel" after delivery (draft bead `af-i67vl0`, `decisions`/`out_of_graph`).

## 5. Gates between "ticket merged" and "convoy done"

None beyond per-ticket CI. `deliver-close` (ADR-0026 §3-4) verifies only: PR merged in the exact repo; recorded URL/branch/base match GitHub; the required workflow has a successful `pull_request` run whose `head_sha` equals the PR head. `grep -iE 'acceptance|review|spec|criteria|screenshot' bin/deliver-close lib/factory_delivery_proof.py`: 0 hits. Acceptance-criteria checkboxes are never read or ticked. The convoy closes by child count alone. `Accepted Outcome` is a glossary term (`CONTEXT.md`) and a Cockpit button (Spec story 30), not a gate.

## 6. Divergence from upstream (pin `c55ee46`, `docs/UPSTREAM_SKILLS.md:11`)

Upstream at the pin (`gh api …/skills/engineering?ref=c55ee46`): ask-matt, code-review, codebase-design, diagnosing-bugs, domain-modeling, grill-with-docs, implement, improve-codebase-architecture, prototype, research, resolving-merge-conflicts, setup-matt-pocock-skills, tdd, to-spec, to-tickets, triage, wayfinder, wizard. Upstream `/implement` in full: use /tdd at pre-agreed seams; typecheck and single test files regularly, full suite once at the end; "Once done, use /code-review"; commit.

- Vendored only on Windows, operator layer: `C:\Users\benja\.claude\skills` and `C:\Users\benja\.agents\skills`. `README-mattpocock-skills.md:94-96`: "Rien n'a été poussé côté Factory (WSL …)".
- Not installed anywhere: `implement`, `code-review` (README `:27-29`: name collision with the built-in), `triage`.
- In WSL: `~/.claude/skills` and `~/.agents` do not exist; `find / -type d -name tdd|to-tickets|to-spec` returns nothing. The worker's skill dir (`.gc/agents/factory-worker/.claude/skills`) holds only `core.gc-*` and `gascity.mayor`. A delivery worker loads zero Pocock skills.
- Used as written (planning only): `/wayfinder`, `/to-spec`, `/to-tickets` (`docs/PLANNING_RUN.md:5-10`).
- `docs/ADAPTATION_REGISTER.md` has AR-001..AR-007: planning allocation, isolation, Planning Exception, observation, three retirements. No entry covers implementation, TDD or review, although the refactor Spec says the "combined independent ticket reviewer" and "whole-outcome assembled-diff review" entries "must be created" (`docs/planning/agent-factory-project-agnostic-refactor-spec.md:49,52,208,224-226`; grilling checkpoint Q47, Q48, Q51).
- `docs/research/2026-09-23-agentic-tdd-review-workflow.md` is listed "none (unreferenced)… orphan" in `docs/INVENTORY.md:178`.
- Upstream `/to-tickets` foresees a final "integrate-and-verify ticket" only for wide refactors sharing an integration branch; C01 had no such ticket and each ticket merged straight to `main`.

## 7. Not present (searched, found nothing)

Greps over the live repo excluding `.git`, `.gc`, `.beads`, `legacy`, `rigs`, `docs/planning`, `docs/research`, `tests`, `lib/cockpit`:

- `integration ticket|integrate-and-verify|integration branch`: 0 hits. No assembly step, no assembled-diff review.
- `playwright`: 0; `visual regression|pixel`: only a superseded SayMyName `.before-delegation` file. No screenshot tooling.
- `design system|design tokens`: only that file and the ux-reviewer prompt. No design-system reference for the Factory.
- `architecture review`, `security review`: 0.
- `code-review|code review`: one incidental line (`assets/workflows/build-basic/publish.md:48`).
- Lint/typecheck: only optional `lint_command` vars in formulas HQ cannot use; CI runs none.
- End-to-end test of the assembled product: none (`e2e` hits are Pushover keys / fixture oracle).
- Human acceptance or demo gate before convoy close: none.
- Any check of acceptance criteria at close: none.

## Not verified

- Worker transcripts were not read: whether workers actually did red/green or opened the prototype branch is unknown.
- PR reviews checked on 4 of 24 PRs; screenshots absence checked via PR bodies (4) and `git ls-files` (all).
- Mayor session's actual model during C01 taken from config, not from its session bead.
- Whether `ticket_description` output is all the worker sees assumes the worker followed `mol-do-work` literally.
