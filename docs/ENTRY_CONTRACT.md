# Entry contract of the new flow (T05, T06, Spec af-wf4w5r §2)

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

T05 holds each ticket to the contract; T06 holds the graph to the Spec it
slices and to its project (coverage of the user stories, operator needs,
launch recipe), poses the pointers in each ticket, and applies all of it to
`bd-patch`. The Validated Prototype reference and the Prototype Fold are
T36. The graph reviewer (T08) is delivered: once the entry contract is
met, `bd-publish` also refuses a draft that declares the contract without a
graph review that holds for its current digest (`docs/GRAPH_REVIEW.md`).

```bash
./bin/ticket-graph-publish bd-publish af-draft --project agent-factory
./bin/ticket-graph-publish lift-need  af-draft --project agent-factory \
    --need cle_api_meteo --by benjamin-hurand --evidence "« la clé est au coffre »"
./bin/ticket-graph-publish bd-patch   af-revised --project agent-factory \
    --author to-tickets --reason "Planning Exception pd-1" \
    --planning-exception-register path/to/register.json
```

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
| `user_stories` | `vertical_slice` | required: the numbers of the Spec's numbered user stories the slice covers, each once, each present in the Spec. Refused on a `prefactoring` (it names the slice it unblocks) and on a `repair` (it names what it restores): neither covers a story |
| `establishes_launch_recipe` | `vertical_slice` | optional, `true` only: this slice establishes the project's launch recipe (see "Launch recipe") |

A `repair` is also held to what the door can read in the approved Spec:
`restores.kind: user_story` must cite the number of exactly one story of
the Spec, and `restores.kind: spec_line` a line found word for word in its
text. An `anchor`, a `repo_rule` or a `red_check` is recorded as cited: the
door has nothing to read it against.

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

## The graph against its Spec and its project (T06)

**Coverage.** The unit is the numbered user story of the Spec, read by
`bin/spec-approve outline` -- the reader `bd-approve` holds the Spec to. A
graph is refused when a story is cited by no `vertical_slice`; the refusal
lists the orphan numbers. Coverage is computed on the whole graph: for a
patch, on the graph that results from it.

**Operator needs.** Every need known at planning is declared in the draft,
under the approved digest:

```yaml
operator_needs:
- id: cle_api_meteo        # lowercase letters, digits and _
  kind: secret             # secret | access | project_declaration | spend
  what: Clé de l'API météo dans le coffre de l'usine
```

Nothing is published while one is not lifted, so no convoy exists that
could start with a need open. A need is lifted by `lift-need`, which
records on the draft bead (`operator_need.<id>`) who lifted it, his exact
words and when; it refuses anyone but the project's declared human
approver, empty words, and a need the draft does not declare. A revised
draft declares only the needs its own changes bring.

**Launch recipe.** The recipe and the entry points live in the project
profile (`config/project-descriptors/<project>.json`, block `launch`; the
project is the Spec's `gc.project_id`; `--descriptors-dir` names another
directory). A project whose profile declares none -- or that has no
profile -- is refused, unless one `vertical_slice` of the graph carries
`establishes_launch_recipe: true` and is its first slice: every other
`vertical_slice` and `repair` waits for it, directly or through other
tickets.

**Declared Scope.** Two tickets not ordered by `blocked_by` whose
`scope.paths` overlap are put in series, as before the contract; the added
edges are listed under `scope_edges`.

## Pointers posed by the door (T06)

The text of a published ticket is what the approved draft says of it, then
four sections the door writes itself -- none is ever written in the draft:

| Section | Content | Source |
|---|---|---|
| `## Spec` | the Spec bead id and its digest | the approved Spec bead |
| `## User stories` | number and text of the stories a slice covers, or of the story a repair restores | `user_stories` / `restores`, and the Spec text |
| `## Sibling tickets` | every other ticket of the graph: id, kind, title, demonstration line | the graph |
| `## Seams` | the entry points of the project profile, and the Spec's « Testing Decisions » (its numbered items, or its lines when none is numbered) | the profile, the Spec text |

After a patch, the tickets the revision does not carry keep their own text
and get these sections again, so a ticket names the siblings added since.

## What a refusal looks like

Everything is checked before any write, and every reason is listed at once,
ticket by ticket -- then `brouillon` for the draft as a whole and `graphe`
for the graph -- in the Operator Language, on stderr (exit 1):

```
ticket-graph-publish: refus : le brouillon af-… déclare le contrat du nouveau flux (new-flow/v1) et ne le respecte pas (3 raison(s), 2 ticket(s)) ; rien n'est écrit.
- T02 : genre inconnu « prefactor » (attendu : vertical_slice, prefactoring ou repair ; aucun genre par défaut)
- T03 : pas de ligne de démonstration : un vertical_slice dit, dans le champ demonstration_line, ce qu'on observe sur le produit lancé
- T03 : critère 1 « Un test montre que … » : ne nomme pas son point d'entrée et son observable (…) ; nomme un test (« test »)
- brouillon : besoin opérateur non levé : cle_api_meteo (secret) — Clé de l'API météo … ; une fois levé par …
- graphe : user stories couvertes par aucun ticket : 2, 3 (chaque user story numérotée de la Spec af-… est citée par au moins une vertical_slice)
```

## What a published new-flow convoy carries

