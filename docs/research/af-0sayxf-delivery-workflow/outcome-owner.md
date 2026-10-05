# Who owns the whole outcome during delivery, and who re-plans

Research date: 2026-10-05 (Paris). Facts only; no recommendation.

Question: while an approved Spec is being delivered as a ticket graph by fresh-context workers, who owns the whole result and re-plans: nobody (deterministic walk + end judgment), a per-Spec owner agent, or the general orchestrator ("Mayor")?

## Method and confidence labels

- **[V]** VERIFIED-from-source: I read the primary text verbatim in this pass (fresh `git clone` at HEAD, or the original page downloaded and stripped to text locally; no summarising model in between).
- **[P]** carried over from the two prior reports (`r-software-factories-practices.md`, `r-pocock-delivery-skills.md`); not re-read in this pass.
- **[S]** SECONDARY: search-result summary or third-party account only.

Quotes are short; everything else is paraphrase. Nothing was posted anywhere; clones live in the scratchpad only.

Vocabulary used below:
- **Owner** = the role that is accountable for "the Spec as a whole works", as opposed to "my ticket is done".
- **Powers**: *judge* (read-only verdict) / *add work* (create repair tickets) / *change plan* (re-order, split, re-scope, drop) / *change spec* (alter what "done" means).
- **Handoff contract** = what a worker must report back, and whether its shape is enforced.

---

## 1. Sources

