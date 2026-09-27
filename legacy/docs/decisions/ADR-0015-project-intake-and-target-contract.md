# ADR-0015: Project intake, declared autonomy, and the upstream half of the release contract

- Status: Accepted
- Date: 2026-09-15
- Accepted: 2026-09-16 by Benjamin in conversation, after arbitrating every open
  question (autonomy `L3`, assumptions over stalling, no spend ceilings, neither
  code nor intent winning a takeover conflict, separate clarification
  accounting, skill registry deferred, contract stays `v1`). See the arbitration
  record at the end.
- Implementation: NOT STARTED. This ADR is specification; the Mayor owns any
  work that follows.
- Supersedes: nothing. Extends ADR-0014 (versioned product release contract),
  ADR-0013 (Mayor-owned continuous campaign), ADR-0011 (decision workspaces),
  ADR-0006 (token-free human cockpit).

## Context

ADR-0014 gave the Factory a versioned, evidence-backed description of a target
once the target is already known: capabilities, journeys, scope, dependencies,
decisions, criteria, `work_graph`, maturity, and the
`draft → approved → executing → frozen` lifecycle. `select_campaign_work`
turns that document into exactly one safe unit of work at a time.

Nothing describes **how a target comes to exist**. Today a human writes
`config/releases/<product>-<version>.json` by hand after the target is already
clear in his head. That works for SayMyName V1, where Benjamin *is* the domain
knowledge. It does not work for the stated objective: the Factory should take a
user project — from a bare idea to a codebase already half-built by someone
else — and carry it to a target, the way a consultancy takes over a client
project: few questions, well chosen, a lot of autonomy.

Two failure modes bound the design.

1. **Interrogation.** A system that asks the human everything it does not know
   is a worse-than-useless consultant. Every question is a cost and a stall.
   Autonomy is an explicit product objective, not a tolerance.
2. **Invention.** A system that asks nothing invents the target, and the
   invention only surfaces after the work is done. ADR-0014 already refuses
   bare claims for *evidence*; the same refusal must apply to *intent*.

The resolution used here is that the opposite of a question is not silence, it
is a **recorded assumption**: typed, attributed, visible in the doc, refutable
in one click, and automatically promoted to a decision when evidence
contradicts it. Assumptions are how the question count goes down without the
truth going soft.

## Decision

### 1. One contract, extended — not a second document

The intake phase lives in the **same** versioned Git document as the release,
under the same `config/releases/` path and the same pure module. The contract
identifier **stays `agent-factory-product-release/v1` with `schema_version: 1`**
*(Benjamin, 2026-09-16)*. The Factory is not published, so there is no external
reader to keep compatible, and the only consumers are in-repo:
`lib/product_release.py`, `lib/factory_cockpit.py`, `lib/factory_campaign.py`,
`bin/product-release`, the tests, and exactly one document,
`config/releases/saymyname-v1.json`.

That has a consequence worth stating, because it is better than the alternative
that was on the table: since nothing external reads the contract, the new fields
do **not** have to be optional. They are added as **required**, and the single
existing document is migrated in the same change. An optional-everything
extension would have left the contract permanently unable to assume its own
shape — validation would have had to tolerate a document with no `objective`,
no `origin` and no `autonomy` forever. Extending in place with required fields
keeps `validate_release_contract` fail-closed, which is the property the whole
design rests on.

`config/product-release.schema.v1-extended.draft.json` in this proposal is that
extension, not a second contract: on acceptance of the implementation work it
replaces `config/product-release.schema.json` outright. Migration of
`saymyname-v1.json` sets `origin.kind = "takeover"`, `intake.state =
"complete"`, empty `assumptions`, `revision = 1`, `autonomy.level = "L3"`, and
the `objective` statement Benjamin writes. `lib/product_release.py` keeps its
property of reading no live state, writing no file, and calling no model.

Rejected alternative: a separate `config/targets/<project>.json` with its own
contract. It reintroduces exactly the four-independently-drifting-shapes
problem ADR-0014 removed: the intake target and the release target would
disagree the first time scope changed, and `select_campaign_work` would need
to know which one is true.

The lifecycle gains one state at the front:

```
intake → draft → approved → executing → frozen
```

