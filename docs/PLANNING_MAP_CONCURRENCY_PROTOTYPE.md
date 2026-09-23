# Planning Map and decision concurrency prototype (P03)

## Status and purpose

`bin/planning-map-concurrency-prototype` is a bounded, deterministic
prototype for the smallest concurrency mechanism guarding independent
Planning Decision claims, child resolution and shared Planning Map updates.
`planning-allocation-prototype` (P02) explicitly left "concurrent Planning
Map writes" unproven; this prototype closes that gap at the same
evidence-bound level as P02, P04 and P06 — a synthetic scenario over a
declared manifest, not a live multi-provider load test or a production
concurrency controller. Because the mechanism must stay deterministic across
runs (the same "run it twice, diff stdout" contract every sibling
prototype uses), concurrency is exercised as a scripted **adversarial
interleaving** of claim and map-write operations rather than real OS
threads: the manifest declares an explicit, out-of-order sequence of
operations from multiple racing actors, and the oracle replays it exactly.

## Run it

```bash
./bin/planning-map-concurrency-prototype validate
./bin/planning-map-concurrency-prototype run
python3 tests/planning-map-concurrency-prototype-test.py
```

`run` emits one deterministic JSON result: a claim-race stress sweep across
every arrival-order rotation of each decision's racing claimants, the replay
of one scripted interleaving of claim and map-write operations across two
independent decisions, the resulting shared Planning Map state, and whether
every acceptance criterion holds. The scenario source is
`config/planning-map-concurrency-prototype.json`.

## What the prototype models

- **Claim.** `ClaimLedger` is a first-writer-wins store keyed by decision id:
  the first successful `claim(decision_id, claimant)` call wins, every later
  call for the same decision returns `False`. `claim_stress` replays every
  declared claimant list under every rotation of arrival order (original,
  reversed, and each cyclic shift) with a fresh ledger per rotation, proving
  exactly-once claim and first-writer-wins hold under any ordering, not just
  the one scripted in the interleaving.
- **Shared Planning Map.** `VersionedMap` is a compare-and-swap store: each
  key carries a version, and `apply(key, value, expected_version)` only
  succeeds if the caller's expected version matches the map's current
  version. Two decisions write to **disjoint** per-decision keys
  (`alpha_resolution`, `beta_resolution`), so their own resolutions never
  collide. A `shared_index_key` accumulator is a genuine conflict point: two
  claim winners both read it at the same stale version, one applies first
  and succeeds, the second is rejected (`applied: false`, not silently
  dropped) and must re-read and retry — recorded explicitly as a `retry` op
  that re-reads the current version before resubmitting a `merge_add`.
- **Resolution guard.** A write to a decision's own `map_key` is only valid
  from that decision's claim winner; the replay records any violation and
  the corresponding acceptance criterion fails if one occurs.
- **Writer separation.** `singular_writers` (Spec and Ticket Graph Draft) and
  `concurrent_map_writers` (the decision ids allowed into this mechanism)
  are validated disjoint by construction — the manifest cannot declare a
  singular writer as a concurrent map writer.

## Acceptance mapping

| Acceptance criterion | How the oracle checks it |
| --- | --- |
| Two independent decision children can progress concurrently. | The interleaving script alternates operations between the two decisions (`interleaving_is_alternating`); both fully claim and resolve within the single replay pass, with no shared lock scoping one decision's critical section over the other's. |
| A child can be claimed and resolved exactly once. | Exactly one `claim` succeeds per decision in the replay, and only that winner may write the decision's own `map_key`; any other writer is flagged as a violation. |
| Conflicting shared-map updates preserve both valid resolutions or reject one for safe retry; no update is silently lost. | Disjoint per-decision keys are both preserved untouched by each other. The shared index key exercises a genuine CAS rejection (`applied: false`) followed by a scripted retry that re-reads and merges, so the final index contains every decision that attempted it — a rejection is a signal to retry, never a silent drop. |
| Spec and Ticket Graph Draft writers remain singular. | `singular_writers` and `concurrent_map_writers` are validated disjoint at manifest load, and re-checked against the decision ids that actually wrote in this run. |
| Evidence distinguishes target, configured, observed and proven behavior and records the mechanism's reversal. | The result's `proof_scope` carries explicit `target`/`configured`/`observed`/`proven`/`not_proven` fields, and `reversal` records the bounded rollback to a single global lock. |

`tests/planning-map-concurrency-prototype-test.py` exercises the default
scenario twice for determinism, then proves both decisions progress, each
decision is claimed exactly once, the conflicting shared write is rejected
and recovered on retry, the claim-race stress covers every arrival order,
and each validation guard rejects the manifest it is meant to reject
(too few decisions, colliding map keys, a shared index key colliding with a
decision key, a single-claimant race, singular/concurrent writer overlap,
and a non-winning claimant attempting resolution).

## Scope of proof

- **TARGET**: live concurrent Planning Decision sessions writing a shared
  Planning Map through the real Beads/Dolt-backed work graph.
- **CONFIGURED**: two disjoint-key decisions, a shared merge-accumulator
  index key, a racing-claimant list per decision, and one adversarial
  interleaving script in
  `config/planning-map-concurrency-prototype.json`.
- **OBSERVED**: the deterministic claim-race stress across every
  arrival-order rotation, and the single scripted interleaving replay,
  reproduced identically on every run.
- **PROVEN**: within this synthetic scenario, exactly-once first-writer-wins
  claim semantics under any arrival order, that disjoint-key writes never
  collide, and that a genuinely conflicting shared-key write is rejected for
  safe retry and recovered without loss on retry.

Not proven here: real OS-thread or multi-process concurrency and its
scheduling, live Beads/Dolt backend transaction and lock behavior, network
partition or crash-during-claim recovery, and production-scale claimant
counts or map key cardinality — those remain the province of a future
kernel, not this concurrency prototype.

## Reversal

`reversal` in the result records the bounded rollback: wrap `ClaimLedger`
and `VersionedMap` in one process-wide mutex, serializing every decision
child's claim and map write. That forfeits concurrent progress across
decisions but keeps exactly-once claim and zero-lost-update guarantees,
since a single serialization point trivially satisfies both. The rule: keep
the per-decision/per-key mechanism only while the claim-race stress shows
exactly-once claims under every arrival order and the interleaving replay
shows zero lost shared-map updates; revert to the single global lock the
moment either invariant fails on any declared scenario.
