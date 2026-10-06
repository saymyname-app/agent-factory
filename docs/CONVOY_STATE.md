# Convoy State (T33, T34, T10, T11, T13, T18, Spec af-wf4w5r §0 rules 2 and 5)

## Status and purpose

`bin/convoy-state` is the only reader and writer of the durable state of a
convoy that carries the **new-flow mark**. The state lives in the tracker
(bead metadata under `gc.flow.*`), never in a session. Every other script of
the Delivery Workflow goes through this command; none writes a `gc.flow.*`
key itself. A field that is missing is added here, in the ticket that needs
it, with its closed list and its refusal test.

A convoy without the mark is not touched: `show` and every write answer
« pas un convoi du nouveau flux » (exit 4) and write nothing, so it is
published, dispatched, merged and closed exactly as before.

```bash
./bin/convoy-state list                                 # the open marked convoys (bin/convoy-advance)
./bin/convoy-state mark af-convoy \
  --demonstration-line af-t1="Sur le produit lancé, …" \
  --user-stories af-t1=4,12 \
  --establishes-launch-recipe af-t1 \
  --prototype-fold af-t1                                # publication door (T05, T06, T36)
./bin/convoy-state show af-convoy --repo rigs/product   # every reader
./bin/convoy-state set-branch   af-convoy af-t1 --branch ticket/af-t1
./bin/convoy-state set-session  af-convoy af-t1 --session <session name>   # bin/ticket-author start
./bin/convoy-state record-gate  af-convoy af-t1 --gate dispatch   # bin/dispatch-door --convoy, after the sling
./bin/convoy-state set-exit     af-convoy af-t1 --exit finished
./bin/convoy-state set-verdict  af-convoy af-t1 --kind code_review --state favorable --commit <sha>
./bin/convoy-state bump-counter af-convoy --ticket af-t1 --counter resumes --counter correction_rounds
./bin/convoy-state set-counter  af-convoy --counter end_rounds --value 0
./bin/convoy-state add-evidence af-convoy af-t1 --piece red_proof --digest sha256:<hex> --commit <sha>
./bin/convoy-state record-gate  af-convoy af-t1 --gate ticket_end --commit <sha>
./bin/convoy-state set-tdd      af-convoy af-t1 --step red --commit <sha> --base <start sha>   # bin/tdd-step, once a step is proven
./bin/convoy-state stop-ticket  af-convoy af-t1 --reason criterion_already_green --detail "critère 2 déjà vert : …"   # bin/tdd-step
./bin/convoy-state open-test-review   af-convoy af-t1 --commit <sha> --file request.json   # bin/test-review review
./bin/convoy-state launch-test-review af-convoy af-t1 --bead af-review                     # bin/test-review, once the reviewer is sent
./bin/convoy-state record-test-review af-convoy af-t1 --file verdict.json                  # bin/test-review record
./bin/convoy-state stop-raised af-convoy af-t1                                              # once the escalation door accepted the stop
./bin/convoy-state set-handoff af-convoy af-t1 --file handoff.json                                   # bin/ticket-exit
./bin/convoy-state park        af-convoy af-t1 --cause planning_exception --detail "La Spec fixe X, …"  # bin/ticket-exit
./bin/convoy-state set-integration af-convoy --branch integration/af-spec --protected main --base <sha>   # bin/spec-integration open
./bin/convoy-state set-merge   af-convoy af-t1 --outcome merged --ticket-commit <sha> --integration <sha> --commit <sha>   # bin/spec-integration merge
./bin/convoy-state invalidate-verdicts af-convoy af-t1 --tip <sha> --kind code_review --kind evaluation   # bin/spec-integration merge
./bin/convoy-state ticket af-t1                         # does this bead carry the mark? (bin/dispatch-door, the Mayor)
./bin/convoy-state record-incident af-convoy --bead af-incident [--signature sha256:<hex>]   # bin/convoy-advance
./bin/convoy-state clear-incident  af-convoy            # bin/convoy-advance, once the state is valid again
```

Every answer is one JSON object on stdout.

| Exit | Meaning |
|---|---|
| 0 | done |
| 1 | refused, or could not run: nothing was written (`{"ok": false, "error": "refus : …"}`) |
| 3 | `show` or `ticket` found an « état sans règle »: the state is printed, with the reason |
| 4 | the convoy, or the ticket asked by `ticket`, does not carry the mark: « pas un convoi du nouveau flux » |

