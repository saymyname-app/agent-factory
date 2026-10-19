# Ticket Exit, Ticket Handoff and deferral detector (T11, Spec af-wf4w5r §5)

## Status and purpose

`bin/ticket-exit` is how the author of a ticket of a convoy that carries the
**new-flow mark** ends its work: by one structured call, never by free text.
Each **Ticket Exit** has a destination fixed by code. The **Ticket Handoff**
is recorded on the ticket in the tracker: four sections written by the
author, and records written by code. A convoy without the mark is not
touched (exit 4).

The author formula ends its sequence with it (`docs/TICKET_AUTHOR.md`).
The ticket-end gate reads the Handoff (condition 2) and the detector's
result (condition 5) at the tip of the branch (`docs/TICKET_END.md`).
`bin/convoy-advance` reads the exit on each pass and sends an interrupted
ticket, a blocked ticket whose repair is closed, and a parked ticket whose
request was answered, to one fresh author session on the same branch; each
resume is counted, and the third parks the ticket (T20,
`docs/CONVOY_ADVANCE.md`).

« terminé » on a `vertical_slice` or a `repair` is refused without the
demonstration proof: the piece `demonstration`, verified by the evidence
store, captured on the launched product at the head commit of the ticket
branch (`bin/ticket-author demonstrate`). The records of the Handoff carry
it as `demonstration_proof`.

« terminé » on a ticket that carries a Validated Prototype is refused while
its fidelity is red at the head commit (af-r2c0tx). Intent (Benjamin, his
words, 2026-10-19 15:50 Paris): « fais mesurer la fidélité par l'auteur avant
sa sortie ». Mechanism (agent interpretation): the exit runs `bin/ticket-end
measure`, the check `bin/ticket-end fidelity` runs after the exit, on the
same states, without its side-by-side captures and writing nothing: at most
2 to 4 minutes on T02R2 and T02R (the measure was sealed that soon after
their exit), where the recorded check, captures included, ended 9 to 15
minutes after it. The
refusal names the open deviations and the answer lists them all under
`fidelity`, each once with its number of renderings; an anchor Benjamin
accepted does not refuse. The author repairs, or exits by
`planning_exception --anchor` for a deviation to have accepted (below). The
recorded check of the ticket-end gate stays the final control.

```bash
./bin/ticket-exit exit af-convoy af-t1 --exit finished --repo <ticket worktree> --handoff handoff.json
./bin/ticket-exit exit af-convoy af-t1 --exit planning_exception --repo <ticket worktree> --handoff handoff.json --kind semantic --summary "La Spec fixe X, la démonstration demande Y" [--anchor liste]
./bin/ticket-exit exit af-convoy af-t1 --exit operator_request --request request.json
./bin/ticket-exit exit af-convoy af-t1 --exit technically_blocked --repair repair.json
./bin/ticket-exit exit af-convoy af-t1 --exit interrupted --repo <ticket worktree> [--handoff partial.json]
./bin/ticket-exit read af-convoy af-t2                       # the ticket as its author receives it
./bin/ticket-exit deferral af-convoy af-t1 --repo <ticket worktree> [--handoff handoff.json]
./bin/ticket-exit fidelity af-convoy af-t1 --repo <ticket worktree>   # the fidelity at HEAD, as « terminé » measures it
```

Every answer is one JSON object on stdout.

| Exit | Meaning |
|---|---|
| 0 | done |
| 1 | refused (`{"ok": false, "error": "refus : …"}`). Nothing was written, unless the answer carries `written`: what was already done when a later step refused |
| 4 | the convoy does not carry the mark: « pas un convoi du nouveau flux » |

An exit is accepted on a ticket that was started through the dispatch door
and is not closed. A later exit replaces the one recorded (a resumed ticket
exits again).

## The five exits

