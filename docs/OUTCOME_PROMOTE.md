# After Benjamin's answer: the one merge and the closing of the convoy (T30, Spec af-wf4w5r §9 and §11)

## What it is for

A convoy that carries the **new-flow mark** delivers its Spec on one
integration branch; the protected branch receives nothing of it while the
Outcome is delivered, judged, returned or repaired
(`docs/SPEC_INTEGRATION.md`). Benjamin's answer is recorded by
`bin/owner-answer` (`docs/OWNER_ANSWER.md`), which merges and closes
nothing. `bin/outcome-promote` is **what code does once that answer is
« accepté » or « abandonné »** (user stories 72 and 73). The rules it holds:

- **No merge into the protected branch without an « accepté »** recorded
  for the tip of the integration branch.
- **One merge commit**, whose parents are the tip of the protected branch
  and the tip of the integration branch. Nothing else of the convoy ever
  reaches the protected branch.
- **The two commits are kept**: the one Benjamin judged and the one the
  protected branch received, on the convoy and beside the dossier he judged.
- **A protected branch that moved since the judgement is taken up first**,
  and only the mechanical controls are replayed on the result. Red, or in
  conflict: nothing is merged, the acceptance is voided, and the Outcome
  goes back through the end of its Spec to a new Acceptance Request.
- **« abandonné » merges nothing**: the convoy is closed with the reason,
  the integration branch stays where it is, as a source.
- **The convoy is closed by code, on his words**, and nothing reopens it:
  neither the convoy nor its tickets. A defect or a wish found afterwards is
  new work, through a Planning Run.
- **No agent merges or closes**: only the order of the Factory runs it.

Everything is written through `bin/convoy-state`, in two convoy fields,
`gc.flow.promotion` and `gc.flow.closed` (`docs/CONVOY_STATE.md`, « The
promotion and the closing »).

A convoy **without** the mark is not concerned: both commands answer « pas
un convoi du nouveau flux » (exit 4) and write nothing.

## The commands

```bash
./bin/outcome-promote run   af-convoy [--repo DIR] [--profile FILE] [--timeout S]   # follows the recorded answer; refused from an agent session
./bin/outcome-promote check af-convoy [--repo DIR]                                  # what run would do; reads only
```

The project is the single one the convoy's first ticket names under
« Target rigs »; `--repo` defaults to its `rig_dir`
(`config/projects/<rig>.toml`), `--profile` to the descriptor of
`config/project-descriptors/` whose `rigs` names it. `--timeout` (default
900 s) is handed to the replay of the mechanical controls.

**`check`** answers `due` — `merge` (an « accepté » stands and no merge is
recorded), `close` (an « abandonné » stands, or the merge is recorded and
the convoy is still open) or `nothing` (no answer that ends the judgement,
or a convoy already closed) — with `response`, `outcome`, `promotion` and
`closed` as `bin/convoy-state show` renders them.

**`run`** reads the last answer of `convoy.judgement`. It is followed when
it is « accepté » or « abandonné » and no red replay voided it.

Every answer is one JSON object on stdout. **Exit codes**: 0 done, or
nothing left to do; 1 refused, or red (`error` starts with `refus : `; a
red also carries `red`, the record of the red control, and `cause`); 3 the
convoy is in an « état sans règle » (`unruled` carries the anomalies;
nothing is merged or closed on such a convoy); 4 the convoy does not carry
the mark.

## What « accepté » leads to

1. **The branches are read** on the remote `origin` when the repository has
   one (after a `git fetch`), else in the local branches. The integration
   branch and the protected branch are the ones recorded on the convoy
   (`convoy.integration`).
2. **The tip must be the accepted commit**: the commit of the answer, or
   that commit taken up by this command (a merge whose first parent is the
   accepted commit and whose second is in the protected branch). Any other
   tip is refused.
3. **The protected branch did not move** (the integration tip holds its
   tip): nothing is replayed, step 6 follows.
