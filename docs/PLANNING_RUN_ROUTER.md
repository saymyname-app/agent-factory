# Planning Run Router (B12.1)

## Status and purpose

`bin/planning-run-router` is the one caller wiring the existing standalone
B03/B04/B05/B06 tools (`planning-run-to-spec-oracle`, `wayfinding-run`,
`spec-approve`, `ticket-graph-publish`) into a single live Planning Run
lifecycle. `af-4a44k` (B12) found that nothing called one of these tools from
another; this is the router `docs/planning/B12-redecomposition-planning-run-
router.md` (Slice 1) files to close that gap.

The router writes nothing directly. It only sequences the existing tools'
documented CLIs, each of which is already all-or-nothing, so a failure at any
step leaves no partial identity behind -- re-running the same request from
scratch is safe. It never re-slices a Spec into tickets and never fabricates
human approval: `spec-approve approve` runs only when the caller supplies
approval evidence, and `ticket-graph-publish publish` runs only against a
caller-supplied, already-approved Ticket Graph Draft.

`legacy_path` is translated before any Planning Run identity is created --
the ADR-0027 kernel obligation the ADR itself flagged as outstanding. A
non-`none` value is rejected fail-closed with a plain-language reason naming
the quarantined artifact; no session, Spec, map or convoy is touched.

This is a deterministic synthetic prototype, not a live Gas City write door
-- the same fixture-bound scope B03/B04/B05/B06 declared.

## Run it

```bash
./bin/planning-run-router run tests/fixtures/planning-run-router/example-request.json
python3 tests/planning-run-router-test.py
```

## Request contract

A request is one JSON file, `contract: agent-factory-planning-run-router-
request/v1`:

| Field | Meaning |
| --- | --- |
| `legacy_path` | `"none"` (default) or one of `planning-base` / `release-contract` / `cockpit-v1-export`. Any non-`none` value is rejected before anything else is read. |
| `session` | Path to the Planning Session record `planning-run-to-spec-oracle run` consumes. |
| `city_registry` | Path to the City's registered rig ids, passed through to `planning-run-to-spec-oracle --city-registry`. |
| `spec_out` | Directory the synthesized Spec is written into (same `--out` contract as `planning-run-to-spec-oracle`). |
| `wayfinding` (optional) | `{request, map, decisions: [...]}`. When present, the router promotes (or reuses) the map, then loops `claim`/`resolve` over the supplied `decisions` before driving `to-spec`. |
| `approval` (optional) | `{approved_by, evidence}`. Omit to stop right after Spec synthesis -- the router never fabricates approval. |
| `publish` (optional) | `{draft}`, a path to an already-approved Ticket Graph Draft YAML. Omit to stop right after approval -- the router never re-slices a Spec into tickets. |

## Sequencing

| Step | Effect |
| --- | --- |
| `legacy_path` translation | A non-`none` selector returns `result: legacy_path_rejected` with a reason naming the quarantined artifact. Nothing else runs. |
| Wayfinding (optional) | Promotes the map if it does not already exist, then claims/resolves every decision the request supplies. If the map is not yet `to_spec_eligible` afterward, the router returns `result: wayfinding_pending` -- the caller may submit the remaining decisions in a later call against the same map, exactly as B04's own resumable design intends. |
| to-spec | Drives `planning-run-to-spec-oracle run` against `session`. A real contradiction/missing trace/undecided behavior/new test seam returns `result: returned_to_planning` with the oracle's own `signal`/`reason` -- no Spec is written. |
| Approval (optional) | Once a `DRAFT_SPEC` exists, `spec-approve approve` runs only if the request supplies `approval`; the linked Wayfinding map (if any) closes in the same call. Without `approval`, the router returns `result: awaiting_approval`. |
| Publication (optional) | Once `APPROVED_SPEC`, `ticket-graph-publish publish` runs only if the request supplies `publish.draft`. Without it, the router returns `result: approved_awaiting_publication`. With it, the router returns `result: published` with the graph digest and the published `ids` (including `_convoy`). |

## Acceptance mapping

| Acceptance criterion | How the tool and tests check it |
| --- | --- |
| A simple request and a Wayfinding request each complete session → Spec → approval → publication → convoy through the router alone, with no manual intervention between steps. | `test_simple_request_completes_end_to_end_through_the_router_alone` and `test_wayfinding_request_completes_end_to_end_through_the_router_alone` each drive one `run` call to `result: published` with a `_convoy` id and an `APPROVED_SPEC` on disk. |
| A `legacy_path` request is rejected before any Planning Run identity, Spec, map, or convoy is created, with a reason naming the quarantined artifact. | `test_legacy_path_selectors_are_rejected_before_any_identity_is_created` asserts all three ADR-0027 selectors return `legacy_path_rejected` with the artifact named in `reason`, and that `spec_out` is never created. |
| A failure at any step (session, approval, or publication) leaves no partial artifact -- re-running the same request from scratch is safe. | `test_rerunning_the_same_simple_request_from_scratch_is_safe` runs the identical request twice and asserts the second run publishes the same `ids` through exactly one underlying `create --graph` transaction (the publish door's own digest-based dedup). `test_missing_trace_returns_to_planning_and_creates_no_spec_or_convoy` and `test_wayfinding_request_with_decisions_still_open_stays_pending` prove the router never writes a Spec before it is actually synthesized/route-clear. |
| The router calls the existing tools only through their documented CLIs; it does not duplicate their state-machine logic. | The router source (`bin/planning-run-router`) only ever shells out to `planning-run-to-spec-oracle`, `wayfinding-run`, `spec-approve` and `ticket-graph-publish` and parses their public JSON output -- it holds no Spec/map/draft validation logic of its own. |
| At least one automated test exercises the router directly, covering the simple path, the Wayfinding path, and one `legacy_path` rejection. | `tests/planning-run-router-test.py` (9 tests): simple end-to-end, Wayfinding end-to-end, Wayfinding pending, missing-trace return-to-planning, all three `legacy_path` selectors, missing-approval stop, approved-without-a-draft stop, and full-request rerun safety. |

## Scope of proof

- **TARGET**: one router sequences an existing session or Wayfinding Run
  through to-spec, approval and publication into a live convoy, translating
  `legacy_path` fail-closed before any identity exists, with no partial
  identity surviving a failed step.
- **CONFIGURED**: the router's own request contract
  (`agent-factory-planning-run-router-request/v1`) plus the four existing
  tools' contracts (`agent-factory-planning-session/v1`,
  `agent-factory-wayfinding-run-request/v1`,
  `agent-factory-planning-run-spec/v1`, the Ticket Graph Draft contract), and
  the fixtures under `tests/fixtures/planning-run-router/`.
- **OBSERVED**: the deterministic CLI output and nine acceptance-mapped
  tests above, run against a fake `bd` (shared with `ticket-graph-publish-
  test.py`) so no real Beads store is touched.
- **PROVEN**: within this fixture set, that the router's sequencing holds
  every Slice 1 acceptance criterion without duplicating any of the four
  existing tools' state-machine logic.

Not proven here: a live Gas City Planning Run driving this router instead of
a synthetic fixture request, the fixture City proof of Slice 2, the
activation switch of Slice 3, or the Cockpit V2 reservation of Slice 4 --
each is intentionally out of scope for this slice per
`docs/planning/B12-redecomposition-planning-run-router.md`.
