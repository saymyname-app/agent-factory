# ADR-0016: Standing design delegation and a campaign that cannot idle

- Status: Accepted
- Date: 2026-09-16
- Decided by: Benjamin, in conversation, 2026-09-16, after the night of
  2026-09-15 stopped twice.
- Extends: ADR-0015 (declared autonomy, reserved questions), ADR-0014
  (versioned release contract, typed stop reasons), ADR-0013 (Mayor-owned
  continuous campaign), ADR-0010 (governance domains and design loop).
- Changes: `docs/products/saymyname/DESIGN_GOVERNANCE.md` approval tiers.

## Context

On the night of 2026-09-15 the factory was authorised to run unattended. It
shipped one complete outcome — backend PR #38 and frontend PR #49 for the
administered CSV import — and then stopped at 01:06 for two unrelated reasons.

The first was a design gate. The next outcome produced a design-ready contract
whose seven decisions carried the `Benjamin + PO` approval tier, so no writer
could start. A live instruction telling the Mayor to decide in Benjamin's place
could not lift it: the tier is a governance rule of the workspace, not a
judgement call of the Mayor. The Mayor was right to stop, and the factory was
idle for six hours over a set of decisions whose recommendations were already
written out in full.

The second was a defect. A delivery bead was closed without its six proof
fields, `saymyname-product-status` refused it, and the one-minute campaign
sentinel that depends on that status died with it. Nothing surfaced: the guard
still reported healthy, because it checks branches, files, config and rigs, not
the status projection. From the outside the night simply looked quiet.

Both failures share a shape. **The factory stops globally for a local reason.**
One journey needing an approval stopped every journey; one malformed bead
stopped the whole wake loop. Benjamin's requirement is that he can leave for
hours without planning his departure, so the fix is not a faster approval — it
is that a local reason may never produce a global stop.

## Decision

### 1. Design decisions are delegated, permanently

Benjamin delegates design decisions to the PO and the Mayor. The delegation
stands until he revokes it in `DESIGN_GOVERNANCE.md`. It is not a relaxation of
review: every delegated decision is recorded with its basis and its exact
reversal, and he may overturn any of them as an ordinary revision.

### 2. Decisions are taken from a declared basis, in order

"The AI decides according to my known objectives" is only safe if the
objectives are a readable, versioned thing rather than an impression. The basis
is, most specific first: the human-only objective — `OBJECTIVE.md` today,
moving into the release contract's `objective.statement` once ADR-0015 is
implemented; `DECISIONS.md`; `PRODUCT_STRATEGY.md` including its
explicitly deferred and prohibited list; the release contract's `criteria`,
`included` and `excluded`. When all four are silent, five ordered tie-breakers
apply: prefer the more reversible option, reuse over fork, narrower exposure,
the smaller provable slice, then the design contract's own recommendation.

A decision that cannot be traced to one of those sources is not a delegated
decision — it is an escalation.

### 3. The gate tests effect, not category

The previous tiers escalated subjects: personal data, invitation, consent,
destructive action, materially new journey. Almost every real feature touches
one of those words, which is exactly why the factory stopped on almost every
journey. The gate now asks what the decision actually does. Escalate only if it
widens who can see real personal data, destroys data beyond recovery, leaves the
system (money, third party, publication), or cannot be undone inside the current
release by a revert plus a reversible migration.

The worked example is the one that stopped the night: a personal CSV import is
categorically "personal data", so the old rule escalated it. Under the new rule
it does not escalate, because the only viewer of the imported people is the
person who imported them — nothing is widened. The decisions it raised —
provisioning trigger, reuse versus fork, duplicate policy, scheduler model,
retention window, publication default, provenance schema — are all internal,
reversible, and traceable to recorded strategy.

This narrows what reaches Benjamin to the set where his answer genuinely changes
the outcome, which is the same principle ADR-0015 applies to intake questions.

### 4. An escalation parks a subgraph, never the campaign

When a decision does escalate, it is queued for Benjamin and its subgraph is
parked. The campaign immediately selects other unblocked work. A campaign may
report a full stop only when the set of unblocked candidates is empty. The
Mayor must never report `blocked` for the whole campaign because the head of
the queue is waiting.

### 5. Four anti-idle invariants, enforced mechanically

Policy alone would not have saved the night; the second failure was code. These
are Factory-scoped work items, not conventions:

1. **The status projection degrades, it does not die.** A malformed or
   incomplete bead yields a typed warning and a usable projection. No single
   bead may raise an exception that kills the one-minute sentinel.
2. **Closing a delivery bead without its six proof fields is rejected**
   (`gc.delivery_status`, `gc.work_outcome`, `gc.github_repo`, `gc.pr_number`,
   `gc.pr_head`, `gc.merge_commit`), or the close records the missing evidence
   explicitly as a failure rather than silently.
