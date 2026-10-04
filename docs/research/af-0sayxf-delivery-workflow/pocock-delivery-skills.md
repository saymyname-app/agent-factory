# Matt Pocock: what he prescribes for the implementation / delivery side

Research date: 2026-10-01. Method: fresh `git clone` of both repos, read at HEAD; aihero.dev pages fetched with curl; talk transcript read on ai.engineer; `gh` read-only for issues/PRs. Nothing was posted anywhere.

Claim labels: **[V]** = VERIFIED-FROM-SOURCE (I read the primary text). **[S]** = SECONDARY/UNVERIFIED (summary page, third-party report, or inference).

Link base for the skills repo: `https://github.com/mattpocock/skills/blob/d81f3a1/` (abbreviated `SK/` below).

---

## 0. State of the sources

| Source | Current state | Label |
|---|---|---|
| `mattpocock/skills` `main` | HEAD = `d81f3a183412e71a5b1e84ca21bc1a35eea03a60`, 2026-09-29 14:37 (Paris), "Merge pull request #1120 from mattpocock/release/v1.3". **Unchanged since the previous read.** No commit on `main` after it. | [V] |
| Version number | `package.json` on `main` still says `1.2.3`; `CHANGELOG.md` top entry is 1.2.3. The 1.3.0 bump lives on the bot branch `changeset-release/main` (`984a2c0`, 2026-09-29 14:38 Paris), not merged. So "v1.3" content is on `main`, the 1.3.0 tag/changelog is not cut yet. | [V] |
| Pending Matt PR | #1121 (2026-09-24) "ask-matt: route post-bug reflection to /retro" - open, not implementation-relevant. | [V] |
| `mattpocock/sandcastle` `main` | HEAD = `e99f832`, 2026-06-29 22:15 (Paris), tag `v0.12.0`. GitHub `pushed_at` = 2026-06-29: **no push to any branch for three months.** | [V] |
| Talk | "Full Walkthrough: Workflow for AI Coding", AI Engineer Europe 2026, 1:36:30, transcript at https://ai.engineer/talks/-QFHIoCo-Ko-ai-coding-workflow (machine transcript; exact date not on page). | [V] transcript text |
| aihero.dev | AI Coding Dictionary entries (undated pages), "My 7 Phases Of AI Development" (2026-03-16), skills changelog post (2026-05-11). The `aihero.dev/skills-*` docs pages are the repo's `docs/engineering/*.md` (the `skills-implement-spec` URL returned 404 today; the repo file is the source). | [V] |
| X / newsletter / YouTube since mid-2026 | Not readable (X returned HTTP 402). One X post about trying `/implement-spec` surfaced only as a search snippet. | [S] |

Changes between `c55ee46` (2026-09-18) and `d81f3a1` on the implementation side [V] (`git diff --stat c55ee46 d81f3a1 -- skills`):
- `implement-spec`, `pr`, `retro` moved from `in-progress/` to `engineering/` (they now ship in the plugin and get docs pages).
- `implement-spec` text changed: goal is now "a single **integration branch**" instead of "a PR"; draft PR only if the tracker closes work through PRs or the user asks, and only after the first merge; implementers now explicitly "call the Skill tool with `tdd`", check their worktree base, and merge the integration tip before reporting done; adds the tracker precondition.
- `resolving-merge-conflicts` removed ("nothing replaces it").
- `retro` added to the end of the main flow in `ask-matt`; `CONTEXT.md` renamed `GLOSSARY.md` everywhere.
- `implement`, `tdd` (one-word rename), `code-review`, `to-tickets`, `prototype`: no substantive change.

---

## 1. Implementation-side skills at HEAD

Invocation rule [V] (`SK/.agents/invocation.md`): user-invoked = `disable-model-invocation: true`; "A user-invoked skill may invoke model-invoked skills, but it can never reach another user-invoked skill."

| Skill | Invocation | File |
|---|---|---|
| `implement` | **user-only** | `SK/skills/engineering/implement/SKILL.md` |
| `implement-spec` | **user-only** | `SK/skills/engineering/implement-spec/SKILL.md` |
| `to-spec`, `to-tickets` | **user-only** | `SK/skills/engineering/to-spec/SKILL.md`, `.../to-tickets/SKILL.md` |
| `retro` | **user-only** | `SK/skills/engineering/retro/SKILL.md` |
| `triage`, `wayfinder`, `improve-codebase-architecture`, `ask-matt`, `grill-with-docs`, `setup-matt-pocock-skills` | **user-only** | same tree |
| `tdd`, `code-review`, `pr`, `prototype`, `codebase-design`, `diagnosing-bugs`, `domain-modeling`, `research`, `wizard` | model-invoked | same tree |
| In-progress (beta, not in plugin): `loop-me`, `setup-ts-deep-modules`, `claude-handoff`, three writing skills | user-only | `SK/skills/in-progress/` |

