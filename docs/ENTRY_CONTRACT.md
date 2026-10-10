# Entry contract of the new flow (T05, T06, T36, Spec af-wf4w5r §2 and §3)

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
`bd-patch`. T36 holds an interface graph to its Prototype Fold and poses
the Validated Prototype reference in each interface ticket ("Interface
tickets and the Prototype Fold"). The graph reviewer (T08) is delivered: once the entry contract is
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
| `prototype_fold` | `vertical_slice` | optional, `true` only: this slice is the Prototype Fold of a Validated Prototype of the Spec (see "Interface tickets and the Prototype Fold") |
| `prototype` | all | optional, a non-empty string: the path (`chemin`) of the ticket's Validated Prototype as the Spec writes it. Required on every interface ticket, each Fold included, when the Spec names several (T46, af-lb9zkz) |

A `repair` restores something that already exists: the door reads each
citation against its source and refuses, naming the ticket and what it
cites, when the source does not hold it (Spec §2: a behaviour the Spec does
not require is never a repair, it is a Planning Exception).

| `restores.kind` | `ref` | Read against |
| --- | --- | --- |
| `user_story` | the number of exactly one story | the numbered user stories of the approved Spec |
| `spec_line` | a line, word for word | the text of the approved Spec |
| `anchor` (T40, af-o6tu3z) | the name of one anchor | the named anchors of every prototyped state of the Validated Prototypes the Spec names, read by `bin/prototype-conformance anchors` in the repository of the project at the commit of each reference (fetched from `origin` when absent). Refused when the Spec names no Validated Prototype, or when the prototype cannot be read |
| `repo_rule` (T40) | `<file path> : <the rule, word for word>` | the file at the tip of the integration branch of the convoy, in the repository of the project (of the protected branch at a first publication, before that branch is opened). Refused when the reference names no file, the file does not exist at that commit, or does not contain the citation |
| `red_check` (T40) | the name of the control | the red controls the convoy carries a record of (`convoy.red_checks` in `bin/convoy-state show`, `docs/CONVOY_STATE.md`). Refused when none bears that name — always at a first publication, which has no convoy yet |

A `repair` that restores a red of the mechanical fidelity (`red_check`
naming a recorded red whose `check` is `fidelity`) is an interface ticket,
as the repair of an anchor is.

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
under the approved digest. The field is required: a draft with no need
writes `operator_needs: []`, and a draft without the field is refused --
nothing else tells "no need" from "nobody thought of it".
The refusal reads `- brouillon : champ operator_needs absent : …` and says
to write the empty list.

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
draft declares only the needs its own changes bring -- an empty list when
they bring none; the field is required of a revision too.

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

## Interface tickets and the Prototype Fold (T36, T46)

The door reads in the approved Spec, through `bin/spec-approve outline`,
which user stories describe an interface (the `[interface]` tag
`spec-approve` already reads) and the reference of each of its Validated
Prototypes (branch, commit, path, states). An **interface ticket** is:

- a `vertical_slice` that covers an interface story;
- a `repair` that restores an interface story, an anchor, or a recorded
  red of the mechanical fidelity (T40);
- the Prototype Fold itself.

There is one Prototype Fold per Validated Prototype the Spec names (T46,
af-lb9zkz). A ticket says which prototype is its own with `prototype`, the
path (`chemin`) the Spec writes. With one Validated Prototype in the Spec
the field is optional and, if present, names that prototype. With several,
every interface ticket -- each Fold included -- carries it: the door refuses
one that does not, and any ticket whose `prototype` is the path of no
Validated Prototype of the Spec.

When the Spec names a Validated Prototype, the door refuses, before any
write, for each prototype:

- interface tickets of that prototype and no `vertical_slice` among them
  that declares `prototype_fold: true` -- the refusal, on `graphe`, names
  the Validated Prototype left without a Fold (path, branch, commit) and the
  interface tickets;
- when the Spec names several and the graph has any interface ticket, a
  prototype with no Fold at all, on `graphe` too: each has its own;
- more than one Prototype Fold for the same Validated Prototype;
- an interface ticket that does not wait for the Fold of its own prototype
  (`blocked_by`, directly or through other tickets) -- the refusal names the
  ticket; waiting for the Fold of another prototype does not count. So among
  the interface tickets of a prototype `bd ready` gives its Fold alone until
  it is closed.

Two cases need no edge to the Fold: a `repair` the Fold itself waits for
(code blocks a ticket behind the repair that unblocks it, so that repair
comes first by construction), and, on a patch, any ticket once the Fold is
closed -- a repair written at the end of the Spec has nothing left to wait
for.

`prototype_fold` is refused on a `prefactoring` or a `repair`, with any
value but `true`, and on a graph whose Spec names no Validated Prototype. A
Spec without interface is sliced without Prototype Fold; so is a Spec whose
interface stories have no Validated Prototype (all their states « non
prototypés »). The door does not check that the Fold's own criteria serve
every prototyped state: that is observed on the launched product, at the
end of the ticket.

## Pointers posed by the door (T06, T36)

The text of a published ticket is what the approved draft says of it, then
the sections the door writes itself -- none is ever written in the draft:

| Section | Content | Source |
|---|---|---|
| `## Spec` | the Spec bead id and its digest | the approved Spec bead |
| `## User stories` | number and text of the stories a slice covers, or of the story a repair restores | `user_stories` / `restores`, and the Spec text |
| `## Sibling tickets` | every other ticket of the graph: id, kind, title, demonstration line | the graph |
| `## Validated Prototype` | in an interface ticket only: `branche`, `commit`, `chemin`, `états` of the ticket's own Validated Prototype, then which ticket is the Prototype Fold of that prototype (« ce ticket », or its id and title) | the approved Spec text (`spec-approve outline`), the graph |
| `## Seams` | the entry points of the project profile, and the Spec's « Testing Decisions » (its numbered items, or its lines when none is numbered) | the profile, the Spec text |

After a patch, the tickets the revision does not carry keep their own text
and get these sections again, so a ticket names the siblings added since,
and an interface ticket the reference of a Spec amended and approved again.

The test method of a ticket is the « Testing Decisions » its Spec wrote,
posed under `## Seams`. Those of a Spec to come on the Factory's own
repository refer to `docs/TEST_GUIDELINE.md` (public interface, level,
decor, durations) instead of restating it (Spec CI01, af-q9urgr §3); for a
Spec of another project the guideline is not yet applied (af-8cfygl). The
door does not pose that reference itself: it copies what the Spec says.

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
| Prototype Fold | `gc.flow.prototype_fold` on each slice that is a Fold (one per Validated Prototype) | `bin/convoy-state mark --prototype-fold` |
| Integration branch of the Spec | `gc.flow.integration` on the convoy, and the branch `integration/<spec id>` in the project's repository | `bin/spec-integration open` |

Code reads them back with `bin/convoy-state show <convoy>`
(`docs/CONVOY_STATE.md`): `kind`, `mark`, `demonstration_line`,
`user_stories`, `establishes_launch_recipe` and `prototype_fold` per ticket.
Which Validated Prototype a ticket belongs to is no tracker field (T46): on
a patch the door reads it back from the `chemin` of the reference it posed
in the ticket's text, and does not freeze `prototype` separately.
The ticket text shows the same demonstration line, what a prefactoring
unblocks, what a repair restores, and each criterion as « Point d'entrée —
Observable — Faux si ».

The graph is created in one tracker transaction, then marked: tickets
first, the convoy last. If the marking fails, the door exits non-zero and
says the convoy is published but not marked; until then it reads as a
convoy of the old flow. Running the same command again resumes at the
marking and changes nothing else. The Mayor is not woken for a marked
convoy: code starts its tickets, not the Mayor (Spec §0 rule 3).

**The integration branch of the Spec (T18).** Once the convoy is marked, the
door opens the branch its tickets are merged into, `integration/<spec id>`,
at the tip of the protected branch, through `bin/spec-integration open`
(`docs/SPEC_INTEGRATION.md`); the result carries it under `integration`.
Where: the repository of the one rig the graph targets (`rig_dir` of
`<config-dir>/<rig>.toml`, under `--repo-root`) and its `protected_branch`.
This is checked before any write: a new-flow graph that targets several
rigs, a rig without such a project file, or a rig whose directory is not a
Git repository, is refused and nothing is written. If the branch cannot be
opened after the marking, the door exits non-zero and says so; the same
command again resumes there. Publishing again opens nothing more. A convoy
without the mark gets no branch and none of these checks. The patch door
opens nothing: the branch exists since the publication.

## The patch door (T06)

`bd-patch` on a draft that declares the contract revises a convoy published
under it. A revised draft carries the unfinished tickets it changes or
needs as blockers, and the tickets it adds; it never carries a closed
ticket. Everything above applies as it is to what the revision carries,
and the graph checks (coverage, launch recipe, Prototype Fold) to the graph that results:
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
- a published ticket whose kind, demonstration line, covered user stories,
  `establishes_launch_recipe` or `prototype_fold` differ from what `bin/convoy-state` holds:
  they are frozen with the approved graph, another one is another ticket.

**Repair without approval.** A revised draft that carries no approval
(`approved_by`, `approved_evidence`, `approved_digest` all absent) is
published only if it adds nothing but `repair` tickets -- each held to the
contract, so each naming what it restores -- to a graph it otherwise leaves
as published: the text of a carried ticket is unchanged, and it may only
gain an added repair among its blockers. A blocker that is already delivered
cannot be carried (a patch never takes a closed ticket), so leaving it out
is not a reordering: the ticket keeps it, in `gc.blocked_by` and as a
tracker edge, under an approved revision as well (T11: a ticket at work has
every blocker delivered, and `bin/ticket-exit` puts the repair of a ticket
blocked technically in front of it this way, `docs/TICKET_EXIT.md`). Anything else (an added slice, a
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
`bin/convoy-state`; the Mayor is not woken. An added ticket waits for each
ticket of its `blocked_by` in the tracker itself, as a published one does
(T48): the door creates it with `bd create --deps depends-on:<blocker>`.
`--deps blocks:<blocker>` is the reverse edge on bd 1.2.2 -- the blocker
would wait for the added ticket, which `bd ready` and `bin/convoy-advance`
would then start first; `gc.blocked_by` says the same thing as the edge,
and is not what they read. The same holds for a patch of the old flow. As
for a publication, a patch
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
`tests/ticket-graph-publish-citation-test.py` does the same for T40 on the
patch door, with a real repository: an anchor absent from or held by the
Validated Prototype, a prototype that cannot be read, a rule whose file is
missing at the commit of the integration branch or does not contain it, a
red control the convoy does or does not carry.
`tests/ticket-graph-publish-prototype-fold-test.py` does the same for T36:
an interface graph without Prototype Fold, an interface ticket that does
not wait for it, the reference read on each published interface ticket, a
Spec without interface, and the same rules on a patch; and for T46
(`SeveralValidatedPrototypesTest`, `SeveralValidatedPrototypesPatchTest`):
one Fold per Validated Prototype, a prototype left without Fold, a ticket
that waits for the Fold of another prototype or does not name its own.
`tests/ticket-graph-publish-new-flow-real-tracker-test.sh` (local-only)
replays refusal, publication, marking, pointers, an orphan story, an
operator need, the Prototype Fold (refusals, reference shown by `gc bd
show`, the Fold alone given by `bd ready` among the interface tickets until
it is closed), a repair added by patch without approval, a withdrawal and
the undeclared case on the real `gc`/`bd` in a disposable city.
`tests/ticket-graph-publish-patch-edges-real-tracker-test.sh` (local-only,
T48) proves the sense of the blocking edges there, on both flows: a ticket
added behind another waits for it, `bd ready` gives the blocker alone, a
pass of `bin/convoy-advance` leaves the blocked repair waiting, and it is
ready once its blocker is closed. In CI the same is asked of the fake
tracker (`test_added_repair_waits_for_the_added_ticket_that_blocks_it`,
`test_bd_patch_added_ticket_waits_for_its_blocker`), and
`tests/fake-tool-contract-test.py` (local-only) runs that fake beside the
real `bd` to prove both pose each dependency the same way round.