| `--exit` | Asks for | What the code does | Effect on the convoy |
|---|---|---|---|
| `finished` | `--repo`, `--handoff` (complete); a fidelity not red at HEAD on a ticket with a Validated Prototype | seals the records, writes the Handoff, then the exit | none: the code review (`docs/CODE_REVIEW.md`) and the Ticket Evaluation on the launched product (`docs/TICKET_EVALUATION.md`) follow, in parallel |
| `planning_exception` | `--repo`, `--handoff` (its four sections), `--kind semantic\|topology`, `--summary` (one line) | seals the records, writes the Handoff, then the Planning Exception; sends the question to the operator through `bin/escalation-door benjamin`, parks, writes the exit | the ticket and every ticket that waits for it are parked |
| `operator_request` | `--request` (`quoi`, `pourquoi`, `que_faire`) | sends the request through `bin/escalation-door benjamin`, parks, writes the exit | the ticket and every ticket that waits for it are parked |
| `technically_blocked` | `--repair` (the fields of a `repair`) | drafts a revision that adds the `repair` in front of the ticket and sends it through `bin/ticket-graph-publish bd-patch`, writes the exit | the ticket waits for the repair; nothing is parked, the rest goes on |
| `interrupted` | `--repo`, optional `--handoff` (partial) | pushes the branch to `origin`, seals the records, writes a partial Handoff, then the exit | none: a fresh session resumes on the same branch |

`operator_request` and `technically_blocked` also take `--repo` and
`--handoff` for a partial Handoff. Everything the author gives is read
before anything is written.

**Planning Exception.** `--kind` is what `bin/planning-exception classify`
calls a Planning Exception (`semantic`, `topology`); `repair` is refused: a
technical defect outside the ticket exits by `technically_blocked`, and a
defect in the Factory's own tools or tests by `operator_request`
(`docs/TICKET_AUTHOR.md`, « Factory defects are fixed on main »). The
request on the operator's list reads « Planning Exception (kind) sur
<ticket> : <summary> ». It is written on the ticket before the request
leaves (`bin/convoy-state raise-planning-exception`, `docs/CONVOY_STATE.md`).

**The Ticket Handoff first** (T41, af-rqgtpi; Spec §3, user story 20). A
Planning Exception is refused without a Ticket Handoff (`--repo`,
`--handoff`) that has its four sections, each with content or `"aucun"`:
the refusal names the section that is missing, and nothing is written. The
Handoff is sealed and written on the ticket before the Planning Exception
is, so the exception is raised on what the Handoff says. That Handoff is
recorded `partial`: only the Handoff of a `finished` exit is read as the
account of a finished ticket by the gates that follow.

**A deviation from the Validated Prototype** (T16, Spec §3) is never decided
by the author: it exits by a Planning Exception that names the anchors
(`--anchor`, repeatable; refused on any other exit and for a malformed
name). The deviation is written in the Handoff first: the exit is refused
when the « Écarts » (`deviations`) of the Handoff does not mention each
anchor named, by its whole name: `fixture` is not named by `fixture.items`,
`fixture:items` or `fixture-items`, while the « . », « , » or « : » that
punctuates a sentence after the name does not hide it. The request then carries a third option, « Accepter l'écart sur
l'ancre <name> », and the ticket records the letter the escalation door
gives it. Once the operator answers by that letter (`bin/escalation-door
repondre`), the fidelity check reads the deviation as « accepté par
Benjamin » (`docs/PROTOTYPE_FIDELITY.md`); any other answer leaves it red.
The option must fit one line of 140 characters: a long list of anchors is
several Planning Exceptions.

**Every Planning Exception has an accept path** (ADR-0030 L5). Without an
anchor, the request carries a third option too, « Accepter l'écart que
décrit le Ticket Handoff », and the ticket records its letter: answered by
it, the exception is `accepted` (no anchor is) and `bin/convoy-advance`
lifts the parking and resumes the ticket, like any accepted deviation;
the option's consequence says so (« Le ticket reprend avec cet écart. »).
Without an anchor, an empty « Écarts » refuses the exit: the option would
accept nothing. A ticket stopped by a script (`criterion_already_green`:
all its criteria already green) stays stopped: the answer lifts no stop,
and `bin/convoy-advance` then raises that stop to the operator; on such a
ticket the consequence says that instead (« Le parcage est levé, pas
l'arrêt … : l'arrêt te revient pour le clore comme satisfait. »).

