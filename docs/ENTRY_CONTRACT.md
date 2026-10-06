# Entry contract of the new flow (T05, Spec af-wf4w5r §2)

## Status and purpose

`bin/ticket-graph-publish bd-publish` holds a Ticket Graph Draft that
**declares the new-flow contract** to the entry contract of the Delivery
Workflow before it writes anything, and publishes its convoy with the
**new-flow mark**. A draft that does not declare the contract is published
exactly as before: same beads, same text, same Mayor wake, no mark.

The contract is opt-in per draft, in the text Benjamin approves:

```yaml
flow_contract: new-flow/v1     # top-level key of the draft description
tickets:
- id: T2
  kind: vertical_slice
  ...
```

The declaration is covered by the approved digest, like the tickets. Any
other value is refused: the contract is never guessed. No draft of a live
project declares it until the new flow is complete (Spec §14).

This is the first part of the entry contract. Coverage of the user stories,
pointers posed by the door, operator needs and tickets added by patch are
T06; the Validated Prototype reference and the Prototype Fold are T36; the
graph reviewer is T08.

## Ticket fields

A ticket carries only fields the door knows; any other field is refused.

| Field | Kinds | Rule |
|---|---|---|
| `id`, `title`, `blocked_by`, `target_rigs`, `what_it_delivers` | all | as before |
| `scope.paths`, `split_from` | all | optional, as before |
| `kind` | all | `vertical_slice`, `prefactoring` or `repair`; **no default** |
| `demonstration_line` | `vertical_slice`, `repair` | required: what is observed on the launched product, in its own field (a line left inside `what_it_delivers` does not count). Refused on a `prefactoring`, which changes no behavior |
| `unblocks` | `prefactoring` | required: the id of a `vertical_slice` of the graph that waits for it (`blocked_by`, directly or through other tickets) |
| `restores` | `repair` | required: `{kind, ref}`, `kind` among `user_story`, `anchor`, `spec_line`, `repo_rule`, `red_check`, `ref` citing it |
| `acceptance_criteria` | all | a list of criteria, each `{entry_point, observable, false_if}` |

A criterion names its entry point (the route, command or public API it is
observed through), its observable (field, role and label) and the
observation that would make it false. A plain sentence is refused: it names
neither. A criterion is also refused when it names:

- **a test** — the word `test`/`tests` or a test runner, in any of the
  three fields (« un test montre que… » is never a criterion);
- **a file** — a source or configuration file name, in `observable` or
  `false_if`. The entry point may be a path: a command and a route are;
- **an internal function** — a call such as `load_items()`, or « fonction
  interne » / "internal function", in `observable` or `false_if`.

These are text checks: they refuse the wordings that let a ticket be green
without the product serving anything, and they cannot prove a criterion is
executable (Spec, Further Notes 6). A product whose visible labels contain
the word « test » has to describe them otherwise.

A draft that declares the contract carries no `global_execution_contract`:
the execution contract copied into every ticket is gone (Spec §2, « prose
de procédé »), and the published ticket text has no such section.

## What a refusal looks like

Everything is checked before any write, and every reason is listed at once,
ticket by ticket, in the Operator Language, on stderr (exit 1):

```
ticket-graph-publish: refus : le brouillon af-… déclare le contrat du nouveau flux (new-flow/v1) et ne le respecte pas (3 raison(s), 2 ticket(s)) ; rien n'est écrit.
- T02 : genre inconnu « prefactor » (attendu : vertical_slice, prefactoring ou repair ; aucun genre par défaut)
- T03 : pas de ligne de démonstration : un vertical_slice dit, dans le champ demonstration_line, ce qu'on observe sur le produit lancé
- T03 : critère 1 « Un test montre que … » : ne nomme pas son point d'entrée et son observable (…) ; nomme un test (« test »)
```

## What a published new-flow convoy carries

| What | Where | Written by |
|---|---|---|
| Kind | `gc.ticket_kind` on each ticket (the declared kind, never a default) | the graph transaction |
| New-flow mark | `gc.flow.mark` on the convoy and each ticket | `bin/convoy-state mark` |
| Demonstration line | `gc.flow.demonstration_line` on each slice and repair | `bin/convoy-state mark --demonstration-line` |

Code reads all three back with `bin/convoy-state show <convoy>`
(`docs/CONVOY_STATE.md`): `kind`, `mark` and `demonstration_line` per ticket.
The ticket text shows the same demonstration line, what a prefactoring
unblocks, what a repair restores, and each criterion as « Point d'entrée —
Observable — Faux si ».

The graph is created in one tracker transaction, then marked: tickets
first, the convoy last. If the marking fails, the door exits non-zero and
says the convoy is published but not marked; until then it reads as a
convoy of the old flow. Running the same command again resumes at the
marking and changes nothing else. The Mayor is not woken for a marked
convoy: code starts its tickets, not the Mayor (Spec §0 rule 3).

`bd-patch` refuses a draft that declares the contract until the patch door
applies it (T06): a ticket added by patch must never be weaker than an
original one.

## Proof

`tests/ticket-graph-publish-entry-contract-test.py` drives the command line
on a fake tracker: one test per refusal and per pass, each refusal
re-reading the tracker to prove nothing was written; the Cockpit V2 draft
(`tests/fixtures/ticket-graph-publish/cockpit-v2-draft.yaml`, a frozen copy
of af-i67vl0) redeclared to the contract is refused ticket by ticket; an
undeclared draft is compared, bead for bead, to what the door published
before this ticket (`legacy-publication-golden.json`).
`tests/ticket-graph-publish-new-flow-real-tracker-test.sh` (local-only)
replays refusal, publication, marking and the undeclared case on the real
`gc`/`bd` in a disposable city.