| # | Source | Version / date | Label |
|---|---|---|---|
| 1 | `mattpocock/skills` `main` | HEAD `f6abdeb`, 2026-10-05 11:15 (Paris); `package.json` 1.3.1 | [V] clone |
| 2 | `mattpocock/sandcastle` `main` | HEAD `62307ab`, 2026-10-02 21:25 (Paris) | [V] clone |
| 3 | Pocock AI Coding Dictionary: [AFK](https://www.aihero.dev/ai-coding-dictionary/afk), [human-in-the-loop](https://www.aihero.dev/ai-coding-dictionary/human-in-the-loop), [subagent](https://www.aihero.dev/ai-coding-dictionary/subagent), [context pointer](https://www.aihero.dev/ai-coding-dictionary/context-pointer), [software factory](https://www.aihero.dev/ai-coding-dictionary/software-factory), [dark factory](https://www.aihero.dev/ai-coding-dictionary/dark-factory) | undated pages, fetched today | [V] |
| 4 | Pocock talk "Full Walkthrough: Workflow for AI Coding" (AI Engineer Europe 2026) | transcript | [P] |
| 5 | Cursor, ["Scaling long-running autonomous coding"](https://cursor.com/blog/scaling-agents) | 2026-01-14 | [V] |
| 6 | Cursor, ["Towards self-driving codebases"](https://cursor.com/blog/self-driving-codebases) | 2026-02-05 | [V] |
| 7 | Factory, ["Introducing Missions"](https://factory.ai/news/missions) | 2026-02-26 | [V] |
| 8 | Factory, ["How Missions Work"](https://factory.ai/news/missions-architecture) (Theo Luan) | 2026-04-10 | [V] |
| 9 | Factory docs: [Missions overview](https://docs.factory.ai/cli/features/missions), [Planning & Validation](https://docs.factory.ai/missions/planning), [Running in the CLI](https://docs.factory.ai/missions/running-cli) | living, fetched today | [V] |
| 10 | Anthropic, ["Harness design for long-running application development"](https://www.anthropic.com/engineering/harness-design-long-running-apps) | 2026-03-24 | [V] |
| 11 | Anthropic, ["Effective harnesses for long-running agents"](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | 2025-11-26 | [V] |
| 12 | Anthropic, ["Building effective agents"](https://www.anthropic.com/engineering/building-effective-agents) | 2024-12 | [V] |
| 13 | Anthropic, ["How we built our multi-agent research system"](https://www.anthropic.com/engineering/multi-agent-research-system) | 2025-06 | [V] |
| 14 | Claude Code docs, [Agent teams](https://code.claude.com/docs/en/agent-teams) | living, fetched today | [V] |
| 15 | OpenAI Symphony [`SPEC.md`](https://github.com/openai/symphony/blob/main/SPEC.md) and reference [`elixir/WORKFLOW.md`](https://github.com/openai/symphony/blob/main/elixir/WORKFLOW.md), README | HEAD `be10a1b`, 2026-09-16 00:12 (Paris) | [V] clone |
| 16 | OpenAI, ["Harness engineering"](https://openai.com/index/harness-engineering/) | 2026-02 | [V] |
| 17 | OpenAI Cookbook, ["Using PLANS.md for multi-hour problem solving"](https://developers.openai.com/cookbook/articles/codex_exec_plans) | 2025 | [V] |
| 18 | Cognition, ["Multi-agents: what's actually working"](https://cognition.com/blog/multi-agents-working) | 2026-04-22 | [V] |
| 19 | `steveyegge/gastown`: `internal/templates/roles/mayor.md.tmpl`, `docs/design/escalation.md`, `docs/design/convoy/mountain-eater.md`, `docs/concepts/convoy.md`, `docs/CLEANUP.md` | HEAD `649b832`, 2026-07-23 15:03 (Paris) | [V] clone |
| 20 | `gastownhall/gascity`: `docs/reference/cli.md` (convoy), `cmd/gc/prompts/mayor.md`, `AGENTS.md`, `docs/getting-started/*`, `docs/reference/specs/formula-spec-v2.md` | HEAD `aa8afe8`, 2026-10-05 12:38 (Paris) | [V] clone |
| 21 | HumanLayer 12-factor agents, [factor 7](https://github.com/humanlayer/12-factor-agents/blob/main/content/factor-07-contact-humans-with-tools.md) | 2025 | [V] |
| 22 | Spotify, ["Feedback loops: background coding agents part 3"](https://engineering.atspotify.com/2025/12/feedback-loops-background-coding-agents-part-3) | 2025-12-09 | [V] |
| 23 | GitHub Spec Kit [`templates/commands/implement.md`](https://github.com/github/spec-kit/blob/main/templates/commands/implement.md), `analyze.md` | `main`, fetched today | [V] |
| 24 | Kiro docs, [Specs](https://kiro.dev/docs/specs/), best practices | page updated 2026-10-02 | [V] |
| 25 | Stripe Minions parts 1-2; StrongDM Software Factory | 2026-02 | [P] (today's re-fetch returned script-rendered shells) |
| 26 | arXiv 2606.15874 "LLM-as-Code"; arXiv 2508.02721 "Blueprint First, Model Second"; Bernstein ADR 006 "no embedded LLM" | 2025-2026 | [S] search summary only |

---

## 2. Matt Pocock, precisely

### 2.1 What changed since the prior read [V]
`skills` moved from `d81f3a1` (1.2.3) to `f6abdeb` (1.3.1). `implement-spec/SKILL.md` is textually the same nine steps. The docs page sentence comparing with Sandcastle now reads that a deterministic loop is "faster, cheaper, and more reliable, because no agent makes the orchestration decisions" (previously: no part "can wander off"). Sandcastle moved from `e99f832` to `62307ab`; the four templates keep the same shape.

### 2.2 `implement-spec`: what the orchestrator does [V] (`skills/engineering/implement-spec/SKILL.md`)
- It is one harness session typed by a human (`disable-model-invocation: true`; Codex side `allow_implicit_invocation: false`).
- Reads spec + tickets as a task graph with a frontier; optional exploration subagent writing notes outside the repo; creates the integration branch; spawns implementer subagents (own worktree, `tdd`, merge integration tip before reporting done); one merger subagent per finished ticket; recomputes the frontier; at the end runs `code-review` once on the integration branch and sends all findings to one fix implementer; resolves the tickets; cleans worktrees.
- Stated goal: the whole spec on one integration branch "with every ticket resolved".

### 2.3 What it does NOT do [V: absence checked by grep over `implement`, `implement-spec`, `tdd`, `code-review`, `to-tickets`, `retro`]
- No instruction to read, judge or act on an implementer's report. The only return channel defined is "reporting done".
- No report format. The single sentence on communication: it "should be sparse", primarily through "context pointers: to the spec, tickets, research notes, and previous commits". So the orchestrator's view of a ticket is pointers (commits, the ticket), not a structured handoff.
- No power to create, split, re-order or re-scope tickets mid-run. The only graph operation is recomputing the frontier. (The docs tell the *human* to add a blocking edge when two frontier tickets collide.)
- No rule for an implementer that reports incomplete or out-of-scope work. Zero occurrences of "escalat", "follow-up", "incomplete" in these skills. Open user issue #723 ("safe incomplete-run handoff") had no maintainer reply [P].
- "Done" = all tickets complete, then one diff-reading review, then one fix pass. No run-the-app step, no acceptance step, no stop condition after the fix (docs: it "doesn't yet say when to stop").
- Dictionary "subagent" [V]: a subagent "reports a single tool result back"; that report is "a secondary source", so what it omits "is invisible to the parent". This is his own description of the dropped-flag mechanism.

### 2.4 Who decides the Spec is done; what stays human [V unless marked]
- Docs page: the run's output is "a draft that the review completes, not something to ship".
- Docs page: with `implement-spec` "you review the integration branch at the end".
- Dictionary AFK: "AFK doesn't remove human review; it defers all of it to the end"; the run must end in something reviewable, "a PR, not changes already merged".
- Dictionary HITL: agents "tend to push forward rather than stop and ask".
- Talk [P]: implementation is "the only AFK bit"; human QA follows and "is how I impose my taste"; QA "is for creating more issues for that Kanban board", including while implementation is still running.
- Human-only by design: `to-tickets` ("Iterate until the user approves the breakdown"), `triage` states `ready-for-agent` / `ready-for-human`, `retro` (proposes only), every orchestrating skill.
- Re-planning exists only upstream of delivery: `wayfinder` maintains a map with fog, adds newly surfaced tickets and closes out-of-scope ones as decisions resolve. It is a planning-stage, human-in-the-loop artefact, not a delivery-stage owner.

### 2.5 Sandcastle templates [V] (`src/templates/*`)
- `parallel-planner(-with-review)`: outer loop is TypeScript (`for` up to `MAX_ITERATIONS = 10`). The **planner** is an LLM with exactly one job and one iteration: read the already-filtered open issues, infer blocking (including "overlapping files or modules"), emit `<plan>{issues:[{id,title,branch}]}</plan>` validated by a Zod schema. It cannot create or edit issues; it only selects. Malformed output aborts the loop.
- Implementer (up to 100 iterations): commit message must carry "Key decisions made" and "Blockers or notes for next iteration"; "If the task is not complete, leave a comment on the issue"; "Do not close the issue".
- The code decides "complete" from one signal: the branch has commits (`commits.length > 0`). Rejected pipelines are logged to console and skipped (`Promise.allSettled`).
- The **merger** agent merges, runs typecheck + tests, and closes the issue of every merged branch. Nothing reads the implementer's issue comment or its `<promise>COMPLETE</promise>` before closing: an implementer that committed partial work and commented "not complete" still gets its issue closed by the merger prompt as written.
- `sequential-reviewer`: one agent picks one issue per iteration by a fixed priority order, closes it itself; "If you are blocked ... leave a comment on the issue and move on".
- No template has an end-of-run evaluator, an acceptance step, a human notification, or any agent holding the whole Spec.

### 2.6 Net position [V for each element, synthesis mine]
Pocock ships both poles and no middle: (a) an LLM orchestrator session that dispatches and merges but neither judges handoffs nor re-plans, and (b) a deterministic loop whose only LLM "planner" is a stateless frontier selector. In both, the owner of the whole outcome is the human at the end (review + manual QA), and repair work enters as new tickets written by the human after QA.

---

## 3. Other systems

### 3.1 Cursor [V] (sources 5, 6)
Evolution, in order, each step motivated by an observed failure:
1. Flat peers with locks or optimistic concurrency: no agent took "responsibility for the project as a whole"; small safe changes only.
2. Planner → **executor** ("sole lead agent responsible" for completing the plan) → workers, plus an **independent judge** after the executor to decide completion / another iteration. Worked, but "bottlenecked by the slowest worker"; too rigid.
3. **Continuous executor** (plans and spawns; judge removed "to keep the system simple"). It then misbehaved: it would "sleep randomly", stop running agents, do the work itself, refuse to plan, not merge worker changes, and "claim premature completion". Their diagnosis: "too many roles and objectives simultaneously" (plan, explore, spawn, check workers, review, edit, merge, judge).
4. Final: **root planner** "owns the entire scope of the user's instructions", "does no coding itself", and is not aware of who picks up its tasks. **Sub-planners** "fully own the delegated narrow slice" (recursive). **Workers** are "unaware of the larger system", talk to nobody, and on completion write "a single handoff that the system submits to the planner that requested the task".
- Handoff content: "not just what was done, but important notes, concerns, deviations, findings, thoughts, and feedback". Free text; delivered as a follow-up message to the requesting planner, which then pulls the latest repo and keeps planning. Information propagates "up the chain to owners with increasingly global views".
- Owner type: LLM. Powers: create tasks, re-plan continuously; no coding. Cadence: on every worker handoff (event-driven); the Jan post lists as still missing that planners "should wake up when their tasks complete".
- Integrator (central quality gate) removed as "an obvious bottleneck" at hundreds of workers.
- Drift remedies: scratchpad "frequently rewritten versus being appended to", self-reflection and alignment reminders, "periodic fresh starts to combat drift and tunnel vision".
- Spec: agents "follow instructions to the end, good or bad"; a wrong initial architecture "was a failure of the initial specification"; humans altered the instructions between runs. No agent may change the spec.
- Escalation to human: none described; "taste, judgement, and direction came from humans" between runs.
- Scale caveat: hundreds to thousands of agents, week-long runs. External criticism of the resulting browser [P, S].

### 3.2 Factory.ai Missions [V] (sources 7, 8, 9)
This is a hybrid, and the most explicit published division of labour:
- **Orchestrator (LLM)**: with the user, clarifies requirements; writes the **validation contract first** ("a finite checklist of testable behavioral assertions"), before features, so that the contract is not shaped by the implementation plan; then decomposes into features, each of which "claims which assertions it will fulfill"; groups features into milestones; writes shared state (`validation-contract.md`, `features.json`, `services.yaml`, `AGENTS.md`). It "avoids accumulating overly granular context" and "doesn't drive validation directly".
- **Programmatic runner (code)**: "takes the feature list and spawns a worker for each feature in order"; when a milestone's features are complete, "the runner triggers validation using fresh agents".
- **Workers (LLM, fresh context)**: tests first, iterate, hand off; "the final judgment on correctness is not their call".
- **Validators (LLM, fresh)**: scrutiny validators review each worker's implementation *and trajectory*; user-testing validators exercise the app as a black box against the contract. They "don't implement fixes"; they surface issues to the orchestrator.
- **Re-entry of the owner**: after validation "the orchestrator reviews what workers and validators flagged" and "creates fix features targeted at actionable gaps"; the milestone re-validates; loop until it passes.
- **Escalation**: if implementation or validation is blocked, the orchestrator "halts the mission and hands control back to the user". Docs: "Missions are not fire-and-forget"; the human is "project manager" and can pause the orchestrator and tell it to re-plan, reorder, re-scope, or mark an item complete.
- Powers: add work (fix features), change plan (reorder, adjust milestone scope) on its own or on user request; spec/contract change only via the user conversation.
- Cadence: per milestone, not per feature. Docs: for simple projects "one milestone is often enough"; more milestones "prevent drift".
- Published numbers for one mission (Slack clone, 16.5 h, 185 runs, 778.5M tokens): orchestration = 2.3% of time and 29.2M tokens; validation 37.2% of time; validators raised 81 issues (65 blocking); orchestrator created 21 fix features on top of 40 original (34.4% of implementation); every milestone converged in 2-4 validation rounds.
- Cost heuristic: total runs ≈ features + 2 × milestones, "a floor rather than a ceiling".
- Owner failure modes they state: the orchestrator "still scopes too broadly sometimes"; missions can freeze (the remedy is a human message to the orchestrator); a feature retry-limit warning exists; open questions on parallelism, long-horizon correctness, and sub-orchestrators ("Three starts to feel like a bureaucracy"). Features run mostly serially.
- Scale: sweet spot "about 1-500 features".
- Not found: the schema of the worker handoff itself (the post says workers and validators "flag" things; the fields are not published).

### 3.3 Anthropic
**Planner / generator / evaluator (Mar 2026)** [V] (source 10)
- Planner: expands a 1-4 sentence prompt into a product spec; runs once (4.7 min, $0.46 in the later run); does not come back during the build.
- Generator: builds; one continuous session.
- Evaluator: fresh agent driving the app via Playwright; hard thresholds; files bugs back to the generator. Read-only judge + feedback; it does not create plan items or change the spec.
- v1 cadence: per sprint, with a generator/evaluator **sprint contract** negotiated before each sprint (27 criteria in one sprint). Communication "handled via files".
- v2 (Opus 4.6): sprint construct removed; evaluator "a single pass at the end". Stated rule: the evaluator "is not a fixed yes-or-no decision"; it is worth its cost when the task is beyond what the model does reliably alone. "Every component in a harness encodes an assumption" about model limits, to be re-tested as models change.
- Owner-side failure modes: self-evaluation praises mediocre work; the untuned evaluator would find real issues then "talk itself into" approving; it tested superficially; tuning took several rounds of reading logs. Cost: $9 solo vs $200 full harness (v1); $124.70 (v2).
- Unassembled-parts evidence: in the solo run the "wiring between entity definitions and the game runtime was broken"; in v2 the generator "was still liable to miss details or stub features" and QA caught them.
- No re-planning owner exists in this harness. One generator, no ticket graph, no parallel workers.

**Effective harnesses (Nov 2025)** [V] (source 11): no owner agent at all. State is `feature_list.json` (each item has `passes`), `claude-progress.txt`, git history; each fresh session reads them, does one feature, updates them. Workers may only flip `passes`; removing or editing tests is called "unacceptable". The whole is "owned" by the immutable feature list. Open question stated: single general agent vs specialised (testing/QA/cleanup) agents.

**Building effective agents** [V] (source 12): workflows = "predefined code paths"; "orchestrator-workers" suits tasks "where you can't predict the subtasks needed"; start with "the simplest solution possible"; workflows give "predictability and consistency for well-defined tasks".

**Multi-agent research system** [V] (source 13): LLM lead agent; subagents need "an objective, an output format", tool guidance and "clear task boundaries", otherwise they "duplicate work, leave gaps"; subagent outputs to the filesystem to limit the "game of telephone"; multi-agent ≈ 15× chat tokens; domains with "many dependencies between agents" are named a poor fit (coding cited).

**Claude Code agent teams** [V] (source 14): experimental. The lead is an LLM session "coordinating work, assigning tasks, and synthesizing results"; shared task list with dependencies; teammates notify the lead on idle with their final answer. Deterministic gates are hooks: `TaskCreated`, `TaskCompleted`, `TeammateIdle` (exit code 2 blocks and sends feedback). Teammate plan approval is granted automatically "without the lead reviewing it". Documented lead failure: it "starts implementing tasks itself instead of waiting"; advice not to let a team "run unattended for too long". Guidance: 3-5 teammates, 5-6 tasks each; teams are less effective for "sequential tasks, same-file edits, or work with many dependencies".

### 3.4 OpenAI
**Symphony** [V] (source 15)
- SPEC: "Symphony is a scheduler/runner and tracker reader." Non-goals include "Built-in business logic for how to edit tickets, PRs, or comments" and being a general workflow engine. The orchestrator relies only on "success versus failure". A successful run may end at a handoff state such as `Human Review`, "not necessarily `Done`". Nothing in the spec owns a multi-ticket outcome.
- Reference `WORKFLOW.md` (the per-ticket agent prompt) carries the handoff discipline instead: one persistent "Codex Workpad" comment per ticket for "all progress and handoff notes"; ticket `Validation` / `Test Plan` sections are "non-negotiable acceptance input"; user-facing changes need a UI walkthrough criterion; out-of-scope discoveries: "file a separate Linear issue instead of expanding scope", with title, description, acceptance criteria, placed in `Backlog`, linked `related`, `blockedBy` when dependent. `Backlog` is human-controlled: the agent must not modify it and waits for a human to move it to `Todo`. "Do not ask a human to perform follow-up actions"; stop early only for a true external blocker.
- So: workers may *propose* work (Backlog), the human *admits* it, the scheduler is deterministic, and the human judges each ticket at `Human Review`. No LLM owner.

**Harness engineering** [V] (source 16): "Humans steer. Agents execute." Humans "prioritize work, translate user feedback into acceptance criteria, and validate outcomes". Agents "escalate to a human only when judgment is required". Human QA capacity became the bottleneck, which motivated making the app drivable by the agent. Complex work uses checked-in execution plans with progress and decision logs.

**ExecPlans** [V] (source 17): the plan document is the owner-state. Mandatory sections `Progress`, `Surprises & Discoveries`, `Decision Log`, `Outcomes & Retrospective`. The executing agent revises the plan itself: "If you change course mid-implementation, document why in the `Decision Log`". "Do not prompt the user for 'next steps'"; "Resolve ambiguities autonomously". It must be possible "to restart from only the ExecPlan". Each milestone "independently verifiable"; acceptance as observable behaviour. Single agent, single thread: owner and worker are the same agent, continuity is the file.

### 3.5 Cognition [V] (source 18)
- Manager Devin splits a task, spawns child Devins, coordinates "through an internal MCP". Shape: "map-reduce-and-manage: a manager splits work, children execute, the manager synthesizes and reports back".
- Manager failure modes stated: managers default "to being overly prescriptive", which backfires when the manager lacks codebase context; agents "assume they share state with their children when they don't"; a child writing back to its manager for relay to siblings "doesn't happen by default" because models were not trained where it mattered.
- Open problems, verbatim: "How does a child agent surface a discovery that should change its siblings' work?" and how a weaker model learns "when to escalate".
- What works today: "writes stay single-threaded"; a clean-context reviewer; the reviewing/coding bridge must filter findings against the user's instructions to prevent "looping" and out-of-scope work.
- Their remark on the big demos (browser, C compiler): they share "a simple, verifiable success criterion" that most real software lacks.

### 3.6 Gas Town / Gas City [V] (sources 19, 20)
- **Mayor (Gas Town template)**: "global coordinator", "not a solo coder"; default action is file a bead and sling it. Responsibilities: work dispatch, cross-rig coordination, "Escalation handling: Resolve issues Witnesses can't handle", "Strategic decisions: Architecture, priorities, integration planning". "NOT your job": per-worker cleanup, session killing, routine nudging (Witness). The template is town-wide, not per convoy or per Spec; it contains no instruction to read each ticket's result against a Spec.
- **Mayor (Gas City built-in prompt)**: "plan work, manage rigs and agents, dispatch tasks, and monitor progress"; hands off to its own next session via `gc handoff` when context is long. Gas City `AGENTS.md`: "Mayor is overseer, not worker" and "ZERO hardcoded roles". The migration doc calls the Mayor session "one window onto the city" while the orchestrator (code) keeps "driving formula graphs to completion behind it".
- **Convoy semantics (Gas City CLI reference)**: `gc convoy check` auto-closes convoys "where all child issues are resolved" (status closed). `--owned` = "manual lifecycle, no auto-close"; `--owner` = "who manages it"; `--notify` = target on completion. `gc convoy land` = "verifying all children are closed", then closes; `--force` lands with open children. Both closing paths test ticket status only; neither tests the assembled outcome. A convoy "owner" is a metadata field plus manual lifecycle, not a defined judging role.
- **Formula v2**: control beads are "orchestrator-owned" (check, retry, fanout, drain, scope-check, workflow-finalize); `check` supports only `mode = "exec"` (a script). Verification inside a formula is deterministic by construction.
- **Witness / Deacon**: health roles (stuck or failed polecats, heartbeats), not outcome roles. Escalation protocol: `gt escalate -s <SEVERITY>`; tiers Deacon → Mayor → Overseer (human), each "can resolve OR forward"; escalations are beads with severity routes (mail to Mayor, email/SMS to the human for HIGH/CRITICAL), stale detection and re-escalation. Polecat `gt done` exit types: `COMPLETED`, `ESCALATED`, `DEFERRED` (structured exit status).
- **Mountain-Eater design doc** (status "Design"; `gt mountain` command exists in the tree and changelog; whether Layers 1-2 run as designed was not verified): the stated problem is large epics stalling because the ConvoyManager "is mechanical". Design principle, verbatim heading: "No Agent Holds the Thread". Reason: an agent keeping an "I'm driving this epic" loop "will lose that thread at compaction". Instead "The beads ARE the state"; periodic fresh-context "Dogs" audit the convoy from scratch and mail the Mayor on stall or completion; skip an issue after 3 polecat failures. "The Mayor is NOT part of the grinding loop"; its actions on notification are retry, permanently skip, notify the user, or "Restructure DAG". The whole design targets *stall and progress*, not *is the assembled result correct*.
- Yegge's essays [P]: work is lost and designs go missing; design, taste and architecture stay with the human.

### 3.7 StrongDM [P]
No in-run owner agent described. The outcome is owned by holdout scenarios the builder cannot see plus a probabilistic satisfaction score; humans own intent before the non-interactive run. Not re-verified today.

### 3.8 Spotify, Stripe
- Spotify [V]: the agent "is built to do one thing"; pushing code, Slack and prompt authoring are "managed by surrounding infrastructure" on purpose, because reduced flexibility "makes it more predictable". Deterministic verifiers via a stop hook; an LLM judge compares diff to prompt and vetoes about a quarter of sessions (agent recovers about half). Their judge has no evals yet. When the agent stops, a human engineer decides whether to fix "half-broken code"; PR review is human.
- Stripe [P]: blueprints mix deterministic nodes with agent nodes; at most two CI rounds, then the work goes to a human; human review of every PR.
- Both are single-task systems: no multi-ticket outcome exists to be owned.

### 3.9 HumanLayer 12-factor [V]
Factor 7: contacting a human is a structured tool call / intent (`request_human_input`, `done_for_now`) handled by the outer deterministic loop, which notifies the human and later appends the response to the thread. Combined with factor 8 ("own your control flow"): code owns the loop; the LLM only emits the next step.

### 3.10 Spec Kit, Kiro [V]
- Spec Kit `implement`: one agent executes `tasks.md` phase by phase, marks `[X]`, halts on a failed non-parallel task and "suggest next steps"; final step checks features "match the original specification". `analyze` is "STRICTLY READ-ONLY" and runs before implementation; remediation requires explicit user approval. If tasks are incomplete, it suggests the user re-run the tasks command. Nothing re-plans during implementation.
- Kiro: tasks grouped into dependency waves, run concurrently within a wave; status updated in `tasks.md`. Spec refinement (requirements → design → tasks) is initiated by the user in a spec session. No in-run re-planning agent is described.

---

## 4. Comparison table

| System | Owner of the whole during delivery | Type | Powers | Worker → owner handoff | Cadence | Escalation to human | Stated failure modes of the owner / remedies |
|---|---|---|---|---|---|---|---|
| Pocock `implement-spec` | Orchestrator session dispatches; human owns the result at the end | LLM dispatcher + human | Dispatch, merge, one end review + one fix pass. No add / re-order / split | "Reporting done" + context pointers (commits, ticket). No format | Frontier recomputed per merge; review once at end | None defined; human reviews integration branch | Review/fix loop without stop (4 h reported); stale frontier; an agent making orchestration decisions is less reliable than a loop |
| Pocock Sandcastle | Nobody in-run; human after | Code loop + stateless LLM planner (frontier selector) | Planner selects only; merger closes issues | Commit message fields (decisions, blockers) + issue comment + completion tag; code reads only "has commits" | Plan → execute → merge cycle, up to 10 | None; console log | Partial work can be merged and closed; no end evaluator |
| Cursor (final design) | Root planner; sub-planners per slice | LLM | Add tasks, re-plan continuously; no coding; cannot change instructions | Single free-text handoff: done, notes, concerns, deviations, findings, feedback | Event-driven, on each handoff | None in-run; humans rewrite instructions between runs | One agent with all roles → sleeps, codes itself, premature completion; tunnel vision; drift. Remedies: split roles, rewrite scratchpad, fresh starts |
| Factory Missions | Orchestrator, re-entering after each milestone validation | LLM owner + programmatic runner + LLM validators | Add fix features; reorder / re-scope; halt. Contract via user | Workers hand off; validators flag issues (blocking / non-blocking / suggestion). Fields unpublished | Per milestone (2-4 validation rounds each) | Orchestrator halts and returns control when blocked; human can pause and redirect | Scopes too broadly; freezes; cost (validation 37% of time); mostly serial |
| Anthropic 3-agent harness | Evaluator judges; planner only at start | LLM judge (no re-planner) | Judge + feedback to generator | Files; sprint contract (v1) | Per sprint (v1) → once at end (v2) | None described | Lenient judge talks itself out of findings; superficial testing; cost; component value shifts with model |
| Anthropic effective harnesses | The feature list file | Files + code loop | Workers flip `passes` only | Progress file + git commit | Every session | None described | Premature "done"; untested "passes" without browser automation |
| Claude Code agent teams | Team lead | LLM (+ optional hooks) | Create / assign tasks, synthesize | Idle notification with final answer; shared task list | On teammate idle | Permission prompts bubble to user | Lead implements itself; token cost; unattended drift |
| OpenAI Symphony | Nobody across tickets; human per ticket | Code scheduler + human review state | Scheduler: dispatch / retry only. Worker may file Backlog issues | Persistent workpad comment; ticket state transition; follow-up issue with acceptance criteria | Per ticket | `Human Review` state; Backlog admission by human | Out of scope by design |
| OpenAI ExecPlans | The plan document, revised by the executing agent | File + single LLM | Agent changes plan, logs why | Decision Log, Surprises, Progress in the plan | Every stopping point | Discouraged during the run | (single agent; none stated) |
| Cognition Devin | Manager Devin | LLM | Split, coordinate, synthesize | Via internal MCP; child → manager relay not default | Not specified | Not specified | Over-prescriptive manager; false shared-state assumption; sibling-relevant discoveries lost (open) |
| Gas Town / Gas City | Code feeds the convoy; Mayor on escalation; human overseer | Code (ConvoyManager / control dispatcher) + LLM Mayor + human | Mayor: retry, skip, restructure DAG, dispatch. Convoy close: by ticket status | `gt done` status COMPLETED / ESCALATED / DEFERRED; bead notes; mail | Continuous feed; Dog audit periodic (design) | `gt escalate` severity routes, tiered Deacon → Mayor → human | A coordinating agent loses the thread at compaction; mechanical feeder cannot judge; work lost |
| StrongDM | Holdout scenarios + satisfaction score | Tests / LLM-judged metric | Judge | n/a | n/a | Intent fixed before run | Cost [P] |
| Spotify / Stripe | Human reviewer of each PR | Human; code pipeline | n/a (single task) | PR | Per task | Stop after verifier failure / 2 CI rounds | Judge without evals (Spotify) |
| Spec Kit / Kiro | The user | Human; single agent executes | Agent halts and suggests | Checkbox in `tasks.md` | Per task / wave | Halt and ask | No in-run re-plan |

---

## 5. Published statements on "deterministic loop + end evaluator" vs "LLM orchestrator that re-plans"

No source runs a controlled comparison of the two at small scale (one Spec, 10-25 tickets, 1-4 workers). What exists:

1. Pocock docs [V]: for truly AFK work a deterministic loop is "faster, cheaper, and more reliable, because no agent makes the orchestration decisions"; the agent-orchestrated skill is for sessions you "watch and steer". Neither of his variants re-plans.
2. Cursor [V]: tried owner-with-judge, then owner-without-judge-doing-everything (pathological), then planners that only plan. Their finding is about role overload of the owner, at very large scale. They removed the judge and the integrator; they kept an LLM owner.
3. Factory [V]: deterministic runner walks the feature list; an LLM owner re-enters only at milestone boundaries to turn validator findings into fix features. Reported share: orchestration 2.3% of runtime; fix features 34% of implementation work. Sweet spot stated as 1-500 features; "one milestone is often enough" for simple projects.
4. Anthropic harness [V]: moved the evaluator from per-sprint to end-only when the model improved; evaluator value depends on whether the task is beyond what the model does reliably alone. No re-planning owner in either version.
5. Anthropic "Building effective agents" [V]: predefined workflows for well-defined tasks; orchestrator-workers when subtasks cannot be predicted.
6. Gas Town Mountain-Eater [V, design doc]: explicit argument *against* a persistent coordinating agent ("No Agent Holds the Thread"), in favour of state in beads plus fresh-context periodic auditors plus escalation to the Mayor. Threshold given: regular convoy for 3-5 tasks; mountain for "10+ tasks and DAG deps".
7. Claude Code agent teams [V]: for sequential or dependency-heavy work, a single session or subagents are "more effective" than a team with a lead.
8. Cognition [V]: the manager pattern is live but coherence took more work than expected; the sibling-discovery problem is unsolved.
9. [S] arXiv 2606.15874, arXiv 2508.02721, Bernstein ADR 006: argue for deterministic control flow with LLMs at leaf nodes. Known from search summaries only.

---

## 6. Convergent / contested / not verified

### Convergent (three or more independent [V] sources)
1. **The worker never has the final say on its own ticket.** Factory ("not their call"), Anthropic (separate evaluator), Cursor (handoff goes up), Symphony (`Human Review`), Spotify (judge + human PR review), Pocock (review at end).
2. **Out-of-scope or follow-up work must become a tracked item, not prose.** Symphony (separate issue with acceptance criteria), Factory (fix features), Cursor (planner creates tasks from handoffs), Pocock (QA creates issues), Gas Town (file a bead).
3. **Whatever owns the whole keeps its state in files or the tracker, not in a context window.** Factory shared state files, Anthropic feature list + progress file, ExecPlans, Cursor rewritten scratchpad, Gas Town beads, Symphony workpad.
4. **An owner that also executes degrades.** Cursor (continuous executor pathologies), Claude Code docs (lead implements itself), Gas Town (Mayor "coordinator, not a solo coder"), Factory (orchestrator delegates all investigation and implementation).
5. **Long-lived owner sessions drift or lose the thread; remedy is fresh context reading durable state.** Cursor (fresh starts), Anthropic (context resets with structured handoff), Gas Town (compaction, Dogs), Gas City Mayor (`gc handoff` to self).
6. **The spec / definition of done is not editable by anything in the delivery loop.** Cursor (instructions changed by humans between runs), Factory (contract written first, changed via user), Anthropic (tests may not be edited), Symphony (ticket validation "non-negotiable"). ExecPlans is the exception for the *plan* (not the purpose).
7. **Mechanical dispatch is code in most systems, even those with an LLM owner.** Factory runner, Symphony scheduler, Sandcastle loop, Gas City control dispatcher, Gas Town ConvoyManager, Spotify/Stripe pipelines. Cursor is the outlier (harness delivers handoffs, planners decide everything else).

### Contested
1. **Is there an LLM owner in the run at all?** Yes: Cursor, Factory, Cognition, Claude Code teams. No (code + files + end/human judgment): Sandcastle, Symphony, Anthropic effective-harness, Spec Kit, Kiro, Stripe, Spotify. Gas Town: code first, LLM only on stall/escalation, and its design doc argues against a persistent driver.
2. **Cadence of the owner's judgment.** Per handoff (Cursor) vs per milestone (Factory) vs end only (Anthropic v2, Pocock) vs per ticket by a human (Symphony).
3. **Handoff shape.** Free text with named topics (Cursor) vs structured exit status (Gas Town `gt done`, Sandcastle completion tag, HumanLayer intents) vs pointers only (Pocock) vs a persistent per-ticket workpad (Symphony). No source publishes a validated schema, and none reports measuring free text against structured.
4. **Who may create repair work.** The LLM owner alone (Factory, Cursor) vs the worker proposing into a human-gated backlog (Symphony) vs the human only (Pocock, Spec Kit, Kiro).
5. **Separate judge beside the owner.** Cursor removed its judge; Factory and Anthropic treat independent validators as the core; Anthropic says the value depends on model capability.
6. **Scale transfer.** Cursor's evidence is hundreds of agents; Factory's is 40-60 features run mostly serially; Gas Town's own threshold says 3-5 tasks need no judgment layer. Nothing published isolates 10-25 tickets with 1-4 workers.

### Directly matching the reported incident (facts from sources, no inference about the fix)
- "Subagent flag dropped by its parent": Pocock's dictionary states a subagent report is a secondary source and omissions are invisible to the parent; Cognition says child → manager → sibling relay "doesn't happen by default".
- "Convoy closed on ticket count": Gas City `gc convoy check` and `gc convoy land` are documented as testing child status only; Sandcastle's merger closes issues on merge.
- "Wiring is a later ticket's job": Cursor reports that constraints such as "No TODOs, no partial implementations" work better than reminders; Anthropic reports stubbed features and broken wiring caught only by an evaluator operating the app; Factory has each feature claim contract assertions, verified black-box at the milestone.

---

## 7. Not verified

- **Factory worker handoff schema**: fields that workers and validators write back are not published; only the categories "blocking / non-blocking / suggestion" appear (in a chart). The secondary names "scrutiny" and "user-testing" validators are now confirmed [V].
- **Cursor**: whether the handoff has any enforced structure in the harness; the root planner's prompt; how a planner decides the goal is met after the judge was removed. Only the blog prose is available.
- **Cognition**: the manager/child MCP message format, and whether a manager may re-plan children mid-flight. The post gives one paragraph.
- **Gas Town Mountain-Eater**: the doc is marked "Design". `gt mountain` exists in the source tree and changelog, but I did not verify that Witness failure tracking and the Deacon Dog audit run as described, nor whether Gas City has an equivalent.
- **Gas City convoy owner**: `--owner` / `--owned` / `--notify` are documented as flags; I found no document defining duties of a convoy owner agent, and did not read the Go implementation. The Gastown pack's `mayor` prompt inside Gas City was not located (only the built-in `cmd/gc/prompts/mayor.md` and example packs were read); `convoymaster` in an example pack has a 4-line prompt that I did not analyse.
- **Yegge "From Clown Show to v1.0"** (April 2026): still not read.
- **StrongDM, Stripe**: not re-read today (script-rendered pages); statements are carried from the prior report.
- **Symphony "proof of work"** contents: README sentence confirmed [V] (CI status, PR review feedback, complexity analysis, walkthrough videos); the mechanism producing them was not traced in the reference implementation.
- **Pocock**: X posts, newsletter and YouTube since mid-2026 not readable; talk statements are from the prior transcript read. Issues #723 and others were not re-queried today.
- **Kiro**: whether the agent ever edits `tasks.md` structure on its own during a run; the docs describe only user-initiated updates.
- **Academic sources in row 26**: search summaries only; claims not checked against the papers.
- **OpenAI harness-engineering date/author**: not shown in the fetched text.
- **Any controlled small-scale comparison** of deterministic loop + end evaluator versus LLM owner that re-plans: none found.
