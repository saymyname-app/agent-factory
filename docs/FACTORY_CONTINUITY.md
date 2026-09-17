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
- **Missing, verified absent 2026-09-16:** no cron, no systemd timer runs
  `factory-guard --check-only` or `mayor-campaign sentinel` on any schedule.
  Every liveness check performed tonight was triggered by a human (Benjamin
  or the PO session) running a command by hand. If nobody had asked "tourne
  tjrs?" tonight, nothing would have surfaced Incident 1 or Incident 3 at
  all until the next time a human happened to look.
- This is squarely a class-D/E fix (§5), not class-C — the machine wasn't
  down, the *check* simply never ran unattended. Once the watchdog runs on
  its own schedule (§5), class C narrows to genuine host failure, which the
  existing supervisor/systemd layer already covers.

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

## 7. What ships now

- `af-3rf3` (existing, urgent, factory-campaign lane): scope stays
  detect-and-page plus the false-success-`CLOSED` detection already added;
  now additionally covers PR-conflict paging (§6, row 4) and the
  mail-read-but-not-acted escalation (§6, row 3), both evidenced tonight.
- New bead: **state machine + live cockpit flow graph** (§5) — a
  zero-token projection page, part of the cockpit reorg already queued.
- New bead: **improvement axes + maintain-alive switch** (§4) — the
  never-idle content for ADR-0016 §7's idle ladder, with the cockpit toggle
  Benjamin asked for.
- `af-ptx7` (existing, P1): the actual dispatcher bug (`mol-scoped-work`
  `load-context` on non-default `base_branch`) — engineering work, not a
  process gap, tracked separately and correctly already.