3. **`factory-guard` checks liveness, not only health.** A guard that reports
   healthy while the campaign has not selected work for N minutes is reporting
   the wrong thing.
4. **An empty product queue is not idleness.** When no product candidate is
   eligible, the Mayor takes Factory-scoped improvement work rather than
   stopping.

### 5b. The objective must exist for the basis to have a top

`OBJECTIVE.md` is created with the delegation and is human-only: no agent may
write, reword or extend it. While it reads `NOT SET`, the basis starts one step
lower and any decision that would have needed the objective to be settled is
escalated rather than guessed — the delegation degrades into caution instead of
into invention. Setting it is the single highest-leverage act available to
Benjamin, because every delegated decision below it inherits its direction.

### 6. What still stops the factory

Unchanged and deliberate: the four escalation tests, a durable failure, an
ADMIN action, and every provider being out of quota. Nothing else. In
particular, neither a design tier, nor a stale flag, nor a malformed bead may
produce a global stop again.

### 7. Every remaining stop case, treated

Benjamin asked for the full list to be worked through rather than left as a
residue. Each case below is either removed, demoted to a parked subgraph, or
kept with its reason stated. Nothing is left implicit.

| case | before | after |
| --- | --- | --- |
| Escalation 1-3 — widen exposure, destroy beyond recovery, leave the system | parks | **kept.** This is the safety floor and it is not reducible. What is reducible is how *often* it fires: a recurring pattern, once decided, is recorded as a standing decision in `DECISIONS.md` and stops being a question the next time. |
| Escalation 4 — not undoable inside the release | parks | **reduced at the source.** Reversibility becomes the engineering default: reversible migrations, no destructive default, a flag where behaviour changes. Fewer decisions fail test 4 because fewer changes are irreversible in the first place. |
| Durable failure — three consecutive failures | stopped the campaign | **quarantine.** The failing node alone is marked `blocked_durable_failure`, a repair item is opened, and the campaign continues with other work. A failure is local; the stop was not. |
| ADMIN action | stopped the campaign | **standing allowlist.** Routine operations stop counting as ADMIN: restarting a dispatcher or a preview, pruning merged branches, cleaning worktrees, rotating logs, reloading city config. Anything outside the allowlist parks and queues. |
| All providers out of quota | stopped the campaign | **degrade, then wait.** Fall to a cheaper profile first; if every profile is exhausted, park with an automatic resume at quota reset. This is a scheduling event, not a human event, and it never requires Benjamin. |
| No eligible product candidate | stopped last night | **the idle ladder.** Product work, then Factory improvement work, then test hardening and flake removal, then backlog grooming and documentation debt. The factory has no state in which the correct action is to do nothing. |
| Stale metadata, malformed bead, delivery closed without evidence | killed the wake loop silently | **invariants in section 5**, plus a watchdog: no campaign selection for N minutes is itself a defect, and the factory must diagnose it, repair it or file it, and say so. |

Two consequences of this table deserve to be stated as rules rather than rows.

**A local reason may never produce a global stop.** This is the governing
principle behind every row above, and the single sentence to apply when a new
case appears that this table does not cover.

**Liveness is a property the factory must be able to prove.** It must be able to
answer "what did you advance in the last hour", and "nothing" is a defect
report, not a status. A guard that reports healthy while the campaign has
selected nothing is answering the wrong question.

### 8. What is left, honestly

After all of the above, the factory can still stop for exactly one class of
reason: a decision that genuinely widens exposure of real personal data,
destroys something beyond recovery, leaves the system, or cannot be undone. Even
then it parks that subgraph and keeps working on everything else, so "stopped"
means "this branch is waiting", never "the factory is idle".

There is no configuration in which the factory both keeps deciding and never
touches those four. That floor is the point of the delegation, not a gap in it.

## Consequences

- Benjamin can leave without planning his departure. The factory continues; what
  needs him accumulates in a queue he reads when he returns, and reading it is
  never a precondition for the factory to keep working.
- What reaches him is smaller and sharper: only decisions his answer would
  actually change.
- Every delegated decision is auditable and reversible, so the delegation is
  recoverable rather than a one-way transfer of judgement.
- The night's two failure modes — a local approval stopping everything, and a
  local defect killing the wake loop — are both addressed, one by policy and one
  by enforced invariants. Neither fix would have been sufficient alone.
- Risk accepted, and worth stating plainly: the AI will sometimes decide
  something Benjamin would have decided differently. The mitigation is the
  recorded reversal, not prevention. A decision taken and reversed costs less
  than six idle hours.
