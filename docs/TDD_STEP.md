# TDD Step (T10, Spec af-wf4w5r §5)

## Status and purpose

`bin/tdd-step` proves, by script, the TDD of a ticket of a convoy that
carries the **new-flow mark**: that the criterion tests were written first
and seen red, that they did not change between red and green, and that they
pass. The author writes the tests and the code; no sentence of the author is
a proof. A convoy without the mark is not touched (exit 4).

The author formula calls it at its red and code steps, and its gates read
what it proved (`docs/TICKET_AUTHOR.md`). No test review stands between
`red` and `freeze` (ADR-0030 L3): the code review reads the criterion tests
after the green (`docs/CODE_REVIEW.md`); a `gc.flow.test_review` left on a
ticket in flight is not read.

```bash
./bin/tdd-step red          af-convoy af-t1 --repo <ticket worktree> --profile <descriptor.json> --dataset content \
                            --base <start commit> --table tests/criteria.json
./bin/tdd-step freeze       af-convoy af-t1 --repo <ticket worktree>
./bin/tdd-step green        af-convoy af-t1 --repo <ticket worktree> --profile <descriptor.json> --dataset content
./bin/tdd-step amend        af-convoy af-t1 --repo <ticket worktree> --profile <descriptor.json> --dataset content \
                            --reason "le champ s'appelle dataset_name dans la Spec"
./bin/tdd-step prefactoring af-convoy af-p1 --repo <ticket worktree> --profile <descriptor.json> --base <start commit>
```

Every step checks the branch checked out in `--repo` at its HEAD, and is
refused when tracked files differ from HEAD. Every answer is one JSON object
on stdout.

| Exit | Meaning |
|---|---|
| 0 | the step is proven: its report is a piece of the evidence store, the step is written on the ticket |
| 1 | refused: nothing was written, in the tracker or in the store (`{"ok": false, "error": "refus : …"}`) |
| 4 | the convoy does not carry the mark: « pas un convoi du nouveau flux » |
| 5 | the ticket is stopped: the stop is written on the ticket (`"stopped": true`), and nothing else |

## How a step is proven

The check of a step is run by `bin/evidence-capture command --expect-exit 0`
(`docs/EVIDENCE_STORE.md`): its JSON report is the output of a sealed piece,
tied to the commit, whose fingerprint is on the ticket. A check that refuses
exits non-zero, so nothing is filed. The step is then written on the ticket
by `bin/convoy-state set-tdd` (`docs/CONVOY_STATE.md`), which holds the
order of the steps under its lock.

| Step | Piece | Report (`output` of the piece, JSON) |
|---|---|---|
| `red` | `tdd_red` | `verdict: red`, `base`, `table`, `criteria` {number: [test id]}, `satisfied` [the numbers of the criteria already green at `base`], `tests` [{`id`, `outcome`, `seam`, `seam_mode`, `entry_points` for a black-box test}], `seam_mode` (the modes the tests went through, joined by `+`: `black_box`, `black_box+import_rule`), `launch.healthy` |
| `freeze` | `tdd_freeze` | `files` {path: `sha256:`}, `table`, `criteria`, `satisfied` (from the red): the **registry of fingerprints** |
| `green` | `tdd_green` | `verdict: green`, `k`, `satisfied` (from the registry), `tests` [{`id`, `runs`: k outcomes, `seam`, `seam_mode`}], `frozen` (the commit of the freeze), `regression` [{`commit`, `exit_code`}] at HEAD |
| `amend` | `tdd_amendment` | the red report of the amended tests, plus `amendment` {`reason`, `diff`, `files`, `previous_freeze`} |
| `prefactoring` | `tdd_prefactoring` | `verdict: unchanged`, `regression` [{`commit`, `exit_code`}] before and after |

## What the profile declares

`--profile` is the project descriptor (`docs/PROJECT_PLANNING_PROFILE.md`,
`launch` block). The steps read `test_perimeter`, `frozen_harness_paths`,
`test_command`, `seams` (the normalized list: a profile that declares
`seam_mode` has one seam named `default` over the whole test perimeter),
`entry_points`, `regression_command`, `k` (3 when the profile declares
none), and the optional `red_error_types` and `import_rule`, both shared by
all seams.

