# Spec Approve (B05; A6b, W04/W10)

## Status and purpose

`bin/spec-approve` approves a planning-plane Spec bead published by
`/to-spec`, over the live Beads/reservation/profile tools -- bead mode
(`bd-approve`/`bd-status`) only. The file-Spec mode this tool originally
had (a `DRAFT_SPEC`/`APPROVED_SPEC` JSON artifact with `approve`,
`freeze-check`, `revise`, `expire-check` and `status` subcommands, carrying
the `agent-factory-planning-run-spec/v1` contract) served only the
now-retired Planning Run router and was retired with it (A6b, W10).

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
