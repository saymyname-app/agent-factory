# Review of the criterion tests before the freeze (T13, Spec af-wf4w5r §5, §8)

## Status and purpose

`bin/tdd-step` proves that the criterion tests of a ticket were written
first and seen red. It does not prove that a test observes its criterion: a
test that only checks a status 200 is red on a route that does not exist yet
and green on a product that does nothing of what the criterion says.

Between the red proof and the freeze, a **test reviewer** reads the tests: a
session of the read-only reviewer role, in a fresh context, that did not
write them. It answers one question per criterion test — does it observe its
criterion, and would it fail on the observation that makes the criterion
false? Code computes the verdict, binds it to the commit and to the
fingerprints of the files the freeze seals, and `bin/tdd-step freeze` refuses
without it. A refusal returns once to the author; a second one stops the
ticket. A review that gives no result is not a passed one.

`bin/test-review` runs the review. Its state lives in the tracker, read and
written through `bin/convoy-state` only. A convoy without the new-flow mark
is not touched (exit 4).

```bash
./bin/test-review review af-convoy af-t1 --repo <ticket worktree>     # the author, after tdd-step red
./bin/test-review settle af-convoy                                    # bin/convoy-advance, at each pass
./bin/test-review brief  af-convoy af-t1                              # the reviewer session (formula mol-test-review)
./bin/test-review record af-convoy af-t1 --verdict-file verdict.json  # the reviewer session
./bin/test-review show   af-convoy af-t1                              # the passes, the open request, the stop
```

Every answer is one JSON object on stdout.

| Exit | Meaning |
|---|---|
| 0 | done; `review`: every criterion test passed the review, the freeze can follow |
| 1 | refused, or could not run (`{"ok": false, "error": "refus : …"}`) |
| 2 | `review`: the reviewer refused at least one test; it returns to the author with the reasons (`refused`) |
| 4 | the convoy does not carry the mark: « pas un convoi du nouveau flux » |
| 5 | the ticket is stopped (`"stopped": true`, `stop`: the reason) and was raised to the operator |
| 6 | `review`: no verdict yet (`"pending": true`); the same command, run again, resumes the same review |

## The sequence

1. **Red.** The author commits the criterion tests and has them proven red
   (`bin/tdd-step red`, `docs/TDD_STEP.md`).
2. **Request.** The author runs `review`. The command reads the red proof at
   HEAD from the evidence store, computes the fingerprints of what the freeze
   will seal (the criterion → test table, each criterion test file, the
   frozen harness paths) and opens the review on them.
3. **Launch.** It creates a review bead and routes it through
   `bin/dispatch-door --role reviewer` on the formula `mol-test-review`
   (`config/delivery-flow.json`, `test_review`). A new session of the
   reviewer role claims it.
4. **Verdict.** The reviewer asks `brief` — the criteria of the ticket, the
   tests that prove each of them, the files as they were proven red, the one
   question — and hands one answer per test to `record`: `favorable`, or
   `unfavorable` with a reason. It gives no overall verdict:
   `bin/convoy-state` computes it. The brief carries nothing of the author
   but its tests: no Handoff, no note, no session.
5. **Favorable**: `review` exits 0 and the author freezes
   (`bin/tdd-step freeze`).
6. **Unfavorable**: `review` exits 2 with each refused test, the criteria it
   proves and the reason. The author corrects the tests, commits, has them
   proven red again, and runs `review` again: a new request, a new reviewer
   session. Tests refused and left unchanged are not reviewed again.
7. **Second refusal**: the ticket is stopped (`test_review_refused`), in the
   same tracker write as the verdict. `review` exits 5.

`review` waits for the verdict up to `--wait` seconds (default 540, under
the ten minutes of one tool call) and exits 6 when none came. Nothing is
kept in the session: the request, its launches and the verdict are in the
tracker, and a second call resumes from there.

## What binds the verdict to the tests

A pass of the review records the commit it judged and the fingerprint
(`sha256:`) of each file. `bin/tdd-step freeze` computes the same
fingerprints at HEAD and refuses, before anything is written:

- no recorded verdict, or a review still open;
- a last verdict that refuses at least one test (each named with its reason);
- a verdict given at another commit than the one being frozen;
- a verdict bound to other fingerprints than those of the files to freeze
  (each differing file named).

`bin/convoy-state set-tdd --step freeze` holds the same order under its
lock: it refuses a freeze without a favorable verdict at the same commit,
whoever calls it.

A freeze that ends an **amendment** asks for no test review: an amended test
is read by the code review of the ticket (Spec §6, T14).

## A review that gives no result

