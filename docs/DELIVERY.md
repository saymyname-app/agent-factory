# Delivery V1

## Status and authority

GitHub is authoritative for branches, commits, pull requests, checks and merges. Beads is authoritative for executable work, dependencies and gates. Gas City provides dispatch through existing formulas and provider configuration. V1 has one writer per rig; concurrent worktrees and multiple writers remain TARGET, not PROVEN.

The configured writer provider inherits `builtin:codex` and appends `-m gpt-5.6-sol`. M2 observed and proved that effective model on a real writer session. Mechanical decisions such as exit codes, diffs, SHAs, PR state and check conclusions are L0 deterministic work.

## Provider routing

- **PROVEN primary — Codex/Sol:** `codex` remains the workspace default and the
  only normal writer. Use it for Backend/Frontend implementation and keep the
  one-writer-per-rig rule.
- **CONFIGURED secondary — Claude:** the explicit `claude` provider inherits
  Gas City `v1.4.1`'s `builtin:claude`, pins the host CLI to `2.1.236`, selects
  `claude-sonnet-5`, and defaults to `plan`. The `claude-reviewer` template is
  on-demand only. Use it for fallback analysis or an independent GUARDED review
  when the risk justifies L3; it is not a global reviewer and must not overlap a
  writer on the same rig.
- **EXPERIMENTAL local candidate — OpenCode/Ollama:** Gas City already provides
  `builtin:opencode`, and OpenCode supports Ollama through its standard
  OpenAI-compatible provider plus denyable edit/shell permissions. Do not add a
  `local-*` provider until WSL-to-Ollama transport and repository read-only
  behavior are both proven. Even then, limit it initially to summaries, triage,
  documentation exploration and mechanical assistance; never use it as the
  authoritative security writer or reviewer.

The local lane may replace paid inference only for those low-risk L0/L1 classes
after its Gas City canary passes. A direct Windows-model response is not proof
of a usable factory lane.

## Profiles

| Profile | Selection | Required path | LLM level | Gate |
|---|---|---|---|---|
| FAST | Documentation, formatting, or another small reversible low-risk change | one writer; task-specific deterministic validation; branch and PR; merge only when required deterministic gates pass | L0 plus at most one L2 writer | no independent LLM reviewer by default |
| STANDARD | Normal feature or bug with bounded impact | one strong writer; task tests; GitHub CI/checks defined by the target rig; PR; review only when change risk or repository policy requires it | L2; L3 only when justified | required checks and existing human/repository review policy |
| GUARDED | Production, secrets, irreversible/data/security operations, or substantive product decisions | prepare all reversible work automatically; create a Beads gate only on the dependent path; keep unrelated ready work dispatchable | minimum sufficient L0-L3 | explicit human or supported GitHub/Beads gate at the exact risky transition |

L4 multi-agent execution is not a delivery profile and requires a concrete, measured decomposition benefit. A paid reviewer is never added merely because a PR exists.

## Existing primitives

- `gc sling` routes a bead directly or through an existing formula. `mol-do-work` is the proven minimal one-writer lifecycle; it does not provide worktree isolation.
- Gas City packs/formulas/orders supply workflow compilation, dispatch and maintenance. Do not wrap them in a proprietary runner.
- `bd dep` represents prerequisites. `bd gate create` supports `human`, `timer`, `gh:run`, and `gh:pr`; `bd ready` is blocker-aware.
- `gc github pr` supplies GitHub PR monitoring where configured. GitHub remains authoritative for actual PR/check/merge state.
- Provider inheritance supplies the pinned writer model; profile selection does not silently replace it.

## Review synthesis — redundancy filtering

`review-synthesizer` (and any bead that merges output from more than one
reviewer, e.g. `design-implementation-reviewer` + `design-test-risk-reviewer`
+ `gap-analyst` on the same change) runs the vendor pack's generic role
prompt, which executes exactly the claimed bead's description — there is no
built-in deduplication of agreeing reviewer findings at the framework level.
Research on multi-agent debate (S²-MAD, 2025) shows filtering out redundant,
agreeing exchanges before synthesis cuts token cost up to 94.5% with under
2% performance loss, by keeping only findings that differ from what's
already been said rather than re-stating consensus.

