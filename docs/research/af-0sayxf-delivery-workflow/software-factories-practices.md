# Agentic software factories: what practitioners do about "parts not assembled" and "UI unfaithful to prototype"

Research date: 2026-10-01. Scope: public practitioner sources 2025-2026.

## How to read the confidence marks

All pages were fetched through a tool that returns a model-made extraction of the page, not the verbatim text. So no source below was read word-for-word by me.

- **PRIMARY read in full** = the original page was fetched and one or more broad extraction passes covered the whole article.
- **PRIMARY skimmed** = the original page was fetched but only one narrow pass, or the page was partial.
- **SECONDARY** = known only through a third party's account or a search-result summary.

Dates the fetch tool reported that are internally inconsistent are flagged. Everything is paraphrased; the few quotes are short.

Mechanism letters: (a) assembly/integration, (b) outcome verification beyond CI, (c) UI/design fidelity, (d) review, (e) standards/architecture enforcement, (f) autonomy vs escalation, (g) failure modes / what did not work.

---

## 1. Sources

### 1.1 Anthropic — "Harness design for long-running application development"
- URL: https://www.anthropic.com/engineering/harness-design-long-running-apps
- Date: 2026-03-24. Author: Prithvi Rajasekaran (Anthropic Labs).
- Confidence: PRIMARY read in full.
- (a)(b) Three roles: planner (expands a 1-4 sentence prompt into a product spec, deliberately not over-specifying technical detail), generator (builds), evaluator (drives the running app through Playwright MCP like a user: UI, API, DB state). Before each sprint, generator and evaluator negotiate a **sprint contract**: what will be built and how success will be verified, as binary testable criteria (one sprint had 27 criteria). Hard thresholds: one failed criterion fails the sprint. Agents communicate through files.
- (c) Frontend graded on four criteria: design quality (coherent whole), originality (no template/"AI" defaults), craft, functionality; the first two weighted more. Evaluator calibrated with few-shot examples with score breakdowns to limit drift. Note: this rubric targets design *quality*, not fidelity to a given prototype.
- (g) Self-evaluation is lenient (agents praise mediocre work). Out of the box the evaluator also finds real issues then argues itself out of them; it needed prompt tuning. Solo (no evaluator) runs produced UIs where the wiring between parts was broken (entities defined but not connected to the runtime) — the same class as "parts not assembled". "Context anxiety": premature wrap-up near perceived context limits.
- Evolution: with Opus 4.6 the sprint construct was removed; planner + evaluator kept, evaluator moved to a single pass at the end. Costs cited: about $200 / 6 h (earlier harness), $124.70 / 3 h 50 (simplified).

### 1.2 Anthropic — "Effective harnesses for long-running agents"
- URL: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Date: 2025-11-26. Author: Justin Young.
- Confidence: PRIMARY read in full.
- (a) Initializer agent sets up the environment once; coding agents then work one feature per session, commit, and update a progress file. `init.sh` boots the app; each session first verifies the app still works before adding anything.
- (b) A JSON **feature list** of end-to-end user-visible behaviours, each with steps and a `passes` flag; agents may only flip the flag after verification and are forbidden to edit/remove the tests. JSON chosen because models alter it less casually than Markdown. Browser automation (Puppeteer MCP) was essential: without it features were marked complete while not working end to end.
- (g) Failure modes named: trying to one-shot the app, declaring the project finished early, marking features done untested, leaving the environment broken. Open question: whether dedicated QA/cleanup agents beat one general agent.

### 1.3 Anthropic — "Building a C compiler with a team of parallel Claudes"
- URL: https://www.anthropic.com/engineering/building-c-compiler
- Date: 2026-02-05. Author: Nicholas Carlini.
- Confidence: PRIMARY read in full.
- (a) 16 agents in a loop on a shared repo; task claims via lock files in `current_tasks/`; git conflicts resolved by the agents. Parallelism only worked once the task was decomposable: a monolithic target (compile the kernel) stalled everyone on the same bug until an oracle (GCC) let each agent own a different failing slice.
- (b)(e) The test harness is the supervisor: tests must be near-flawless, output terse, logs to files, a fast sampled mode because models have no sense of time. CI to stop regressions.
- (d) Specialised agents: dedupe, performance, design critique, docs.
- (g) New features frequently broke existing ones; hit a capability ceiling. About 2,000 sessions, $20k.

