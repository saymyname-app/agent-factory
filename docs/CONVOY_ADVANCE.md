# Convoy Advance (T04, T34, T18, T13, T14, T15, T17, T19, T20, T21, T23, T26, T45, Spec af-wf4w5r §0 rules 3 and 5, §4, §5, §6, §7, §8, §9, §11)

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
./bin/convoy-advance --all          # one pass on every open marked convoy, and on those closed outside acceptance or abandon
./bin/convoy-advance --check-only   # exit 0 if such a convoy exists, else 1
./bin/convoy-advance --all --stopped-ok   # what the order runs (see « État sans règle »)
```

The Factory runs it by itself: the controller evaluates
`orders/convoy-advance.toml` on each of its ticks (every 20 to 30 seconds
observed on Gas City 1.4.1: a `condition` order is paced by its check, not
by its `interval`) and runs `--all --stopped-ok` only while `--check-only`
passes. The
order costs one tracker read and runs nothing while no marked convoy is
open or was closed outside its commands. A convoy closed by command, on
Benjamin's words (T30), is neither walked by `--all` nor a reason for the
order to run.

A pass that exits 1 or 3 prints its answer on stdout, then one last line on
stderr: `convoy-advance: échec de la passe -- <convoy> <step>.<key>: <detail>
; …`, each step that failed it (the « état sans règle » message first). The
controller keeps only the tail of a failed order's output (af-ypj2g0), so
this line is what the `order.failed` event and its `on-order-failed` bead
show.

## What one pass does

For each ticket of the convoy, in the convoy's own order, the pass starts it
when all of this holds:

- the ticket is `open`, carries the mark, and has no gate record and no
  Ticket Exit yet (it was never started);
- the ticket is not parked (T11: a Ticket Exit `planning_exception` or
  `operator_request` parks its ticket and every ticket that waits for it,
  `docs/TICKET_EXIT.md`; T20: so does the last resume (its bound) of a same cause, below);
  a parked ticket is listed under `waiting`, with its cause and the ticket
  that parked it, and the tickets that wait for none of them keep starting;
- the convoy is not stopped (T21, « The two stops of a convoy » below): its
  integration branch is not red — or the ticket is the `repair` of that
  red — and fewer Planning Exceptions are open on its Spec than the bound;
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

Before the starts, and under the same lock, the pass reads the answers of
the operator that lift a parking and sends the tickets whose author must
take them again to a fresh session (T20, « Resumes, their bound, parking and
the grouped request » below); after the starts it raises or withdraws the
grouped request of the convoy.

Run at the end of a pass, even under a red: when the repair rounds of
the end of the Spec are stopped, the pass has the « non conforme » dossier
generated and sends the request to the operator, once per stop (T26, « The
rounds of the end are bounded » below).

The last step of each convoy's pass: on a Delivered Outcome, the pass sends
the Acceptance Request to the operator, once, and publishes the `repair` of
an Acceptance Session whose product did not start (T28, « A Delivered
Outcome waits for Benjamin » below).

Once Benjamin answered « accepté » or « abandonné », none of the above is
rendered on that convoy: after the starts, the pass follows his answer
through `bin/outcome-promote run` and does nothing else on it (T30, « After
Benjamin's answer » below).

A pass decides from the tracker alone: a second pass on the same state
starts nothing more, because a started ticket carries its `dispatch` gate
record. Whole passes, including settlement after the starts, are serialised
Factory-wide by a lock (`CONVOY_ADVANCE_LOCK_DIR`, default
`$XDG_RUNTIME_DIR` or `/tmp`), so two of them never count the same free
place or repeat the same tracker-heavy settlement. A pass that finds the
lock held does not wait for it: it answers `ok` with `skipped` (« passe déjà
en cours »), writes nothing and exits 0. The order starts a pass while the
last one still runs; on 20/10 01:32 to 01:56 Paris, under a load of 23 to 45
on 8 vCPU, each new pass waited 120 to 180 s for that lock, the 300 s of the
order ran during the wait, and five passes were killed (af-wz4dd8). On
21/10, releasing the lock before settlement let several passes repeat the
same reads and writes until they exceeded the same deadline (af-ebqm1y); the
lock now stays held through the whole pass.

## Finished tickets are merged by the pass (T18)

Once the starts are made and the reviews settled (below), under the same
whole-pass lock, the pass hands each convoy
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

N is `max_sessions` in `config/delivery-flow.json`: the ceiling of the
authors, one setting for the whole Factory, shared between the Specs. Each
delivery role has its own ceiling (af-4xxlo7): N for the authors,
`max_reviewer_sessions` for the reviewer and `max_evaluator_sessions` for the
Evaluator. Gas City applies the last two through `max_active_sessions` of
their agents (`tests/delivery-agents-test.sh` holds them equal). A review
or an evaluation never waits for N, and a reviewer or Evaluator session,
even idle until its `idle_timeout`, takes no author's place. A place under N
is taken by:

- each live session of the author agent (`config/delivery-roles.json`),
  read from `gc session list`, whatever the convoy or the Spec;
- each ticket of any open marked convoy that was started through the door
  and that no session has picked yet (still `open`): its author session is
  on its way;
- each ticket a resume was sent for (T20) and that no session has taken
  since, as long as the bead of that resume is not closed: its fresh author
  session is on its way.

Between the moment an author session appears and the moment it takes its
ticket, that ticket counts twice. The count is therefore never below the
real one: the ceiling can be reached early for a moment, never exceeded.

A resume (T20) takes a place like a start: the pass that sends it counts it
with its starts, and a ticket to resume when no place is free is listed
under `waiting` (« reprise (<cause>) : plafond N=… atteint ») and counts
nothing meanwhile. A resume that was sent keeps its place on the later
passes until its session takes the ticket (`bin/ticket-author start`); a
resume whose bead is closed without the ticket taken holds no place: it is
one more interruption, counted and sent again by that pass.

The settings file also names what the door receives for a start:
`start.formula` and `start.role`: the author formula `mol-ticket-author`
and the role `author` (`docs/TICKET_AUTHOR.md`). With no formula the
command refuses and starts nothing. `resume.formula` and `resume.role` name
what the door receives for a resume: the formula `mol-ticket-resume` and the
role `author`. Without a `resume` entry nothing is resumed: a ticket that
needs a resume is listed under `refused`, by name, and the pass exits 1.

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

The command sends no reviewer on a branch that does not contain the tip of
the integration branch (T44, Spec §6). The resumes of the pass run before
the code review and hand such a ticket back to its author (cause `behind`,
« Resumes, their bound, parking and the grouped request » below), so the
review is sent once the author finished again on a branch that holds the
tip.

The convoy's entry then carries `code_review` (`launched`, `relaunched`,
`pending`, `waiting`, `stopped`, `escalated`, `deferred`, `refused`,
`behind`). A launch the door deferred is retried by the next pass; a
settlement that could not run, or a launch the door refused, fails the pass
(exit 1). A launch `bin/code-review settle` refused for a branch behind the
integration tip is listed under `behind`, not `refused`, and does not fail
the pass: the next pass hands the ticket back. A stopped convoy (« état
sans règle ») is settled no more than it is started.

## A finished ticket is evaluated on the launched product before its merge (T15)

In the same pass as the code review — the two run in parallel, on the same
tip — the pass hands each convoy that has a finished ticket not merged yet,
a launched product left to stop, a ticket its evaluation stopped and that
did not reach the operator yet, or a finished ticket stopped `still_refused`
whose every Blocking Finding is overridden (af-ppdbza), to `bin/ticket-evaluation settle <convoy>
--repo <project repository>` (`docs/TICKET_EVALUATION.md`). For each ticket
finished and green at the tip of its branch, the command launches the
product from a clean copy of that tip and sends the evaluation to a session
of the Evaluator role when the ticket is an interface ticket (ADR-0030 L4;
for a `prefactoring` or any other ticket: checks itself that the product
starts, without a session, and records the model evaluation « not
required »); it sends an evaluation left without result once
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

## A merged ticket is closed by the ticket-end gate (T19)

A ticket of a marked convoy is closed by the pass, through `bin/ticket-end`
(`docs/TICKET_END.md`), and by nothing else:

- **Before the merge**, a convoy that has a finished interface ticket whose
  fidelity was not measured at its tip is handed to `bin/ticket-end fidelity
  <convoy> --repo <project repository> --profile <project profile> --limit
  1`, which runs the mechanical fidelity check on the commit that merges.
  Reported under `fidelity` (`checked`, `waiting`, `refused`). The check
  runs in its own session, under a lock per convoy in the directory of the
  pass's lock (af-pxijl6): the pass does not wait for it (ADR-0032,
  af-wz4dd8; `CONVOY_ADVANCE_FIDELITY_WAIT` sets a wait in seconds), it
  leaves it running, its tickets under `waiting`. The order's timeout kills the
  pass, not the check; a pass that finds it running leaves it, and the
  pass that finds it ended reports its answer. Before this, a check longer
  than what was left of the 300 s was killed with its pass and started
  again from zero by the next one: no pass ended any more. A measurement
  refusal (for example, a declared screen that does not answer) stays visible
  under `fidelity.refused`, but is informative and does not fail the pass
  (ADR-0032). A controller error or an unreadable answer still fails it.
- **After the merge**, a convoy that has a merged ticket still open, or in
  which this pass merged one, is handed to `bin/ticket-end settle <convoy>
  --repo <project repository>`. Reported under `ticket_end`: `closed` (the
  tickets closed, each with the merged commit and the version of the list)
  and `open` (the merged tickets left open, each with the numbers of the
  missing conditions and the text of the gate).

A ticket merged by a pass is closed by the same pass when its nine
conditions hold; its dependents start at the next one. A ticket left open
is an outcome of the pass, not a failure. A fidelity check or a settlement
that could not run is a failure of the pass (exit 1): this includes a pass
run from an agent session, which the gate refuses.

A ticket closed without the record of the gate, or with a record that lacks
the nine verdicts, is an « état sans règle »: the convoy stops (below).

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

## Resumes, their bound, parking and the grouped request (T20)

Spec §5 and §8, user stories 52 and 54. On each pass, for each marked convoy
that is not stopped (« état sans règle »), before the starts and under their
lock, the pass does three things from the tracker alone; a fourth follows
the starts.

**1. It lifts the parkings the operator answered** (`settle_lifts`). Read on
`bin/convoy-state show` (`park.answer`, rendered on the ticket that caused
the parking only):

| Parked for | Lifted by |
|---|---|
| `operator_request` (its own Ticket Exit) | any answer given to the request of that ticket (`bin/escalation-door repondre`) after the parking |
| `planning_exception` (its own Ticket Exit) | only the option that accepts the deviation: the last Planning Exception of the ticket is `accepted` (it was answered by its `accept_option`, `docs/CONVOY_STATE.md`; every exception raised since ADR-0030 L5 has one, with or without anchors). Any other answer leaves the ticket parked |
| `planning_exception` (its Ticket Evaluation: the ticket is `finished`, its last evaluation's outcome is `planning_exception`, no entry under `planning_exceptions`) | only option `a`, « Juger ce qui est inobservable prouvé par son test de critère vert » (`bin/ticket-evaluation`); `lift-park` records what that evaluation found unobservable by the criterion under `proven_by_test`, and the evaluation the lift sends again counts it proven (`docs/TICKET_EVALUATION.md`); or option `c`, « Réévaluer sur le produit relancé » (af-npz9v1.38): the lift records nothing proven, and the evaluation it sends again judges every item on the products launched again. Option `b` (remove the ticket from the graph) or no answer: parked |
| `resumes_exhausted` | option `a` of the convoy's grouped request (below), for the tickets that request names as lifted; or, without an answer, the ticket has resumes left under the bounds of now (`resumes_left` above 0): a parking left by a bound that no longer holds, such as the one an answered resume took before af-npz9v1.41. That lift gives no resume back |

The lift is `bin/convoy-state lift-park <convoy> <ticket> --request <bead>
--option <letter>`: the parking is removed from the ticket and from those
parked behind it — a ticket that still waits for another parked ticket is
parked behind that one instead — and kept on the ticket under `park_lifts`.
An exhausted ticket takes its resumes again, three per cause, counted from
the lift; the counter itself is never reset. No hand is put on a ticket.

**2. It parks the ticket that is out of resumes.** A ticket at work (started
through the door, not closed, neither parked nor stopped) whose
`resumes_left` is 0 is parked with every ticket that waits for it, directly
or not: `bin/convoy-state park --cause resumes_exhausted`. The bound is K
(Spec §8), `bounds.resumes` of `config/delivery-flow.json` (3), read by
`bin/convoy-state` (T21, « The bounds are set in one place » below), **per
cause** (ADR-0030 L2): each cause of a resume of this section, and a commit
added after a verdict (T18), counts against its own bound; the correction
round (T17) is not one of them, it keeps its own bound of one round. A
resume an answer of the operator opened (`answered`, `amendment_granted`)
takes no bound either: each one needs a new request and a new answer, so no
loop runs blind, and a bound on it could only ask the operator again for
what they just answered (af-npz9v1.41: R2, af-cifk1e, parked on 28/10/2026
at its third answer, the resume that answer opened counted and never sent).
Intent (Benjamin, his words, 28/10/2026, relayed by Codex): « je ne veux pas
devoir autoriser un dépassement purement technique ». A red
merge returned to its author takes nothing of the interruptions' bound, and
`resumes_left` is the fewest any one cause has left (`resumes_left_by_cause`
of `bin/convoy-state show` names each). Its value is a starting one with
no measured basis. The park detail names the cause of the last resume
recorded (`dernière reprise enregistrée : <cause>`; T17/T18 count without an
entry) and, when it is `returned` by a red merge, the merged commit and the
first three tests the piece `merged_tests` lists as `FAILED: <file>`
(`bin/ci-run-tests`'s form; another regression command gives the commit
alone) (af-w6xtw0); the grouped request (4) quotes that detail.

**3. It sends a ticket whose author must take it again to one fresh author
session** (`settle_resumes`), on the same branch. The cause is read on the
ticket:

| Cause | Read on the tracker |
|---|---|
| `interrupted` | the Ticket Exit is `interrupted`; or the ticket is `in_progress` with no Ticket Exit and its recorded session is not among the live ones (`gc session list`); or the bead of its last resume is closed and no session took the ticket since |
| `returned` | the Ticket Exit is `finished` and the merge returned the ticket (`merge.outcome` `conflict` or `red`) at the tip of its branch. Also on a ticket stopped `still_refused` whose every Blocking Finding the operator overrode, which `bin/spec-integration` merges as if at work: the resume lifts that stop, keeps it on its entry and withdraws its request; with no resume left the stop stays with the operator (af-n4bn62: F and G1 of af-strhoy, returned red on 21/10/2026, were neither merged again nor resumed) |
| `unblocked` | the Ticket Exit is `technically_blocked` and no bead it waits for with a `blocks` edge is open any more (its repair is closed) |
| `answered` | the Ticket Exit is `planning_exception` or `operator_request` and the ticket is no longer parked: its parking was lifted |
| `behind` | the Ticket Exit is `finished`, the ticket is not merged, and `bin/code-review show <convoy> <ticket> --repo` reports `behind`: its branch does not contain the tip of the integration branch, so no reviewer is sent on it (T44, `docs/CODE_REVIEW.md`). The fact is `integration:<tip>/exit:<exit time>`: once per Ticket Exit |
| `evaluation_no_result` | the ticket is stopped `evaluation_no_result` (its Ticket Evaluation gave no result, relaunch included, `docs/TICKET_EVALUATION.md`), it is neither parked nor closed, it has a resume left, the operator has not answered the request of that stop, and no resume of this cause was opened yet on the current tip of the integration branch (on `origin` when it is there, else local). The fact is `integration:<tip>/stop:<stop time>`: once per tip of the integration branch (af-xhc0sj) |
| `stage_removed` | the ticket is stopped by a stage ADR-0030 L3 removed from the flow, the test review (`test_review_refused`, `test_review_no_result`), it is neither parked nor closed, it has a resume left, and the operator has not answered the request of that stop. The fact is `stop:<reason>/<stop time>`: once per stop; the stage that wrote it no longer runs, so it cannot stop the ticket again (af-pjvsgo) |
| `code_review_no_result` | the ticket is stopped `code_review_no_result` (its code review gave no verdict, relaunch included, `docs/CODE_REVIEW.md`), it is neither parked nor closed, it has a resume left, and the operator has not answered the request of that stop. The fact is `stop:<reason>/<stop time>`: once per stop; a review stopped again writes a new stop time, resumed again within K (af-wu6xj7) |

The pass counts the resume first — `bin/convoy-state open-resume <convoy>
<ticket> --cause <cause> --ref <fact>`: one more `resumes`, the record under
`resume`, and the Ticket Exit it replaces removed, in one tracker write; the
same fact again counts nothing. If that was the third, the ticket is parked
as in 2 and **not** restarted: a ticket interrupted three times is restarted
twice. Otherwise the pass files a bead of its own, « Reprise — <ticket> »,
whose description carries `convoy:`, `ticket:` and `cause:`, routes it
through `bin/dispatch-door <bead> --rig <project> --formula
mol-ticket-resume --role author`, and records it (`bin/convoy-state
launch-resume`): one session per resume. The session takes the ticket with
`bin/ticket-author start`, does only what is missing, and leaves by a Ticket
Exit (`formulas/mol-ticket-resume.formula.toml`).

An `evaluation_no_result`, `stage_removed` or `code_review_no_result` resume lifts the stop in that same write: the stop
leaves the ticket and is kept on its resume (`resume.entries[].stop`), never
erased; the request the stop raised is withdrawn first (`bin/escalation-door
clear <ticket>`). A Ticket Evaluation without result is most often a defect
of the factory (an Evaluator role, a brief, a launch) whose repair is merged
elsewhere; the fresh author session brings the integration branch into the
ticket branch and finishes again, and the next passes withdraw the
evaluation left open on the old exit and send a new one. Stopped again on
the same integration tip, the ticket stays with the operator; once the tip
moves, it is resumed once more, always within K: the last resume (its
bound) of that cause parks it
(its stop lifted) and the grouped request follows. A `stage_removed` resume
sends the ticket back to its author past a stage that no longer exists: the
session finishes the ticket on the current flow, and the code review reads
its criterion tests (below, « No test review »). A `code_review_no_result`
resume also drops the spent round of the review in that write
(`code_review.request`, its two launches): the session finishes again and
the next pass sends a fresh reviewer on that exit, even at the same commit.
A review without result is most often a defect of the factory (T59 and T62R,
2026-10-17: the reviewer seat was held by a session that answered `no_work`,
af-epkrcv). Every other stop — `evaluation_outage`, `amendment_exhausted`, a
ticket still refused — is never resumed.

A `behind` resume is recorded like the others (an entry, one more
`resumes`, a fresh author session) but **K does not count it**: the
integration branch moved because another ticket merged, an event of the
factory, not of the ticket. Intent (Benjamin, his words, 27/10/2026 16:27
Paris): « Oui : une mise à jour behind causée par l'usine ne compte plus dans les reprises d'un ticket. » Before, 15:45 Paris: « oui les 6 », whose point 3 read « Un ticket a droit à 3 reprises
par cause […] une simple remise à jour, quand d'autres tickets ont fusionné
avant lui, compte comme une reprise […] a (recommandé) : ne plus compter ces
remises à jour. » Mechanism (agent interpretation, af-npz9v1.36): the first
`behind` resume on each tip of the integration branch (the `<tip>` of its
fact) is free; a second one on a tip already resumed for means the author
finished without taking it, and is counted against `bounds.resumes.behind`
(3): a ticket that never takes the tip is still parked, its detail saying
« behind : une même pointe d'intégration reprise sans être prise ». A tip
moves only when a ticket or a repair merges, so the free resumes are
finite. Ticket D (`af-ten1sp`) was parked on 23/10 at 17:36 Paris after 8
resumes, each merge of another ticket costing it one.

Unlike the other resumes, a `behind` one is recorded even when the ceiling N is reached
and its session has to wait for a later pass (`waiting`, « reprise (behind)
: plafond N=… atteint »): with the Ticket Exit taken back, neither the code
review nor the Ticket Evaluation is sent on the old tip meanwhile. Its
author merges the integration branch into the ticket branch, corrects,
commits and finishes again; the review then runs on the new tip.

An `unblocked` resume brings the integration branch into the ticket branch
too: the repair the ticket waited for landed there, not on the ticket's
branch, and without it the ticket meets the same defect again (af-m4np8z;
T59 met the regression its repair had fixed).

A ticket to resume that names no single known project, or when the
settings have no `resume` entry, is listed under `refused` (exit 1) before
anything is counted or written. A resume the door deferred is listed under
`deferred`, one the door refused under `refused` (exit 1): the bead that was
filed is closed, the resume stays counted once, and the next pass sends it
without counting it again. The tickets of the convoy that wait for no parked
ticket keep starting in the same pass.

**4. When nothing but parked tickets is left, it raises one request for the
convoy** (`settle_grouped_request`), after the starts. « Nothing but parked
tickets » means: every ticket of the convoy that is not closed is parked.
The pass files one bead, « Demande groupée : convoi … , il ne reste que des
tickets parqués », whose text names each parked ticket, its cause and the
tickets parked behind it, and sends it through `bin/escalation-door
benjamin`: one line on the operator's list for the convoy, never one per
ticket. It is recorded on the convoy (`bin/convoy-state
record-grouped-request`, `convoy.grouped_request`) with a signature of the
parkings: the next passes on the same parkings raise nothing, an answer
included. If the parkings change, the same bead is completed and raised
again. Once a ticket of the convoy may advance again, the pass withdraws the
request (`bin/escalation-door clear`), closes its bead and removes the
record (`clear-grouped-request`).

The request has two options. Option `a`, when at least one ticket is parked
for exhausted resumes: « Relancer les tickets aux reprises épuisées » — the
next pass lifts those tickets, sends the resume that was counted and not
sent when there is one, and the tickets behind them are startable again. When no ticket is
exhausted, option `a` only sends the operator to the request of each ticket,
and lifts nothing. Option `b`, « Laisser ces tickets parqués »: nothing
starts, the convoy stays open, the request does not come back.

If option `a` is recorded while the same pass is resuming another ticket,
the pass applies it before withdrawing the grouped request: the request-door
lock orders the answer and the withdrawal, so the named exhausted tickets
are lifted and their counted resumes are launched exactly once (af-g2ukoq).

Two decisions taken here:

- **A ticket parked for exhausted resumes raises no request of its own.**
  The operator hears of it through the grouped request only, that is once
  nothing else can advance in the convoy; until then it is visible under
  `parked` in the answer of the pass and under `waiting` afterwards.
- **A ticket parked by its own Ticket Exit keeps the request that exit
  raised**, and the grouped request names it too: the operator may see the
  ticket's line and the convoy's line together. The grouped request never
  lifts such a ticket; the answer to its own request does.

### What is not resumed

- **A stopped ticket**, but for its stop `evaluation_no_result`, its stop
  `code_review_no_result` and the stops of the removed test review
  (`stage_removed`, above). Nor is a ticket stopped by the removed test
  review or by a code review without result whose request the operator
  answered or that is out of resumes.
  Its sequence failed and it is with the operator; it is never read as
  interrupted, and nothing else lifts a stop. Nor is a ticket stopped
  `evaluation_no_result` whose request the operator answered, that is out
  of resumes, or that was already resumed for it on the same tip of the
  integration branch: it stays stopped, with the operator.
- **A correction session that dies without closing its bead**
  (`docs/CORRECTION_ROUND.md`): the ticket still carries its Ticket Exit
  `finished` and was not returned by the merge, so nothing here reads it as
  interrupted. It waits.
- **A ticket the ticket-end gate leaves waiting** — a red fidelity, a
  missing condition (`docs/TICKET_END.md`).
- **A Planning Exception that names no anchor**, or that was answered by
  another option than the one that accepts the deviation: the pass does not
  lift its parking.
- **A stopped convoy** (« état sans règle »): nothing is lifted, resumed,
  parked or grouped until its state is valid again.
- **A ticket behind the integration tip while the integration branch is
  red** (T21, below): only the repair is resumed then, so the ticket is not
  handed back until the branch is green again; its review stays refused
  meanwhile (`code_review.behind`). The Ticket Evaluation has no check of
  the integration tip of its own: it is kept off the old tip only by the
  Ticket Exit the `behind` resume takes back.
- A session is read as ended from `gc session list` alone, by the names a
  live session answers to (`id`, `name`, `session_name`, `alias`). There is
  no timeout on a resume session that stays alive without working.

## The two stops of a convoy: red integration branch, open Planning Exceptions (T21)

Spec §8, user story 53: « le convoi s'arrête entièrement si la branche
d'intégration est rouge ou si 2 Planning Exceptions sont ouvertes ». Both
stops are read on the tracker at each pass, and both end by code: no hand is
put on the convoy.

**Red integration branch.** `bin/spec-integration merge` writes the red on
the convoy when the regression command of the profile is red on the
integration branch once it has taken up the protected branch — a red that
belongs to no ticket (`bin/convoy-state record-integration-red`: the control,
quoted, the commit it was red on and the tips of both branches;
`docs/SPEC_INTEGRATION.md`). While `integration_red` is recorded:

- **no ticket starts and no resume is sent**, places free or not; each
  ready ticket is listed under `waiting` with « branche d'intégration rouge
  (<the control>) »;
- **the pass publishes one `repair`** for that red (`settle_red`), created
  by code: a revision that adds one ticket of kind `repair` to the graph as
  it is published, sent through the patch door (`bin/ticket-graph-publish
  bd-patch`, with no approval: Spec §2, a repair inside the approved intent
  needs none). Its `restores` is `{kind: red_check, ref: <the control>}` —
  the name the convoy records that red under (`convoy.red_checks` in
  `bin/convoy-state show`), which is what the patch door reads it against
  (T40); the repair of a red of the mechanical fidelity cites it the same
  way and is published as an interface ticket —,
  its demonstration line and its one criterion are that control green
  again, and what the control printed is quoted in what it delivers. The
  entry contract applies to it as to any added ticket; a refusal of the
  door fails the pass (`repair.error`) and nothing starts. The repair is
  then named on the red (`bin/convoy-state set-integration-repair`): **one
  repair per red**, whatever the number of passes — a red that has its
  repair publishes nothing more, and a repair of that red already tracked
  by the convoy (a pass that failed between the door and the record) is
  taken as it is;
- **that repair is the one ticket the pass starts**, resumes, has reviewed
  and evaluated like any ticket, and the one ticket `bin/spec-integration`
  merges (on the protected branch taken up, the tests on that result);
- **the merge command is handed the convoy at every pass**, finished
  ticket or not: it alone merges the repair or sees that the control is
  green again. While it refuses on the red, the pass reports
  `integration.stopped` and `integration.red` and is not a failure.

The reviews, the evaluations and the correction rounds of tickets already
finished are still settled: they judge the branch of a ticket, not the
integration branch, and nothing of them is merged meanwhile.

**The red ends by code.** `bin/spec-integration` withdraws it
(`clear-integration-red`) when the merged result of the repair is green, or
when the control it runs again — once a tip moved, or once the repair is
closed without having been merged — is green. From the next pass on the
ready tickets start and the finished ones are merged. A control found red
again keeps the red, and its repair while that one is open; found red once
its repair is closed, the red has no repair any more and the next pass
publishes a new one.

**Open Planning Exceptions.** A Planning Exception is open on a ticket
while the last one its author raised (`planning_exceptions`, state `open`)
has no answer of the operator, or while the ticket is parked by one an
evaluation raised (a criterion the Evaluator could not observe), not
answered either. When as many are open on the tickets of the convoy — the
convoy delivers one Spec — as `bounds.open_planning_exceptions` (2), **no
new ticket starts**: each ready one is listed under `waiting` with « 2
Planning Exceptions ouvertes sur la Spec ». The tickets at work go on: their
resumes are sent, they are reviewed, evaluated, merged and closed. With
fewer open, the starts continue outside the parked tickets, as before. An
exception the operator answered through `bin/escalation-door repondre` is no
longer open: the next pass starts again.

A red integration branch is read first: under it the open Planning
Exceptions change nothing more.

### The bounds are set in one place

`bounds` of `config/delivery-flow.json` holds the bounds of the flow
delivered so far (Spec §8), and no command holds one in its code:

| Bound | Setting | Value | Read by | Effect |
|---|---|---|---|---|
| K, resumes of a ticket, per cause (ADR-0030 L2) | `bounds.resumes` | 3 per cause | `bin/convoy-state` | at the last one of a same cause the ticket is parked with its descendants |
| Planning Exceptions open on a Spec | `bounds.open_planning_exceptions` | 2 | `bin/convoy-advance` | no new ticket of its convoy starts |
| Repair rounds at the end of a Spec, every source of findings together | `bounds.end_rounds` | 2 | `bin/convoy-state`, in the write that would count one more round | a refusal more counts no round and publishes no repair: the rounds are stopped and a « non conforme » request goes to the operator (T26) |

Each is an integer of at least 1; a missing or malformed one is a refusal
of the command that reads it (`bounds.<name>` named), never a default. The
file is the one under `FACTORY_ROOT`; a root that sets no `bounds` at all (a
synthetic city of the suites) runs under those of the Factory's own file.
The values are starting ones with no measured basis (Spec, Further Notes 2).

k, the runs in a row of the green step, is not one of them: it is a
declaration of each project's profile (`launch.k`, Spec §12,
`docs/PROJECT_PLANNING_PROFILE.md`), read there and nowhere else by
`bin/tdd-step`; a missing or malformed one refuses the profile.

### What these stops leave open

- A takeover of the protected branch **in conflict** is still a refusal of
  the merge command at each pass, with no red recorded and no repair: a
  conflict is not a red control.
- The repair of a red is written by code from the control alone: its one
  criterion is the regression command green again. When the author needs a
  criterion on the product, the amendment of a criterion is a Planning
  Exception, as for any ticket.
- The red is found by the merge command, so only once a ticket is ready to
  merge or the convoy is already red, and by the end-of-Spec gate once every
  ticket is closed (T23, below): nothing else runs the regression command
  on an integration branch no ticket is being merged into.

## The end of the Spec: three mechanical verdicts on one tip (T23)

Spec §9, points 1 to 3: once every ticket of the convoy is closed, the end
of the Spec is verified by code. At the end of each pass, after the
ticket-end gate, the pass hands a convoy **whose every ticket is closed and
whose integration branch is not red** to `bin/spec-end run`
(`docs/SPEC_END.md`), with the repository and the profile of its project.
While a ticket is open, or on a convoy without an integration branch,
nothing is run.

The gate renders its three verdicts — `registry`, `tests`, `fidelity` — on
one tip of the integration branch, the protected branch taken up. The entry
of the convoy carries `spec_end`:

- every condition met: `verdicts`, the `commit` they are tied to, and
  `replayed` (`false` when the mechanical verdicts were already recorded on
  that tip: the pass then wrote nothing);
- a condition that is not met: `verdicts`, `missing`, and `reason`, the text
  of the gate. It is **an outcome of the pass, not a failure**: the pass
  exits 0. With it, `refused` and `requests` when the registry refused
  (each element named, and the requests raised to the operator), or `red`
  and `end_rounds` when the tests or the fidelity are red;
- a gate that could not run (no profile, a takeover in conflict, a fidelity
  check that cannot run, a pass run from an agent session): `error`, and the
  pass exits 1.

**Red tests or a red fidelity** are recorded by the gate as the red of the
integration branch, with one round of the end counted — or, the rounds
consumed, with the stop of the rounds and no repair (T26, below). The next
pass treats it as any red (above): it publishes the one `repair` and starts
it. For a
red fidelity (`integration_red.check` is `fidelity`) the `repair` restores
an `anchor` and its criterion is the screens of the profile serving every
prototyped state as the Validated Prototype does.

**Tracked elements to repair.** At its start, each pass looks for tickets
whose deviations or « non faits » the operator asked to have repaired
(their Planning Exception answered by another option than the one that
accepts) and that have no `repair` yet. It publishes one `repair` per such
ticket through the patch door, as for a red — `restores: {kind: red_check,
ref: registre de la porte de fin de Spec : …}`, the name `convoy.red_checks`
gives that red, the elements quoted in what it delivers —, names
it on the elements (`bin/convoy-state set-item-repair`) and starts it. The
entry carries `item_repairs` (`{id, key, draft, published, ticket, items}`,
or `error`). One repair per request, whatever the number of passes. A
repair that could not be published fails the pass and is tried again by the
next.

## The assembled product is evaluated once the mechanical verdicts are green (T24)

Spec §7 and §9, points 4 and 5 (`docs/OUTCOME_EVALUATION.md`). The gate now
holds seven conditions (`spec-end/v4`; the sixth is the end code review,
below, the seventh the Evidence Pack, last section): with three green mechanical verdicts and no favorable Outcome
Evaluation at their commit, `spec_end` names condition 4 in `missing` and in
its `reason` — an outcome of the pass, which exits 0.

The product is launched from a clean copy of that commit and evaluated
story by story by one Evaluator session. An evaluation left without result
is launched once more, then stopped and raised once. An unfavorable
evaluation is an outcome of the pass, not a failure.

- **After the gate**, the pass hands the convoy to `bin/outcome-evaluation
  settle` with the repository and the profile of its project, when the gate
  was due or when an evaluation has something left to settle (an open
  request, a launched product to stop, a stop that did not reach the
  operator). The entry carries `outcome_evaluation` (`action`: `launched`,
  `relaunched`, `pending`, `waiting`, `stopped`, `escalated`; with `commit`,
  `bead`, `launches`, `deadline`, `reason`, `stop` as they apply); nothing
  when there was nothing to do. A settlement that could not run (no
  `outcome_evaluation` block in the settings, no project) is `error`, and
  the pass exits 1; the mechanical verdicts are recorded all the same.
- **At its start**, each pass publishes what the Evaluator of the end
  drafted and code has not published yet: one `repair` per user story the
  last Outcome Evaluation did not observe, and one per finding « hors
  ticket » classified « repaired ». Each goes through the patch door as the
  Evaluator wrote it, is named where it was drafted (`bin/convoy-state
  set-outcome-repair`) and starts like any ticket. The entry carries
  `outcome_repairs` (`{id, key, draft, published, story}` or `{…, finding}`,
  or `error`). Nothing is published while an evaluation is open, nor once
  the rounds of the end are stopped (T26). One repair
  per draft, whatever the number of passes; one that could not be published
  fails the pass and is tried again by the next.

Once such a repair is merged and closed, the tip moved: the gate renders its
mechanical verdicts again and the product is evaluated again. The round is
counted when the evaluation that refuses the tip is recorded, not when its
repair is published (T26, below).

## No test review (ADR-0030 L3)

A pass starts no review of criterion tests and settles none: no test review
precedes the freeze, and the code review reads the criterion tests after
the green (`docs/CODE_REVIEW.md`). A `gc.flow.test_review` left on a ticket
in flight by the flow before L3, open or not, is ignored (`bin/test-review` was removed in L7). A ticket a test
review stopped before L3 (`test_review_refused`, `test_review_no_result`) is
resumed on itself (`stage_removed`, above, af-pjvsgo): its request is
withdrawn through `bin/escalation-door clear` and a fresh author session
finishes it on the current flow. Only when it has no resume left does its
stop stay, raised once with the TDD stops (`tdd_stops`) if it was not yet.

A ticket whose criteria are all already green at the red
(`criterion_already_green`, ADR-0030 L5) is raised with the TDD stops too,
« Ticket <id> arrêté : critères tous déjà verts — … », once its author
settled it: the Planning Exception raised since the stop (its `at` not
before the stop's) is answered and no longer parks the ticket — the
« accept » answer lifts the parking, not the stop — or the author's session
is over without raising one (af-npz9v1.9), so the convoy never stalls
silently. While a parking holds its own request, while that exception is
unanswered, or while the author's session is alive without one, nothing is
posted; an exception raised before the stop does not count. This request
offers « Clore ce ticket comme satisfait par le code existant » and
« Laisser le ticket arrêté », not a second Planning Exception: one decision,
one request. No door closes an unmerged ticket (`bin/ticket-end` closes on
its nine conditions), so the close is done in the Planning Run, and the
consequence says that this answer alone closes nothing.

## A ticket stopped at its second amendment reaches the operator (T45)

`bin/tdd-step amend` stops a ticket at its second amendment
(`amendment_exhausted`, `docs/TDD_STEP.md`; Spec §8: one amendment per
ticket, then « ticket bloqué, remonte »). It runs in the author's session
and writes the stop only; no review or evaluation settles that stop. The
pass raises it itself, before the reviews: for each ticket whose stop is
`amendment_exhausted` and has not reached the operator, it posts one request
through `bin/escalation-door benjamin` on the ticket — « Ticket <id> arrêté
: amendement épuisé — <the refusal `bin/tdd-step` recorded> », in the
Operator Language — then records it with `bin/convoy-state stop-raised`.
The convoy's entry carries `tdd_stops` (`escalated`: `[{ticket, reason}]`).
A later pass on the same state sees `raised` on the stop (`bin/convoy-state
show`) and posts nothing more. A request the door could not post is an
`error` in `tdd_stops` and fails the pass (exit 1); nothing is recorded, so
the next pass posts it.

While it is stopped, the ticket is never resumed and never merged (a
stopped ticket is not at work, and it has no Ticket Exit « terminé »); the
tickets it blocks do not start; the others keep starting and merging. The
request offers two options: « Accepter un amendement de plus de ses tests et
faire reprendre le ticket » (a) or « Laisser le ticket arrêté » (b). Once the
operator answered **a** through `bin/escalation-door repondre`, after the
stop, the pass lifts it by a resume of cause `amendment_granted`
(`bin/convoy-state open-resume`, counted under `bounds.resumes` like the
other causes; the resume keeps the stop it lifted) and sends a fresh author
session on the same branch. That resume allows the author one amendment more
(`docs/TDD_STEP.md`); a further amendment stops the ticket again, and the
next pass raises that new stop. Answered **b**, or not answered, the ticket
stays stopped, unless every change at its tip since the freeze is the
base's it merged (`bin/tdd-step changes`: `own` empty, `inherited` not):
then no amendment was the ticket's to take, and the pass lifts the stop by
a resume of cause `inherited_change` (af-npz9v1.39), its request withdrawn,
once per stop. Before af-25o7vr (2026-10-21) no code carried out answer a.

## The end code review of the assembled diff (T25)

Spec §6 « Fin de Spec », §9 point 4: right after the gate, in the same pass,
a convoy whose every ticket is closed and whose integration branch is not
red is handed to `bin/spec-end-review settle` (`docs/SPEC_END_REVIEW.md`).
The review is so launched by the pass that recorded the three mechanical
verdicts, on their commit — the pass, and the commit, the Outcome Evaluation
is launched in and on (T24): the two are made in parallel. Until the review
is favorable there, `spec_end` carries the refusal of condition 6 in its
`reason`.

One reviewer session reviews the whole assembled diff of the Spec. A review
left without result is launched once more, then stopped and raised. A
review that is unfavorable or without result is an outcome of the pass, not
a failure.

The entry of the convoy carries `end_review` whenever something is due or
done: `action` (`launched`, `relaunched`, `pending`, `deferred`, `reviewed`,
`stopped`, `escalated`), the `commit`, and with it `bead`, `launches`,
`deadline`, `extent`, `outcome`, `blocking`, `stop`, `raised`. A review that
is not due yet is not listed.

**Drafted repairs.** On a review with Blocking Findings whose repair is not
published yet, the pass publishes each draft of the reviewer through the
patch door, as any added ticket, and names the ticket on its finding
(`bin/convoy-state set-end-review-repair --ticket`): `end_review.repairs`
lists `{id, key, draft, published, finding}`. The repair then follows the
flow of any ticket, started by the next pass. A draft the door refuses is
written on the finding (`--refused`) and listed with `refused`: it is an
outcome of the pass, and the next pass stops the review and raises it to the
operator. A settlement that could not run, or a repair that was published
but could not be named on its finding, is an `error`: the pass exits 1.

No draft of the review is published once the rounds of the end are stopped,
nor while the Outcome Evaluation of the same tip is still open: what it
hands in may stop the rounds (T26, below).

## Answers

Every answer is one JSON object on stdout: the ceiling, the sessions counted
per role, the tickets awaiting a session, and per convoy the tickets
`started`, `waiting` (with the reason: blocker ids, or the ceiling),
`deferred` (the door deferred: low memory, hot path held — retried on the
next pass) and `refused` (the door refused, with its reason), `resumed`
(T20: each ticket sent to a fresh author session, `{id, cause, bead}`),
`parked` (each ticket parked for exhausted resumes by this pass, `{id,
cause, parked}`: itself and those behind it) and `lifted` (each parking
lifted on an answer, `{id, option, request, lifted}`), plus
`grouped_request` when the convoy has or had one (`{bead, raised}`, `{bead,
withdrawn}`, or `error`), `stop` when the convoy is stopped by one of its
two stops (T21: `{reason: integration_red, control, repair}` or `{reason:
planning_exceptions, open, bound}`), `repair` when the pass published the
repair of a red (`{id, key, draft, published}`, or `error`),
`integration` when the pass ran a merge, `tdd_stops` when it raised a ticket
stopped at its second amendment (T45), `code_review` when it settled code reviews,
`evaluation` when it settled Ticket Evaluations, `correction` when a
correction round was opened, awaited or ended in a stop, `fidelity` when it
measured an interface ticket, `ticket_end` when the gate settled merged
tickets, `item_repairs` when the pass published the repair of tracked
elements, `spec_end` when it ran the end-of-Spec gate (T23),
`outcome_repairs` when it published what the Evaluator of the end drafted,
`outcome_evaluation` when it settled the Outcome Evaluation (T24),
`end_review` when it settled the end code review (T25), `evidence_pack`
when it had the pack generated (T27) and `non_conforme` while the rounds of
the end are stopped and their request has not reached the operator (T26:
`{action: raised, reason, commit, page, digest, bead}`, `{action: pending,
reason}`, or `error`), and `acceptance` when it sent the Acceptance Request
of a Delivered Outcome or published the repair of an Acceptance Session's
outage (T28: `{action: requested, commit, page, bead}`, `repair`, or
`error`), and `promotion` once « accepté » or « abandonné » stands (T30,
« After Benjamin's answer »). `spec_end` passes `delivered` and `end_stop`
through as the gate answered them. A stopped convoy carries `signal`,
`unruled` (the anomalies) and `incident`. A convoy closed by command, when
it is named as CONVOY, carries `closed`, the record of its closing.

| Exit | Meaning |
|---|---|
| 0 | the pass is done; what it started is listed, possibly nothing |
| 1 | refused or could not run (settings, a bound, tracker), the door refused a ticket or a resume (named under `refused`), a ticket to resume has no `resume` setting or no project, a parking could not be lifted, an incident or a grouped request could not be raised or withdrawn, the repair of a red integration branch or of tracked elements could not be published, or the merge pass, the settlement of the code reviews, of the evaluations or of the correction rounds, the fidelity controller (not an informative measurement refusal), the ticket-end gate, the end-of-Spec gate, the Outcome Evaluation or the settlement of the end code review could not run, a repair the Evaluator of the end drafted could not be published, the Evidence Pack could not be generated, the « non conforme » request of stopped rounds could not be raised or recorded, the Acceptance Request of a Delivered Outcome or the repair of an Acceptance Session's outage could not be sent, published or recorded, or the merge or the closing that follows the operator's answer could not be made (`promotion.error`, `promotion.message`, `promotion.pending`, or the `repair` of a voided acceptance that could not be published) |
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

A state the command has a rule for can still leave a ticket that no pass
moves on: T02R (#673) and T02R2 (#687) each sat so for hours. That one is
caught outside the pass, by `bin/factory-watchdog` (`tickets`,
`docs/FACTORY_TOOLS.md`): a started ticket with no live session, no open
launch, no request on the operator's list and nothing recorded for 30 min
raises the same kind of « Incident d'usine », withdrawn once the ticket
moves again (af-1fvzns).

The repair is Factory maintenance: bring the tracker back to a state the
command has a rule for (`bin/convoy-state show <convoy>` lists what is
wrong). It never consists in advancing or closing the convoy's tickets by
hand.

### A marked convoy does not close by itself (T22)

Spec §9, user story 55: a marked convoy stays open when all its tickets are
closed; it closes only by code, on the operator's words (accepted or
abandoned: recorded by `bin/owner-answer`, T29, `docs/OWNER_ANSWER.md`;
closed by `bin/outcome-promote`, T30, « After Benjamin's answer » below).
Three things hold that:

- `bin/convoy-state mark` puts the convoy under Gas City's manual lifecycle
  (the label `owned`): `gc convoy check`, which
  `orders/convoy-parent-sweep.toml` runs on every closing, leaves it open.
  A convoy without the mark is closed by that sweep as before.
- `bin/planning-artifacts-close` closes the Spec and the Ticket Graph Draft
  of a closed convoy; it leaves alone those of a marked convoy that
  `bin/convoy-state list` names under `closed_outside`, and closes those of
  a marked convoy closed by command (`closed`).
- a marked convoy found closed any other way (by hand, or by a sweep after
  the label was removed), whatever answer it carries, is an « état sans
  règle » of the convoy. `--all` walks
  it with the open ones and `--check-only` passes on it, so the order runs:
  the pass starts nothing in it and raises the factory incident above,
  `Incident d'usine : convoi <id> — convoi fermé hors commande …`, in
  `bin/escalation-door list`. Reopening the convoy is the repair: the next
  pass withdraws the incident.

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