## Stored fields and closed lists

| Field | Key | On | Values |
|---|---|---|---|
| Mark | `gc.flow.mark` | convoy, ticket | `new-flow/v1` |
| Spec | `gc.spec_id` (read only: written by the publication door) | convoy | the id of the Spec the convoy delivers; the evidence store is filed under it (T09, `docs/EVIDENCE_STORE.md`) |
| Kind | `gc.ticket_kind` (read only: written by the publication door) | ticket | `vertical_slice`, `prefactoring`, `repair` |
| Demonstration line | `gc.flow.demonstration_line` | ticket (`vertical_slice`, `repair`) | one non-empty line, written once by `mark` |
| Covered user stories | `gc.flow.user_stories` | ticket (`vertical_slice`) | the numbers of the Spec's user stories the slice covers, at least one, each once; written once by `mark` |
| Launch recipe established here | `gc.flow.establishes_launch_recipe` | ticket (`vertical_slice`, at most one per convoy) | `true`, written with the mark; absent otherwise |
| Prototype Fold | `gc.flow.prototype_fold` | ticket (`vertical_slice`) | `true`, written with the mark; absent otherwise |
| Ticket branch | `gc.flow.branch` | ticket | branch name |
| Author session | `gc.flow.session` | ticket | `name`, `at`; the same write puts the ticket `in_progress` with `gc.session_name`. Refused for a session that already took another ticket of the convoy, for a ticket the dispatch door did not start, for a closed ticket |
| Ticket Exit | `gc.flow.exit` | ticket | `finished`, `planning_exception`, `operator_request`, `technically_blocked`, `interrupted` |
| Verdict | `gc.flow.verdict.<kind>` | ticket | kind: `test_review`, `code_review`, `evaluation`, `fidelity`; state: `favorable`, `unfavorable`; always with the full commit SHA it judged; `invalidated` (`tip`, `at`) once `invalidate-verdicts` wrote that a newer commit outdated it |
| Counter | `gc.flow.counter.<name>` | ticket: `resumes`, `correction_rounds`; convoy: `end_rounds` | integer ≥ 0 |
| Evidence fingerprint | `gc.flow.evidence.<piece>` | ticket | `sha256:<64 hex>` and the commit of the piece |
| Gate record | `gc.flow.gate.<gate>` | ticket | `dispatch`, `ticket_end` (commit required), `withdrawn` (removed from the graph by a resolved Planning Exception) |
| TDD step | `gc.flow.tdd.<step>` | ticket | step: `red`, `freeze`, `green`, `amendment`, `prefactoring`; always with the full commit SHA it was proven at; `red` and `prefactoring` with their start commit (`base`), `amendment` with its one-line reason |
| Stop | `gc.flow.stop` | ticket | reason: `criterion_already_green`, `amendment_exhausted`, `test_review_refused`, `test_review_no_result`; with a one-line detail, and `raised` once `stop-raised` wrote that the escalation door accepted it |
| Test review | `gc.flow.test_review` | ticket (`vertical_slice`, `repair`) | `rounds`: each recorded pass (`commit`, `files`: path → `sha256:`, `verdict`: `favorable` / `unfavorable`, `tests`: test id → `state` and, when unfavorable, `reason`, `recorded_by`, `at`); `request` while a review is open (`commit`, `files`, `criteria`: the criterion → test table, `launches`: at most two `{bead, at}`, `at`) |
| Ticket Handoff | `gc.flow.handoff` | ticket | `sections` (`done`, `deviations`, `not_done`, `out_of_ticket`: each `aucun` or a non-empty list of one-line items; an item of `not_done` may be `{what, paths}`), `partial`, the full commit SHA it was taken at, and the `records` written by code |
| Parking | `gc.flow.park` | ticket | cause: `planning_exception`, `operator_request`; the ticket whose Ticket Exit parked it (`origin`); a one-line detail |
| Integration branch | `gc.flow.integration` | convoy | `branch`, the `protected` branch it takes up, and `base`, the full commit SHA of the protected branch it left from; written once |
| Merge | `gc.flow.merge` | ticket | outcome: `merged`, `conflict`, `red`; `ticket_commit` (the tip of the ticket that was taken), `integration` (the tip it was merged on), and `commit`, the merged result, for `merged` and `red` only |
| Declared Scope | `gc.scope_paths` (read only: written by the publication door) | ticket | the declared paths, comma-separated; they order tickets and bound nothing |
| Acceptance criteria | the bead's description (read only) | ticket | the checkbox lines under `## Acceptance criteria`, in order |
| Factory incident | `gc.flow.incident` | convoy | the bead that carries the open incident of a stopped convoy and, once it reached the escalation door, the `sha256:` signature of the anomalies it names |