Consequence for an autonomous factory [V]: every orchestrating step (`implement`, `implement-spec`, `to-tickets`, `retro`) is designed to be typed by a human. `docs/engineering/implement.md`: "that is an instruction to you, not something the agent will do unprompted."

**There is no `qa`, `design`, `ui`, `frontend`, `integrate`, `verify` or `deploy` skill at HEAD** [V] (file listing). The old `qa` skill was removed on 2026-08-05 (`c66bdee`), CHANGELOG: "`qa` → `/triage` and `/to-tickets`".

### 1.1 `/implement` (whole skill is 5 sentences) [V]
`SK/skills/engineering/implement/SKILL.md`:
- "Use /tdd where possible, at pre-agreed seams."
- "Run typechecking regularly, single test files regularly, and the full test suite once at the end."
- "Once done, use /code-review to review the work."
- "Commit your work to the current branch."

Documented behaviour and gaps [V] (`SK/docs/engineering/implement.md`):
- One run = one ticket = one fresh context; "It never reopens the plan. There is no interview, no clarifying round".
- "`implement` has no completion step." It does not close the ticket, does not tick acceptance criteria, and "does not act on the findings `code-review` produced".
- Review-order bug, unfixed: `code-review` diffs `<fixed-point>...HEAD`, which excludes uncommitted work, but `implement` runs it before committing.
- "Pre-agreed" seams are "the skill's weakest joint": if seams are agreed nowhere, "the run quietly becomes 'just write the code'".
- It "trusts" the planning skills: "a horizontally-layered ticket gets built as written."
- No PR mode; it commits straight to the current branch.

### 1.2 `/implement-spec` [V]
`SK/skills/engineering/implement-spec/SKILL.md`, nine steps (paraphrased, key quotes):
1. Read spec + tickets as a **task graph** with a **frontier**.
2. Optional exploration subagent writing notes outside the repo.
3. Create the integration branch; draft PR only if the tracker closes work through PRs or the user asks.
4. Implementer subagents, "each in its own worktree on its own branch"; each "calls the Skill tool with `tdd`" and "merges the integration branch tip into its own branch before reporting done".
5. "merge its work to the integration branch with a **merger subagent**."
6. Recompute the frontier, start more implementers.
7. "Once all tickets are complete, call the Skill tool with `code-review` on the integration branch. Fix all issues raised by the code review in a single **implementer subagent**."
8. Mark PR ready, or resolve tickets and "report the integration branch".
9. Clean up worktrees.

Also: "Communication to and from subagents should be sparse. Communicate primarily through **context pointers**".

