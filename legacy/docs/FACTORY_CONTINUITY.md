# Factory continuity: every known stop cause, root-caused, with a plan to leave almost none legitimate

Written 2026-09-17 by the PO/Tech-Lead session, after one night with three
distinct stalls (see `INCIDENT_2026-09-16-silent-campaign-stall.md`),
following Benjamin's explicit instruction: audit every way the Factory can
stop, root-cause each one (five-whys — the count is indicative, ask "why"
until you hit bedrock, not a fixed number), fix the roots rather than the
symptoms, and design so that "the factory stopped and nobody meant it to"
approaches zero.

This document is the taxonomy and the plan. It does not itself change
behavior — the beads at the bottom do that, through the normal delivery
pipeline (ADR-0017: verified, not asserted).

## 1. The taxonomy Benjamin asked for

Every way the Factory can be not-advancing, sorted into what should remain
legitimate versus what should not exist:

| Class | Is it legitimate? | Condition |
|---|---|---|
| **A. Human stopped it on purpose** | Yes, always | A human (Benjamin) explicitly stopped the city, or explicitly toggled "maintain-alive" off after confirming the release, or the host machine is off because he turned it off. |
| **B. Release complete, human confirmed** | Yes, but only with confirmation | The release reached its criteria AND a human said so — not "the campaign ran out of eligible work and stopped," which looks identical today but is class D. |
| **C. External failure, unwanted** | No — must be caught and paged, but the *cause* (power loss, network, a crashed dependency) is genuinely outside the Factory's control | The city process died, the machine rebooted unexpectedly, WSL/Docker/Dolt crashed. |
| **D. Ran out of eligible work, nobody said stop** | **Should not exist** | Tonight's actual failure mode's cousin: `select_campaign_work` finds nothing eligible and the campaign goes idle, without a human having confirmed anything. ADR-0016 §7 already specifies an "idle ladder" for exactly this (product → factory-improvement → test hardening → docs debt) — see §4 below for why it isn't enough as specified, and the fix. |
| **E. A defect stopped the loop (bug, bad dispatch, stale metadata)** | **Should not exist** | Tonight's three incidents: rabbit-holing on unrelated work, a gate with no timeout, a broken dispatcher retry path, an escalation mail that got read but not acted on. |
| **F. A genuine reserved decision (ADR-0015 §3 / ADR-0016 §8)** | Yes, but only that one subgraph, never the whole campaign | Personal data exposure, irreversible action, money, legal, authority, outcome-defining choice. Correctly narrow already; not the problem tonight. |

Benjamin's framing question — is "maintain-alive" different from "auto-refill
toward the release target" — maps directly onto B vs D here. They are
related but must be **two separate switches**, not one:

- **Auto-refill toward the release target** is bounded: it only ever
  materializes work that closes a gap in the *current* release contract
  (`config/releases/saymyname-v1.json`). It has a natural stop: every
  criterion `proven`, `release_target_proven`. This should already work —
  it's `select_campaign_work` as designed.
- **Maintain-alive** is the answer to "the release-target queue is empty,
  now what?" It must default to **on** (per ADR-0016 §7's own "the factory
  has no state in which the correct action is to do nothing"), be visibly
  toggleable in the cockpit, and when on, pulls from a **bounded, named set
  of improvement axes** (§4) — never from unscoped invention. When off
  (Benjamin turned it off after confirming the release), the Factory goes
  idle *and says so plainly* — that is class A/B, legitimate, and should
  look nothing like class D/E in the cockpit.

## 2. Five-whys on tonight, consolidated

Ran individually on each of the night's failures
(`INCIDENT_2026-09-16-silent-campaign-stall.md` has the raw timeline); here
is where each chain actually bottoms out.

**Incident 1a — 4h rabbit-hole on `af-k8we` while eligible work waited.**
Why did the Mayor not touch the eligible queue? → It was investigating a
different filed bug. Why did that crowd out everything else? → Nothing
forces a session to check "is there unrelated eligible work I'm starving"
before spending its full budget on one thread. Why does nothing force that?
→ **Root: dispatch priority is not enforced — it is left to a single
session's judgment, with no external check that a not-directly-blocked lane
actually got a turn.**

**Incident 1b — gate sat 2h+ unpaged.** Why did nobody see it? → No signal
outside `gc bd show <gate-id>` exists. Why is there no signal? → Gates were
built for correctness (block dispatch until resolved) but not for
visibility. → **Root: the Factory has async wait primitives (gates, mail)
but no aging/escalation layer on top of them — same root as 1a, restated:
a signal exists, nothing forces it into a human's or the Mayor's attention
within a bound.**

