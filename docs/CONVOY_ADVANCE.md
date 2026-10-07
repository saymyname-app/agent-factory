# Convoy Advance (T04, T34, T18, T13, T14, T15, T17, Spec af-wf4w5r §0 rules 3 and 5, §4, §6, §7, §8)

## Status and purpose

`bin/convoy-advance` starts the ready tickets of a convoy that carries the
**new-flow mark** (`docs/CONVOY_STATE.md`). No agent decides which ticket
starts, in what order, or how many at once: the command reads the tracker,
and each start goes through `bin/dispatch-door`, which records it.

A convoy without the mark is not touched: the command answers « pas un
convoi du nouveau flux » (exit 4), starts nothing and writes nothing. The
Mayor advances such a convoy as before.

```bash
./bin/convoy-advance af-convoy      # one pass on that convoy
./bin/convoy-advance --all          # one pass on every open marked convoy
./bin/convoy-advance --check-only   # exit 0 if an open marked convoy exists, else 1
./bin/convoy-advance --all --stopped-ok   # what the order runs (see « État sans règle »)
```

The Factory runs it by itself: the controller evaluates
`orders/convoy-advance.toml` on each of its ticks (every 20 to 30 seconds
observed on Gas City 1.4.1: a `condition` order is paced by its check, not
by its `interval`) and runs `--all --stopped-ok` only while `--check-only`
passes. The
order costs one tracker read and runs nothing while no marked convoy is
open.

## What one pass does

For each ticket of the convoy, in the convoy's own order, the pass starts it
when all of this holds:

- the ticket is `open`, carries the mark, and has no gate record and no
  Ticket Exit yet (it was never started);
- the ticket is not parked (T11: a Ticket Exit `planning_exception` or
  `operator_request` parks its ticket and every ticket that waits for it,
  `docs/TICKET_EXIT.md`); a parked ticket is listed under `waiting`, with
  its cause and the ticket that parked it, and the tickets that wait for
  none of them keep starting;
- every bead it depends on with a `blocks` edge is closed — which is what
  makes the starts follow the dependency order;
- a place is free under the ceiling N.

A start is `bin/dispatch-door <ticket> --rig <project> --formula <formula>
[--role <role>] --convoy <convoy>`. The door asks `bin/convoy-state`, before
anything is dispatched, that the convoy is marked and tracks the ticket;
once the ticket is routed it stamps `gc.dispatched_via=dispatch-door` and
records the `dispatch` gate through `bin/convoy-state`. The project is the
single one the ticket names under « Target rigs »; a ticket that names none,
several, or one without a `config/projects/<name>.toml` is not started and
is reported under `refused`.

A pass decides from the tracker alone: a second pass on the same state
starts nothing more, because a started ticket carries its `dispatch` gate
record. Passes are serialised Factory-wide by a lock
(`CONVOY_ADVANCE_LOCK_DIR`, default `$XDG_RUNTIME_DIR` or `/tmp`), so two of
them never count the same free place.

## Finished tickets are merged by the pass (T18)

Once the starts are made and the reviews settled (below), and outside the
lock of the starts, the pass hands each convoy
that has an integration branch and a finished ticket not merged yet to
`bin/spec-integration merge <convoy> --repo <project repository> --profile
<project profile> --limit 1` (`docs/SPEC_INTEGRATION.md`): one ticket per
pass and per convoy is merged into the integration branch of the Spec, with
tests on the merged result. The repository is the one of the single project
the convoy's tickets name; the profile is the file of
`config/project-descriptors` whose `rigs` lists that project. A convoy with
no finished ticket runs no merge and asks nothing of the profile; a stopped
convoy merges nothing.

What the merge did is reported under the convoy's `integration`: `merged`,
`returned` (a conflict or red tests: the ticket is back with its author),
`refused` (a verdict outdated by a newer commit) and `waiting`. Those are
outcomes of the pass, not failures. A merge pass that could not run (no
profile for the project, a takeover of the protected branch in conflict or
red, a tracker or a repository that cannot be read) carries `error`, and the
pass exits 1.