**`test_command`** runs one test and writes its report: it carries `{test}`
(a test id, a file of the test perimeter optionally followed by `::…`) and
`{report}` (where to write a JUnit XML file, one `testcase` per test, with a
`failure` child for an assertion failure, an `error` child with its `type`
for any other exception, a `skipped` child for a skipped test). It runs
from the root of a clean tree, with the address of the launched product in
`PRODUCT_ADDRESS`. A command without `{report}` is refused: an exit code
alone does not tell a failure from an error.

## Red

The author has committed the criterion tests and a criterion → test table
(`--table`, a JSON file of the test perimeter: `{"criteria": {"1": ["<test
id>", …], "2": […]}}`, numbered like the checkbox lines under `## Acceptance
criteria` of the ticket). `red` refuses, naming what is wrong:

- a file changed since `--base` outside the test perimeter (« fichier modifié
  hors du périmètre de test : … ») ;
- a criterion without a test, a test id outside the test perimeter, a test
  file that does not exist ;
- a product that is not healthy when `bin/project-launch` launches it at the
  start commit ;
- a test that runs nothing (« test vide »), is skipped, or ends in error
  (« test en erreur », with the type) : a valid red is an assertion failure
  reported per test ;
- a test that does not go through an entry point of the product (below).

Two declared cases accept an error as the red: on the slice that
`establishes_launch_recipe`, the launch failure is the expected red
(`launch.healthy` is `false` in the report); an error whose type is listed
in the profile's `red_error_types` (a missing symbol on a library seam).

**A criterion already green is satisfied by the existing code** (ADR-0030
L5): if every test is otherwise valid and every test of a criterion passes
at the start commit, the red is proven for the other criteria and the report
names that criterion in `satisfied` (its tests carry `outcome: passed`; the
piece is sealed with the start commit `base`, so the evidence is the
criterion test passing there). The freeze and the green carry `satisfied`
on; its tests stay frozen and must pass at the green like the others. A
test green at the start commit in a criterion that another of its tests
keeps red is a plain refusal, no stop (« test vert au commit de départ : …
(critère N encore rouge) »): the author fixes the table or the test.
**Only a ticket whose criteria are all already green stops**: the answer
names them (« critère 2 déjà vert »), `bin/convoy-state stop-ticket` writes
the stop (`criterion_already_green`) and the exit status is 5. A stopped
ticket is refused by every step.

### Proof of the seam

Each criterion test is proven by the mode of the seam it goes through: the
seam whose `test_paths` hold the file of the test. A test under no declared
seam is refused (« test hors de tout seam : … », the declared seams named).
The report names, per test, its `seam` and `seam_mode`.

