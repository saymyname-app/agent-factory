# Parallel writer agents on one Spec / one integration branch: who does it, with which mechanisms, with what results

Research date: 2026-10-05. Scope: public first-hand sources, 2025-2026. Facts only; no recommendation.
Builds on `r-software-factories-practices.md` and `r-pocock-delivery-skills.md` (2026-10-01); what those already state is not repeated except where a new detail was read.

## 0. How to read the labels

| Label | Meaning |
|---|---|
| **[V-raw]** | VERIFIED-from-source, verbatim: file fetched raw with `gh api` (GitHub) or a docs page the fetch tool returned verbatim. I read the actual text. |
| **[V-ext]** | VERIFIED-from-source, via extraction: the original page was fetched, but the tool returned a model-made extraction, not the verbatim text. Numbers and quotes are as the extractor returned them. |
| **[S]** | SECONDARY: third-party account or search-result summary only. |

Quotes are under 15 words. Everything else is paraphrase.

---

## 1. Sources

| # | Source | URL | Date | Label |
|---|---|---|---|---|
| 1 | CooperBench paper (Khatua, Zhu, ... Yang; Stanford) | https://arxiv.org/abs/2601.13295 , HTML v2 https://arxiv.org/html/2601.13295v2 | 2026-01-19, rev. 2026-01-26 | [V-ext], two passes |
| 2 | Stanford HAI article on CooperBench | https://hai.stanford.edu/news/ai-coding-agents-fail-at-teamwork | 2026-06-01 | [V-ext] |
| 3 | Cursor, "Scaling long-running autonomous coding" | https://cursor.com/blog/scaling-agents | 2026-01-14 | [V-ext] |
| 4 | Cursor, "Towards self-driving codebases" | https://cursor.com/blog/self-driving-codebases | 2026-02-05 | [V-ext] |
| 5 | Anthropic, "Building a C compiler with a team of parallel Claudes" | https://www.anthropic.com/engineering/building-c-compiler | 2026-02-05 | [V-ext] |
| 6 | Claude Code docs, "Orchestrate teams of Claude Code sessions" (agent teams) | https://code.claude.com/docs/en/agent-teams | living, read 2026-10-05 | [V-raw] |
| 7 | Claude Code docs, "Run agents in parallel" | https://code.claude.com/docs/en/agents | living | [V-raw] |
| 8 | Claude Code docs, "Run parallel sessions with worktrees" | https://code.claude.com/docs/en/worktrees | living | [V-raw] |
| 9 | Cognition, "Multi-agents: what's actually working" | https://cognition.com/blog/multi-agents-working | 2026-04-22 | [V-ext] |
| 10 | Cognition, "Devin can now manage Devins" | https://cognition.com/blog/devin-can-now-manage-devins | 2026-03-19 | [V-ext] |
| 11 | Factory, "Introducing Missions" | https://factory.com/news/missions | 2026-02-26 | [V-ext] |
| 12 | Factory docs, Missions | https://docs.factory.com/cli/features/missions | living | [V-ext] |
| 13 | OpenAI, "Harness engineering" | https://openai.com/index/harness-engineering/ (via reader proxy) | 2026-02-11 | [V-ext] |
| 14 | OpenAI Symphony `SPEC.md` at `be10a1b` | https://github.com/openai/symphony/blob/main/SPEC.md | HEAD 2026-09-15 | [V-raw] for the lines grepped, [V-ext] for the rest |
| 15 | Gas Town docs at `649b832`: `docs/concepts/integration-branches.md`, `docs/concepts/polecat-lifecycle.md`, `docs/design/convoy/stage-launch/prd.md`, `docs/design/convoy/mountain-eater.md`, `internal/formula/formulas/mol-refinery-patrol.formula.toml` | https://github.com/gastownhall/gastown | HEAD 2026-07-23 | [V-raw] |
| 16 | Gas City at `aa8afe8`: `engdocs/design/convoy-first-formulas-and-drain-v0.md`, `examples/lifecycle/.../refinery|polecat/prompt.template.md` | https://github.com/gastownhall/gascity | HEAD 2026-10-05 | [V-raw] |
| 17 | Yegge, "Welcome to Gas Town" | https://steve-yegge.medium.com/welcome-to-gas-town-4f25ee16dd04 (via reader proxy) | 2026-01-01 | [V-ext] |
| 18 | Yegge, "Gas Town: from Clown Show to v1.0" | https://steve-yegge.medium.com/gas-town-from-clown-show-to-v1-0-c239d9a407ec (via reader proxy) | 2026-04-03 | [V-ext]; contains nothing on parallel writes (see 2.2) |
| 19 | Pocock `implement-spec` SKILL.md + docs page | `mattpocock/skills` at `d81f3a1` | 2026-09-29 | [V-raw] in the prior report, not re-read |
| 20 | Pocock Sandcastle `parallel-planner-with-review`: `plan-prompt.md`, `merge-prompt.md`, `main.mts` at `e99f832` | https://github.com/mattpocock/sandcastle/tree/main/src/templates/parallel-planner-with-review | 2026-06-29 | [V-raw] |
| 21 | GitHub Spec Kit at `ae5ade7`: `templates/tasks-template.md`, `templates/commands/tasks.md`, `templates/commands/implement.md` | https://github.com/github/spec-kit | HEAD 2026-10-03 | [V-raw] for the grepped lines |
| 22 | Kiro docs, Specs; changelog IDE 0.12 | https://kiro.dev/docs/specs/ ; https://kiro.dev/changelog/ide/0-12/ | living; 2026-05-06 | [V-ext] |
| 23 | AgenticFlict (Ogenrwot, Businge; AIware 2026) | https://arxiv.org/abs/2604.03551 | 2026-04-04 | [V-ext], abstract only |
| 24 | Claim Plane (Nikolaev) | https://arxiv.org/abs/2607.21909 | 2026-07-24 | [V-ext], abstract only |
| 25 | Kiro "shared files flagged as dependent" | byteiota.com summary of Kiro 0.12 | 2026 | [S] |
| 26 | Augment Code guides on worktrees / multi-agent workspace | augmentcode.com/guides/... | 2026 | [S] (search summary; vendor guide) |