## The ceiling N

N is `max_sessions` in `config/delivery-flow.json`: one setting for the
whole Factory, shared between the Specs. A place is taken by:

- each live session of a delivery role agent — author, reviewer, Evaluator
  (`config/delivery-roles.json`) — read from `gc session list`, whatever the
  convoy or the Spec;
- each ticket of any open marked convoy that was started through the door
  and that no session has picked yet (still `open`): its author session is
  on its way.

Between the moment an author session appears and the moment it takes its
ticket, that ticket counts twice. The count is therefore never below the
real one: the ceiling can be reached early for a moment, never exceeded.

The settings file also names what the door receives for a start:
`start.formula` and `start.role`: the author formula `mol-ticket-author`
and the role `author` (`docs/TICKET_AUTHOR.md`). With no formula the
command refuses and starts nothing.

## The code of a finished ticket is reviewed before its merge (T14)

Before the merge, the pass hands each convoy that has a finished ticket not
merged yet — or a ticket its code review stopped and that did not reach the
operator yet — to `bin/code-review settle <convoy> --repo <project
repository>` (`docs/CODE_REVIEW.md`). For each ticket finished and green at
the tip of its branch, the command opens the review at that tip and sends it
to a session of the reviewer role; it sends a review left without result
once more, stops the ticket when the relaunch gave none either and raises
the stop through `bin/escalation-door`; and it sends the answers given to
the Blocking Findings of a review to a second reviewer session. The merge
that follows in the same pass takes a ticket only when its review is
favorable at its tip, so a ticket whose verdict was already there is merged
by that pass, and the others wait.

The convoy's entry then carries `code_review` (`launched`, `relaunched`,
`pending`, `waiting`, `stopped`, `escalated`, `deferred`, `refused`). A
launch the door deferred is retried by the next pass; a settlement that
could not run, or a launch the door refused, fails the pass (exit 1). A
stopped convoy (« état sans règle ») is settled no more than it is started.

## A finished ticket is evaluated on the launched product before its merge (T15)

In the same pass as the code review — the two run in parallel, on the same
tip — the pass hands each convoy that has a finished ticket not merged yet,
a launched product left to stop, or a ticket its evaluation stopped and that
did not reach the operator yet, to `bin/ticket-evaluation settle <convoy>
--repo <project repository>` (`docs/TICKET_EVALUATION.md`). For each ticket
finished and green at the tip of its branch, the command launches the
product from a clean copy of that tip and sends the evaluation to a session
of the Evaluator role (for a `prefactoring`: checks itself that the product
starts, without a session); it sends an evaluation left without result once
more, stops the ticket when the relaunch gave none either; it parks a ticket
whose criterion cannot be observed and puts the Planning Exception on the
operator's list; and it stops the products once the states are in. The
launched products outlive the pass: a later pass stops them. The merge that
follows takes a ticket only when its evaluation is favorable at its tip.

The convoy's entry then carries `evaluation` (`launched`, `relaunched`,
`pending`, `waiting`, `started`, `refused_startup`, `planning_exception`,
`stopped`, `escalated`, `deferred`, `refused`). A launch that is deferred —
by the door, or because the Evaluator would run on the author's supplier
while another declared one is available — is retried by the next pass; a
settlement that could not run, or a launch the door refused, fails the pass
(exit 1).

## One correction round, then the ticket stops (T17)

After the code review and the evaluation, and before the merge, the pass
hands each convoy that has a finished ticket not merged yet — or a ticket
stopped still refused that did not reach the operator yet — to
`bin/correction-round settle <convoy> --repo <project repository>`
(`docs/CORRECTION_ROUND.md`). Once both controls have answered at the tip of
a ticket and at least one refused, the command opens the single correction
round of that ticket and sends everything both refused to one fresh author
session; while one of the two has not answered, it waits. After the round,
it stops the ticket that is still refused and raises it once through
`bin/escalation-door`: no second round, no merge.