- `black_box`: the tests of such a seam run in a tree that holds only the test perimeter
  and the frozen harness paths, so they cannot read or import the code of
  the product; they reach the product through a recording proxy placed in
  front of it. A test that sent no request to a declared `http` entry point
  is refused (« aucun point d'entrée du produit : … »); the entry points each
  test went through are in the report (`"entry_points": ["GET /"]`).
- `import_rule`: the tests of such a seam run in the tree of the start
  commit, under the tests of HEAD. The profile's `import_rule` gives two regular expressions
  applied to each line: a line matching `product_import` must match
  `entry_point_import` (« règle d'import », file, line and text named), and
  every criterion test file must import an entry point. The rule is applied
  to the files of import-rule seams only.

## Freeze

`freeze` takes no profile: it freezes what the red proof at HEAD says was
proven. It records the SHA-256 of the table, of each criterion test file
and of each frozen harness path in the piece `tdd_freeze` — the registry of
fingerprints, in the evidence store, filed under the Spec, outside any work
tree (a store inside a Git repository is refused) and sealed. It is refused
without a red proof at the same commit: a commit added after the red means
the red is replayed first.

## Green

`green` verifies the registry through `evidence-capture verify` (a registry
rewritten by hand no longer matches the fingerprint of the tracker), then
refuses any frozen file that is no longer what was frozen (« fichier gelé
modifié : … », « fichier gelé supprimé ou déplacé : … » — a removed test, a
renamed one, a test left out of the table, a harness file). It then runs the
test ids of the frozen table, from the files of the frozen commit, against
the product launched at HEAD, each in the tree of its seam's mode, `k` times
in a row (3 when the profile declares no `k`): a test that never passes
is « test en échec », a mixed result is « test instable », a skipped test is
refused. Last, the profile's `regression_command` runs once in a clean tree
of HEAD (ADR-0030 L1): a non-zero exit is « commande de régression en échec
à la pointe du ticket », a plain refusal — no stop, no resume — so the author
fixes the code in the same session and runs `green` again. A change that
keeps its criterion tests green but breaks existing tests is caught at the
author's handoff (the `code` gate of `bin/ticket-author` asks for `green` at
the tip), not only at the merged regression of `bin/spec-integration`.

## Amendment

One path changes a frozen test, once per ticket. The author commits the
change, then `amend --reason`: the amended tests are proven red again against
the product at the start commit recorded by `red` (a test that passes there
is refused, without stopping the ticket, unless its criterion was recorded
`satisfied` by the first red), the piece `tdd_amendment` records
the reason and the diff of the frozen files since the freeze, and the new
state is frozen. The ticket then carries `tdd.amendment` (commit, reason):
this is the deviation the Ticket Handoff reports (`records.amendment`,
`docs/TICKET_EXIT.md`). After an amendment, the
red proof of the amended tests is `tdd_amendment`; `tdd_red` stays the first
one.

A second `amend` on the same ticket stops it (`amendment_exhausted`, exit
5). The next pass of `bin/convoy-advance` raises that stop to the operator,
once (`docs/CONVOY_ADVANCE.md`, « A ticket stopped at its second amendment
reaches the operator »). If the freeze that ends an amendment could not be recorded, `tdd-step
freeze` at the same commit completes it.

## Prefactoring

A `prefactoring` ticket has no red step (`red` refuses it; `prefactoring`
refuses another kind). The profile's `regression_command` is run in a clean
tree of `--base`, then of HEAD: both must exit 0 (« commande de régression
en échec avant / après le changement »). A file of the test perimeter or of
the frozen harness that existed at `--base` and was modified or deleted is
refused (« test existant modifié : … »); added tests are allowed.

**Characterization tests first.** When the test perimeter holds no file at
`--base` (the frozen harness aside), the regression command has no test to
run there and the regime refuses to start (« … Écrire d'abord des tests de
caractérisation … »), nothing recorded. It is accepted once the first
commits after `--base` add nothing but files of the test perimeter: the last
of them is the characterization commit. The « avant » run is then taken at
that commit — the product of the start commit, with those tests — and must
exit 0; from there those tests are existing tests, so a later commit that
modifies or deletes one is refused. The proof names the commit
(`characterization`). Tests added in the same commit as the change do not
count: nothing shows they passed before it.

The control is on the files, not on what the command runs: a
`regression_command` is opaque and reports no count of tests.

## Limits

- The scripts prove the order and the outcomes, not that a test observes its
  criterion: that is the code reviewer's question, asked after the green
  (`docs/CODE_REVIEW.md`, ADR-0030 L3).
- `amend` proves the amended tests red at the start commit; it does not
  re-check that only the test perimeter changed, since the code of the
  ticket is written by then.
- A frozen harness file changed on the integration branch by another
  ticket's merge is seen by `green` as modified.
- Lifting a stop is not in this command.

## Proof

`tests/tdd-step-test.py` drives the command lines on a fake tracker state,
against a copy of the Delivery Fixture City launched for real by
`bin/project-launch` and with pieces filed for real by
`bin/evidence-capture`: one test per pass and per refusal, each refusal
re-reading the tracker and the store to prove nothing was written.
`tests/convoy-state-real-tracker-test.sh` (local-only) replays the stored
steps, the stop and the acceptance criteria on the real `gc`/`bd`.
