# The ticket-end gate (T19, Spec af-wf4w5r §9)

## What it is for

In a convoy that carries the **new-flow mark**, a ticket is closed by one
gate and by nothing else: a closed, versioned list of nine conditions, each
read on the durable state of the convoy and on the evidence store. A merged
pull request and a green CI are not among them. The author never closes its
ticket. A ticket closed any other way is an anomaly, and the advance command
stops the convoy on it (`docs/CONVOY_ADVANCE.md`).

A convoy **without** the mark is not concerned: its tickets are closed by
`bin/deliver-close`, exactly as before.

`bin/ticket-end` is the gate. It writes one thing, through
`bin/convoy-state close-ticket`: the record of the gate and the closed status
of the ticket, in a single tracker write.

```bash
./bin/ticket-end check    af-convoy af-t1 --repo <project repository>                  # the nine verdicts; writes nothing
./bin/ticket-end check    af-convoy af-t1 --repo <project repository> --before-merge   # what the merge command asks
./bin/ticket-end settle   af-convoy --repo <project repository>                        # bin/convoy-advance, after the merge
./bin/ticket-end fidelity af-convoy --repo <project repository> --profile <descriptor> [--limit N]   # bin/convoy-advance, before the merge
./bin/ticket-end close    af-convoy af-t1 --repo <project repository>                  # one ticket; refused from an agent session
./bin/ticket-end measure  af-convoy af-t1 --repo <repository> --profile <descriptor> --commit <sha>   # bin/ticket-exit fidelity, for information; writes nothing
```

To know why a ticket is still open, run `check`: each condition has a
verdict and one line that says what was read.

## The nine conditions (list `ticket-end/v1`)

Every condition is read at the **tip of the ticket's branch**: the commit
that is, or was, merged.

| # | Name | Met when |
| --- | --- | --- |
| 1 | `criteria` | The acceptance criteria on the ticket have the fingerprint `bin/convoy-state mark` froze with the approved graph, under the same graph digest; the demonstration line the Ticket Evaluation judged is the ticket's (ADR-0030 L4: the frozen criterion tests prove the criteria). |
| 2 | `handoff` | Exit « terminé », a complete Ticket Handoff at the tip, its records sealed there; the Handoff names the red proof recorded on the ticket, sealed at its commit; the demonstration is sealed at the tip. A prefactoring: its regression instead of the red and of the demonstration. |
| 3 | `evaluation` | The last Ticket Evaluation is favorable at the tip, no evaluation is in progress, the demonstration line is « observed » with a sealed piece captured at the tip (a round recorded before ADR-0030 L4 with a state per criterion is read the same way). A prefactoring: the product started at the tip, with its piece. |
| 4 | `fidelity` | **Informative, never blocking** (ADR-0032, af-hcriwn): always met. Its detail says what was measured at the tip — « vert », or the count of deviations joined for the visual finishing pass, or that no measure was made there. |
| 5 | `deferral` | The deferral detector has a result at the tip (`deferral_markers` in the records of the Handoff) and every marker it found is declared under « non fait ». |
| 6 | `merge` | Merged into the integration branch at the tip; the merge commit is on that branch; the tests on the merged result are sealed at the merge commit and green. |
| 7 | `evidence` | Every piece of the ticket verifies (`bin/evidence-capture verify`: filed and sealed by the capture tool, matching its fingerprint), and the pieces that prove the merged state are tied to the tip. |
| 8 | `tdd` | Red, freeze and green are recorded, each with its sealed report at its commit; green is at the tip; the red report says `red` and carries its seam; the green report says `green`. A prefactoring: its regression at the tip says `unchanged`. |
| 9 | `review` | The code review is favorable at the tip with no Blocking Finding left without a favorable verdict; or every such finding carries Benjamin's recorded override (`bin/correction-round override`). |

After an amendment (`bin/tdd-step amend`), the red of conditions 2 and 8
is the one recorded at the commit of the amendment, proven by the piece
`tdd_amendment`; `tdd_red` stays the first red (`docs/TDD_STEP.md`,
af-9cjg26).

A ticket « touches a screen » when the publication door posed the reference
of the Validated Prototype in its description (`## Validated Prototype`,
T36). `bin/convoy-state show` renders it as `interface` and
`validated_prototype`.

Changing the list means a new version. `bin/convoy-state` holds the same
names and refuses a record that is not the nine conditions of the version
it knows, all passing.

## When each part runs

`bin/convoy-advance` calls the gate on each pass of its order
(`docs/CONVOY_ADVANCE.md`):

1. **Before the merge, `fidelity`.** For each finished interface ticket
   whose fidelity was not measured at its tip, it extracts the Validated
   Prototype named by the ticket (path at commit, read in the project
   repository) and runs `bin/prototype-fidelity check` at the tip, on the
   screens of the profile that serve a state of that prototype. Only the
   states of the reference the ticket names in its criteria or demonstration
   line are measured, every one when it names none (af-lvhakk). The result
   is recorded on the ticket by that command (`docs/PROTOTYPE_FIDELITY.md`).
   One ticket per pass (`--limit 1`).
