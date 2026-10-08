# The end-of-Spec gate (T23, T24 and T25; Spec af-wf4w5r §9, points 1 to 5)

## What it is for

In a convoy that carries the **new-flow mark**, the tickets being closed is
not the Spec being verified. Once every ticket of the convoy is closed, code
renders three mechanical verdicts, in this order, **all tied to one commit**
of the integration branch that holds the tip of the protected branch. No
agent renders them, and no agent sets a deviation or a « non fait » aside
(user stories 56 and 59). On that same commit, three more conditions are
read, which the gate does not render: the Outcome Evaluation and the
findings « hors ticket », in what the Evaluator of the end handed in (T24,
`docs/OUTCOME_EVALUATION.md`, user stories 57 and 60), and the end code
review of the whole assembled diff (T25, `docs/SPEC_END_REVIEW.md`, user
story 58).

A convoy **without** the mark is not concerned: the gate answers « pas un
convoi du nouveau flux » (exit 4) and writes nothing.

`bin/spec-end` is the gate. `bin/convoy-advance` runs it on each pass of its
order, once every ticket of the convoy is closed and its integration branch
is not red (`docs/CONVOY_ADVANCE.md`).

```bash
./bin/spec-end check af-convoy --repo <project repository>                          # the verdicts as they stand now; reads only
./bin/spec-end run   af-convoy --repo <project repository> --profile <descriptor>   # the gate; refused from an agent session
```

To know where the end of a Spec stands, run `check`: each condition has a
verdict and one line that says what was read.

## The six conditions (list `spec-end/v3`)

| # | Name | Met when |
| --- | --- | --- |
| 1 | `registry` | Every ticket is closed by the ticket-end gate (`docs/TICKET_END.md`) or withdrawn from the graph by a resolved Planning Exception; none is parked; every deviation and every « non fait » of a Ticket Handoff is in a final state, « réparé » or « accepté par Benjamin »; no Planning Exception is open. |
| 2 | `tests` | The integration branch has taken up the protected branch and the regression command of the project's profile ends with code 0 on that tip (`bin/spec-integration take-up`, `docs/SPEC_INTEGRATION.md`). |
| 3 | `fidelity` | On that same tip, the mechanical fidelity check is green on every anchor of every prototyped state, for every screen of the profile (`bin/prototype-fidelity check`, `docs/PROTOTYPE_FIDELITY.md`). A deviation on an anchor a resolved Planning Exception accepted is not an open one. A convoy none of whose tickets names a Validated Prototype passes with « sans objet ». |
| 4 | `outcome_evaluation` | Once 1 to 3 are green: every numbered user story of the Spec is « observée avec preuve » on the assembled product at that commit (`bin/outcome-evaluation verdict`), and no finding « hors ticket » is left unclassified. |
| 5 | `findings` | Every finding « hors ticket » of a Ticket Handoff is in a final state: « réparé », « proposition pour Benjamin » or « écarté ». |
| 6 | `end_review` | Once 1 to 3 are green, on that same commit: the end code review of the whole diff of the integration branch against the protected branch is complete and favorable (`bin/spec-end-review`, `docs/SPEC_END_REVIEW.md`). Read in the tracker, not rendered by the gate. Absent, running, stopped without a verdict, made on another commit, or with a Blocking Finding: not met, and the detail says which. |

A condition that is not met stops the gate there: the following ones are
**not launched** (`not_run`); the end review alone does not wait for the
Outcome Evaluation: both are made in parallel on the commit of the three
verdicts (Spec §9, point 4), and condition 6 is read whatever conditions 4
and 5 say. Changing the list means a new version. Conditions 1 to 3 are the
**mechanical** ones: their verdicts are what the gate records, as soon as
the three are green, and `bin/convoy-state` holds the same names and refuses
a record that is not those three, all passing. Conditions 4 to 6 are not
recorded by the gate: they are read at each call in what the Evaluator of
the end and the reviewer of the end handed in, which is tied to the commit
of the three verdicts. The gate launches no agent; `bin/convoy-advance` has
the evaluation and the review settled (`bin/outcome-evaluation settle`,
`bin/spec-end-review settle`). A record written under `spec-end/v1` or
`spec-end/v2` is read as outdated: everything is replayed.

## The registry: tracked elements

A **tracked element** is a deviation or a « non fait » an author declared in
its Ticket Handoff (sections `deviations` and `not_done`). `bin/convoy-state
show` renders them per ticket under `tracked_items`, each with an id
(`deviations.1`, `not_done.2`), its text and a state that code computes:

