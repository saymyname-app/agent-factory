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
./bin/spec-end check af-convoy --repo <repository>  # the five conditions of the end of the Spec
```

## What code prepares, what the Evaluator hands in

| Step | Who | Command |
| --- | --- | --- |
| Launch the product from a clean copy of the commit of the gate, once per declared dataset; route the evaluation | code, in the pass | `settle` (`bin/project-launch`, `bin/dispatch-door` on the formula `mol-outcome-evaluation`, role `evaluator`) |
| Read what is to evaluate: the numbered user stories, the launched products, the findings to classify, the prototypes | Evaluator session | `brief` |
| Classify each finding « hors ticket » | Evaluator session | `classify` |
| Hand in the states, the two free sections and the drafted repairs | Evaluator session | `record` |
| Compute the verdict | code | `verdict` (read by `bin/spec-end`) |

`brief`, `classify` and `record` are refused outside a session of the
read-only Evaluator role. The session is given no repository: it sees the
product through its addresses only.

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
published while an evaluation is open.

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
| `outcome_evaluation_no_result` | Two launches, each left without states past `timeout_seconds` |
| `outcome_evaluation_outage` | The clean copy does not start, or two outages in a row at the same commit |
| `story_unobservable` | A story handed in as `unobservable` |

A stop is raised once to the operator through `bin/escalation-door benjamin`
on the convoy, in French, and holds for its commit: nothing is launched
again on it. An evaluation is **deferred**, not stopped, when the Evaluator
would run on the supplier of an author while another declared supplier is
available (`./bin/provider-failover` sets the role). When no other supplier
is available, or a supplier was not recorded, the evaluation runs and the
record says so (`independence`).

## Settings

`config/delivery-flow.json`, block `outcome_evaluation`: `formula`, `role`,
`rig`, `timeout_seconds`, `start_timeout_seconds`. Without the block,
`settle` refuses and the pass fails, naming it.

## Refusals and exit status

Every answer is one JSON object on stdout. Exit 0 done; 1 refused or could
not run; 3 « état sans règle »; 4 the convoy does not carry the mark. A
refusal writes nothing.

## Limits

- **No bound on the rounds of the end.** A story still not observed after
  its repair gets a new drafted repair at the next evaluation. The counter
  of end rounds and its bound are T26's.
- **No real Evaluator session ran.** The formula and the commands are
  proven with a stand-in for the door and the session; no adoption trial of
  the role on `mol-outcome-evaluation` was run in an isolated city.
- **The Evidence Pack is not generated here.** `show` holds what its
  generator reads (states, proofs, exploration, fidelity deviations,
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