4. **It moved.** The two tips are first tried against each other
   (`git merge-tree`): a conflict is a red of cause `conflict`. Otherwise
   `bin/spec-end replay` takes the protected branch up in the integration
   branch and replays, on that one tip, the regression command of the
   profile and the mechanical fidelity to the Validated Prototype
   (`docs/SPEC_END.md`, « After « accepté »: `replay` »). No judged
   condition is read again — neither the Outcome Evaluation nor the end
   code review — and no round of the end is counted.
5. **The product is started** from a clean copy of the new tip, by the
   recipe of the profile, once per synthetic dataset, and stopped
   (`bin/project-launch start --commit`, two attempts of 30 s each).
6. **Green: one merge commit** is created (`git commit-tree`: the tree of
   the integration tip, parents the protected tip then the integration tip)
   and the protected branch is moved to it, and only from the tip that was
   read: `git push --force-with-lease=<branch>:<old tip>` on a repository
   with a remote, `git update-ref <branch> <new> <old>` without one. Its
   message names the Spec, the convoy, the judged commit, the integration
   tip, and the approver with his words.
7. `bin/convoy-state record-promotion` records the promotion: `judged`,
   `merged`, `protected` (the tip of the protected branch before the merge)
   and `tip` (the integration tip that was merged).
8. `bin/evidence-pack promoted` writes `fusion.html` beside the `index.html`
   Benjamin judged, which keeps its bytes and its fingerprint
   (`docs/EVIDENCE_PACK.md`).
9. `bin/evidence-capture purge --spec <spec>` removes the evidence store of
   the Spec (`docs/EVIDENCE_STORE.md`); `purged` is the number of pieces
   removed.
10. `bin/convoy-state close-convoy` closes the convoy: the closed status
    and `gc.flow.closed` (`how: accepted`, his words, the approver) in one
    tracker write. `bin/convoy-state show` then renders `outcome:
    accepted`.
11. `bin/planning-artifacts-close` closes the Spec and the Ticket Graph
    Draft the convoy was published from.

The answer is `{promoted: true, merged, judged, closed: true, how, said,
outcome, promotion, purged}`.

### Red, or in conflict: nothing is merged

| Cause (`cause`) | What was found | The red is recorded by |
| --- | --- | --- |
| `conflict` | the protected branch and the integration branch do not merge; `detail` names the files | `bin/outcome-promote` (`record-integration-red`) |
| `regression` | the regression command is red on the take-up | `bin/spec-integration take-up`, called by `replay` |
| `fidelity` | a deviation from the Validated Prototype is open on the take-up | `bin/spec-end replay` (`--check fidelity`) |
| `start` | the product does not start from a clean copy of the take-up | `bin/outcome-promote` (`record-integration-red`) |

In each case `bin/convoy-state void-acceptance --cause <cause>` then
writes, in one tracker write: `voided: {cause, at}` on the « accepté »,
which stays in the judgement; `gc.flow.delivered`, `gc.flow.acceptance` and
`gc.flow.end_round` withdrawn; `gc.flow.counter.end_rounds` set to 0. The
answer is exit 1 with `promoted: false`, `merged: null`, `closed: false`,
`cause`, `red` and:

> refus : après « accepté », <contrôle> ; rien n'est fusionné vers la
> branche protégée ; l'acceptation est annulée, un repair suit, puis la
> porte de fin de Spec et une nouvelle demande d'acceptation

What follows is the unchanged flow. The integration branch is red: the pass
of `bin/convoy-advance` publishes its one `repair` through the patch door
and starts nothing else (`docs/CONVOY_ADVANCE.md`, « The two stops of a
convoy »); once it is delivered, the whole end-of-Spec gate runs at the new
tip — mechanical verdicts, a fresh Outcome Evaluation and end code review,
a new Evidence Pack — then Delivered and a **new Acceptance Request**.
Benjamin answers again with `bin/owner-answer`: a voided « accepté » is not
an answer that ends the judgement.