| State | Read when |
| --- | --- |
| `ouvert` | Anything else. |
| `accepté par Benjamin` | The last Planning Exception that names the element, raised since that Handoff, was answered by the operator with the option that accepts it. |
| `réparé` | The operator answered otherwise, code published a `repair` for the element, and the ticket-end gate closed that `repair`. |

There is no command that sets an element to a state. An element left
`ouvert` refuses the registry, which names it. The first time, the gate asks
the operator, once per ticket: one request through `bin/escalation-door
benjamin` on the ticket, with two options — **a** « Faire réparer par un
ticket repair », **b** « Accepter ce qui est livré, tel quel » — recorded as
a Planning Exception that names the elements (`bin/convoy-state
raise-planning-exception --item`). The operator answers with
`./bin/escalation-door repondre <ticket> a|b`. The closed ticket stays
closed.

- **b**: the elements read « accepté par Benjamin ».
- **a**: the next pass of `bin/convoy-advance` publishes one `repair` for
  the elements of that ticket through the patch door, names it on them
  (`bin/convoy-state set-item-repair`) and starts it like any ticket. The
  elements read « réparé » once the ticket-end gate has closed it. This
  repair counts no round of the end: Benjamin asked for it, it is not a
  mechanical red.

## A mechanical red: one repair by code, one round

Red tests (condition 2) or a red fidelity (condition 3) are recorded as the
**red of the integration branch** (`bin/convoy-state record-integration-red`,
with `check: fidelity` for the second), and one round of the end of the Spec
is counted in the same tracker write (`counters.end_rounds`). From there the
red is the one of T21 (`docs/CONVOY_ADVANCE.md`, « The two stops of a
convoy »): the next pass publishes its one `repair` through the patch door
and starts it; nothing else starts or merges; the gate renders no verdict
while the branch is red. Once the `repair` is merged green and closed, the
gate replays everything on the new tip.

- Red tests: nothing is pushed; the red names the regression command.
- Red fidelity: the takeover of the protected branch is already pushed (the
  tests were green on it); the red names the deviations, and its `repair`
  restores an `anchor`.

The same red seen by several passes is recorded once and counted once.

## One commit more outdates every verdict

Three green verdicts are recorded on the convoy
(`bin/convoy-state record-spec-end`) with the commit they were rendered on
and the tip of the protected branch that commit holds:

```json
{"at": "…", "commit": "<tip of the integration branch>", "protected": "<tip of the protected branch>",
 "version": "spec-end/v3",
 "conditions": [{"number": 1, "name": "registry", "verdict": "pass", "detail": "…"}, "… three entries"],
 "records": {"tests": {"command": "…", "exit_code": 0, "commit": "…"}, "fidelity": {"commit": "…", "prototypes": ["…"]}}}
```

It is stored as `gc.flow.spec_end` and rendered under `convoy.spec_end` by
`bin/convoy-state show`. `check` reads it against the branches as they are
now: as soon as the integration branch holds one commit more, or the
protected branch moved, the three verdicts are `stale` (« périmés ») and
everything is to replay. `run` on the tip the verdicts were rendered on
replays nothing and writes nothing (`replayed: false`); on another tip it
runs the three conditions again and rewrites the record. Conditions 4 to 6
follow: an Outcome Evaluation handed in at another commit is to replay on
the tip, and a round of the end review made on another commit never stands
for it (« revue de fin liée à un autre commit »): the review is made again
in full on the new tip.

## Refusals and exit status

Every answer is one JSON object on stdout: `conditions` (number, name,
label, verdict `pass` / `fail` / `not_run` / `stale`, detail), `missing`,
`mechanical` (whether the three mechanical verdicts are green on the tip,
their commit, and why not), and for `run` what it did (`refused`,
`requests`, `red`, `end_rounds`, `replayed`). `run` names in `missing` the
conditions that refused; `check` every condition that is not green.

| Exit | Meaning |
| --- | --- |
| 0 | The six conditions are met on the current tip. |
| 1 | Refused, or a condition is not met: it is named (`condition N (label) non réunie : …`). |
| 3 | The convoy is in an « état sans règle »: no verdict. |
| 4 | The convoy does not carry the mark. |

- `run` is refused from an **agent session** (`GC_AGENT`, `GC_SESSION_NAME`
  or `GC_SESSION_ID` set), whatever its role. `check` is open to anyone.
- `run` is refused while the integration branch is red, and on a convoy
  without an integration branch.
