# The single correction round, the stop of a ticket, the override (T17, Spec af-wf4w5r §8)

## Status and purpose

A finished ticket of a convoy that carries the **new-flow mark** is reviewed
(`docs/CODE_REVIEW.md`) and evaluated on the launched product
(`docs/TICKET_EVALUATION.md`) in parallel, on the same tip. What happens when
one of them refuses is held here, by code:

- **One correction round per ticket**, common to the code review and the
  Ticket Evaluation. It is opened once both have answered at the tip, and it
  goes to **one fresh author session**, which receives every finding of both.
- **It counts among the resumes** of the ticket (`resumes`,
  `correction_rounds`).
- **Still refused after that round, the ticket stops**: no second round
  starts, nothing of it is merged, and it is raised to the operator **once,
  as one item**, whatever refused it.
- **On a stopped ticket**, the declared human approver of the project may
  **override a Blocking Finding of the code review**, with their words; it is
  then read as « dérogation enregistrée ». **A criterion that was not
  observed is never waived**: the command refuses it and names the Planning
  Exception.

`bin/correction-round` holds it. Its state lives in the tracker, read and
written through `bin/convoy-state` only. A convoy without the mark is not
touched (exit 4).

```bash
./bin/correction-round settle   af-convoy [--repo <project repository>]   # bin/convoy-advance, at each pass
./bin/correction-round brief    af-convoy af-t1                           # the author session of the round (formula mol-ticket-correction)
./bin/correction-round override af-convoy af-t1 --finding F1.1 --approved-by <human approver> --words "…"   # the operator, on a stopped ticket
./bin/correction-round show     af-convoy af-t1                           # the round, the overrides, the stop, the counters
```

Every answer is one JSON object on stdout.

| Exit | Meaning |
|---|---|
| 0 | done |
| 1 | refused, or could not run (`{"ok": false, "error": "refus : …"}`); `settle`: a ticket was refused (listed under `refused`) |
| 4 | the convoy does not carry the mark: « pas un convoi du nouveau flux » |

## When the round is opened

`settle` decides from the tracker and the ticket branch alone, ticket by
ticket, after `bin/code-review settle` and `bin/ticket-evaluation settle` of
the same pass. It reads, at the tip of the ticket branch, what each of the
two controls says:

| Control | `accepted` | `refused` | `pending` |
|---|---|---|---|
| code review | last round favorable at the tip | an unfavorable review at the tip (its Blocking Findings), or answers judged unfavorably | a round open, none yet, or one at an older commit: `bin/code-review` replays it at the tip, an unfavorable one too while no round is taken (af-s31cvi) |
| Ticket Evaluation (for a `prefactoring`, the startup control) | last round favorable at the tip | `return_to_author` at the tip (what was not observed, or a product that does not start) | open, none at the tip, an outage, or an unobservable criterion (a Planning Exception, `docs/TICKET_EVALUATION.md`) |

| At the tip, no round taken yet | What `settle` does |
|---|---|
| both accepted | nothing: the merge may follow |
| one refused, the other pending | **waits** (`waiting`): one session receives every finding, so the round is not opened on half of them |
| one or both refused, none pending | opens the round at the tip (`bin/convoy-state open-correction`) and sends it to one author session |
| the ticket is not finished and green at the tip, is parked, stopped, closed or merged | nothing |

Opening writes, in one tracker write: the round — the commit both answered
at, the Blocking Findings of the review, the states the evaluation did not
observe — and one more `resumes` and `correction_rounds`. A second call on
the same state does nothing.

## The author session of the round

The round is sent as a bead of its own, routed through `bin/dispatch-door
--role author` on the formula `mol-ticket-correction`
(`config/delivery-flow.json`, `correction`). There is **one launch**: a
launch the door defers is retried by the next pass and counts nothing; a
launch the door refuses fails `settle` (exit 1); once a session was sent, no
other one ever is.

The session is new — not the one that wrote the ticket. It takes the ticket
with `bin/ticket-author start` (the session is recorded on the ticket, the
work tree is the one of the ticket branch) and reads `brief`, which is
everything both controls hold against the ticket:

| Field | Content |
|---|---|
| `commit`, `branch`, `tip`, `repo` | the commit both controls answered at, and where the ticket lives |
| `code_review.blocking_findings` | each Blocking Finding: `id`, `axis`, `summary`, and the `citation` (or the closed `question`) it rests on |
| `code_review.non_blocking_findings` | the findings recorded without blocking, for information |
| `code_review.respond`, `response_shape` | how each Blocking Finding is answered (`bin/code-review respond`) |
| `evaluation.not_observed` | each criterion, or the demonstration line, that was not observed: `what`, its `text`, the `reason` of the Evaluator and the `evidence` piece |
| `round`, `counters` | that this is the only round, and the counters of the ticket |

