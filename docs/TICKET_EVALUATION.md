# Ticket Evaluation on the launched product (T15, Spec af-wf4w5r §7, §8)

## Status and purpose

« Green » is confronted with « it works ». Once a ticket of a convoy that
carries the **new-flow mark** is finished and green, the flow — not the
author — has it evaluated on the **launched product**, before its merge:

- Code launches the product from a **clean copy** of the commit the author
  finished at (`bin/project-launch`: a work tree of its own, the recipe of
  the project's profile, a free port, synthetic datasets). The author's work
  tree is never what is evaluated.
- An **Evaluator** uses it: a session of the read-only Evaluator role, in a
  fresh context, as a black box. It is given the demonstration line and the
  frozen criteria only — neither the Ticket Handoff nor the diff.
- It hands in **one state per criterion and one for the demonstration
  line** — `observed`, `not_observed`, `unobservable` — each resting on a
  piece captured by `bin/evidence-capture` on one of those products. It
  gives no verdict: code computes it.
- Only an **interface ticket** (one whose publication posed a Validated
  Prototype reference, `interface: true` in `convoy-state show`) gets an
  Evaluator session (ADR-0030 L4): its frozen criteria are already proven by
  the frozen criterion tests, and in 2026-10 model evaluation never found a
  defect the code review missed. For a **`prefactoring`** and for **any
  ticket without interface** no session runs: code checks that the product
  starts and that its probe answers (the **startup control**, below); on a
  ticket without interface the round records the model evaluation
  `model: "not_required"`.
- `bin/spec-integration` **merges nothing** without a favorable evaluation
  at the tip of the ticket branch. An evaluation that is absent, open or
  without result is not an agreement.

`bin/ticket-evaluation` holds it. Its state lives in the tracker, read and
written through `bin/convoy-state` only. A convoy without the mark is not
touched (exit 4): it is merged as before.

```bash
./bin/ticket-evaluation cleanup af-convoy af-t1 [--repo DIR]              # stopped ticket only
./bin/ticket-evaluation settle  af-convoy [--repo <project repository>]   # bin/convoy-advance, at each pass
./bin/ticket-evaluation brief   af-convoy af-t1                           # the Evaluator session (formula mol-ticket-evaluation)
./bin/ticket-evaluation record  af-convoy af-t1 --file result.json        # the Evaluator session
./bin/ticket-evaluation verdict af-convoy af-t1                           # any gate: the verdict, computed
./bin/ticket-evaluation show    af-convoy af-t1                           # rounds, open request, roles, products still running
```

Every answer is one JSON object on stdout.

| Exit | Meaning |
|---|---|
| 0 | done |
| 1 | refused, or could not run (`{"ok": false, "error": "refus : …"}`); `settle`: a ticket was refused (listed under `refused`) |
| 4 | the convoy does not carry the mark: « pas un convoi du nouveau flux » |

## When an evaluation is due

`settle` decides from the tracker and the ticket branch alone, ticket by
ticket, on the same conditions as the code review (`docs/CODE_REVIEW.md`):
the Ticket Exit is « terminé », the complete Ticket Handoff was taken at the
tip, the ticket is green at the tip (`bin/tdd-step`), and it is not stopped,
parked, closed, or already merged at that tip. `bin/convoy-advance` calls
the code review and the evaluation in the same pass: they run in parallel,
on the same tip. A finished ticket whose branch does not contain the tip of
the integration branch is handed back to its author by the resumes of that
pass, before both (cause `behind`, T44, `docs/CONVOY_ADVANCE.md`): its
Ticket Exit is taken back, so no evaluation is sent on the old tip. The
evaluation has no check of that tip of its own.

A pass reads the convoy once, then skips without reading it again every
ticket that has no Ticket Exit, no stop, no open evaluation, no tracked
product and no launch record in its product folder: nothing can be due on
it. Only the others are read again, under their lock, before anything is
decided (af-x11w4x: reading the convoy again for each of 62 tickets made
`settle` the first caller of `bin/convoy-state`, 34 reads a minute).

| State of the evaluation | What `settle` does |
|---|---|
| none at the tip (none yet, or a commit was added after the last one) | launches the products at the tip and opens an **evaluation**: a commit added after a verdict has it replayed in full (Spec §8). For a `prefactoring` or a ticket without interface (ADR-0030 L4): the **startup control**, no session. A startup control that stood for the evaluation (the product started) does not stand for a ticket that has since become interface: it gets its model evaluation at the same tip; a product that did not start stays the verdict at that tip |
| favorable at the tip | nothing: the merge may follow |
| `not_observed` at the tip | waits: back to the author, nothing merges before a new commit. `bin/correction-round settle` sends what was not observed, with the findings of the code review, to the one author session of the ticket's correction round, and stops the ticket still not observed after it (`docs/CORRECTION_ROUND.md`) |
| `unobservable` by the criterion at the tip | **Planning Exception**: one request on the operator's list (`bin/escalation-door`), the ticket and those that wait for it are parked (`bin/convoy-state park`) |
| `unobservable` by the environment only | an **outage**: no verdict, nothing counted as a refusal; the evaluation is made once more on products launched again. A second outage at the same commit stops the ticket (`evaluation_outage`) |
| open, launched, within its time | waits |
| open on a ticket that is no longer to be evaluated at that commit (its author added a commit, it was parked, or it has no interface: a model evaluation opened before ADR-0030 L4) | withdraws it and stops its products: what its session hands in later is refused |
| any launched product that no open evaluation runs on | stops it (`bin/project-launch stop`) and records that it is gone |

A second call on the same state does nothing.

## The product that is evaluated

Intent (Benjamin, 2026-10-12): « l’évaluation lise la recette du ticket qui l’établit, sans affaiblir les contrôles ».
Mechanism (agent interpretation): for a ticket marked `establishes_launch_recipe`
by publication, read only `launch` from the same project descriptor at the exact
commit being evaluated, using Git objects, never the author's checkout. Keep the
live project's identity and reject a candidate that changes its project or rigs.
Validate the resulting profile through the ordinary profile command; missing or
invalid committed recipes are refused, never replaced by a live fallback. The
Evaluator brief reads the requested commit, even if the branch has since moved.
All other tickets keep the ordinary profile selection. This changes no evidence,
criterion, independent-session or favorable-verdict requirement.


For an evaluation, `settle` opens only the first declared dataset from a
clean worktree of the evaluated commit. The Evaluator reads every declared
game in `brief.datasets` and asks for the next one with `ticket-evaluation
product CONVOY TICKET --dataset NAME`. A `ready=false` response records the
request. The next controller pass stops the old product, confirms its
descendants, port and worktree are gone, then opens the requested game.
`--wait SECONDS` repeats the ask inside one call until `ready=true` or the
timeout (af-oowsc2); capture with the returned address and launch record.
`--fresh` requests a new initial state for a revisit at the same commit. Capture proof before switching away. The read-only role
never launches or stops a process itself. The controller verifies the clean
copy's commit, launch marker and ownership of its listening socket, then writes
an exact identity attestation. The Evaluator's sandbox sees that directory
read-only and confirms the attested socket still listens before `ready=true`.
A session without the protected mount, a stale socket, or a changed launch
record receives `ready=false`; an HTTP response or port alone is insufficient
(af-bjvd8z).

Ticket and Outcome Evaluation share two host slots and allow one active
product per evaluation. Startup and shutdown count as occupied. An
unconfirmed stop keeps its record and slot. Waiting for admission before
the first Evaluator session starts does not consume that session's deadline.
`project-launch` writes a provisional record before spawning, so an
interrupted pass recovers the exact repository, commit and game or stops it.
A superseded commit is never reused. For a ticket that establishes its
launch recipe, the controller tests a disposable start/stop cycle **before**
opening the evaluated product. Its sealed observation still includes the
lifecycle result and validated reference checks; the trial and the evaluated
product never run together.

**The games of a ticket** (af-kdxk6k) are the declared datasets the ticket
names: in its frozen criteria or its demonstration line (the exact name,
not inside a longer one), or as the `dataset` of a validated expectation of
its criteria. A ticket that names none is evaluated on the first declared
dataset only. Every declared dataset for every ticket made one evaluation
need about 95 two-minute coverages against a 3,600-second deadline, and
stopped T01R, T01R2 and T01R3 without a result (Benjamin, 2026-10-15:
« l'évaluation […] limitée aux datasets du ticket »). The Evaluator can
request only these games; the request keeps the list it was opened with.
A behaviour that must hold on every dataset belongs in a deterministic test,
not in a model's tour of the product. Outcome Evaluation still covers every
declared game.

The request retains historical addresses for Evidence Record verification
after a switch; `live` names only the product still running. A favorable
result requires a sealed `coverage` piece for every game of the ticket as well
as one state and proof for every criterion and the demonstration line.
The result carries `coverage: [{"dataset": NAME, "evidence": PIECE}, ...]`.
A missing game or a piece captured on another game's address is refused.
After the result, stop or withdrawal, the controller stops the remaining
product and releases its slot only after cleanup is confirmed.
When a ticket is stopped or withdrawn while its evaluation is open, the
controller also cancels every launch of that request through its exact input
convoy and Ticket Evaluation workflow. It closes the source bead as
`fail`/`abandoned`, then closes only an Evaluator session that was assigned
to that workflow and holds no other in-progress work. The request is removed
after product and workflow cleanup; its launch history remains. A failed
cleanup leaves the request open for retry and never creates a favorable
verdict.

A product that does not start from the clean copy (two attempts, each within
`start_timeout_seconds`) cannot be observed: `settle` records it as an
unfavorable startup round, on a slice as on a `prefactoring`, and no
Evaluator session is started.

## What the Evaluator is given

`brief` is the preparation command: its output is everything the Evaluator
session receives.

| Field | Content |
|---|---|
| `demonstration_line` | the demonstration line of the approved ticket |
| `criteria` | the acceptance criteria of the approved ticket, numbered in order |
| `environments` | the active product: `dataset`, `address`, and `launch_state`, the launch record to name to the capture tool |
| `datasets`, `product` | the games of the ticket (below) and the command to request one |
| `entry_points` | the entry points the profile declares |
| `states`, `unobservable_causes` | the closed lists |
| `capture`, `result_shape` | how a piece is captured on a launched product, and the shape of what `record` takes |
| `commit` | the evaluated commit |
| `roles`, `independence` | the provider and supplier of the author and of the Evaluator, and the mention when they are the same or not known |

**Neither the Ticket Handoff, nor the diff, nor the repository, nor the
branch.** The formula tells the Evaluator not to read the ticket bead, its
notes, commit messages, mail or the author's session, and to use only the
addresses of `environments`.

## What the Evaluator hands in, and what code makes of it

`record` runs only in a read-only role session (`DELIVERY_ROLE_READ_ONLY`,
set by `bin/delivery-role-sandbox`).

```json
{"commit": "<evaluated commit>",
 "criteria": [{"number": 1, "text": "<the criterion, copied exactly>", "state": "observed", "evidence": "evaluation.c1"},
              {"number": 2, "text": "…", "state": "not_observed", "evidence": "evaluation.c2", "reason": "…"}],
 "demonstration_line": {"text": "<the line, copied exactly>", "state": "unobservable", "cause": "environment",
                        "evidence": "evaluation.demo", "reason": "…"}}
```

Refused, with nothing written:

- a **`verdict`** or an `outcome` given by the Evaluator: the verdict is
  computed by code;
- a state **outside the three**; a state that is not `observed` without a
  `reason`; an `unobservable` without its `cause` (`criterion` or
  `environment`);
- a state **without a valid Evidence Record**: no piece named; a piece the
  capture tool did not produce (`bin/evidence-capture verify`: no seal, a
  fingerprint written by hand); a piece captured at another commit than the
  evaluated one; a piece captured **at an address that is not one of the
  products launched for this evaluation** — a capture on a product the
  author, or anybody else, launched is not evidence;
- criteria that are **not those of the approved ticket**: a criterion whose
  `text` is not the approved one (« reformulé »), a criterion left out
  (« retiré »), one the ticket does not have, two states for one criterion,
  a demonstration line reworded; and criteria that changed on the ticket
  since the request was opened;
- states for another commit than the evaluated one, states when no
  evaluation is open, states on a `prefactoring`, states on a stopped
  ticket.

**The verdict** is computed by `bin/convoy-state` in the same tracker write
as the round:

| States | Outcome | Verdict `gc.flow.verdict.evaluation` | What follows |
|---|---|---|---|
| every criterion and the demonstration line `observed` | `favorable` | favorable | the merge may follow |
| a `not_observed` (and no `unobservable` by the criterion) | `return_to_author` | unfavorable | back to the author |
| an `unobservable` by the **criterion** | `planning_exception` | unfavorable | Planning Exception: request to the operator, ticket parked |
| an `unobservable` by the **environment**, nothing else refused | `environment_outage` | none written | an outage, not counted as a refusal: evaluated once more |

Nobody waives a criterion: a state other than `observed` never gives a
favorable verdict, and no option of the command lifts one.

`verdict` computes the same answer again from the tracker, the evidence
store and the tip of the ticket branch, for a gate: `favorable` is true only
if the last round is favorable, **was made at the head commit**, no
evaluation is open, every piece it rests on is still a valid Evidence Record
of one of its products, and the verdict stored on the ticket is the one of
that round. Otherwise `reasons` says why.

## A prefactoring or a ticket without interface: the startup control

A `prefactoring` changes no behaviour: nothing new is to be observed. A
ticket without interface has its criteria proven by its frozen criterion
tests and its code read by the code review; a model evaluation of it is not
required (ADR-0030 L4), and its `startup` round says so (`model:
"not_required"`). No Evaluator session is started. A ticket that
establishes the launch recipe first proves that the product starts and
stops (the lifecycle preflight, as before an evaluation). `settle` launches each game of the ticket (a
prefactoring names none: the first declared dataset) in
sequence from a clean copy of the tip, captures the answer of the profile's
health probe with `bin/evidence-capture`, and confirms cleanup before opening
the next game. The first piece is `evaluation.startup`; later pieces are
numbered. The `startup` round stores one coverage piece per game and is
favorable only when every launch and probe succeeded. A failed launch or
probe is unfavorable; failed cleanup retains its capacity slot.

## The roles: another supplier than the author's

`settle` writes the agent, provider and model of the Evaluator role on the
ticket before it opens an evaluation (`bin/convoy-state set-model`, role
`evaluator`), and each request and each round carries `roles`:

```json
{"author": {"provider": "claude-standard", "supplier": "anthropic"},
 "evaluator": {"provider": "codex", "supplier": "openai"},
 "same_provider": false, "other_declared": ["openai"]}
```

The **supplier** of a provider is its `pool` in `config/provider-policy.json`:
two profiles of one account are one supplier. The suppliers **declared** for
the Evaluator are those of the chain of its target, as
`bin/provider-failover status --json` gives it (`lib/delivery_role_identity.py`).

| Situation | What happens |
|---|---|
| the Evaluator runs on another supplier than the author | recorded; no mention |
| same supplier, no other one declared for the Evaluator | recorded with the mention « même fournisseur que l'auteur (…) » |
| same supplier, another one declared but not available | recorded with the mention, which names the other supplier as « indisponible » |
| same supplier, another one declared **and available** | the evaluation is **not launched** (listed under `deferred`, tried again by the next pass): `bin/provider-failover` puts the role on it |
| the supplier of the author or of the Evaluator is not recorded | recorded with « indépendance de fournisseur non établie » |

The mention is in `show` and in `brief` (`independence`), and `roles` stays
in the round for the Evidence Pack. It is never left out.

## An evaluation that gives no result

A launch gives no result when `timeout_seconds` passed since it was sent
(`config/delivery-flow.json`, `evaluation`; 3600 s, a value without a
measured base), or when its bead was closed while the request is still
open. It is not a passed evaluation: no verdict is written and the merge
stays refused. It is launched **once more**, on a new bead, for a new
session (on products launched again if the first ones are gone). When that
relaunch replaces the product of a ticket that establishes its launch recipe,
the lifecycle trial and controller observation are captured again for the new
launch record before the new Evaluator receives its brief. The prior product's
observation is not reused as the identity proof of its replacement. When that
second launch gives no result either, the ticket is stopped
(`evaluation_no_result`), its products are stopped, and it is raised once to
the operator through `bin/escalation-door`. That stop alone is lifted by
code: `bin/convoy-advance` resumes the ticket itself, once per tip of the
integration branch and within the bound K of the resumes, withdrawing the
request (`docs/CONVOY_ADVANCE.md`, cause `evaluation_no_result`).

An evaluation handed in by a session that already rendered a review of
tests, a code review or a Ticket Evaluation of the convoy is refused the
same way (Spec §5, T42; `docs/TEST_REVIEW.md`, « A fresh session per
review »): the launch it answered is marked `refused` and gave no result.
`agents/delivery-evaluator/agent.toml` carries the same work query as the
reviewer and `wake_mode = "fresh"`, and `record` signs with
`GC_SESSION_NAME`, else `GC_SESSION_ID`, and `"c:"` + `CLAUDE_CODE_SESSION_ID`, else `"g"` + `GC_RUNTIME_EPOCH` as
`conversation` (`docs/CONVOY_STATE.md`).

A dispatch the door refuses or defers launched nothing: it counts no launch
and its bead is closed. A deferral is listed under `deferred` and tried
again by the next pass; a refusal is listed under `refused` and makes
`settle` exit 1.

## The merge control

`bin/spec-integration merge` (`docs/SPEC_INTEGRATION.md`) leaves a finished
ticket under `waiting`, and merges nothing of it, unless the last round of
its evaluation is favorable, was made at the tip, no evaluation is open, and
the verdict `evaluation` is favorable and valid there. A favorable verdict
written without the evaluation it comes from (`convoy-state set-verdict`)
does not pass.

## Stored state

On the ticket, written by `bin/convoy-state` only (`docs/CONVOY_STATE.md`):

| Key | Value |
|---|---|
| `gc.flow.evaluation` | `rounds`: each recorded round — an `evaluation` (`commit`, `criteria`: number, text, state, evidence, reason, cause; `demonstration_line`; optional `screen_findings`; `outcome`, `verdict`, `roles`, `environment`: dataset and address of each product, `recorded_by`, `conversation` when known, `at`) or a `startup` (`commit`, `started`, `evidence` and `environment`, or `detail`; `model`: `not_required` on a started ticket without interface, ADR-0030 L4; `outcome`, `verdict`, `at`). `request`, while an evaluation is open — `commit`, `criteria`, `demonstration_line`, `roles`, `environment` (with `state_file`), `launches` (`bead`, `at`, and `refused`: `{session, at}` when the session that answered had already served), `at`. `live`: the launch records of the products still to stop |
| `gc.flow.verdict.evaluation` | the verdict of the last round that gave one, and the commit it judged |
| `gc.flow.models` | per delivery role: `agent`, `provider`, `model`, `at` |
| `gc.flow.stop` | reason `evaluation_no_result` or `evaluation_outage`, a one-line detail, and `raised` once the escalation door accepted the request |
| `gc.flow.park` | cause `planning_exception`, once a criterion could not be observed |
| `gc.flow.evidence.<piece>` | the fingerprint of each captured piece (`bin/evidence-capture`) |

## Design standards in the brief

For an interface ticket, `brief` includes the root `DESIGN.md` text from the
exact evaluated commit and a short screen checklist: keyboard operation,
visible focus, image descriptions, and reduced motion. The Evaluator's role
cannot read the repository; these fields give it the written rule to cite
and the observations to make on the launched product. `record` accepts
`screen_findings` only on an interface ticket: each finding names one check,
copies an exact rule line from `DESIGN.md` at the evaluated commit, gives a
sealed evidence piece and a one-line reason. The state-writing door checks
the interface marker, the exact committed rule and the sealed piece too, so a
direct `convoy-state record-evaluation` call cannot bypass them. A valid
finding makes the verdict unfavorable even when the ticket criteria pass. A project still without
`DESIGN.md` has no design rule text to cite. Tickets without an interface
reference receive neither brief field.

## Limits

- The states are an agent's judgement. Code bounds them (closed states, a
  sealed piece captured on the launched product at the evaluated commit,
  criteria that are the approved ones, verdict computed); it does not check
  that the piece really shows what the state says. The captures are not
  replayed by code (Spec §0): the criterion tests are what code replays.
- « The criteria of the approved digest » is held by the text: the criteria
  are read on the ticket bead when the evaluation is opened and compared
  again when the states come in. There is no fingerprint per criterion, so
  a description rewritten before the evaluation is opened is not seen here
  (the publication door writes it, and no session of the flow is given a
  way to).
- The clean copy is hidden from the Evaluator by the sandbox of its role,
  not by this command: `launch_state` names it, and a session outside the
  sandbox could read it.
- The supplier is the configured one (`pool` of the provider), not one
  observed in the sessions. `record` checks that it runs in a read-only
  role session, not which one.
- The Evaluator role holds one session at a time: an evaluation waits
  behind another one, and the time of a launch runs from the dispatch. The
  products of a waiting evaluation stay up meanwhile.
- A launched product belongs to no service manager: if the host restarts
  between the launch and the session, the Evaluator finds nothing at the
  address (an `unobservable` by the environment, or no result), and the
  evaluation is made again.
- The mechanical fidelity controls of a ticket that touches a screen are
  `bin/prototype-fidelity` (`docs/PROTOTYPE_FIDELITY.md`); the gate that
  runs them for a ticket is T19's. The fresh author session after a refusal, its single
  correction round and the stop of a ticket still refused are
  `bin/correction-round`'s (`docs/CORRECTION_ROUND.md`). Nothing lifts a stop
  but `evaluation_no_result`, resumed by `bin/convoy-advance`
  (`docs/CONVOY_ADVANCE.md`).

## Proof

`tests/ticket-evaluation-test.py` drives the command lines on a fake tracker
state, against a copy of the Delivery Fixture City in a throwaway repository
with its own remote: the product is launched by the real
`bin/project-launch`, every piece is captured by the real
`bin/evidence-capture`, the merge control is the real `bin/spec-integration`,
and a stop or a Planning Exception is read back from the list of the real
`bin/escalation-door`. No agent runs in CI:
`tests/fixtures/ticket-evaluation/evaluator` stands in for the dispatch door
and the Evaluator sessions, and observes the launched product for real.
`tests/convoy-state-test.py` holds each state write and its refusals,
`tests/spec-integration-test.py` the merge control,
`tests/convoy-advance-test.py` the settlement by the pass.
`tests/ticket-evaluation-isolated-city-test.sh` (local-only) replays the
demonstration line on a real controller, with the real order, the real
formula, the real dispatch door, launcher and merge command, and a scripted
Evaluator that runs inside the real read-only sandbox of its role.


## Controller observations for a launch recipe

Intent (Benjamin, his words, 2026-10-12): « Oui je valide, rends ces observations accessibles sans affaiblir les contrôles, puis relance le chantier et vérifie qu’il avance vraiment. »
Mechanism (agent interpretation): for a published recipe-establishing ticket,
settle captures an independent command observation before dispatch. It exercises
start/stop on an additional disposable product of the same commit and dataset,
records whether its process and port remain, and probes existing local TCP
listeners before and after. It extracts the published convoy prototype references
through prototype-conformance anchors in the clean launched checkout, checks the
named dataset bytes against the approved Git objects, and reports declared screen
addresses. No private planning profile or author handoff is read. TCP reachability
is not a claim about the functional health of a neighbouring service.

The disposable trial keeps a `.trial` launch record beside the preparation.
An interrupted capture leaves it for the next reap; it is never reused as a
dataset environment. The report retains the pre-stop process identities so a
survivor is still detectable after removal of its checkout.

The ordinary evidence-capture command seals the actual output against the first
product's commit and address. The brief keeps verifying that same sealed
observation after a dataset switch; only `environments` changes to the current
product. The brief exposes controller_observation with the piece, fingerprint,
path and output; failures remain visible for the Evaluator's judgement.
No state is inferred from that report. There is no exemption from
piece_refusal, no imported report text, and no relaxation of criteria, freshness,
independence or the merge gate. observe refuses agent sessions; the evaluator
reads the report without gaining repository or process-control access.

When the operator resolves an evaluation Planning Exception and its parking is
lifted through convoy-state lift-park, the next pass may evaluate the same commit
again. It retains the prior round and negative verdict until new independent
states are recorded. One lift only covers the older refusal: a refusal after the
lift requires a new resolution. Neither a code review refusal nor an unobserved
criterion is waived by a lift.

## Validated simple expectations

For a ticket establishing the first launch recipe, the active Factory descriptor
can declare expectations while its `launch` is still absent. The evaluator
uses that descriptor's expectations with the recipe read from the ticket's
exact commit. Keep those expectations unchanged during an open evaluation:
the brief and the recorded comparison must describe the same pass.

The Factory-owned project descriptor may declare `validated_expectations` for
simple values that an approved criterion or Spec story and validated data or
prototype fix. This is a project-specific mapping; the author cannot change it
by changing the product commit. Each entry has `scope` (`ticket` or `outcome`),
`owner` (ticket or convoy ID, to distinguish reused local numbers), the frozen subject `number` and exact `text`, a declared `dataset`, a `source`
with a human-reviewable `reference` and `sha256:` `digest`, a typed `expected`
value (boolean, number or exact text), and an `observation` with an HTTP `path`
and JSON `pointer`. For example:

```json
{"scope":"outcome","number":3,"text":"As an operator, I want suspension status...",
 "dataset":"factory-suspended",
 "source":{"reference":"approved factory-suspended scenario","digest":"sha256:..."},
 "expected":true,"observation":{"path":"/status","pointer":"/suspended"}}
```

The entry's source citation and digest must be checked against the approved
data or prototype when the Factory descriptor is reviewed. Code matches the
entry to the frozen text and exposes it with the evaluated commit in the
Evaluator brief. The Evaluator captures that URL while the named dataset is
open and returns the piece as `comparisons: [{"id": N, "evidence": "..."}]`.
Code verifies the seal, commit, launched address and capture command, then
compares the typed scalar in the captured JSON. It computes the consequence:
a contrary value is `not_observed` even if the Evaluator claims `observed`;
an incomplete or contradictory declared expectation is `unobservable` with
cause `criterion`, leading to Planning Exception. A missing or forged capture
is refused. Criteria without an applicable declared simple expectation stay
with the existing Evaluator judgment and evidence rules. Every declared
dataset still requires coverage evidence.

For an interface ticket with changed Playwright references, the brief also
contains `visual_changes`: before/after PNG paths exported from exact commits and the visual
intent declared by that ticket. The Evaluator reads the images, checks them
against the launched product and intent, and records a cited `screen_findings`
entry with a sealed screenshot when they disagree. Initial captures are
excluded. The record gate accepts the visual check only with an exact
`DESIGN.md` rule at the evaluated commit; a finding makes the verdict
unfavorable.