- Three green verdicts with the end review missing: exit 1, the three
  verdicts are recorded (or kept, `replayed: false`), and `error` names
  condition 6 with what was read, after conditions 4 and 5 if they are not
  met either. `check` renders conditions 4 to 6 only when the three before
  them are green on the tip, `not_run` otherwise.
- A registry that refuses writes nothing but the request to the operator,
  once. `check` never writes.
- In the answer of `bin/convoy-advance`, a condition that is not met is an
  outcome of the pass (`spec_end.reason`); a gate that could not run is a
  failure of it (`spec_end.error`).

## Limits

- **The gate runs inside the pass of the order**, whose timeout is 300 s
  (`orders/convoy-advance.toml`), and under the Factory-wide lock of the
  passes. The regression command and the fidelity of every screen with a
  real browser may take longer: the order is then killed before the record
  is written and the next pass starts over. Not measured on a real project.
- **No sealed piece for the end tests and the end fidelity.** The evidence
  store files pieces per ticket; what the two controls read is kept in the
  record on the convoy (`records`), which is not sealed.
- **The request of the registry sits on a closed ticket bead**:
  `bin/escalation-door list` shows it under « sur un bead fermé ».
- **A takeover of the protected branch in conflict** is a refusal of the
  gate at each pass, with no red, no repair and no round: a conflict is not
  a red control (same limit as the merge, `docs/SPEC_INTEGRATION.md`).
- **Only the Ticket Handoff is tracked.** A TDD amendment is not a tracked
  element. A finding « hors ticket » is not one either: it is classified by
  the Evaluator of the end and read by condition 5
  (`docs/OUTCOME_EVALUATION.md`).
- **The repair of tracked elements is written by code** from the text of the
  Handoff: one criterion, on the entry point of the ticket's demonstration
  line. A sharper criterion is a Planning Exception, as for any ticket.
- **The gate verifies; it accepts nothing and closes nothing.** The
  acceptance by Benjamin is a later ticket; the round counted here is not
  yet compared to a bound, and a story still not observed after its repair
  counts no round.
- **The Fixture City Oracle has no scenario of its own for the end of a
  Spec**: its delivery driver walks the gate with a stand-in for the
  Evaluator and for the reviewer of the end. Under the real controller,
  order and tracker, the gate passed its six conditions in one isolated-city
  trial, the one of the end review, with a stand-in for the Evaluator of the
  end called in place of the dispatch door (Proof).

## Proof

- `tests/spec-end-test.py`: the command lines on a fake tracker state, with
  a copy of the Delivery Fixture City in a throwaway repository and its own
  remote. The tickets are closed by the real `bin/ticket-end`, the takeover
  made by the real `bin/spec-integration`, the fidelity measured by the real
  `bin/prototype-fidelity`, the request raised and answered through the real
  `bin/escalation-door`. One test per pass and per refusal, each refusal
  re-reading the tracker, the store and the branches.
- `tests/convoy-stops-fixture-city-test.py`: on the graph published by the
  real publication door, the pass runs the gate; red tests count one round
  and their one `repair` is published by the real patch door, as is the
  `repair` of a red fidelity and the one the operator asks for a « non
  fait »; an accepted « non fait » passes the registry.
- `tests/convoy-advance-test.py`: the gate run by the pass once every ticket
  is closed and not before, a registry refusal and red tests as outcomes, a
  gate that cannot run as a failure.
- `tests/outcome-evaluation-test.py` and the suites above: conditions 4 and
  5, and the six conditions green on one commit
  (`docs/OUTCOME_EVALUATION.md`, Proof).
- `tests/spec-end-review-test.py` and
  `tests/spec-end-review-isolated-city-test.sh` (local-only): condition 6,
  the second under the real controller, order and tracker
  (`docs/SPEC_END_REVIEW.md`).
- `tests/spec-integration-test.py` (`take-up`), `tests/convoy-state-test.py`
  (tracked elements, `--item`, `set-item-repair`, `record-spec-end`,
  `--check`, `--end-round`).
- `tests/spec-end-real-tracker-test.sh` (local-only): in a disposable city,
  on the real `gc`/`bd`, the state the gate writes is written and read
  back — tracked elements, the Planning Exception that names them, their
  repair and « réparé » once it is closed, a red with `check: fidelity` and
  one round in the same write, the record of the gate — with each refusal
  leaving the tracker unchanged. Passed on 2026-10-08 (gc and bd as
  installed on the Factory host). No gate runs in it.
