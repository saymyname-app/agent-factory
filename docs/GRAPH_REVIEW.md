# Graph review before Benjamin's approval (T08, Spec af-wf4w5r §2)

## Status and purpose

A Ticket Graph Draft that declares the new-flow contract (`flow_contract:
new-flow/v1`, `docs/ENTRY_CONTRACT.md`) is read by a **graph reviewer**
before Benjamin approves it: a session of the read-only reviewer role, in a
fresh context, that did not write the graph. It answers closed questions per
ticket and on the graph; code computes the verdicts and binds them to the
digest of the draft. `bin/ticket-graph-publish bd-publish` refuses a draft
without a review that holds for its current digest, and so does `bd-patch`
for an approved revision of a published graph (af-8mbftn): the revision is
reviewed, critical path included (ADR-0031), before it reaches the convoy.
A revision that only adds `repair` tickets, drafted and published by code
without approval, is not reviewed.

`bin/graph-review` is the only reader and writer of that state. A draft that
does not declare the contract is not touched (exit 4) and is published
exactly as before.

```bash
./bin/graph-review review af-draft --author-model claude-opus-5-5   # the /to-tickets session, before approval
./bin/graph-review remaining af-draft --text                         # what Benjamin rules on, as he reads it
./bin/graph-review decide af-draft --ticket T07 --decision publish \
  --approved-by benjamin-hurand --project agent-factory \
  --words "T07 reste ainsi : …"                                      # his exact words, one ticket at a time
./bin/graph-review check af-draft                                    # the publication door
./bin/graph-review show af-draft                                     # every pass, request and decision
./bin/graph-review brief af-draft                                    # the reviewer session (formula mol-graph-review)
./bin/graph-review record af-draft --verdict-file verdict.json       # the reviewer session
```

Every answer is one JSON object on stdout; `remaining --text` prints the
list in the Operator Language.

| Exit | Meaning |
|---|---|
| 0 | done |
| 1 | refused, or could not run: nothing was written (`{"ok": false, "error": "refus : …"}`, the same text on stderr) |
| 4 | the draft does not declare the new-flow contract: « pas un brouillon du nouveau flux » |
| 5 | a third pass was asked: refused, with the remaining refusals |

## The sequence

1. **First pass.** The `/to-tickets` session runs `review` with the model it
   runs on (`--author-model`). The command opens the pass, creates a review
   bead and routes it through `bin/dispatch-door --role reviewer` on the
   formula `mol-graph-review`; a new session of the reviewer role claims it,
   asks `brief`, answers, and hands its answers to `record`. `review` waits
   (`--timeout`, default 1800 s) and prints the verdicts and the refusals.
2. **Corrections**, with Benjamin, in the draft. Any change gives the draft
   another digest: the verdicts of the first pass no longer hold for it.
3. **One second pass**, the same command, on the corrected draft.
4. **Benjamin rules.** What the second pass still refuses is listed by
   `remaining`. He rules ticket by ticket (and on the graph, `--graph`, when
   the refusal is on the graph): `publish` (« publier tel quel ») or `rework`
   (« à reprendre »), each with his words. There is no third pass: `review`
   refuses it (exit 5) and prints that list.
5. **Approval and publication.** Benjamin approves the draft as before; the
   publication door then asks `check`.

A review that returns no verdict (the door refused the dispatch, the session
died, the timeout passed) is not a passed one and counts no pass: the command
exits 1 and the same pass can be asked again.

## The closed questions

The reviewer gives one state per question, `favorable` or `unfavorable`; an
unfavorable answer carries a reason. It gives no overall verdict: a ticket,
or the graph, is `unfavorable` as soon as one of its answers is.

| On | Question | Asks |
|---|---|---|
| ticket | `demonstrable_alone` | once this ticket and its blockers are merged, and nothing later, its demonstration line is observed on the launched product |
| ticket | `criteria_observable_falsifiable` | every criterion is an observation through a public interface, with what would make it false |
| ticket | `size_tenable` | one author session can deliver it |
| ticket | `same_surface_ordered` | every other ticket that changes the same code or the same mechanism is ordered against it; the same screen alone is no dependency (ADR-0031) |
| ticket | `declared_scope_includes_wiring` | the declared `scope.paths` include the files where the slice is wired in. Asked only of a ticket that declares a scope; code records `not_applicable` otherwise |
| graph | `no_orphan_story` | every numbered user story of the Spec is covered by a ticket. Not asked of a revision (`revises_digest`): it carries only the tickets it changes, so code records `not_applicable` and `bd-patch` computes coverage on the resulting graph before it asks `check` (af-2zmznz) |
| graph | `assembly_point_not_confiscated` | the ticket that establishes shared assembly points is ordered first; none keeps the wiring for itself |
| graph | `prototype_fold_present_and_first` | a Prototype Fold exists and every other interface ticket depends on it; `not_applicable`, with a reason, when the graph has no interface ticket |
| graph | `critical_path_bounded` | **answered by code, never by the reviewer**: the longest chain of `blocked_by` is at most max(4, ⌈n/3⌉) of the draft's n tickets; the reason names the chain and every link another link already implies (ADR-0031) |

`brief` does not ask `critical_path_bounded`; `record` computes it on the
draft and a reviewer answer to it is refused as outside the list. An
unfavorable measure is a graph refusal like the others: correct the draft
(keep a link only where the blocked ticket consumes a deliverable its text
cites), ask the second pass, or let Benjamin rule `--graph`.