## What « abandonné » leads to

`bin/convoy-state close-convoy` closes the convoy with `how: abandoned` and
the reason he gave; `bin/planning-artifacts-close` closes its Spec and its
draft. **Nothing is merged and no branch is fetched or moved**: the
integration branch keeps its tip, as a source for later work. No promotion is recorded,
no `fusion.html` is written and the evidence store of the Spec is not
purged. The answer is `{promoted: false, merged: null, closed: true, how:
abandoned, said, outcome: abandoned, withdrawn}`.

An abandon recorded during delivery (`in_flight`, `docs/OWNER_ANSWER.md`)
leaves tickets that are not closed. Before the closing, each of them gets
the gate record `withdrawn` (`bin/convoy-state record-gate`) and is closed
with the reason in its notes, as `bin/ticket-graph-publish` withdraws a
ticket; `withdrawn` names them (empty after a Delivered Outcome, whose
tickets are all closed). Their branches and their beads stay. A run
interrupted between two tickets is taken up by the next one, which also
closes a ticket that already carries its record.

## Refusals

| Command | Refused when | Written |
| --- | --- | --- |
| `run` | called from an agent session: one of `GC_AGENT`, `GC_SESSION_NAME`, `GC_SESSION_ID` is set | nothing |
| `run` | neither « accepté » nor « abandonné » stands on the convoy (no answer, « constats rendus », or an « accepté » that was voided) | nothing |
| `run` | the tip of the integration branch is neither the accepted commit nor this command's own take-up of it | nothing |
| `run` | the convoy has no recorded integration branch; its tickets name no single project of `config/projects`; no descriptor covers the rig or it declares no launch recipe; a branch cannot be found; `git fetch` fails | nothing |
| `run` | the mechanical controls could not be replayed (a refusal of `bin/spec-end replay` that carries no red) | nothing by this command |
| `run` | a branch moved while the controls were replayed | nothing more; the next pass starts over |
| `run` | the protected branch did not take the merge (the lease no longer holds, or the remote refuses the push) | nothing: « l'Outcome reste accepté et non fusionné ; la prochaine passe réessaie » |
| `run` | the merge is recorded but `fusion.html` or the purge failed | the promotion stays recorded, the convoy stays open |
| both | the convoy is in an « état sans règle »: exit 3, not a refusal | nothing |

Refused by `bin/convoy-state` itself, whoever calls it: `record-promotion`
without an « accepté » that stands, for another commit than the accepted
one, or a second time; `void-acceptance` without an « accepté » that
stands, once the promotion is recorded, or with a cause outside the list;
`close-convoy` without an answer that ends the judgement, on an accepted
convoy whose merge is not recorded, on an abandoned convoy that carries a
merge, or on a convoy already closed outside the command.

## Nothing reopens a closed convoy

Once `close-convoy` has written, **every write of the flow on that convoy
and on its tickets is refused** by `bin/convoy-state` (`mark` included; the
record of a factory incident and of a grouped request apart), and
`bin/owner-answer verdict`, `record` and `resolve-exception` refuse before
it:

> refus : l'Outcome du convoi <id> est accepté et son convoi est fermé :
> rien ne le rouvre, ni lui ni ses tickets ; un défaut ou un souhait trouvé
> après entre comme travail nouveau, par un Planning Run

A convoy reopened by hand after its closing, or closed by hand whatever
answer it carries, is an « état sans règle » (`docs/CONVOY_STATE.md`).

## Interrupted runs and retries

`run` is made to be run again: each pass of the order calls it while an
answer that ends the judgement stands.

