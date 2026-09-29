# Wayfinder gap analysis: upstream `wayfinder` vs the Agent Factory Planning Run

Read-only analysis, 2026-09-29 (Paris). Nothing was modified in the Factory, Beads or Git.

Sources and versions read:

| Source | Version read |
| --- | --- |
| Upstream `mattpocock/skills` | `main` = `d81f3a183412e71a5b1e84ca21bc1a35eea03a60` (commit 2026-09-29 14:37 Paris, "Merge #1120 release/v1.3") |
| Pinned commit cited by the Factory | `c55ee46073ed923f86ce59a5eb3b6d895095d1b7` (2026-09-18 12:12 Paris) |
| Factory repo `/home/benja/agent-factory` | HEAD `2481344272e5ba7d8f04c9b50e92f50f08d6893b` (2026-09-29 14:36 Paris) |
| C01 planning folder | worktree `/home/benja/agent-factory-po/c01-cockpit`, last commit `8e0f014` "round 5" |
| Operator skills | `C:\Users\benja\.agents\skills\` (listed 2026-09-29) |

**Pinned vs main:** `main` is 21 commits ahead of `c55ee46`, 0 behind. `skills/engineering/wayfinder/SKILL.md` is **byte-identical** (diffed). The changes touch other files: the `CONTEXT.md` → `GLOSSARY.md` rename (domain-modeling, setup `domain.md`, to-spec/to-tickets docs), `implement-spec`/`pr`/`retro` moving into engineering, and `ask-matt` routing for those. None changes the wayfinder contract. One consequence: the Factory's own `CONTEXT.md` naming now differs from upstream's `GLOSSARY.md` convention (not a wayfinder issue).

Abbreviations used below: **HITL** = human in the loop; **AFK** = the agent works alone. `W:` = `skills/engineering/wayfinder/SKILL.md` at `d81f3a1`. `WD:` = `docs/engineering/wayfinder.md`. `S:` = `skills/engineering/setup-matt-pocock-skills/`.

---

## 1. How upstream wayfinder works end to end

### 1.1 Purpose and trigger
- It plans a "loose idea … too big for one agent session" as a **shared map** of **decision tickets** on the repo's issue tracker, then resolves them one at a time "until the route is clear" (W:7). It plans and does not build: "produce decisions, not deliverables" (W:11-13).
- It runs only when the user types it: `disable-model-invocation: true` (W:4), `allow_implicit_invocation: false` (`agents/openai.yaml`). WD:9: "the agent won't reach for it on its own."
- The trigger is narrow: `grill-with-docs` for planning that fits one session, `/wayfinder` for multi-session planning (WD:11, WD:59-60; `ask-matt/SKILL.md:50`).

### 1.2 The map (W:19-53)
- One issue labelled `wayfinder:map`. Its tickets are child issues (W:21).
- The map is "an **index**, not a store". Each decision lives only in its ticket; the map gives a gist and a link (W:23).
- Where the map lives is tracker-specific. The skill reads the tracker doc's **"Wayfinding operations"** section. If no tracker is configured, it tells the user to run `/setup-matt-pocock-skills`, and the default is **local markdown** (W:25).
- The map body has fixed sections: `Destination`, `Notes` (domain, skills to consult, standing preferences), `Decisions so far` (one line per closed ticket), `Not yet specified` (fog), `Out of scope` (W:31-53). Open tickets are **not** listed on the map; a query finds them (W:29).

### 1.3 Tickets, claiming, blocking (W:55-71)
- Each ticket is a child issue whose body is a `## Question`, sized to one 100K-token session (W:57-63).
- Each ticket carries a label `wayfinder:<type>`, where the type is `research`, `prototype`, `grilling` or `task` (W:65).
- **Claim:** the session assigns the ticket to the driving dev **before any work**. "That assignee _is_ the claim" (W:67).
- **Blocking:** the tracker's **native** dependency links, because they render the frontier in the tracker's own UI. A text convention is used only when the tracker has no native links (W:69).
- **Frontier** = open, unblocked, unclaimed children (W:69).
- The answer is not in the ticket body. It is recorded on resolution. Assets are linked from the ticket, not pasted into it (W:71).

