# The Outcome Evaluation and the findings « hors ticket » (T24, Spec af-wf4w5r §7, §9 points 4 and 5)

## What it is for

In a convoy that carries the **new-flow mark**, three green mechanical
verdicts (`docs/SPEC_END.md`) say the pieces hold together; they do not say
the assembled product does what the Spec asks. Once they are green on one
commit of the integration branch, an **Evaluator of the end** uses the
assembled product at that commit, in a fresh context and as a black box, and
hands in **one state per numbered user story of the Spec, each with its
Evidence Record**. Code computes the verdict; the Evaluator gives none (user
story 57). The same session classifies every finding « hors ticket » the
authors declared in their Ticket Handoffs (user story 60), and code writes
down each story the assembled product does not show although the tickets
that cover it were all « observés » (user story 63).

A convoy **without** the mark is not concerned: every command answers « pas
un convoi du nouveau flux » (exit 4) and writes nothing.

`bin/outcome-evaluation` is the command. `bin/convoy-advance` has it settled
at each pass (`settle`); `bin/spec-end` reads its verdict as conditions 4
and 5 of the end-of-Spec gate (`verdict`).

```bash
./bin/outcome-evaluation show    af-convoy          # states, proofs, drafted repairs, contradictions; reads only
./bin/outcome-evaluation verdict af-convoy          # the computed verdict and why; reads only
./bin/spec-end check af-convoy --repo <repository>  # the six conditions of the end of the Spec
```

## What code prepares, what the Evaluator hands in

| Step | Who | Command |
| --- | --- | --- |
| Open one product from a clean copy of the gate commit; route the evaluation | code, in the pass | `settle` (`bin/project-launch`, `bin/dispatch-door` on the formula `mol-outcome-evaluation`, role `evaluator`) |
| Read what is to evaluate: the numbered user stories, the launched products, the findings to classify, the prototypes | Evaluator session | `brief` |
| Classify each finding « hors ticket » | Evaluator session | `classify` |
| Hand in the states, the two free sections and the drafted repairs | Evaluator session | `record` |
| Compute the verdict | code | `verdict` (read by `bin/spec-end`) |

`brief`, `classify` and `record` are refused outside a session of the
read-only Evaluator role. The session is given no repository: it sees the
product through its addresses only. `brief.datasets` lists every declared
dataset the Evaluator may open, `brief.cited` the ones it must cover, and
`brief.screens` which datasets show which screen (« Which datasets », below),
while `brief.environments` lists only the active product. `product
CONVOY --dataset NAME` returns `ready=false` until the controller's next
pass confirms the old product stopped and opens the requested one;
`--wait SECONDS` blocks for that inside one call (af-oowsc2). `--fresh`
revisits a game from its initial state at the same commit. Capture before
switching. The sealed result includes one `coverage` entry (`dataset`,
`evidence`) for each game opened, every cited one among them; a missing game
or wrong address refuses it.
Historical addresses remain in the request and round for proof checks
after their products stop. Ticket and Outcome Evaluation share two host
slots, with one active product per evaluation. Startup and shutdown count;
failed cleanup retains the slot. A valid launch record whose PID, process
group, marked descendants and worktree are all gone no longer occupies a
slot; an incomplete or unreadable record still does, fail-closed. Product
readiness uses the same controller attestation and live socket check as Ticket Evaluation
(`docs/TICKET_EVALUATION.md`, af-bjvd8z).

## Which datasets

Intent (Benjamin, his words, operator chat, 2026-10-17 around 11:40 Paris,
recorded on `af-npz9v1`): to « En fin de Spec, l'évaluation du produit
assemblé (Outcome Evaluation) est prévue sur les 95 jeux de données :
plusieurs heures, et un risque d'échec par délai comme pour T02. On la
réduit ? » he answered « Réduire aux jeux cités ».
Mechanism (agent interpretation, `af-npz9v1.11`): the rule of the Ticket
Evaluation (`af-kdxk6k`) applied to the Spec.

- **Cited (`brief.cited`), due:** the declared datasets of the project's
  profile (`launch.datasets`) that a numbered user story of the Spec, the
  demonstration line of a ticket of the convoy, or a validated expectation of
  a story names, by their exact name. The Spec carries no demonstration line
  of its own: those of its tickets are what demonstrate it. None named, the
  first declared dataset (in name order) alone. The first cited dataset is
  the product launched first; each cited one is opened and covered.
