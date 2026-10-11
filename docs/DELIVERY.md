# Delivery V1

## Status and authority

GitHub is authoritative for branches, commits, pull requests, checks and merges. Beads is authoritative for executable work, dependencies and gates. Gas City provides dispatch through existing formulas and provider configuration. Worker pools are capped explicitly (`agents/factory-worker/agent.toml`, `[[patches.agent]]` in `city.toml`), not left uncapped: since 2026-09-29 (P17) the `agent-factory` rig runs up to 2 concurrent `factory-worker` sessions, each isolated in its own worktree with its own declared scope; product rigs stay at 1 writer until the same canary work runs there. `ticket-graph-publish` serializes any two not-yet-ordered tickets whose declared scopes overlap, and the dispatch door defers a dispatch whose scope touches a hot-file path an in-progress ticket already holds — a rejected ticket returns to the pool rather than being left stranded. Concurrent worktrees are PROVEN on the agent-factory rig by this rollout; wider multi-rig, multi-writer scaling remains TARGET.

The configured writer provider inherits `builtin:codex` and appends `-m gpt-5.6-sol`. M2 observed and proved that effective model on a real writer session. Mechanical decisions such as exit codes, diffs, SHAs, PR state and check conclusions are L0 deterministic work.

## Provider routing

- **PROVEN primary — Codex/Sol:** `codex` remains the workspace default and the
  only normal writer. Use it for Backend/Frontend implementation and keep the
  one-writer-per-rig rule.
- **CONFIGURED secondary — Claude:** the explicit `claude` provider inherits
  Gas City `v1.4.1`'s `builtin:claude`, needs host CLI `2.1.280` or newer
  (`2.1.290` installed 2026-10-06), runs `claude-opus-5-5` (passed in
  `args_append`, see the note in `city.toml`), and defaults to `permission_mode = "unrestricted"` (`city.toml`;
  `factory-guard` treats `plan` as broken: it strands unattended agents). The
  standalone `claude-reviewer` template was retired 2026-09-28 (O14, F15): no
  formula or prompt ever dispatched it, and the dispatch door has no path for
  an ad-hoc named reviewer session outside a rig's fixed `sling_target`. L3
  independent review for GUARDED-tier risk comes from `build-basic`'s own
  plan-review/review steps or the on-demand `ux-reviewer`, not a standalone
  reviewer pool.
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

A delivery is complete only when the bead notes record the effective agent/session and model when an LLM ran, branch, commit SHA, PR URL/number, required checks and their conclusions, merge/final state, and deterministic validation. Closing a Bead never substitutes for GitHub merge evidence. For PR-backed work, `closed` is itself guarded: only `bin/deliver-close` may atomically close after recording `merge_result=merged`, `merged_sha`, `merged_target`, the six ADR-0016 proof fields, and a successful required workflow run whose `gc.ci_head_sha` equals `gc.pr_head` (ADR-0026). A ticket of a convoy that carries the new-flow mark is not closed by that proof: `bin/deliver-close` refuses it, and it closes only through `bin/ticket-end` (`docs/TICKET_END.md`; ADR-0026, amendment 2026-10-09).

For GUARDED work, create the gate against only the bead that performs the protected transition:

```bash
gate_id=$(bd gate create --type human --blocks <dependent-bead> \
  --reason "Exact decision or irreversible transition requiring Benjamin" \
  --json | jq -r '.id')
bd ready --explain
```

The gate must state the decision and evidence required. Continue any independent ready beads. Resolve the gate only after the named authority decides; do not encode secrets in its reason or notes.

## Closed-loop delivery — how work reaches `dev`

**The loop is closed to `dev` as of 2026-09-15.** Rig pull requests targeting
`dev` merge themselves when their required status check passes; `main` stays a
human decision. The merge actor is GitHub, armed by a deterministic local
script, so closing the loop costs zero model tokens.

