# SayMyName design governance

## Default: code-first, system-first

The product repositories are the implementation truth. Maintain a small set of
versioned design tokens, reusable components, interaction/state rules, responsive
breakpoints and accessibility constraints. New work reuses these primitives and
includes realistic loading, empty, error, permission and recovery states.

Figma is optional, not the default state store. Use it for a genuinely ambiguous
new journey, brand exploration, or a high-impact interaction that Benjamin and
the PO need to compare before implementation. If a stable shared component
library later exists, Figma Variables and Code Connect/MCP may mirror code tokens
and components; they must not create a second conflicting design system.

## Design loop

1. PO defines the user, job, outcome, constraints and acceptance evidence.
2. A bounded UX role inventories existing patterns and produces the smallest
   inspectable flow: annotated states in code by default, Figma only when useful.
3. The decision rule below is applied before the Mayor receives the outcome.
4. Mayor owns delivery; implementation uses the approved system and states.
5. Automated checks cover types, tests, accessibility rules, responsive layout
   and visual regressions where stable. A human checks only the risky difference.

## Standing delegation

Benjamin delegated design decisions to the PO and the Mayor on 2026-09-16, in
conversation, so that the factory can run unattended for hours without a planned
handover. The delegation is permanent until Benjamin revokes it here, and every
decision taken under it is recorded and reversible.

**Decisions are taken by the AI from Benjamin's declared objectives, never from
improvisation.** The basis is read in this order, most specific first:

1. `OBJECTIVE.md` — Benjamin's verbatim sentence, writable by him alone. Moves
   into the release contract's `objective.statement` once ADR-0015 is
   implemented. **SET on 2026-09-16.** It wins on conflict with every source
   below it; a decision that would contradict it is not a decision, it is an
   escalation. Its `What each clause settles` table is PO text recording how the
   clauses apply, not part of the statement and never a substitute for it.
2. `DECISIONS.md` — accepted decisions, the most recent wins on conflict.
3. `PRODUCT_STRATEGY.md` — thesis, roadmap order, and the explicitly deferred or
   prohibited list.
4. The release contract's `criteria`, `included` and `excluded`.
5. The tie-breakers below, when all four are silent.

**Tie-breakers, in order.** When the basis does not settle a choice, prefer:

1. **what comparable products do** — Benjamin's standing rule, 2026-09-16: "il
   faut faire le même choix que mes concurrents feraient." It applies to
   user-visible behaviour where the category already has a settled convention:
   deletion and recovery, export, sign-in, notification, empty states, error
   recovery, pricing shape. Parity is the default because a user arrives with
   expectations formed elsewhere, and spending originality on a solved
   mechanic costs attention that belongs to the product's real difference.
   **Qualification, added by the PO and open to Benjamin's rejection:** parity
   does not apply to what SayMyName is differentiating on — what the learner
   chooses to memorise, how practice and recall work, and the guarantee that a
   person's selections are never exposed to anyone else. Copying a competitor
   there would copy away the product. When the two readings conflict, say so
   and escalate rather than guessing which one is meant;
2. the more reversible option;
3. reuse of something already shipped and tested over a fork or a rewrite;
4. the narrower data exposure;
5. the smaller slice that can be proven now over the larger one that cannot;
6. the design-ready contract's own recommendation, when it satisfies 1-5.

## The decision rule

A design decision is **taken by the AI, recorded, and delivery continues** —
unless it fails one of the four escalation tests below.

This is a test of **effect**, not of category. The previous approval tiers
escalated whole subjects — "personal data", "invitation", "destructive action" —
and nearly every real feature touches one of those words nominally, which is why
the factory stopped on almost every journey. What matters is whether this
specific decision actually exposes something to someone new, or actually
destroys something that cannot be recovered.

**The tests are evaluated against the environment stage, not in the abstract.**
Benjamin, 2026-09-16: while the product is in full development, changing who
can see personal data harms nobody, because there is no real person's data to
harm. The stage is declared here and is the only thing that decides how tests 1
and 2 are read:

- `pre_production` — **current stage.** No real personal data about third
  parties exists in any environment that survives a test run. Tests 1 and 2 do
  not escalate: the decision is taken, and the visibility change is appended to
  `EXPOSURE_REVIEW.md` instead.
- `piloted` — a real cohort's data exists. Tests 1 and 2 escalate normally.
- `production` — as `piloted`, plus ADMIN rules on the data itself.

