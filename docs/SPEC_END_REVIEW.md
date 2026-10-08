# The end code review of a Spec, on its assembled diff (T25, Spec af-wf4w5r §6 « Fin de Spec », §9 point 4)

## Status and purpose

In a convoy that carries the **new-flow mark**, each ticket is reviewed
before its merge (`docs/CODE_REVIEW.md`). That review sees one ticket. Two
tickets, each correct alone, may contradict each other on a line of the Spec
once assembled, and no per-ticket review can see it (user story 58).

Once the end-of-Spec gate has rendered its three mechanical verdicts on one
tip of the integration branch (`docs/SPEC_END.md`), code — never an author —
sends **the whole diff of that tip against the protected branch** to a
reviewer in a fresh context: one session of the read-only reviewer role,
started as routed work through `bin/dispatch-door --role reviewer`, on the
formula `mol-end-review`, which calls Matt Pocock's `code-review` skill
unchanged. The rules are those of the review of a ticket: a finding blocks
only with a citation that is found in its source. The end-of-Spec gate reads
the result as its sixth condition, `end_review`, on its own commit, beside
the Outcome Evaluation (`docs/OUTCOME_EVALUATION.md`), which is made in
parallel on that same commit.

A convoy **without** the mark is not concerned: every command answers « pas
un convoi du nouveau flux » (exit 4) and writes nothing.

```bash
./bin/spec-end-review show   af-convoy [--repo DIR]               # where the end review stands; reads only
./bin/spec-end-review settle af-convoy [--repo DIR]               # what is due; run by bin/convoy-advance at each pass
./bin/spec-end-review brief  af-convoy [--repo DIR]               # the reviewer session: its preparation record
./bin/spec-end-review record af-convoy --file FILE [--repo DIR]   # the reviewer session: what it hands in
```

Every answer is one JSON object on stdout. Exit status: 0 done; 1 refused or
could not run; 4 the convoy does not carry the mark.

## When the review is due

`settle` decides from the tracker and the branches alone, under a lock per
convoy; a second call on the same state does nothing. The review is due on
the **commit of the gate** (`convoy.spec_end.commit`) while the three
mechanical verdicts hold: every ticket closed, the integration branch not
red, that commit still the tip of the integration branch, and the tip of the
protected branch still held by it. Otherwise `settle` answers `waiting` with
the reason, and launches nothing.

`bin/convoy-advance` calls `settle` in the pass that ran the gate, right
after `bin/outcome-evaluation settle`: the Outcome Evaluation and the review
are launched by the pass that recorded the three verdicts, both on their
commit, and neither waits for the other (`docs/CONVOY_ADVANCE.md`).

| `action` | Meaning |
| --- | --- |
| `waiting` | Not due: the reason is given. |
| `launched` / `relaunched` | A request was opened on the commit of the gate and a review bead routed to the reviewer role (`bead`, `launches`, `extent`). |
| `pending` | A launch is running; `deadline` says until when. |
| `deferred` | The dispatch door deferred the launch: nothing is counted, the next pass tries again. |
| `reviewed` | A complete round exists on this commit: `outcome`, `blocking`, and `repairs_due` for the Blocking Findings whose drafted repair is not published yet. |
| `stopped` | The review is stopped on this commit (`stop`); `raised` says whether this call sent the request to the operator. |
| `escalated` | A stop that had not reached the operator was raised by this call. |

## What the reviewer is given

`brief` prints the **preparation record** of the review, and everything the
session is given:

- `diff`: `scope` (« tout le diff de la branche d'intégration … contre la
  branche protégée … »), `fixed_point` and `command`, `files` (status and
  path), `commits`, and `extent` — `files`, `commits`, `insertions`,
  `deletions` counted by code, and `digest`, the `sha256:` of the sorted
  paths. The extent is stored with the request; a brief whose diff no longer
  has that extent is refused.
- `spec`: the approved Spec, read on its bead.
- `tickets`: the approved text of every ticket of the convoy that a resolved
  Planning Exception did not withdraw — description, criteria, demonstration
  line, user stories.
- `standards`: the files of the repository that usually hold its written
  rules (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `docs/agents/…`), a
  hint for the Standards axis of the skill.
- `models` and `independence` (see « Models »), and `review_shape`, the
  shape of what `record` takes.

It is given **nothing of an author but the committed diff**: no Ticket
Handoff, no note or comment of a ticket bead, no commit message.

## What the reviewer hands in, and what code makes of it

`record` is accepted only from a read-only role session
(`DELIVERY_ROLE_READ_ONLY=1`, `bin/delivery-role-sandbox`) and only while a
request is open. The file holds `commit` (the commit of the request),
`coverage` (`axes` run, `files` reviewed) and `findings`. A `verdict` or an
`outcome` given by the reviewer is refused: **the outcome is computed**.