**Operator request.** The file is the request the operator reads, as the
escalation door takes it: `quoi` and `pourquoi` on one line of at most 140
characters each, `que_faire` a non-empty list of `{option, consequence}`.
The language and the blocking flag are set by code. The line `<ticket> —
<quoi>` then appears in `bin/escalation-door list`. The door also takes an
optional `lien`, the link of a dossier, which a Ticket Exit never sets
(T26, `docs/CONVOY_ADVANCE.md`, « The rounds of the end are bounded »).

**Parking.** `bin/convoy-state park` writes the parking on the ticket and on
every ticket of the convoy that waits for it, directly or not, read on the
tracker's `blocks` edges (`docs/CONVOY_STATE.md`). `bin/convoy-advance` does
not start a parked ticket and reports it under `waiting`; the tickets that
wait for none of them keep starting. A parking is lifted by
`bin/convoy-advance`, on the operator's answer (T20,
`docs/CONVOY_ADVANCE.md`): any answer to an `operator_request`; for a
`planning_exception`, only the option that accepts the deviation. The
ticket is then sent to a fresh author session (cause `answered`) and the
tickets behind it are startable again.

**Technically blocked.** `--repair` is a JSON object with exactly `title`,
`what_it_delivers`, `restores` (`{kind, ref}`), `demonstration_line` and
`acceptance_criteria` (`[{entry_point, observable, false_if}]`), the fields
the entry contract asks of a `repair` (`docs/ENTRY_CONTRACT.md`). The code
sets the rest: the key (`R1`, `R2`, …), the kind, the target rigs of the
blocked ticket, no blocker. It files a revised draft bead (no approval) that
carries the blocked ticket as published, with the repair among its blockers,
and its blockers still open; the patch door holds the repair to the entry
contract and publishes it, marked and tracked by the convoy. If the door
refuses, the revision bead is closed and the exit is refused.

One defect, one repair (af-q6j79b). When an open repair of the convoy
already restores what this one restores (the same `restores`, or for a
`repo_rule` a rule of the same file), no repair is added: the revision only
puts that repair among the ticket's blockers, and the answer names it with
`"attached": true`. A ticket it already blocks gets nothing new. On 16/10,
T59 published R2 (af-q8a2oe) for the defect R1 (af-qsloqo) was repairing;
R2 then reached Benjamin as a Planning Exception.

The door reads what the repair cites against its source
(`docs/ENTRY_CONTRACT.md`, T40): a user story or a line in the Spec, an
anchor in its Validated Prototype, a rule in its file at the commit of the
integration branch (`ref`: `<path> : <rule>`). A red control
(`restores.kind: red_check`) must be one the convoy carries a record of:
the exit records the control the author names on the ticket first
(`bin/convoy-state record-blocking-red`, shown among `convoy.red_checks`),
and withdraws it if the door refuses the repair.

**Interrupted, and a session that ended without an exit.** `read` renders a
started ticket that is `in_progress`, has no recorded exit, and whose
session (`assignee`, `gc.session_name`, `gc.session_id`) is closed or absent
from `gc session list`, as `{"exit": "interrupted", "declared": false}`.
Nothing is written: the tracker keeps saying that no exit was declared.

## The Ticket Handoff

`--handoff` is a JSON object with the four sections of the author and
nothing else:

| Section | Field | Content |
|---|---|---|
| Fait | `done` | per criterion, the observation obtained; how to see the demonstration line |
| Écarts | `deviations` | delivered otherwise than the ticket or the Spec, within the approved intent |
| Non fait | `not_done` | what the ticket asked for and is missing |
| Constats hors ticket | `out_of_ticket` | defects or improvements seen elsewhere |

Each section is `"aucun"` or a non-empty list of one-line items. An item of
`not_done` may be `{"what": "<line>", "paths": ["<file or directory>"]}`:
`paths` is what the deferral detector matches. `finished` is refused when a
section is absent or empty, or when the file carries any other field, and
so is `planning_exception`; a partial Handoff may leave sections out.

**Records.** No option and no field carries them: they are computed by
`ticket-exit records`, run inside `bin/evidence-capture command
--expect-exit 0`, so they are a sealed piece of the evidence store
(`handoff_records`, `docs/EVIDENCE_STORE.md`) whose fingerprint is on the
ticket. `bin/convoy-state set-handoff` then writes the Handoff (sections,
`partial`, the commit, the records) and refuses records that have no
`handoff_records` piece at the same commit.

