# Wayfinding Run (B04)

## Status and purpose

`bin/wayfinding-run` promotes and resumes a durable Wayfinding Run: work
that exceeds one healthy session, promoted before material decision loss
into a Planning Map with non-executable Planning Decision Beads that can
progress, pause, resume and abandon without depending on any session
transcript.

The tool operates directly on a JSON Planning Map file (`promote` creates
it; every other subcommand mutates it in place through an exclusive OS-level
lock, so two sessions can safely claim and resolve independent decisions, or
race the same decision, at the same time — the real mechanism P03's
`planning-map-concurrency-prototype` proved synthetically). Every object it
writes carries positive `plane: planning` / `delivery_routable: false`
metadata and can never become delivery-routable.

## Run it

```bash
./bin/wayfinding-run promote tests/fixtures/wayfinding-run/request.json --out /tmp/map.json
./bin/wayfinding-run claim /tmp/map.json --decision staffing-model --claimant me --session s-1
./bin/wayfinding-run resolve /tmp/map.json --decision staffing-model --session s-1 \
    --resolution "embedded staffing" --evidence "af-example-evidence"
./bin/wayfinding-run status /tmp/map.json
./bin/wayfinding-run route-check /tmp/map.json
python3 tests/wayfinding-run-test.py
```

## Lifecycle

| Subcommand | Effect |
| --- | --- |
| `promote <request> --out <map>` | Validates the request declares `exceeds_one_session: true`, a non-empty `trigger_reason`, and at least one Planning Decision; writes a new map with `plane: planning` / `delivery_routable: false` baked onto the map and every decision, `status: active`. |
| `claim <map> --decision --claimant --session` | First-writer-wins: only succeeds while the decision is `open`; concurrent claims for different decisions never block each other, concurrent claims for the same decision produce exactly one winner. |
| `resolve <map> --decision --session --resolution --evidence` | Only the session that claimed the decision may resolve it; records `resolution`/`evidence` on the decision and closes it. If this was the last open decision, the run flips straight to `to_spec_ready` inside this same call — no separate audit step exists. |
| `pause <map> --reason` | Releases every `claimed` decision back to `open` (clearing `claimed_by`/`session_id`) and sets the run `paused`; already-resolved decisions, their resolutions and evidence are untouched. Claim/resolve are rejected while paused. |
| `resume <map> --refresh <facts.json>` | Only while `paused`. Merges the refresh payload into `time_sensitive_facts`, restricted to the keys the map declared in `time_sensitive_fields` at promotion time — any other key is rejected, so resume can never silently touch a resolution or evidence. Returns the run to `active` (or straight to `to_spec_ready` if every decision was already resolved before the pause). |
| `abandon <map> --reason` | Sets the run `abandoned`. Writes only the map file — no to-spec call, no other artifact, nothing published. |
| `status <map>` | Reports `status`, `plane`, `delivery_routable`, `route_clear` (no decision `open`/`claimed`) and `to_spec_eligible` (`status == to_spec_ready`). |
| `route-check <map>` | Simulates a delivery router's eligibility test (spec: a Delivery Bead needs positive `plane: delivery`); always reports the map and every decision ineligible, since they carry `plane: planning`. |

## Acceptance mapping

| Acceptance criterion | How the tool and tests check it |
| --- | --- |
| Planning Map and Planning Decision Beads carry positive `plane=planning` metadata and are never delivery-routable. | `promote` bakes `plane: planning` / `delivery_routable: false` onto the map and every decision unconditionally; `test_promote_creates_plane_planning_never_delivery_routable` checks the map file and `route-check`. |
| One disposable session resolves one claimed decision, records evidence, updates the map and closes. | `test_claim_resolve_records_evidence_updates_map_and_closes` claims and resolves a decision through separate CLI invocations (no shared process state) and checks the evidence/resolution land in the map; `test_resolve_rejects_session_that_did_not_claim` proves only the claiming session may resolve. |
| Independent children progress concurrently under the protection proven by P03. | `test_independent_decisions_progress_concurrently` runs two real threads claiming and resolving different decisions at the same time against the same map file, through the same exclusive-lock read-modify-write P03 modeled; `test_racing_claims_on_the_same_decision_produce_exactly_one_winner` races five threads on one decision and proves exactly one wins. |
| Pause releases sessions but retains map, resolutions and evidence; resume refreshes only time-sensitive facts; abandon publishes nothing. | `test_pause_releases_sessions_but_retains_map_resolutions_and_evidence`, `test_resume_refreshes_only_declared_time_sensitive_facts`, `test_resume_rejects_refresh_of_non_time_sensitive_fields`, `test_abandon_publishes_nothing` (diffs the directory listing before/after abandon). |
| When normal map rules declare the route clear and no child remains open, `to-spec` starts without a second fog audit. | `resolve` flips the run straight to `to_spec_ready` inside the call that closes the last decision; `test_route_clear_flips_to_spec_ready_inside_the_closing_resolve` and `test_tool_exposes_no_separate_fog_audit_subcommand` (the CLI has no `audit`/`fog-audit` subcommand at all). |

## Scope of proof

- **TARGET**: any request that exceeds one healthy session, promoted into a
  Planning Map whose decision children can be claimed, resolved, paused,
  resumed and abandoned by disposable sessions with no transcript
  dependence, and that is never delivery-routable.
- **CONFIGURED**: the `agent-factory-wayfinding-run/v1` map contract, the
  `agent-factory-wayfinding-run-request/v1` promotion contract, and the
  fixtures under `tests/fixtures/wayfinding-run/`.
- **OBSERVED**: the deterministic CLI output and twelve acceptance-mapped
  tests above, including real multi-threaded concurrent-claim and racing-
  claim runs against the same on-disk map file, reproduced identically
  across 300+ stress iterations with no lost update.
- **PROVEN**: within this fixture set, that the map/decision lifecycle
  (promote → claim → resolve → pause → resume → abandon) holds every
  acceptance criterion using OS-level exclusive locking (`fcntl.flock`) with
  an explicit flush-before-unlock, rather than a synthetic replay.

Not proven here: a live Beads/Dolt-backed Planning Map (this tool's map is a
plain JSON file, the same fixture-bound scope P02/P03/P04 declared), network
partition or crash-during-claim recovery, or the `to-spec` adapter itself
(out of scope for B04 — B04 stops at `to_spec_ready`).