### 1.4 Ticket kinds and the skill that resolves each (W:73-80; WD:42-55)

| Kind | Mode | Resolved by |
| --- | --- | --- |
| `research` | AFK | a **subagent** that calls the Skill tool with `research` (W:77). It is fired at charting time and runs in parallel on a throwaway `research/<name>` branch (W:115; WD:50). |
| `prototype` | HITL | the Skill tool with `prototype`. The prototype is linked as an asset (W:78). The prototype skill keeps it on a throwaway branch as a primary source (`prototype/SKILL.md:26`). The human picks the variant, not the agent (WD:75). |
| `grilling` | HITL (the default) | "Always call the Skill tool twice, for `grilling` and `domain-modeling`" (W:79). |
| `task` | HITL or AFK | manual work that unblocks a decision, never a slice of the product (W:80; WD:53, WD:69). |

Rule: a HITL ticket resolves only through a live exchange with the human. "A grilling agent that answers its own questions has broken this" (W:75).

### 1.5 Fog of war and out of scope (W:82-101)
- Fog is written in `Not yet specified`. The test for fog versus ticket: can the question be stated precisely now? Whether it can be answered now does not matter (W:88-91).
- Resolving a ticket "graduates" fog into new tickets. Fog is not pre-sliced (W:84, W:91).
- `Out of scope` holds closed tickets that never graduate, plus one line on the map explaining why (W:95-101).

### 1.6 Invocation (W:103-128)
- Rule: "never resolve more than one ticket per session, with the exception of research tickets" (W:105).
- **Chart the map** (W:107-116):
  1. Name the Destination with `grilling` + `domain-modeling`.
  2. Grill **breadth-first** to map the frontier. **Exit without a map:** "If this surfaces no fog … you don't need a map. Stop and ask the user how they'd like to proceed" (W:112).
  3. Create the map.
  4. Create the tickets, then wire the blocking edges in a second pass.
  5. Fire the research subagents.
  6. Stop. "charting is one session's work; it hand-resolves nothing."
- **Work through the map** (W:118-128):
  1. Load the map at low resolution.
  2. Pick the named ticket, or else the first frontier ticket. **Claim it**.
  3. Resolve it with the skills named in `## Notes`. When in doubt, use `grilling` + `domain-modeling`.
  4. Post a **resolution comment**, **close** the ticket, append a context pointer to `Decisions so far`.
  5. Create any newly surfaced tickets (create, then wire). Graduate fog. Rule out-of-scope tickets. Update or delete tickets the decision invalidates.