`intake` is fail-closed for execution: `select_campaign_work` on an `intake`
release returns `release_not_executable` exactly as it does for `draft`.
`transition_release` keeps its existing semantics (idempotent same-state,
fail-closed on skip or backward move); `intake → draft` additionally requires
`intake.state == "complete"`, so an unfinished intake can never be approved.

### 2. Structured intake: discovery first, then at most five questions

Intake runs in four ordered passes. The human enters at pass 3 and only there.

**Pass 1 — Deterministic discovery (0 model calls).** The Factory reads what
already exists and records it under `origin.discovery` with
`method = "deterministic_scan"`: repository inventory, languages and build
files, routes and endpoints, data schema and migrations, test and CI
configuration, README/ADR/doc files, open issues and recent commit shape. For
a greenfield project this pass produces an empty-but-explicit finding set. No
question has been asked yet and no model has been called.

**Pass 2 — Model-assisted drafting (bounded, one call budget).** From the
statement of intent plus the discovery findings, the Factory drafts the whole
contract document: capabilities, journeys, included/excluded, dependencies,
criteria with human-observable `acceptance` statements, and a first
`work_graph`. Everything it could not establish from evidence is written as an
`assumption` with `status = "standing"` and an explicit `confidence`, never as
a silent default and never as a question.

**Pass 3 — The questions that survive (human).** A candidate question is
*asked* only if it satisfies one of two tests, evaluated mechanically:

- **Reserved test** — it belongs to the reserved classes below. Always asked,
  regardless of budget or autonomy level.
- **Leverage test** — the answer changes the identity or order of at least one
  of the first three nodes of the `work_graph`, or changes whether a criterion
  can be proven at all. Formally: the question is asked only if two admissible
  answers produce two different `select_campaign_work` selections over the
  next three selections.

Everything failing both tests becomes an assumption. The budget is hard:
**at most 5 questions on the first pass, at most 2 per later iteration**,
tracked in `intake.question_budget`. Reserved questions are counted but never
suppressed by the budget — if reserved questions alone exceed 5, they are all
asked and the leverage-test questions are dropped. When the budget is
exhausted and the exit criteria are still unmet, the Factory proceeds on
standing assumptions and says so loudly in the derived doc; it does not stall
and it does not demand a sixth question. *(Settled by Benjamin, 2026-09-16:
`question_budget.on_exhausted = "proceed_on_assumptions"`.)*

**Pass 4 — Exit, deterministically checked.** `intake.state` becomes
`complete` only when all of the following hold — computed, not asserted:

1. every `criteria[]` item has a non-empty human-observable `acceptance`;
2. every criterion is referenced by at least one `work_graph` node, and every
   `work_graph` node references at least one criterion;
3. every reserved question has `status = "answered"` with an `answer_ref`;
4. `maturity.criteria` references only existing criteria;
5. every `assumption` with `confidence = "low"` that is referenced by a
   first-order (`depends_on == []`) work node has been either confirmed,
   refuted, or promoted to a `decision`;
6. the existing `validate_release_contract` semantic checks pass (no dangling
   refs, no duplicate ids, no `work_graph` cycle, no self-dependency, no
   Factory-kind work recorded as a product capability).

Intake is therefore *finishable by the system* and *not* finishable by
assertion.

### 3. Reserved questions — the invariant autonomy cannot touch

These classes are always asked of the human and can never be answered by an
assumption, at any autonomy level. They mirror the decision tiers already in
force for SayMyName (`CLAUDE.md`, `DESIGN_GOVERNANCE.md`):

| class | covers |
| --- | --- |
| `outcome` | what "done" means for this version; the release's own definition of success |
| `identity_and_consent` | navigation, invitation, consent, exposure of personal data |
| `irreversible` | production data, destructive migration, public publication, anything not undoable |
| `money` | pricing, spend, purchase, contractual commitment |
| `authority` | who may approve on the human's behalf; who owns the product |
| `legal` | licensing, regulatory or contractual constraints |

`autonomy.level` governs **how much is asked**, never **what may be skipped**.
A level can only enlarge the set of questions asked, never shrink the reserved
set. This is the single invariant that makes a high autonomy level safe to
grant, and it should be enforced in `validate_release_contract` rather than
left to convention.

### 4. Declared autonomy

A level does not describe how capable the Factory is. It describes **when it
stops to talk to the human**. Same contract, same machinery, four stopping
points:

| level | the Factory may | it stops for | what it feels like |
| --- | --- | --- | --- |
| `L0` observe | read the project, scan the code, draft the target and a work graph. Executes nothing. | everything | An audit. A documented target, zero lines of code. |
| `L1` assisted | all of that, plus execute — but it comes back before **every** materialization | every ticket before it starts, plus the reserved classes | Roughly SayMyName today: approval result by result. |
| `L2` delegated | chain work continuously inside the **already-approved** target without re-asking per node | the reserved classes only | The target is approved once; afterwards the human only hears from the Factory when it hits a real decision. The only level at which "continuous campaign" means anything. |
| `L3` autonomous | additionally revise the target itself and open the next version, inside an objective the human froze | the same reserved classes, never fewer | "SayMyName must be usable by a real cohort" — the Factory decides on its own that this means V1 then V2, and rewrites its own release contract in between. |

The `L1 → L2` difference is **how often it interrupts**. The `L2 → L3`
difference is **who may change the target**. In neither case does the reserved
set shrink: raising autonomy removes non-reserved questions only.

**Granted level: `L3` (Benjamin, 2026-09-16).** Two constraints come with it,
and neither is a discount on the grant.

*Freezing stays human.* `start_next_version` freezes the current release
permanently — ADR-0014 makes a frozen release immutable forever. Permanent
irreversibility is the `irreversible` reserved class by definition, so at `L3`
the Factory may revise the target as often as it likes **inside** a version,
but declaring the version reached, freezing its evidence, and opening the next
one requires one human confirmation. That is one confirmation per *version*,
not per ticket and not per revision, and it rules out the single genuinely
costly failure: partial evidence frozen beyond recovery.

*L3 needs a ceiling the Factory may not move.* "Revise the target freely" is
unbounded unless something above the target is fixed. The contract therefore
gains `objective`: the human's durable statement of what the product must
become, recorded verbatim, readable by the Factory and **not writable by it**
at any autonomy level. A revision that would contradict `objective` is not a
revision — it raises a reserved `outcome` decision. `L3` means the Factory owns
the route; the human still owns the destination.

Recommended default for a new project: **L2**. `L2` is what makes a continuous
campaign meaningful; `L1` reproduces today's ticket-by-ticket approval, `L3`
lets the system change its own target and should be a deliberate grant. The
grant is recorded with `granted_by` and `granted_at`, is per-project, and is
itself a reserved (`authority`) question. *(Q1.)*

### 5. Assumptions as first-class, refutable objects

```
standing → confirmed          (evidence arrived and agreed)
standing → refuted            (evidence arrived and disagreed)
standing → promoted_decision  (the human overturned it, or it blocked work)
```

An assumption carries `invalidated_by`: typed evidence references whose
arrival forces re-evaluation. When an assumption is refuted, every criterion
and work node in its `scope_refs` is marked for re-derivation and the Factory
raises exactly one `decision_required` — it does not silently re-plan. The
evidence status enum gains `assumed`, so the doc can show at a glance which
part of the target rests on the Factory's own inference rather than on proof.

This is the mechanism that makes "few questions" honest: nothing is guessed
invisibly.

### 5b. Takeover conflict: neither code nor intent wins by default

*(Settled by Benjamin, 2026-09-16.)*

When deterministic discovery finds that the existing codebase contradicts the
stated target — the code does X, the human's `origin.statement` says the target
is not-X — the Factory **does not resolve it**. Neither source is given
priority: a rule that says "the code wins" silently ratifies whatever the
previous team built, and a rule that says "intent wins" silently orders a
rewrite nobody costed.

Each contradiction is recorded in `origin.conflicts[]` and raises exactly one
`decision` of reserved class `outcome`, with three fixed options:

| option | meaning |
| --- | --- |
| `keep_target` | the target stands; the existing code is what must change |
| `adapt_target` | the target bends to what already exists |
| `mix` | part of the target stands, part bends — the answer names which |

Because the class is `outcome`, this is a reserved question: it is always asked,
it can never be answered by an assumption, and intake cannot complete while one
is unanswered. This is the one place where a taken-over project deliberately
costs a question rather than saving one — the alternative is an entire campaign
executed against a target the human never actually agreed to.

### 6. Derived interactive documentation — still zero token to read