T22: the same file covers a marked convoy closed outside its commands
(raised once on the escalation door's list, withdrawn once reopened, the
order's check passing on it, an unmarked closed convoy left alone);
`tests/planning-artifacts-close-test.sh` covers its Spec and Draft left
open. `tests/convoy-manual-lifecycle-isolated-city-test.sh` (local-only) is
the adoption trial: in a disposable city with its own supervisor, no Mayor
and no agent, the city's own `convoy-parent-sweep` order closes an unmarked
convoy whose tickets are closed and leaves the marked one open with its
Spec and Draft; closed by hand, the marked convoy is raised by the city's
own `convoy-advance` order.

T18: the same file covers the pass that merges, through the real
`bin/spec-integration` on a throwaway repository: one finished ticket merged
per pass, a ticket returned by red tests, a merge pass that cannot run, a
stopped convoy that merges nothing.

T17: the same file covers the settlement of the correction rounds through
the real `bin/correction-round`: a ticket its review refused sent to one
author session, a ticket still refused stopped and raised once, a round
that cannot be sent, a convoy nothing refused.

T20: the same file covers the resumes in the pass, through the real
`bin/convoy-state`, `bin/dispatch-door` and `bin/escalation-door`: one test
per cause of resume, a session ended without an exit, a resume bead closed
without the ticket being taken, a resume that cannot be sent (counted once,
sent by the next pass), no `resume` setting, the ceiling, a stopped ticket
never resumed, a ticket stopped without evaluation result resumed on
itself once per integration tip, its stop kept, its request and its open
evaluation withdrawn, and left stopped once its request is answered, the
the last resume (its bound) of a same cause parking the ticket and its descendants,
three different causes leaving it at work (ADR-0030 L2), the unrelated tickets still starting, exactly one
grouped request naming each parked ticket and its cause, none while a
ticket that is not parked is left, one for several passes, the answer that
lifts (including one recorded while another ticket is resumed) and the one
that leaves the tickets parked, and the answer to the request of a ticket
its own exit parked. `tests/convoy-state-test.py`
covers the state commands (`docs/CONVOY_STATE.md`). The cause `behind`
(T44), through the real `bin/code-review`:
`test_a_finished_ticket_behind_the_integration_tip_goes_back_to_its_author_once_and_is_counted`
and
`test_a_finished_ticket_that_holds_the_integration_tip_is_reviewed_and_not_resumed`.
`tests/convoy-advance-isolated-city-test.sh` (local-only) ends on a resume:
once the third ticket's author session has left by the exit « interrompu »,
the city's own order counts one resume, routes one bead « Reprise — »
through the real dispatch door on the real `mol-ticket-resume`, sends no
second one at the next passes and counts its place under N. The agent of
that trial is a stub: no session runs the step of the formula, and the
last resume (its bound) of a same cause, the lift of a parking and the grouped request are not part
of it.

T21: the same file covers the two stops on a fake tracker state: tests
recorded red at the tip of the integration branch that start no ready
ticket but the repair and merge no finished one, several passes on the same
red, the starts and the merges that resume once the red is withdrawn, a red
whose repair the patch door cannot publish, two open Planning Exceptions
that start no new ticket while a ticket at work is resumed, one that lets
the others start, an exception raised by an evaluation, an answered one,
and the bound read in the settings or refused when malformed.
`tests/convoy-stops-fixture-city-test.py` is the demonstration line of T21:
on the graph of the Fixture City published by the real publication door, a
red integration branch stops the starts and the merges and one `repair`
naming the control appears in the convoy through the real patch door, one
for several passes; the repair closed and the control green again — the
real regression command, run again by the real `bin/spec-integration` —
the convoy goes on by itself; with two Planning Exceptions open no ready
ticket starts. `tests/spec-integration-test.py` covers the merge command
under a red (`docs/SPEC_INTEGRATION.md`).

T23: the same file covers the end-of-Spec gate in the pass, through the
real `bin/spec-end`: three green verdicts once every ticket is closed, on
the tip of the integration branch, and nothing replayed by the next pass;
no gate while a ticket is open, on a convoy without an integration branch
or under a red; a registry that refuses and red tests as outcomes of the
pass, one round counted; a gate that cannot run, or a pass run from an
agent session, as failures. `tests/convoy-stops-fixture-city-test.py` plays
the rest on the graph of the Fixture City, with the real patch door: the
`repair` of red tests and of a red fidelity, the request raised once for a
« non fait », the `repair` published on the operator's answer and the
element read « réparé » once it is closed, an accepted « non fait ». No
isolated-city trial runs the gate under the real order.

T19: the same file covers the gate in the pass, through the real
`bin/ticket-end`: a ticket merged and closed by one pass with its nine
verdicts, an interface ticket measured against its Validated Prototype
before its merge, a merged ticket that misses a condition left open and
named, a closure whose record lacks the nine verdicts stopping the convoy,
a pass run from an agent session refused. `tests/ticket-end-isolated-city-test.sh`
(local-only) is the adoption trial: the city's own order merges and closes
a ticket on the real tracker.

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

## The Evidence Pack is generated once the six conditions before it are met (T27)

Spec §10 and §9, point 6 (`docs/EVIDENCE_PACK.md`). The gate reads the
pack as its seventh condition and generates nothing. When its answer names
that condition alone — every condition before it `pass`, `evidence_pack`
`fail`: no pack, or one that no longer holds — the pass runs
`bin/evidence-pack generate` with the repository of the project, then runs
the gate again. The convoy entry of the answer carries `evidence_pack`
(`action: generated`, `commit`, `digest`, `page`, `conforming`,
`inadmissible`, or `error`), and `spec_end` is the answer of that second
run. A pack that could not be generated — the rubric « Ce qui n'a PAS été
vérifié » cannot be filled, the Spec cannot be read — fails the pass, named,
and is tried again by the next. On a state whose pack holds, nothing is
generated and the entry has no `evidence_pack`.

The pass generates no conforming pack while a condition before it is red.
The one pack it generates then is the « non conforme » dossier of a convoy
whose rounds of the end are stopped (T26, below).

`tests/convoy-advance-test.py` covers it: the pass that finds the six
conditions met has the pack generated on their commit, the gate then passes
its seven conditions in that same pass, and the next pass generates nothing.

## The rounds of the end are bounded, then a « non conforme » request (T26)

Spec §8 (« Tours de réparation en fin de Spec, toutes sources : 2, puis
demande « non conforme » à Benjamin »), §9, §11, user story 61. The rounds
are counted and stopped by `bin/convoy-state`, in the write that records
each refusal of a tip (`docs/CONVOY_STATE.md`, « The rounds of the end »):
one counter for the mechanical reds, the end review and the Outcome
Evaluation, the bound `bounds.end_rounds` (2), and two early stops on the
user stories an Outcome Evaluation did not observe (a round that did not
reduce their number, a story refused twice). The pass only reads the result,
`convoy.end_stop`.

**While `end_stop` is set, no repair of the end is published**, whatever
the number of passes:

- the red of the integration branch gets no `repair`: the red stays
  recorded, the convoy stays stopped by it (`stop.reason: integration_red`,
  `repair: null`) and nothing starts;
- the repairs the Evaluator of the end drafted stay drafts
  (`outcome_repairs` absent);
- so do those of the end review (`end_review.repairs` absent). They are
  also held while the Outcome Evaluation of the same tip is open, so that a
  repair is never published by the pass just before the evaluation stops
  the rounds.

**The request, once per stop.** As its last step, under a red too, the pass
settles the stop:

1. while an Outcome Evaluation or an end review is still open on the tip,
   it waits — `non_conforme: {action: pending, reason}` — so that the
   dossier holds what they hand in;
2. it runs `bin/evidence-pack generate` on the refused tip: the page says
   « Dossier non conforme » in its header and the stop in its rubric 8
   (`docs/EVIDENCE_PACK.md`). A pack that comes out conforming is refused:
   no request is sent;
3. it sends the request through `bin/escalation-door benjamin <convoy
   bead>`, blocking: `quoi` is « Demande « non conforme » — convoi X :
   <cause> » (tours de réparation de fin de Spec épuisés / un tour de
   réparation n'a pas réduit les user stories non observées / la même user
   story est refusée deux fois), `pourquoi` the `detail` of the stop, `lien`
   the page of the pack, and three options — « Relancer un tour de
   réparation », « Retourner à la planification », « Abandonner ».
   « Accepté » is never one of them (Spec §11): a non-conforming Outcome is
   not accepted through this request;
4. it records the request on the stop (`bin/convoy-state end-stop-raised`),
   and answers `non_conforme: {action: raised, reason, commit, page, digest,
   bead}`.

**The link of the dossier: `lien`, a field of the escalation door.**
`bin/escalation-door benjamin <bead> '<json>'` takes, beside `quoi`,
`pourquoi`, `que_faire`, `langue` and `bloquant`, an optional `lien`: the
dossier the operator reads to decide. It is one non-empty line of any
length — not held to the 140 characters of the other fields, a path is
longer — and a value on several lines or empty refuses the request
(« champ « lien » doit être une ligne de texte non vide »). The door stores
it as `gc.escalation_lien`, mails it as a `DOSSIER:` line above `EVIDENCE:`,
and `bin/escalation-door list` prints it on the request's own line:
`<bead> — <quoi> — dossier : <lien>`. The link belongs to one request: a
later request without `lien` on the same bead resets it (`none`, printed by
nothing), and a bead that never carried one gets no such field. The
« non conforme » request is its one caller so far
(`tests/escalation-door-test.sh`).

Once `end_stop.request` is written the pass does nothing more about the
stop and the entry has no `non_conforme`. An error at any of these steps is
`non_conforme.error`: the pass exits 1 and the next one tries again. No
agent writes the dossier, the request or its wording.

**What it leaves open.**

- Nothing reads the operator's answer yet: no command withdraws `end_stop`,
  so a stopped convoy stays stopped whatever option is taken.
  `bin/acceptance-session record` hands the chosen issue to the door (T28,
  `docs/ACCEPTANCE_SESSION.md`) and nothing reads it: T29 covers the answer
  to a Delivered Outcome only (`docs/OWNER_ANSWER.md`, Limits).
- A pass that fails between the door and `end-stop-raised` sends the request
  again at the next pass: the bead carries one request, the operator gets a
  second mail.
- The dossier is generated on the tip as it stands when the pass settles
  the stop; a tip that moved since the stop (the protected branch taken up)
  gives a dossier on the newer commit, still « non conforme ».

`tests/convoy-stops-fixture-city-test.py` covers it on the graph of the
Fixture City, with the real gate, patch door, pack generator and escalation
door: two rounds consumed and a tip refused once more — no third repair,
one request on the operator's list with the link of the dossier and three
options, nothing more written by later passes; a round that does not reduce
the stories not observed and a story refused twice, both stopped before the
second round; a round that reduces them, whose second round starts; a
mechanical red and a finding of the end review sharing the two rounds; a
mechanical red found once the rounds are consumed, left without repair, the
request raised under the red. No isolated-city trial runs it under the real
order, and no real convoy reached it.

## A Delivered Outcome waits for Benjamin: the Acceptance Request (T28)

Spec §11. The last step of each convoy's pass is `settle_acceptance`; its
result is the key `acceptance` of the convoy's entry, absent when nothing
was due.

**The request.** When the convoy carries `delivered` and its `acceptance`
record has no `request` at that commit, the pass:

1. checks that the Evidence Pack recorded on the convoy is the one of the
   Delivered Outcome (commit and fingerprint) — otherwise it is refused and
   nothing is sent;
2. sends the Acceptance Request through `bin/escalation-door benjamin
   <convoy>`, on the convoy's own bead: blocking, `lien` = the `index.html`
   of the pack, **one** option (« Ouvrir l'Acceptance Session ») and **no
   recommendation** — its `pourquoi` says only that each condition of the
   end of the Spec is green at that commit;
3. notes it with `bin/convoy-state acceptance-requested <convoy> --bead
   <convoy>` (`docs/CONVOY_STATE.md`, « The acceptance record »).

The answer is `acceptance: {action: requested, commit, page, bead}`. Once
per Delivered Outcome: a later pass on the same state sends nothing. A
convoy Delivered again on another commit (after a repair) gets a new
request.

**The repair of an outage.** When `acceptance.panne` is recorded
(`bin/acceptance-session open` found that the product does not start at the
commit of the dossier, `docs/ACCEPTANCE_SESSION.md`) and names no ticket,
the pass publishes one `repair` through the patch door — written by code:
it restores the launch by the recipe of the profile, and its demonstration
line is the product answering its health probe on each synthetic dataset —
and names it with `set-acceptance-repair`. The answer carries
`acceptance.repair`. **Not while the rounds of the end are stopped**: under
`end_stop` no repair is published, this one included.

**The repairs of the findings Benjamin returned (T29).** When his last
answer is « constats rendus » (`convoy.judgement`, written by
`bin/owner-answer`, `docs/OWNER_ANSWER.md`), the pass publishes, for each
Owner Finding of route `repair` that names no tracked ticket, **one**
`repair` through the patch door — the draft recorded with the finding,
restoring the user story or the anchor it cites — and names it with
`bin/convoy-state set-owner-repair`. The answer carries
`acceptance.owner_repairs`: `{finding, …the published ticket}` each. A
finding of another route gets no repair, ever.

**The propositions of his « plus tard » (T29).** While a verdict « plus
tard » or an Owner Finding « plus tard » of his last answer names no
proposition — the proposition door failed when he answered — the pass runs
`bin/owner-answer proposals`: what it created is under
`acceptance.owner_proposals`, what the door still did not create under
`acceptance.proposals_pending`. Neither holds the end of the Spec.

**The end of the Spec is held** (`Convoy.end_due()` is false) while such a
finding has no published repair, or while the Planning Exception of the
batch is open: `acceptance.owner_hold` says which. The exception is lifted
by `bin/owner-answer resolve-exception`, on Benjamin's words; no code
starts the Planning Run that amends the Spec, and nothing notifies the
Mayor. Once the repairs are closed by their ticket-end gate and nothing is
held, the unchanged flow runs again at the new tip: the whole end-of-Spec
gate, a fresh Outcome Evaluation and end review (freshness is commit
equality), a new Evidence Pack — with its rubric 0 — and a new Acceptance
Request. The rounds of the end were set back to 0 by the answer.

An error at any step is `acceptance.error`: the pass exits 1 and the next
one tries again.

**Nothing here reads a clock.** No delay accepts, merges or closes in
Benjamin's place: a Delivered Outcome stays Delivered until he answers.

**What it leaves open.**

- Benjamin's answer to a Delivered Outcome (accepté, constats rendus,
  abandonné) is recorded by `bin/owner-answer`, not by the pass
  (`docs/OWNER_ANSWER.md`); answering the option of the request on the door
  triggers nothing. What the pass does once « accepté » or « abandonné » is
  recorded is the next section.
- The repair of an outage is published by the pass that follows `open`,
  not by `open`.
- A pass that fails between the door and `acceptance-requested` sends the
  request again at the next pass: one request on the bead, a second mail.

`tests/owner-answer-test.py` covers the judgement record and its holds;
`tests/acceptance-session-test.py` covers the records;
`tests/convoy-stops-fixture-city-test.py` and
`tests/fixture-city-oracle-test.py` cover the pass on the graph of the
Fixture City. No isolated-city trial runs it under the real order, and no
real convoy reached it.

## After Benjamin's answer: the merge and the closing (T30)

Spec §9 and §11, user stories 72 and 73. Once the last answer of
`convoy.judgement` is « accepté » or « abandonné » and no red replay voided
it, the pass hands the convoy to `bin/outcome-promote run <convoy> --repo
<rig_dir>` (`settle_promotion`, `docs/OUTCOME_PROMOTE.md`) **before any
other settlement, and renders nothing else on that Outcome**: no review, no
merge of a ticket, no ticket-end gate, no end-of-Spec gate, no Outcome
Evaluation, no Evidence Pack, no request. The end of the Spec is not run
again on a commit he judged. The pass is the order of the Factory, not an
agent session: `run` refuses any other caller that carries a session
identity.

The result is the key `promotion` of the convoy's entry, absent while
neither answer stands:

| What happened | `promotion` | The pass |
| --- | --- | --- |
| « accepté », merged and closed | `{promoted: true, merged, judged, closed: true, how: accepted, said, outcome: accepted, purged}` (`resumed: true` when an earlier run had recorded the merge) | exit 0 |
| « abandonné », closed, nothing merged | `{promoted: false, merged: null, closed: true, how: abandoned, said, outcome: abandoned}` | exit 0 |
| the take-up of the protected branch is red or in conflict | `{promoted: false, merged: null, closed: false, cause, red, reason, repair}` | exit 0: an outcome of the pass |
| the Spec or the draft could not be closed | the entry above, with `pending` | exit 1; the next pass, and `orders/planning-artifacts-close.toml`, take it up |
| the merge, the note, the purge or the closing could not be made | `{error: "refus : …"}` | exit 1; the next pass tries again |
| « état sans règle » found by the command | `{message, unruled}` | exit 1 |

**A red is not a failure.** When the protected branch moved since the
judgement and the mechanical controls replayed on its take-up are red, or
the two branches conflict, `bin/outcome-promote` merges nothing, records
the red of the integration branch and voids the acceptance. The pass moves
its `error` to `reason` and, **in the same pass**, publishes the one
`repair` of that red through the patch door (`settle_red`, « The two stops
of a convoy » above): `promotion.repair`. From the next pass on no answer
stands any more, so the unchanged flow runs: only that `repair` starts, the
red is cleared once it is delivered, the whole end-of-Spec gate runs at the
new tip with a fresh Outcome Evaluation and end review, a new Evidence
Pack, Delivered, and a new Acceptance Request. The rounds of the end were
set back to 0 by the voiding.

**A convoy closed by command is not advanced.** `bin/convoy-state list`
names it under `closed`, which `--all` does not walk and `--check-only`
does not count. Named as CONVOY, the pass starts nothing in it, answers
`closed` (the record of its closing) and `promotion: {done: true, …}`:
`bin/outcome-promote run` writes nothing on the convoy and only has the
closing of its Spec and its draft replayed.

**What it leaves open.**

- The merge is made inside the pass, under the timeout of the order (40 min, derived from
  `config/test-budgets.json`);
  a replay of the mechanical controls killed there is taken up by the next
  pass (`docs/OUTCOME_PROMOTE.md`, Limits).
- Once an answer that ends the judgement stands, `settle_acceptance` no
  longer runs: a « plus tard » whose proposition the door had not created
  yet (`acceptance.proposals_pending`) is not retried by the pass, and
  after the closing `bin/convoy-state` refuses to name it on the convoy.
- A protected branch that refuses the push leaves the Outcome accepted and
  unmerged: each pass exits 1 with `promotion.error`, so the order fails on
  every tick until it is settled.
- Nothing tells Benjamin that his acceptance was voided, other than the new
  Acceptance Request that follows the repair.

`tests/outcome-promote-test.py` covers the command;
`tests/convoy-stops-fixture-city-test.py`, class
`PromotionOnTheFixtureCity`, covers the pass on the graph of the Fixture
City with the real patch door — one merge and the convoy closed on
« accepté », the convoy closed and the protected branch unmoved on
« abandonné », a conflict after « accepté » merging nothing and the pass
publishing one `repair`. `tests/convoy-manual-lifecycle-isolated-city-test.sh`
(local-only) shows, under the real order, that no pass names a convoy
closed by command any more. No isolated-city trial runs a merge under the
real order, and no real convoy reached it.
