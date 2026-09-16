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