`mark` is idempotent: it marks the tickets first and the convoy last, sets
each counter to an explicit `0`, and on a later run marks only the tickets
added since (a patch), leaving existing counters alone.

A ticket is marked with its entry fields or not at all (T05,
`docs/ENTRY_CONTRACT.md`): `mark` writes the demonstration line of a ticket
in the same tracker write as its mark, from `--demonstration-line
<ticket>=<line>` (repeatable). It refuses, before any write, a ticket whose
kind is absent or outside the closed list (no default kind), a
`vertical_slice` or a `repair` without a demonstration line, a line on a
`prefactoring`, a line for a ticket the convoy does not track, and a line
that differs from the one already written: it is frozen with the approved
graph.

The same holds for the user stories a `vertical_slice` covers (T06),
written from `--user-stories <ticket>=<n>,<n>` (repeatable): `mark` refuses
a `vertical_slice` without any, a list on a `prefactoring` or a `repair`
(neither covers a story), anything that is not a list of story numbers each
given once, and a list that differs from the one already written.
`--establishes-launch-recipe <ticket>` (repeatable) names the slice that
establishes the project's launch recipe: refused on anything but a
`vertical_slice`, on more than one ticket of the convoy, and on a ticket
that already carries the mark without it. `--prototype-fold <ticket>`
(T36) names the slice that is the Prototype Fold of the Spec's Validated
Prototype: refused on anything but a `vertical_slice` of the convoy and on
a ticket that already carries the mark without it. That a graph has one
Fold, and that the interface tickets wait for it, is the publication
door's check (`docs/ENTRY_CONTRACT.md`).

`add-evidence` is called by `bin/evidence-capture` (T09), which files the
piece in the evidence store and computes its fingerprint
(`docs/EVIDENCE_STORE.md`); a fingerprint written by hand for a piece the
tool did not produce is refused by `evidence-capture verify`.

`set-tdd` is called by `bin/tdd-step` (T10, `docs/TDD_STEP.md`) once the
check of a step has passed and its report is a piece of the evidence store.
The order of the steps is held here, under the lock: `freeze` needs a `red`
at the same commit; once frozen, a new `red` or `freeze` is accepted only at
the commit of the ticket's `amendment`; `amendment` needs a freeze and is
written once per ticket; `green` needs a freeze; `prefactoring` is the only
step of a `prefactoring` ticket and is refused on another kind. `stop-ticket`
writes why a script stopped the ticket (Spec §5: a criterion already green,
a second amendment); a stopped ticket takes no further step, and a second
stop is refused. Nothing here lifts a stop.

`open-test-review`, `launch-test-review` and `record-test-review` are called
by `bin/test-review` (T13, `docs/TEST_REVIEW.md`), which holds the review of
a ticket's criterion tests between red and freeze. `open-test-review` opens
a review of the tests proven red at `--commit`, with the fingerprints the
freeze will seal and the criterion → test table (`--file`, a JSON object
`{files, criteria}`); the same request again writes nothing, another one
replaces the request that was open. It refuses a `prefactoring`, a ticket
already frozen, a commit that is not the one of the `red` step, a request
without fingerprints or with a test whose file has none, tests a pass
refused and that did not change, and tests already reviewed favorably at
that commit. `launch-test-review` records each reviewer bead sent for the
open request: the first, then one relaunch; a third is refused.
`record-test-review` takes the answers of the reviewer (`--file`: `commit`,
`files`, `tests`, `recorded_by`) and refuses, with every reason listed, a
verdict when no review is open, on another commit or other fingerprints
than the request, with a test left out or unknown, a state outside the
closed list, or a refusal without a reason. The verdict is computed here:
`unfavorable` as soon as one test is. The pass is appended and the request
closed in one tracker write; a **second** unfavorable pass writes the stop
(`test_review_refused`) in that same write (Spec §8: one return to the
author). `set-tdd --step freeze` is refused unless the last pass is
favorable, was given at the commit being frozen, and no review is open; the
freeze that ends an amendment is exempt (Spec §6: the code review reads an
amended test). `stop-raised` records that the stop of a ticket reached the
operator, so the code that stopped it raises it once; it refuses a ticket
that is not stopped, and the same record again writes nothing.