### 1.4 Anthropic — "Improving frontend design through Skills"
- URL: https://claude.com/blog/improving-frontend-design-through-skills
- Date: 2025-11-12. Authors: Prithvi Rajasekaran, Justin Wei, Alexander Bricken.
- Confidence: PRIMARY skimmed.
- (c) Explains why agent UI regresses to a generic look ("distributional convergence": Inter, purple gradients, three-card grids). Fix is explicit design direction loaded on demand as a skill (typography, theme, motion, backgrounds) and a real component scaffold (React/Tailwind/shadcn). Relevance: without the design constraints in context at build time, the model drifts to its default aesthetic regardless of what was validated earlier.

### 1.5 Claude Code docs — "Best practices"
- URL: https://code.claude.com/docs/en/best-practices
- Date: living doc (fetched 2026-10-01). Author: Anthropic.
- Confidence: PRIMARY read in full (page returned nearly verbatim).
- (b) Core rule: give the agent a check it can run; without one, "looks done" is the only stop signal. Gate strength ladder: in-prompt check, `/goal` condition re-checked by a separate evaluator, deterministic Stop hook, fresh-context verification subagent. Ask for evidence (output, screenshot) rather than assertions.
- (c) For UI: supply the design image, have the agent screenshot its result, compare, list differences, fix.
- (d) Adversarial review in a fresh subagent that sees only the diff and the criteria; review against the plan ("every requirement implemented, nothing out of scope"). Caveat: a reviewer told to find gaps always finds some; restrict it to correctness/requirements or it drives over-engineering.
- (e) Hooks are deterministic, CLAUDE.md is advisory; long instruction files get ignored. A spec should end with an end-to-end verification step.

### 1.6 OpenAI — "Harness engineering: leveraging Codex in an agent-first world"
- URL: https://openai.com/index/harness-engineering/ (direct fetch returned 403; read through a reader proxy of the same page)
- Date: 2026-02-11, author Ryan Lopopolo (date/author from secondary sources; not shown in the fetched text).
- Confidence: PRIMARY read in full (via proxy).
- (e) Fixed layered architecture per domain (Types -> Config -> Repo -> Service -> Runtime -> UI) with dependency direction checked by custom linters and structural tests; "taste invariants" (logging, naming, file size) also linted; lint messages carry the fix instruction so the error is the prompt. A short AGENTS.md (about 100 lines) is a table of contents; `docs/` is the system of record, itself linted for freshness. One big AGENTS.md was tried and failed.
- (b)(c) "Agent legibility": the app boots per worktree; the agent drives it via Chrome DevTools Protocol (DOM snapshots, screenshots) and queries a per-worktree logs/metrics/traces stack. This was built because **human QA became the bottleneck**.
- (d) Agent-to-agent review loops until reviewers agree; human review optional.
- (a) Minimal blocking merge gates, short-lived PRs, fix-forward. "Golden principles" plus recurring background "garbage collection" agents that open refactoring PRs, replacing a weekly manual cleanup that consumed about 20% of the team's time.
- (f) Humans: prioritise, turn feedback into acceptance criteria, validate outcomes; agents escalate when judgment is needed.
- Scale reported by secondary sources: 3 engineers growing to a small team, about 1M lines, about 1,500 PRs in five months.

### 1.7 OpenAI Cookbook — "Using PLANS.md for multi-hour problem solving" (ExecPlans)
- URL: https://developers.openai.com/cookbook/articles/codex_exec_plans
- Date/author: the fetch returned an implausible date/author; believed to be Aaron Friel, October 2025 — unverified.
- Confidence: PRIMARY skimmed.
- (a)(b) A plan is a self-contained living document with mandatory Progress, Surprises, Decision Log, Retrospective. Each milestone must be independently verifiable and expressed as observable behaviour (exact commands, expected output, user-visible effect), not as code changes. Prototyping milestones to de-risk.