The convoy's entry carries `correction` (`launched`, `pending`, `waiting`,
`stopped`, `escalated`, `deferred`, `refused`) **only when the settlement had
something to say**: a convoy whose tickets nothing refused has none, and
asks nothing of the `correction` settings. A launch the door deferred is
retried by the next pass; a settlement that could not run, or a launch the
door refused, fails the pass (exit 1).

## Test reviews left without result (T13)

Once the starts are made, and before the merge, the pass hands each convoy that has
a review of criterion tests open, or a ticket that review stopped and that
did not reach the operator yet, to `bin/test-review settle`
(`docs/TEST_REVIEW.md`): a review whose launch gave no result in
`test_review.timeout_seconds` is launched once more, the ticket is stopped
when the relaunch gave none either, and the stop is raised through
`bin/escalation-door`. No author session has to be alive for that. The
convoy's entry then carries `test_review` (`launched`, `relaunched`,
`pending`, `stopped`, `escalated`, `deferred`, `refused`); a launch the
door deferred is retried by the next pass, while a settlement that could
not run, or a launch the door refused, fails the pass (exit 1). A
convoy with nothing due is not handed over, and a stopped convoy (« état
sans règle ») is settled no more than it is started.

## Answers

Every answer is one JSON object on stdout: the ceiling, the sessions counted
per role, the tickets awaiting a session, and per convoy the tickets
`started`, `waiting` (with the reason: blocker ids, or the ceiling),
`deferred` (the door deferred: low memory, hot path held — retried on the
next pass) and `refused` (the door refused, with its reason), plus
`integration` when the pass ran a merge, `test_review` when it settled
reviews of criterion tests, `code_review` when it settled code reviews,
`evaluation` when it settled Ticket Evaluations and `correction` when a
correction round was opened, awaited or ended in a stop. A stopped convoy carries `signal`,
`unruled` (the anomalies) and `incident`.

| Exit | Meaning |
|---|---|
| 0 | the pass is done; what it started is listed, possibly nothing |
| 1 | refused or could not run (settings, tracker), the door refused a ticket, an incident could not be raised or withdrawn, or the merge pass or the settlement of the test reviews, of the code reviews, of the evaluations or of the correction rounds could not run |
| 3 | a convoy is in an « état sans règle »: none of its tickets is started, the anomalies are listed (0 with `--stopped-ok` once its incident is raised) |
| 4 | the convoy does not carry the mark: « pas un convoi du nouveau flux » |

## « État sans règle »: the convoy stops, one factory incident (T34)

Spec §0 rule 5: when the code meets a state it has no rule for, it does not
improvise. `bin/convoy-state show` names those states (exit 3): a ticket in
progress without the dispatch door's record (started outside the door), a
ticket closed without a `ticket_end` or `withdrawn` record (closed outside
its gate), evidence without a fingerprint, an incoherent counter, an unknown
mark or field. On such a convoy the pass:

1. **starts nothing** of that convoy and writes none of its tickets. The
   other marked convoys keep advancing in the same pass.
2. **raises one factory incident.** It files one bead, « Incident d'usine :
   convoi … arrêté », and sends it through `bin/escalation-door benjamin`:
   the line `Incident d'usine : <ticket> — <reason>` appears in
   `bin/escalation-door list` and the operator is mailed once. The incident
   is recorded on the convoy (`bin/convoy-state record-incident`) with a
   signature of the anomalies: the next passes on the same anomalies raise
   nothing. If the anomalies change, the same bead and the same line are
   updated. If the escalation door fails, the pass exits 1 and the next
   pass retries on the same bead.
3. **resumes by itself.** Once `bin/convoy-state show` reports a valid
   state again, the next pass withdraws the incident (`bin/escalation-door
   clear`), closes its bead, removes the record and starts the ready
   tickets. No agent advances or closes a ticket to resume the convoy.

The repair is Factory maintenance: bring the tracker back to a state the
command has a rule for (`bin/convoy-state show <convoy>` lists what is
wrong). It never consists in advancing or closing the convoy's tickets by
hand.