- **Every other declared dataset, on demand** (Benjamin, 2026-11-09 21:53
  Paris, to « On ouvre à l'Evaluator tous les jeux déclarés, un à la fois ? »:
  « Oui, ouvre-les », `af-ip0nrq`): `product --dataset` opens any dataset of
  `brief.datasets`, one product at a time as before. On 2026-11-09 the
  Cockpit convoy `af-strhoy` was stopped with 57 of 89 stories
  « unobservable » on the one cited dataset, whose situations other declared
  datasets showed: the factory, not the stories, made them unobservable.
  `brief.screens` (the profile's `launch.screens`: screen, path, datasets)
  helps choose where a story's situation is.
- **The coverage:** one `coverage` entry per dataset opened, every cited one
  among them; nothing more is due for a dataset never opened.
- **The delay of one launch:** `max(timeout_seconds, datasets ×
  per_dataset_seconds)`, the very function of the Ticket Evaluation
  (`launch_timeout`, `lib/evaluation_capacity.py`, `af-vtg5kl`); the datasets
  counted are those the Evaluator may open (95 datasets: 22 800 s).
- **An evaluation opened before this rule** (no `cited` in its request)
  keeps its datasets and the coverage of each until it is replayed.

**What this changes before Benjamin's Acceptance Session.** Only the cited
datasets are due: a story that holds on an opened dataset and fails on one
never opened is not caught by this evaluation, nor by the condition 4 of the
gate; it is found in the Acceptance Session or not at all. The Acceptance
Session itself is unchanged (`docs/ACCEPTANCE_SESSION.md`).

`record` takes one JSON file:

```json
{"commit": "<commit of the gate>",
 "stories": [{"number": 3, "text": "<the story, as the Spec writes it>", "state": "observed", "evidence": "outcome.s3"},
             {"number": 4, "text": "…", "state": "not_observed", "evidence": "outcome.s4", "reason": "…"}],
 "exploration": "aucun", "fidelity_deviations": "aucun",
 "repairs": [{"story": 4, "title": "…", "what_it_delivers": "…",
              "restores": {"kind": "user_story", "ref": "user story 4"},
              "demonstration_line": "…",
              "acceptance_criteria": [{"entry_point": "…", "observable": "…", "false_if": "…"}]}]}
```

- **One state per story, each with a piece.** The stories are those the Spec
  of the convoy numbers, read at the commit of the gate. A story that is
  missing, one the Spec does not number, or a state without a valid piece
  refuses the whole record. A piece is valid when `bin/evidence-capture`
  captured it under the convoy, at the commit of the gate, on one of the
  launched products (`docs/EVIDENCE_STORE.md`).
- **States**: `observed`, `not_observed`, `unobservable`.
- **An `unobservable` names the datasets tried** (`tried`: each declared
  dataset opened in this evaluation to look for that story). Without it, or
  with a dataset never opened, `record` refuses the whole hand-in
  (`af-ip0nrq`). Which dataset is relevant to a story is the Evaluator's
  judgement, helped by `brief.screens`; code proves the try was made on a
  product it opened.
- **`exploration` and `fidelity_deviations`** are kept for the Evidence Pack
  and change nothing to the verdict.
- **A `verdict`, an `outcome` or a `contradictions` field is refused**: code
  computes them.
- **Refused while a finding « hors ticket » is left unclassified.**

## The verdict, computed

Favorable only if **every** numbered user story is `observed` with a valid
piece, at the commit the gate rendered its mechanical verdicts on.

| Outcome | When | What follows |
| --- | --- | --- |
| `favorable` | every story observed with proof | condition 4 of the gate is met |
| `repair` | a story `not_observed` | its drafted `repair`, which must cite that story, is published by the next pass through the patch door and started like any ticket |
| `planning_exception` | a story `unobservable` | the evaluation stops (`story_unobservable`) and the operator is asked: a story is neither waived nor reworded by an agent |
| `environment_outage` | the product could not be used | not counted as a refusal; evaluated again, stopped after two in a row at the same commit (`outcome_evaluation_outage`) |

The Evaluator drafts a repair and **publishes nothing**: `bin/convoy-advance`
publishes it through the patch door (`bin/ticket-graph-publish`), then names
it on the story (`bin/convoy-state set-outcome-repair`), once. Nothing is
published while an evaluation is open. A draft the patch door refuses (a
criterion that names a file, say) is recorded where it was drafted with the
reason (`set-outcome-repair --refused`), never published again, and stops
the evaluation at the commit of its last round (`outcome_repair_refused`)
(af-68sgzq). A finding whose draft was refused may be classified again by
the next evaluation.

One commit more on the integration branch, or a move of the protected
branch, outdates the mechanical verdicts and with them the evaluation: it is
withdrawn with its products and replayed on the new tip.

## Findings « hors ticket »

A finding is one line of the `out_of_ticket` section of a Ticket Handoff,
named `TICKET:out_of_ticket.N`. `bin/convoy-state show` renders them per
ticket under `findings`, with a state code computes:

| Classification (`--as`) | Required | State read |
| --- | --- | --- |
| `repaired` | `--file` with a drafted `repair` whose `restores` cites what it restores (`kind` among `user_story`, `anchor`, `spec_line`, `repo_rule`, `red_check`, and `ref`) | « à réparer » until the `repair` code published is closed by the ticket-end gate, « réparé » then |
| `proposal` | nothing | « proposition pour Benjamin », final, kept for the Evidence Pack |
| `dismissed` | `--reason` | « écarté », final |
| — | — | « non classé » |

« repaired » without the citation and « dismissed » without a reason are
refused and write nothing. A new Handoff of the ticket puts its findings
back to « non classé ».

## Conditions 4 and 5 of the end-of-Spec gate

| # | Name | Met when |
| --- | --- | --- |
| 4 | `outcome_evaluation` | The verdict is favorable at the commit of the three mechanical verdicts, and no finding is « non classé ». A finding left unclassified is named. |
| 5 | `findings` | Every finding is in a final state (« réparé », « proposition pour Benjamin », « écarté »). A finding « à réparer » is named with its repair. |

The gate records nothing for them and launches no agent: it reads, at each
call, what the Evaluator handed in.

## Contradictions with the tickets' proofs

When a story is `not_observed` and **every** ticket that covers it had its
criteria « observés » by its Ticket Evaluation, code writes a contradiction
with the record: the story, and each covering ticket with the commit and
date of its favorable evaluation. The Evaluator cannot write or remove one.
`./bin/outcome-evaluation show` renders them under `contradictions` for the
generator of the Evidence Pack. A story no ticket covers is not a
contradiction.

## Stops

| Reason | When |
| --- | --- |
| `outcome_evaluation_no_result` | Two claimed launches, each left without states past the delay of one launch (« Which datasets ») |
| `outcome_evaluation_outage` | The clean copy does not start, or two outages in a row at the same commit |
| `story_unobservable` | A story handed in as `unobservable` |
| `outcome_repair_refused` | The patch door refused a repair the Evaluator drafted, for a story or a finding « hors ticket » (written by `bin/convoy-advance`) |

**A `story_unobservable` the factory caused** is lifted by code, not by an
answer (`af-ip0nrq`). A Factory maintenance that repairs the cause is linked
to the stop: `bin/convoy-state link-outcome-repair CONVOY --repair BEAD`
(an authorized maintenance or a bead under the PR+CI delivery contract,
the same check as `link-technical-repair`). Once every linked repair is
merged with its CI proven on the exact head (`delivery_readiness`), the next
`settle` clears the request from the operator's list
(`bin/escalation-door clear`, no answer recorded), lifts the stop
(`bin/convoy-state lift-outcome-stop`, kept under `lifts`, the round it
stopped on set aside) and opens the evaluation again at the same commit.
No counter moves: a refusal at that same commit counts no round of the end
(`end_rounds`, once per tip, `docs/CONVOY_STATE.md`). Until the repair is
delivered the stop holds and its request stays on the list. If the new
evaluation still renders a story `unobservable`, with its datasets tried,
that is a new stop and a new request.

**A stop holds its commit only** (`af-mmefvq`). Once the gate renders its
verdicts on another commit, whatever the reason of the stop, the next
`settle` sets it aside: its request leaves the operator's list without an
answer (`bin/escalation-door clear`, only while it is still the request on
the convoy), the stop is kept under `lifts` with the commit that outdated it
(`bin/convoy-state lift-outcome-stop --outdated-by`), and the evaluation is
made at the new commit. No counter moves. If that evaluation stops again, it
is a new stop and a new request.

A stop is raised once to the operator through `bin/escalation-door benjamin`
on the convoy, in French, and holds for its commit: nothing is launched
again on it. An evaluation is **deferred**, not stopped, when the two host
product slots are occupied, or when the Evaluator would run on the supplier
of an author while another declared supplier is available
(`./bin/provider-failover` sets the role). The next pass retries a deferral;
it is never recorded as `outcome_evaluation_outage`. When no other supplier
is available, or a supplier was not recorded, the evaluation runs and the
record says so (`independence`).

A routed evaluation becomes an attempt only when the `evaluate` step of its
`mol-outcome-evaluation` workflow carries `gc.claimed_at`. Its timeout starts
at that claim, not at dispatch. A route waiting for the single Evaluator seat
therefore stays pending and consumes neither attempt. If workflow cleanup
closes such an unclaimed route, its history is retained and one replacement
may be routed; only the two actually claimed attempts count toward
`outcome_evaluation_no_result`.

## Settings

`config/delivery-flow.json`, block `outcome_evaluation`: `formula`, `role`,
`rig`, `timeout_seconds` (the floor of the delay of one launch),
`per_dataset_seconds` (optional, 0 by default; 240 like the Ticket
Evaluation), `start_timeout_seconds`. Without the block,
`settle` refuses and the pass fails, naming it.

## Refusals and exit status

Every answer is one JSON object on stdout. Exit 0 done; 1 refused or could
not run; 3 « état sans règle »; 4 the convoy does not carry the mark. A
refusal writes nothing.

## Limits

- **The wait for a requested dataset counts against the launch.** Unlike the
  Ticket Evaluation (`af-4nop0m`, #657), the time the controller takes to
  open a dataset the Evaluator asked for is not given back to the launch.
- **The rounds of the end are bounded (T26).** An evaluation that leaves a
  story not observed, or a finding « hors ticket » still « à réparer »,
  refuses its tip: `record-outcome-evaluation` counts one round of the end
  in the same write (`counters.end_rounds`, one counter with the mechanical
  reds and the end review, once per tip; bound `bounds.end_rounds`, 2), or
  stops the rounds (`gc.flow.end_stop`) — when the bound is consumed, and,
  **before the second round is counted**, when the round before did not
  reduce the number of stories not observed (`stories_not_reduced`) or when
  a story not observed in an earlier round is not observed again
  (`story_refused_twice`). Once stopped, the drafted repairs are not
  published and a « non conforme » request goes to the operator
  (`docs/CONVOY_STATE.md`, « The rounds of the end »; `docs/CONVOY_ADVANCE.md`,
  « The rounds of the end are bounded »). The early stops read the stories
  not observed only: a finding « hors ticket » to repair counts a round and
  meets the bound, nothing earlier.
- **No real Evaluator session ran.** The formula and the commands are
  proven with a stand-in for the door and the session; no adoption trial of
  the role on `mol-outcome-evaluation` was run in an isolated city.
- **The Evidence Pack is not generated here** but by `bin/evidence-pack`
  (T27, `docs/EVIDENCE_PACK.md`). `show` holds what its generator reads (states, proofs, exploration, fidelity deviations,
  proposals, contradictions, independence).
- **The products run on the Factory host**, launched inside the pass of the
  order (timeout 300 s, `orders/convoy-advance.toml`); a product that is
  slow to start is an outage.
- **A proposal is only kept.** Nothing turns a « proposition pour
  Benjamin » into work: the operator reads it in the pack.

## Proof

- `tests/outcome-evaluation-test.py`: the command lines on a fake tracker
  state, on a copy of the Delivery Fixture City launched by the real
  `bin/project-launch`, pieces captured by the real `bin/evidence-capture`.
  On the conforming fixture every story is « observée avec preuve »; on the
  one where a story is not served, the story is « non observée » with its
  piece, a drafted repair appears and the contradiction with the covering
  ticket is written. One test per refusal, each re-reading the tracker.
- `tests/spec-end-test.py`: conditions 4 and 5, a finding left unclassified
  named by the gate.
- `tests/convoy-advance-test.py`: the pass launches the evaluation once the
  mechanical verdicts are green, publishes nothing while it is open, fails
  when it cannot be settled.
- `tests/convoy-stops-fixture-city-test.py`: the drafted repair of a story
  and of a finding « à réparer » published once by the real patch door.
- `tests/fixture-city-oracle-test.py`: the walked ticket's convoy reaches
  the end of its Spec and has its assembled product evaluated by the
  stand-in Evaluator.
- `tests/spec-end-real-tracker-test.sh` (local-only): in a disposable city,
  the state writes of the evaluation and of the findings, and their
  refusals, on the real `gc`/`bd`; the user stories are read in a Spec bead
  of that tracker.

Validated scalar expectations use the project-specific profile mapping and sealed comparison contract described in docs/TICKET_EVALUATION.md. The Outcome Evaluation applies it to frozen Spec stories; a contrary value drafts the existing one-story repair, while a missing validated expectation follows Planning Exception.
