# Convoy State (T33, Spec af-wf4w5r §0 rule 2)

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
./bin/convoy-state mark af-convoy \
  --demonstration-line af-t1="Sur le produit lancé, …"  # publication door (T05)
./bin/convoy-state show af-convoy --repo rigs/product   # every reader
./bin/convoy-state set-branch   af-convoy af-t1 --branch ticket/af-t1
./bin/convoy-state record-gate  af-convoy af-t1 --gate dispatch
./bin/convoy-state set-exit     af-convoy af-t1 --exit finished
./bin/convoy-state set-verdict  af-convoy af-t1 --kind code_review --state favorable --commit <sha>
./bin/convoy-state bump-counter af-convoy --ticket af-t1 --counter resumes --counter correction_rounds
./bin/convoy-state set-counter  af-convoy --counter end_rounds --value 0
./bin/convoy-state add-evidence af-convoy af-t1 --piece red_proof --digest sha256:<hex> --commit <sha>
./bin/convoy-state record-gate  af-convoy af-t1 --gate ticket_end --commit <sha>
```

Every answer is one JSON object on stdout.

| Exit | Meaning |
|---|---|
| 0 | done |
| 1 | refused, or could not run: nothing was written (`{"ok": false, "error": "refus : …"}`) |
| 3 | `show` found an « état sans règle »: the state is printed, with the reason |
| 4 | the convoy does not carry the mark: « pas un convoi du nouveau flux » |

## Stored fields and closed lists

| Field | Key | On | Values |
|---|---|---|---|
| Mark | `gc.flow.mark` | convoy, ticket | `new-flow/v1` |
| Kind | `gc.ticket_kind` (read only: written by the publication door) | ticket | `vertical_slice`, `prefactoring`, `repair` |
| Demonstration line | `gc.flow.demonstration_line` | ticket (`vertical_slice`, `repair`) | one non-empty line, written once by `mark` |
| Ticket branch | `gc.flow.branch` | ticket | branch name |
| Ticket Exit | `gc.flow.exit` | ticket | `finished`, `planning_exception`, `operator_request`, `technically_blocked`, `interrupted` |
| Verdict | `gc.flow.verdict.<kind>` | ticket | kind: `test_review`, `code_review`, `evaluation`, `fidelity`; state: `favorable`, `unfavorable`; always with the full commit SHA it judged |
| Counter | `gc.flow.counter.<name>` | ticket: `resumes`, `correction_rounds`; convoy: `end_rounds` | integer ≥ 0 |
| Evidence fingerprint | `gc.flow.evidence.<piece>` | ticket | `sha256:<64 hex>` and the commit of the piece |
| Gate record | `gc.flow.gate.<gate>` | ticket | `dispatch`, `ticket_end` (commit required), `withdrawn` (removed from the graph by a resolved Planning Exception) |

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
`ticket_end` gate record without a commit; a ticket that is not tracked by
the convoy, or that does not carry the mark.

Writes on one convoy are serialised by a lock (`CONVOY_STATE_LOCK_DIR`,
default `$XDG_RUNTIME_DIR` or `/tmp`), so concurrent counter bumps are all
counted and a reviewer and an Evaluator can write the same ticket in parallel.

## What a read reports

`show` renders, per ticket: mark, kind, demonstration line, tracker status,
branch and its tip, Ticket Exit, verdicts, counters, evidence fingerprints
and gate records.

**Verdict validity** (Spec §8, « commit après verdict »). A verdict carries
`"valid": true` only while its commit is the tip of the ticket's branch in
`--repo` (default: the current directory; the local branch is read first,
then `origin/<branch>`). A commit added to the branch after the verdict
makes it `"valid": false`: nothing is rewritten in the tracker, the verdict
simply has to be replayed on the new tip.

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
- any stored value this command would have refused to write, and any
  `gc.flow.*` key it does not know (a field invented outside the command).

`convoy-state` only signals. Stopping the convoy and raising the factory
incident on exit 3 is T34's.

## Proof

`tests/convoy-state-test.py` drives the command line on a fake tracker
state (`tests/fixtures/convoy-state/gc`): one test per pass and per
refusal, each refusal re-reading the tracker to prove nothing was written.
`tests/convoy-state-real-tracker-test.sh` (local-only) replays the same
contract on the real `gc`/`bd` in a disposable city.
