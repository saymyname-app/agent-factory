# Spec integration branch and serial merge (T18, T14, T21, T23, Spec af-wf4w5r §4, §6, §8 and §9)

## Status and purpose

A convoy that carries the **new-flow mark** delivers its Spec on one
integration branch. `bin/spec-integration` opens that branch when the convoy
is published and merges the tickets into it, one at a time, with tests on
each merged result. No ticket opens a pull request toward the protected
branch, and the protected branch receives nothing: its one merge comes after
the acceptance, made by `bin/outcome-promote` (T30,
`docs/OUTCOME_PROMOTE.md`). A convoy without the mark is not touched
(exit 4).

```bash
./bin/spec-integration open  af-convoy --repo <project repository> --protected main
./bin/spec-integration merge af-convoy --repo <project repository> --profile <descriptor.json> [--limit 1] [--timeout 1260]
./bin/spec-integration take-up af-convoy --repo <project repository> --profile <descriptor.json> [--timeout 1260] [--end-round]
```

Who calls it: `bin/ticket-graph-publish bd-publish` calls `open` once the
convoy is marked (`docs/ENTRY_CONTRACT.md`); `bin/convoy-advance` calls
`merge --limit 1` on each of its passes for a convoy that has a finished
ticket (`docs/CONVOY_ADVANCE.md`); `bin/spec-end run` calls `take-up
--end-round` for the one tip of the end-of-Spec gate (`docs/SPEC_END.md`).
No agent decides when a ticket is merged.

Every answer is one JSON object on stdout.

| Exit | Meaning |
|---|---|
| 0 | done: what was merged or returned to its author is listed, possibly nothing |
| 1 | refused (`{"ok": false, "error": "refus : …"}`), or a ticket was refused (listed under `refused`) |
| 3 | the convoy is in an « état sans règle » (`bin/convoy-state show`): nothing is merged |
| 4 | the convoy does not carry the mark: « pas un convoi du nouveau flux » |

## The branches

The integration branch is `integration/<spec id>`, the Spec being the one
the convoy names (`gc.spec_id`). When the repository has a remote `origin`,
the protected and the integration branches are read there, after a fetch,
and the integration branch is pushed there; a repository without that remote
uses its local branches. A ticket branch is read as `bin/convoy-state` reads
it: the local branch first, then `origin/<branch>`.

Nothing is ever checked out in the repository itself: the merges of a pass
are made in a work tree of their own (`SPEC_INTEGRATION_WORK_DIR`, default
under `$XDG_RUNTIME_DIR` or `/tmp`), removed at the end of the pass; one left
by an interrupted pass is removed by the next. The merge commits are authored
by « Agent Factory ».

## `open`

Creates the branch at the tip of the protected branch and records it on the
convoy through `bin/convoy-state set-integration` (branch, protected branch,
commit it left from). Opening it again changes nothing. A branch of that
name that exists without being recorded is taken as it is when it holds no
commit the protected branch lacks (an `open` interrupted before its record);
otherwise it is refused: it was not opened by this command. Refused too: a
convoy that names no Spec, a protected branch the repository does not have.

## `merge`

One pass reads the convoy through `bin/convoy-state show` and takes its
tickets in the convoy's order. A ticket is **ready** when its author has
finished at the tip of its branch — Ticket Exit `finished`, and a complete
Ticket Handoff taken at that very tip — and its **code review and its
Ticket Evaluation are favorable at that tip** (below). The other tickets are
left alone; those worth a word are listed under `waiting` with the reason
(parked, stopped, an unfavorable verdict, a verdict to replay, an author
still at work, a code review or a Ticket Evaluation that is absent, open or
unfavorable, a ticket already returned to its author).

**No merge without a favorable code review** (T14, Spec §6,
`docs/CODE_REVIEW.md`). A finished ticket is merged only when the last
round of its code review (`code_review.state` of `bin/convoy-state show`)
is favorable, was given at the tip, no round is open, and the verdict
`code_review` is favorable and valid at the tip. A ticket with no review, a
review still running or left without output, a Blocking Finding without a
favorable verdict (named in the reason), or a favorable verdict written
without the review it comes from, stays under `waiting`: nothing of it is
merged, nothing is written.

**No merge without a favorable Ticket Evaluation** (T15, Spec §7,
`docs/TICKET_EVALUATION.md`). The same holds for the evaluation of the
launched product: a finished ticket is merged only when the last round of
its evaluation (`evaluation.state` of `bin/convoy-state show`) is favorable,
was made at the tip, no evaluation is open, and the verdict `evaluation` is
favorable and valid at the tip. For a `prefactoring` that round is the
control that its product starts. A ticket with no evaluation, an evaluation
still running or left without result, a state that is not « observé »
(named in the reason), an outage of the environment, or a favorable verdict
written without the evaluation it comes from, stays under `waiting`.

Passes on one convoy are serialised by a lock (`SPEC_INTEGRATION_LOCK_DIR`):
two merges are never made at once, and each merge is made on the result of
the one before. `--limit N` merges at most N tickets in the pass.

For the ready tickets, in order:

1. **The integration branch takes up the protected branch**, once per pass,
   when it does not already hold its tip. The takeover is a merge commit of
   its own, tested by the same command, and pushed before any ticket is
   merged. A takeover in conflict, or red, is refused for the whole pass: no
   ticket is merged, nothing is pushed, no ticket is blamed.
2. **The ticket is merged** (`git merge --no-ff`) on the current tip.
3. **The tests run on the merged result**: the `regression_command` of the
   project's profile (`--profile`, `docs/PROJECT_PLANNING_PROFILE.md`), run
   from the root of the work tree by `bin/evidence-capture command`. The
   record is the piece `merged_tests` of the ticket, tied to the commit of
   the merged result (`docs/EVIDENCE_STORE.md`).
4. **Green**: the integration branch moves to the merged result, and only
   from the tip the merge was made on. The ticket carries `merge.outcome:
   merged` with that commit.

| Outcome | What is written | What happens to the branches |
|---|---|---|
| `merged` | `merge` on the ticket (`merged`, ticket tip, integration tip before, commit of the result), piece `merged_tests` at that commit | the integration branch moves to the result |
| `returned`, cause `conflict` | `merge` (`conflict`, ticket tip, integration tip) | nothing: the merge is aborted, the conflicting files are named in the answer |
| `returned`, cause `red` | `merge` (`red`, ticket tip, integration tip, commit of the tested result), piece `merged_tests` with its non-zero exit code | nothing is pushed: the integration branch stays on its green tip |
| `refused` | the outdated verdicts are marked invalid, one resume is counted | nothing |

**Returned to its author.** A conflict or a red belongs to the ticket being
merged. Nothing here resolves a conflict or repairs a test: the ticket waits
for a new commit of its author, who takes up the integration tip in a fresh
session. That session is sent by the next pass of `bin/convoy-advance`,
which counts one resume of cause `returned` (T20,
`docs/CONVOY_ADVANCE.md`). It is not tried again until its tip has changed
and its author has finished again at the new tip.

**A commit added after a verdict** (Spec §8). When the branch of a ticket
has a commit newer than the commit its code review or its Ticket Evaluation
judged, the merge of that ticket is refused: `bin/convoy-state
invalidate-verdicts` marks each outdated verdict invalid, with the tip that
outdated it, and counts one resume (K) — not the correction round — in the
same tracker write. The next passes count nothing more and list the ticket
under `waiting` until the verdicts are replayed on the new tip
(the code review and the Ticket Evaluation each record a new round there).
When the outdated verdicts were given at the commit of the ticket's
correction round, the reason says « aucune reprise de plus n'est comptée » :
that round was counted when it was opened (`docs/CORRECTION_ROUND.md`). The
same holds when they were given at the commit the merge returned and the
pass already counted a `returned` resume for that return (T20): the return
is counted once, not twice. A verdict that is merely unfavorable
merges nothing and invalidates nothing.

**A red integration branch stops the merges** (T21, Spec §8). Before the
first merge of a pass the integration branch takes up the protected branch
and the regression command is run on the result. Red there, the red belongs
to no ticket: nothing is pushed, no ticket is blamed, and the command
records it on the convoy — `bin/convoy-state record-integration-red`: the
control quoted on one line (« commande de régression (<command>) : code N,
sur <branch> après reprise de <protected> »), the commit it was red on, the
tips of both branches, and the end of what the command printed. The answer
is a refusal (exit 1) that carries the record under `red`.
`bin/convoy-advance` reads it, starts no ticket and publishes its one
`repair` (`docs/CONVOY_ADVANCE.md`). While a red is recorded, `merge`:

- **refuses**, exit 1, « branche d'intégration rouge (<the control>) », with
  `red` in the answer, as long as neither tip has moved and the repair is
  not ready: nothing is run and nothing is written;
- **merges the repair of that red, and nothing else**, once it is ready
  like any ticket (finished, reviewed, evaluated, the ticket-end gate
  before the merge): the protected branch is taken up in the work tree
  only, the repair is merged on it, and the tests are run on that result.
  Green: the result is pushed — the takeover with it — and the red is
  withdrawn (`clear-integration-red`); the other ready tickets are listed
  under `waiting` and merged by the next pass. Red: the repair returns to
  its author like any ticket, the red stays;
- **runs the control again** once a tip moved (the protected branch was
  mended elsewhere) or once the repair is closed without having been
  merged. Green: the takeover is pushed, the red is withdrawn and the ready
  tickets are merged by the same pass. Red: the record is rewritten under
  the new tips, with its repair while that one is open, and the command
  refuses.

A regression command that does not finish in `--timeout` is a refusal, not
a red. So is one that exits 75, its NOT RUN (the host was busy past its
wait, or its budget ran out): nothing is merged, no ticket is returned, the
next pass runs it again; the `merged_tests` piece keeps that exit 75 until
then. A takeover in conflict is a refusal too: a conflict is not a red
control.

A profile without `regression_command` is refused when a ticket is ready: no
test, no merge. A pass with no ready ticket does not read the profile,
unless a red makes it run the control again.

## `take-up`