| Record | Content |
|---|---|
| `branch`, `head`, `base` | the ticket branch checked out in `--repo`, its HEAD, and the start commit proven by the red step |
| `commits` | every commit of `base..head`, with its subject |
| `files_changed`, `files_outside_declared_scope` | the files that differ, and those outside the Declared Scope (`null` when the ticket declares none). The scope bounds nothing: this is a record, never a refusal |
| `red_proof` | the step (`red`, or `prefactoring`), its commits, its piece and fingerprint |
| `amendment` | the commit and reason of the ticket's amendment of a frozen test, if any |
| `deferral_markers` | every marker found: `path`, `line`, `marker`, `text`, `declared` |
| `pushed` | `interrupted` only: the remote, branch and commit read back from `origin` |

`finished` is refused without a proven red (`bin/tdd-step red`, or
`prefactoring`): the records start from the commit it proved. `--repo` must
hold the ticket branch (the one `bin/convoy-state set-branch` recorded, when
one is) with no tracked file differing from HEAD.

**Who receives it.** `read CONVOY TICKET` renders the ticket (text, kind,
demonstration line, criteria, Declared Scope), its exit, its parking, its
own Handoff, and under `blocker_handoffs` the Handoff of each direct blocker
that is closed (`null` for a blocker closed without one). The Evaluator and
the reviewer do not call it.

## The deferral detector

It reads the lines the ticket **added** between the start commit and HEAD
and looks for a marker, whatever the case: `TODO`, `FIXME`, « not wired »
(or « not yet wired »), « à brancher ». A marker is declared when an item of
`not_done` names its file, or a directory above it, in `paths`. `finished`
is refused while a marker is not declared; the refusal names file, line and
marker. Declared or not, every marker is listed in the records. On another
exit the markers are recorded and refuse nothing.

`deferral` runs the detector alone, against `--handoff` or the Handoff on
the ticket: exit 0 when it passes, 1 with the markers when it refuses. It
writes nothing. `fidelity` does the same for the fidelity check at HEAD:
exit 0 when it is green, accepted or « sans objet » (no Validated
Prototype), 1 with the deviations when it is red.

## Limits

- The detector is a net by markers (Spec §0): a deferral written without one
  of these words passes it. The real guard is the demonstration line,
  evaluated on the launched product.
- A marker in a line the ticket added on purpose (a test datum, a quoted
  text) has to be declared like any other.
- The exit, the Handoff and the parking are separate tracker writes. If one
  refuses after another passed, the answer says what was written; the same
  call again completes it.
- A revision the patch door refuses leaves one closed draft bead behind.
- The Planning Exception is recorded on the ticket (`planning_exceptions`),
  as a parking and as a request to the operator. It is not written into a
  `bin/planning-exception` register: no register is attached to a marked
  convoy yet.
- Nothing here resumes a ticket, lifts a parking, or counts a resume:
  `bin/convoy-advance` does, from the exit recorded here (T20,
  `docs/CONVOY_ADVANCE.md`). Every Planning Exception has an option the
  code reads as accepting it (ADR-0030 L5); one raised before L5 without an
  anchor has none, and its parking is not lifted by the pass.

## Proof

`tests/ticket-exit-test.py` drives the command lines on a fake tracker
state: one test per pass and per refusal, each refusal re-reading the
tracker, the evidence store and the remote to prove nothing was written. The
records are sealed by the real `bin/evidence-capture`, the requests go
through the real `bin/escalation-door`, the parked convoy is advanced by the
real `bin/convoy-advance`, and the repair is published by the real patch
door on the graph of the Fixture City. The fidelity before « terminé » is measured by the real `bin/ticket-end` and
`bin/prototype-fidelity` on the launched Fixture City, with the fake browser
of `tests/fixtures/prototype-fidelity`. `tests/convoy-state-test.py` covers
`set-handoff` and `park`. On the real `gc`/`bd`, in a disposable city
(local-only): `tests/convoy-state-real-tracker-test.sh` (a 20 kB Handoff
read back as written, a parking that follows real `blocks` edges) and
`tests/ticket-graph-publish-new-flow-real-tracker-test.sh` (the exit
« bloqué technique » through the real patch door).