2. **The merge asks `check --before-merge`.** `bin/spec-integration merge`
   merges a ready ticket only when conditions 1 to 5 and 7 to 9 are met.
   Otherwise the ticket is listed under `waiting` with the text of the
   gate, and nothing is merged (`docs/SPEC_INTEGRATION.md`).
3. **After the merge, `settle`.** Each merged ticket that is still open is
   checked on its nine conditions. All met: the ticket is closed with the
   record of the gate. Otherwise it stays open, nothing is written, and
   the pass lists it under `ticket_end.open` with what is missing.

## The record

```json
{"at": "…", "commit": "<tip that was merged>", "version": "ticket-end/v1",
 "conditions": [{"number": 1, "name": "criteria", "verdict": "pass", "detail": "…"}, "… nine entries"]}
```

It is stored as `gc.flow.gate.ticket_end` and rendered under
`gates.ticket_end` by `bin/convoy-state show`. `bin/convoy-state
close-ticket` writes it together with `status closed`
(`docs/CONVOY_STATE.md`); `record-gate --gate ticket_end` is refused.

## Refusals and exit status

Every answer is one JSON object on stdout.

| Exit | Meaning |
| --- | --- |
| 0 | Done: `check` found every asked condition met; `close` closed the ticket; `settle` and `fidelity` ran (tickets left open or red are listed, not failures). |
| 1 | Refused, or a condition is missing: each is named (`condition N (label) non réunie : …`). Nothing is written. |
| 3 | The convoy is in an « état sans règle »: nothing is closed. |
| 4 | The convoy does not carry the mark. |

- `close` and `settle` are refused from an **agent session** (`GC_AGENT`,
  `GC_SESSION_NAME` or `GC_SESSION_ID` set), whatever its role: only the
  order of the Factory runs them. `check` is open to anyone.
- `bin/deliver-close` refuses every closing form on a ticket that carries
  the mark and names this gate. Parking (`--outcome blocked`) is unchanged.
- A ticket stopped `still_refused` whose every unsettled Blocking Finding
  is overridden may be merged and closed (condition 9). No other stopped
  ticket is.

## Limits

- **The author may see the fidelity first.** `bin/ticket-exit fidelity`
  runs `measure` (the same check at the head commit, without captures,
  written nowhere) for information; nothing refuses on it (ADR-0032).
- **A red fidelity is not run again at the same tip**, and nothing sends the
  ticket back to its author: the resumes of T20 (`docs/CONVOY_ADVANCE.md`)
  do not cover a ticket this gate leaves waiting. Once its code review and
  its evaluation accept that tip, `bin/correction-round settle` stops it and
  raises it to the operator (`docs/CORRECTION_ROUND.md`, af-ckbood); any
  other missing condition still leaves it waiting.
- **The link ticket → screen is not recorded at publication.** Every screen
  of the profile that serves a state of the ticket's Validated Prototype is
  compared.
- **Fidelity with a real browser is slow** against the 300 s timeout of the
  order; hence one ticket per pass.
- **A fidelity check that cannot run** (no screen serves a state of the
  prototype, the prototype is not at the named commit) is a refusal of the
  pass, repeated at each pass until the profile or the reference is fixed.
- **Condition 5 reads the detector's result**, as `bin/ticket-exit` recorded
  it at the exit; the gate does not run the detector again.
- **The gate closes tickets only.** The end of a Spec is verified by
  `bin/spec-end` (T23, `docs/SPEC_END.md`), which reads the records of this
  gate; a convoy does not close itself here (T22).

## Proof

- `tests/ticket-end-test.py`: the command lines on a fake tracker state,
  with a copy of the Delivery Fixture City in a throwaway repository. Every
  piece is filed by the real `bin/evidence-capture`, the merge is the real
  `bin/spec-integration`, the fidelity check the real
  `bin/prototype-fidelity`. One test for the pass, one per missing
  condition (nine), each refusal re-reading the tracker, the store and the
  branches.
- `tests/convoy-advance-test.py`: the pass measures the fidelity of an
  interface ticket, merges it and closes it; a merged ticket that misses a
  condition stays open and is named; a ticket closed with a record that
  lacks the nine verdicts stops the convoy.
- `tests/convoy-state-test.py`: `mark` freezes the criteria, `close-ticket`
  and each of its refusals. `tests/deliver-close-test.sh`: the refusal on a
  marked ticket, and every existing close on an unmarked one.
- `tests/fixture-city-oracle-test.py`: one ticket observed state by state
  from published to closed by the gate (`docs/FIXTURE_CITY_ORACLE.md`).
- `tests/ticket-end-isolated-city-test.sh` (local-only): the real
  controller, order and tracker in a disposable city.