It corrects, proves the ticket green again at the tip (`bin/tdd-step`),
demonstrates it again (`bin/ticket-author demonstrate`), answers every
Blocking Finding « corrigé » or « contesté » (`bin/code-review respond`), and
leaves by the Ticket Exit « terminé » (`bin/ticket-exit`). What it says
closes nothing: code decides what follows.

Intent (Benjamin, his words, 2026-10-21 about 03:45 Paris): « Oui, maintenance
(Recommandé) », to the question « Je corrige aussi la règle d usine pour les
prochains tickets : un constat de revue sur un test gelé, quand l amendement
est déjà utilisé, ne peut plus mener qu à un arrêt. On la corrige ? ».
Mechanism (agent interpretation): a Blocking Finding that asks to change a
frozen test is corrected by `bin/tdd-step amend`, and the round opened after
the ticket's amendment allows one amendment more, once, not bounded to the
files the findings name (a finding cites a line, not a test file); a further
one stops the ticket `amendment_exhausted` (af-vsni1n, `docs/TDD_STEP.md`).

## After the round

| State at the tip, the round taken | What `settle` does |
|---|---|
| the author session is at work (its bead is open): the ticket is not finished at the tip, a Blocking Finding has no answer, or the evaluation refused at the commit of the round | waits (`pending`) |
| the answers wait for their judgement, or the ticket waits for its evaluation at the new tip | waits (`pending`): `bin/code-review` sends the judgement to a second reviewer session, `bin/ticket-evaluation` evaluates the new tip |
| both accepted at the tip | nothing: the merge follows, whatever the fidelity (below) |
| a review judgement or replay blocks, or an evaluation remains not observed at the new tip, even while the other control is pending | **stops the ticket**; the pending control cannot lift the stop |
| the author session ended (its bead is closed) without finishing the ticket at the tip, or leaving a Blocking Finding unanswered or the refused evaluation as it was | **stops the ticket** |

**A red fidelity never stops a ticket** (ADR-0032, af-hcriwn, 2026-10-19;
it replaced af-ckbood). The fidelity to the Validated Prototype is still
measured at the tip (`bin/ticket-end fidelity`) and joined for the visual
finishing pass Benjamin judges at the end of the Spec; it is not part of a
stop, nor of the « ne suffit pas » of an override request.

Before raising the stop, `bin/ticket-evaluation cleanup` reaps only this
ticket's products. A failed cleanup leaves the stop recorded and is retried on
the next settlement; the open evaluation request and prior evidence remain
readable, and a late result is refused by the stopped-ticket gate.

The stop is `bin/convoy-state stop-ticket --reason still_refused`, with one
line that names everything still refused (« revue de code (F1.1) ; Ticket
Evaluation (critère 1) »), and every other condition of the merge still red
at the tip: a review or evaluation with no favorable verdict there, a red
fidelity. When the fidelity is red or no evaluation is favorable at the tip,
the request says the override alone « ne suffit pas » (T02R2, af-r2c0tx). A stopped ticket takes no further step: no
review, no evaluation, no round, no merge (`docs/SPEC_INTEGRATION.md`),
but the evaluation of a ticket whose findings are all overridden (below). It is
raised **once** through `bin/escalation-door benjamin`: one line for the
ticket in `bin/escalation-door list`, whether one control or both refused
it. `bin/convoy-state stop-raised` records it; a stop whose request could
not be sent is raised by the next pass.

The commit of the correction outdates the verdicts given before it. The
merge command writes that (`bin/convoy-state invalidate-verdicts`) **without
counting a second resume**: verdicts given at the commit of the round are
outdated by the round, which was counted when it was opened. Any other
commit added after a verdict still counts one resume (Spec §8).

## The override of the operator

```bash
./bin/correction-round override af-convoy af-t1 --finding F1.1 --approved-by benjamin-hurand --words "Je passe outre : …"
```

Accepted only when all of this holds; otherwise refused, and nothing is
written:

- the ticket is **stopped**;
- `--finding` names a **Blocking Finding of its code review left without a
  favorable verdict**;
- `--approved-by` is the **declared human approver** of the project the
  ticket names (`human_approver` in `config/projects/<project>.toml`, read
  by `bin/project-planning-profile human-approver`);