`project_target_doc(value) -> dict` is added to `lib/product_release.py`:
pure, deterministic, model-free, a projection of the contract exactly like
`project_release`. The cockpit renders it statically. The doc offers:

- **Graphs**, all derived from data already in the contract: journey →
  capability → criterion → work; the `work_graph` DAG with dependency edges;
  the assumption overlay (which part of the target is `assumed`); the blocker
  subgraph (what one decision is actually holding).
- **Progress**, by joining `work_graph[].work_ref` to the Beads/GitHub state
  the cockpit collector already reads. Reading live state is a data read, not
  a model call: the 0-token contract is preserved.
- **Linked tickets**, per node and per criterion, with their PR/CI evidence.
- **One clarification button**, per element. It is the *only* path that spends
  a token, it is always an explicit human click, it routes through the
  existing ADR-0011 decision workspace and the PO bridge so the spend is
  attributed, and its output may only land as (a) a doc annotation or (b) a
  `decision_required`. A clarification may never mutate the contract directly.

No new UI surface: this is a panel of the existing Produit view, which already
declares `DOCUMENTATION INTERACTIVE · Lecture · 0 token`.

### 7. Continuous campaign: stop conditions, budget, live re-targeting

**Stop conditions** extend the typed reasons `select_campaign_work` already
returns. The campaign runs until exactly one of:

| reason | meaning |
| --- | --- |
| `release_target_proven` | every criterion `proven` — the release is reached |
| `all_remaining_blocked_by_decision` | no runnable node; every remaining one is blocked by a human decision |
| `blocked_admin` / `blocked_limit` / `blocked_durable_failure` | existing typed blocks |
| `intake_incomplete` | `intake.state != "complete"` |
| `provider_quota_exhausted` | every configured provider is out of quota — a switch first, a stop only as a last resort |
| `no_progress` | the anti-idle guard below |

`all_remaining_blocked_by_decision` is the condition Benjamin asked for: it
must be distinguishable from "one thing is blocked". A single decision blocker
stops only its own subgraph (ADR-0014 already guarantees this); the campaign
stops only when the *unblocked* candidate set is empty. Note what is **not** in
the table: there is no "the version took too long" stop. A version stays open
until it is released *(Benjamin, 2026-09-16: V1 stays open as long as needed
until release; a finer versioning scheme comes later, once there is something
released to version).*

**No spend ceiling.** *(Settled by Benjamin, 2026-09-16: token and wall-clock
ceilings are removed.)* The earlier draft proposed `tokens_max` and
`wall_clock_max_minutes`. They are wrong for this operator and the objection
that killed them is correct: the subscriptions in use (Codex Pro ×5, Claude
Max ×5) are flat-rate, so a token is not money — it is quota in a rolling
window. A spend ceiling therefore protects nothing, while being perfectly
capable of stopping a campaign at 90% of the result. A budget that prevents
the result is a defect, not a safeguard. The goal is the result.

**The loop guard stays, and it is not a budget.** `max_consecutive_no_progress`
(default 3) does not stop a campaign that advances expensively; it stops one
that does not advance at all. **Progress is measured on the contract, not on
activity** — an iteration counts as progress only if a `work_graph` node
changed state or an evidence `status` changed. Three consecutive selections
with no contract-observable change stop the campaign with `no_progress` and a
typed cause. An agent that is busy and moves nothing is, by this definition,
not working; without the guard, one flaky test burns the whole rolling window
and takes the rest of the work down with it.

**The scarce resource is provider availability, not tokens.** The typed stop
`provider_quota_exhausted` should, by default, not stop the campaign at all: it
switches provider through the multi-provider mechanism that already exists
(`city.toml` `[providers.*]`, per-agent `agent.toml`) and only stops when every
configured provider is exhausted. Operational consequence worth stating: with
two ×5 subscriptions there is a fallback; consolidating to a single ×20 removes
it, and `provider_quota_exhausted` becomes a real stop rather than a switch.

**Clarification spend is accounted separately.** *(Settled by Benjamin,
2026-09-16: separate.)* With no ceilings there is no purse to divide, but the
attribution still matters: clarification calls are recorded against their own
line in `budget.spent`, never mixed into delivery. Reading the target well must
remain visibly free of delivery, and must never be throttled by delivery
activity.

