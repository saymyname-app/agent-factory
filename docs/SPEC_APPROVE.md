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
./bin/spec-approve outline < spec.md
```

`outline` (T06, af-cgauf8) reads a Spec text on stdin and prints as JSON
its numbered user stories (`user_stories`: `number`, `text`) and its
« Testing Decisions » (`testing_decisions`: the numbered items of that
section, or its lines when none is numbered). It reads no bead and writes
nothing; it exits 1 on a text without numbered user stories. The
publication door calls it on the approved Spec, so the unit of coverage has
one reader (`docs/ENTRY_CONTRACT.md`).

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
6. The Spec holds its side of the delivery entry contract (T07, see
   "Entry contract" below): numbered user stories, and, when a story
   describes an interface, a complete Validated Prototype reference, a
   state inventory and a conformant Validated Prototype.

On success it sets `spec_state=APPROVED_SPEC`, `approved_by`,
`approved_evidence` and `approved_digest` (`sha256:` of the bead's current
description text) as bead metadata in one `bd update`, then closes the
named map (`bin/planning-map close`) -- an unmapped Spec's `bd-approve`
never touches a map. `bd-status` recomputes the description's digest and
reports `void: true` once it no longer matches `approved_digest`, i.e. the
Spec was edited after approval and needs re-approval with fresh evidence.

## Entry contract (T07, af-tvda3w; spec af-wf4w5r sections 2 and 3)

The Spec is the unit of coverage of the delivery flow, so `bd-approve`
reads its text and refuses, naming what is missing, a Spec that cannot be
sliced and verified. Refusal messages are in French (Operator Language).
An already approved Spec is never re-examined: `bd-status` is unchanged.

What `bd-approve` reads in the Spec's description:

- **Numbered user stories.** A heading `User Stories` (any level) whose
  section holds at least one line starting with its number (`1. As a ...`).
  Numbers are the stories' identifiers and must not repeat.
- **Interface stories.** A story describes an interface when its line
  carries the tag `[interface]`. This is a declaration by the Spec's
  author: an untagged story is not detected.
- **Validated Prototype reference.** Required as soon as one story is
  tagged; checked whenever it is present. A heading `Validated Prototype`
  followed by four list items, in French or English: `branche`/`branch`,
  `commit` (the full 40-character id), `chemin`/`path`,
  `états`/`states` (comma-separated ids of the prototype's states).
- **State inventory.** Under that heading, one sub-heading per screen,
  `Écran : <name>`, each followed by a table `État | Statut | Détail`.
  `Statut` is `prototypé` (`Détail` names a state of the reference),
  `non prototypé`, or `sans objet` (`Détail` gives the reason). The six
  control states -- `vide`, `chargement`, `erreur`, `contenu long`,
  `écran étroit`, `thème sombre` -- are each listed for every screen;
  only they may be `sans objet`. Every state of the reference is
  prototyped in at least one screen.

```markdown
## User Stories

1. As a visitor, I want to see the items on the home page, so that I can read them. [interface]

## Validated Prototype

- branche : `prototype/<map>-<topic>`
- commit : `<40 hexadecimal characters>`
- chemin : `<directory of the frozen version>`
- états : `empty`, `content`

### Écran : accueil

| État | Statut | Détail |
| --- | --- | --- |
| vide | prototypé | empty |
| contenu | prototypé | content |
| chargement | sans objet | <reason> |
| erreur | non prototypé | |
| contenu long | non prototypé | |
| écran étroit | non prototypé | |
| thème sombre | sans objet | <reason> |
```

With a reference in hand, `bd-approve` reads the prototype from the remote
repository only -- `--prototype-remote <url>`, by default the `origin`
remote of `--repo-root`; a commit that exists only locally does not count.
It clones the named branch into a temporary directory (nothing is written
in `--repo-root`), refuses when the branch is absent, when the commit is
not on that branch, or when the path is absent at that commit, then runs
`bin/prototype-conformance check` on the path with the reference's states
(`docs/VALIDATED_PROTOTYPE.md`) and refuses a prototype that is not
conformant, quoting each failed property.

A Planning Run for a project whose repository is not this one passes that
project's repository as `--prototype-remote`.

## Acceptance mapping (bead mode)

| Acceptance criterion | How the tool and tests check it |
| --- | --- |
| A test per refusal (wrong target while reserved, unfinished map, wrong approver, empty evidence, no map and no No-fog evidence) shows the Spec bead and the map left untouched. | `SpecApproveBeadModeTest.test_bd_approve_refuses_*` in `tests/spec-approve-test.py`: each seeds a fake `bd` state, asserts a non-zero exit and an actionable `error`, then re-reads the state to prove neither the Spec bead's metadata nor the map's status changed. |
| A test shows a valid mapped Spec approved, its digest recorded and its map closed. | `test_bd_approve_approves_valid_mapped_spec_records_digest_and_closes_map` asserts `spec_state`, `approved_by`, `approved_digest` on the Spec bead and `status: closed` on the map. |
| A test shows a valid unmapped Spec approved with its No-fog evidence. | `test_bd_approve_approves_valid_unmapped_spec_with_no_fog_evidence` approves a Spec whose `planning_map` is `"none"` and asserts `map_closed: false`, `map: null`. |
| A test shows a Spec edited after approval reported void by status. | `test_bd_status_reports_void_after_spec_edited_post_approval` edits the fake bd state's description post-approval and asserts `bd-status` reports `void: true`; `test_bd_status_reports_not_void_when_unchanged` proves the negative case. |
| T07: a Spec without numbered user stories is refused, metadata unchanged. | `SpecApproveEntryContractTest.test_refuses_a_spec_whose_user_stories_are_not_numbered` (and `..._without_a_user_stories_section`, `..._numbers_repeat`): every refusal test of that class compares the whole fake tracker state before and after. |
| T07: an interface story without a prototype reference (branch, commit, path, states), or a commit absent from the remote repository, is refused naming what is missing. | `test_refuses_an_interface_story_without_prototype_reference`, `test_refuses_a_reference_without_commit`, `test_refuses_a_reference_without_branch_path_or_states`, `test_refuses_a_reference_whose_commit_is_not_on_the_remote_repository` (and `..._branch_...`, `..._path_...`). |
| T07: a missing or incomplete state inventory is refused. | `test_refuses_a_spec_without_state_inventory`, `test_refuses_an_inventory_missing_one_of_the_six_control_states`, `test_refuses_a_state_that_is_neither_prototyped_nor_not_prototyped`, `test_refuses_a_control_state_without_object_and_without_reason`, `test_refuses_a_prototyped_state_that_the_reference_does_not_list`. |
| T07: a Validated Prototype that is not conformant is refused. | `test_refuses_when_an_anchor_is_removed_from_the_prototype`, `test_refuses_when_a_state_dataset_is_missing_from_the_prototype`, on a prototype branch whose frozen files differ from the fixture's by one edit. |
| T07: the fixture Spec is approved; a Spec without interface is approved without reference; approved Specs stay approved. | `test_approves_the_fixture_spec`, `test_approves_a_spec_without_interface_and_without_prototype_reference`, `test_an_already_approved_spec_without_numbered_stories_stays_approved`. |
| CI is green. | `tests/spec-approve-test.py`, `tests/project-planning-profile-test.py` and `tests/project-registry-test.sh` run under `bin/ci-run-tests`. |