The section above names the merge *condition* ("merge only when required
deterministic gates pass") but not the *actor*. This section names the actor and
records what was verified about the machinery underneath.

### The wired path

1. A work session implements on a branch and the `publisher` role opens a PR
   against the rig's `dev`. It records `gc.delivery_contract=pr-ci-merged-v1`
   and `gc.delivery_status=waiting`; the work bead remains `in_progress`.
2. `bin/pr-autopilot` (registered as `orders/pr-autopilot.toml`, cooldown 3 min)
   arms GitHub auto-merge (`--auto --squash --delete-branch`) on every open,
   non-draft PR targeting `dev`.
3. GitHub merges the PR itself the moment the required check goes green —
   `Maven verify` (ruleset `22629508`) or `Tests and build` (ruleset
   `22629678`). Nothing polls; no session waits on CI.
   GitHub does not always do it: on 2026-10-09 pull request #479 stayed open
   17 minutes while armed, with `Tests` green on its exact head and a `CLEAN`
   merge state, and `gh pr merge --squash` merged it at once (#459 had waited
   13 minutes the day before). The cause is on GitHub's side and was not
   found in the ruleset or in the pull request's events (af-n8gft2). So
   `pr-autopilot` merges such a pull request itself, by its direct path
   (`gh pr merge --squash --delete-branch --match-head-commit <head>`), when
   it is armed, `CLEAN`, and its required check completed green at least
   `PR_AUTOPILOT_ARMED_MERGE_DELAY_SECONDS` ago (default 180; GitHub
   normally merges within two minutes). It is the same gate as auto-merge.
   A non-zero exit is never retried in the same pass: the server state is
   read again, and a pull request still open counts as one error of the run
   (`tests/pr-autopilot-armed-not-merged-test.sh`).
4. On its next pass, `pr-autopilot` loads the complete Beads history explicitly
   (`gc bd list --all --limit 0`), matches bead `gc.work_branch` to the PR
   `headRefName`, and calls `bin/deliver-close`. The door independently reads
   the merged PR and the latest configured required workflow run for the exact
   PR head. One atomic Beads write records `merge_result`, merge SHA/target,
   PR identity, `gc.required_ci_workflow`, `gc.ci_run_id`,
   `gc.ci_head_sha`, `gc.ci_conclusion=success`, and closes the work bead.
   Missing/red CI, a different CI head, an unmerged PR, or mismatched recorded
   branch/base/URL leaves the bead open and dependencies unreleased. A first successful finalization sends one compact
   `ACTION/STATE/EVIDENCE/NEXT` wake to the Mayor only when GitHub's `mergedAt`
   is at most one hour old, or an `open`/`in_progress` bead actively waits on
   the delivered bead through a `blocks` dependency or `gc.waiting_on`.
   Historical backfills still receive delivery metadata through the same door but remain silent when
   nobody is waiting. `gc mail send` has no live session to attribute this to
   (`pr-autopilot` is a deterministic script, not a session) and resolves the
   sender to `human`; the message body's own `ACTION: pr-autopilot reconciled
   …` line self-identifies the true actor instead (af-4ruvv). The
   `merge_result` stamp makes later passes silent.
5. A PR whose required check **failed** is never armed. It is raised as a P1
   bug bead in the rig instead, so a red build becomes ready work rather than a
   silently open PR.

Repository settings changed to support this: `allow_auto_merge=true` and
`delete_branch_on_merge=true` on `saymyname-app/Say-my-name-back` and
`saymyname-app/Say-my-name-front`. `saymyname-app/agent-factory` has since been
added to the autopilot's rig table (see *Production stays gated* below).

### Reading delivery state

A PR-backed bead is delivered only when it is closed with coherent merge and
exact-head CI proof. A ticket of a marked convoy is the exception: that
proof does not close it, `bin/deliver-close` refuses it, and it closes only
through `bin/ticket-end` (`docs/TICKET_END.md`; ADR-0026, amendment
2026-10-09). `merge_result=merged` alone, `closed` alone, or a green run
for another head is insufficient. `lib/factory_delivery_proof.py` owns this
pure predicate; `factory-waiting-guard`, `factory-delivery-guard`,
`factory-guard` and `pr-autopilot` use it, so a legacy false close cannot clear
a named wait. Explicit no-op, blocked, abandoned, and generic non-PR closes
retain their prior terminal semantics.

*Amendment 2026-09-27:* the scoped Mayor readiness lane (`mayor-campaign`),
which also rechecked approved-graph tickets with this predicate, left with the
campaign (ADR-0025 and ADR-0026 amendments). The Mayor now releases the next
approved-graph ticket itself when it is woken.

### Multi-repo / cross-rig delivery proof (af-kidv)

ADR-0016's six delivery-proof fields (`gc.delivery_status`, `gc.work_outcome`,
`gc.github_repo`, `gc.pr_number`, `gc.pr_head`, `gc.merge_commit`) fit exactly
one (repo, PR) pair per bead. A goal that ships as more than one pull request
across rigs cannot record all of them on itself. `af-7700` (personal CSV
import) is the worked example: it shipped as backend PR #39
(`saymyname-backend`) and frontend PR #50 (`saymyname-frontend`), both merged.

The convention, made explicit rather than left as a per-goal judgment call:

- The goal bead's own six fields record exactly one pair — call it the
  *primary* delivery. `af-7700` mirrors its backend child's pair (PR #39).
  Which pair is primary is not load-bearing; it is whichever pair the goal
  bead's own work session produced directly.
- Every rig's contribution, primary included, ships through its own
  `gc.goal=<goal-id>`-linked child execution bead (`smb-esa3`, `smf-2q6` for
  `af-7700`), each closed independently through `bin/deliver-close` with its
  own complete, GitHub-verified six-field proof. This was already required
  practice before this was written down — mol-do-work/mol-polecat-commit
  always close the execution bead they were dispatched with, never the goal
  bead directly — it just was not named as *the* rule for the cross-rig case,
  and nothing enumerated the full set back for a reader.
- The goal bead's own fields are **not** the complete delivery footprint for
  a cross-rig goal — they are one pair among possibly several. Never infer
  "this goal shipped exactly one PR" from the goal bead alone.
- To get the complete, deterministic list instead of manually tracking down
  each rig's child bead: `bin/goal-delivery-pairs <goal-id>` (or
  `--json`). It unions the goal bead's own six fields (when closed and
  delivered) with every closed, `gc.delivery_status=merged` bead carrying
  `gc.goal=<goal-id>` across the city and every registered rig, deduped by
  (repo, PR number) — the goal's own fields legitimately mirror one child's
  and must count once, not as an extra delivery.

### Production stays gated

In the SayMyName rigs, `dev -> main` is not automated and must not be:
`pr-autopilot` arms only PRs targeting a rig's `dev`. Promotion to production
remains a GUARDED transition requiring Benjamin.

The Factory's own repository is different, by Benjamin's standing
authorization of 2026-09-16: `agent-factory` has one long-lived branch, `main`,
and `pr-autopilot` arms its green PRs too (`bin/pr-autopilot`, rig table entry
`.|saymyname-app/agent-factory|main`). `main` there is the running factory,
not a product production branch.

### Outside authors are left to a human (af-996mmd)

Intent (Benjamin, his words, 2026-10-11): « en soit l'usine peut aller en
publique aussi , pour les CI github »
Mechanism (agent interpretation): before `agent-factory` can be public,
`pr-autopilot` acts only on a pull request opened from a branch of the
repository itself by one of the operator's own GitHub accounts
(`config/operator.toml`, `github_logins`; agents push with the operator's
token, so every pull request the Factory opens is on the list). It does not
mean a review step for the Factory's own pull requests, nor that the
repository is public: Benjamin changes the visibility himself.

| Cause | Effect without the rule | What holds now |
|---|---|---|
| On a public repository anyone opens a pull request, and the workflow that runs for it is the pull request's own | A stranger makes `Tests` green and `pr-autopilot` merges his code into `main`, the code the Factory runs on the host | A fork's pull request, or one whose author is not on the list, is skipped before anything else: never armed, merged, retried, labelled or turned into a bead. The pass prints `fork or outside author -> left to a human` |
| GitHub does not report the author or the fork flag | | Read as an outsider's |
| `github_logins` is empty or missing | | Nothing is armed, in any repository, and the pass counts an error |

Proof: `tests/pr-autopilot-outside-author-test.sh`. Undo: revert the change;
the list itself is one line of `config/operator.toml`.

### Historical note — why this needed building

`mol-refinery-patrol.toml` implements an equivalent loop upstream (its `direct`
strategy fast-forward merges, verifies `origin/$TARGET`, then closes the bead
with `merge_result=merged`). It lives in the **Gastown example pack**
(`examples/gastown/packs/gastown/formulas/`), which this city does not import,
and is absent from `gc formula list`. Its `mr`/`pr` strategy closes the bead at
"Pull request ready" anyway, so importing it would not have given close-on-merge
for PR-based delivery.

The imported role set (`gascity/roles`, `sha:3b3b89f2011e06d84459aa7bea1552382f13930a`)
ends at `publisher` — "authorized pushes, PR creation, and publication
surfaces". Grep count is zero for `gh pr merge`, merge-conditioned `bd close`
and `merge_result` across `publish`, `review`, `implement`, `do-work` and
`build-basic`. No bead carried `merge_strategy` or `pr_number` metadata, which
is why `pr-autopilot` links PR to bead by branch name instead.

## Marked convoys — the delivery flow of a Planning Run (D01)

A second delivery flow exists beside the closed loop above. It applies to
**marked convoys** only: convoys that carry the **new-flow mark**, posed at
publication for a Ticket Graph Draft that declares `flow_contract:
new-flow/v1` (`docs/ENTRY_CONTRACT.md`). It is opt-in per draft. No draft of
a live project declares it yet; the flow runs on the Fixture City. An
unmarked convoy is published, dispatched, merged and closed exactly as
before: the commands below read the mark first and write nothing on a convoy
that does not carry it.

In a marked convoy the control of the flow is code and agents are at the
leaves (Spec `af-wf4w5r` §0). The state lives in the tracker, read and
written through `bin/convoy-state` only, and in the evidence store. The
Mayor is not woken for it and never advances, closes or modifies its
tickets; it keeps the operation of the Factory. One order runs
`bin/convoy-advance` on every open marked convoy; each pass does what is due
and nothing else.

**The life of a ticket.**

1. **Start.** `bin/convoy-advance` starts the ready tickets, in dependency
   order, under the ceiling N (`max_sessions` of
   `config/delivery-flow.json`), through `bin/dispatch-door`. The door
   refuses a marked ticket to anyone else.
2. **Author.** One fresh author session, in a work tree of its own, on a
   branch that leaves from the integration branch of the Spec; the formula
   `mol-ticket-author` holds the sequence and `bin/ticket-author` its gates.
3. **TDD.** `bin/tdd-step red` proves the criterion tests red;
   `bin/test-review` has a test reviewer read them; `bin/tdd-step freeze`
   refuses without its favorable verdict; `bin/tdd-step green` proves them
   green, unchanged since the freeze.
4. **Exit.** The author ends by `bin/ticket-exit`, with its Ticket Handoff
   and the demonstration captured on the launched product. It never closes
   its ticket.
5. **Review and evaluation**, in parallel on the same tip: `bin/code-review`
   (a reviewer session; a finding blocks only with a citation found in its
   source) and `bin/ticket-evaluation` (an Evaluator on the launched
   product, one state per criterion; code computes the verdict). When the
   ticket touches a screen, `bin/prototype-fidelity` compares it to the
   Validated Prototype.
6. **At most one correction round** (`bin/correction-round`), common to
   both, by another fresh author session. Still refused: the ticket stops.
7. **Merge.** `bin/spec-integration merge` merges the ticket into the
   integration branch, one at a time, with tests on the merged result. No
   ticket opens a pull request toward the protected branch.
8. **Close.** `bin/ticket-end` reads its nine conditions and writes the
   closing with its gate record. Nothing else closes the ticket.

**The end of the Spec.** Once every ticket is closed, `bin/spec-end` renders
three mechanical verdicts (registry, tests, fidelity) on one tip of the
integration branch that holds the tip of the protected branch. On that
commit, in parallel, `bin/outcome-evaluation` gives one state per numbered
user story of the Spec and `bin/spec-end-review` reviews the whole assembled
diff. A refusal counts one repair round, its `repair` tickets published
by code; the rounds are bounded to 2, then a « non conforme » request goes
to the operator. `bin/evidence-pack` then generates the Evidence Pack, by code;
with its seven conditions met on one commit, the Outcome is **Delivered**.

**Acceptance.** The pass sends one Acceptance Request through
`bin/escalation-door`, with the link of the Evidence Pack.
`bin/acceptance-session` launches the product at the commit of that dossier
and stops it. `bin/owner-answer` records the owner's answer — « accepté »,
« constats rendus » or « abandonné », no other — and routes each Owner
Finding by code. The next pass runs `bin/outcome-promote`: on « accepté »,
one merge commit into the protected branch and the convoy closed; on
« abandonné », the convoy closed and nothing merged. No delay answers in
the owner's place, and a marked convoy never closes by itself.

**Stops and bounds.** The bounds are set in `bounds` of
`config/delivery-flow.json` and nowhere else.

- A ticket is resumed at most 3 times, every cause together; at the third
  it is parked with its descendants and raised to the operator.
- The convoy stops entirely while its integration branch is red (code
  publishes one `repair`) or while 2 Planning Exceptions are open on its
  Spec.
- An author that meets a question about approved intent exits by a Planning
  Exception (`bin/ticket-exit`, `docs/PLANNING_EXCEPTION.md`); a ticket
  leaves the graph only by a resolved one.
- A state the code has no rule for — a ticket started outside the dispatch
  door or closed outside its gate, evidence without a fingerprint — stops
  the convoy and raises one factory incident. The repair is Factory
  maintenance, never advancing or closing the tickets by hand; the convoy
  resumes by code once the state is valid again.

| Question | Read |
|---|---|
| What must a draft hold to be published marked? Who reviews the graph? | `docs/ENTRY_CONTRACT.md`, `docs/GRAPH_REVIEW.md` |
| Where does a convoy stand, and why does nothing start? | `docs/CONVOY_STATE.md`, `docs/CONVOY_ADVANCE.md` |
| What does the author session do, step by step? | `docs/TICKET_AUTHOR.md`, `docs/TDD_STEP.md`, `docs/TEST_REVIEW.md`, `docs/TICKET_EXIT.md` |
| Why was a ticket refused before its merge? | `docs/CODE_REVIEW.md`, `docs/TICKET_EVALUATION.md`, `docs/PROTOTYPE_FIDELITY.md`, `docs/VALIDATED_PROTOTYPE.md`, `docs/CORRECTION_ROUND.md` |
| How is a ticket merged, and why is it still open? | `docs/SPEC_INTEGRATION.md`, `docs/TICKET_END.md` |
| Why is the Spec not Delivered? | `docs/SPEC_END.md`, `docs/OUTCOME_EVALUATION.md`, `docs/SPEC_END_REVIEW.md` |
| What is a proof, and what does the owner read? | `docs/EVIDENCE_STORE.md`, `docs/EVIDENCE_PACK.md` |
| How does the owner judge and answer, and what follows? | `docs/ACCEPTANCE_SESSION.md`, `docs/OWNER_ANSWER.md`, `docs/OUTCOME_PROMOTE.md` |

Two checks hold this description to the code. `./bin/method-check table`
reads the requirement → mechanism → proof table of
`docs/REQUIREMENT_TABLE.md` and is red in CI when a row has no mechanism or
cites a command absent from `bin/`. `./bin/method-check register` checks
that every deviation of Spec §16 has its entry in the Adaptation Register
(`docs/ADAPTATION_REGISTER.md`), with its reason and the v1.3.1 baseline.

## Main-landing gate — `main` cannot go red silently anymore

**As of 2026-09-16, `git push` to `main` in `saymyname-app/agent-factory`
runs the guarded local test suite first and refuses the push if it fails**
(`bin/factory-main-gate`, installed as `.githooks/pre-push`, ADR-0020).

This closes a real gap: commit `8d92c13` landed directly on `main` and broke
referential integrity between `legacy/docs/products/saymyname/DECISIONS.md` and
`config/products/saymyname.json`'s `decision_refs` — a check
the Cockpit V1 suite (`tests/factory-cockpit-test.py`, since removed) already had. Nothing forced that suite to run
before the commit reached `main`; Factory CI (which then also ran `on: push`
to `main`; it no longer does, see `OPERATIONS.md`, "Factory CI cost and the
Actions quota") only reported it after the fact, and
both CI and the live cockpit stayed broken for hours before it was noticed.
At the time (2026-09-16) this repository could not use GitHub branch
protection or a required check — private repo, no GitHub Pro, `403` on the
branches API — so a local gate was the available mechanism, not a fallback
choice. Ruleset `AF-main-protection` exists since 2026-09-17 and is now
read/write with the Factory's token (see "Merge safety — `main` requires
up-to-date branches" below); this local gate remains the only mechanism for
the guarded local test suite itself, which a GitHub required check does not
run.

The gate runs `bin/ci-run-tests` — the same discovery CI itself runs (every
`tests/*.py|*.sh` file, minus anything marked `# ci: local-only`) — so it can
never drift from CI's own list, and neither has to be hand-edited when a
test file is added (ADR-0017, `tests/ci-registration-test.sh`).

What the marker leaves out of CI runs at night instead (T49, af-xcfup7):
`bin/local-only-tests`, started at 04:00 by `orders/local-only-tests.toml`,
runs every `tests/*.sh|*.py` file marked `# ci: local-only`, one at a time,
and on a failure files a bead and pages the Mayor through
`bin/escalation-door`. It reads the marker, not a list of names: a new
local-only test runs the next night with nothing else to edit. The only
files left out are the ones `config/local-only-tests-exclusions.txt` names, each
with its reason — a test whose every run spends a real session (today the
real Mayor of `tests/convoy-stop-mayor-isolated-city-test.sh`); run those
by hand. `bin/local-only-tests --list` prints what a run would do (`run
<path>` / `excluded <path> <reason>`) without running anything, and
`tests/local-only-tests-coverage-test.sh` fails in CI when a marked file is
neither run nor excluded, or when an exclusion has no reason or names no
marked file. A test stopped after `LOCAL_ONLY_TEST_TIMEOUT` (default
1800 s) counts as failed; the order's own timeout (`6h`) bounds the night: run one at a
time on a loaded host, the marked tests take a little over two hours.
A trial on the real tracker that calls `bin/convoy-state` or a tool built on
it exports `FACTORY_ROOT` to its disposable city: the tools name their city
to `gc` from it, and left unset they name the repository they run from.

The runner also keeps tests off the host's escalation lock (af-wnj692): each
test runs with a throwaway `XDG_RUNTIME_DIR`, and one that still reaches
`bin/escalation-door`'s default lock file fails the run. A test that calls
the door — directly or through a script that escalates — sets
`ESCALATION_DOOR_LOCK_FILE` to a path it owns; `tests/lib/sandbox.sh` and
`tests/lib/sandbox.py` do it for every test built on them
(`tests/ci-run-tests-host-lock-test.sh`).

**What to run before a pull request (af-66bfyx).**

Intent (Benjamin, his words, 2026-10-08): « ok pour ta reco », in answer to
the table below as it was shown to him; and, earlier that day: « je veux que
l'usine finisse son taf pendant que je dors, et je veux que ca consomme pas
toutes les minutes github et que les tests soient intelligents et econome en
token, mais que la qualité soit là à la fin »
Mechanism (agent interpretation): what an agent runs on the host before it
opens a pull request on this repository depends on the kind of change. It
does not mean a change of the merge gate: Factory CI runs on every pull
request and `Tests` is still the required check.

Intent (Benjamin, his words, 2026-10-08, about 22:35 Paris): « A. », in
answer to the two options shown to him once Factory CI ran on the host's own
runner (af-r1ymfm): A, the rule checks and the touched tests before a
delivery's pull request, the whole battery left to CI; B, the rule as it
was. And: « Il faut réduire les tests au minimum requis pour avoir la
qualité suffisante. »
Mechanism (agent interpretation): while CI runs on the host, a delivery no
longer runs the whole battery before its pull request, because CI runs it
right after on the same machine and a red there is billed nothing. It does
not mean fewer tests in CI, a test removed, or a merge without the whole
battery green: his second sentence is a direction for later work, not
applied here.

| Kind of change | Where CI runs (`./bin/ci-runner mode`) | Before the pull request | Why |
|---|---|---|---|
| A delivery: a `do-work` ticket, or anything that changes a tool, a formula, an order or a configuration | `self-hosted`: the host's own runner | The rule checks and the tests the change touches: `bin/ci-run-tests --rule-checks --changed-since origin/main` | The battery by hand (14 minutes on 4 cores) and the CI run that follows (15 minutes on 4 cores) were the same work twice on the same machine, 29 minutes a push; a red in CI is billed nothing there (measured 2026-10-08, `docs/OPERATIONS.md`, "Factory CI on the host's own runner") |
| The same | `github`, or no clear answer | The whole battery: `bin/ci-run-tests --jobs 4` from the work tree | On GitHub's runners a red is seen after about 37 billed minutes; a run aimed at what the change touches is 75 to 96% of the battery (merged pull requests #407 to #438), and batteries queue on the host (below) |
| Docs, CI or tests alone | either | The rule checks and the tests the change touches, same command | 2 to 6% of the battery, and none of the 6 test files that failed in CI in that sample would have been missed |

What the lighter check costs: a long test broken by a delivery is seen in
CI, about 15 minutes after the push, instead of before it; the pull request
stays unmerged, the agent fixes and pushes again. Nothing merges without the
whole battery green in CI, on the host as on GitHub's runners.

The rule checks are the test files `config/ci-test-seconds.tsv` gives 5
seconds or less: catalogues, registration, lints (105 files, 107 s together
on 2026-10-08). Of those 6 failed files, 5 were rule checks of 1 second or
less, a stale generated catalogue most often, and each was seen only after
about 37 billed minutes of a run. `--changed-since` adds the test files the
branch changes, committed or not; the run starts with `NOT the battery` and
counts both. It waits its turn on the host like a battery. In doubt about
the kind of change, or about where CI runs, run the battery
(`tests/ci-run-tests-rule-checks-test.sh`, `tests/ci-runner-test.sh`).

On GitHub's runners Factory CI does not run the rule checks before the long
lots (Benjamin, his words, 2026-10-08: « A pour la ligne 3 », A being "not
in CI"). Measured gain: about 2 billed minutes a run (4 of 70 runs, about 35
minutes each). `Tests` must exist from the first second of a run, so it
cannot wait on a gate job, and the variants that keep it were estimated at
1 to 3 billed minutes on every run.

On the host's own runner it does (Benjamin, his words, 2026-10-08, about
22:50 Paris: « oui, vas-y pour la première tranche », the first slice being
"the rule checks first in CI, and a measure of the long tests"). Mechanism
(agent interpretation): there the run is one lot and is billed nothing, so
`bin/ci-run-tests --rule-checks-first` runs the same tests in another order
inside the job named `Tests`: the rule checks first (110 files, 118 s of
test time, about half a minute on 4 cores), and a red one stops the run
there instead of after the long tests. It does not mean a test left out of
a green run, nor another gate: green, every test ran
(`tests/ci-run-tests-rule-checks-first-test.sh`).

**One battery at a time on the host (af-7m7ymg).**

Intent (Benjamin, his words, 2026-10-08): « je veux que l'usine finisse son
taf pendant que je dors, et je veux que ca consomme pas toutes les minutes
github et que les tests soient intelligents et econome en token, mais que la
qualité soit là à la fin »
Mechanism (agent interpretation): batteries started on the host run one
after the other. It does not mean fewer tests, nor a different gate.

On 2026-10-08, 06:04 to 06:35 (Paris), three batteries ran at once beside the
live Factory (two delivery workers and an operator session): load 37 on 12
cores, 8 GB of memory full, one test file at 504 s instead of about 60, and
two Cockpit tests red on "nothing listening on 127.0.0.1:<port> after 5s"
that pass alone in 14 s on the same commit. A false red costs an agent a
diagnosis and a second run, and can send a red or a retry to GitHub.

| What you see | What it means | What to do |
|---|---|---|
| `ci-run-tests: waiting for the battery of <work tree> (pid, since HH:MM, J file(s) at once) -- ... waited Ns of at most Ms`, repeated every minute | Another battery holds the host; yours has not started and starts by itself when that one ends. | Nothing. Do not start a second one, do not kill the other. |
| `ci-run-tests: NOT RUN -- the battery of ... still holds the host after Ns`, exit 75 | The wait reached `CI_RUN_TESTS_HOST_WAIT` seconds (default 5400). No test ran. | Not a test failure: start it again later. Never report it as red or green. |

How it holds: `bin/ci-run-tests` takes `/tmp/agent-factory-ci-run-tests-<uid>.lock`
through `flock --close` and runs itself under it, so the lock belongs to the
battery and to nothing a test leaves behind, and it goes when the battery
ends, however it ends. `--list`, a GitHub runner (one run per machine), a job
of the host's own runner (boxed and held to 8 cores and 4 GB:
`docs/OPERATIONS.md`, "Factory CI on the host's own runner") and a
`ci-run-tests` started from inside a battery (the tests of the runner) do not
wait. Proof: `tests/ci-run-tests-host-queue-test.sh`.

What it does not cover:

- The size of one battery: `--jobs J` still runs J files at once. Lots
  started side by side by one session (`--shard 1/4 &`, `--shard 2/4 &` ...)
  now run one after the other: on the host use `--jobs`, lots are for CI.
- A test file run alone (`bash tests/x-test.sh`, `python3 tests/x-test.py`),
  `bin/local-only-tests` and its nightly order, and any other heavy process
  (on that night a secret scan of the archive's whole history held 4 GB): they
  do not take the lock.
- The order of arrival: when several batteries wait, any of them is next.
- A game or anything else Benjamin runs on the PC: the lock does not look at
  the load, it only keeps batteries from adding to each other.

**It does not touch the automated delivery loop.** `bin/pr-autopilot` lands
merges with `gh pr merge` — a GitHub-side API call, never a local `git push`
— so this hook never runs on that path. Rig PRs into `dev` are unaffected;
they are still gated purely by their own required GitHub CI checks as
described above. Only a `git push` that includes `refs/heads/main` in this
repository is gated, and only by the same tests CI already runs.

Emergency bypass is the standard git escape hatch, `git push --no-verify` —
this is a local convenience gate, not a security boundary. See ADR-0020 for
the full decision record and `tests/factory-main-gate-test.sh` for the proof
that it actually blocks a broken push and never blocks anything else.

## Merge safety — `main` requires up-to-date branches (P05, af-yl964)

**As of 2026-09-29, ruleset `AF-main-protection` on `saymyname-app/agent-factory`
requires PRs to be up to date with `main` before merge**
(`strict_required_status_checks_policy: true`), and the repo setting
`allow_update_branch: true` lets `gh pr update-branch` catch a PR up.
Applied and read back once by `bin/enable-strict-main-protection`
(A6 Planning Run, `docs/planning/parallel-delivery/decisions-log.md` Q4).

This closes the gap P04 (`bin/pr-autopilot`, af-s6lef) could only work
around: before this change a PR could merge onto `main` while BEHIND, so two
PRs each green against an older `main` could combine into a red `main`
without ever conflicting textually. P04 already never arms a BEHIND PR and
brings BEHIND PRs up to date itself — this ruleset flip is what makes
that mechanism load-bearing instead of optional, by making GitHub itself
refuse a BEHIND merge.

**One queue head at a time (af-31t0y8).**

Intent (Benjamin, his words, 2026-10-11): « là ya plein de CI qui sont
refaites car la PR n'est plus à jour, il faut eviter ca structurellement
non ? »
Mechanism (agent interpretation): `bin/pr-autopilot` brings a BEHIND PR up
to date only when no other PR of the same repository holds the queue. It
does not mean the "up to date before merge" rule is relaxed, nor any spend.

| Term | Meaning |
|---|---|
| Queue head | A PR that is up to date with its base (neither BEHIND nor in conflict), past the autopilot's holds, whose required check is waiting, running, or green and about to merge. |
| Waiting PR | A BEHIND PR while another PR is the head. It is left alone: no branch update, so no run. |

| Event | Effect on the next tick |
|---|---|
| The head merges | Every other PR is BEHIND, none is the head: the oldest BEHIND PR whose last required run is not red is updated and becomes the head. A PR whose last run is red is taken only when no other waits. |
| The head goes red (after its single automatic retry) | It is sent back or flagged as before, stops being the head, and the next BEHIND PR is updated on that same tick. |
| The head conflicts (DIRTY) | Same: it is no longer the head. |
| The head carries the `autopilot-stuck` label (blocked with nothing pending) | Same: it will not merge by itself, so it does not hold the queue. |
| A new PR is opened | It is up to date at birth and its run starts by itself, so it counts as a head too: nothing is updated while it runs. Two heads can therefore exist; the autopilot never creates a second one. |

Why: before, one BEHIND PR was updated per tick (3 minutes), whoever was
already up to date. With one CI job at a time and a run of 14 to 45 minutes,
ten PRs put ten runs in the queue, one merged, and its merge made the nine
other runs stale (measured 2026-10-11 from 00:00 to 15:42 Paris: 40 runs for
9 merges, 18 cancelled). Now a run is asked for only for the PR that can
merge next.

Known limits:

- A waiting PR meets the recent `main` only at its turn: a red caused by the
  combination shows late and costs one run.
- The queue is serial: N waiting PRs merge in about N runs, one after the
  other. A red head costs its run and its retry before the next one starts.
- A PR opened while a head runs keeps its own first run; if the head merges
  first, that run is stale and still occupies the runner until it ends or
  the PR is updated.
- When the tick's time budget cuts the list of open PRs short, no branch is
  updated on that tick (an unread PR may be the head).

Proof: `tests/pr-autopilot-queue-head-test.sh`. Undo: revert the pull
request of af-31t0y8; the previous rule (one BEHIND PR per tick) comes back.

Replaced later by GitHub's own merge queue (one run for a batch of PRs), if
it becomes available for this repository: it needs the `merge_group`
trigger in `.github/workflows/ci.yml` and a ruleset rule, and makes this
BEHIND logic useless for the repository that uses it.

This is a poor-man's merge queue, not GitHub's merge queue: the org's plan
does not confirm GitHub Enterprise Cloud, which the real merge queue
requires on a private repo, so no spend was made (decision Q4). `main`
going red from two independently-green-but-combined PRs stays possible only
if pr-autopilot's update-branch step itself races a second
concurrent merge — not addressed here.

**Scope:** `saymyname-app/agent-factory` only. `bin/enable-strict-main-protection`
refuses any other `--repo` before making a single `gh api` call.
Say-my-name-back's `SMN-back-dev-protection` and Say-my-name-front's
`SMN-front-dev-protection` rulesets, and both repos' `allow_update_branch`,
are untouched by design (SayMyName repos' GitHub settings are out of scope
per the ticket's safety contract).

**Idempotent:** re-running the script reads the live ruleset and repo
setting first and only writes what is not already applied; a second run
against an already-applied repo makes no write call.

**Rollback (one command):**

```
bin/enable-strict-main-protection --rollback
```

This sets `strict_required_status_checks_policy` and `allow_update_branch`
back to `false` — the values recorded live on 2026-09-29 before this script
first ran (`docs/planning/parallel-delivery/facts.md`).

See `tests/enable-strict-main-protection-test.sh` for the proof (idempotent,
scope-guarded, rollback) against a faked `gh`.

## Real-PII containment — CI structural backstop (af-6eqc)

The dev DB currently holds real person data (the "invariant de confinement"
in the pre-refactor `legacy/docs/products/saymyname/DESIGN_GOVERNANCE.md`,
untrusted). Removing that is a separate, non-urgent piece of
work (af-hq2j, a synthetic dataset with the same shape). Until it ships,
this is a **containment** guard against a real identifier landing in a
tracked data file — it does not eliminate the underlying problem, it
contains it.

The local, exact-match layer (`bin/factory-pii-guard`, formerly installed in
`.githooks/pre-push` and surfaced in `bin/factory-guard`'s periodic report)
was retired 2026-09-28 (O14, Benjamin Q4.3); the written rule against real
person data stays in the SayMyName repo's own `knowledge/real-person-data.md`.
What remains is the structural backstop:

**CI, both rigs, zero secrets (`bin/factory-provenance-guard`, run from each
rig's GitHub Actions workflow).** CI cannot hold a real-identifier list at
all — putting one in a GitHub Actions secret would itself hand real PII to
a third party, which is exactly what this guards against. So it does not
attempt exact-value matching. Instead it requires that any data file under a
fixture/seed/test-resource path (`fixtures?/`, `seeds?/`, `test-resources?/`,
`testdata/`, `test-data/`, or Maven's `.../test/resources/`, any depth) carry
a provenance marker proving it came from the synthetic generator (af-hq2j): a
`PROVENANCE.md` manifest in the same directory with a line
`<filename>: synthetic-provenance af-hq2j sha256:<hex>`, where the hash is
the file's own sha256. The hash binds the attestation to the file's exact
current content — a filename+keyword line by itself is not proof, so a data
file swapped in after the manifest entry was written (or an entry never
actually backed by the generator) fails the same way an unmarked file does.
An unmarked or stale-attestation data file in one of those paths fails the
build — it is either real data that should never have landed there, or a
synthetic file someone forgot to record (or re-record after editing).

Its coverage is narrower than "any real data" and the two boundaries that
matter are both hard-coded in `bin/factory-provenance-guard`. **Path:** only
the fixture/seed/test-resource directory names above, at any depth — a data
file anywhere else in the tree (application code paths, docs, top-level data
directories that aren't named one of those) is not looked at by this guard
at all. **File type:** only these extensions —
`.json .csv .sql .yaml .yml .xml .properties .tsv`. Anything else under a
watched directory, including images and other binary formats
(`.jpg .jpeg .png .heic .pdf`, …), is invisible to its regex and is never
asked for a `PROVENANCE.md` entry. This is why real-person photos (Oxyl dev
data) produced no signal for a year: they are binary files, so the extension
filter never selects them even when they sit under a watched path.
Distinguishing real photo data from synthetic photo data is separate,
future work (see the guard candidate referenced from af-ox44d); today,
binary files of any kind are outside what this guard claims to contain.

This is not a security boundary against a determined actor; it is a CI
convenience gate that catches the mistake before it merges. See
`bin/factory-provenance-guard` for the exact mechanism.

## Réversibilité par défaut

Règle (ADR-0019, ADR-0016 §7) : un changement doit pouvoir être défait dans la
release. C'est la forme normale d'un changement, pas l'exception — et c'est ce
qui fait que le test d'escalade 4 (« impossible à défaire ») se déclenche
rarement.

### Migrations Flyway — ce que fait le rédacteur

Avant d'ouvrir la PR, depuis le rig :

```bash
/home/benja/agent-factory/bin/reversibility-check --git . --base origin/dev
```

Chaque **nouvelle** migration est classée, instruction par instruction :

| Classe | Exemples | Déclaration acceptée |
|---|---|---|
| perte de schéma | `DROP TABLE`, `DROP COLUMN`, `TRUNCATE` | `rollback:` ou `irreversible:` |
| perte de données | `DELETE` | `rollback:` ou `irreversible:` |
| réécriture | `UPDATE`, `MODIFY`, `ALTER COLUMN … TYPE` | `reversible:`, `rollback:` ou `irreversible:` |
| renommage | `RENAME`, `CHANGE COLUMN` | `reversible:`, `rollback:` ou `irreversible:` |

Additif (`CREATE`, `ADD COLUMN`, `INSERT`, index, contraintes) : rien à déclarer.
Supprimer un index ou une contrainte n'est pas une perte.

Les déclarations sont une ligne de commentaire dans la migration :

```sql
-- rollback: R12__restore_note.sql
-- reversible: backfill d'une colonne dérivée, recalculée à chaque écriture
-- irreversible: effacement RGPD de la table historique, aucune copie ne doit subsister
```

- `rollback:` nomme un script placé dans `src/main/resources/db/rollback/`,
  **ajouté dans la même PR**. Flyway ne l'exécute jamais (il est hors de
  `db/migration`) : il sert au retour arrière manuel.
- `reversible:` n'est accepté que pour une réécriture ou un renommage. Une
  suppression demande un chemin de retour, pas une assurance.
- `irreversible:` est une **escalade volontaire** (test 4) : la PR ne sera
  fusionnée que par un humain.
- **Ne jamais modifier ni supprimer une migration existante** : Flyway a
  enregistré sa somme de contrôle. Ajouter une nouvelle migration.

Préférer la forme réversible (expand/contract) :

- **supprimer une colonne** : la release N cesse de la lire et de l'écrire ; la
  release N+1 la supprime, avec un rollback ou une copie de sauvegarde ;
- **renommer** : ajouter la nouvelle colonne, copier, basculer la lecture ;
  supprimer l'ancienne plus tard ;
- **réécrire des valeurs** : copier l'ancienne valeur dans une colonne ou une
  table de sauvegarde dans la même migration ; le rollback la restaure ;
- **supprimer des lignes** : les copier d'abord dans une table d'archive.

### Ce que fait le robot de fusion

`bin/pr-autopilot` passe le contrôle sur chaque PR ouverte, une fois par commit :

| Verdict | Effet |
|---|---|
| ok | armée comme avant |
| déclaration requise / historique réécrit | non armée (désarmée si elle l'était), étiquette `reversibility-declaration-needed`, explication postée une fois ; libérée au commit suivant si c'est corrigé |
| irréversible déclaré | idem, étiquette `irreversible-change`, escalade au Mayor (test 4) ; **jamais fusionnée par l'automatisation** |
| contrôle impossible | non armée ce passage (échec fermé) |

**Tranché (Benjamin, 2026-09-16) :** GUARDED ne s'applique qu'aux migrations
Flyway **non additives** (perte de schéma, perte de données, réécriture,
renommage — le tableau ci-dessus). Une migration **additive** (`CREATE`,
`ADD COLUMN`, `INSERT`, index, contraintes — rien à déclarer) continue de
fusionner automatiquement dès `-Pit verify` vert, comme avant ADR-0019 et comme
`bin/pr-autopilot` le fait déjà aujourd'hui. Le code n'a pas changé ; c'est ce
document qui était en retard sur le comportement réel.

### Changements de comportement — point de revue (non mécanique)

Aucun rig n'a de mécanisme de feature flag, et un diff ne dit pas si un
comportement change. Le relecteur vérifie donc :

- aucun comportement **destructif par défaut** (suppression, envoi, écrasement)
  sans confirmation explicite de l'utilisateur ;
- un changement visible par l'utilisateur est défaisable par un simple revert du
  commit, **ou** la PR dit précisément comment revenir en arrière ;
- sinon, la PR le déclare et c'est une escalade (test 4).

## Observed and proven baseline

- **PROVEN FAST:** M2 bead `af-v7a` used one Codex/Sol writer, deterministic diff validation, commit `77f206a85ab97352aa2e6f9bd2a4f2e653db6d69`, PR #9 and merge `43614760bce9a855a6aeecbfb38090461a905e70`.
- **OBSERVED GitHub (M2, historical):** at M2 this private repository had no Actions workflows and PR #9/#16 reported an empty check rollup. It has since gained `.github/workflows/ci.yml` (`Factory CI`), the required workflow `lib/protected_rigs.sh` names for this repository. Repository rulesets and branch protection are unavailable on the current GitHub plan (API HTTP 403).
- **PROVEN scoped GUARDED gate:** gate `af-q4v` blocked only `af-wisp-2o0m`; independent `af-wisp-r31o` remained visible in `bd ready --include-ephemeral`. After resolution, the guarded bead became ready. All probe artifacts were closed.
- **CONFIGURED STANDARD contract:** target rigs must declare their own deterministic tests and GitHub CI/check requirements before STANDARD delivery is claimed. The Agent Factory repository runs `Factory CI` on its pull requests.

These classifications are deliberately separate: the three contracts are durable and usable, FAST and gate isolation are proven, while target-repository CI remains to be observed during rig onboarding.

## Contrôles `exec` des builds GUARDED

Les contrôles `exec` déclarés par les formules sont résolus par Gas City depuis
la racine du rig cible. Les scripts restent pourtant la propriété du pack
épinglé : les recopier à la main les désynchroniserait au prochain re-pin, et
un script factice qui retourne toujours vrai ferait passer un build sans le
valider.

`bin/factory-build-gates` lit `gc formula list --rig <rig> --json` pour chaque
rig, déduplique les chemins réellement actifs, et matérialise les scripts du
pack résolu pour ce rig. Gas City refuse un lien symbolique présenté comme
contrôle si sa cible sort du confinement du rig : chaque chemin `exec` est donc
une copie locale régulière. Le validateur Python appelé par le contrôle reste,
lui, un lien suivi vers le pack afin de résoudre les schémas voisins ; il n'est
pas lui-même soumis au résolveur `exec`. Copies et dépendance sont suivies par
`.gc/scripts/.factory-build-gates.json`. Cette résolution par rig évite de
réutiliser silencieusement le pack par défaut si un rig a sa propre version.
`factory-boot` le fait avant le démarrage du
contrôleur ; `factory-guard` vérifie et répare ensuite une disparition après un
re-clone ou un artefact géré périmé après un re-pin. `--check-only` ne modifie rien et
sort non-zéro en nommant chaque couple rig/chemin une seule fois. Un fichier
réel déjà présent, ou un artefact géré modifié hors de l'outil, n'est jamais
écrasé silencieusement.

La racine de la cité n'est pas un rig, mais un ticket de la cité elle-même vit
dans son magasin et Gas City y lance les contrôles `exec` depuis cette racine.
Quand la cité possède ses propres contrôles (`assets/scripts/` à côté de ses
`formulas/`), `bin/factory-build-gates` réconcilie donc la racine comme un
magasin de plus, nommé `(city root)` dans les rapports, pour ces contrôles-là
seulement : les contrôles du pack restent ceux des rigs. Le premier est
`.gc/scripts/checks/ticket-author-check.sh`, le contrôle de la formule de
l'auteur (`docs/TICKET_AUTHOR.md`).

Preuve attendue avant de considérer une réparation comme livrée : un build
trivial complet se termine avec `gc.outcome=pass` dans chaque rig, et un
artefact volontairement invalide est refusé avec les erreurs structurées du
validateur. Vérifier seulement que le chemin existe ne prouve pas que le
contrôle s'exécute.

`build-basic` place en plus toute sa chaîne — préparation, exigences, plan,
décomposition, implémentation, synthèse, revue, finalisation et publication —
dans une portée Gas City `build-pipeline`. Chaque étape porte
`gc.on_fail=abort_scope`. Une fermeture dure d'un contrôle (`gc.outcome=fail`,
par exemple `gc.failure_reason=control_dispatch_error`) ferme donc la portée en
échec et ferme les étapes suivantes avec `gc.outcome=skipped` avant qu'un agent
puisse les réclamer ; le finaliseur ferme ensuite la racine en échec. Une
dépendance graph.v2 attend seulement la fermeture de son prédécesseur, pas son
succès : retirer cette portée réintroduirait l'exécution coûteuse des producteurs
et des boucles de revue après un gate en échec. Le test
`tests/build-basic-fail-fast-test.py` verrouille l'enveloppe complète, y compris
les deux variantes de drain et les étapes héritées recopiées localement pour ne
pas perdre leur prompt. Le test local
`tests/build-basic-fail-fast-runtime-test.sh` instancie en plus un graphe dans
une ville isolée, injecte `control_dispatch_error`, exécute les contrôles réels
et prouve que les descendants de revue sont fermés `skipped`, qu'aucune seconde
itération n'apparaît et que la racine se ferme `fail` en deux passes bornées.
La métadonnée portée par l'hôte d'une expansion n'est
pas transmise aux étapes générées : le fork local
`build-basic-review-scoped.formula.toml` place donc aussi la préparation, le
contrôle de boucle et la cible finale de la revue dans `build-pipeline`. Sans
cette seconde protection, une boucle de revue imbriquée déjà matérialisée
pourrait rester exécutable malgré l'échec d'un gate antérieur.

### Drain partagé : un worktree, une branche, une PR

Pour `build-basic --var drain_policy=same-session`, Gas City garantit l'ordre
du drain (`single_lane=true`) et ferme les éléments suivants en `skipped` dès
qu'un élément échoue (`on_item_failure=skip_remaining`). Le contrôleur ne crée
cependant pas le dépôt de travail : `do-work-item` exige à juste titre un
`work_dir` déjà publié sur son source anchor et refuse toute lecture de source
sans lui.

La couche Factory comble uniquement ce raccord. Avant le premier item,
`prepare-shared-worktree` appelle `bin/factory-shared-drain-workspace prepare` :
une branche `build-basic/<workflow-root-id>` et un seul worktree sous
`<rig>/.gc/worktrees/` sont créés, puis leur chemin absolu est écrit sur tous
les source anchors du convoy. Chaque item travaille et commit séquentiellement
sur cette même histoire ; le second voit donc les commits du premier. La revue
lit ce worktree comme source de vérité. L'étape de publication pousse la branche
une fois et crée ou réutilise une seule PR, jamais une PR par item.

Après succès ou échec de la portée, `cleanup-shared-worktree` est un teardown :
il retire le worktree enregistré et efface les `work_dir` correspondants. Il ne
supprime jamais un worktree sale ; dans ce cas il conserve les éléments de
récupération et enregistre `preserved_dirty`. Une branche locale propre reste
récupérable même si `push=false`, mais aucun worktree ne reste pour épingler une
branche fusionnée. Le mode `drain_policy=separate` demeure inchangé : chaque
item continue d'utiliser le cycle Gas City `do-work`.

Preuve déterministe : `tests/factory-shared-drain-workspace-test.sh` construit
un dépôt et un convoy jetables de deux items dépendants, vérifie le chemin
partagé, l'ascendance des deux commits, le contrat de saut sur échec, l'unique
PR, le retrait du worktree et l'absence de changement du drain séparé. Ce
raccord supprime les reprises manuelles après l'erreur « source anchor has no
work_dir metadata » et remplace jusqu'à N worktrees/PR par un seul pour N items,
sans coût modèle supplémentaire pour le cycle Git.