A launch gives no result when `timeout_seconds` passed since it was sent
(`config/delivery-flow.json`, `test_review`; 1800 s, a value without a
measured base), or when its review bead was closed while the request is
still open. It is not a passed review: nothing is recorded as a verdict and
the freeze stays refused. The review is launched **once more**, on a new
bead, for a new session. When that second launch gives no result either,
the ticket is stopped (`test_review_no_result`).

A dispatch the door refuses or defers (no adoption trial for the role, total
provider exhaustion, low memory) launched nothing: it counts no launch, its
bead is closed, and `review` exits 1 with the door's reason. In `settle`, a
deferral is listed under `deferred` and tried again by the next call; a
refusal is listed under `refused` and makes the command exit 1.

## A stopped ticket reaches the operator once

When the review stops a ticket, the command asks `bin/escalation-door
benjamin` for the ticket itself, then records through `bin/convoy-state
stop-raised` that the door accepted it. The ticket is one line of
`bin/escalation-door list`, whatever the number of later calls; a stop whose
request could not be sent (the door refused, the mail failed) is raised by
the next call. An answer of the operator is not followed by a second
request.

A stopped ticket takes no further step: `bin/tdd-step` refuses every step,
the gates of `bin/ticket-author` refuse it, so the author's sequence ends
there and `bin/spec-integration` merges nothing of it. Lifting a stop is not
in this command.

## Without the author session

`settle` does what is due on every ticket of a convoy from the tracker
alone: it launches a review that is open and was never sent, launches once
more one left without result, stops the ticket when the relaunch gave none
either, and raises a stop that did not reach the operator. A second call on
the same state does nothing. `bin/convoy-advance` runs it at each pass on
every convoy that has a review open or such a stop
(`docs/CONVOY_ADVANCE.md`), so an author session that died while waiting
does not leave a review unsettled. `review` goes through the same code,
under a lock per ticket: a review is never launched twice for one deadline.

## Stored state

On the ticket, written by `bin/convoy-state` only (`docs/CONVOY_STATE.md`):

| Key | Value |
|---|---|
| `gc.flow.test_review` | `rounds`: each recorded pass — `commit`, `files` (path → fingerprint), `verdict`, `tests` (test id → `state`, and `reason` when unfavorable), `recorded_by` (the reviewer session), `at`; `request`, while a review is open — `commit`, `files`, `criteria` (the criterion → test table), `launches` (`bead`, `at`), `at` |
| `gc.flow.stop` | reason `test_review_refused` or `test_review_no_result`, a one-line detail, and `raised` once the escalation door accepted the request |

The verdict is not written under `gc.flow.verdict.test_review`: a verdict of
that family holds only while its commit is the tip of the ticket branch
(Spec §8), and the review of the tests holds for the frozen tests, which the
code of the ticket is committed after.

## Limits

- The question is judged by an agent. Code bounds the answer (one per test,
  closed states, reason required, verdict computed, fingerprints bound); it
  does not check that a reason is true.
- `record` checks that it runs in a read-only role session
  (`DELIVERY_ROLE_READ_ONLY`, set by `bin/delivery-role-sandbox`), not which
  session it is.
- The reviewer role holds one session at a time
  (`agents/delivery-reviewer/agent.toml`): a review waits behind another one,
  and the time of a launch runs from the dispatch, not from the moment its
  session starts.
- A reviewer session always answers the review that is open on its ticket
  at the moment it asks its brief, whichever launch it came from. A session
  that arrives once the verdict is given (the first launch answered after
  the relaunch, a step Gas City handed to a second session) finds no open
  review, records nothing and ends: one short session spent for nothing.
- A helper of the test perimeter that is neither a criterion test file nor a
  declared harness path has no fingerprint; the verdict is bound to it by
  the commit only.
- Nothing lifts a stop yet, and nothing resumes a stopped ticket.

## Proof

`tests/test-review-test.py` drives the command lines on a fake tracker
state, against a copy of the Delivery Fixture City whose red and freeze are
proven by the real `bin/tdd-step`, with the real `bin/escalation-door` read
back from its list: one test per pass and per refusal, each refusal
re-reading the tracker. No agent runs in CI:
`tests/fixtures/test-review/reviewer` stands in for the dispatch door and
the reviewer session. `tests/tdd-step-test.py` and
`tests/convoy-state-test.py` hold the refusals of the freeze and of each
state write; `tests/convoy-advance-test.py` the settlement by the pass.
`tests/test-review-isolated-city-test.sh` (local-only) replays the three
cases — a refusal corrected then frozen, a second refusal, a review without
result — on a real controller, with the real formulas, the real dispatch
door and a scripted author and reviewer.
