# B12 re-decomposition: Planning Run router, activation switch, fixture proof, Cockpit V2 reservation

- Status: Slice 1 delivered (`af-pxq7e`). Slices 2–4 delivered by `af-mav0b`,
  collapsed into a one-way cutover per Benjamin's explicit instruction to
  skip the reversible activation flag this note's Slice 3 proposed — see
  "One-way collapse (af-mav0b)" below. Draft decomposition note (not an ADR;
  the delivered shape differs from Slice 3 as originally proposed here).
- Authority: `af-6eipz`, filed after `af-4a44k` (B12) closed `blocked`
- Context: `docs/planning/agent-factory-project-agnostic-refactor-ticket-graph-draft.yaml` (B12),
  `docs/decisions/ADR-0027-legacy-planning-and-cockpit-v1-quarantine.md`,
  `docs/FIXTURE_CITY_ORACLE.md`

## Why B12 could not be executed as written

`af-4a44k` researched B12 ("cut all new planning over to the minimum kernel
and repair forward") and closed `blocked`. Its findings, reconfirmed here:

- B02–B09 shipped as independent standalone CLI tools with no orchestrator:
  `bin/planning-run-to-spec-oracle` (B03), `bin/spec-approve` (B05),
  `bin/ticket-graph-publish` (B06), `bin/wayfinding-run` (B04),
  `bin/factory-observe` (B09). Nothing calls one from another.
- ADR-0027's `legacy_path` fence lives only inside
  `bin/fixture-city-oracle`'s synthetic request contract. The ADR says
  explicitly the real kernel must translate its own selection into that
  vocabulary once it exists — that translation does not exist.
- No activation flag/switch/mechanism exists anywhere in the tree (`grep -r
  legacy_planning\|planning_kernel\|minimum_kernel\|activation` — zero hits
  outside prose docs).
- `tests/fixtures/fixture-city/` has no fixture proving B12 AC#1 (a simple
  request and a Wayfinding request each walking through approved Spec →
  approved graph publication → convoy continuation).

B12's premise — "cut over to the minimum kernel" — assumes a kernel and an
activation mechanism that do not exist yet. That is a topology gap in the
ticket, not a bounded technical repair, so it needs re-decomposition into
buildable slices before another worker can execute it.

## Decomposition into four slices

Each slice is independently verifiable in one fresh implementation context,
matching the existing B02–B11 granularity.

### Slice 1 — Planning Run router (`B12.1`)

A new deterministic CLI, `bin/planning-run-router`, that is the one caller
wiring the existing standalone tools into a single live Planning Run
lifecycle:

1. Accept a Planning Run request (session id, declared Project Planning
   Profile context, optional `legacy_path` selector).
2. **Translate `legacy_path` before creating any Planning Run identity** —
   this is the ADR-0027 obligation the ADR itself flags as outstanding. A
   non-`none` value is rejected fail-closed with a plain-language reason
   naming the quarantined artifact; no session, Spec, map, or convoy is
   created.
