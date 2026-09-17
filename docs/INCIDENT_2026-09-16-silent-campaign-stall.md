# Incident, 2026-09-16: campaign stalled silently for ~4h while showing "active"

Written same day by the PO/Tech-Lead session, from live observation while
Benjamin was away and asked to check back in. Kept as a durable record per
ADR-0017 condition 4 (documented for both agents and humans) and as the
evidence base for the watchdog bead this incident produced (see bottom).

## What actually happened, in order

- **~17:08Z** `factory-guard`'s own liveness check (ADR-0016 §7, invariant
  already specified: "no campaign selection for N minutes is itself a
  defect") correctly detected no campaign progress and filed `af-zt3p`
  (P1 bug, "Campagne vivante mais immobile — diagnostiquer").
- Between then and **~21:00Z** the Mayor session was alive (real PID, CPU
  time accruing) but spent that time investigating an unrelated internal
  bug (`af-k8we`, a quarantine-repair bead that never got created) instead
  of the flagged liveness defect or the deferred product-queue candidates
  waiting behind it.
- **21:10Z** `af-caht` was finally materialized as `af-u8id.4`.
- **21:18Z** a worker session on `af-u8id.4` escalated 4 legitimate
  blockers by mail (`af-wisp-ds03ds`) and created a human gate
  (`af-oihx`), then exited.
