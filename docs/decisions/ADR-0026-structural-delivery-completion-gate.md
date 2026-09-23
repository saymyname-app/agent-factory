# ADR-0026: PR-backed work closes only after merge and exact-head CI proof

- Status: Accepted
- Date: 2026-09-23
- Authority: Benjamin via repair bead `af-v54f2`, for approved graph digest
  `sha256:53a663ab5841e8e43dd05f5a4c470496ce50613b3b9690b5102df881c83be417`
- Extends: ADR-0016, ADR-0023, ADR-0025

## Context

P01 and P02 were closed when their pull requests were merely opened. Beads
therefore considered their `blocks` edges satisfied and exposed dependent
tickets before merge, review, and required CI were proven. P01 needed the
repair chain PR #197 → #198 → #199; P02 was integrated by PR #200. P04 then
reproduced the same false-done state with PR #201 still open.

Prompt wording such as “under review, not shipped” cannot repair this: Beads
read status structurally, and `closed` releases a dependency regardless of the
close reason.

## Decision

1. A PR-opening formula records `gc.delivery_contract=pr-ci-merged-v1`,
   `gc.delivery_status=waiting`, the PR URL, branch, and base, and leaves its
   work bead `in_progress`.
2. `pr-autopilot` matches a merged PR to the work bead but does not write merge
   metadata itself. It calls `bin/deliver-close`, the single write door.
3. The door independently verifies:
   - the exact repository and PR are merged;
   - recorded PR URL, head branch, and base (when present) match GitHub;
   - the configured required workflow has a completed successful
     `pull_request` run whose `head_sha` equals the PR `headRefOid`.
4. One Beads update records the original six ADR-0016 fields plus
   `merge_result=merged`, `merged_sha`, `merged_target`,
   `gc.required_ci_workflow`, `gc.ci_run_id`, `gc.ci_head_sha`, and
   `gc.ci_conclusion=success`, then closes the bead. Failure writes nothing.
5. `lib/factory_delivery_proof.py` owns the pure structural completion
   predicate. In an exclusive approved graph, `mayor-campaign` rechecks every
   raw-ready candidate's `blocks` targets against a complete graph snapshot.
   `factory-waiting-guard` uses the same predicate before clearing a wait whose
   target is closed. Closed-under-review, unmerged, missing-proof, red-CI, and
   head-mismatched blockers therefore remain ineligible.
6. Explicit `no-op`, `blocked`, and `abandoned` outcomes, and generic non-PR
   work, retain their existing terminal semantics. The stronger predicate is
   only the completion contract for work that claims PR-backed delivery.

## Consequences and verification

- PR creation no longer means done; the merge actor is also the finalizer.
- A historical raw close can no longer advance the scoped graph merely because
  Gas City reports a dependent as ready.
- The extra graph snapshot is read only while an exclusive graph scope is
  active; a missing snapshot fails closed.
- `tests/deliver-close-test.sh` covers the write door; P01/P02-shaped fixtures
  in `tests/factory-delivery-proof-test.py` and
  `tests/mayor-campaign-test.py` cover proof and dependency readiness;
  `tests/factory-waiting-guard-test.sh` covers named waits.
- Reversal requires reverting this ADR and all four coupled surfaces together:
  formula state, the close door, scoped readiness, and the waiting guard.