| Rule | What code does |
| --- | --- |
| Citation | A finding blocks only if it cites a line of the Spec (`spec`), of a ticket of the convoy (`ticket`, with the `ticket` id), or a written rule of the repository (`repo_rule`, with its `path`), and the quote — at least 12 characters, spaces folded — is found in that source at the reviewed commit. Otherwise it is recorded as non-blocking, with `demoted` and the reason. |
| Drafted repair | Each Blocking Finding comes with the `repair` its reviewer drafted: `title`, `what_it_delivers`, `restores` (`kind` among `user_story`, `anchor`, `spec_line`, `repo_rule`, and `ref`), `demonstration_line`, `acceptance_criteria` (each `entry_point`, `observable`, `false_if`). A Blocking Finding without one, or a malformed draft, refuses the whole record. |
| Coverage | Code compares `coverage.files` to the files of the diff and stores how many were read and which were left out (the first 20 named, `missing_count` beyond). |
| Outcome | `incomplete` when an axis (`standards`, `spec`) or a file of the diff is left out; else `unfavorable` with a Blocking Finding; else `favorable`. |

There is no « corrigé / contesté » at the end of a Spec: a Blocking Finding
is answered by its repair.

Each round is stored with its `commit`, the `base` it was read against, its
`extent`, `coverage`, `findings`, `models`, the session that recorded it,
`launched_at` and `duration_seconds` (from its launch to its record).

## A Blocking Finding becomes a repair, published by code

On a `reviewed` answer with `repairs_due`, `bin/convoy-advance` publishes
each draft through the patch door (`bin/ticket-graph-publish`), as any added
ticket: the title and the text name the finding, the commit of the review
and the cited line. It then names the ticket on the finding
(`bin/convoy-state set-end-review-repair --ticket`). From there the repair
is an ordinary ticket: started by the pass, written by an author, reviewed,
evaluated, merged, closed by the ticket-end gate.

A draft the patch door refuses is recorded on the finding with the reason
(`--refused`); the next `settle` stops the review (`end_review_repair_refused`)
and raises it once to the operator. Each finding gets its repair once.

## Replayed in full on each new tip

A round says nothing of another commit than its own. The merge of a repair
moves the tip of the integration branch: the gate replays its three
verdicts there, `settle` opens a new request on the new commit, and **another
session reviews the whole diff again**. A request left on an earlier commit
is replaced; a verdict of an earlier round is never read for the new tip.
On a commit that already has a complete round, no second review is opened.

An unfavorable review counts **one round of the end of the Spec**
(`counters.end_rounds`) in the write that records it. The round is counted
once per tip, whichever source refuses that tip first: `gc.flow.end_round`
keeps the commit and the source of the last round counted.

## What the gate reads

`bin/spec-end` reads condition 6, `end_review` (list `spec-end/v3`), on the
commit its three verdicts are recorded on, and renders nothing there
(`docs/SPEC_END.md`). It is read whatever conditions 4 and 5 — the Outcome
Evaluation and the findings « hors ticket » — say. It is met only by a
complete, favorable round **on that very commit**. The gate refuses and says
which case it is:

- absent: no review of the assembled diff on this commit;
- running: launches counted, and whether the last output was incomplete;
- stopped without a verdict;
- tied to another commit;
- a Blocking Finding without a favorable verdict — each named with its
  repair (published, refused, or not published yet).

## Models

At the request, `bin/convoy-state` stores the models the review runs under:
the model of each author of the convoy (as recorded on its ticket), the
model the reviewer role is configured on, and `same_model`. `brief` and
`show` render it as `independence`: null when the reviewer runs on another
model than every author; « revue non indépendante » when it runs on the
model of an author; « indépendance de modèle non établie » when a model is
not recorded. It is never left out, and it refuses nothing.

## A review that gives no result

A launch gives no result when `timeout_seconds` passed since it was sent
(`config/delivery-flow.json`, `end_review`; 7200 s, far above the one measure of « Proof »), when its review bead was closed while the request is still
open, or when its output is `incomplete`. It is not a passed review: the
gate goes on refusing. The review is launched **once more**, on a new bead,
for a new session. When that second launch gives no result either, the
review is stopped on its commit (`end_review_no_result`) and raised once to
the operator through `bin/escalation-door`, on a bead of its own;
`bin/convoy-state end-review-stop-raised` records it, and a stop whose
request could not be sent is raised by the next `settle`.

An incomplete output is recorded as a round, with its duration and the files
it left out: it is what an adoption trial reads to say whether the review
held on a diff of a real size.

A dispatch the door refuses or defers launched nothing: it counts no launch
and its bead is closed.

## Stored state

On the convoy, written by `bin/convoy-state` only (`docs/CONVOY_STATE.md`):