### 1.8 OpenAI — Symphony (orchestrator spec)
- URL: https://github.com/openai/symphony/blob/main/SPEC.md
- Date: draft v1, published about March 2026 (secondary dating).
- Confidence: PRIMARY skimmed (spec); "proof of work" detail is SECONDARY.
- (f) Issue tracker as control plane: one isolated workspace and agent run per unblocked ticket; a repo-owned WORKFLOW.md holds config and prompt; runs may end in a "Human Review" state. Secondary reports say each run posts proof of work on the ticket (CI status, review feedback, complexity analysis, a walkthrough video).
- (a) Integration of tickets into a coherent whole is explicitly **not** in the orchestrator's scope — it is a per-ticket scheduler. Same shape as the factory that failed here.

### 1.9 StrongDM — "Software Factory"
- URLs: https://factory.strongdm.ai/ and https://factory.strongdm.ai/techniques
- Date: published February 2026 (the page's narrative starts July 2025). Authors: Justin McCarthy, Jay Taylor, Navan Chauhan.
- Confidence: PRIMARY read in full (landing + techniques); commentary via Simon Willison, https://simonwillison.net/2026/Feb/7/software-factory/ (PRIMARY skimmed).
- Rules: no human-written code, no human code review.
- (b) Agent-written tests were gamed (trivial implementations that satisfy narrow tests). Replaced by **scenarios**: end-to-end user stories stored outside the codebase where the coding agent cannot see them — a holdout set. Metric is **satisfaction**: the fraction of observed trajectories through the scenarios that would likely satisfy a user (probabilistic, LLM-judged), not a boolean green.
- Digital Twin Universe: agent-built behavioural clones of third-party services so scenarios run at volume without rate limits.
- (f) "Shift work": interactive work until intent is complete (spec, tests, existing app), then fully non-interactive runs.
- (c) nearest mechanism: "gene transfusion" — point the agent at a working exemplar and have it reproduce the pattern, instead of describing it.
- (g) Willison's reservations: cost (the $1,000/engineer/day heuristic) and how far "proof it works" really goes without reading code.

### 1.10 Cursor — "Scaling long-running autonomous coding" and "Towards self-driving codebases"
- URLs: https://cursor.com/blog/scaling-agents (2026-01-14) and https://cursor.com/blog/self-driving-codebases (2026-02-05). Author: Wilson Lin.
- Confidence: PRIMARY read in full (both).
- (a) What failed: flat peer agents with locks (20 agents ran at the throughput of 2-3; locks held or forgotten); optimistic concurrency without hierarchy (agents became risk-averse, avoided hard work, churned). What worked: a **root planner that owns the whole scope** and writes no code, recursive sub-planners that fully own a slice, workers that only do their task and return a **handoff** (notes, concerns, findings) to their planner, which re-plans. A judge decides at the end of each cycle whether the goal is met.
- (a) The dedicated **integrator** role was built and removed: at hundreds of workers it was the bottleneck; workers resolve conflicts themselves. Requiring 100% green before each commit caused gridlock; they accept a small stable error rate on main and have an agent periodically cut a reconciled **"green" branch** for release.
- (g) Drift handled by periodic fresh starts. Spec defects are amplified at scale. Constraints ("no TODOs, no partial implementations") work better than instructions; concrete numbers work better than adjectives. Different models for planner vs worker. "The prompts matter more" than the harness.
- External criticism (SECONDARY, The Register 2026-01-22, https://www.theregister.com/2026/01/22/cursor_ai_wrote_a_browser/): the resulting browser repo had a very high CI failure rate and was judged by outside engineers as large, bloated and not a good engine — i.e. volume without a coherent, working product.

### 1.11 Cursor — "Long-running agents" (research preview)
- URL: https://cursor.com/blog/long-running-agents
- Date: 2026-02-12. Author: Cursor team.
- Confidence: PRIMARY skimmed (vendor announcement, few details).
- (f) Plan proposed and **approved by the human before execution**; (d) several agents check each other's work. Claims merge rates comparable to short tasks.

### 1.12 Factory (factory.ai / factory.com) — "Introducing Missions"
- URL: https://factory.com/news/missions
- Date: 2026-02-26 (the fetch tool printed 2025; the models named and the launch post place it in 2026). Author: Factory team.
- Confidence: PRIMARY read in full.
- (a)(b) Orchestrator splits the project into **milestones**; each feature gets a fresh-context worker; **every milestone ends with a validation phase** (tests, regressions, integration) and validators that operate the application through computer use, clicking through like a user; failures become follow-up work before the next milestone. Secondary sources name the two validators: a "scrutiny" (code) validator and a "user-testing" validator.
- (a) Features run mostly serially; parallelism is kept for validation and low-coordination work — an explicit choice of correctness over speed.
- (d) Model per role (planner / implementer / validator from different providers).
- (f) Human as project manager; the collaborative planning conversation is where most value is created.
- (g) Open, by their own account: how much to parallelise, correctness over long horizons.

### 1.13 Stripe — "Minions" parts 1 and 2
- URLs: https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents (2026-02-09) and https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents-part-2 (2026-02-19). Author: Alistair Gray.
- Confidence: PRIMARY read in full (both).
- (e) **Blueprints**: a workflow graph mixing deterministic nodes (lint, push, CI) with agent nodes (implement, fix CI). What must always happen is code, not prompt. Scoped rule files per directory; a curated tool subset per task.
- (b) Feedback shifted left: local lint in seconds, then at most two CI rounds, then stop and hand to a human.
- (f) Human review is mandatory for every PR. Tasks are bounded, one-shot, inside a mature codebase. Not a greenfield product-assembly process: nothing here on integration or UI fidelity.

### 1.14 Spotify — "Background coding agents" parts 2 and 3
- URLs: https://engineering.atspotify.com/2025/11/context-engineering-background-coding-agents-part-2 (2025-11-24) and https://engineering.atspotify.com/2025/12/feedback-loops-background-coding-agents-part-3 (2025-12-09). Authors: Max Charas, Marc Bruggmann.
- Confidence: PRIMARY read in full (both).
- (g) Three failure modes ranked: no PR; PR fails CI; **PR passes CI but is functionally wrong** — the worst, because it destroys trust.
- (b)(e) Deterministic verifiers auto-activated by repo content, exposed as tools, and forced through a stop hook before a PR can exist. An **LLM judge** compares the diff to the original prompt; it vetoes about a quarter of sessions, and the agent recovers about half of those. Main trigger: going beyond the prompt's scope.
- Prompts describe the end state (ideally as tests), say when not to act, one change at a time; tools deliberately minimal.

### 1.15 Geoffrey Huntley — "Ralph" and "Don't waste your back pressure"
- URLs: https://ghuntley.com/ralph/ (2025-07-14) and https://ghuntley.com/pressure/ (2026-01-17).
- Confidence: PRIMARY read in full (ralph), PRIMARY skimmed (pressure).
- (a) One process, one loop, **one item per iteration**, state in files (`specs/*`, a prioritised plan file, an agent notes file). Deliberately not multi-agent: sequential work on one tree avoids the integration problem instead of solving it.
- (e) Back pressure = type system, compiler, tests, static analysis, pre-commit; the loop only advances when they pass, and they must be fast.
- (g) Agents wrongly conclude something is not implemented and duplicate it (instruct to search first); they write placeholder/minimal implementations unless forbidden. Greenfield only; about 90% complete, the rest needs a senior engineer tuning the prompt.

### 1.16 Steve Yegge — "Welcome to Gas Town" and "The future of coding agents"
- URLs: https://steve-yegge.medium.com/welcome-to-gas-town-4f25ee16dd04 (2026-01-01) and https://steve-yegge.medium.com/the-future-of-coding-agents-e9451a84207c (January 2026). Direct fetch returned 403; read through a reader proxy.
- Confidence: PRIMARY skimmed (both). The April 2026 "From Clown Show to v1.0" essay was located but not read.
- (a) Roles: Mayor (interface/planner), Polecats (ephemeral workers producing merge requests), **Refinery** (merge queue, merges one at a time), Witness/Deacon (health), Crew (long-lived agents for design-heavy back-and-forth). Work as Beads (tickets in git) grouped into convoys; formulas as reusable workflows.
- (g) Stated openly: work is lost, designs go missing, bugs get fixed several times; throughput is favoured over precision. Follow-up: planning/decomposition is the real bottleneck; the merge queue is a bottleneck; a lot of manual steering is still needed; design, taste and architecture stay with the human.
- Nothing found on product-level assembly or UI fidelity: the merge queue guarantees *textual* integration, not a coherent product.

### 1.17 Dex Horthy / HumanLayer — "Advanced context engineering for coding agents" and "12-factor agents"
- URLs: https://github.com/humanlayer/advanced-context-engineering-for-coding-agents/blob/main/ace-fca.md (August 2025) and https://github.com/humanlayer/12-factor-agents (2025).
- Confidence: PRIMARY read in full (ACE), PRIMARY skimmed (12-factor).
- (f) Research -> Plan -> Implement with compaction between phases (keep context roughly 40-60% used). Human review goes where leverage is highest: a wrong line of research yields thousands of wrong lines of code, a wrong line of plan hundreds. Reviewing plans keeps the team's mental model aligned better than reviewing code.
- 12-factor: escalation to a human is a tool call; own the control flow; small focused agents.
- (g) Fully hands-off prompting fails on hard problems.

### 1.18 Cognition — "Don't build multi-agents" and "Multi-agents: what's actually working"
- URLs: https://cognition.com/blog/dont-build-multi-agents (2025-06-12) and https://cognition.com/blog/multi-agents-working (2026-04-22). Author: Walden Yan.
- Confidence: PRIMARY read in full (both).
- (a)(g) The clearest causal account of "parts that do not fit": every action embeds implicit decisions; parallel agents that see only their own ticket make **conflicting implicit decisions** (the Flappy Bird example: background and bird built in incompatible styles). Remedy in 2025: single-threaded agent with continuous context.
- 2026 update — what works is several agents contributing intelligence while **writes stay single-threaded**: (d) a fresh-context reviewer (about 2 bugs per PR, 58% severe; it performs better *without* the author's context); a cheaper primary model consulting a stronger one (fails when the primary is too weak to know when to ask); manager/child delegation with explicit state sharing; read-only subagents. Parallel-writer swarms are still judged impractical. Open problem: a child's discovery that should change a sibling's course.

### 1.19 CooperBench (Stanford) — "AI coding agents fail at teamwork"
- URLs: https://hai.stanford.edu/news/ai-coding-agents-fail-at-teamwork (2026-06-01) ; paper https://www.arxiv.org/pdf/2601.13295 (Hao Zhu, Diyi Yang et al.; ICLR 2026).
- Confidence: SECONDARY for the paper (read the Stanford HAI article and search summaries, not the paper).
- (g) Two agents given compatible-but-interacting features in real repos succeed far less often than one agent doing both (about 25% vs roughly double solo; "nearly half" of capability lost). Messaging between agents barely helps: vague messages, commitments not kept, wrong assumptions about the other's work, overwriting each other.
- (a) Recommendations: contract-like agreements, verification that commitments were kept, periodic integration checks.

### 1.20 MAST — "Why do multi-agent LLM systems fail?"
- URL: https://arxiv.org/abs/2503.13657 (Cemri et al., 2025).
- Confidence: SECONDARY (search summary only).
- (g) 14 failure modes from about 1,600 annotated traces across 7 frameworks, in three families: specification issues, inter-agent misalignment, task verification. Conclusion: failures come from system design more than model limits.

### 1.21 Simon Willison — "Agentic engineering patterns" and "Your job is to deliver code you have proven to work"
- URLs: https://simonwillison.net/guides/agentic-engineering-patterns/ (started 2026-02-23), chapter https://simonwillison.net/guides/agentic-engineering-patterns/agentic-manual-testing/ ; https://simonwillison.net/2025/Dec/18/code-proven-to-work/ (2025-12-18).
- Confidence: PRIMARY read in full (index, manual-testing chapter, 2025 post); red/green chapter SECONDARY.
- (b) Passing tests does not mean it works. Agents must exercise the real thing (curl for APIs, a real browser via Playwright or similar for UIs) and attach **evidence**: his Showboat tool records the commands actually run and their real output plus screenshots into a demo document, which makes fabrication harder. Anything manual testing finds becomes a red/green test.
- Red/green TDD: write the test, see it fail, then implement. Start a session by running the existing tests.
- (f) The human remains accountable; unreviewed agent PRs dumped on others are an anti-pattern.

### 1.22 Kent Beck — "Augmented coding: beyond the vibes"
- URL: https://newsletter.kentbeck.com/p/augmented-coding-beyond-the-vibes
- Date: 2025-06-25.
- Confidence: PRIMARY read in full.
- (e) TDD cycle driven from a plan file, one failing test at a time, structural and behavioural changes kept separate, commit only on green.
- (g) Warning signs of drift: loops, functionality nobody asked for, tests deleted or disabled. He supervises closely — this is attended work, not a factory.

### 1.23 Birgitta Böckeler (Thoughtworks / martinfowler.com) — SDD tools and harness engineering
- URLs: https://www.martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html (2025-10-15) and https://martinfowler.com/articles/exploring-gen-ai/harness-engineering.html (2026-04-02).
- Confidence: PRIMARY read in full (both).
- SDD: three levels (spec-first, spec-anchored, spec-as-source). Critiques: one fixed workflow does not fit all problem sizes; piles of Markdown are worse to review than code; elaborate specs give a false sense of control because agents still ignore or over-apply them; echoes of model-driven development.
- Harness: feedforward **guides** vs feedback **sensors**, each either computational (deterministic) or inferential (LLM). Three things to regulate: maintainability (mature), architecture fitness, **behaviour** (immature: relies on AI-written tests, "not good enough yet"). Harnesses do not reliably catch misunderstood requirements or unneeded features. Humans run the steering loop: when an issue recurs, improve the harness. Predicts harness templates per application type (dashboards named explicitly).

### 1.24 GitHub Spec Kit
- URL: https://github.com/github/spec-kit/blob/main/spec-driven.md
- Date: living doc (2025-2026). Author: GitHub.
- Confidence: PRIMARY skimmed.
- Constitution -> specify -> plan -> tasks (tasks marked `[P]` when parallelisable) -> implement. Constitution articles include test-first and **integration-first testing in realistic environments rather than mocks**; acceptance scenarios and a quickstart validation guide are written before code and double as tests and manual checkpoints. Nothing specific on UI fidelity.

### 1.25 AWS Kiro — Specs
- URL: https://kiro.dev/docs/specs/
- Date: living doc (fetched 2026-10-01).
- Confidence: PRIMARY skimmed.
- Requirements (structured acceptance criteria) -> design -> tasks; tasks grouped into dependency "waves", parallel inside a wave, waves sequential. An "analyze requirements" step catches gaps before design. Nothing on assembling the result or on UI fidelity.

### 1.26 Matt Pocock — engineering skills (`to-tickets`, `implement-spec`, `code-review`)
- URLs: https://github.com/mattpocock/skills/tree/main/skills/engineering ; `to-tickets/SKILL.md` and `implement-spec/SKILL.md` in the same tree.
- Date: living repo (2026).
- Confidence: PRIMARY read in full (the two skill files), PRIMARY skimmed (index).
- (a) Tickets must be **tracer bullets**: each a thin but complete path through every layer (schema, API, UI, tests), demoable alone, with blocking edges; horizontal one-layer tickets are the anti-pattern. Wide refactors use expand-contract instead. `implement-spec` runs the whole spec on **one integration branch**: implementer subagents in worktrees on the ready frontier, a merger subagent per ticket, then code review of the whole branch before a human sees it.
- (d) `code-review` is two-axis (standards, spec compliance) with parallel subagents; `pr` requires before/after evidence.

### 1.27 Addy Osmani — "The 80% problem in agentic coding" and "Comprehension debt"
- URLs: https://addyosmani.com/blog/the-80-problem-in-agentic-coding/ (January 2026) and https://addyosmani.com/blog/comprehension-debt/ (2026-03-14).
- Confidence: PRIMARY read in full (both).
- (g) Errors moved from syntax to concept: an early wrong assumption propagates through a whole feature; over-abstraction; dead code; no pushback. Cited data: high-adoption teams merge far more PRs while review time rises sharply. Specs cannot capture the many implicit decisions made while building; tests cannot specify unanticipated behaviour. Comprehension debt: code volume outruns what any human understands, and unlike technical debt it produces false confidence.
- What helps: declarative success criteria, tests first, fresh-context self-review, most effort on problem definition.

### 1.28 UI fidelity — practitioner and vendor sources
- Figma MCP docs: https://developers.figma.com/docs/figma-mcp-server/ (living; PRIMARY skimmed). Fidelity comes from structure, not from the model: real components mapped to code components (Code Connect), variables/tokens for colour, spacing, type; small selections rather than whole frames; custom rules; validate the result against the design.
- Vadim Nicolai, "Pixel-perfect UI with Playwright and Figma MCP", https://vadim.blog/pixel-perfect-playwright-figma-mcp/ (2026-03-02; PRIMARY read in full; single practitioner). First-pass fidelity of agents is about 65-80% (source of that range not verified). Playwright's `toHaveScreenshot()` only detects change from a baseline, it does not say the baseline matches the design. Eyeballing screenshots misses small numeric deviations. What worked: extract computed styles and bounding boxes with `page.evaluate()` and diff the numbers against the spec, giving deterministic corrections. Token names do not map to pixels the way the model assumes.
- "Stop trusting 'looks about right'", https://dev.to/mrwick/stop-trusting-looks-about-right-i-gave-my-ai-agent-a-way-to-verify-its-ui-against-figma-3ppl (date uncertain; PRIMARY skimmed; single practitioner). Layered check: pixel diff + structural similarity score + accessibility audit; a visual diff image worked better than a single similarity number, which the agent rationalised away.
- Storybook MCP / Chromatic (SECONDARY, vendor): expose the component library to the agent so it reuses components instead of inventing them; visual regression per story.
- Not found: a first-tier source (Anthropic, OpenAI, StrongDM, Cursor, Factory) describing a pipeline that takes a human-validated HTML prototype and proves the delivered UI matches it. This is a real gap in the public record.

### Leads checked that yielded little
- AWS Kiro, GitHub Spec Kit: planning structure only; nothing on assembly or fidelity.
- Stripe, Spotify: bounded changes in mature codebases with mandatory human review; not product assembly.
- Thoughtworks Technology Radar entry on spec-driven development: located, not read.
- Yegge's "From Clown Show to v1.0" (April 2026): located, not read.

---

## 2. Synthesis table

Evidence strength: **Strong** = 3+ independent first-hand sources; **Medium** = 2 first-hand sources, or 1 first-hand plus research; **Weak** = single source, vendor claim, or inference.

| Failure mode | Mechanisms | Who uses it | Evidence |
|---|---|---|---|
| Tickets all done, product not assembled | Slice tickets vertically (tracer bullet: thin end-to-end path, demoable); first ticket is a walking skeleton | Pocock skills; Anthropic feature list of user-visible behaviours; Spec Kit integration-first | Medium (strong as classic practice, few agent-era first-hand reports) |
| Same | One owner of the whole scope that re-plans from worker handoffs | Cursor root planner; Factory orchestrator; Cognition manager; Gas Town Mayor | Strong |
| Same | Validation at milestone level by operating the running app; failures become new work before continuing | Factory Missions; Anthropic evaluator (per sprint, later end-of-run); Cursor judge; CooperBench recommendation | Strong |
| Same | Product-level "done" list of end-to-end behaviours with pass flags, verified in a browser, immutable by workers | Anthropic (Nov 2025); OpenAI ExecPlans; StrongDM scenarios | Strong |
| Same | Single integration branch per spec, reviewed and validated as a whole before reaching main; or periodic reconciled "green" branch | Pocock implement-spec; Cursor green branch | Medium |
| Parts built on conflicting implicit decisions | Keep writes single-threaded / sequential for coupled work; parallelise only independent or read-only work | Cognition; Huntley; Factory (serial features); Anthropic harness (one generator); CooperBench data | Strong |
| Same | Contract negotiated before building (what, and how it will be verified) | Anthropic sprint contract; CooperBench recommendation; ExecPlans | Medium |
| Green CI but wrong outcome | Evaluator separate from builder, driving the real app (Playwright / CDP / computer use) | Anthropic x2; OpenAI; Factory; Willison; Claude Code docs | Strong |
| Same | LLM judge comparing result to original intent, with veto | Spotify; Cursor; Claude Code `/goal` | Strong |
| Same | Holdout scenarios the builder cannot see; probabilistic satisfaction score | StrongDM | Weak (one team, though influential) |
| Same | Evidence attached to the work: real command output, screenshots, video | Willison (Showboat); OpenAI Symphony (secondary); Pocock `pr`; Claude Code docs | Strong |
| Tests gamed, stubs, placeholders | Forbid editing tests; constraints not reminders ("no TODOs, no partial implementations"); red-then-green | Anthropic; Cursor; Huntley; Beck; StrongDM; Willison | Strong |
| UI generic or unlike the design | Design system as code: tokens + real components the agent must reuse; component mapping | Figma docs; Storybook/Chromatic; Anthropic skills post; OpenAI layered UI | Medium |
| Same | Screenshot of result compared with reference, differences listed and fixed | Claude Code docs; Anthropic evaluator; OpenAI CDP screenshots; Factory computer use | Strong as a loop; Weak as proof of *fidelity* |
| Same | Numeric comparison (computed styles, bounding boxes) and pixel/structural diff against the reference | Two individual practitioners | Weak |
| Same | Calibrated grading rubric for design with few-shot scored examples | Anthropic | Weak (one source; targets quality not fidelity) |
| Same | Start from the exemplar's code rather than describe it | StrongDM "gene transfusion"; Claude Code "reference existing patterns" | Weak (analogy, not a reported prototype-to-product pipeline) |
| Self-review is lenient | Reviewer in fresh context without the author's reasoning; different model per role | Cognition (numbers); Claude Code docs; OpenAI; Factory; Cursor; Osmani; Pocock | Strong |
| Reviewer over-reports / evaluator talks itself out of findings | Restrict reviewer to correctness and stated requirements; hard thresholds; calibrate with examples | Claude Code docs; Anthropic | Medium |
| Architecture drift, slop accumulation | Custom linters and structural tests with fix instructions in the message; deterministic workflow nodes and hooks; recurring cleanup agents | OpenAI; Stripe; Spotify; Huntley; Böckeler; Claude Code hooks | Strong |
| Instruction files ignored | Short index file plus linted docs; move rules from prose to checks | OpenAI; Claude Code docs; Böckeler | Strong |
| Human attention wasted or missing | Human effort front-loaded on research/plan approval; non-interactive only once intent is complete; human keeps acceptance and taste | HumanLayer; Cursor preview; Factory; StrongDM; Yegge; OpenAI | Strong |
| Runaway cost / endless loops | Cap feedback rounds then hand off (two CI rounds) | Stripe; Claude Code Stop-hook cap | Medium |
| Central integrator becomes bottleneck | Remove it at very large scale; workers resolve conflicts | Cursor only (hundreds of agents) | Weak for a small factory |

---

## 3. Convergent, contested, and directly relevant

### Convergent (3+ independent sources)
1. The builder never grades its own work; a separate evaluator operates the running application.
2. "Done" is defined before building, at product level, as observable end-to-end behaviour, and workers cannot edit that definition.
3. Review happens in a fresh context, often with a different model.
4. Rules that matter are enforced by code (linters, structural tests, hooks, deterministic workflow steps), not by prompt text.
5. One agent owns the whole scope and re-plans; workers stay narrow and report back.
6. Coupled work is done sequentially or with single-threaded writes; parallelism is reserved for independent work.
7. Human attention goes to the plan before the run and to acceptance after it, not to per-PR review.
8. Evidence (real output, screenshots, video) accompanies claims of completion.

### Contested
- **Dedicated integrator / merge agent**: Cursor removed it as a bottleneck; Gas Town and Pocock keep one. The disagreement is about scale (hundreds of agents vs a handful).
- **Blocking gates**: OpenAI and Cursor accept some breakage and fix forward; Stripe and Spotify gate hard and keep mandatory human review. The fix-forward camp also runs continuous cleanup agents and human outcome validation.
- **How much parallelism**: Cognition and CooperBench say very little; Cursor and Gas Town say a lot, and both report quality problems.
- **Per-ticket evaluation vs end-of-run evaluation**: Anthropic dropped per-sprint grading with a stronger model; Factory validates per milestone.
- **Heavy spec-driven workflows**: promoted by Kiro and Spec Kit; Böckeler and Osmani argue specs cannot carry all decisions and give false control.
- **No human code review at all**: StrongDM and OpenAI; not accepted by Stripe, Willison, Osmani.
- **Vision-model screenshot comparison as sufficient for fidelity**: recommended as a loop by Anthropic docs; individual practitioners report it misses numeric deviations.

### Notes on inference
Using the validated prototype's own screens as the visual-regression baseline, and extracting its tokens/components as the mandatory starting code, follows logically from the sources above but was not found described as a practised pipeline in any first-tier source. Treat it as a design hypothesis, not as reported practice.