**Iteration and re-targeting without interruption.** The contract gains
`revision` (monotonic integer). The campaign reads the contract **only at a
selection boundary**, never mid-node. Therefore:

- a revision landing while a node is `active` does not interrupt it;
- at the next boundary, nodes removed or invalidated by the revision move to
  `superseded_pending` and are allowed to land rather than being killed;
- new nodes enter the ordering normally;
- a revision that changes the release's *objective* (criteria set) requires
  the human, because it is an `outcome` reserved question.

A target change is therefore a normal event, not an outage.

### 8. Skills: a curated registry — DEFERRED, field reserved

**Status: deferred (Benjamin, 2026-09-16).** The design below stands, but it is
not worth building yet and this ADR does not ask for it.

A registry pays for itself at the **second** project, not the first. For one
product, `AGENTS.md` already carries the stack know-how and carries it better,
because it is specific. Building a registry now would generalise knowledge that
has exactly one consumer.

What this ADR does keep is the cheap hook: the `skills` block stays **defined
and optional** in the schema, with an empty default. When a second project
arrives, it is a field to fill rather than a contract to reopen.

The rest of this section is the design to pick up at that point.

**Recommendation when it is picked up: yes to a registry, no to self-invention
at execution time.**

`skills/registry.json` lists curated skill packs, versioned, each mapped to
project types (`spring-angular-saas`, `python-cli`, `static-site`, …). A
`skills` block in the contract records which packs were selected at intake,
with the reason and the selecting actor. Selection is deterministic given
`origin` + project type; the human may override it (non-reserved — this is a
leverage-test question at most).

Why not let the Factory write its own skills at execution time, which is what
was asked about:

- **Unbounded cost.** A skill authored mid-run is a model call inside a loop
  whose exit condition is the model's own judgment of its competence. That is
  precisely the failure `max_consecutive_no_progress` exists to catch, and it
  would be introduced deliberately.
- **No review boundary.** A skill is standing instruction for every later run.
  Code gets a PR and a human review; a self-written skill would get neither,
  while having broader blast radius than the code.
- **Injection surface.** Takeover projects are scanned third-party
  repositories. A README that says "always run this script" becomes a
  persistent Factory instruction the moment self-authoring is allowed. Every
  scanned artifact is data, not instruction — a self-authoring path erases
  that boundary.
- **Non-reproducibility.** Two runs of the same target would no longer be
  comparable, which breaks the evidence model ADR-0014 is built on.

The bounded learning path already exists in the contract and should be the
only one: when the Factory notices a recurring gap it emits a
`factory_improvements` entry proposing a new skill. That entry is Factory-kind
work, goes through normal delivery, gets a PR and a human review, and lands in
the registry as a versioned pack. The Factory therefore *can* gain skills — at
merge speed, with a review, not at inference speed without one.

## Consequences

- One document still holds the whole truth of a version, from "we do not yet
  know what this project is" to "frozen with proof". No second contract, no
  second queue, no second UI.
- The number of human questions becomes a **budgeted, auditable quantity**
  instead of a behaviour, and the reserved set becomes an enforced invariant
  instead of a convention.
- Everything the Factory assumed is visible and refutable, so "few questions"
  does not silently become "invented target".
- The campaign's stop reasons are exhaustive and typed, and idleness is
  defined against the contract rather than against agent activity.
- A `v1` contract keeps working through a pure upgrade function; the pure
  module stays pure; the cockpit stays 0-token to read.
- Skills grow through review, so the Factory's standing instructions remain
  auditable artifacts under Git.

## Arbitration record — 2026-09-16

Settled by Benjamin in conversation, folded into the sections above:

| | question | decision |
| --- | --- | --- |
| Q2 | budget exhausted, intake incomplete | **proceed on standing assumptions**, say so loudly, never stall |
| Q3 | takeover, code contradicts intent | **neither wins** — raise one reserved `outcome` decision with options `keep_target` / `adapt_target` / `mix` |
| Q4 | spend ceilings | **removed.** Flat-rate subscriptions mean a token is quota, not money; a ceiling can stop a campaign short of the result. The `no_progress` loop guard stays, and `provider_quota_exhausted` switches provider before it stops anything |
| Q5 | clarification spend | **accounted separately** from delivery, and never throttled by it |
| Q1 | default autonomy level | **`L3`** — the Factory owns the route. Two constraints attach: freezing a version stays one human confirmation (permanent irreversibility), and a new `objective` field, writable by the human only, bounds what the Factory may revise toward |
| Q6 | skill registry | **deferred.** A registry pays off at the second project; `AGENTS.md` already covers the first. The `skills` block stays defined and optional so it is a field to fill later, not a contract to reopen |
| — | version duration | a version stays open until released; a finer versioning scheme is deferred until something has been released |