3. Drive `planning-run-to-spec-oracle to-spec` for a simple request. When the
   session reports it exceeds one healthy session (the existing "return to
   planning" signal `bin/planning-run-to-spec-oracle` already emits), the
   router instead drives `wayfinding-run promote`, then loops
   `claim`/`resolve` per decision, then calls `to-spec` once the map reports
   the route clear (B04's existing "no second fog audit" contract).
4. On a synthesized `DRAFT_SPEC`, call `spec-approve approve` only when the
   caller-supplied approval evidence is present (this router does not
   fabricate human approval).
5. On `APPROVED_SPEC`, hand the Spec to the same to-tickets authority (not
   re-slicing here) and call `ticket-graph-publish publish` to create the
   graph and convoy atomically.
6. Any step failure leaves no partial identity: the router itself writes
   nothing directly — it only sequences the existing doors, each of which
   already is all-or-nothing.

This is the only new code this decomposition requires; slices 2–4 are
config, tests, and a reservation mechanism around it.

**Acceptance criteria:**
- A simple request and a Wayfinding request each complete session → Spec →
  approval → publication → convoy through the router alone (no manual
  intervention between steps).
- A `legacy_path` request is rejected before any Planning Run identity,
  Spec, map, or convoy is created, with a reason naming the quarantined
  artifact (satisfies the ADR-0027 kernel obligation).
- A failure at any step (session, approval, or publication) leaves no
  partial artifact — re-running the same request from scratch is safe.
- The router calls the existing tools only through their documented CLIs;
  it does not duplicate their state-machine logic.

### Slice 2 — Fixture proof (`B12.2`, blocks activation)

Extend `tests/fixtures/fixture-city/` (or the router's own fixture, if the
router does not live inside the fixture City harness) with:
- A simple-path fixture: synthetic request → router → approved Spec →
  published graph → convoy continuation, asserted end-to-end.
- A Wayfinding-path fixture: a request the router promotes, resolves through
  two or more decisions, then completes to-spec → approve → publish →
  convoy, asserted end-to-end.
- A forced-defect fixture: an injected failure in the router (e.g.
  publication rejects) suspends only the affected run and does not fall
  back to or reactivate any legacy path.
- Reuse of the existing `legacy_path` fixtures
  (`legacy-planning-base.json`, `legacy-release-contract.json`,
  `legacy-cockpit-v1-export.json`) against the router itself, not only
  against `fixture-city-oracle`'s synthetic contract, so the translation
  obligation from ADR-0027 is proven, not just implemented.

This slice directly satisfies B12 AC#1 ("fixture City proves simple and
Wayfinding paths... before activation") and AC#3 ("forced new-path defect
suspends only affected runs").

**Acceptance criteria:**
- `tests/fixture-city-oracle-test.py` (or a new
  `tests/planning-run-router-test.py`) contains passing tests for all four
  fixtures above.
- The suite fails red before Slice 1 exists and passes green after, proving
  it exercises the router rather than restating its own assumptions.

### Slice 3 — Activation switch (`B12.3`, blocked by Slice 2)

A single, greppable activation mechanism — closing the "no
activation flag/switch/mechanism exists anywhere" gap `af-4a44k` found:
- `config/planning-kernel-activation.json` (schema-validated like the
  Factory's other config doors) with one field,
  `planning_kernel_active: true|false`, defaulting `false`.
- The one call site that currently decides how a new Planning Run request is
  handled (today: none — this is the gap) reads that flag through a small
  door script (e.g. `bin/planning-kernel-activation`) rather than being
  inlined at each caller.
- `true` routes new requests to `bin/planning-run-router` (Slice 1). `false`
  is a no-op for this decomposition — B12 does not require deleting or
  disabling any legacy path, only gating the new one, since no legacy
  Planning Run orchestrator exists to retire yet.
- Flipping the flag is reversible: setting it back to `false` stops routing
  new requests to the router without touching any already-published graph
  or convoy (AC#4, "already-started delivery remains eligible according to
  its existing verified graph" — the router never touches published Beads
  after `ticket-graph-publish`, so this is true by construction once Slice 1
  is scoped correctly).

**Acceptance criteria:**
- `planning_kernel_active` is `false` by default and only Slice 3's own
  change (or a later explicit flip) can set it `true`.
- Flipping `true` requires Slice 2's fixture proof to be green (documented
  precondition; enforced by making Slice 3 blocked_by Slice 2 in the graph,
  not by runtime coupling — a runtime coupling would let the switch silently
  no-op instead of failing closed).
- Flipping `false` after `true` stops new-request routing without mutating
  any existing Delivery Bead, convoy, or graph.

### Slice 4 — Cockpit V2 reservation (`B12.4`, blocked by Slice 3)

B12 AC#5 ("the next real non-critical Planning Run is reserved for C01,
Cockpit V2") needs a deterministic reservation, not a comment. Concretely:
- A one-shot marker (e.g. `gc.next_planning_run_reserved_for=C01` recorded
  through the same coordination-state write door pattern ADR-0023 already
  requires — never a bare `--set-metadata`) written when Slice 3 flips the
  activation flag `true`.
- `bin/planning-kernel-activation` (or the router itself) refuses to start
  any new non-critical Planning Run while the marker is set and its named
  target (`C01`) has not yet started, and clears the marker exactly once
  when C01's own Planning Run is created.
- This proves AC#5 the same way the rest of this decomposition proves its
  criteria: as an enforced, observable property, not documentation.

**Acceptance criteria:**
- After activation, a second new non-critical Planning Run request is
  rejected with a reason naming the C01 reservation, until C01's own run is
  created.
- Once C01's run exists, the reservation clears and subsequent non-critical
  requests are unaffected.
- The reservation does not block already-scoped delivery convoys (only new
  Planning Run creation), consistent with ADR-0025's `is_scoped_delivery_bead`
  boundary.

## One-way collapse (af-mav0b)

Filed 2026-09-24 (`gc.authorized_by: Benjamin, live PO conversation
2026-09-24`), `af-mav0b` re-scoped Slices 2–4 from live evidence once
`af-pxq7e` merged, exactly as this note anticipated above — with one
deliberate departure from Slice 3 as designed here:

- **Slice 2 (fixture proof)** landed as designed, using the "router's own
  fixture" option this note explicitly allowed: `test_simple_request_
  completes_end_to_end_through_the_router_alone` and `test_wayfinding_
  request_completes_end_to_end_through_the_router_alone` in `tests/planning-
  run-router-test.py` already proved both paths end-to-end (session →
  `APPROVED_SPEC` → published graph → `_convoy`) before this bead started;
  `af-mav0b` documented that proof in `PLANNING_RUN_ROUTER.md` rather than
  duplicating it against the heavier `tests/fixtures/fixture-city/` harness,
  which the router does not live inside.
- **Slice 3 (activation switch) did not land as designed.** Benjamin's
  explicit instruction for `af-mav0b` was one ticket covering both build and
  cutover, "no flag, env var, or code branch allows falling back to the
  legacy planning path" — a stronger, one-way requirement than this note's
  reversible `planning_kernel_active` switch. Since no legacy Planning Run
  orchestrator ever existed for a switch to gate (this note's own Slice 3
  text: "B12 does not require deleting or disabling any legacy path, only
  gating the new one"), the router became the unconditional entry point
  instead — no `config/planning-kernel-activation.json`, no
  `bin/planning-kernel-activation` door, no `true`/`false` state at all.
- **Slice 4 (Cockpit V2 reservation)** landed as an enforced property exactly
  as this note required (not documentation): `config/planning-run-
  reservation.json` plus the router's own reservation check and clear, all
  described in `PLANNING_RUN_ROUTER.md`'s "Reservation" and "Cutover
  guarantees" sections.

## Buildable order

```
Slice 1 (router)  ─▶  Slice 2 (fixture proof)  ─▶  Slice 3 (activation switch)  ─▶  Slice 4 (C01 reservation)
```

Sequential, not parallel: each slice's acceptance criteria assume the prior
slice exists and passed. This mirrors B12's own AC ordering (prove before
activating; activate before reserving the next run).

## Narrower first implementation ticket filed from this note

Slice 1 (the router) is the first ticket: it is the one genuinely new piece
of code, it is independently verifiable (call the existing tools against a
synthetic request and assert the sequencing and fail-closed `legacy_path`
behavior — no fixture-harness changes required to verify Slice 1 alone), and
every later slice depends on it existing. Filed as bead `af-pxq7e`
("B12.1 - Planning Run router: wire to-spec, approve, publish, wayfinding
into one live sequence"), `gc.authorized_by: af-6eipz`, referencing this
note. Slices 2–4 (fixture proof, activation switch, Cockpit V2 reservation)
are intentionally not filed yet — each is blocked on the previous slice
landing and should be re-scoped from live evidence once `af-pxq7e` merges,
not pre-filed from this design note's assumptions.