Whoever authors a review-synthesis bead description for this Factory (Mayor,
design-author, or a formula) must therefore say so explicitly in that
description, since the generic role prompt won't do it on its own:

- Merge inputs by **distinct finding**, not by reviewer — when two or more
  reviewers report the same issue, keep it once with a note of which
  reviewers agreed, not each reviewer's full restatement.
- Only carry forward a reviewer's finding verbatim when it *disagrees* with
  or adds to what another reviewer already said; summarize agreement in one
  line instead.
- The synthesized verdict is the deliverable; raw per-reviewer transcripts
  stay in their own beads/mail for audit, not duplicated into the synthesis
  output.

## External Evidence Gate

This gate adapts Compound Engineering's [`ce-plan` Phase 1.2 research-intent
triage](https://github.com/EveryInc/compound-engineering-plugin/blob/44d65ad64a0ac8e542eabee31ce031a7aeb41b28/skills/ce-plan/references/research.md#12-decide-on-external-research)
at official commit `44d65ad64a0ac8e542eabee31ce031a7aeb41b28`: explicit external requests,
intent classification, then local-pattern, risk, and uncertainty signals. This
is a pinned policy reference, not an imported pack or delegated decision.

The Mayor owns the judgment to **RUN**, **SKIP**, or mark external research
**UNAVAILABLE**. Record that judgment and its rationale in the work Bead before
it affects implementation. Deterministic signals may identify potentially
stale, version-sensitive, security-sensitive, or disputed claims, but they are
advisory: they do not launch research, establish truth, or replace the Mayor's
judgment.

- **RUN** when an unresolved external fact is material to a decision and cannot
  be established from the repository, configured runtime, deterministic tools,
  or already-recorded authoritative evidence.
- **SKIP** for trivial deterministic work and when local source, tests, runtime
  inspection, Beads, Git, or GitHub can answer the question authoritatively.
- **UNAVAILABLE** when load-bearing evidence cannot be obtained without
  speculation, prohibited disclosure, or an inaccessible source. Name the
  missing evidence and the affected decision; narrow the claim, retain the
  relevant gate, or escalate instead of presenting an unsupported conclusion.

Research reuses upstream `mol-polecat-report` as a report-only route and stores
the resulting Research Brief, or a durable link to it, in Beads notes. It does
not authorize source changes. The research worker may mutate only workflow and
Bead records needed to run and record the report. It must baseline Git HEAD and
working-tree status before research and recheck both afterward; it must not edit
files, create branches, push, comment, or otherwise mutate external systems.
Use one researcher by default. Fan out to two or three researchers only when
the Mayor records distinct, independent evidence axes and why parallel work has
measured value; do not duplicate the same query. No custom research service,
formula, broad methodology pack, or provider route is implied by this policy.

Each run uses the reusable [Research Brief template](RESEARCH_BRIEF.md). Prefer
dated primary official sources, identify the exact relevant product/runtime
version, and explain why every finding applies to the current decision.
Separate **TARGET**, **CONFIGURED**, **OBSERVED**, and **PROVEN** claims. Record
risks and unknowns, confidence with a reason, and the evidence's concrete impact
on the decision. Secondary sources may help discovery but cannot silently
replace available primary evidence for a load-bearing claim.

## Selection and completion contract

Choose the lowest-risk sufficient profile when creating the work bead and record the profile as a label (`delivery:fast`, `delivery:standard`, or `delivery:guarded`). The bead description names the repository, allowed scope, required deterministic validations and the merge authority. Risk escalation changes the profile before the risky step; it does not broaden the original authorization.

A delivery is complete only when the bead notes record the effective agent/session and model when an LLM ran, branch, commit SHA, PR URL/number, required checks and their conclusions, merge/final state, and deterministic validation. Closing a Bead never substitutes for GitHub merge evidence.

For GUARDED work, create the gate against only the bead that performs the protected transition:

```bash
gate_id=$(bd gate create --type human --blocks <dependent-bead> \
  --reason "Exact decision or irreversible transition requiring Benjamin" \
  --json | jq -r '.id')
bd ready --explain
```

The gate must state the decision and evidence required. Continue any independent ready beads. Resolve the gate only after the named authority decides; do not encode secrets in its reason or notes.

## Closed-loop status — where "done" actually ends

Verified 2026-09-15 against the imported pack, the city configuration and live
`gc` state. **This city has no automatic merge and no close-bead-on-merge.**
The delivery loop terminates at *pull request published*, not at *merged*.

This section exists because the section above names the condition ("merge only
when required deterministic gates pass") without naming the *actor*, which has
been read as an automated merge that does not exist.

### What is actually wired

The rigs import `gascity/roles` (`sha:3b3b89f2011e06d84459aa7bea1552382f13930a`),
which provides twelve agent roles: `design-author`,
`design-implementation-reviewer`, `design-test-risk-reviewer`, `gap-analyst`,
`implementation-reviewer`, `implementation-worker`, `issue-triager`,
`publisher`, `requirements-planner`, `review-synthesizer`, `run-operator`,
`task-decomposer`.

`publisher` is the terminal role — "authorized pushes, PR creation, and
publication surfaces". It closes **its own work bead** once the PR exists. No
imported formula (`publish`, `review`, `implement`, `do-work`, `build-basic`)
contains `gh pr merge`, a merge-conditioned `bd close`, or `merge_result`
metadata; the grep count is zero for all of them.

Consequence: a work bead reaching `closed` proves a pull request was opened. It
does **not** prove the change is on `dev`.

### What exists upstream but is NOT imported

`mol-refinery-patrol.toml` implements the full closed loop. Its `direct`
strategy fast-forward merges, pushes, re-reads `origin/$TARGET` to confirm the
push landed, writes `merge_result=merged` and `merged_sha`, then runs
`gc bd close "$WORK" --reason "Merged to $TARGET at $MERGED_SHORT"`.

It lives in the **Gastown example pack**
(`examples/gastown/packs/gastown/formulas/`), which this city does not import.
It is absent from `gc formula list`. Note that even importing it would only
give close-on-merge under `direct`: its `mr`/`pr` strategy closes the bead at
`"Pull request ready: $PR_URL"`, i.e. the same PR-terminal semantics we already
have.

No bead in the city carries `merge_strategy` metadata (count: 0), and the key
appears nowhere in `city.toml` or the rig configuration. The refinery's `local`
strategy escalates to the Mayor rather than merging.

### The gate conditions do exist — on GitHub, not in the city

Branch protection supplies the "under conditions" half of the loop:

- backend ruleset `22629508` requires the `Maven verify` check
- frontend ruleset `22629678` requires the `Tests and build` check

These block a bad merge. They do not perform a good one. Nothing in the city
observes "required checks green" and acts on it.

### Current operational consequence

Both rigs are `suspended_on_start = true`, and `claude-reviewer` / `ux-reviewer`
are `suspended = true`, so no rig-side delivery runs at all today. Factory
PR #47 (`feat(af-hho5.4): versioned SayMyName V1 release contract`) has been
open and unmerged since 2026-09-14 — the expected steady state of a loop that
ends at publication.

### Current policy — de facto, not yet a recorded decision

Until a merge actor is chosen and wired, **merging is Benjamin's step.** A
closed work bead must be read as "PR ready for merge", and any agent reporting
a bead as delivered must state which of the two meanings it intends.

Closing the loop requires an explicit decision on three points, none of which
has been made:

1. **Which actor merges** — import the refinery under `direct`, add a
   `gh pr merge --auto` step to the `publish` formula, or enable GitHub
   auto-merge on the repositories so branch protection releases the merge
   itself once checks pass.
2. **Which profiles may merge without a human** — FAST only, or FAST and
   STANDARD. GUARDED must stay gated in every option, per the profile table
   above.
3. **Where the bead closes** — at PR-ready (today) or at merged. Moving it to
   merged is what makes a closed bead mean "shipped", and requires the
   `merge_result` / `merged_sha` forensic metadata the refinery writes.

## Observed and proven baseline

- **PROVEN FAST:** M2 bead `af-v7a` used one Codex/Sol writer, deterministic diff validation, commit `77f206a85ab97352aa2e6f9bd2a4f2e653db6d69`, PR #9 and merge `43614760bce9a855a6aeecbfb38090461a905e70`.
- **OBSERVED GitHub:** this private repository currently has no Actions workflows and PR #9/#16 reported an empty check rollup. Repository rulesets and branch protection are unavailable on the current GitHub plan (API HTTP 403). Therefore checks cannot be claimed as configured here.
- **PROVEN scoped GUARDED gate:** gate `af-q4v` blocked only `af-wisp-2o0m`; independent `af-wisp-r31o` remained visible in `bd ready --include-ephemeral`. After resolution, the guarded bead became ready. All probe artifacts were closed.
- **CONFIGURED STANDARD contract:** target rigs must declare their own deterministic tests and GitHub CI/check requirements before STANDARD delivery is claimed. The Agent Factory repository currently proves PR transport/review, not CI execution.

These classifications are deliberately separate: the three contracts are durable and usable, FAST and gate isolation are proven, while target-repository CI remains to be observed during rig onboarding.

## SayMyName rig contracts

### Backend — `saymyname-backend` / `smb`

- **CONFIGURED:** default branch `dev`; one Codex/Sol writer; GitHub PR is the delivery boundary.
- **OBSERVED:** Java 21, Maven and Spring Boot 3.3.1; `Backend CI` executes `mvn -B -ntp -Pit verify` on pull requests to `dev`/`main`; Flyway and Testcontainers/MySQL are present. Active GitHub ruleset `22629508` requires the `Maven verify` status check.
- **PROVEN GitHub cleanup:** PR #27 merged at `5fc753308a1522c5f4f5d0ccc98df69bc982cc7b` with the required check green.
- **PROVEN locally:** unit test modules pass with Java 21. After the 2026-09-13 WSL/Docker remediation, `CourseKnowledgeTenantIsolationIT` passed 2/2 through Testcontainers, Ryuk, MySQL 8.0.41 and Flyway V1-V9. This scoped canary does not replace the full GitHub `Backend CI`, which remains authoritative for a STANDARD delivery.
- **FAST:** documentation or bounded test-only maintenance with task-specific deterministic validation. **STANDARD:** ordinary bounded backend changes with `-Pit verify` green in GitHub CI. **GUARDED:** Flyway/schema changes, persistent data changes, production actions, secrets, security-sensitive changes or irreversible transitions.

### Frontend — `saymyname-frontend` / `smf`

- **CONFIGURED:** default branch `dev`; one Codex/Sol writer; GitHub PR is the delivery boundary.
- **OBSERVED:** Node 22/npm; `Frontend CI` runs `npm ci`, non-blocking `npm run lint`, `npm test`, and `npm run build` on pull requests to `dev`/`main`. Active GitHub ruleset `22629678` requires the `Tests and build` status check.
- **PROVEN GitHub cleanup:** PR #41 merged at `b98e1ee176b7ed8af62987fdd84b35065b49c9e1` with the required check green.
- **PROVEN:** baseline tests pass (108 unit and 2 component) and the production build passes with CI placeholders. Full lint is currently non-gating and reports 197 errors/31 warnings; a task must still avoid introducing a scoped lint regression.
- **FAST:** documentation, isolated tests or bounded low-risk maintenance. **STANDARD:** ordinary bounded UI bugs/features with tests and build green in GitHub CI. **GUARDED:** production deployment/configuration, secrets, irreversible operations, security-sensitive changes or substantive product decisions.

M5 provides the first **PROVEN STANDARD** path: `smf-0jx` -> workflow `smf-7og` -> session `af-4g6` on `gpt-5.6-sol` -> commit `ba6745cd7193f79811471c8956698c1929303f2c` -> Frontend PR #40 -> successful `Frontend CI` -> merge `aa82099a183c64e0b02af80979dc1e28353edc4c`. The existing Claude review workflow exhausted its own turn limit without comments; M4 does not promote that optional paid reviewer into a gate for this low-risk one-line change.