**Incident 1c — PR #57 sat 3h with a conflict, `pr-autopilot` silent.** Why
didn't autopilot report it? → It only knows "merge on green check"; a
conflicting PR or one with zero checks is invisible to that rule. → **Root:
the same missing-escalation root as above, applied to a third primitive
(pull requests) that also has no aging/escalation layer.**

**Incident 2a — `mol-scoped-work` load-context fails 3/3 on non-default
`base_branch`.** Why? → Root cause not yet isolated even by the Mayor's own
investigation (ruled out convoy-history, confirmed branch-correlated). This
one bottoms out in a real, not-yet-understood dispatcher bug — legitimate
engineering work, tracked as `af-ptx7`. Not a process gap; an actual defect.

**Incident 2b — a workflow closes `CLOSED` with all downstream steps
`skipped` and no visible signal.** Why? → `on_fail=abort_scope` was designed
to stop cleanly, not to report loudly. Why does clean-stop not also mean
loud-report? → Nobody specified that a `CLOSED` status must be falsifiable
from the outside without reading nested metadata. → **Root: the same
missing-escalation root, but sharper — this is a case where the *primitive
itself lies* (a closed bead that isn't actually done), which is more
dangerous than a primitive that's merely silent.**

**Incident 3 — Benjamin's decision mail was read (inbox: 0 unread) but not
acted on for ~2h until a second, sharper mail forced it.** Why? → Reading
mail and acting on its content are two different things; nothing connects
"mail marked read" to "the described action was taken." → **Root: same as
above, one layer up — even when escalation *reaches* a session, nothing
verifies the session actually executed the described next step, only that
it saw it.**

### The one root cause underneath all five

**The Factory has plenty of signals (liveness checks, gates, mail, PR
status, bead status) but no layer that (a) ages each signal against a
bound, (b) forces a concrete action when a signal crosses that bound, and
(c) verifies the action actually happened rather than trusting that it was
seen.** Every incident tonight is this same gap wearing a different
primitive's clothes. Fixing five different symptoms would be fixing the
same bug five times; the watchdog design in §5/§6 fixes the one root.

A second, smaller root, specific to class D: **ADR-0016 §7's idle ladder is
specified but has no concrete, bounded content** — "Factory improvement
work, then test hardening... " is a category list, not an actual queue a
selection function can draw from. That is why an empty release-target queue
risks looking like a stop instead of a seamless drop into improvement work —
nothing currently guarantees the ladder's rungs are populated.

## 3. Class C (external failure) — what already exists, what's missing

- `gc supervisor run` is a persistent process, already under the host's own
  process supervision (systemd, per `OPERATIONS.md`), so a WSL/process crash
  restarts it — this part is real and already true.
- **Correction, 2026-09-17 (see §8.1 for the full re-audit):** this
  document originally claimed no scheduled check existed at all — checked
  only OS-level `crontab`/`systemd` and missed Gas City's own internal
  order scheduler. `orders/factory-guard.toml` and `orders/mayor-campaign.toml`
  run those exact commands automatically every 5 and 1 minutes, respectively,
  all night. That was wrong twice: a prior 2026-09-16 session had already
  corrected the same mistake once. The real gap was never "nothing checks" —
  it is that the check's first action has no follow-up (§8.2-8.4).
- Class C therefore narrows further than originally stated: genuine host
  failure is already covered by the existing supervisor/systemd layer: not a
  gap this document needs to close.

## 4. Improvement axes — bounded, human-controlled, never-idle content for the ladder

Concrete answer to "comment éviter que le maintien en vie ne dérive hors
scope": each axis is a **named, separately toggleable, separately scoped**
category, defined in a new config file (`config/factory-improvement-axes.json`,
proposed — actual location is implementation's call), for example:

| Axis | Scope boundary (what it may touch) | Default |
|---|---|---|
| `code-review` | Re-review already-merged code for correctness/simplification findings, file beads, never merge without normal review | on |
| `dead-code` | Detect and remove code with zero live references, guarded by full test suite | on |
| `architecture-debt` | Propose refactors, require PO sign-off before dispatch (design-tier by nature) | on, gated |
| `ui-ux` | Only within existing `DESIGN_GOVERNANCE.md` tiers — no new navigation/journeys without the existing PO+Benjamin gate | on |
| `i18n` | Translation completeness/consistency only, no copy rewrites | off by default (needs Benjamin's confirmation it's wanted at all) |
| `security` | Read-only audits + P0-P2 fixes only, no new auth providers without an explicit reserved decision | on |
| `auth-providers` | Explicitly listed here because Benjamin named it: **adding a new login provider is a reserved `identity_and_consent`-class decision under ADR-0015 §3, always asked, never assumed** — this axis may draft a proposal, never ship one unreviewed | off by default, drafting only |
| `docs-debt` | Keep `CONTEXT_INDEX.md` and ADRs current, no behavior change | on |
| `v2-scope-exploration` | Draft-only speculative capabilities for a version that does not exist yet; may never be dispatched as executable work, only ever produces a document for the human to accept or reject | on, draft-only |

Each axis is independently on/off in the cockpit (ties directly into the
cockpit reorg already queued — `af-lnbc`/`af-thna`), and the **"maintain
alive" master switch** (§1) gates whether the idle ladder runs at all,
separate from any individual axis. When maintain-alive is off, the cockpit
must say so as plainly as a blocked campaign does today — not silence.

This directly answers Benjamin's worry about hallucinated scope-creep: no
axis can dispatch executable work outside its stated boundary, and any axis
whose boundary itself is a reserved-class decision (new auth provider,
architecture change) stays draft-only until a human accepts it — the
existing ADR-0015/ADR-0016 reserved-decision machinery already provides
this; the axes just need to declare which one applies to each so nothing
new has to be invented.

**Implemented, 2026-09-17/18 (`af-xe30d`):** the table above is
`config/factory-improvement-axes.json` (documented by
`config/factory-improvement-axes.schema.json`, enforced by
`lib/factory_improvement_axes.validate_policy`); live on/off state --
overriding the config's own defaults, cockpit- and CLI-mutable -- is
`.gc/runtime/factory-improvement-axes-state.json` via
`bin/factory-improvement-axes` (`status --json`, `set --action
maintain-alive|enable|disable`), mirroring the config/provider-policy.json
vs `.gc/provider-state.json` split ADR-0018 already proved. `factory_campaign
.plan_idle_ladder` gained a rung 5: when `maintain_alive` is true and no
earlier rung (product, a ready Factory bead, the factory-lane queue, tests,
docs) has anything to do, `factory_improvement_axes.select_improvement_axis`
picks the first enabled axis in table order -- a `draft_only` axis only ever
produces a proposal (`action: "propose"`), never dispatched work; a
non-draft, not-yet-wired stub (dead-code, architecture-debt, i18n, docs-debt)
is skipped as a deliberate no-op, exactly like an empty generative rung, not
a stall. `maintain_alive = false` gates the *entire* ladder beyond a bead
already tracked in progress, returning the explicit `maintain_alive_off`
reason (cockpit-visible in the new "Axes d'amélioration" panel,
`ui/factory-cockpit/index.html#axes-panel` /
`improvement-axes.js`) instead of silently doing nothing, per the "says so
plainly" requirement above. `select_campaign_work`
(`lib/product_release.py`) needed no code change for its own stop, as
scoped: it already returns `reason: "release_target_proven"` and selects no
further work once every release criterion is `proven` --
`tests/product-release-test.py` already covers that path. Tests:
`tests/factory-improvement-axes-test.py`,
`tests/mayor-campaign-test.py::IdleLadderPlanTest` (axis rung cases),
`tests/factory-cockpit-test.py` (`AxesBridge`, HTTP routes, panel presence).

## 5. State machine + live cockpit graph

Benjamin asked to see, in the cockpit, exactly which state the Factory is
in — not just "active/blocked" but the actual flow. Proposed states (from
observed behavior across tonight, not invented):

```
IDLE_RELEASE_QUEUE          -- select_campaign_work has an eligible candidate
  -> MATERIALIZING           -- Mayor turning a candidate into an execution bead
  -> DISPATCHING             -- work handed to a formula/worker
  -> AWAITING_REVIEW         -- PR open, independent review pending
  -> AWAITING_GATE           -- a "Gate: human" or reserved decision is open
  -> MERGING                 -- CI green, pr-autopilot armed
  -> back to IDLE_RELEASE_QUEUE (or IDLE_LADDER if release queue is empty)
IDLE_LADDER                  -- release queue empty, maintain-alive on, drawing from an improvement axis
STOPPED_HUMAN                -- class A/B: human confirmed release done, or explicitly toggled off
BLOCKED_EXTERNAL             -- class C: host/process failure
```

Each transition should be a fact already available from existing sources
(bead status, gate status, PR status, `gc.queue_state`) — this is a
projection, not new state to invent, matching the zero-token contract the
cockpit already holds elsewhere (`project_release`, `project_target_doc`).
Render it as a small state diagram on a page of its own (ties into the
cockpit-reorg work already queued), with the current state highlighted and
a short history of the last N transitions with timestamps — so "what is it
doing right now, and since when" is answerable from the cockpit in one
glance, without needing to run `factory-guard` by hand the way every check
tonight required.

**Implemented, 2026-09-17 (`af-3cat8`):** `lib/factory_continuity.py`
projects `human_state` (already-computed by `factory_state.py`) into exactly
one state — no new source read, matching the zero-token contract exactly as
asked. Three adjustments from this sketch, each because the signal either
already exists elsewhere or does not exist at all yet (see the module's own
docstring for the full reasoning):

- `AWAITING_GATE` reuses `resume.mode == "blocking_decision"`
  (`needs_benjamin`) rather than a literal `gc bd gate list` read — sec5's
  own wording already covers this ("a 'Gate: human' *or* reserved decision*
  is open"), and it needed zero new command calls.
- `BLOCKED_STALLED` is added: a non-admin `campaign.blocked` or a bare
  result-level `resume.mode == "blocked"` is a real, already-encoded "stuck,
  needs a diagnosis" condition distinct from a gate or an external failure.
- `AWAITING_REVIEW`/`MERGING` stay defined but unreachable today: no work
  bead carries a live PR state (only `merge_result=merged`, once merged) —
  wiring `pr-autopilot` to write one back is separate follow-on work.

Rendered on the existing "Workflow" page (`ui/factory-cockpit/index.html`,
`#continuity-flow`) rather than waiting on the deferred cockpit reorg
(`af-lnbc`/`af-thna`); history persists to
`.gc/runtime/factory-continuity-history.json`. Tests:
`tests/factory-continuity-test.py`.

## 6. Automated remediation, not just paging

The watchdog (`af-3rf3`) was originally scoped as detect-and-page. Given the
root cause in §2 (signals reach someone but aren't verified acted-on),
extend it one step further where the fix is mechanical and safe:

| Signal | Current behavior | Proposed automated remediation |
|---|---|---|
| Liveness > N min | Files a bug bead, nobody paged | Page (mail + notify) immediately; if still no state change after a second bound, auto re-dispatch the first eligible candidate rather than waiting for a session to notice |
| Gate `human` open > N min | Sits silently | Re-notify mayor and surface prominently in cockpit "Aujourd'hui"; do **not** auto-resolve — a human gate stays a human gate, this only fixes the paging gap |
| Mail to `mayor`/`human` marked read, no state change after N min | Nothing | Re-send with escalating urgency; this is exactly what the PO session had to do by hand three times tonight |
| PR conflicting or zero CI checks after N min | Sits silently | File a bug bead, mail the branch owner/mayor with the specific `mergeable` state |
| Workflow closes `CLOSED` with any downstream step `outcome=skipped` | Looks identical to success | Never allow a bare `CLOSED` in this shape without a comment explaining what didn't run — reject the close, or force a distinct status |

None of this resolves a genuine reserved decision automatically — per §1
class F, those stay exactly as narrow and human-gated as ADR-0015/0016
already made them. This only removes the gap between "a signal exists" and
"someone with the authority to act on it actually saw and acted on it in
bounded time."

## 8. Deep audit: what the actual files do, and why "add an alert" is the wrong shape

Benjamin, 2026-09-17: an alert on top of the flow is not enough — the flow
itself must act. This section reads the real files (`orders/*.toml`,
`.beads/formulas/mol-scoped-work.formula.toml`, `bin/factory-guard`,
`lib/factory_liveness.py`, `bin/pr-autopilot`) rather than describing them
from memory, and reframes §6/§7 around editing the four mechanisms that
already run on a schedule, instead of adding a fifth one beside them.

### 8.1 Orders are plain files, not magic

`orders/*.toml` are four small files, each wired to one of this repo's own
`bin/` scripts on a fixed cooldown:

| Order | Interval | Timeout | Runs |
|---|---|---|---|
| `mayor-campaign` | 1 min | 50s | `./bin/mayor-campaign sentinel` |
| `factory-guard` | 5 min | 180s | `./bin/factory-guard --quiet` |
| `pr-autopilot` | 3 min | 120s | `./bin/pr-autopilot` |
| `provider-failover` | 2 min | 100s | `./bin/provider-failover tick --quiet` |

Correction to §2/§3 of this document and to both incident reports: these
were never absent. They ran, on schedule, all night. The gap was never
"nothing checks" — it was always "checking is not the same as acting past
the first response."

### 8.2 The exact liveness bug, in the code

`bin/factory-guard` §7 calls `lib/factory_liveness.py`, which correctly
classifies a stall as `stale` after the configured window (60 min default).
What it does with a `stale` verdict, read directly from the script:

1. It checks `gc.campaign_liveness_bead` on the coordination bead. If a
   still-open bead is already linked, it prints `"liveness defect already
   filed: $prior"` **and stops** — no re-notification, no urgency increase,
   no second action, no matter how much longer the stall runs.
2. Only if no bead is linked (or the prior one is closed) does it create a
   new one — and even then, `did "filed liveness defect $created for the
   Mayor"` is a line the guard prints to **its own log**. It is not a mail.
   **No `gc mail send` call exists anywhere in this path.** A liveness
   defect bead is filed for the Mayor to find, never told to it.

This is the precise mechanism behind Incident 1's four-hour silence and
Incident 3's unread-then-ignored decision: the very tool designed to catch
a stall (ADR-0016 §5.3, built specifically after the 2026-09-15 six-hour
incident) itself has no escalation past its first, single action. It was
built to stop the *previous* failure (nothing checks) and inherited a new
one (checking doesn't reach anyone).

### 8.3 The concrete fix — edit the mechanism, not a bead pointing at it

Not "add a watchdog that also checks this." Edit `bin/factory-guard` §7
directly:

```
verdict = stale, no prior bead           -> file bead (unchanged) + mail mayor --notify (NEW)
verdict = stale, prior bead open < 30min -> nothing (unchanged; give the Mayor time to react)
verdict = stale, prior bead open 30-90min -> re-mail mayor --notify, escalate bead priority (NEW)
verdict = stale, prior bead open > 90min -> mail human directly + gc.needs_benjamin=true on the bead (NEW)
```

Same order, same 5-minute cooldown, same zero-token/deterministic script —
three new branches in an `if`, not a new subsystem. This is what "modify
the flow instead of bolting on a sensor" means concretely here.

### 8.4 The same shape repeats in three other places

- **Gates.** The core `gate-sweep` order re-evaluates gate *conditions*
  every 30s (does the thing it's waiting for still hold), never gate *age*.
  A `Gate: human` has no TTL and no re-notify field anywhere in `bd gate
  --help`'s surface. Concrete fix: a small companion check (could ride on
  the existing `factory-guard` tick, §8.3's shape, rather than a new order)
  that reads open gates' `created_at`, and at the same 30/90-minute bounds
  re-mails whoever the gate names and surfaces it in the cockpit's
  "Aujourd'hui" attention panel — exactly the panel that already exists for
  a different block kind (`campaign-block-today`).
- **`mol-scoped-work`'s hard failure.** Read directly from
  `.beads/formulas/mol-scoped-work.formula.toml`: every step's
  `[steps.retry]` block already defines `max_attempts = 3` and
  `on_exhausted = "hard_fail"`. `workspace-setup` and its siblings carry
  `gc.on_fail = "abort_scope"`, which is exactly what produced Incident 2's
  silent cascade — every downstream step closes `skipped`, and nothing in
  the formula itself communicates that outward. Concrete fix: `hard_fail`
  should carry its own mail step in the formula (a `[[steps]]` entry that
  only runs `needs`-gated on the failed step's hard-fail state), not rely
  on a future session stumbling onto nested `gc.outcome` metadata to notice.
- **`pr-autopilot` already holds the data it would need to self-report.**
  Its own `open_prs` query already pulls `mergeStateStatus` and
  `statusCheckRollup` for every open PR on every tick (`bin/pr-autopilot`
  §1). A PR sitting `mergeStateStatus=DIRTY` (conflicting) or with an empty
  check list past a few ticks is data the script already has in hand and
  currently does nothing with beyond attempting (and silently failing) the
  merge call. Concrete fix: a branch in the same loop that files/mails on
  exactly those two conditions, using data the order already fetched —
  again, editing the existing order, not adding a new one to watch it.

### 8.5 What this changes about `af-3rf3`

The bead's acceptance criteria described a new detection layer. Revise it to
instead specify **edits to the four existing files above**, each with the
exact before/after in this section, so whoever implements it edits
`bin/factory-guard`, the gate-age check, the formula, and `bin/pr-autopilot`
directly — not a fifth process reading the same signals from outside.