## Nothing left open

Every question this ADR raised was arbitrated by Benjamin on 2026-09-16, in
conversation, and folded into the sections above. The last one, the contract
version, was settled by extending `v1` in place — see section 1.

Two things are deliberately *not* recorded here and must not be invented later:

- **`objective.statement` for SayMyName is not written yet.** It is the human's
  verbatim sentence and belongs to the `outcome` reserved class. Nobody but
  Benjamin writes it.
- **Nothing was added to `docs/products/saymyname/DECISIONS.md`.** This is a
  structural Factory decision, so an ADR is its home; the product decision
  register stays for product truth.

## Intake protocol v1 — dry-run validated 2026-09-16

Superseded for future intakes by **Intake protocol v2** below. Left in place,
not deleted, because it is the historical record v2 was built from — same
non-destructive supersession rule `DECISIONS.md` uses for its own entries.

This section is the concrete interaction procedure this ADR's schema needs to
actually run. It is versioned on its own (`v1`), separately from the contract
schema version, so a different protocol can be tried later against the same
contract shape without reopening this ADR's decision.

**Procedure:**

1. **Minimal input.** A one-line pitch, plus (for a resumed project) the
   existing repository and durable docs. Nothing else is asked up front.
2. **The AI drafts the full canvas alone** — objective, primary user, non-goals,
   MVP, evolution horizon, references, differentiation, existing-code stance,
   hard limits, autonomy level — by reading what exists, not by interviewing.
3. **Each field is tagged**, against objective tests rather than a judgment
   call:
   - widens who sees real personal data → `à trancher`
   - involves money, a real third party, or publication → `à trancher`
   - irreversible within the current version → `à trancher`
   - otherwise → `déduit`: decided now, recorded with its basis and its
     reversal, same as any other delegated decision under ADR-0016
4. **One human reading pass**, on the `à trancher` fields only, each with a
   recommendation already attached so the human confirms or corrects rather
   than drafts from nothing.