**Entering `piloted` is itself an escalation, and its precondition is one human
review of `EXPOSURE_REVIEW.md` in a single pass.** This is the whole point of
the ledger: the gate is not removed, it is moved to the one moment where it is
load-bearing. The defaults written today are the defaults the first real cohort
meets, and nobody re-reads visibility defaults at launch — so they are read
once, together, before real data arrives, rather than one at a time now when
they cost nothing.

**Real data is present, and the stage stays `pre_production`.** Benjamin,
2026-09-16: the development database holds real people, used as test data, and
it does not leave that machine. An earlier wording of this file said any real
third-party data flips the stage to `piloted`; that was too coarse and is
corrected here. What decides the stage is not whether the data is real but
whether a path exists by which it reaches someone else. Today there is none:
the database is local, both product repositories are private, there is no
production deployment, and Benjamin is the only person with access. Flipping
the stage would reimpose an interruption per decision and remove almost no
risk.

`real_data_present: true` is therefore declared alongside the stage, and it
carries one hard containment invariant, which is where the actual risk lives.

**Real personal data stays in the local database.** It must never appear in a
test fixture, a seed file, a snapshot, committed test data, an analytics
payload, a log line, a CI output, an issue or PR description, a preview
environment, or a bead note. Agents write synthetic fixtures — same shape,
invented people — and never copy a row they found in the database. This is not
a preference and it is not covered by the delegation: an agent may not decide
to use real names because they were convenient.

The reason this invariant carries the weight, rather than the escalation tests,
is that in an agent-driven loop the realistic leak is a fixture, not a
visibility default. An agent that finds real names in the database and writes
them into a test is doing something that looks locally reasonable and that
lands in Git permanently.

The stage still changes on fact, not on preference: if the data becomes
reachable by anyone else — a shared or deployed environment, a repository made
public, a real cohort invited — the stage is `piloted` from that moment,
whatever this file says. Public figures in an editorial challenge are not
personal data in this sense.

**Escalate to Benjamin only if the decision:**

1. **Widens who can see real personal data** — exposes identifiable data to
   another person, another tenant, or the public, where it was not visible
   before. A journey whose only viewer is the person who owns the data does not
   widen anything. At stage `pre_production` this test never escalates; it
   appends to `EXPOSURE_REVIEW.md`.
2. **Destroys or removes data beyond recovery** — production data, a hard delete
   with no restore path, or a non-reversible migration. At stage
   `pre_production` this test never escalates for data that is seed, synthetic
   or the developer's own; it still escalates for anything that would destroy a
   real person's data.
3. **Leaves the system** — money, a purchase, a contractual commitment, a real
   send to a third party, or publication under the brand.
4. **Cannot be undone inside the current release** — no code revert plus
   reversible migration would restore the previous behaviour.

Everything else is decided by the AI. In particular, and explicitly: internal
schema shape, reuse-versus-fork, scheduling and algorithm choices, duplicate
handling, retention windows that only shorten exposure, default visibility that
only narrows it, component composition, copy, states, and navigation inside an
already-approved journey.

**An escalation never stops the factory.** It parks its own subgraph, is added
to Benjamin's review queue, and the campaign immediately continues with other
unblocked work. A campaign may only report a full stop when the set of unblocked
candidates is empty — never because the first item in the queue is waiting.

## Recording a delegated decision

Every decision taken under the delegation is written to `DECISIONS.md` with
`Tier: delegated`, and must carry four things:

- the choice, in one sentence;
- the basis it came from — which of the five sources above, and the exact
  reference;
- the reversal: the precise action that would undo it;
- the date and the deciding role.

A delegated decision has the same standing as any other until Benjamin overturns
it. Overturning one is an ordinary revision, not an incident: it changes the
record, and the work that rests on it is re-derived.

Benjamin receives a digest of delegated decisions and parked escalations when he
returns. He is never required to read it before the factory may continue.

## Approval tiers

- **Automatic** — existing component/pattern, copy or spacing adjustment; all
  deterministic tests and visual baselines pass. No record required.
- **Delegated** — everything that passes the four escalation tests. The PO or the
  Mayor decides from the declared basis, records it as above, and delivery
  proceeds without waiting.
- **Benjamin** — the four escalation tests only. Parked, queued, never blocking
  the rest of the campaign.

## Definition of design-ready

The work names the target user and success moment, entry and exit, all essential
states, content hierarchy, mobile behavior, keyboard/focus behavior, reused or
new components, analytics evidence, and — for each decision it raises — the
options, a recommendation, and which escalation test it passes or fails. "Make it
beautiful" is not a sufficient design contract.
