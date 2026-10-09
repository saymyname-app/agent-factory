# Code review of a ticket before its merge (T14, Spec af-wf4w5r §6, §8)

## Status and purpose

The author of a ticket is never the judge of its code. Once a ticket of a
convoy that carries the **new-flow mark** is finished and green, the flow —
not the author — sends its committed diff to a **reviewer**: a session of the
read-only reviewer role, in a fresh context, on another model than the
author's when one is configured. The reviewer calls Matt Pocock's
`code-review` skill unchanged (two axes: Standards, Spec) and hands in
findings; code decides what they are worth.

- A finding **blocks only if it cites** a line of the Spec, a line of the
  ticket, or a written rule of the repository, and the cited line is found
  in that source. Anything else is recorded and blocks nothing.
- A **closed question** on the tests answered « non » is a Blocking Finding.
- Each **Blocking Finding** is answered « corrigé » or « contesté », and a
  **second reviewer session** judges that closed list.
- `bin/spec-integration` **merges nothing** without a favorable verdict at
  the tip of the ticket branch. A review that is absent, open, crashed or
  without output is not an agreement.

`bin/code-review` holds the review. Its state lives in the tracker, read and
written through `bin/convoy-state` only. A convoy without the mark is not
touched (exit 4): it is merged as before.

```bash
./bin/code-review settle  af-convoy [--repo <project repository>]       # bin/convoy-advance, at each pass
./bin/code-review brief   af-convoy af-t1                               # the reviewer session (formula mol-code-review)
./bin/code-review record  af-convoy af-t1 --file result.json            # the reviewer session
./bin/code-review respond af-convoy af-t1 --file responses.json         # the fresh author session, after a refusal
./bin/code-review show    af-convoy af-t1                               # rounds, open request, verdict, models
```

Every answer is one JSON object on stdout.

| Exit | Meaning |
|---|---|
| 0 | done |
| 1 | refused, or could not run (`{"ok": false, "error": "refus : …"}`); `settle`: a ticket was refused (listed under `refused`) |
| 4 | the convoy does not carry the mark: « pas un convoi du nouveau flux » |

## When a review is due

`settle` decides from the tracker and the ticket branch alone, ticket by
ticket. A review is opened at the tip of the ticket branch when:

- the Ticket Exit is « terminé » and the complete Ticket Handoff was taken at
  that tip (`bin/ticket-exit`);
- the ticket is **green at that tip**: the `green` step of `bin/tdd-step`
  (the `prefactoring` step, for a `prefactoring`) is recorded at that commit;
- the ticket is not stopped, parked, closed, or already merged at that tip.

The diff under review is the ticket's own: from the merge base of the ticket
branch and the integration branch of the Spec (`bin/spec-integration`) to
the tip. A ticket that is not there yet is listed under `waiting` with the
reason. A second call on the same state does nothing.

| State of the review | What `settle` does |
|---|---|
| none, or favorable at an older commit than the tip | opens a **review** at the tip: a commit added after a verdict has it replayed in full (Spec §8) |
| favorable at the tip | nothing: the merge may follow |
| unfavorable review, a Blocking Finding without an answer | waits (`respond`) |
| unfavorable review, every Blocking Finding answered | opens a **judgement** at the tip, against the reviewed commit |
| unfavorable judgement | nothing more opens, nothing merges; `bin/correction-round settle` stops the ticket, still refused after its correction round (`docs/CORRECTION_ROUND.md`) |
| a round open at a commit the author has since left | replaced by one at the tip |

## What the reviewer is given

`brief` is the preparation command: its output is everything the reviewer
session receives.