- `--words` is **not empty**: the words are stored as given.

It is written by `bin/convoy-state override-finding` and read back, in
`show` of both commands, under `overrides`: `finding`, `approver`, `words`,
the `commit` of the review, `at`, and `state`: `dérogation enregistrée`. The
same override again writes nothing; other words for a finding already
overridden are refused.

**A criterion is never overridden.** `--criterion <n>`, or a `--finding`
that is not a finding id (« critère 1 », « ligne de démonstration »), is
refused with « un critère non observé ne se dispense jamais » and the way
out: a Planning Exception (`bin/planning-exception`,
`docs/PLANNING_EXCEPTION.md`).

The override records a decision; it lifts nothing by itself. The finding
keeps its unfavorable verdict (`code_review.state.unsettled`), the ticket
stays stopped. Once **every** Blocking Finding left unsettled is overridden,
the override stands for the code review and for nothing else: the ticket
is still evaluated at its tip. When no evaluation is favorable there — the
stop withdrew the one that was open — `bin/ticket-evaluation settle` opens
and launches it at the next pass, once (its relaunch rule unchanged), and
`cleanup` no longer releases its products (af-ppdbza, T02R2). Favorable,
the next pass merges the ticket and the ticket-end gate closes it: its
condition 9 reads `overrides` (`docs/TICKET_END.md`). Unfavorable, or
without a result after its relaunch, the ticket stays stopped and nothing
of it is merged.

## Stored state

On the ticket, written by `bin/convoy-state` only (`docs/CONVOY_STATE.md`):

| Key | Value |
|---|---|
| `gc.flow.correction` | `commit`, `blocking_findings` (finding ids), `not_observed` (names), `launches` (at most one `{bead, at}`), `at` |
| `gc.flow.counter.resumes`, `gc.flow.counter.correction_rounds` | each one more when the round is opened |
| `gc.flow.stop` | reason `still_refused`, a one-line detail, and `raised` once the escalation door accepted the request |
| `gc.flow.overrides` | `entries`: one `{finding, approver, words, commit, at}` per overridden Blocking Finding |

## Avoiding reads for tickets with no work

Intent (Benjamin, his words, 2026-10-12): « corriger le flow par tranches ordonnées et vérifiées ».
Mechanism (agent interpretation): the initial convoy snapshot skips tickets
with neither an exit nor a stop before settlement. Their malformed state is
still refused. Every candidate is read again under its ticket lock before any
action, and changes made by an author after the snapshot are seen on the next
pass. This removes a full-convoy tracker read per unfinished ticket without
caching a verdict or authorising an action from stale state (af-8cfygl).

## Limits

- The author session of the round is recognised as ended when its bead is
  closed. There is **no timeout** on it: a session that dies without closing
  its bead leaves the ticket waiting. The resumes of T20
  (`docs/CONVOY_ADVANCE.md`) do not cover it: the ticket still carries its
  Ticket Exit « terminé », so the pass does not read it as interrupted. The
  round itself counts among the three resumes that park a ticket.
- The words of an override are whatever the caller gives with the name of
  the approver: nothing technically stops an agent from typing them. The
  record makes it visible afterwards (the same limit as the acceptance,
  Spec §11).
- Nothing lifts a stop. A ticket whose every unsettled Blocking Finding is
  overridden is merged and closed while still carrying its stop
  (`docs/TICKET_END.md`); no other stopped ticket is resumed: T20 never
  resumes a stopped ticket (`docs/CONVOY_ADVANCE.md`).
- A Planning Exception named by the refusal of a criterion is not opened by
  this command.
- The author role counts in the ceiling N once its session is alive; like a
  review, the launch itself does not wait for a free place.

## Proof

`tests/correction-round-test.py` drives the command lines on a fake tracker
state, against a copy of the Delivery Fixture City in a throwaway repository
with its own remote: one test per pass and per refusal, the tracker read
again after each refusal. The merge control is the real
`bin/spec-integration`, the stop is read back from the list of the real
`bin/escalation-door`, the approver from the real
`bin/project-planning-profile`. No agent runs in CI:
`tests/fixtures/correction-round/author` stands in for the dispatch door and
the author session. `tests/convoy-state-test.py` holds each state write and
its refusals, `tests/convoy-advance-test.py` the settlement by the pass.
`tests/correction-round-isolated-city-test.sh` (local-only) replays the
demonstration line on a real controller: the real order, formulas, dispatch
door, product launcher and merge command, with a scripted reviewer,
Evaluator and correction author.