- **21:24Z → 23:31Z (~2h7m)**: the gate sat open. Nothing paged anyone. The
  cockpit's `campaign` API kept reporting `state: active` / `blocked:
  false` throughout nearly this entire window — technically true (the
  *campaign* wasn't the thing blocked; one subgraph was, correctly parked
  per ADR-0016 §8) but functionally misleading, since no visible signal
  told a human "a gate needs you" without them running `gc bd show
  af-oihx` or reading mail by hand.
- **~23:31Z**: PO session found this by manually running
  `factory-guard --check-only`, `gc session peek mayor`, and reading mail
  — not because anything notified it. Resolved the gate's 3 resolvable
  points directly (routing, ADR-0015-vs-acceptance-criteria wording,
  ADR-0021 authorship — see reply to `af-wisp-ds03ds`), the 4th
  (independent Verify pass) specified as a required split. Also found and
  fixed a **second, independent** stall cause during the same check: PR #57
  (the ADR-0021 docs PR) had sat unmerged for ~3h with a merge conflict and
  zero CI checks ever having run on it (`statusCheckRollup: []`) —
  `pr-autopilot`'s "merge on green CI" assumption never fires for a
  conflicting PR, and nothing reported that either.

## The four concrete gaps, stated as defects

1. **Liveness violations are filed but not paged.** `af-zt3p` existed the
   whole time and said exactly the right thing. A filed bead nobody is
   nudged to read is equivalent to silence from Benjamin's chair.
2. **Human gates have no escalation timeout.** `af-oihx` sat 2h+ as
   `await_type: human` with no re-notification, no urgency escalation, no
   surfacing in the cockpit's "Aujourd'hui" attention panel that a human
   session would see without already knowing to look for it.
3. **A single Mayor incarnation can starve unrelated eligible work.**
   Investigating `af-k8we` is legitimate work, but ADR-0016 §7's own rule
   ("a local reason may never produce a global stop") was violated in
   effect: the factory-campaign lane (6 independent cockpit-UI candidates,
   not blocked by anything related to `af-k8we`) also saw zero progress
   for the same 4 hours, even though nothing formally blocked it.
4. **`pr-autopilot` has no signal for a PR that can never self-merge.** A
   conflicting PR or one CI never ran on is indistinguishable, from the
   outside, from one quietly waiting its turn — both show up as "not merged
   yet." Nothing currently tells the difference or ages one out to a human.

## Guardrail work this produced

Filed as a Factory-campaign candidate (`goal=none`, `product-queue` lane,
label `adr-0016`, `incident-2026-09-16`) — see
`./bin/saymyname-product-queue list` for its live position. Acceptance
criteria references this document by path so the eventual implementer has
the full timeline rather than a compressed summary.

## Incident 2, same night, 2026-09-16 21:43Z → 2026-09-17 ~02:00Z (~4h20)

A second, structurally different stall, found the same way (Benjamin asking
"tourne tjrs?" from bed; PO session running `factory-guard --check-only`
live rather than trusting the cockpit's `state: running` label).

**What happened:** after Incident 1's gate was resolved, a worker (`af-sbmf`)
successfully applied `af-u8id.4.1` (the ADR-0015/0021 schema wiring) and
opened PR #59. Independent review correctly returned `CHANGES_REQUESTED`
(a real bug: a takeover-derived `evidencedBlock` could read `status=proven`
with no `review` key and still validate — the exact fail-closed rule
ADR-0021 specifies was not actually enforced). Applying that fix then failed
**3 times in a row** (`af-g7ts`, `af-wbn2`, `af-tkpr`), each attempt's
`mol-scoped-work` workflow hard-failing at its `load-context` step with
`failure_reason=missing_outcome` — despite each attempt closing with a
correct, substantive `close_reason`. Root cause isolated by the Mayor itself
(not yet fixed): this reproduces specifically when `base_branch` is a
non-default feature branch (the fix-forward branch after review), not
`main` — the one `base_branch=main` pass needed only a single retry.

**The part worth its own line:** `on_fail=abort_scope` then silently skips
every downstream step (workspace-setup/implement/review/submit) **with no
comment explaining why** — the workflow root bead **closes as `CLOSED` with
zero visible top-level failure signal**. Discovering the real state required
reading nested `gc.outcome` metadata, which itself cost the Mayor "a full
extra cycle to even notice" (its own words, `af-wisp-ajklgu`). A `CLOSED`
bead in this Factory can currently mean "done" or "silently gave up" and
looks identical from the outside.

**What went right this time, worth keeping:** the Mayor did not keep
retrying blindly. After the 3rd reproduction it stopped, filed `af-ptx7`
(P1, `gc.needs_benjamin=true`) with the full evidence trail, and mailed
`human` directly (`af-wisp-k0c2qd`, sent 23:39Z) rather than going silent —
exactly ADR-0016 §7's intended behavior, and a real improvement over
Incident 1's rabbit-hole.

**What still didn't work:** that mail sat unread for ~4h20 until Benjamin
happened to check from bed. Mail-to-`human` is not a push — nobody is paged.
This is the same gap Incident 1's guardrail (`af-3rf3`) already exists to
close, now evidenced a second time from a different failure shape (a correct
escalation nobody saw, vs. Incident 1's absent escalation).

## The three additional gaps from Incident 2

5. **`mol-scoped-work`'s `load-context` step is unreliable on non-default
   `base_branch`** — 3/3 failure rate observed, root cause not yet fixed.
   Tracked as `af-ptx7` (P1). This blocks every fix-forward-after-review
   workflow, which is exactly the path Incident 1's own routing decision
   (require independent review before merge) now depends on — fixing gap 1
   made gap 5 load-bearing.
6. **A workflow can close `CLOSED` while having internally failed, with no
   visible signal at the top level.** This is more severe than a slow
   notification: it is a **false-positive success state**. Any tooling
   (including this Factory's own liveness/guard checks, and a human glancing
   at bead status) that trusts a bare `CLOSED` without reading nested
   `gc.outcome` can be wrong. This deserves its own acceptance criterion
   distinct from paging speed: a `CLOSED` molecule/workflow bead whose
   downstream steps all show `outcome=skipped` should not look the same as
   one that actually finished.
7. **A correct, well-written escalation mail is not a substitute for a page.**
   Confirms Incident 1's finding from the opposite direction — even when the
   Mayor did exactly the right thing, Benjamin still had to think to check.

## Guardrail scope, revised

`af-3rf3`'s acceptance criteria now also covers gap 6 (surface a
false-success `CLOSED` state, not just slow notification) — see the bead for
the current text. Gap 5 stays tracked separately on `af-ptx7` since it is a
specific, already-diagnosed dispatcher bug rather than a general guardrail.