T23, Spec §9 (« sur une seule pointe après reprise de la branche
protégée »). `take-up` merges no ticket. Under the same lock as `merge`, the
integration branch takes up the protected branch — when there is something
to take up — and the regression command of the profile is run on the
result, **whether there was anything to take up or not**.

- Green: the takeover, if any, is pushed. The answer gives `integration`
  (the tip), `protected_tip` (the tip of the protected branch it holds),
  `takeover` (`null` when there was nothing to take up) and `tests`
  (`command`, `exit_code`, `commit`).
- Red: nothing is pushed, and the red is recorded on the convoy as `merge`
  does (above). With `--end-round`, one round of the end of the Spec is
  counted in the same write (`docs/CONVOY_STATE.md`). Exit 1, with `red`.
- Refused, nothing written: a convoy whose integration branch is already
  red (before any control), no integration branch, a takeover in conflict,
  a profile without `regression_command`, a malformed `--timeout`. An
  « état sans règle » is exit 3, a convoy without the mark exit 4.

The tests of `take-up` are not filed in the evidence store: a piece belongs
to a ticket, and this tip belongs to none.

## Limits

- **A ready ticket is merged only when the ticket-end gate agrees** (T19):
  once the author, the code review and the Ticket Evaluation have answered
  at the tip, `merge` asks `bin/ticket-end check --before-merge` and merges
  the ticket only if conditions 1 to 5 and 7 to 9 are met
  (`docs/TICKET_END.md`); condition 6 is read on what `merge` writes. A
  ticket that misses one is listed under `waiting` with the text of the
  gate, and the pass still exits 0: a missing condition is not a failure of
  the command. A gate that cannot be read is one (exit 1).
- **A ticket stopped `still_refused` is merged when every Blocking Finding
  its review left unsettled carries Benjamin's recorded override**
  (`bin/correction-round override`, condition 9). Any other stopped ticket
  is not merged.
- **Starting the fresh author session of a returned ticket is not in this
  command.** The return is recorded (`merge` on the ticket, listed by the
  pass); `bin/convoy-advance` reads it and sends the ticket to a fresh
  author session on the formula `mol-ticket-resume` (T20,
  `docs/CONVOY_ADVANCE.md`).
- **The tests on a merged result are the profile's regression command**, the
  one whole-suite command a profile declares. The frozen criterion tests of
  the merged tickets are replayed only as far as that command runs them.
- **One repository per convoy.** The publication door refuses a new-flow
  graph that targets several rigs.
- A takeover of the protected branch in conflict is refused at each pass:
  it records no red and has no `repair`.
- The control of the integration branch is run by `merge` when a ticket is
  ready to merge or when a recorded red is to be checked again, and by
  `take-up` when the end-of-Spec gate runs (T23); never otherwise.
- A frozen harness file changed on the integration branch by another
  ticket's merge is still seen by `bin/tdd-step green` as modified
  (`docs/TDD_STEP.md`, Limits) when an author takes up the integration tip.
- The order that runs `bin/convoy-advance` has a 30 min timeout. A pass may
  run the regression command twice (the control after a take-up, then the
  tests of the merged result), up to `--timeout` (1260 s: the cockpit's
  regression waits at most 600 s for the host, then runs within 600 s)
  each. Unloaded both fit (about 6 min each on 22/10/2026); two long waits
  in one pass do not, and the controller then kills the pass. A run past
  `--timeout` is killed with every process it started (its own session). A
  pass killed by the controller has pushed nothing; its work tree is removed
  by the next. Deriving these numbers from measures is T3 of
  `docs/research/2026-10-22-strategie-tests-budgets.md`.

## Proof

`tests/spec-integration-test.py` drives the command lines on a fake tracker
state, against a copy of the Delivery Fixture City in a throwaway repository
with its own remote; the tests on a merged result are run and sealed by the
real `bin/evidence-capture`. One test per pass and per refusal, each refusal
re-reading the tracker, the evidence store and every branch of the remote.
`tests/ticket-graph-publish-integration-branch-test.py` covers the
publication door, `tests/convoy-advance-test.py` the pass that merges,
`tests/convoy-state-test.py` the three records. T21: the same
`tests/spec-integration-test.py` covers a red takeover recorded with its
control quoted, the refusal while the branch is red (nothing written), the
refusal on tests recorded red at the tip, the repair merged alone and the
red withdrawn, the merges that resume at the next pass, a repair that
leaves the branch red, the control run again once the protected branch is
mended, and a branch checked again and still red;
`tests/convoy-stops-fixture-city-test.py` plays it on the graph of the
Fixture City. T23: the same `tests/spec-integration-test.py` covers
`take-up`: the regression command run with nothing to take up, the takeover
pushed once green, a red takeover neither pushed nor counted without
`--end-round`, one round counted once with it, the refusal under a red, a
conflict, and the outright refusals. On the real `gc`/`bd`, in a
disposable city (local-only): `tests/spec-integration-demonstration-test.sh`
(the demonstration line), `tests/convoy-state-real-tracker-test.sh` and
`tests/ticket-graph-publish-new-flow-real-tracker-test.sh`.