- Concurrent sessions are expected (W:128). Upstream defines the write order but no lock (Factory checkpoint Q25, citing upstream issue #476 — UNVERIFIED by me).

### 1.7 Done condition and hand-off
- Done = "the way is clear, with nothing left to decide" and no tickets remain (W:13, W:84).
- The hand-off is not in SKILL.md itself. It is in the docs and the router:
  - WD:18 and WD:65-66: a cleared map goes to `/to-spec #<map_issue>`, then `/to-tickets`, then `implement`. "Looping the map straight into implement … throws the linked detail away."
  - `ask-matt/SKILL.md:52`: "When the map clears, it hands off, it doesn't build: merge onto the main flow at /to-spec."
  - WD:97: "hands you toward a spec, not a pull request."
- `to-spec` does not interview; it only synthesizes (`to-spec/SKILL.md:7`). It checks the test seams with the user (line 17), publishes to the tracker and labels the result `ready-for-agent` (line 19).
- `to-tickets` produces tracer-bullet slices with blocking edges, quizzes the user on the breakdown (lines 42-56), and publishes with native blocking where the tracker has it (lines 58-65).

### 1.8 What `setup-matt-pocock-skills` configures
- It writes three files: `docs/agents/issue-tracker.md`, `docs/agents/domain.md`, and `docs/agents/triage-labels.md` (the last only if `triage` is installed). It also adds an `## Agent skills` block to `CLAUDE.md` or, failing that, `AGENTS.md` (S:SKILL.md:9-13, 63-112).
- It is committed per repo. "There is no user-level or global mode" (`docs/engineering/setup-matt-pocock-skills.md:26`, `:76-78`).
- Tracker options: GitHub, GitLab, Local markdown, **Other** ("ask the user to describe the workflow in one paragraph; the skill will record it as freeform prose") (S:SKILL.md:44-47, 112).
- The GitHub template's **Wayfinding operations** (`S:issue-tracker-github.md:36-45`):
  - map = issue with the `wayfinder:map` label;
  - child = sub-issue with a `wayfinder:<type>` label;
  - blocking = native `dependencies/blocked_by`;
  - frontier query = open children, no open blocker, no assignee, first in map order;
  - claim = `--add-assignee @me`, the session's first write;
  - resolve = comment, close, then append a pointer on the map.
- The local-markdown template does the same with `Type:`, `Status: claimed|resolved` and `Blocked by:` lines, and an `## Answer` section (`S:issue-tracker-local.md:21-30`).
- **"Other" explicitly covers Beads.** From `docs/engineering/setup-matt-pocock-skills.md:49`: "'Other' is not a stub either. It is the reason Jira, Linear, Azure DevOps and Beads all work: you describe the workflow … and the downstream skills follow the prose." For an "Other" tracker there is no seed template, so the "Wayfinding operations" section has to be written by hand.
- Labels are not created by the setup skill. `wayfinder:map` and `wayfinder:<type>` must exist before the first run (`docs/…/setup-matt-pocock-skills.md:65-70`).

---

## 2. How the Factory Planning Run works today

### 2.1 Router (`bin/planning-run-router`, 534 lines; `docs/PLANNING_RUN_ROUTER.md`)
- It is the only Planning Run entry point, one-way cutover by `af-mav0b`, with no fallback flag (PLANNING_RUN_ROUTER.md:87-96, 257-265).
- Its input is a request JSON: `session`, `city_registry`, `spec_out`, and optionally `wayfinding {request, map, decisions[]}`, `approval`, `publish.draft`, `planning_run_target` (PLANNING_RUN_ROUTER.md:157-169).
- Sequence (PLANNING_RUN_ROUTER.md:209-219):
  1. `legacy_path` rejection.
  2. Reservation check (`.gc/runtime/planning-run-reservation.json`: factory-operations-v2, then C01).
  3. Optional wayfinding: promote the map, then claim+resolve **every decision the caller supplies with its resolution already written**. The code loop is `bin/planning-run-router:325-334`. It returns `wayfinding_pending` if the route is not clear.
  4. `to-spec` oracle on the **session file** (`to_spec_run(session_path, …)`, router:207-220, 398).
  5. `spec-approve approve`, only when `approval` is supplied.
  6. `ticket-graph-publish publish`, only when an approved draft is supplied.
- The router "writes nothing directly". It sequences the CLIs of the tools (router docstring lines 1-37).
- **The map's resolutions never feed the Spec.** `to-spec` reads only `planning-session.json` (`shared_understanding` entries). The map only gates the `to_spec_eligible` step (router:382-398). UNVERIFIED beyond these lines: I did not read the full 534 lines.

### 2.2 to-spec oracle (`bin/planning-run-to-spec-oracle`, 311 lines; `docs/PLANNING_RUN_TO_SPEC_PROTOTYPE.md`)
- It is deterministic. It checks declared context only, target rigs in the registry, **ceremony**, and explicit signals. It collects `shared_understanding` entries for 7 required topics and synthesizes a `DRAFT_SPEC` with a content digest (lines 38-56, 236-245).
- `check_ceremony` (lines 163-178) reads `request.complexity`, `wayfinder_ceremony_invoked` and `interview_rounds`. It only **rejects `complexity == "simple"` combined with `wayfinder_ceremony_invoked` or `interview_rounds > 1`**. It never requires wayfinder for `complex`. `wayfinder_ceremony_invoked` is a self-declared boolean that nothing checks against any map.
- Return-to-planning signals: `contradiction`, `missing_trace`, `undecided_behavior`, `new_test_seam` (lines 51-56). The oracle has no notion of an unverified fact or of missing research or prototype.
- It is a synthetic prototype, not an LLM `to-spec`. The Spec is a concatenation of confirmed statements, not the upstream template (Problem, Solution, User Stories, Implementation, Testing decisions…).

### 2.3 `bin/wayfinding-run` (480 lines; `docs/WAYFINDING_RUN.md`)
- It is a registry of a JSON map file with `fcntl.flock` locking (WAYFINDING_RUN.md:11-17; header lines 1-20).
- `promote` requires `exceeds_one_session: true`, a `trigger_reason`, and ≥ 1 decision `{id, map_key, summary}` (lines 115-172). Each decision is stored with the fields `plane`, `delivery_routable`, `map_key`, `summary`, `status`, `claimed_by`, `session_id`, `resolution`, `evidence`. There is **no type, no blocking edge, no Destination, no Notes, no fog, no out-of-scope, and no way to add a child after promotion**.
- Lifecycle: `claim` (first writer wins), `resolve` (only the claimant; the last resolve flips the map to `to_spec_ready`), `pause`, `resume --refresh`, `abandon`, `status`, `route-check` (WAYFINDING_RUN.md:31-42).
- Self-declared limit: "Not proven here: a live Beads/Dolt-backed Planning Map (this tool's map is a plain JSON file …) … or the to-spec adapter itself" (WAYFINDING_RUN.md:72-75).
- `spec-approve approve --map` closes the map when it approves the Spec (spec-approve header lines 1-22, 158-164).

### 2.4 What the fixture proves
- The proof is the router's **own** fixture, not the `tests/fixtures/fixture-city/` harness (PLANNING_RUN_ROUTER.md:278-287; B12 note:180-188).
- `tests/fixtures/planning-run-router/wayfinding/request.json` has 2 decisions (`staffing-model`, `rig-topology`). The router request supplies their resolutions. The session declares `complexity: complex`, `wayfinder_ceremony_invoked: true`, `interview_rounds: 2`.
- So the proof covers **plumbing** only: map lock, claim/resolve, the eligibility gate, digest, approval, publication. No skill runs. No research, prototype or HITL exchange is exercised. Nothing links map content to Spec content.

### 2.5 Live uses so far
- **factory-operations-v2 (A5, 2026-09-28)** used `wayfinding-run`. The map has 7 decisions, all `resolved`. Each resolution reads "see decisions-log.md § …" and each evidence reads "Benjamin live chat 2026-09-28". They are themes grilled in one PO conversation, then recorded with `decisions: []` in the router request (`docs/planning/factory-operations-v2/planning-map.json`, `router-request.json`, `decisions-log.md:1-8`). No typed tickets, no research, no prototype.
- **C01 (2026-09-29):**
  - Router request with no `wayfinding` block (`c01-cockpit/router-request.json`).
  - The session declares `complexity: "complex"`, `wayfinder_ceremony_invoked: false`, `interview_rounds: 5` (`planning-session.json`). The oracle accepts this combination.
  - The decisions log says "One session, four rounds … so a simple Planning Session (no Wayfinding map)" (`decisions-log.md:4-5`). This contradicts the `complex` field.
  - Round 5 (`decisions-log.md` §Round 5, item 3): "this run used the `grilling` skill and a read-only fact agent, not Matt Pocock's `wayfinder` (not installed; Factory `wayfinding-run` only keeps a decision map). No research or prototype step exists in the Planning Run flow."
  - Repairs made for C01 only: a K00 prototype ticket was added to the published graph (`ticket-graph-draft.yaml:62-83`), and a separate research.md was started. `facts.md:60` still carries an "(UNVERIFIED)" fact.

### 2.6 Mayor, workers, formulas
- `git grep -i wayfind` finds no match in `agents/` or `formulas/`.
- The Mayor prompt only refers to "the Planning Run flow" (`agents/mayor/prompt.template.md:103, 271, 293`).
- The worker prompt tells workers not to load skills (`agents/factory-worker/prompt.template.md:23`).
- WSL has no Matt skill at all: `~/.claude/skills` is absent, `~/.codex/skills` is empty. The repo's `.claude/skills` holds only `core.gc-*` and `gascity.mayor`.
- P02's selected allocation `skill-loaded-planner` lists `required_skills: [grill-with-docs, to-spec, to-tickets]` (`config/planning-allocation-prototype.json:9-13`). It has **no wayfinder, research, prototype or domain-modeling**. Its roles (`planning-agent`, `planning-session`, `planning-run-prototype` formula) are prototype names. UNVERIFIED that they exist as real Gas City agents, formulas or orders: `ls agents` shows only `factory-worker`, `mayor`, `ux-reviewer`, and `ls formulas` shows no planning formula.

---

## 3. Gap table

| Upstream element | Factory equivalent | Status | Evidence |
| --- | --- | --- | --- |
| Explicit `/wayfinder` invocation by the human | None. `wayfinding-run promote` is called by the PO or the router on a hand-built request | **missing** | §2.1, §2.6 |
| Charting session (Destination via grilling+domain-modeling, breadth-first grill, create map, create+wire tickets, fire research, stop) | None. Decisions are hand-written into `wayfinding-request.json` | **missing** | wayfinding-run:115-172; A5 wayfinding-request.json |
| Exit without a map when no fog (W:112) | Oracle forbids wayfinder for `simple`; C01 labelled itself both simple and complex | **partial / contradicts**. The upstream exit is a finding made during charting; the Factory uses a self-declared `complexity` flag | oracle:163-178; C01 decisions-log:4-5 vs planning-session.json |
| Map = index issue with `Destination`, `Notes`, `Decisions so far`, `Not yet specified`, `Out of scope` | JSON map with `run_id`, `trigger_reason`, `decisions{}`, `time_sensitive_fields`, `history` | **partial**. No Destination, Notes, fog or out-of-scope sections | wayfinding-run:165-196 |
| Map on the project tracker (for the Factory, Beads; spec Q20 says "one authoritative Beads/Dolt graph… Do not create a second tracker") | Plain JSON file in `docs/planning/<run>/` | **contradicts** Q20 and upstream "canonical artifact on tracker" | WAYFINDING_RUN.md:72-75; checkpoint Q20 |
| Tickets as child issues sized to one session, body = `## Question` | Decision entry `{summary}` inside the JSON | **partial** | wayfinding-run:136-160 |
| Ticket kind label `wayfinder:research/prototype/grilling/task` | None. CONTEXT.md defines Planning Decision Bead as "research, grilling, prototype, or prerequisite-task", but no code field carries it | **missing** (the glossary has it, the code does not) | CONTEXT.md:59-61; wayfinding-run:151-160 |
| HITL vs AFK distinction; HITL resolves only through a live human exchange | None. The router resolves decisions from caller-supplied text; the evidence field is free text | **missing** | router:325-334 |
| Research tickets resolved by parallel `research` subagents at charting, on `research/<name>` branch | None. C01 research was ad hoc after Spec approval | **missing** | af-0xoj26; C01 round 5 |
| Prototype tickets resolved with the `prototype` skill, linked asset, human picks | None in planning. C01 got K00 as a **delivery-graph** prototype ticket after approval | **missing** (worked around by putting it in delivery) | C01 ticket-graph-draft.yaml:62-83 |
| Grilling tickets resolved with `grilling` + `domain-modeling` | The PO session uses operator `grilling`; domain-modeling is not tied to tickets | **partial** (operator side only, not wired to decisions) | C01 round 5 item 3; operator skill list |
| Task tickets (unblock a decision, never build) | None | **missing** | — |
| Claim = assignee before work | `claim --claimant --session`, first writer wins, file lock | **present** (different mechanism) | WAYFINDING_RUN.md:36 |
| Native blocking edges and frontier query | None. Every decision is independent | **missing** | wayfinding-run:136-160 |
| One ticket per session (except research) | AC "One disposable session resolves one claimed decision"; the router loops all decisions in one call | **partial / contradicts** in the router | B04 AC2; router:325-334 |
| Resolution = comment on the ticket + close + pointer on the map | `resolution` and `evidence` strings on the decision; the map is the store (A5: "see decisions-log.md") | **partial**. The map is a store, not an index; the detail lives in a markdown log outside the map | A5 planning-map.json |
| Fog graduation into new tickets after each resolution | Impossible: no add-child subcommand after promote | **missing** | WAYFINDING_RUN.md:31-42 |
| Out-of-scope closure | None | **missing** | — |
| Invalidated tickets updated or deleted | None | **missing** | — |
| Concurrency protection | `fcntl.flock` exclusive lock, proven by P03 | **present** (a Factory addition beyond upstream, registered) | WAYFINDING_RUN.md:11-17 |
| Pause / resume / abandon | Present | **present** (Factory addition) | WAYFINDING_RUN.md:38-40 |
| Done = no open tickets, route clear → hand-off to `/to-spec #map` | The last `resolve` flips `to_spec_ready`, which gates the router's to-spec step | **partial**. The gate exists, but `to-spec` synthesizes from the session file, not from the map's decisions | router:382-398; oracle:236-245 |
| `to-spec`: LLM synthesis into upstream template, seam check with the user, publish | Deterministic oracle concatenating confirmed statements into 7 topics; approval via `spec-approve` | **partial** (adapted; template differs) | oracle:38-49, 203-232 |
| `to-tickets`: slices + quiz + publish with native blocking | The Ticket Graph Draft YAML is written by the PO agent; `ticket-graph-publish` publishes to Beads atomically | **present** (adapted; the publish door is deterministic) | refactor graph method_baseline; ticket-graph-publish |
| `setup-matt-pocock-skills` "Other tracker" prose incl. "Wayfinding operations" for Beads | None. No `docs/agents/issue-tracker.md` in the Factory or SayMyName | **missing** | git grep; operator README |
| Skills available to the agent that runs it | Operator (Windows): grilling, domain-modeling, prototype, research, ask-matt, grill-with-docs… installed; **wayfinder, to-spec, to-tickets, setup-matt-pocock-skills not installed**. WSL Factory: no Matt skill | **missing** for wayfinder | `C:\Users\benja\.agents\skills\`; §2.6 |

---

## 4. Where the intent was lost

What Benjamin intended can be traced in the refactor checkpoint (confirmed Q1-Q56, 2026-09-23):
- Q17 (`docs/research/2026-09-22-agent-factory-refactor-grilling-checkpoint.md:29`): "one Planning Map Bead plus non-executable Planning Decision Beads for research, grilling, prototypes, or prerequisite tasks … Launch eligible AFK research automatically; instantiate HITL sessions on demand".
- Q21 (line 33): "Apply the upstream Wayfinder resolution rules … graduates newly specifiable fog into new children".
- Q25 (line 37): "Keep Matt's Wayfinder writing protocol".
- Q10 (line 22): "Inspect and apply `setup-matt-pocock-skills` prerequisites where relevant".
- Q23 (line 35): "skills for agent method".

Where each element was dropped, in order:

1. **Spec, Observable Acceptance Criteria** (`docs/planning/agent-factory-project-agnostic-refactor-spec.md`, APPROVED 2026-09-23, digest `9ce47e19…`).
   - The ticket kinds survive only in *Implementation Decisions* line 122: "Multi-session research, grilling, prototypes, and prerequisite decisions use Planning Decision Beads."
   - The acceptance criteria that tickets are cut from drop them. AC5 (line 37) says only: "promoted … into a Wayfinding Run whose Planning Map and Planning Decision Beads preserve decisions". AC7-9 cover concurrency, pause and the no-second-fog-audit rule.
   - No AC mentions the four kinds, the research subagents, the prototype skill, fog graduation, blocking edges between decisions, or using the upstream skill.
   - AC27 (line 59) pushes "the exact Gas City allocation of … skills" to prototypes.
   - **This is the first artefact where "use wayfinder's mechanics" stops being testable.**
2. **Ticket graph P02** (`…ticket-graph-draft.yaml` P02, approved 2026-09-23) and its output `config/planning-allocation-prototype.json:9-13`.
   - The skills allocation keeps only `grill-with-docs`, `to-spec`, `to-tickets`.
   - **`wayfinder`, `research`, `prototype` and `domain-modeling` are absent from the required skills.**
   - This is the first place where skill wiring was actually decided, and it left wayfinder out.
3. **B04 `af-q7r0d`** (ticket graph lines 237-251, closed 2026-09-24, PR #214). The AC copies Spec AC5-9 word for word: "One disposable session resolves one claimed decision, records evidence, updates the map and closes." It has no kind, no skill, no fog graduation and no blocking. The worker built exactly that: a JSON registry (`bin/wayfinding-run`). WAYFINDING_RUN.md:72-75 admits it is not Beads-backed.
4. **B03 `af-hzhhr`** (ticket graph 221-235). "without mandatory Wayfinder ceremony" became `check_ceremony`, which only forbids wayfinder for simple requests. Nothing requires it for complex ones (oracle:163-178).
5. **af-4a44k (B12) → af-mav0b** (2026-09-24). The AC reads "The fixture City proves simple and Wayfinding paths …" and "The next real non-critical Planning Run is reserved for C01". The "Wayfinding path" is proven with pre-written resolutions. **C01 is reserved as the next run, but nothing says it must exercise wayfinder.** The C01 node in the refactor graph lists operator needs ("remaining decision frontier") but no method requirement.
6. **Operator audit, 2026-09-18** (`C:\Users\benja\.agents\skills\README-mattpocock-skills.md:38-43`). It classes `wayfinder` as "Supposent un tracker qu'on n'a pas (GitHub/GitLab/markdown local, jamais Beads/`bd`)". Upstream says the opposite: "Other" is how Beads works (`docs/engineering/setup-matt-pocock-skills.md:49`), and wayfinder falls back to local markdown (W:25). The claim was repeated in `SayMyName/knowledge/agent-skills.md:19-20`: "they assume GitHub/markdown trackers, not Beads". This kept wayfinder uninstalled at operator level, so the C01 PO session could not run it.
7. **Symptom surfaced**: C01 decisions-log §Round 5 item 3, then proposal bead `af-0xoj26` (open, 2026-09-29).

Side finding: `docs/research/2026-09-22-agentic-factory-autonomy-frontier.md:149` cites `wayfinder/SKILL.md#L273-L284` and `ask-matt/SKILL.md#L205-L231` at `c55ee46`. Those files have 128 and 90 lines at that commit, so the line anchors are broken. The content cited (the exit-without-map rule and ask-matt routing) is real, at W:112 and `ask-matt:50`.

Also: SayMyName decision 3 (`knowledge/decisions.md:18-20`) records Benjamin's belief that the refactor ADRs were "planned with wayfinding and grilling". This analysis shows the refactor itself was grilled (Q1-Q56 checkpoint), not run through upstream wayfinder. UNVERIFIED whether a wayfinder map existed for the refactor run `agent-factory-autonomy-frontier-2026-09-22`; I found none in the repo.

---

## 5. What a correct wiring would need: candidate decisions

These are options for Benjamin to decide. They are not recommendations on spend or exposure.

**D1. Where the skills live.**
- (a) Operator level: install `wayfinder`, `setup-matt-pocock-skills`, `to-spec` and `to-tickets` in `~/.agents/skills` with junctions into `~/.claude/skills`, consistent with SayMyName decision 10.
- (b) Vendored in the Factory repo (`.claude/skills` / agent packs), so a Mayor or planning agent in WSL can run it.
- (c) Both, pinned to one commit. Current candidate: `d81f3a1`; wayfinder is identical to `c55ee46`.
- Constraint: the Factory must stay project-agnostic, and workers are told not to load skills (worker prompt:23).

**D2. Which repo gets `setup-matt-pocock-skills` output.**
- `docs/agents/issue-tracker.md` is per repo (no global mode). Candidates: the Factory repo (for Factory planning), each project repo (SayMyName), or both.
- It also decides which instruction file receives `## Agent skills`. The Factory and SayMyName both have `CLAUDE.md` → `@AGENTS.md`; upstream would edit `CLAUDE.md` (known Codex gap, `docs/…/setup-matt-pocock-skills.md:61-63`).

**D3. Beads as the "Other" tracker: the "Wayfinding operations" prose.** Mapping to decide:
- map = one bead labelled `wayfinder:map` + `plane=planning` metadata;
- child = bead with `--parent <map>` (or a `parent-child` dep) + `wayfinder:<type>` label;
- blocking = `bd dep add <child> <blocker>` (native `blocks` edges);
- frontier = `bd ready` scoped to the map's children and filtered to `plane=planning`;
- claim = `bd update <id> --assignee <driver>` or `--claim`, as the first write;
- resolve = `bd comments add` + `bd close` + append to the map bead's `Decisions so far`.

UNVERIFIED: the exact `bd` flags for parent, claim and comments in the installed Beads version, and whether `bd ready` can be scoped by parent. Constraint: Mayor selectors must positively require `plane=delivery` (checkpoint Q20). Planning beads must never enter delivery selectors.

**D4. What happens to `bin/wayfinding-run`.**
- (a) Keep it as the JSON registry and add kinds, blocking, add-child, fog and out-of-scope. This diverges further from upstream.
- (b) Replace it with a Beads-native map as in D3, keeping its lock, pause and resume semantics as thin checks over Beads. This fits Q20.
- (c) Keep it only as a derived read model or cockpit view of the Beads map.
- Router and `spec-approve --map` callers would change accordingly.

**D5. How research is recorded.**
- Upstream: a research subagent writes a cited markdown file on a throwaway `research/<name>` branch, with a context pointer from the ticket.
- To decide: branch versus the planning folder (`docs/planning/<run>/research/`), which repo it lands in, and whether charting fires research automatically. Q17 says "Launch eligible AFK research automatically". Firing it spends tokens (Benjamin's tier if model/provider budget applies).

**D6. How prototypes are recorded and approved.**
- Upstream: `prototype/<name>` branch, the human picks, and the asset is linked from the ticket.
- The C01 precedent put the prototype (K00) in the **delivery** graph after approval. To decide: prototypes as planning tickets that block to-spec (upstream) versus delivery tickets (C01 workaround) versus both, and where the approval quote is stored.

**D7. Hand-off from map to Spec.**
- Upstream: `/to-spec #map` synthesizes from the map's linked decisions.
- Factory today: the oracle reads `planning-session.json` only.
- To decide: whether the map's closed tickets become the `shared_understanding` source (generated), whether the session file stays hand-written, and whether to add an oracle signal such as `unverified_fact` (proposed in af-0xoj26).

**D8. Entry rule.**
- Keep the checkpoint's Q7 hypothesis (grill-with-docs first, promote when > 1 session)? Or test wayfinder-first, as Benjamin doubted in Q7 and as the autonomy-frontier research (:138, :147) kept open?
- Also: replace the self-declared `complexity` and `wayfinder_ceremony_invoked` fields with evidence (a map bead id, or a recorded "no fog" exit from charting per W:112).

**D9. Who charts and who works tickets.**
- Upstream charting and HITL tickets need a live human. Decision 9 says agents propose and Benjamin decides. Benjamin says he always goes through an agent (C01 Q6).
- Options:
  - (a) Charting and HITL tickets are run in Benjamin's operator session (Codex or Claude, PO agent); AFK research runs as subagents or Factory workers.
  - (b) The Mayor charts, and Benjamin answers through the cockpit or mail. This conflicts with the Mayor being "executor of approved graphs" (decision 7) and with the Q11 split of planning from delivery authority.
  - (c) A dedicated planning agent per the P02 `skill-loaded-planner`. UNVERIFIED that it exists.
- Also to decide: whether the router's "loop all supplied decisions" mode stays, since it violates one-ticket-per-session and lets agents pre-write HITL resolutions.

**D10. Registering the deviation.** Record the adopted mapping in `docs/ADAPTATION_REGISTER.md` (Q32), and amend CONTEXT.md, B04 docs and PLANNING_RUN_ROUTER.md. Correct the 2026-09-18 audit line in `README-mattpocock-skills.md:38-43` and `knowledge/agent-skills.md:19-20`.

**D11. Retro-applying to C01.** Either C01 stays as published, with K00 and research.md as the repairs, or its remaining planning questions are re-run through a map. This decision is Benjamin's; the C01 graph is already approved and published.

---

## UNVERIFIED items (summary)
- The upstream issue #476 content (lost map update) was cited by the Factory; I did not open it.
- Exact `bd` CLI flags for parent, claim and comments, and `bd ready` scoping (D3).
- Whether the P02 `planning-agent`, `planning-session` and planning formulas exist beyond the prototype config.
- Whether any wayfinder map existed for the 2026-09-22 refactor Planning Run.
- I read `bin/planning-run-router` only in its header, docstring and the key lines cited (207-434), not all 534 lines.