| Where the run stopped | What the next run does |
| --- | --- |
| after the take-up was pushed, before the merge | the tip is this command's own take-up and holds the protected tip: step 6 follows (see Limits) |
| after the protected branch took the merge, before `record-promotion` | the merge is recognised — the protected tip is a merge whose second parent is the integration tip — and recorded; nothing is merged twice |
| after `record-promotion` (`fusion.html` or the purge failed, exit 1) | `resumed: true`: the note and the purge are done again, then the closing. The convoy **stays open** until both are done |
| after `close-convoy`, the Spec or the draft not closed | exit 0 with `pending: ["Spec et brouillon : …"]`; `orders/planning-artifacts-close.toml`, which runs on every `bead.closed`, takes it up, and so does the next `run` |
| the convoy is closed by command | `done: true`: nothing is merged, nothing is written on the convoy; only `bin/planning-artifacts-close` is run again |

`fusion.html` written again is the same page (`written: false`).

## State written

| Where | What | By |
| --- | --- | --- |
| the project repository | the take-up of the protected branch in the integration branch, when it moved | `bin/spec-integration take-up`, called by `bin/spec-end replay` |
| the project repository | one merge commit on the protected branch | `bin/outcome-promote` |
| `gc.flow.spec_end` | the three mechanical verdicts on the take-up, when it was green; that write withdraws `gc.flow.delivered`, tied to the judged commit | `bin/spec-end replay` |
| `gc.flow.integration_red` | the red control, when there is one | see « Red, or in conflict » |
| `gc.flow.judgement` | `voided: {cause, at}` on the « accepté » | `bin/convoy-state void-acceptance` |
| `gc.flow.promotion` | `{judged, merged, protected, tip, at}` | `bin/convoy-state record-promotion` |
| `gc.flow.closed` and the status `closed` | `{how: accepted\|abandoned, said, approver, at}` | `bin/convoy-state close-convoy` |
| `<packs>/<spec>/<convoy>/<judged commit>/fusion.html` | the note of the merge | `bin/evidence-pack promoted` |
| the evidence store of the Spec | removed | `bin/evidence-capture purge --spec` |
| the Spec bead and the Ticket Graph Draft bead | closed, with a reason naming the convoy | `bin/planning-artifacts-close` |

## Who runs it

**The order of the Factory, through `bin/convoy-advance`**
(`orders/convoy-advance.toml`): once an « accepté » or an « abandonné »
stands, the pass calls `outcome-promote run <convoy> --repo <rig_dir>`
first and renders nothing else on that Outcome — the end of the Spec is not
run again on a commit Benjamin judged. Its result is the key `promotion` of
the convoy's entry (`docs/CONVOY_ADVANCE.md`, « After Benjamin's answer »).
A red is an outcome of the pass, which publishes the `repair` of that red
itself; a refusal, an « état sans règle » or a `pending` makes the pass
exit 1, and the next one tries again.

**Never an agent.** Gas City exports `GC_AGENT`, `GC_SESSION_NAME` and
`GC_SESSION_ID` into every agent session, the Mayor's included, and into
none of the controller's orders (`docs/CONVOY_ADVANCE.md`, « Who may start
a ticket of a marked convoy »): `run` refuses when one is set. Recording
Benjamin's words is the operator session's work (`bin/owner-answer`);
following them is not.

## Environment

| Variable | Default | Used for |
| --- | --- | --- |
| `FACTORY_ROOT` | the parent of `bin/` | `config/projects/<rig>.toml`, the project's `rig_dir`, `config/project-descriptors/` |
| `GC_BIN` | `gc` | reading the first ticket (`gc bd show`) |

## Proof

- `tests/outcome-promote-test.py` (fake tracker, Delivered Outcome of the
  delivery fixture in a throwaway repository with its own remote, about
  2 min 20): nothing of the convoy in the protected branch before
  « accepté », then one merge and the convoy closed; `fusion.html` with the
  two commits and the judged page byte for byte; the Spec and the draft
  closed and the evidence store purged; a protected branch that moved taken
  up, the controls replayed green and both commits kept; red controls and a
  conflict merging nothing and voiding the acceptance, and Benjamin
  answering again; « abandonné » closing with its reason, nothing merged,
  the branch left; no merge without an « accepté », nor of a tip that is
  not the accepted commit; an agent session refused; a convoy without the
  mark; a second run that writes and merges nothing; the commands of the
  flow refusing to reopen an accepted Outcome.