`record` refuses, before any write and with every reason listed: a verdict
on another digest than the draft's; a ticket of the draft without answers, or
a ticket the draft does not have; a question left unanswered or outside the
list; a state outside the list; an unfavorable answer without a reason; a
verdict handed in outside a read-only reviewer session
(`bin/delivery-role-sandbox`); a verdict when no pass is open, or when the
draft changed since the pass was opened.

## What the publication door refuses

`check` passes only when the last recorded pass holds for the draft's
current digest and leaves nothing undecided. It refuses, and the door
writes nothing:

- no recorded pass;
- a draft whose digest is no longer the one the last pass was given on;
- a first pass with refusals (correct, then ask the second pass);
- a refusal of the second pass without a decision of Benjamin;
- a refusal of the second pass he ruled `rework`.

A decision is bound to the digest it was taken on, like the verdicts. Once
the two passes are spent, a draft that changes again cannot be reviewed a
third time: the corrected graph is a new draft bead, with its own review.

On a pass, the door's result carries `graph_review`: the pass, the digest,
`same_model`, and Benjamin's decisions with his words.

## Model independence

The Spec asks for a reviewer of another model than the one that wrote the
graph. The command compares the model the caller declares
(`--author-model`, required) with the model of the provider the reviewer
role runs on right now (`bin/provider-failover` for the role's agent, then
that provider's `--model` in `city.toml`, else `config/model-catalog.json`).
Spelling, case and punctuation are ignored.

When they are the same, the review still runs and is **flagged, never
silent**: `same_model: true` is stored with the verdicts, and
`model_independence` says « relecture non indépendante… » in the output of
`review`, of `remaining` (text included), of `check` and of the publication
door. With one Anthropic account and a reviewer role tried on Claude only
(`config/provider-policy.json`), a graph written by a Claude session is
flagged this way until the reviewer role is tried on another provider
(`bin/role-adoption-trial`). A review whose author model is not declared, or
whose reviewer model cannot be read, is refused.

## Stored state

On the draft bead, written by this command only:

| Key | Value |
|---|---|
| `gc.graph_review.request` | the pass that is open: number, digest, author model, reviewer agent, provider and model, `same_model` |
| `gc.graph_review.pass.1`, `.pass.2` | a recorded pass: the request, who recorded it and when, the answers and computed verdict of each ticket and of the graph |
| `gc.graph_review.decisions` | per ticket (or `graphe`): `decision`, `words`, `by`, `at`, `digest` |

These keys live on the draft, not under `gc.flow.*`: `bin/convoy-state`
(`docs/CONVOY_STATE.md`) owns the state of a marked convoy, and no convoy
exists before publication. The draft bead stays readable through delivery;
its convoy names it (`gc.artifact_id`).

## Limits

- The author model is declared by the session that asks for the review, and
  the reviewer model is the configured one, not one observed in the session.
- `decide` refuses anyone but the project's declared human approver and
  refuses empty words, as `bin/spec-approve` does; nothing technically stops
  an agent from typing Benjamin's name and words. The record makes it
  visible afterwards (Spec §11, same limit).
- `record` checks that it runs in a read-only role session
  (`DELIVERY_ROLE_READ_ONLY`, set by `bin/delivery-role-sandbox`), not which
  session it is.
- The questions are judged by an agent. Code bounds the answers (closed
  lists, reason required, verdict computed, digest bound); it does not check
  that a reason is true.

## Proof

`tests/graph-review-test.py` drives `bin/graph-review` and the publication
door on a fake tracker state: one test per pass and per refusal, each
refusal re-reading the tracker to prove nothing was written. No agent runs
in CI: `tests/fixtures/graph-review/reviewer` stands in for the dispatch
door and the reviewer session. `tests/graph-review-isolated-city-test.sh`
(local-only) replays the state, the refusals and the publication on the real
`gc`/`bd` in a disposable city and, with `GRAPH_REVIEW_TRIAL_SESSION=1`, has
one real reviewer session review the fixture draft in which a ticket is not
demonstrable alone (`tests/fixtures/graph-review/not-demonstrable-draft.yaml`).

That real session is what showed that a read-only role could not run any
`gc` command: `gc` takes a lock in its pack cache
(`$GC_HOME/cache/repos/.packman-cache.lock`) before it reads the city, and
`bin/delivery-role-sandbox` mounted it read-only. The sandbox now leaves
that one file writable; the cached packs beside it stay read-only. Trial
record of 2026-10-06 (Gas City 1.4.1): the session claimed the routed step,
recorded its answers itself, and refused T2 as not demonstrable alone.

## Shared role aliases

A fresh role session may reuse `delivery-reviewer` as its alias. Historical
work assigned to that alias belongs to the session recorded in `gc.session_id`,
not every later seat using the alias. The delivery roles restrict alias-history
reads to that exact session id while preserving their own workflow affinity.
This also applies to authors and evaluators. An old completed review cannot
make a new review disappear from its session's claim query (af-wet0sq).

## Delegated derivation (AR-039)

Under `PLANNING_DELEGATION.md`, technical corrections run without Benjamin;
the two-pass limit and existing independent reviewer remain. For a
derived graph, the verdict also freezes the source Spec digest: changing
that Spec invalidates the review even when graph text stays identical. One draft is
bound to the source authorization, so another draft cannot reset its review
budget. The delegated publication path accepts no override of an unfavorable
review. Exhaustion triggers bounded technical diagnosis; a new product
choice is shown to Benjamin concretely. Human-led approvals above remain.