| Key | Value |
| --- | --- |
| `gc.flow.end_review` | `rounds`: each recorded round — `commit`, `base`, `outcome`, `findings`, `coverage`, `extent`, `models`, `recorded_by`, `launched_at`, `duration_seconds`, `at`. `request`, while a review is open — `commit`, `base`, `extent`, `models`, `launches` (`bead`, `at`, and `result: incomplete`), `at`. `stop` — `reason`, `detail`, `commit`, `at`, then `bead` and `raised`. |
| `gc.flow.end_round` | `commit`, `source`, `at`: the tip the last round of the end was counted for. |
| `gc.flow.counter.end_rounds` | the rounds of the end of the Spec, every source together. |

Settings: `config/delivery-flow.json`, `end_review` — `formula`, `role`,
`rig`, `timeout_seconds`. `mol-end-review` is in the `formulas` list of
`config/projects/agent-factory.toml`; only `bin/spec-end-review` dispatches
it.

## Limits

- **The findings are an agent's judgement.** Code bounds them (closed axes,
  citation found in its source, drafted repair of a closed shape, outcome
  computed); it does not check that the cited line really says the diff is
  wrong, nor that the drafted repair restores it.
- **Coverage is declared.** Code checks that the reviewer lists every file
  of the diff and both axes; it cannot check that a listed file was read.
- **The citation check is textual**, as in the review of a ticket. Any
  tracked file may be named as a written rule.
- **« En même temps que l'Outcome Evaluation » means the same pass and the
  same commit.** The pass that records the three verdicts settles the
  Outcome Evaluation, then the review, one after the other; the two sessions
  then run side by side. A dispatch the door defers puts one of them a pass
  later.
- **`end_rounds` is counted, and compared to no bound yet.**
- **Nothing lifts a stop of the end review on its tip.** A new tip opens a
  new review; on the same tip the gate goes on refusing.
- **No closed questions on the tests at the end**: they are asked per ticket.
- **The reviewer role holds one session at a time**: an end review waits
  behind a ticket review, and the time of a launch runs from the dispatch.
- **The models are the configured ones**, not ones observed in the sessions.
- **The time limit has one measure behind it**: one real reviewer session
  on 50 files and about 14,000 changed lines took 548 s (see « Proof »);
  7200 s is far above it, and no real convoy has been reviewed yet.

## Proof

- `tests/spec-end-review-test.py`: the command lines on a fake tracker
  state, with a copy of the Delivery Fixture City in a throwaway repository
  and its own remote; the gate is the real `bin/spec-end`, a stop is read
  back from the list of the real `bin/escalation-door`. One test per pass
  and per refusal, each refusal re-reading the tracker. No agent runs in CI:
  `tests/fixtures/spec-end-review/reviewer` stands in for the dispatch door
  and the reviewer sessions.
- `tests/spec-end-test.py`: condition 6 of the gate — absent, running,
  stopped, tied to another commit, with a Blocking Finding, favorable.
- `tests/fixture-city-oracle-test.py`: the delivery driver of the Fixture
  City walks the gate with a stand-in for the reviewer of the end.
- `tests/convoy-state-test.py`: each state write and its refusals.
- `tests/convoy-advance-test.py`: the settlement by the pass — the review
  launched by the pass that renders the mechanical verdicts, on their commit,
  with the Outcome Evaluation — and the drafted repairs published through the
  patch door.
- `tests/convoy-stops-fixture-city-test.py`: on the graph published by the
  real publication door, the drafted repair of a Blocking Finding is
  published by the real patch door, and the review is replayed in full on
  the new tip.
- `tests/spec-end-review-isolated-city-test.sh` (local-only): the
  demonstration line on a real controller, with the real order, gate,
  formula, dispatch door, publication and patch doors and tracker, and a
  scripted reviewer. The pass that renders the three verdicts launches the
  review and the Outcome Evaluation on their commit (the real
  `bin/outcome-evaluation` on the launched product, with the stand-in of its
  suite for the Evaluator, called in place of the dispatch door); the gate
  then passes its six conditions on the tip that holds the repair. Passed on
  2026-10-08 (gc 1.4.1).
- `tests/spec-end-review-real-session-test.sh` (local-only, and only with
  `SPEC_END_REVIEW_TRIAL_SESSION=1`: it costs a model session): one real
  session of the reviewer role, with its prompt, its `code-review` skill and
  its read-only profile, reviews a range of this repository's own history of
  the size of a real convoy. Its record says how long the review took and
  whether its output covers both axes and every file. Run on
  2026-10-08 (`delivery-reviewer`, `claude-readonly`, claude-opus-5-5; ten
  commits, 50 files, +10091 −3917): **the review held** — a complete output
  in 548 s, 50/50 files and both axes, 21 findings of which 5 blocking, each
  cited and with its drafted repair. The Spec of the trial is synthetic: the
  findings of the Spec axis say nothing of that code.