The verdict of the test review is not a `gc.flow.verdict.test_review`: a
verdict of that family holds only while its commit is the tip of the branch,
and this one holds for the frozen tests. The kind stays in the closed list
of `set-verdict`, unused by the flow.

`set-handoff` is called by `bin/ticket-exit` (T11, `docs/TICKET_EXIT.md`)
with the Handoff it built, as a JSON file: the sections of the author and
the records it sealed. It refuses a section that is absent or empty (a
complete Handoff has the four, each with content or `aucun`; only a
`partial` one may leave some out), a section it does not know, a complete
Handoff without records, and records without a `handoff_records` evidence
fingerprint at the commit of the Handoff: the records are written by code,
never given. `set-exit` itself is unchanged: that `finished` needs a valid
Handoff is the exit tool's refusal.

`park` writes the parking on the ticket and on every ticket of the convoy
that waits for it, directly or through others, following the `blocks` edges
read on each ticket; the descendants first, the ticket last, so that the
same call completes an interrupted one. A descendant that is closed or
already parked is left as it is. It refuses a cause outside the list, a
missing detail, a closed ticket and a ticket already parked. Nothing here
lifts a parking.

`set-integration`, `set-merge` and `invalidate-verdicts` are called by
`bin/spec-integration` (T18, `docs/SPEC_INTEGRATION.md`). `set-integration`
writes the integration branch of the convoy's Spec once: the same record
again writes nothing, another branch, protected branch or start commit is
refused. `set-merge` writes what the merge command did of a ticket; it
refuses an outcome outside the list, a `merged` or a `red` without the
commit of the merged result, a `conflict` with one, a convoy without a
recorded integration branch, and a closed ticket. `invalidate-verdicts`
(Spec §8, « commit après verdict ») writes on each named verdict the tip
that outdated it and adds one to `resumes`, in one tracker write; a verdict
already invalidated is left as it is and counts nothing more, so repeating
the call is harmless. It refuses a kind outside the list, a ticket that has
no such verdict, and a verdict that judged that very tip. `set-verdict`
writes a fresh verdict: replaying is what lifts an invalidation.

A piece name is made of letters, digits, `_` and `.` only: the tracker
refuses any metadata key outside `[a-zA-Z_][a-zA-Z0-9_.]*` (observed on bd
1.2.2), so a hyphen is refused here before it is tried.

## What a write refuses

Before anything is written: a verdict without a full commit SHA; a Ticket
Exit, verdict kind, verdict state, counter or gate outside its closed list;
a negative or non-integer counter; a ticket counter on the convoy or the
reverse; a counter write after which `correction_rounds` would exceed
`resumes` (a correction round counts among the resumes, Spec §8); an
evidence fingerprint without a `sha256:` digest or without a commit; a
Ticket Handoff, a parking, an integration branch, a merge or an invalidation
as described above; a
`ticket_end` gate record without a commit; a TDD step outside its closed
list, without a full commit SHA, out of order, or on a stopped ticket; a
freeze without a favorable test review at the same commit; a request, a
launch or a verdict of the test review as described above, or on a stopped
ticket; a stop whose reason is outside its closed list or that has no
detail; a ticket
that is not tracked by the convoy, or that does not carry the mark.

Writes on one convoy are serialised by a lock (`CONVOY_STATE_LOCK_DIR`,
default `$XDG_RUNTIME_DIR` or `/tmp`), so concurrent counter bumps are all
counted and a reviewer and an Evaluator can write the same ticket in parallel.

## What a read reports

`list` answers `{"convoys": [...]}`: the ids of the convoys that carry the
mark and are not closed. It is what `bin/convoy-advance` walks
(`docs/CONVOY_ADVANCE.md`); an unmarked convoy never appears in it.

