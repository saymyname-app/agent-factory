# Convoy Advance (T04, Spec af-wf4w5r §0 rule 3, §4)

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
```

The Factory runs it by itself: the controller evaluates
`orders/convoy-advance.toml` on each of its ticks (every 20 to 30 seconds
observed on Gas City 1.4.1: a `condition` order is paced by its check, not
by its `interval`) and runs `--all` only while `--check-only` passes. The
order costs one tracker read and runs nothing while no marked convoy is
open.

## What one pass does

For each ticket of the convoy, in the convoy's own order, the pass starts it
when all of this holds:

- the ticket is `open`, carries the mark, and has no gate record and no
  Ticket Exit yet (it was never started);
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
`start.formula` and `start.role`. With no formula the command refuses and
starts nothing.

## Answers

Every answer is one JSON object on stdout: the ceiling, the sessions counted
per role, the tickets awaiting a session, and per convoy the tickets
`started`, `waiting` (with the reason: blocker ids, or the ceiling),
`deferred` (the door deferred: low memory, hot path held — retried on the
next pass) and `refused` (the door refused, with its reason).

| Exit | Meaning |
|---|---|
| 0 | the pass is done; what it started is listed, possibly nothing |
| 1 | refused or could not run (settings, tracker), or the door refused a ticket |
| 3 | a convoy is in an « état sans règle »: none of its tickets is started, the anomalies are listed |
| 4 | the convoy does not carry the mark: « pas un convoi du nouveau flux » |

On an « état sans règle » (`bin/convoy-state show`, exit 3) the pass starts
nothing in that convoy and names the anomalies. Raising the factory incident
and the automatic resume are T34's.

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