- `tests/convoy-close-test.py` (fake tracker, about 1 min):
  `record-promotion`, `void-acceptance` and `close-convoy` with each
  refusal; a convoy closed by command ruled, one closed or reopened by hand
  not; no write of the flow on a closed convoy or on its tickets.
- `tests/owner-answer-promotion-fixture-city-test.py`, class
  `PromotionOnTheFixtureCity`: on the graph of the Fixture City, with the
  real passes — the protected branch holds nothing of the convoy before
  « accepté », then one merge and the convoy closed; an abandoned convoy
  closed with its reason, the protected branch unmoved; a protected branch
  in conflict after « accepté » merging nothing, the pass publishing one
  `repair` (`docs/FIXTURE_CITY_ORACLE.md`).
- `tests/convoy-manual-lifecycle-isolated-city-test.sh` (local-only): under
  the real controller, orders and tracker, `close-convoy` on « abandonné »
  and on « accepté » — the status and the record in one `gc bd update`, the
  convoy listed as closed by command and ruled, every later write refused,
  the city's own order closing its Spec and its draft, no pass naming it
  any more. The judgement and the promotion are written by hand there; no
  merge is made.

## Limits

- **On a repository with a remote the merge is a direct push to the
  protected branch**, protected by a lease on the tip that was read, not a
  pull request. A branch protection that refuses it leaves the Outcome
  accepted and unmerged: every pass tries again, exits 1 and says so, and
  nothing else reports it. The remote is `origin`; no other name is read.
- **Without a remote the branch is moved by `git update-ref`**: a working
  tree that has the protected branch checked out is not refreshed: its
  files stay those of the tip before the merge until it is reset.
- **A run interrupted between the take-up and the end of the replayed
  controls merges at the next run without them.** Once the take-up is
  pushed the integration tip holds the protected tip, and the next run
  reads that as « did not move »: the fidelity and the start that had not
  been replayed yet are not. The regression command was green on that tip
  (the take-up is pushed only then).
- **The replay runs inside the pass of the order**, whose timeout is 300 s
  (`orders/convoy-advance.toml`); the regression command, the fidelity of
  every screen and the start may take longer (same limit as the end-of-Spec
  gate, `docs/SPEC_END.md`), which is how the interruption above happens.
- **A registry condition that refuses at replay** (condition 1 of the
  end-of-Spec gate, read again before the take-up) is a refusal at each
  pass, with no red and no repair.
- **Nothing tells Benjamin that his acceptance was voided** when it
  happens: no request is raised for it. The `repair` of the red is
  published, and a new Acceptance Request arrives once the Outcome is
  Delivered again; its dossier has no rubric that says the earlier
  « accepté » was voided — the cause is in `convoy.judgement` only.
- **The Cockpit does not read the closing.** It reads the last answer
  (`docs/COCKPIT.md`): a convoy closed on « abandonné » is shown as
  delivered and waiting for Benjamin, with an « Accepter » whose click is
  refused; nothing there says « abandonné ».
- **The start is tried, not judged**: the product answers its health probe
  and is stopped. No Outcome Evaluation and no end code review is made on
  the take-up; what the protected branch brought is covered by the
  regression command and the fidelity only.
- **`bin/planning-artifacts-close` is run without a convoy**: it closes the
  Spec and the draft of every closed convoy that still has them open, as
  its order does.
- **The Evidence Pack is not purged**, only the evidence store: the pages
  stay in their folders, and the pieces they show are their own copies.
- **The refusal of an agent session is a guard on the honest path**: an
  agent with a shell can unset the three variables, or push to the
  protected branch itself. The record makes it visible afterwards — a merge
  no promotion names, a convoy closed outside the command.
- No isolated-city trial runs a merge, and no real convoy was promoted.