| Field | Content |
|---|---|
| `diff` | the fixed point (`base`), the command `git diff <base>...<commit>`, the changed files, the SHAs of the commits |
| `spec` | the id and the text of the Spec the convoy delivers |
| `ticket_text` | the approved ticket: title, description, criteria, demonstration line, covered user stories, Declared Scope |
| `standards` | the standards files found at the reviewed commit (`AGENTS.md`, `CONTRIBUTING.md`, `CODING_STANDARDS.md`, `docs/agents/*`, …): a hint, the skill looks for them itself |
| `records` | the records written by scripts: the proven TDD steps, the evidence fingerprints, the merge record, and the *records* of the Ticket Handoff |
| `tests` | the test perimeter, the frozen harness, the frozen criterion tests with their fingerprints, the listed seams (the profile's entry points) |
| `questions` | the closed questions on the tests (below) |
| `models`, `independence` | the model of the author and of the reviewer, and the mention when they are identical or not known |

**Neither the Ticket Handoff nor any prose of the author.** The four
sections of the Handoff are not in the brief; of its records, the subject of
each commit and the reason of an amendment are left out (commits are given
by SHA, markers by file and line). The formula tells the reviewer not to
read commit messages, bead notes, mail or the author's session.

For a **judgement** the brief gives instead the Blocking Findings of the
reviewed round with their citations, the answer given to each, and the
correction diff (from the reviewed commit to the tip). The reason of a
« contesté » is the author's, by construction: it is what is judged.

## What the reviewer hands in, and what code makes of it

`record` runs only in a read-only role session (`DELIVERY_ROLE_READ_ONLY`,
set by `bin/delivery-role-sandbox`). The reviewer gives no verdict: a
`verdict` field is refused.

**A review** hands in `findings` and `answers`:

```json
{"commit": "<reviewed commit>",
 "findings": [{"axis": "spec", "blocking": true, "summary": "…",
               "citation": {"source": "spec", "quote": "<the cited line, copied>"}}],
 "answers": {"Q1": {"answer": "non", "reason": "…"}}}
```

- `axis`: `standards` or `spec` — the two axes of the skill stay apart.
- `citation.source`: `spec`, `ticket`, or `repo_rule` (with `path`, a file of
  the repository at the reviewed commit).
- A finding given as `blocking` is **recorded as non-blocking**, with the
  reason under `demoted`, when it has no citation, a malformed one, a quote
  shorter than 12 characters, or a quote that is not found (spaces folded) in
  the Spec, in the ticket (description and demonstration line), or in the
  named file. While a repository has no written rule, the Standards axis can
  therefore block nothing.
- Findings are numbered `F<round>.<n>` by code.

**The closed questions** (Spec §6, « troisième vérification ») are asked by
code, not found by the reviewer:

| Kind | Asked for | Question |
|---|---|---|
| `internal_test` | each file of the diff that sits in the test perimeter of the profile, or looks like a test file, and is neither a frozen criterion test nor a frozen harness path | does it go through a listed seam? |
| `amended_test` | each frozen criterion test file whose content at the tip is no longer the one the test reviewer read (`bin/test-review`) | does the amended test still observe its criterion? |

Each takes `oui` or `non` (with a reason). A « non » becomes a Blocking
Finding of axis `tests`, written by code. An answer left out, or to a
question that was not asked, refuses the whole record.

**The verdict** is computed by `bin/convoy-state`: unfavorable as soon as
one finding blocks. It is written as `gc.flow.verdict.code_review`, at the
reviewed commit, in the same tracker write as the round.

## « Corrigé » or « contesté », judged by a second session

After an unfavorable review, `respond` records the answer to **every**
Blocking Finding of that round, and nothing else:

```json
{"responses": {"F1.1": {"response": "fixed", "commit": "<commit of the correction>"},
               "F1.2": {"response": "contested", "reason": "…"}}}
```

A `fixed` names a commit of the ticket branch that follows the reviewed
commit. Once the author has finished again at the tip (or at the same tip,
when everything is contested), `settle` opens the **judgement** and sends it
to a new reviewer session, which gives one state per Blocking Finding —
`favorable`, or `unfavorable` with a reason — and no new finding. A
judgement recorded by the session that made the review is refused. The
verdict is favorable only if every Blocking Finding is judged favorably.

The fresh author session that answers is the one of the ticket's single
correction round, started by `bin/correction-round` once this review and the
Ticket Evaluation have both answered (`docs/CORRECTION_ROUND.md`). A ticket
whose answers are judged unfavorably is stopped there, and the operator may
then override a Blocking Finding with their words.

## The merge control

`bin/spec-integration merge` (`docs/SPEC_INTEGRATION.md`) leaves a finished
ticket under `waiting`, and merges nothing of it, unless the last round of
its code review is favorable, was given at the tip, no round is open, and
the verdict `code_review` is favorable and valid there. A favorable verdict
written without the review it comes from (`convoy-state set-verdict`) does
not pass.

## Models per role

`bin/ticket-author start` writes the model of the author role on the ticket
when its session takes it; `settle` writes the model of the reviewer role
before it opens a round (`bin/convoy-state set-model`, field `models`). Both
are the configured model: the provider `bin/provider-failover` gives the
role's agent, and that provider's `--model` in `city.toml`, else
`config/model-catalog.json` (`lib/delivery_role_identity.py`).

Each request and each recorded round carries `models: {author, reviewer,
same_model}`. Identical models do not refuse the review (Spec §6: same pool
admitted): `same_model: true` is recorded and `show` / `brief` say « revue
non indépendante : le relecteur tourne sur le même modèle que l'auteur ».
A model that could not be read gives `same_model: null` and « indépendance
de modèle non établie ». The mention is never left out.

## A review that gives no result

A launch gives no result when `timeout_seconds` passed since it was sent
(`config/delivery-flow.json`, `code_review`; 3600 s, a value without a
measured base), or when its review bead was closed while the request is
still open. It is not a passed review: no verdict is written and the merge
stays refused. The round is launched **once more**, on a new bead, for a new
session. When that second launch gives no result either, the ticket is
stopped (`code_review_no_result`) and raised once to the operator through
`bin/escalation-door`; `bin/convoy-state stop-raised` records it, and a stop
whose request could not be sent is raised by the next pass.

A round handed in by a session that already rendered a review of tests, a
code review or a Ticket Evaluation of the convoy is refused the same way
(Spec §5, T42; `docs/TEST_REVIEW.md`, « A fresh session per review »): the
launch it answered is marked `refused` and gave no result. That is also what
holds the judgement to a second session: the session that reviewed cannot
judge the answers. `record` signs with `GC_SESSION_NAME`, else
`GC_SESSION_ID`.

A dispatch the door refuses or defers launched nothing: it counts no launch
and its bead is closed. A deferral is listed under `deferred` and tried
again by the next pass; a refusal is listed under `refused` and makes
`settle` exit 1.

## Stored state

On the ticket, written by `bin/convoy-state` only (`docs/CONVOY_STATE.md`):

| Key | Value |
|---|---|
| `gc.flow.code_review` | `rounds`: each recorded round — `kind` (`review`, `judgement`), `commit`, `base`, `verdict`, `models`, `recorded_by`, `at`; a review with its `findings`, `answers` and, once given, `responses`; a judgement with its `judgements`. `request`, while a round is open — `kind`, `commit`, `base`, `questions`, `models`, `launches` (`bead`, `at`, and `refused`: `{session, at}` when the session that answered had already served), `at` |
| `gc.flow.verdict.code_review` | the verdict of the last round and the commit it judged |
| `gc.flow.models` | per delivery role: `agent`, `provider`, `model`, `at` |
| `gc.flow.stop` | reason `code_review_no_result`, a one-line detail, and `raised` once the escalation door accepted the request |

## Limits

- The findings are an agent's judgement. Code bounds them (closed axes,
  citation found in its source, closed questions, verdict computed); it does
  not check that the cited line really says the diff is wrong.