| What | Where | Written by |
|---|---|---|
| Kind | `gc.ticket_kind` on each ticket (the declared kind, never a default) | the graph transaction |
| New-flow mark | `gc.flow.mark` on the convoy and each ticket | `bin/convoy-state mark` |
| Demonstration line | `gc.flow.demonstration_line` on each slice and repair | `bin/convoy-state mark --demonstration-line` |
| Covered user stories | `gc.flow.user_stories` on each slice | `bin/convoy-state mark --user-stories` |
| Launch recipe established here | `gc.flow.establishes_launch_recipe` on at most one slice | `bin/convoy-state mark --establishes-launch-recipe` |

Code reads them back with `bin/convoy-state show <convoy>`
(`docs/CONVOY_STATE.md`): `kind`, `mark`, `demonstration_line`,
`user_stories` and `establishes_launch_recipe` per ticket.
The ticket text shows the same demonstration line, what a prefactoring
unblocks, what a repair restores, and each criterion as « Point d'entrée —
Observable — Faux si ».

The graph is created in one tracker transaction, then marked: tickets
first, the convoy last. If the marking fails, the door exits non-zero and
says the convoy is published but not marked; until then it reads as a
convoy of the old flow. Running the same command again resumes at the
marking and changes nothing else. The Mayor is not woken for a marked
convoy: code starts its tickets, not the Mayor (Spec §0 rule 3).

## The patch door (T06)

`bd-patch` on a draft that declares the contract revises a convoy published
under it. A revised draft carries the unfinished tickets it changes or
needs as blockers, and the tickets it adds; it never carries a closed
ticket. Everything above applies as it is to what the revision carries,
and the graph checks (coverage, launch recipe) to the graph that results:
what the convoy tracks -- whatever digest each ticket was last published
under -- less what is withdrawn, with the revision on top. Before any
write it also refuses:

- a revision whose `revises_digest` is not the convoy's current digest,
  or whose Spec is not the one the convoy was published from;
- a draft that declares the contract against a convoy without the mark,
  and a draft that does not declare it against a marked convoy: a ticket
  added to a marked convoy is never weaker than an original one;
- `--reslice`: it is the Mayor's gesture, and the Mayor does not modify the
  tickets of a marked convoy (Spec §0 rule 3);
- a published ticket whose kind, demonstration line, covered user stories
  or `establishes_launch_recipe` differ from what `bin/convoy-state` holds:
  they are frozen with the approved graph, another one is another ticket.

**Repair without approval.** A revised draft that carries no approval
(`approved_by`, `approved_evidence`, `approved_digest` all absent) is
published only if it adds nothing but `repair` tickets -- each held to the
contract, so each naming what it restores -- to a graph it otherwise leaves
as published: the text of a carried ticket is unchanged, and it may only
gain an added repair among its blockers. Anything else (an added slice, a
changed criterion, a reordering, a withdrawal) is refused and asks for the
approval of the revised graph. This is the mechanical reading of « tant
qu'il reste dans l'intention approuvée » (Spec §2): the door checks the
citation where it can read it (a user story, a line of the Spec), not that
the cited object is really broken.

**Withdrawing a ticket.** An approved revision removes a ticket from the
graph by naming it and the Planning Exception that decided it:

```yaml
withdrawn:
- ticket: T4
  planning_exception: pd-1
```

The door reads `bin/planning-exception status <register>`
(`--planning-exception-register`) and refuses unless the decision is
`resolved`. It refuses a ticket the revision still carries, a closed
ticket, and a withdrawal that leaves an unfinished ticket waiting for the
withdrawn one without saying what becomes of it. Coverage is recomputed
without the withdrawn ticket: a story it alone covered is an orphan unless
the amended, re-approved Spec no longer holds it or another slice of the
revision covers it. The ticket is then closed behind its `withdrawn` gate
record (`bin/convoy-state record-gate`), so it is not read as closed
outside a gate.

On success the added tickets are created in dependency order, tracked by
the convoy (`bd dep add <convoy> <ticket> --type tracks`) and marked through
`bin/convoy-state`; the Mayor is not woken. As for a publication, a patch
whose marking fails says so, and running the same command again completes
it (withdrawals and marking) without writing anything twice.

## Proof

`tests/ticket-graph-publish-entry-contract-test.py` drives the command line
on a fake tracker: one test per refusal and per pass, each refusal
re-reading the tracker to prove nothing was written; the Cockpit V2 draft
(`tests/fixtures/ticket-graph-publish/cockpit-v2-draft.yaml`, a frozen copy
of af-i67vl0) redeclared to the contract is refused ticket by ticket; an
undeclared draft is compared, bead for bead, to what the door published
before this ticket (`legacy-publication-golden.json`).
`tests/ticket-graph-publish-coverage-test.py` does the same for T06, on
both doors: coverage, operator needs and `lift-need`, launch recipe,
pointers read on the published ticket, a patch that adds, changes or
withdraws tickets, with and without approval, the Planning Exception
register being written by the real `bin/planning-exception`.
`tests/ticket-graph-publish-new-flow-real-tracker-test.sh` (local-only)
replays refusal, publication, marking, pointers, an orphan story, an
operator need, a repair added by patch without approval, a withdrawal and
the undeclared case on the real `gc`/`bd` in a disposable city.
