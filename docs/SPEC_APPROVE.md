# Spec Approve (B05)

## Status and purpose

`bin/spec-approve` approves, freezes and revises the canonical Spec Planning
Artifact `planning-run-to-spec-oracle` (B03) produces: given a Spec file in
state `DRAFT_SPEC`, `approve` names its artifact identity and exact content
digest and flips that same file to `APPROVED_SPEC` -- it never writes a
second document, and it closes the linked Planning Map (`wayfinding-run`,
B04) in the same call so the map never outlives the Spec it produced.

Once `APPROVED_SPEC`, the artifact is frozen. `revise` is the only sanctioned
way to change it: the caller must name the exact digest it is revising,
a revision that does not actually change the content is refused, and every
accepted revision records provenance back to the digest it replaces while
keeping the Spec's identity (`spec_id`) stable. `freeze-check` is an optional
integrity check that localizes drift to the exact section that changed
instead of reporting a bare boolean, and nothing in `approve` or `revise`
requires it to run first. `expire-check` reports that the artifact stays
recoverable while its convoy is open and is only expire-eligible after the
convoy closes -- it is never itself the artifact of durable truth, which
belongs in code, tests, the domain glossary and qualifying ADRs.

This is a deterministic synthetic prototype, not a live Gas City write door
-- the same fixture-bound scope B03/B04 declared.

## Run it

```bash
./bin/spec-approve approve tests/fixtures/spec-approve/draft-spec.json \
    --approved-by benjamin --evidence af-example-evidence \
    --map tests/fixtures/spec-approve/to-spec-ready-map.json
./bin/spec-approve freeze-check tests/fixtures/spec-approve/draft-spec.json
./bin/spec-approve revise tests/fixtures/spec-approve/draft-spec.json \
    --expected-current-digest sha256:... --new-sections new-sections.json \
    --revised-by benjamin --provenance af-example-evidence
./bin/spec-approve expire-check tests/fixtures/spec-approve/draft-spec.json --convoy-status open
./bin/spec-approve status tests/fixtures/spec-approve/draft-spec.json
python3 tests/spec-approve-test.py
```

## Lifecycle

| Subcommand | Effect |
| --- | --- |
| `approve <spec> --approved-by --evidence [--map]` | Requires `state == DRAFT_SPEC` and that `content_digest` matches the actual digest of `sections`; flips the same file to `APPROVED_SPEC`, records `approved_by`/`approved_evidence`/`approved_digest` and per-section digests. When `--map` is given, validates the map is `to_spec_ready` before writing the spec, then closes the map (`status: closed`) -- either both happen or neither does. |
| `freeze-check <spec> [--expected-digest]` | Read-only. Requires `state == APPROVED_SPEC`; recomputes each section's digest against the digests recorded at approval and reports exactly which section(s) drifted, plus an optional identity check against a caller-supplied expected digest. |
| `revise <spec> --expected-current-digest --new-sections --revised-by --provenance` | Requires `state == APPROVED_SPEC` and that the caller's `--expected-current-digest` matches the artifact's actual current digest -- a stale or wrong digest is rejected as mutation of a frozen artifact. Refuses to mint a revision whose new sections produce the same digest (no genuine semantic change). On a genuine change, appends a `revisions` entry with `prior_digest`/`provenance`/`revised_by`, updates `sections`/`content_digest`, and returns the artifact to `DRAFT_SPEC` (it needs its own approval) while keeping `spec_id` stable. |
| `expire-check <spec> --convoy-status open\|closed` | Reports `recoverable: true, expire_eligible: false` while the convoy is open, and `recoverable: false, expire_eligible: true` once it is closed. Always reports `durable_truth_lives_here: false`. |
| `status <spec>` | Reports `spec_id`, `state`, `content_digest`, `approved_by`, `revision`. |

## Acceptance mapping

| Acceptance criterion | How the tool and tests check it |
| --- | --- |
| Approval names the Spec artifact identity and exact digest and changes the same artifact to Approved Spec. | `test_approve_names_identity_and_digest_and_flips_state` asserts the returned `spec_id`/`digest` match the input file and that the same file (same `spec_id`) now carries `state: APPROVED_SPEC`. `test_approve_rejects_declared_digest_that_does_not_match_content` proves a mismatched identity is refused before any mutation. |
| Approval closes the Planning Map and does not create a duplicate approved document. | `test_approve_closes_map_without_duplicating_the_document` approves with `--map` and checks the map flips to `closed` while only the original two files exist on disk. `test_approve_rejects_reapproving_an_already_approved_spec` and `test_approve_rejects_closing_a_map_that_is_not_to_spec_ready` prove a second approval, or closing a map that is not ready, is rejected without touching the existing artifacts. |
| Mutation of a frozen artifact is rejected; an approved semantic change creates a new digest with provenance. | `test_revise_rejects_wrong_expected_current_digest` and `test_revise_rejects_a_spec_that_is_not_yet_approved` prove revision is rejected without the exact current digest or outside `APPROVED_SPEC`. `test_revise_rejects_no_semantic_change` proves a no-op revision is refused. `test_revise_creates_new_digest_with_provenance_and_requires_reapproval` proves a genuine change produces a new digest, a `revisions` entry naming the prior digest, a stable `spec_id`, and a return to `DRAFT_SPEC` that must be approved again. |
| Artifacts remain recoverable during their convoy and may expire only after closure while durable truth remains in code, tests, glossary and qualifying ADRs. | `test_expire_check_recoverable_while_open_eligible_after_closure` checks both convoy states and that `durable_truth_lives_here` is always `false`. |
| Any optional integrity check reports distinct value and never becomes another fog audit. | `test_freeze_check_localizes_drift_instead_of_a_bare_boolean` tampers with one section and asserts `freeze-check` names exactly that section, not just `ok: false`. `test_freeze_check_is_optional_not_a_mandatory_second_audit` proves `approve` and `revise` both succeed end-to-end without ever calling `freeze-check`. |