5. **Execution is gated**: nothing starts before this pass is confirmed
   (`intake` precedes `draft`, per this ADR's lifecycle).
6. **A resumed project ports, it does not re-litigate.** Existing durable
   decisions (`OBJECTIVE.md`, `DECISIONS.md`, `PRODUCT_STRATEGY.md` or
   equivalent) are read in full — not sampled from the tail of a file — and
   carried into the new contract fields as already-answered. Only fields the
   old format never had are asked fresh.

**Dry run on SayMyName, 2026-09-16 — what it found:**

Applied by hand (no tooling yet) against `docs/products/saymyname/DECISIONS.md`.
First pass read only the file's trailing `## Open` list and proposed fresh
answers for all nine items — step 6 was skipped, the file's body was not read
in full. Second pass read the whole file and found seven of those nine already
`Accepted`, dated 2026-09-14/15, and better-specified than the fresh answers
just proposed (concrete thresholds and figures where the redo offered generic
ones). Only one item was genuinely open, and it already had its own entry
saying so. Cleanup recorded in `DECISIONS.md` under `## Superseded`,
2026-09-16.

**What this validates and what it corrects:**

- The tag mechanism (step 3) worked: every genuinely `à trancher` field in the
  dry run was one that touched a real third party, money, or entry into the
  `piloted` stage — exactly the intended trigger, nothing over- or
  under-flagged.
- Step 6 is upgraded from a preference to a hard rule after this run: **read
  the full durable document before drafting, never the tail alone.** A partial
  read looks identical to a clean deduction until it collides with an existing
  decision, which is the failure mode this run hit.
- Confirms a boundary from the standing delegation
  ([[agentfactory-standing-delegation]]): fields that resolve to `déduit`
  under the tests above are still decided *incrementally*, one item at a time,
  not batched into a heavier "resolve everything now" pass — the batch is what
  produced the duplicate-decision risk here.

## Intake protocol v2 — checklist form, 2026-09-16

Supersedes v1 above for future intakes. Protocol versions stay independently
versioned from the contract schema (v1's own note still holds), so a v3 can be
tried later and compared against both without reopening this ADR.

### Job to be done

Stated in the same shape this version now requires of a product's own
`objectif` field (see Basic, Draft): when a project starts or resumes, and its
target must be cadenced with the fewest possible questions without losing
quality, this protocol produces a confirmed target contract, so execution can
begin without guessing at the target or re-asking the human something already
decided.

### Why a checklist, and why tiered

v1 stated its rules in prose — "read the whole document before drafting" —
and the dry run broke that exact rule anyway. A checklist forces consistent
application of what is already known; prose reminders do not (Gawande, *The
Checklist Manifesto*: expert failure is usually inconsistent application, not
ignorance — cited effect: 47% fewer surgical deaths with a checklist in place).

The steps are tiered the way the Kano model tiers a product's own features —
basic, performance, conditional — applied here to the protocol's steps
instead of a product's:

- **Basic** — absence breaks the protocol; always required.
- **Performance** — rigor scales with what is at stake; full weight on
  structuring or irreversible-adjacent fields, light elsewhere.
- **Conditional** — only in a specific circumstance.
- **Not included** — considered, and kept out on purpose; recorded so a later
  reader does not re-litigate it from a blank page.

### Basic — always required

**Bootstrap**
- [ ] One-line pitch obtained.
- [ ] If resuming a project: every durable target document is located by
      scanning section headers first (`grep '^## '` or equivalent) — never by
      sampling the tail of a file.
- [ ] Each located document is read **end to end**; the count of sections
      read is checked against the header-scan count, not assumed. This is the
      exact step that failed on the SayMyName dry run — v1 stated it in
      prose and the rule was broken the same day it was written.

**Draft** (the AI alone, no human input yet)
- [ ] `objectif` is written as *circumstance → sought progress*, not a
      feature list (Christensen, Jobs to Be Done). Benjamin's own
      `OBJECTIVE.md` for SayMyName already has this shape without having been
      asked to; this makes it the required shape for every future project.
- [ ] All ten canvas fields are drafted.
- [ ] Every field that will be tagged `déduit` carries an exact citation —
      file and line, a direct quote, or a named external reference. No
      citation, no `déduit` tag: it defaults to `à trancher`. (Citation
      grounding measurably cuts hallucination in document-grounded LLM
      answers.)

**Tag**
- [ ] Each field is tested against the three objective triggers already in
      v1: widens who sees real personal data; involves money, a real third
      party, or publication; irreversible within the current version. Any
      trigger firing → `à trancher`. None firing and a citation exists →
      `déduit`, decided now with its basis and its reversal.
- [ ] A fourth tag, `deferred`: a field whose answer only matters once a
      later, not-yet-reached project phase actually starts (e.g. a
      go-to-market question asked during a pre-release build) is tagged
      `deferred`, not `à trancher`. It is not asked, decided, or acted on
      before that phase begins, however confident a recommendation could be.
      Added 2026-09-16 from a real failure on SayMyName: several
      Enterprise-tier decisions (pilot recruitment, pricing, brand) had been
      answered early by accepting the first offered recommendation, or by an
      answer that did not really engage the question — not because the
      recommendation was bad, but because the question was asked before it
      was load-bearing. The fix is not a better recommendation; it is not
      asking yet. A `deferred` field is re-tagged, not silently dropped, the
      first time the intake procedure runs again after that phase begins.

**Verify** (independent, before the human sees the draft)
- [ ] A separate reasoning pass re-derives each `déduit` field from its cited
      source **alone**, without access to the drafted answer, then compares
      the two. (Dhuliawala et al., *Chain-of-Verification*, arXiv:2309.11495 —
      the factored/independent variant, where verification does not condition
      on the original draft, outperforms a verifier that can see it first.)
- [ ] The verifier is explicitly instructed and permitted to overturn the
      draft; a mismatch is corrected or downgraded to `à trancher`, never
      smoothed over. (Multi-agent debate research: majority and anchoring
      pressure suppress independent correction unless the setup is
      structured against it.)
- [ ] For a resumed project specifically: this pass reconciles every `déduit`
      answer against the **entire** existing decision register, not a
      section of it. This is the exact check that would have caught the
      SayMyName dry-run duplication before it reached Benjamin.

**Human pass**
- [ ] Only `à trancher` fields are shown, each with a recommendation already
      attached.
- [ ] No field is ever phrased as an open or yes/no question. Requirements-
      elicitation research names two reasons: the "why-not mentality" (people
      default to yes when a request carries no perceived cost) and
      social-desirability bias (answers skew toward what sounds reasonable to
      the asker), both of which a direct ask triggers and a recommendation-
      to-correct does not.

**Gate & record**
- [ ] Execution does not start before this pass is confirmed (`intake`
      precedes `draft` in this ADR's lifecycle, unchanged from v1).
- [ ] Every `déduit` decision is recorded with basis, citation and reversal,
      exactly like any other delegated decision under ADR-0016.
- [ ] The protocol version used is recorded alongside the contract.

### Performance — rigor scales with what is at stake

- [ ] Structuring `déduit` fields — the ones that condition many other
      decisions, such as an architecture choice or a selected connector —
      get a short pre-mortem before being finalized: imagine this choice has
      already failed, and write down why. (Klein, *HBR* 2007, grounded in
      Mitchell/Russo/Pennington 1989: imagining failure first finds ~30% more
      of the real causes than asking "will this work?".) Applied to every
      field, this would be a heavier ritual than the decision deserves; kept
      to structuring fields only, it stays cheap.
- [ ] The `assumptions` block already in this ADR's schema places each entry
      on an impact × confidence map; a high-impact, low-confidence assumption
      is resolved — by research or a cheap test, not necessarily by building
      — before anything is built on top of it. (Riskiest Assumption Test /
      Lean Startup assumption mapping.)
- [ ] MVP feature candidates are tiered basic / performance / delighter
      rather than listed flat, and re-tiered at each version — a delighter
      decays into a baseline expectation over time. (Kano, 1984.)
- [ ] For a field genuinely without a confident recommendation, up to **two**
      "why" follow-ups are allowed to reach the real reason behind a stated
      preference before recording it — never more, so the question budget
      stays intact. (Laddering / means-end chain interviewing.)

### Conditional — only when it applies

- [ ] **Fresh project, no existing durable docs to deduce from**: draft a
      short mock announcement of what the product delivers, plus an
      anticipated-objections FAQ, before drafting `objectif`/`MVP` from it.
      If it is hard to write clearly, the target is not defined yet — a
      cheap diagnostic, not a document to maintain going forward. (Amazon
      "working backwards" PR/FAQ.) Skipped entirely for a resumed project —
      its `objectif` already exists and must be ported, not re-derived.

### Not included — considered, kept out on purpose

- **Reference class forecasting** (correcting an estimate by comparing it to
  a class of already-completed similar projects, rather than reasoning from
  inside the project being estimated; Kahneman & Tversky, endorsed by the
  American Planning Association) is sound in principle but inapplicable
  today: the Factory has completed one product, which is not a reference
  class. Writing it into this protocol now would recreate the exact failure
  this version exists to fix — a step nobody can apply and nobody notices
  going stale. It is deliberately **not** part of this protocol. The
  condition to reconsider it (2-3 completed projects) is tracked in session
  memory instead of here, so it resurfaces on its own trigger rather than
  rotting in an ADR as another unchecked box.

### Sources

Requirements elicitation and bias: Springer, *Elicitation Revisited for More
Inclusive Requirements Engineering*; LinkedIn/Smponias, *Why Asking Isn't
Enough*. Pre-mortem: Klein, *Performing a Project Premortem*, HBR 2007;
Mitchell, Russo & Pennington (1989) on prospective hindsight. LLM
verification: Dhuliawala et al., *Chain-of-Verification Reduces Hallucination
in Large Language Models*, arXiv:2309.11495; multi-agent debate literature on
majority/anchoring pressure. Checklists: Gawande, *The Checklist Manifesto*.
Amazon PR/FAQ: *Working Backwards* (Bryar & Carr). Reference class
forecasting: Kahneman & Tversky on the planning fallacy; Flyvbjerg on
reference class forecasting in practice. Kano model: Kano (1984). Jobs to Be
Done: Christensen. Riskiest Assumption Test: Lean Startup assumption-mapping
literature. Laddering: means-end chain interviewing (Reynolds & Gutman).