- The citation check is textual: the quote must be found in the Spec, the
  ticket or the named file. Any tracked file may be named as a written rule.
- The review is opened on the tip the author finished at. It does not ask
  that the ticket branch already contains the tip of the integration
  branch: the merge command tests the merged result, and returns a conflict
  to the author, whose new commit has the review replayed.
- An internal test file is detected by the profile's test perimeter and by
  its name. A test that lives elsewhere under another name is not asked
  about.
- The models are the configured ones, not ones observed in the sessions.
- `record` checks that it runs in a read-only role session, not which one;
  a judgement is distinguished from the review by the session name.
- The Ticket Evaluation of the launched product is another control, sent
  by the same pass on the same tip (`docs/TICKET_EVALUATION.md`): the merge
  asks for both.
- The reviewer role holds one session at a time: a review waits behind
  another one, and the time of a launch runs from the dispatch.
- Nothing lifts a stop yet. A ticket still refused after its judgement is
  stopped by `bin/correction-round`, not here.

## Proof

`tests/code-review-test.py` drives the command lines on a fake tracker
state, against a copy of the Delivery Fixture City in a throwaway repository
with its own remote; the merge control is the real `bin/spec-integration`,
and a stop is read back from the list of the real `bin/escalation-door`. No
agent runs in CI: `tests/fixtures/code-review/reviewer` stands in for the
dispatch door and the reviewer sessions. `tests/convoy-state-test.py` holds
each state write and its refusals, `tests/spec-integration-test.py` the
merge control, `tests/convoy-advance-test.py` the settlement by the pass,
`tests/ticket-author-test.py` the model of the author.
`tests/code-review-isolated-city-test.sh` (local-only) replays the
demonstration line on a real controller, with the real order, the real
formula, the real dispatch door and merge command, and a scripted reviewer.