---

## 2. Per team / tool: what runs in parallel, by which mechanism, under which stated condition

### 2.1 Cursor (hundreds of writers, one branch)
- Tried and abandoned [V-ext, #3]: (1) flat peers with **file locks** — agents held locks too long or forgot to release; "Twenty agents would slow down to the effective throughput of two or three"; (2) **optimistic concurrency** (write fails if the file changed since read) — more robust, but agents became risk-averse and made small safe changes; work churned.
- Kept [V-ext, #3, #4]: root planner owns the whole scope and writes no code; recursive sub-planners own a slice; **workers do not coordinate with each other**, each on its own copy of the repo, unaware of the others; each returns a **handoff** (what was done plus concerns, deviations, findings) to its planner, which re-plans. A judge decides whether to continue.
- Conflicts [V-ext, #4]: not prevented. Several agents do touch the same file or refactor the same code; the claim is that the system converges and settles over a short period. The dedicated **integrator** was removed: with hundreds of workers one gate was "an obvious bottleneck".
- Accepted cost [V-ext, #4]: some error rate on the shared branch; an agent periodically snapshots and does a fix-up pass to produce a **"green" branch** for release.
- Numbers [V-ext, #3, #4]: peak "~1,000 commits per hour" over a week; browser project over 1M lines across 1,000 files. No rework rate, no conflict rate, no success rate per task is published. External assessment of the result (CI failure rate, bloat) is [S], in the prior report.
- Stated conditions [V-ext]: role separation; model choice per role; constraints rather than checklists in prompts; one large VM; build tooling that tolerates many parallel compilations. Also stated: rigid up-front planning failed because the path through a large project is ambiguous.
- Scale note: every figure is for hundreds of agents on greenfield projects. Nothing published for 2-5 agents on one feature. The "20 agents at 2-3" figure describes the lock design that was thrown away, not the final design.

### 2.2 Gas Town / Gas City (polecats + Refinery)
- Mechanism for **which tickets run together** [V-raw, #15 stage-launch PRD]: waves computed from `blocks` / `conditional-blocks` / `waits-for` edges by topological sort (Kahn). "Wave 1 = all tasks with no unsatisfied" blocking deps; tasks not reachable by a blocking chain go to Wave 1 ("maximum parallelism"). **There is no file-overlap or module-overlap analysis**: concurrency is decided only by the edges the planner wrote. The PRD lists as a known user problem that tasks "will try to run in parallel when they should be serialized". Wave computation is display-only; runtime dispatch re-checks blockers each cycle.
- Isolation [V-raw, #15]: one worktree per polecat.
- **Integration branch per epic** [V-raw, #15 integration-branches.md]: polecats spawn their worktree **from the integration branch**, so each "starts with sibling work already present" (work that has already merged, not work in flight); the Refinery merges child MRs into `integration/<epic>` instead of main; when all children are closed it lands as one `--no-ff` merge commit, after running tests on the merged result under a file lock. Stated benefit: "CI on main ... Runs once on combined work"; cross-child dependencies stop depending on merge order.
- **Refinery** [V-raw, #15 refinery formula]: merges polecat branches "one at a time without rewriting submitted heads". Steps: merge rehearsal; on textual conflict, abort the merge, record metadata, **create a conflict-resolution task for a polecat** and re-queue the MR; otherwise run the rig's configured pipeline (setup, typecheck, lint, test, build) on the merged result; then push. A "quality-review" step on the merge diff exists but is "measurement-only": it does "NOT gate merges".
- Polecat side [V-raw, #15 polecat-lifecycle.md]: `gt done` pushes the branch and submits an MR; the polecat session dies. "If rebase fails, Refinery creates a conflict-resolution task". The author of the conflicting change is therefore not the one who resolves it, and has no say afterwards.
- Stalls [V-raw, #15 mountain-eater.md]: users report large epics stalled around 40%; root cause given: the feeder is mechanical and cannot see "a subtle blocking condition ... outside the dep graph". Design answer: skip an issue after 3 polecat failures, let work flow around it, escalate.
- Yegge's own account [V-ext, #17]: the Refinery exists because workers otherwise fight over rebasing and merging; during a swarm the baseline can change so much that late workers must "completely reimagine their changes and reimplement them"; "Some bugs get fixed 2 or 3 times"; other fixes get lost; "You can use 20-30 at once". The v1.0 essay [V-ext, #18] is about Beads moving to Dolt and release status; it says nothing about parallel-write mechanisms or rework rates.
- Gas City (the successor engine, `gc`) [V-raw, #16]: the shipped example Refinery "merge[s] them to main with fast-forward"; the convoy/drain v0 design states "Arbitrary parallel shared-context drain is not in v0" — shared drains must be `single_lane = true`, "materialized one item at a time"; separate-context drains may scatter. (Here "context" is the agent's working context for the drain, as far as the document shows; the document does not discuss git integration.) No Gas City document describing integration branches was found in `docs/` or `engdocs/`; the integration-branch feature documented above is Gas Town's (`gt mq integration`).
- No semantic-conflict detection anywhere in these documents: detection is the test pipeline on the merged result.

### 2.3 Matt Pocock
- `implement-spec` (agent-orchestrated) — already in the prior report [V-raw there]: frontier of the ticket graph; implementer per ticket in its own worktree; implementer merges the integration tip into its branch before reporting done; merger subagent per ticket; whole-branch review at the end. His documented limit: worktrees "postpone them to merge time"; remedy he gives for a name collision: add a blocking edge or pin names in the exploration notes.
- Sandcastle planner [V-raw, #20 `plan-prompt.md`]: B is blocked by A if (1) B needs code or infrastructure A introduces; (2) "B and A modify overlapping files or modules, making concurrent work likely to produce merge conflicts"; (3) "B's requirements depend on a decision or API shape that A will establish". Rules 2 and 3 are **planner judgement from issue text**, re-evaluated at each cycle; no declared scope paths, no static analysis. If every issue is blocked, the planner emits the single least-blocked one, so the loop degrades to one writer.
- Sandcastle merger [V-raw, #20 `merge-prompt.md`]: one agent merges all branches of the cycle sequentially; after each conflicted merge it runs `npm run typecheck` and `npm run test` and fixes failures before the next branch. Implementers run via `Promise.allSettled`; a failed pipeline is skipped and re-planned next cycle.
- Measured results: none published for either tool. The only number is a user anecdote (five-ticket feature, review/fix loop about four hours), prior report.

### 2.4 Anthropic
- C compiler [V-ext, #5]: 16 agents, each with its own clone, one shared upstream. Task claim = a text file in `current_tasks/`; git's sync makes the second claimant pick something else. Cycle: work, pull, merge others' changes, push, remove lock. "Merge conflicts are frequent, but Claude is smart enough to figure that out." Parallelism broke on a monolithic target: "Every agent would hit the same bug" and overwrote each other; it was restored by a harness that used GCC as oracle so each agent got a different failing file. Separate agents for dedup, performance, design critique, docs. About 2,000 sessions, about $20k, 100k lines, two weeks. Stated limit: new features frequently broke existing ones.
- Agent teams docs [V-raw, #6]: experimental, off by default. Shared task list with dependencies ("a pending task with unresolved dependencies cannot be claimed"); claims use file locking. Teammates are **not** isolated in worktrees [V-raw, #7]. Guidance: "Two teammates editing the same file leads to overwrites"; each teammate should own a different set of files. "For sequential tasks, same-file edits, or work with many dependencies, a single session or subagents are more effective." Size: "Start with 3-5 teammates"; "Three focused teammates often outperform five scattered ones"; 5-6 tasks per teammate; coordination overhead and token cost grow with team size. Newcomers are told to start with tasks that "don't require writing code" because parallel implementation brings coordination challenges. Hooks `TaskCompleted` / `TeammateIdle` can block completion (exit code 2) as quality gates.
- Worktrees docs [V-raw, #8]: worktrees "isolate file edits" only. Subagent worktrees branch from the repository's **default branch** unless `worktree.baseRef` is `"head"`; `baseRef` cannot be a named branch. A worktree is a fresh checkout: gitignored files are absent unless listed in `.worktreeinclude`. The page gives no guidance on merging parallel work back. `/batch` [V-raw, #7] splits one large change into "5 to 30 worktree-isolated subagents" (elsewhere on the page: each publishes its own change/PR).
- No 2026 Anthropic post was found that reports results for parallel writers on one feature of a product codebase.

### 2.5 OpenAI
- Harness engineering [V-ext, #13]: app bootable per worktree, one isolated instance (with its own logs/metrics) per change; short-lived PRs, "minimal blocking merge gates", agents often squash-merge their own PRs; about 1,500 PRs with three engineers, "3.5 PRs per engineer per day". Consistency across concurrent agents is held by **mechanical enforcement** (custom linters, structural tests), by preferring "shared utility packages over hand-rolled helpers", and by background agents that scan for deviations and open refactoring PRs. Each PR targets main independently; this is not a one-Spec-one-branch model. No conflict or rework rate published.
- Symphony SPEC [V-raw, #14 lines 187-194, 1278]: `blocked_by` is "Best-effort provider metadata"; adapters must not invent blocker semantics; eligibility comes from an adapter-specific `dispatchable`. [V-ext]: global `max_concurrent_agents` (default 10) and per-state caps; one workspace per issue; no mechanism addresses two concurrent issues touching the same files; integration is left to the workflow prompt and the agent.

### 2.6 Factory Missions
- [V-ext, #11]: milestones are sequential, each closed by a validation phase where workers "run tests, check for regressions, and verify that everything integrates". Parallelism is used "within features and during validation", where coordination overhead is low. Reason given against broad parallelism: "Agents conflict, duplicate work, and drift without structure". Numbers are about duration and cost only (median mission 2 h; 14% over 24 h; 12x the tokens of a normal session).
- [V-ext, #11, #12]: both the launch post and the docs list as an open question whether parallelisation produces better results than sequential execution.
- Not stated in either page: worker isolation mechanism, or what happens when one worker's discovery affects another feature.

### 2.7 Cognition / Devin
- [V-ext, #9]: parallel agents make implicit choices about style, edge cases and code patterns that conflict; "most multi-agent setups in the world are limited to 'readonly' subagents"; systems work best "when writes stay single-threaded" and extra agents contribute intelligence rather than actions. Open problem named: "How does a child agent surface a discovery that should change its siblings' work?" Managers also wrongly assume children share their state, and over-prescribe.
- [V-ext, #10]: managed Devins each run in their own VM; the coordinator scopes, assigns, monitors, "resolves any conflicts, and compiles the results". Example uses are independent and repetitive: QA per page, migrations, audits across services, component conversions ("10 at a time"). The post does not say whether children's code lands as one PR or several, nor how conflicts are resolved.
- Reading the two together: Cognition ships parallel children for separable work across PRs or services and still describes same-feature parallel writing as not practical. That juxtaposition is mine; neither post states it in one sentence.

### 2.8 Kiro
- [V-ext, #22]: "Run all Tasks" builds a dependency graph from `tasks.md`; Wave 1 = tasks with no dependencies, run concurrently; waves run sequentially; each task in "its own isolated context". Claim: for specs with 4+ independent tasks, "up to 4x" shorter execution. Released 2026-05-06.
- [S, #25]: tasks that write to shared files, call the same endpoints or validate overlapping state are flagged dependent. Not found in the docs pages I could fetch.
- Not stated: whether parallel tasks share one working tree; how results are integrated; any conflict or rework figure.

### 2.9 GitHub Spec Kit
- Rule [V-raw, #21 `commands/tasks.md` line 161]: `[P]` is included "ONLY if task is parallelizable (different files, no dependencies on incomplete tasks)". Each task line names its file path. `commands/implement.md` line 153: "Tasks affecting the same files must run sequentially"; a failing non-parallel task halts; failing `[P]` tasks are reported while the others continue.
- Ordering [V-ext, #21 tasks-template]: Setup, then **Foundational, which blocks all user stories**, then user stories (parallel or by priority), then polish. The template warns against "same file conflicts, cross-story dependencies".
- The rule is file-level only; it does not address two tasks in different files that must agree on a name or a shape, except through the Foundational phase and contract tests written first.

### 2.10 Others checked
- Amp manual: the page fetched held no subagent content. Not verified.
- Conductor, Claude Squad, vibe-kanban, Zed, Augment: only vendor guides and search summaries surfaced [S]; they describe worktree-per-agent plus sequential merge and state that semantic conflicts survive file isolation. No first-hand measured report found.

---

## 3. Mechanisms catalogue

Evidence strength: **Strong** = 3+ independent first-hand sources describe using it; **Medium** = 2, or 1 plus research; **Weak** = one source, or stated without any reported outcome.

| # | Mechanism | Who | What it prevents | What it does not prevent | Evidence |
|---|---|---|---|---|---|
| a1 | Concurrency decided by explicit blocking edges only (frontier / waves by topological sort) | Gas Town stage-launch; Kiro waves; Pocock implement-spec frontier; Claude agent-teams task deps; Symphony (weaker: best-effort) | Starting a ticket before its prerequisite exists | Two unblocked tickets touching the same file, name or shape; Gas Town's PRD and mountain-eater doc name this gap | Strong (as practice); no outcome data |
| a2 | File/module overlap treated as a blocking edge | Sandcastle planner (judgement); Spec Kit `[P]` (declared file path per task); Kiro [S]; Claude agent-teams guidance (own different files) | Textual merge conflicts; overwrites | Semantic disagreement across different files | Strong (as rule); CooperBench shows the spatial part is the easy part |
| a3 | "Decision or API shape" dependency treated as a blocking edge | Sandcastle planner rule 3; Pocock docs (add an edge, or pin names in notes) | Two tickets inventing the same concept twice | Depends on the planner foreseeing it from ticket text | Weak (one author; no outcome data) |
| a4 | Foundation first, then fan-out | Spec Kit Foundational phase "BLOCKS all stories"; Pocock "prefactoring ... first"; Anthropic C compiler (parallelism only after an oracle made slices independent); Gas Town waves from the integration branch | Siblings each building their own base | Later cross-story coupling | Medium |
| a5 | Contract pinned before parallel work (interfaces, insertion points, names) | CooperBench authors propose "verifiable commitments"; Claim Plane prototype (declared typed resources, fail-closed on undeclared mutation); Spec Kit contract tests first | Divergent architecture, unkept promises | Unknown: Claim Plane's sample is "intentionally too small" (6 pairs; full static admission serialised all 6) | Weak (proposal + feasibility prototype) |
| a6 | Planner owns scope; workers never talk to each other | Cursor; Factory; Devin manager | Duplicate assignment; coordination chatter | Overlapping edits (Cursor accepts them) | Medium |
| a7 | Task claim by lock | Anthropic C compiler (`current_tasks/` file); Claude agent teams (file-locked claim); Cursor file locks (abandoned) | Two agents taking the same task | File-level locks throttled Cursor to 2-3 effective agents; task-level claims did not | Medium |
| b1 | Worktree / clone / VM per writer | All of the above except Claude agent teams | Silent overwrite while working | Anything at merge time ("postpone", Pocock); skipped tests from missing gitignored fixtures (Pocock; Claude docs `.worktreeinclude`) | Strong |
| b2 | New writer branches from the integration tip, not from main | Gas Town integration branches; Pocock implement-spec (checks worktree base) | Re-doing or contradicting merged sibling work | In-flight sibling work | Medium |
| c1 | Serial merge queue: one merge at a time, checks on the merged result | Gas Town Refinery; Sandcastle merger; Pocock merger subagent | Broken integration tip; textual conflicts reaching the branch unnoticed | Semantic conflicts the tests do not cover | Strong |
| c2 | Writer merges the integration tip into its own branch before "done" | Pocock implement-spec; Anthropic C compiler (pull, merge, push by the author) | Conflict resolution by an agent that lacks the ticket's context | Races between two writers finishing together (still need c1) | Medium |
| c3 | Conflict sent back as a new task to a worker | Gas Town Refinery (conflict-resolution task; branch preserved) | Merge agent guessing | Yegge reports late workers re-implementing from scratch | Medium (one system, candidly reported) |
| c4 | No gate; accept breakage; periodic reconciled green branch | Cursor; OpenAI (minimal gates, fix-forward, cleanup agents) | Gate as bottleneck at hundreds of agents | A coherent tip at any given moment | Medium; scale-specific |
| c5 | Whole-outcome checks once on the combined branch before landing | Gas Town `integration land` (tests under lock); Factory milestone validation; Pocock end-of-run review | Per-ticket green hiding a broken whole | — | Strong |
| d1 | Mechanical invariants (linters, structural tests, shared utility packages) | OpenAI; (prior report: Stripe, Spotify) | Style and layering drift between concurrent writers; hand-rolled duplicate helpers | Conflicting product decisions | Strong |
| d2 | Dedicated dedup / cleanup / design-critique agents after the fact | Anthropic C compiler; OpenAI background tasks; Cursor green-branch fix-up | Accumulated duplication | Cost of producing it first | Medium |
| d3 | Fresh-context review of the whole integration branch | Pocock; Gas Town quality-review (measurement-only, does not gate) | Some naming and duplication issues | No convergence guarantee (Pocock) | Medium |
| d4 | Tests on the merged result as the only semantic detector | Gas Town; Sandcastle; CooperBench evaluation method | Regressions covered by tests | Whatever the tests do not assert | Strong (it is what everyone actually has) |
| e1 | Worker handoff notes to its planner, which re-plans siblings | Cursor | Discovery lost with the worker's context | Siblings already running keep going | Weak (one source) |
| e2 | Add an edge / pin the name in shared exploration notes after a collision | Pocock docs | Recurrence in the same run | First occurrence | Weak |
| e3 | Sibling discovery propagation | Cognition lists it as unsolved; Factory silent; Gas Town: none (polecat dies at `gt done`) | — | — | Open problem (stated by Cognition) |

---

## 4. Measured results

### 4.1 CooperBench (the only controlled measurement found) [V-ext, #1]
- Size: 652 tasks, 12 repositories, 4 languages (Python, TypeScript, Go, Rust).
- Setup: two agents, one feature each, features "can be implemented independently but may conflict"; isolated Docker workspaces; **no access to each other's code**, only an asynchronous message tool; patches merged with `git merge-file`, then a small trained model resolves trivial conflicts; expert tests on the merged result. Solo baseline: **one agent implements both features in one context**.
- Success, Solo vs Coop: GPT-5 50.6% vs 32.5%; Claude Sonnet 4.5 46.9% vs 28.3%; MiniMax-M2 37.4% vs 17.1%; Qwen3-Coder-30B 23.6% vs 14.8%; Qwen3-Instruct 10.6% vs 7.2%. Abstract: on average "30% lower success rates when working together". Retention about 59% on average. (The abstract's other headline, about 25% in pairs and "around 50% lower" than solo for the two best models, is a different cut of the same data; the two phrasings coexist in the paper.)
- Communication: with vs without messaging, the difference in success is "not statistically significant". Messaging does reduce merge conflicts, but that gain disappears in final success: it fixes the spatial problem, not the semantic one. Up to 20% of steps were spent communicating.
- "Having a Plan message in the very first turn nearly halves the conflict rate (29.4% vs 51.5%)" — conflict rate, not success rate.
- More agents: on a 46-task subset, 68.6% with 2 agents, 46.5% with 3, 30.0% with 4. The extraction did not make clear which metric and model this is; treat the trend as verified and the absolute values as unverified.
- Failure symptoms: work overlap 33.2%, divergent architecture 29.7%, repetition 14.7%, unresponsiveness 8.7%. Root causes: expectation failures 42% (wrong model of what the partner is doing), commitment failures 32% (promise not kept), communication failures 26%.
- What successful pairs did: explicit role division with mutual confirmation; resource division down to files and line ranges; negotiation ending in one fully specified plan before acting.
- **Not tested** in the paper: a pre-written shared plan, pre-assigned file ownership, sequential execution with the second agent seeing the first's merged code, or a planner above the two agents. So the paper measures unstructured peer pairs with blind workspaces; it does not measure the orchestrated designs of section 2. HAI article [V-ext, #2] adds the practitioner reading: contract-like agreements, verification that commitments were kept, periodic integration checks.

### 4.2 Other numbers
- AgenticFlict [V-ext, #23]: of 107k+ agent-authored PRs replayed through merge simulation, 27.67% had textual merge conflicts (142k PRs, 59k repos; rate varies by agent). These are PRs against moving human repositories, not sibling agents on one Spec.
- Cursor: throughput only (section 2.1). Anthropic C compiler: cost and size only; "frequent" conflicts, unquantified. OpenAI: PR counts only. Factory: durations only. Kiro: "up to 4x" vendor claim. Gas Town, Pocock: no numbers.
- Small scale (2-5 writers) specifically: CooperBench (2, 3, 4 agents) is the only measurement. Claude agent-teams docs give sizing guidance (3-5) without data. No published throughput-vs-agent-count curve for an orchestrated small team exists in the sources read.

---

## 5. Preconditions the sources state for parallel writes to pay off

| Precondition | Stated by |
|---|---|
| Work is decomposable into slices that fail independently; a monolithic goal makes all agents collide on the same bug | Anthropic C compiler [V-ext] |
| A strong, fast test oracle that can judge the merged result | Anthropic C compiler; Gas Town Refinery pipeline; Sandcastle merger [V-raw] |
| A foundation that exists before fan-out | Spec Kit Foundational phase [V-raw/V-ext]; Gas Town waves on the integration branch [V-raw] |
| Tasks that own different files | Spec Kit `[P]` [V-raw]; Claude agent teams [V-raw]; Sandcastle planner [V-raw] |
| Dependencies and shared decisions made explicit as edges before dispatch | Gas Town PRD; Sandcastle rule 3; Pocock docs [V-raw] |
| Mechanical enforcement of conventions so writers converge without talking | OpenAI [V-ext] |
| Acceptance of waste (duplicate fixes, re-implementation, some red on the branch) | Yegge; Cursor [V-ext] |
| Spend is not a constraint | Yegge; Claude docs (tokens scale linearly with teammates); Factory (12x tokens) |

On small versus large scale:
- The bottleneck argument against a serial merge gate is made only at hundreds of workers (Cursor). The systems built for a handful to a few dozen writers (Gas Town, Sandcastle, implement-spec) all keep a serial merger.
- Claude docs: start at 3-5, fewer focused beats more scattered, and single session or subagents for same-file or dependency-heavy work.
- CooperBench: success falls monotonically from 2 to 4 unstructured agents.
- Factory and Cognition, both operating at small agent counts per task, keep feature writes serial and say the value of parallelism is unproven or impractical for coupled work.

---

## 6. Convergent, contested, not verified

### Convergent (3+ independent sources)
1. Isolation per writer (worktree, clone or VM) is universal, and by itself only moves collisions to merge time.
2. Whoever parallelises below "hundreds" keeps integration serial: one merge at a time, checks run on the merged result (Gas Town, Sandcastle, implement-spec; Anthropic's push-after-pull is the same ordering without a dedicated agent).
3. Concurrency is decided before dispatch from a dependency graph; the common rule is "different files and no unmet dependency" (Spec Kit, Sandcastle, Kiro, Claude agent teams).
4. Textual conflicts are the tractable part; semantic conflicts (names, shapes, duplicated helpers, divergent architecture) are what remains. CooperBench measures it (communication reduces conflicts, not failures); Pocock, Cognition, Yegge and Factory report it.
5. Nobody has a dedicated detector for semantic conflicts. What exists: tests on the merged branch, mechanical lint/structure rules, a whole-branch review, and after-the-fact dedup agents.
6. A foundation or shared base lands before siblings fan out.
7. Parallel writing costs more tokens and produces rework; the sources that do it say so.

### Contested
- **Whether same-feature parallel writers are worth it at all**: Cognition (no), Factory (mostly serial, value unproven), CooperBench (unstructured pairs lose 30-50%) versus Gas Town, Pocock, Kiro, Spec Kit (yes, with a graph and a merge step) and Cursor/Anthropic (yes, at large scale, with waste accepted). The pro side has published no success or rework rates.
- **Who resolves a conflict**: the author before reporting done (Pocock, Anthropic) versus a separate merge agent (Sandcastle) versus a new task for another worker (Gas Town) versus nobody in particular (Cursor convergence).
- **Gate or no gate**: serial gate with tests (Gas Town, Sandcastle) versus accepted breakage plus periodic green branch (Cursor, OpenAI).
- **How overlap is known**: declared file path per task (Spec Kit) versus planner judgement per cycle (Sandcastle) versus not considered, edges only (Gas Town).
- **Agent-to-agent messaging**: Claude agent teams build on it; Cursor removed worker-to-worker coordination; CooperBench finds no significant benefit.

### Not verified
- CooperBench: read through extraction of the HTML, not the PDF. The metric and model behind the 68.6 / 46.5 / 30.0 scaling figures are unclear. The relation between the "30% lower" and "around 50% lower" headlines was not reconciled against the tables by me.
- Cursor: no rework, conflict or per-task success rate is published; the convergence claim is theirs alone. Whether the "20 agents at 2-3" figure has any bearing on designs without file locks is not stated.
- Kiro: the rule "shared files or endpoints make tasks dependent" is [S]; working-tree sharing and integration behaviour are undocumented in the pages fetched; "up to 4x" is a vendor claim.
- Devin managed children: whether children write to one branch, how conflicts are resolved, and any outcome numbers.
- Factory Missions: isolation mechanism, what "parallelizes within features" concretely means, and handling of cross-feature discoveries.
- Gas Town: no figures for conflict-task frequency, re-implementation rate or stalled-convoy rate; the 40% stall is an anecdote in a design doc. Gas Town docs were read at `649b832` (2026-07-23); behaviour of Gas City `gc` 1.4.1 for integration branches and refinery was **not** checked against the running factory or the `gc` source, only against two example prompts and one design doc.
- Yegge "From Clown Show to v1.0": fetched through a reader proxy and extracted; the extraction found nothing on parallel writes. A paywalled remainder cannot be excluded.
- Symphony: only the `blocked_by` lines were read verbatim; the rest is extraction.
- Pocock `implement-spec`: not re-read today; state taken from the 2026-10-01 report (`d81f3a1`).
- Amp, Zed, Augment, Conductor, Claude Squad, vibe-kanban, HumanLayer: no first-hand mechanism-plus-result report found; nothing from them is used above except as [S].
- Claim Plane and AgenticFlict: abstracts only.
- No source measures the specific configuration "2-4 fresh-context writers, ticket graph with edges, one integration branch, serial merge with tests". Its expected rework rate is unknown from public data.
