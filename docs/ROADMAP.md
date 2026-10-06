# Factory Roadmap

Intent in prose; the current step and its status live in `docs/roadmap.toml`
(GLOSSARY.md: Roadmap Step), validated by `bin/project-roadmap validate` and
resolved by `bin/project-roadmap check-target` for a given
`planning_run_target`. Rewrite this file's prose in place when intent
changes; change status by editing `roadmap.toml` with a normal commit.

## Where this roadmap came from

Through 2026-09-30 the Factory's own roadmap lived inside SayMyName's
knowledge repo (`saymyname-app/Say-my-name-product`, `knowledge/roadmap.md`
and `knowledge/state.md`) as steps **A1-A6** and a step SayMyName called
**A7**: "Planning Run C01 'Cockpit V2'". T03 (af-s0qa19) moves that Factory
work to the Factory's own structured roadmap. The step SayMyName called A7
keeps the id **C01** here, because that is the id every Spec, ticket, and
convoy for this work already uses as `planning_run_target` — giving it a
second id (A7) alongside C01 would let the two drift. SayMyName's own
roadmap keeps only "B1 attend l'étape usine X"; moving that line is a
SayMyName-side operator step after T03 merges, not part of this ticket's
graph.

## Horizon A — finish the Factory refactor

- **A1** Legacy isolation: move every retired command and pre-refactor
  ADR/doc out of the trusted tree, with living ops docs citing none of them.
- **A2** Project-agnostic Mayor: the Mayor no longer special-cases SayMyName;
  each rig declares its own owner rules.
- **A3** `factory-guard` inside its budget: the guard stays inside 180 s with
  margin, not "usually".
- **A4** "Nothing forgotten" inventory: every Factory file gets a verdict
  (kernel / ops / legacy / to redo), plus a prompt-vs-code drift audit and a
  sweep of stale rig checkouts and host-local runtime state.
- **A5** Planning Run "Factory operations v2": the order system, Mayor
  wake-on-publish, orphan-signal handling, exhaustion parking, and the
  proposals flow, reviewed and hardened as one Planning Run.
- **A6** Planning Run "Parallel delivery": more than one worker safely on the
  same repo — worktree per dispatch, declared file scope, hot-file leases,
  live-city test isolation, and a conflict-repair loop.

**Horizon A is done when:** A1-A6 are done, no order fails chronically over
24 h, and A4's inventory has no open "to redo" line outside A5's tickets.

## Horizon B — Cockpit V2

- **C01** Planning Run "Cockpit V2": an operator cockpit with notifications
  and ritual reminders, so Benjamin sees what's waiting on him without
  opening an agent session. This is the step SayMyName's roadmap named A7;
  see "Where this roadmap came from" above for why it now carries the id
  C01 instead.

- **D01** Planning Run "Delivery Workflow": the Delivery Workflow from a
  published graph to an accepted Delivered Outcome (map af-0sayxf, Spec
  af-wf4w5r). Delivered by today's flow; ends with a final verification
  against its Spec, then the Cockpit V2 redelivery as validation case.

Everything past C01 (SayMyName's own B1 "test the app himself", B2 release
scope, and horizon C "deliver SayMyName to release") stays on SayMyName's
roadmap — it is that project's work, not the Factory's.
