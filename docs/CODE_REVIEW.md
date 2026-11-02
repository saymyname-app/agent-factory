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
- It is the **one review of the ticket** (ADR-0030 L3): no test review
  precedes the freeze, so the reviewer also reads the criterion tests the
  freeze sealed (`.tests.criterion_tests`, `.tests.frozen` of the brief,
  read from the registry `tdd_freeze`) against the ticket's criteria — does
  each observe its criterion and fail on the observation that makes it
  false; on the Factory's repository, is it a double of a lower test
  (`docs/TEST_GUIDELINE.md`)? Such a finding blocks under the same citation
  rule (the criterion line of the ticket, or that guideline). A
  `gc.flow.test_review` left on a ticket in flight is not read. The brief
  names under `.tests.satisfied` the criteria whose tests already passed at
  the start commit (ADR-0030 L5), never proven red: for each, the closed
  question « would its test fail on a product where that criterion is
  false? » is asked, and a « non » blocks under the same citation rule.
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
./bin/code-review show    af-convoy af-t1 [--repo <project repository>] # rounds, open request, verdict, models; with --repo, `behind`
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

**No reviewer is sent on a branch that has not taken the integration tip**
(T44, Spec §6). Before it sends a reviewer — to open a round, review or
judgement, or for the one relaunch of a launch that gave no result —
`settle` checks that the ticket branch contains the current tip of the
integration branch (`git merge-base --is-ancestor <integration tip> <ticket
tip>`). When it does not, the launch is refused: the ticket is listed under
`refused` with `cause: "behind"`, `integration` (the tip of the integration
branch) and `commit` (the tip of the ticket branch), the reason names both
commits, and `settle` exits 1. No round is opened, no reviewer session is
launched, nothing is written in the tracker. A review already sent and still
awaited when the integration branch moves is not refused: it stays
`pending`; only a new launch is. `show --repo` gives the same fact, read
only, under `behind`: `{"integration": <sha>, "commit": <sha>}` when the
reviewer the next settlement would send would be refused for that reason,
else `null`. `bin/convoy-advance` reads it and hands the ticket back to its
author, cause `behind` (`docs/CONVOY_ADVANCE.md`).

| State of the review | What `settle` does |
|---|---|
| none, or favorable at an older commit than the tip | opens a **review** at the tip: a commit added after a verdict has it replayed (Spec §8), targeted after the first (ADR-0034, below) |
| favorable at the tip | nothing: the merge may follow |
| unfavorable review at an older commit than the tip, no correction round taken and no answer given (the author was resumed outside the round, af-s31cvi) | opens a **review** at the tip, replayed (targeted, its old Blocking Findings unsettled): no session would answer the old findings |
| unfavorable review, a Blocking Finding without an answer | waits (`respond`) |
| unfavorable review, every Blocking Finding answered | opens a **judgement** at the tip, against the reviewed commit |
| unfavorable judgement under the current judgement contract | nothing more opens, nothing merges; `bin/correction-round settle` stops the ticket, still refused after its correction round (`docs/CORRECTION_ROUND.md`) |
| unfavorable judgement at the tip under an older judgement contract | invalidates that judgement and its verdict, clears its `still_refused` stop when present, then opens exactly one new **judgement** at the same commit under the current contract; no author round opens |
| a round open at a commit the author has since left | replaced by one at the tip |

## Revue ciblée après le premier passage (ADR-0034)

Intent (Benjamin, ses mots, 2026-10-23 16:07 Paris) : « 3. ok pour ta
recommandation D1. » et « 4. je suis la recommandation que tu me donneras
pour ca, fait le choix parfait pour moi stp. »
Mechanism (interprétation agent) : la première revue d'un ticket reste
complète ; toute revue suivante (« replayed » dans le tableau ci-dessus :
après un tour de correction, après des commits ajoutés à une revue
favorable, après une revue défavorable dépassée, sur la pointe d'un ticket
dont les constats ont reçu une dérogation) est **ciblée**.

`bin/code-review` calcule son périmètre à l'ouverture et
`bin/convoy-state open-code-review` le vérifie (`scope` de la demande puis
de la passe) :

