# ADR-0027: Legacy planning and Cockpit V1 are fenced as read-only evidence

- Status: Accepted
- Date: 2026-09-23
- Authority: ticket `B01` (bead `af-cfl9j`) of the approved graph digest
  `sha256:53a663ab5841e8e43dd05f5a4c470496ce50613b3b9690b5102df881c83be417`,
  spec `sha256:9ce47e19172505d26fd7d0ba8696bad29896e7614b0dc5c15a2f19061064b9fa`
- Extends: ADR-0014, ADR-0025
- Related: `docs/planning/agent-factory-project-agnostic-refactor-spec.md`,
  `docs/FIXTURE_CITY_ORACLE.md`

## Context

The project-agnostic refactor (B01–B12) replaces the SayMyName-specific
planning methodology (`.beads/formulas/planning-base.toml`), its duplicated
Release Contract (`lib/product_release.py`,
`config/product-release.schema.json`, `agent-factory-product-release/v1`), and
Cockpit V1 (`lib/factory_cockpit.py`, `ui/factory-cockpit/`) with a
project-agnostic Planning Run kernel (B02–B05). Those kernel tickets are
blocked on B01 and do not exist yet, so there is nothing today that could
accidentally reuse the legacy path — but there is also nothing that would stop
it once the kernel lands. Fencing the boundary now, before B02–B05 write any
kernel code, keeps the quarantine a proven property of the system rather than
a convention future beads must remember to honor.

Cockpit V1 must stay consultable as evidence (nothing is deleted or hidden),
but its routes, screens, and state model must never become the target
contract for a new Planning Run or its future Cockpit V2.

## Decision

1. **Legacy path is a named, rejectable selection.** A Planning Run request
   may declare `legacy_path` as one of `planning-base`, `release-contract`, or
   `cockpit-v1-export`. Any value other than the implicit `none` is rejected
   before a Planning Run is created — no Planning Run identity, work item, or
   convoy exists for it.
2. **Rejection is fail-closed and operator-readable.** The rejection carries a
   plain-language reason naming the quarantined artifact (the planning-base
   methodology, the `agent-factory-product-release/v1` contract, or Cockpit
   V1's routes/screens/state model) so a human or an agent reading the
   rejection knows exactly what was refused and why, without reading this ADR.
3. **Already-attached delivery is unaffected.** The fence only engages when a
   request explicitly selects a `legacy_path`. Convoy-attached delivery
   selected through the existing `is_scoped_delivery_bead` /
   `mayor-campaign scope` mechanism (ADR-0025) does not pass through Planning
   Run selection at all, so it continues exactly as before.
4. **The quarantine is proven through the fixture City, not only documented.**
   `bin/fixture-city-oracle` and its reference operator adapter
   (`tests/fixtures/fixture-city/operator`) are extended with the same
   `legacy_path` selector: a real (sandboxed) fixture request attempting any
   of the three legacy selections must be observed to fail closed with a
   reason, while a request that omits `legacy_path` continues to complete the
   full Planning Run lifecycle unchanged.
5. **Cockpit V1 is not modified.** No file under `lib/factory_cockpit.py`,
   `bin/factory-cockpit`, or `ui/factory-cockpit/` is changed by this ADR — it
   remains fully readable as evidence. Only the ability of a *new* Planning
   Run to declare it as an export target is fenced.
   *Amendment 2026-09-26:* the same files now live, unchanged, under
   `legacy/` (Benjamin, 2026-09-25: isolate pre-refactor code; see
   `legacy/README.md`). The fence above is unaffected.

## Consequences and verification

- `tests/fixture-city-oracle-test.py::test_new_planning_run_selecting_legacy_planning_base_fails_closed`,
  `::test_matt_path_cannot_create_or_consume_a_duplicated_release_contract`, and
  `::test_cockpit_v1_export_of_routes_screens_or_state_model_fails_closed` each
  run the fixture City end-to-end and assert a fail-closed rejection with a
  named reason and no Planning Run identity, artifact, publication, or write
  door interaction.
- `::test_default_planning_path_is_unaffected_by_the_legacy_fence` proves the
  fence is opt-in per request and does not regress the existing single-rig
  lifecycle.
- Because the real Planning Run kernel (B02–B05) does not exist yet, this
  fence lives in the fixture City's request contract today. When the kernel
  ships, it must translate its own methodology/profile selection into the same
  `legacy_path` vocabulary (or an equivalent guard) before it can claim
  conformance with this ADR — a kernel that skips this check is not fencing
  the legacy path, regardless of what it documents.
- Reversal requires reverting the `legacy_path` handling in
  `bin/fixture-city-oracle` and `tests/fixtures/fixture-city/operator` together
  with this ADR; the three legacy artifacts (`planning-base`,
  `product_release.py`, Cockpit V1) are otherwise untouched and remain in the
  tree as evidence.