`show` renders, per ticket: mark, kind, demonstration line, covered user
stories (`user_stories`, a list of numbers or `null`), whether it
establishes the launch recipe (`establishes_launch_recipe`), whether it is
the Prototype Fold (`prototype_fold`), tracker status,
branch and its tip, Ticket Exit, verdicts, counters, evidence fingerprints
and gate records, its acceptance criteria (`criteria`, the lines of its
description, numbered from 1 by `bin/tdd-step`), the proven steps of its
TDD (`tdd`, `{step: {commit, at, base?, reason?}}`), its stop (`stop`,
`null` when it is not stopped), the review of its criterion tests
(`test_review`, `null` before the first request), its Ticket Handoff (`handoff`), its parking
(`park`) and its Declared Scope (`declared_scope`, a list of paths), each
`null` when the ticket has none, and what the merge command did of it
(`merge`, `null` while it did nothing); and for the convoy the Spec it
delivers (`spec`, `null` when it names none), its counters, its open factory
incident (`incident`, `null` when there is none) and the integration branch
of its Spec (`integration`, `null` before it is opened).

`ticket` answers whether one bead carries the mark, without naming its
convoy: exit 0 and `"new_flow": true`, or exit 4 and `"new_flow": false`.
With `--bead-json -` it reads the bead from stdin, as `gc bd show --json`
printed it, instead of reading the tracker again: `bin/dispatch-door` asks
it that way on every dispatch, so a bead without the mark costs no further
tracker read and is dispatched exactly as before.

**Verdict validity** (Spec §8, « commit après verdict »). A verdict carries
`"valid": true` only while its commit is the tip of the ticket's branch in
`--repo` (default: the current directory; the local branch is read first,
then `origin/<branch>`). A commit added to the branch after the verdict
makes it `"valid": false`: nothing is rewritten by a read, the verdict simply has
to be replayed on the new tip. The merge command is what writes it
(`invalidate-verdicts`): the verdict then carries `invalidated` and stays
`"valid": false` until a fresh one replaces it.

**« État sans règle »** (Spec §0 rule 5). A ticket in one of these states
carries `"signal": "état sans règle"` and one `{field, reason}` per anomaly
in `unruled`; the offending field is rendered as `{"unruled": reason, "raw":
stored value}` (a verdict keeps its state and commit but has no `valid`
key), never as a default value:

- closed without a `ticket_end` or `withdrawn` gate record (closed outside
  the gate);
- in progress without a `dispatch` gate record (started outside the gate);
- a verdict whose commit is not on the ticket's branch, whose ticket has no
  recorded branch, or whose branch cannot be found in `--repo`;
- a counter that is absent, not an integer ≥ 0, or `correction_rounds`
  above `resumes`;
- a ticket without the mark in a marked convoy, or an unknown mark;
- a kind that is absent or outside the closed list (never rendered as a
  kind), a `vertical_slice` or a `repair` without a demonstration line, a
  demonstration line on a `prefactoring`;
- a `vertical_slice` without covered user stories, covered user stories or
  a launch recipe established on another kind, a Prototype Fold of another
  kind;
- any stored value this command would have refused to write, and any
  `gc.flow.*` key it does not know (a field invented outside the command).

`convoy-state` only signals. `bin/convoy-advance` stops the convoy and
raises the factory incident (`docs/CONVOY_ADVANCE.md`); it records that
incident here with `record-incident` (first the bead alone, then the
signature once the escalation door accepted it) and removes it with
`clear-incident` when the state is valid again. Both are accepted on a
convoy whose mark is unknown, which is itself an « état sans règle » to
report. An incident record that this command would not have written is one
more anomaly of the convoy.

## Proof

`tests/convoy-state-test.py` drives the command line on a fake tracker
state (`tests/fixtures/convoy-state/gc`): one test per pass and per
refusal, each refusal re-reading the tracker to prove nothing was written.
`tests/convoy-state-real-tracker-test.sh` (local-only) replays the same
contract on the real `gc`/`bd` in a disposable city, a Ticket Handoff of
20 kB, a parking along real `blocks` edges, and the integration branch, an
invalidated verdict and a merge (T18) included.