What it does not contain [V]: no instruction to run the app, no build/typecheck/full-suite step on the integration branch (only the merger's fast-forward and the review), no stop condition after the fix pass, no QA step, no escalation rule.

Known limits, stated in his own docs page [V] (`SK/docs/engineering/implement-spec.md`):
- "the run's output is a draft that the review finishes, not something to ship on its own."
- The skill "doesn't yet say when to stop after that fix"; a user reported a five-ticket feature where the review/fix loop "took roughly four hours".
- "Worktrees don't remove collisions; they postpone them to merge time." Example: two tickets named the same string `blockedSince` and `blockedOn`. Remedy: add a blocking edge or pin names in exploration notes.
- GitHub frontier goes stale mid-run (blocked-by count only drops on close).
- A test can skip silently in a worktree (gitignored fixtures/DB) and "reported green".
- Seams: "There is still no step where seams get agreed interactively".
- vs Sandcastle: "For work that is truly AFK, a deterministic loop (Sandcastle, a shell script, a CI job) is faster, cheaper, and more reliable, because no part of the orchestration can wander off."
- "The price is that you no longer read each ticket's work as it lands; you review the integration branch at the end."

### 1.3 `/tdd` (model-invoked reference, not a driver) [V]
`SK/skills/engineering/tdd/SKILL.md`:
- "Tests verify behavior through public interfaces, not implementation details."
- "**Test only at pre-agreed seams.** ... No test is written at an unconfirmed seam."
- Anti-patterns: implementation-coupled, tautological, horizontal slicing ("one test → one implementation → repeat, each test a **tracer bullet**").
- "**Refactoring is not part of the loop.** It belongs to the review stage".

Docs caveats [V] (`SK/docs/engineering/tdd.md`):
- Row "Config, wiring, glue, type annotations, straight CRUD delegation | Nothing here fits well" - "That last row is a real hole" (issue #746, open). **Wiring/glue is explicitly outside what TDD covers.**
- Browser/E2E tests: "Usually not, and the skill will not stop it"; advice is to declare in `CLAUDE.md` that browser tests "are written after the behaviour works".
- Agents sometimes write the implementation first; "No instruction makes an agent comply 100% of the time".
- The docs say `code-review` "checks that only agreed-upon test seams were used". **I could not find that check in `code-review/SKILL.md`** (the Standards and Spec briefs never mention seams). Treat the claim as aspirational. [V that the text is absent]

### 1.4 `/code-review` (model-invoked) [V]
`SK/skills/engineering/code-review/SKILL.md`:
- Two axes, "**parallel sub-agents** so they don't pollute each other's context".
- Fixed point supplied by the user; diff is `git diff <fixed-point>...HEAD`.
- Spec source search order: issue refs in commits → path argument → file under `docs/`, `specs/`, `.scratch/` → ask.
- Standards sources: "Anything in the repo that documents how code should be written, such as `CODING_STANDARDS.md` or `CONTRIBUTING.md`" plus a fixed 12-item Fowler **smell baseline**; "**The repo overrides.**"; "skip anything tooling already enforces".
- Spec brief: "(a) requirements the spec asked for that are missing or partial; (b) behaviour in the diff that wasn't asked for (scope creep); (c) requirements that look implemented but where the implementation looks wrong. Quote the spec line for each finding. Under 400 words."
- "Do **not** merge or rerank findings".

It is a **diff-reading** review. It never runs the code, the tests, or the app [V]. Docs caveats (`SK/docs/engineering/code-review.md`): "Sub-agent output is a hypothesis, not evidence"; "There is no convergence guarantee ... do not run it in a loop until it comes back clean"; known open bug where sub-agents re-invoke the skill ("50-plus agents"); name clash with Claude Code's built-in `/code-review`; "Prefer a fresh" session over the authoring one.

### 1.5 `/pr` (model-invoked, format only) [V]
`SK/skills/engineering/pr/SKILL.md`: body = Summary (smallest visual) / Evidence / Merge Danger.
- "Screenshots are S-tier - when the environment is set up for it and the change is visual."
- "Execution-based evidence is A-tier."
- Merge Danger: "**Door:** <one-way or two-way>" and "**Blast Radius:**".
Docs: it does not open the PR, does not triage review comments, and the door call is a self-report ("Not blindly").

### 1.6 `/retro` (user-only) [V]
`SK/skills/engineering/retro/SKILL.md`: improves the agent's **environment**, not the code; categories: navigation, automated checks, coding standards, global AGENTS.md, tool economy, no-ops, information access. Only proposes; the human picks.
- "a **mechanical** one ... gets a deterministic check, full stop"; "Reserve `CODING_STANDARDS.md` for genuine **judgement calls**".
- "A repo with no **guardrail** ... is itself a finding".
- Information access example: "Teeing dev server logs, readonly access to third-party services."

### 1.7 Others touching delivery [V]
- `/triage` (`SK/skills/engineering/triage/SKILL.md`): state machine for issues **you didn't create**; states `needs-triage`, `needs-info`, `ready-for-agent` ("fully specified, ready for an AFK agent"), `ready-for-human` ("needs human implementation"), `wontfix`. Includes "**Verify the claim.** ... For a bug, reproduce it". Output is an **agent brief** (`AGENT-BRIEF.md`): behavioural, no file paths, "concrete, testable acceptance criteria", explicit out-of-scope.
- `/improve-codebase-architecture`: periodic survey for "deepening opportunities", HTML report, then grilling. README: "once every few days".
- `/codebase-design`: vocabulary (module, interface, depth, seam, adapter, leverage, locality).
- `/diagnosing-bugs`: lists feedback-loop options including "**Headless browser script** (Playwright / Puppeteer) that drives the UI" and a last-resort HITL bash script. This is the **only** place browser automation appears in the skills.
- `setup-ts-deep-modules` (beta): dependency-cruiser rules so packages are reachable only through entry points.

---

## 2. How `to-tickets` slices work

[V] `SK/skills/engineering/to-tickets/SKILL.md`:
- "Each slice cuts a narrow but COMPLETE path through every layer (schema, API, UI, tests): vertical, NOT a horizontal slice of one layer"
- "A completed slice is demoable or verifiable on its own"
- "Each slice is sized to fit in a single fresh context window"
- "Any prefactoring should be done first"
- Ticket template: "**What to build:** the end-to-end behaviour this ticket makes work, from the user's perspective, not a layer-by-layer implementation list."
- Human gate: "Iterate until the user approves the breakdown."
- Published with `ready-for-agent`: "the tickets are agent-grabbable by construction."

**AFK vs HITL on tickets** [V]: the per-slice `Type: HITL / AFK` field existed in the old `to-issues` and was **removed on 2026-06-03** (commit `788b5c3`; the deleted line read "Slices may be 'HITL' or 'AFK'"). In the talk he still shows a ticket "given it a type of AFK" (40:43). At HEAD, HITL/AFK classification survives only (a) on **wayfinder decision tickets** (Research = AFK, Prototype = HITL, Grilling = HITL, Task = either; `SK/skills/engineering/wayfinder/SKILL.md`) and (b) as triage states `ready-for-agent` / `ready-for-human`.

**Integration / wiring / final-assembly ticket type** [V]: **none for feature work.** The only "integrate" ticket in the whole repo is inside the wide-refactor exception: batches "share an integration branch that all block a final integrate-and-verify ticket; green is promised only there." For features, integration is supposed to be a property of every ticket (each one is already end to end), not a ticket of its own.

His own documentation of what goes wrong [V] (`SK/docs/engineering/to-tickets.md`):
- "One team ran a 26-ticket stack sliced by layer ... and got roughly twenty agent runs per closed ticket, about three quarters of them rework." Root cause traced to "the horizontal slicing rather than to the implementations". (Third-party field report relayed by him.)
- "The tickets came out one per layer ... the skill still produces it sometimes." Test: "what can I demo when this is done? A ticket with no answer is a horizontal slice." Some users add a "demo path" line per ticket.
- "The acceptance criteria graded nothing: some passed before any work was done." Check by hand: "name the observation that would show it false, and confirm it fails at the commit the implementer starts from."
- "The skill stops at the artifact, and there is no auto-dispatch mode."

Talk [V transcript]: 45:44 "I want to see some new service being created, and I want a minimal representation of that on the front end."

---

## 3. Prototype after it is chosen; UI fidelity; frontend quality

### 3.1 What happens to the prototype [V]
`SK/skills/engineering/prototype/SKILL.md` rule 6: "Fold any validated decision into the real code, then capture the prototype itself as a **primary source**: commit it to a throwaway branch, out of main, and leave a context pointer to that branch on the implementation issue."

`SK/skills/engineering/prototype/UI.md`:
- Strongly prefers variants mounted **inside the real page** ("real header, real sidebar, real data, real density"), switched by `?variant=`.
- "**Sub-shape A**: fold the winner into the existing page; drop the losing variants and the switcher from main."
- Anti-pattern: "**Promoting the prototype directly to production.** ... Rewrite it properly when you fold it in."
- "The interesting feedback is usually 'I want the header from B with the sidebar from C'".

`SK/docs/engineering/prototype.md`: "Wait, isn't the prototype supposed to be deleted? Not any more." It is kept on a `prototype/<name>` branch, "never merged", with a pointer from the implementation issue.

How the spec/tickets reference it [V]: `to-spec` and `to-tickets` forbid file paths and snippets, with one exception: "if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it". **The exception names logic artefacts only; nothing tells to-spec or to-tickets to carry a UI/visual target** (no screenshot, no variant URL, no layout description requirement).

Dictionary "Prototyping" [V] (https://www.aihero.dev/ai-coding-dictionary/prototyping): "You can build the pieces you're actually evaluating to production quality, so when the decision lands, the component or API you reacted to can transfer into the real codebase. This makes prototyping essential material for the spec to reference."

"My 7 Phases" (2026-03-16) [S, read via summariser]: prototyping early "lets you commit the winning design to your codebase, making it available to agents during implementation."

Net reading [inference, S]: his mechanism for UI fidelity is **front-loading**: the winning UI is folded into the real codebase (on the real route) by a human-in-the-loop session, so later tickets extend existing UI rather than recreate it from prose. A prototype kept only as a reference on a side branch, with tickets written in prose, is exactly the case his flow does not protect.

### 3.2 Does anything verify UI fidelity or check the running app? [V]
No. Across `implement`, `implement-spec`, `tdd`, `code-review`, `pr`, `retro` there is no step that starts the app, opens a browser, takes a screenshot, or compares against a prototype. Mentions of browser tooling in the repo:
- README failure mode #3: "You need the usual tranche of feedback loops: static types, browser access, and automated tests." (stated as a prerequisite of the environment; no skill sets it up)
- `pr`: screenshots as best evidence "when the environment is set up for it".
- `diagnosing-bugs`: Playwright as one feedback-loop option.
- `tdd` docs: browser tests after the behaviour works.
Open user proposals with no maintainer reply [V via `gh`]: #489 "implementation walkthrough / guided QA", #1047 "tickets carry Gherkin scenarios + QA checklist; implement verifies the run before committing", #1124 "choose a verification strategy before /implement reaches for /tdd", #337 "prototype UI decisions have no documentation home", #923 "improve-codebase-architecture can silently break the UI it's refactoring".

### 3.3 What he says about frontend quality with agents [V transcript]
- 1:02:39 "front end is, like, really sensitive to human eyes. You need human eyes looking at the front end all the time".
- 1:02:48-1:03:04 on agent-browser / Playwright MCP: "it's not very good at that yet, and it can't create a nice front end in a mature code base."
- 1:03:16 the answer is prototypes: "Give me three prototypes ... in a throwaway route".
- 1:11:03 "I do find front-end really hard to test here. We're essentially just testing the service."
- Changelog post 2026-05-11 [V] (https://www.aihero.dev/skills/skills-changelog-handoff-prototype-review-and-writing): "you need a human in the loop to apply taste, because AI often can't see what it's building."

---

## 4. How the pieces are supposed to form a working whole

Layered model [V] (dictionary: [automated check](https://www.aihero.dev/ai-coding-dictionary/automated-check), [automated review](https://www.aihero.dev/ai-coding-dictionary/automated-review), [human review](https://www.aihero.dev/ai-coding-dictionary/human-review), [AFK](https://www.aihero.dev/ai-coding-dictionary/afk)):

| Layer | What it catches | His words |
|---|---|---|
| Vertical slices | Integration found early, per ticket | each slice "demoable or verifiable on its own" |
| Automated checks (types, tests, lint, CI) | Mechanical failures | "green checks mean the asserted properties hold, not that the code is right." |
| Integration branch + merger subagent | Textual/merge integration | merges are meant to be fast-forwards |
| Automated review (fresh context, other model) | Judgement-shaped problems in the diff | "treat it as a filter that raises the floor before a human looks, not a gate that replaces one." |
| Human review + human QA at the end | Whether it is the right thing, taste, real behaviour | "AFK doesn't remove human review; it defers all of it to the end" |

"Green != works" in his own demo [V transcript]: 1:12:03 after a green Ralph run, manual QA hits "SQLite error. I don't have the right table."

What human QA looks like [V transcript]:
- 59:27 "the implementation here is really the only AFK bit. We then also need to QA the work and code review the work".
- 1:09:15 because of tracer bullets "we can immediately go and QA it."
- 1:12:35-1:13:32 "it's so important to QA it manually"; "QA is how I ... impose my taste"; teams that automate QA "end up with apps that ... lack taste"; "that's what the QA is for."
- 1:27:23 the human's work "is in QA. And that you can sort of do that AFK, I suppose, but in my experience, you're not gonna get a lot of juice out of it."
- It is a person using the running feature. There is no script, checklist, or skill for it at HEAD.

How findings re-enter the board [V transcript]: 1:34:44 "what the QA phase is for is creating more issues for that Kanban board. So while it's implementing even, you can be QA-ing the stuff and going back, adding more issues". Mechanically at HEAD [V]: the retired `qa` skill (conversational: user describes the problem, agent files durable issues, "Do NOT ask the user to review first") was replaced by `/triage` (for raw reports → agent brief → `ready-for-agent`) and `/to-tickets`. 7-phases article [S]: QA "typically uncovers issues ... resulting in more Kanban tickets and another execution loop."

Order of AI review vs human QA [V transcript 1:05:35]: "you should get it to review its own code before you then QA it."

Unresolved by him [S, ai.engineer summary of 59:27-59:49]: big AFK batches conflict with small reviewable PRs; he states the tension and offers no fix.

Sandcastle `parallel-planner-with-review` template [V] (`https://github.com/mattpocock/sandcastle/tree/e99f832/src/templates/parallel-planner-with-review`):
- Planner (Opus, 1 iteration) builds the dependency graph and emits only unblocked issues; treats "overlapping files or modules" as a blocking reason.
- Implementer (Sonnet, up to 100 iterations) per issue in its own sandbox/branch: RGR, `npm run typecheck` + `npm run test` before commit; "Do not close the issue".
- Reviewer (1 iteration, same sandbox, only if commits exist): **edits the branch directly** for clarity/correctness, "Never change what the code does", applies `@.sandcastle/CODING_STANDARDS.md`.
- Merger (1 iteration): merges all branches into the current branch, resolves conflicts, "run `npm run typecheck` and `npm run test`", fixes failures, then closes issues.
- Outer loop up to 10 plan→execute→merge cycles.
- The template merges **into the current branch**, with no PR and no human gate; that is the template default, while the dictionary says an AFK run should end in "a PR, not changes already merged".
- No run-the-app or browser step anywhere in the templates.

---

## 5. Standards: where they live, pull vs push

[V transcript 1:28:02-1:32:27]: "you want the coding standards to be available via pull" for the implementer; "if you then have an automated reviewer afterwards, then you want it to push"; "in the reviewer, I would push the coding standards. In the implementer, I would allow it to pull. And I'm actually using Sonnet for implementation and Opus for reviewing".

[V] `SK/skills/engineering/retro/SKILL.md`, "Implementation vs Review":
- "The implementation agent has the most **context pressure**."
- "the review agent should be responsible for imposing coding standards, not the implementation agent."
- `CLAUDE.md`/`AGENTS.md`: "used incredibly sparingly, usually only for **navigation pointers**".
- "`CODING_STANDARDS.md`: this file is read during review, not implementation."
- Docs as reference files reached by pointers; skills for docs whose description should sit in context.

Where things live [V]:

| Kind of rule | Home | Consumer |
|---|---|---|
| Mechanical (banned API, import shape, file location) | Linter rule, pre-commit hook, CI job | Implementer self-corrects from the failing check |
| Judgement calls | `CODING_STANDARDS.md` (nothing ships it; `retro` proposes creating it) | Pushed to the Standards sub-agent of `code-review` |
| Domain language | `GLOSSARY.md` | Pulled by every skill |
| Hard-to-reverse decisions | ADRs under `docs/adr/` | Pulled; "respect ADRs in the area you're touching" |
| Module boundaries | `codebase-design` vocabulary; beta `setup-ts-deep-modules` enforces entry points with dependency-cruiser | Check + vocabulary |
| Smell baseline | Inside `code-review/SKILL.md` | Standards axis, always, "judgement call" only |

Standards axis checks [V]: violations of documented standards (cite file + rule) and the 12 Fowler smells; "Skip anything tooling enforces. Under 400 words."

**Design-system / UI rules** [V]: no dedicated home. The only mention is in `prototype/UI.md` (variants must use "The project's component library / styling system"). If UI conventions are to be reviewed, they would have to be written into `CODING_STANDARDS.md` or a doc it points to; the reviewer still only reads a diff, never pixels.

Note [V]: Sandcastle's own dogfood implement prompt does list `.sandcastle/CODING_STANDARDS.md` under "Read ... before changing code" (`.sandcastle/agent-workflows/implement/prompt.md` at `e99f832`), which is push-to-implementer and contradicts the stated principle. The shipped template's comment keeps the principle: standards are "enforced during review without costing tokens during implementation."

---

## 6. Escalation: when does an AFK implementer stop and hand back?

**The skills define no escalation rule.** [V] Neither `implement` nor `implement-spec` nor `tdd` says when to stop and ask. What exists:

- Before the run (the real control point): planning is HITL ("has to be human in the loop. Has to be", 26:58); `to-tickets` needs explicit approval; tickets needing a human get `ready-for-human` ("judgment calls, external access, design decisions, manual testing", `triage/SKILL.md`).
- Human-only steps: `/wizard` is model-invoked "the moment it hits a wall only you can pass" (credentials, dashboards, cutovers).
- `tdd` stops for seam confirmation when run interactively; in `implement-spec` this gate does not exist.
- Dictionary AFK [V]: unattended, "the agent picks a default and keeps going, and every later decision builds on that guess." "Agents don't reliably know when they're off track; left alone, they tend to push forward rather than stop and ask." His answer is to remove ambiguity before, check during, review after; not to teach the agent to escalate.
- Dictionary HITL [V], when to keep work in the loop: "ambiguous, irreversible, or where you'd struggle to review the finished result"; "how expensive is a wrong turn, and how late would you catch it?"
- Sandcastle [V]: implementer has `maxIterations: 100` and a completion signal `<promise>COMPLETE</promise>`; "If the task is not complete, leave a comment on the issue with what was done." Failed pipelines are logged and skipped (`Promise.allSettled`); the planner picks the issue up again next cycle. No human notification.
- Open user proposal #723 "implement: define a safe incomplete-run handoff" - no maintainer reply. [V via `gh`]

---

## 7. Published limits / failures, and what changed since v1.3

Since `d81f3a1`: nothing on `main` [V]. Sandcastle: nothing since 2026-06-29 [V].

Limits he states himself (all [V], repo docs at `d81f3a1` unless noted):
1. `implement-spec` output "is a draft that the review finishes".
2. No stop condition on the review/fix loop; `code-review` has "no convergence guarantee".
3. Parallel implementers collide on shared surfaces and names.
4. `implement` never closes tickets or checks criteria, so "nothing ever becomes visibly unblocked".
5. `code-review` cannot see uncommitted work; `implement` runs it before commit.
6. Same-session review is weak ("confirmation bias with a slash command", quoting a reader).
7. TDD has no answer for wiring/glue/config (#746), agents skip red-first sometimes, the refactor step was dropped ("agents essentially never performed it").
8. `to-tickets` over-decomposes and still sometimes slices by layer; acceptance criteria can be vacuous.
9. Agent-driven orchestration can "wander off"; deterministic loops are "more reliable".
10. Worktrees can make tests skip silently and report green.
11. Frontend: agents with browser tools are "not very good at that yet" (talk).
12. Review volume vs small PRs: acknowledged, unsolved (talk 59:27).
13. `retro` sees one session, can "invent generic advice", never prunes old checks.
14. `pr` Merge Danger is a self-report by the agent that wrote the change.
15. Dictionary "dark factory": with no human review, "Automated checks and automated review are the only gates. If they do not find a problem, the problem goes into the code."

---

## 8. What his flow does NOT cover (gap list)

1. No step that runs the application (build, start, smoke) at ticket end or on the integration branch.
2. No UI fidelity check: no screenshot, visual diff, Playwright/browser verification, or comparison to the chosen prototype.
3. No rule that carries a UI prototype into spec/tickets as a visual target (the snippet exception covers logic shapes only).
4. No integration / wiring / final-assembly ticket type for features; no full-suite or E2E gate on the integration branch beyond one diff review.
5. No QA skill, script, or checklist; QA is an unscripted human using the product. No acceptance-walkthrough step tied to the spec's user stories.
6. No design-system or frontend-standards home.
7. No escalation protocol for AFK implementers (when to stop, how to hand back, how to mark a ticket incomplete).
8. No ticket completion step in `/implement`; no automatic dispatch (orchestrating skills are user-invoked by design).
9. No stop condition for review/fix loops; no verification that review findings are true before fixing.
10. No verification that tests were written red-first, or that tests exist at the agreed seams (claimed in docs, absent in the skill).
11. No handling of PR review comments, CI failures after merge, deploy, or release.
12. No project bootstrap (issue #967: nothing stands a new project up).
13. No answer to the batch-size vs reviewability tension.
14. Sandcastle templates: no human gate before merge into the current branch, no browser tooling, generic `npm` commands only.

---

## 9. Reading for the cockpit failure (inference, [S])

"25 tickets, CI green, unassembled parts, nothing like the prototypes" lines up with four things his material predicts:
- Layer-shaped tickets instead of demoable slices (his 26-ticket anecdote; test: "what can I demo when this is done?").
- Prototype winner not folded into the real page before ticketing, and tickets written as prose, so no implementer ever saw the visual target.
- Acceptance criteria that could pass without the assembled behaviour ("graded nothing").
- No human QA between "green" and "done", which in his flow is the only gate for taste and real behaviour.

His flow would not have caught the visual mismatch automatically either; it relies on the human looking at the running app.