## Scope of proof

- **TARGET**: an owner approves the exact canonical Spec by digest, its
  Planning Map closes in the same act without a duplicate document, a
  frozen artifact rejects mutation while a genuine semantic change is an
  explicit new revision with provenance, and the artifact stays recoverable
  during its convoy while expiring only after closure.
- **CONFIGURED**: the `agent-factory-planning-run-spec/v1` Spec contract
  (shared with B03) and the `agent-factory-wayfinding-run/v1` map contract
  (shared with B04), plus the fixtures under `tests/fixtures/spec-approve/`.
- **OBSERVED**: the deterministic CLI output and thirteen acceptance-mapped
  tests above, including the digest-mismatch, wrong-digest, no-op-revision
  and already-approved rejection paths.
- **PROVEN**: within this fixture set, that `approve`/`freeze-check`/
  `revise`/`expire-check` hold every acceptance criterion against a plain
  JSON Spec file and a plain JSON Planning Map file, using the same
  `fcntl.flock` read-modify-write discipline B04 proved for concurrent map
  writers.

Not proven here: a live Beads/Dolt-backed Spec or Planning Map, a real
convoy-closure signal driving `expire-check` (its `--convoy-status` is
caller-supplied, not observed), or wiring this tool into `ticket-graph-
publish` (B06) as the actual gate before publication.

## Bead mode: `bd-approve` / `bd-status` (A6b, W04)

A Spec published by `/to-spec` is a planning-plane Beads bead, not a JSON
file: its description is the prose Spec, and its metadata carries
`planning_run_target`, `planning_map` (a map bead id, or `"none"`),
`no_fog_evidence` (only when `planning_map` is `"none"`), plus the
approval state once approved (`spec_state`, `approved_by`,
`approved_evidence`, `approved_digest`). `bd-approve` and `bd-status` work
on that bead by id, over the live `bd`/`bin/planning-map`/
`bin/planning-run-reservation`/`bin/project-planning-profile` tools rather
than a JSON file on disk. The file mode above stays only for the router
until W10 retires both.

```bash
./bin/spec-approve bd-approve --spec af-3s8prq \
    --approved-by benjamin-hurand --evidence "« J'approuve » (Benjamin, live chat, 2026-09-30 Paris)" \
    --project agent-factory
./bin/spec-approve bd-status --spec af-3s8prq
```

Before any write, `bd-approve` refuses unless, in order:

1. The Spec is not already `APPROVED_SPEC` -- approval never creates a
   duplicate approved bead.
2. Its `planning_run_target` is allowed through by
   `planning-run-reservation check` -- when a reservation is active for a
   different target, the Spec bead and its map are left untouched.
3. Its named map is `finished` per `planning-map check`, or it names no
   map (`planning_map` absent/blank/`"none"`) and carries non-empty
   `no_fog_evidence`.
4. `--approved-by` equals the project's declared human approver
   (`project-planning-profile human-approver --project <id>`).
5. `--evidence` is non-empty.

On success it sets `spec_state=APPROVED_SPEC`, `approved_by`,
`approved_evidence` and `approved_digest` (`sha256:` of the bead's current
description text) as bead metadata in one `bd update`, then closes the
named map (`bin/planning-map close`) -- an unmapped Spec's `bd-approve`
never touches a map. `bd-status` recomputes the description's digest and
reports `void: true` once it no longer matches `approved_digest`, i.e. the
Spec was edited after approval and needs re-approval with fresh evidence.

## Acceptance mapping (bead mode)

| Acceptance criterion | How the tool and tests check it |
| --- | --- |
| A test per refusal (wrong target while reserved, unfinished map, wrong approver, empty evidence, no map and no No-fog evidence) shows the Spec bead and the map left untouched. | `SpecApproveBeadModeTest.test_bd_approve_refuses_*` in `tests/spec-approve-test.py`: each seeds a fake `bd` state, asserts a non-zero exit and an actionable `error`, then re-reads the state to prove neither the Spec bead's metadata nor the map's status changed. |
| A test shows a valid mapped Spec approved, its digest recorded and its map closed. | `test_bd_approve_approves_valid_mapped_spec_records_digest_and_closes_map` asserts `spec_state`, `approved_by`, `approved_digest` on the Spec bead and `status: closed` on the map. |
| A test shows a valid unmapped Spec approved with its No-fog evidence. | `test_bd_approve_approves_valid_unmapped_spec_with_no_fog_evidence` approves a Spec whose `planning_map` is `"none"` and asserts `map_closed: false`, `map: null`. |
| A test shows a Spec edited after approval reported void by status. | `test_bd_status_reports_void_after_spec_edited_post_approval` edits the fake bd state's description post-approval and asserts `bd-status` reports `void: true`; `test_bd_status_reports_not_void_when_unchanged` proves the negative case. |
| CI is green. | `tests/spec-approve-test.py`, `tests/project-planning-profile-test.py` and `tests/project-registry-test.sh` run under `bin/ci-run-tests`. |