| Champ | Contenu |
|---|---|
| `from` | la pointe jugée par la dernière passe |
| `unsettled` | les Blocking Findings que cette passe laisse non soldés, moins ceux qui ont reçu une dérogation |
| `changed` | par fichier, les plages de lignes du commit revu ajoutées ou modifiées à la fois dans le diff propre du ticket (depuis la base de fusion avec la branche d'intégration, comme `bin/ticket-exit`, #714) et dans `from..commit` : les commits d'intégration repris ne sont pas des lignes du ticket |

Le relecteur reçoit tout le diff et, sous `.scope` du brief, ce périmètre
(le texte de chaque constat non soldé). Un constat ne peut bloquer que s'il
redonne un constat non soldé (`carries`) ou pointe une ligne de `changed`
(`location: {path, line}`), en plus de la règle de citation. Un constat
donné bloquant hors du périmètre est enregistré **non bloquant**, raison
sous `demoted`, `finishing_pass: true` ; `show` les liste sous
`finishing_pass`, pour la passe de fin (la revue de fin du diff assemblé,
`bin/spec-end-review`, relit de toute façon tout le diff de la Spec). Les
questions fermées d'une revue ciblée ne portent que sur les fichiers de
`changed`. `.scope` vaut `null` pour la première revue, qui reste complète.

Une ligne de `changed` attribue provisoirement le constat au ticket : une
modification syntaxique peut envelopper un comportement déjà présent dans la
base du ticket sans l'introduire. Si l'auteur le conteste, le jugement reçoit
donc aussi `reviewed_diff`, le diff original `base...commit` qui a produit le
constat et son `scope`. Le second relecteur juge l'attribution : un comportement
déjà présent dans `base`, inchangé sémantiquement par le ticket, est soldé ; un
comportement introduit par le ticket ou une vraie interaction entre son
changement et le contexte hérité reste défavorable.

**La revue ne juge pas la fidélité visuelle** (ADR-0032, ADR-0034) : la
formule `mol-code-review` laisse de côté la part d'un critère qui demande
que l'écran ressemble à sa référence, dans la lecture des tests de critère
comme dans la question `amended_test`, dont le texte le redit. Seul le
reste du critère est jugé (comportement, clavier, débordement, focus,
valeurs affichées).

## What the reviewer is given

`brief` is the preparation command: its output is everything the reviewer
session receives.

| Field | Content |
|---|---|
| `diff` | the fixed point (`base`), the command `git diff <base>...<commit>`, the changed files, the SHAs of the commits |
| `spec` | the id and the text of the Spec the convoy delivers; the formula writes only its « Testing Decisions » to `code-review-spec.md` and the reviewer reads another section by heading only when the ticket or one of its criteria cites it (af-s1yzo9: a Spec can run to ~100 KB; the citation check still uses the whole text) |
| `ticket_text` | the approved ticket: title, description, criteria, demonstration line, covered user stories, Declared Scope |
| `standards` | the standards files found at the reviewed commit (`AGENTS.md`, `CONTRIBUTING.md`, `CODING_STANDARDS.md`, `docs/agents/*`, `DESIGN.md`, …): a hint, the skill looks for them itself |
| `records` | the records written by scripts: the proven TDD steps, the evidence fingerprints, the merge record, and the *records* of the Ticket Handoff |
| `tests` | the test perimeter, the frozen harness, the frozen criterion tests with their fingerprints, the listed seams (the profile's entry points, and under `declared` the seams it names with the mode of each) |
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
| `amended_test` | each frozen criterion test file the one amendment changed (`amendment.files` of the piece `tdd_amendment`, `bin/tdd-step amend`) | does the amended test still observe its criterion (comportement, clavier, débordement, focus…)? Its visual fidelity to the prototype is not judged (ADR-0032, ADR-0034) |

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
The judgement brief carries both `.diff` (the correction diff) and
`.reviewed_diff` (the original reviewed diff, including the targeted scope),
so a contest that says the behavior was inherited can be checked against the
ticket base instead of being rejected merely because the behavior still
exists at the tip.

The judgement request and its recorded round carry the deterministic contract
version `code-review-attribution/v2`. That version covers the judgement inputs
and instructions, including `reviewed_diff`; it is bumped when either changes.
An unfavorable judgement without that version (or with an older one) is kept
in `rounds` with `invalidated` naming the new version, and `settle` sends one
replacement judgement at the same commit. The normal fresh-session and two-
launch no-result controls apply to that replacement. A favorable old judgement
is not replayed; an unfavorable result already rendered under the current
version remains terminal, so settlement cannot loop.

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
whose request could not be sent is raised by the next pass. `bin/convoy-advance`
then resumes the ticket once per stop, within K (cause `code_review_no_result`,
`docs/CONVOY_ADVANCE.md`, af-wu6xj7): the request is withdrawn, the stop kept
on the resume, the spent round dropped, and the next finished exit is
reviewed afresh. An answer of the operator to that request leaves it stopped.

A dispatch the door refuses or defers launched nothing: it counts no launch
and its bead is closed. A deferral is listed under `deferred` and tried
again by the next pass; a refusal is listed under `refused` and makes
`settle` exit 1.

## A fresh session per review

One reviewer session renders one round (Spec §5, T42). Two things hold it:

- `agents/delivery-reviewer/agent.toml` carries the work query of the
  author agent: a session that has ever been assigned a bead is offered, of
  the unassigned work, only that of the workflows it already works. Once it
  has rendered its round it is offered nothing and leaves; the next round
  starts a new session, or wakes this one: gc 1.5.0 wakes a drained session
  again under the same name, and the agent's `wake_mode = "fresh"` makes
  that wake start a fresh conversation instead of resuming the last one.
- When routed work of another workflow already waits as the session ends,
  Gas City 1.5.0 keeps the warm seat for it and cancels the drain-ack: the
  seat answers no_work and kept the role's one seat until `idle_timeout`
  (2 h) while the waiting launches expired (17/10, T59; af-epkrcv).
  `bin/delivery-seat-release`, run every 2 min by
  `orders/delivery-seat-release.toml`, closes a reviewer or Evaluator
  session that has served, holds no open bead, while ready routed
  work of another workflow waits; Gas City then starts a fresh session for
  it. A seat that never served, or whose own workflow has the ready work,
  is left alone. Each close is a line of `var/delivery-seat-release.log`.
- A round handed in by a session that already rendered a code review or a
  Ticket Evaluation of the convoy (or a review of tests recorded before
  ADR-0030 L3) is refused: the launch it answered is marked `refused` and
  gave no result, as above. That is also what holds the judgement to a
  second session: the conversation that reviewed cannot judge the answers
  (a session is its name and its conversation).

`record` signs with `GC_SESSION_NAME`, else `GC_SESSION_ID` — never
`GC_AGENT`, which names a place in the pool of the agent that the next
session takes — and with `"c:"` + `CLAUDE_CODE_SESSION_ID`, else `"g"` +
`GC_RUNTIME_EPOCH` as `conversation` (`docs/CONVOY_STATE.md`).

## Stored state

On the ticket, written by `bin/convoy-state` only (`docs/CONVOY_STATE.md`):

| Key | Value |
|---|---|
| `gc.flow.code_review` | `rounds`: each recorded round — `kind` (`review`, `judgement`), `commit`, `base`, `verdict`, `models`, `recorded_by`, `conversation` when known, `at`; a review with its `findings`, `answers` and, once given, `responses`; a judgement with its `judgements`, the optional historical `contract`, and `invalidated: {contract, at}` when a newer contract superseded it. `request`, while a round is open — `kind`, `commit`, `base`, `questions`, `models`, `launches` (`bead`, `at`, and `refused`: `{session, at}` when the session that answered had already served), `at`, and `contract` for a judgement |
| `gc.flow.verdict.code_review` | the verdict of the last effective round and the commit it judged; `invalidated` may name the same tip and the replacement judgement contract |
| `gc.flow.models` | per delivery role: `agent`, `provider`, `model`, `at` |
| `gc.flow.stop` | reason `code_review_no_result`, a one-line detail, and `raised` once the escalation door accepted the request |

## Avoiding reads for tickets with no work

Intent (Benjamin, his words, 2026-10-12): « corriger le flow par tranches ordonnées et vérifiées ».
Mechanism (agent interpretation): the initial convoy snapshot skips tickets
with neither an exit nor a stop before settlement. Their malformed state is
still refused. Every candidate is read again under its ticket lock before any
action, and changes made by an author after the snapshot are seen on the next
pass. This removes a full-convoy tracker read per unfinished ticket without
caching a verdict or authorising an action from stale state (af-8cfygl).

## Limits

- The findings are an agent's judgement. Code bounds them (closed axes,
  citation found in its source, closed questions, verdict computed); it does
  not check that the cited line really says the diff is wrong.
- The citation check is textual: the quote must be found in the Spec, the
  ticket or the named file. Any tracked file may be named as a written rule.
- The check of the integration tip is made when a reviewer is sent, not
  afterwards: a review sent before the integration branch moved is awaited
  and its verdict stands at that tip. The merge command still tests the
  merged result, and returns a conflict or a red to the author, whose new
  commit has the review replayed.
- This command hands no ticket back: `bin/convoy-advance` does, in its
  resumes. While the integration branch is red, only its repair is resumed:
  a ticket behind is not handed back until the branch is green again, and
  its review stays refused meanwhile.
- An internal test file is detected by the profile's test perimeter and by
  its name. A test that lives elsewhere under another name is not asked
  about.
- The models are the configured ones, not ones observed in the sessions.
- `record` checks that it runs in a read-only role session, not which one;
  a judgement is distinguished from the review by the session name.
- The Ticket Evaluation of the launched product is another control, sent
  by the same pass on the same tip (`docs/TICKET_EVALUATION.md`): the merge
  asks for both. It has no check of the integration tip of its own: it is
  kept off the old tip by the Ticket Exit the `behind` resume takes back.
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
dispatch door and the reviewer sessions. The integration tip (T44):
`test_no_review_is_launched_on_a_branch_that_has_not_taken_the_integration_tip`,
`test_a_branch_that_took_the_integration_tip_is_reviewed_as_before` and
`test_a_review_already_sent_is_awaited_when_the_integration_branch_moves`.
`tests/convoy-state-test.py` holds
each state write and its refusals, `tests/spec-integration-test.py` the
merge control, `tests/convoy-advance-test.py` the settlement by the pass,
`tests/ticket-author-test.py` the model of the author.
`tests/code-review-spec-scope-test.sh` runs the formula's own lines on a
sample brief: the reviewer is handed the ticket and the « Testing Decisions »
of the Spec, not the whole Spec.
`tests/delivery-seat-release-test.sh` holds the seat release.
`tests/code-review-isolated-city-test.sh` (local-only) replays the
demonstration line on a real controller, with the real order, the real
formula, the real dispatch door and merge command, and a scripted reviewer.