`--stopped-ok` makes the pass exit 0 instead of 3 for a stopped convoy whose
incident is raised. The order runs it that way: without it the order would
fail on every tick while a convoy is stopped, and `bin/on-order-failed`
would page the Mayor about a convoy it must not touch — a second incident
for the same anomaly.

## Who may start a ticket of a marked convoy (T34)

Only this command, run by its order. `bin/dispatch-door` asks
`bin/convoy-state ticket` whether the bead it is about to dispatch carries
the mark, and then refuses it (exit 2, nothing dispatched, nothing written):

- without `--convoy` — the way the Mayor dispatches, `bin/factory-work-dispatch`
  included;
- to any agent session, whatever the arguments: Gas City exports
  `GC_AGENT`, `GC_SESSION_NAME` and `GC_SESSION_ID` into every agent
  session, the Mayor's included, and into none of the controller's orders
  (observed on Gas City 1.4.1, isolated city and live supervisor,
  2026-10-06).

The refusal is a guard on the honest path, not a lock: an agent with a shell
can still call `gc sling` or `gc bd close`. That is what the stop above is
for — a ticket started or closed outside its door stops the whole convoy and
puts an incident on the operator's list. The Mayor's prompt
(`agents/mayor/prompt.template.md`, « New-flow convoys: hands off ») says
what it must not do and what it keeps doing: failing orders, stuck sessions,
quotas, guard-filed beads.

## Why not Gas City's control dispatcher

Tried on Gas City 1.4.1 in an isolated city (2026-10-06):

- `gc convoy control --serve` only processes the control beads of a formula
  workflow (`gc.kind=check|fanout|scope-check|workflow-finalize`). With a
  convoy of ready tickets and the controller running, it starts none.
- `gc convoy control <bead>` on a ticket or on a convoy answers
  `quarantined … unsupported control bead kind ""` **and closes that bead**.
  It must never be pointed at a ticket.
- `gc convoy stranded` lists ready, unassigned tickets but starts nothing.

Gas City has no component that walks a convoy's ready frontier and starts
its tickets. What it does provide, and what this command uses: orders with
an `exec` action run by the controller (the trigger), `gc sling` (the start,
behind the dispatch door), and `gc session list` (the ceiling).

## Proof

`tests/convoy-advance-test.py` drives the command line and the real
dispatch door on a fake tracker state (`tests/fixtures/convoy-state/gc`):
one test per pass and per refusal, each refusal re-reading the tracker to
prove nothing was written. `tests/convoy-advance-isolated-city-test.sh`
(local-only) is the adoption trial: in a disposable city with its own
supervisor and no Mayor, the city's own order starts a marked convoy's three
tickets in dependency order under N, the third only after the trial closed
the two others in the tracker.

T18: the same file covers the pass that merges, through the real
`bin/spec-integration` on a throwaway repository: one finished ticket merged
per pass, a ticket returned by red tests, a merge pass that cannot run, a
stopped convoy that merges nothing.

T17: the same file covers the settlement of the correction rounds through
the real `bin/correction-round`: a ticket its review refused sent to one
author session, a ticket still refused stopped and raised once, a round
that cannot be sent, a convoy nothing refused.

T34: the same `tests/convoy-advance-test.py` covers the stop (one test per
kind of anomaly), the single incident read back from the real
`bin/escalation-door list`, the resume, and each refusal and passage of the
dispatch door. `tests/convoy-stop-mayor-isolated-city-test.sh` (local-only)
is the adoption trial: a disposable city with the Factory's real Mayor on a
real provider, a ready marked convoy, a ready unmarked ticket as control and
a really failing order. The Mayor dispatches the unmarked ticket, acts on
the order failure, and leaves every ticket of the marked convoy untouched;
then a ticket closed by hand stops the convoy, one incident naming it
appears in the escalation door's list, and the city's own order resumes the
convoy once the state is valid again.
