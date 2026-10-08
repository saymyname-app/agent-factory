# Convoy State (T33, T34, T10, T11, T13, T14, T15, T16, T17, T18, T19, T20, T22, T21, T23, Spec af-wf4w5r §0 rules 2 and 5)

## Status and purpose

`bin/convoy-state` is the only reader and writer of the durable state of a
convoy that carries the **new-flow mark**. The state lives in the tracker
(bead metadata under `gc.flow.*`), never in a session. Every other script of
the Delivery Workflow goes through this command; none writes a `gc.flow.*`
key itself. A field that is missing is added here, in the ticket that needs
it, with its closed list and its refusal test.

The code is `lib/convoy_state.py`; `bin/convoy-state` is its entry point and
holds nothing else. The delivery flow and its tests start this command
thousands of times, and Python keeps the compiled form only of what it
imports (af-xhryl7).

A convoy without the mark is not touched: `show` and every write answer
« pas un convoi du nouveau flux » (exit 4) and write nothing, so it is
published, dispatched, merged and closed exactly as before.

```bash
./bin/convoy-state list                                 # the open marked convoys, and apart those closed outside acceptance or abandon (bin/convoy-advance, bin/planning-artifacts-close)
./bin/convoy-state mark af-convoy \
  --demonstration-line af-t1="Sur le produit lancé, …" \
  --user-stories af-t1=4,12 \
  --establishes-launch-recipe af-t1 \
  --prototype-fold af-t1                                # publication door (T05, T06, T36)
./bin/convoy-state show af-convoy --repo rigs/product   # every reader
./bin/convoy-state set-branch   af-convoy af-t1 --branch ticket/af-t1
./bin/convoy-state set-session  af-convoy af-t1 --session <session name>   # bin/ticket-author start
./bin/convoy-state record-gate  af-convoy af-t1 --gate dispatch   # bin/dispatch-door --convoy, after the sling
./bin/convoy-state set-exit     af-convoy af-t1 --exit finished
./bin/convoy-state set-verdict  af-convoy af-t1 --kind code_review --state favorable --commit <sha>
./bin/convoy-state bump-counter af-convoy --ticket af-t1 --counter resumes --counter correction_rounds
./bin/convoy-state set-counter  af-convoy --counter end_rounds --value 0
./bin/convoy-state add-evidence af-convoy af-t1 --piece red_proof --digest sha256:<hex> --commit <sha>
./bin/convoy-state close-ticket af-convoy af-t1 --commit <merged tip> --file report.json   # bin/ticket-end: the record of the gate and the closed status, in one write
./bin/convoy-state set-tdd      af-convoy af-t1 --step red --commit <sha> --base <start sha>   # bin/tdd-step, once a step is proven
./bin/convoy-state stop-ticket  af-convoy af-t1 --reason criterion_already_green --detail "critère 2 déjà vert : …"   # bin/tdd-step
./bin/convoy-state open-test-review   af-convoy af-t1 --commit <sha> --file request.json   # bin/test-review review
./bin/convoy-state launch-test-review af-convoy af-t1 --bead af-review                     # bin/test-review, once the reviewer is sent
./bin/convoy-state record-test-review af-convoy af-t1 --file verdict.json                  # bin/test-review record
./bin/convoy-state stop-raised af-convoy af-t1                                              # once the escalation door accepted the stop
./bin/convoy-state set-model af-convoy af-t1 --role reviewer --agent delivery-reviewer --provider codex --model gpt-5.6-sol   # bin/ticket-author start (author), bin/code-review (reviewer)
./bin/convoy-state open-code-review    af-convoy af-t1 --kind review --commit <tip> --base <fixed point> [--file questions.json]   # bin/code-review settle
./bin/convoy-state launch-code-review  af-convoy af-t1 --bead af-review                    # bin/code-review, once the reviewer is sent
./bin/convoy-state record-code-review  af-convoy af-t1 --file result.json                  # bin/code-review record
./bin/convoy-state respond-code-review af-convoy af-t1 --file responses.json               # bin/code-review respond
./bin/convoy-state open-evaluation    af-convoy af-t1 --commit <tip> --file request.json  # bin/ticket-evaluation settle: the roles and the launched products
./bin/convoy-state launch-evaluation  af-convoy af-t1 --bead af-evaluation                # bin/ticket-evaluation, once the Evaluator is sent
./bin/convoy-state record-evaluation  af-convoy af-t1 --file states.json                  # bin/ticket-evaluation record
./bin/convoy-state record-startup     af-convoy af-t1 --commit <tip> --piece evaluation.startup --file environment.json   # bin/ticket-evaluation settle (or --detail "…" when the product did not start)
./bin/convoy-state release-evaluation af-convoy af-t1 --state-file <launch record> [--withdraw]   # bin/ticket-evaluation settle, once a launched product is stopped
./bin/convoy-state set-handoff af-convoy af-t1 --file handoff.json                                   # bin/ticket-exit
./bin/convoy-state park        af-convoy af-t1 --cause planning_exception --detail "La Spec fixe X, …"  # bin/ticket-exit
./bin/convoy-state set-fidelity af-convoy af-t1 --commit <sha> --piece fidelity --file result.json   # bin/prototype-fidelity
./bin/convoy-state raise-planning-exception af-convoy af-t1 --kind semantic --summary "…" [--anchor liste --accept-option c]   # bin/ticket-exit
./bin/convoy-state raise-planning-exception af-convoy af-t1 --kind semantic --summary "…" --item not_done.1 --accept-option b   # bin/spec-end: tracked elements left without a final state
./bin/convoy-state set-item-repair af-convoy af-t1 --repair af-r2   # bin/convoy-advance, once the patch door published the repair the operator asked for
./bin/convoy-state set-integration af-convoy --branch integration/af-spec --protected main --base <sha>   # bin/spec-integration open
./bin/convoy-state set-merge   af-convoy af-t1 --outcome merged --ticket-commit <sha> --integration <sha> --commit <sha>   # bin/spec-integration merge
./bin/convoy-state invalidate-verdicts af-convoy af-t1 --tip <sha> --kind code_review --kind evaluation   # bin/spec-integration merge
./bin/convoy-state open-correction   af-convoy af-t1 --commit <tip>          # bin/correction-round settle: the single correction round
./bin/convoy-state launch-correction af-convoy af-t1 --bead af-correction    # bin/correction-round, once the author session is sent
./bin/convoy-state override-finding  af-convoy af-t1 --finding F1.1 --approver <human approver> --words "…"   # bin/correction-round override
./bin/convoy-state open-resume   af-convoy af-t1 --cause interrupted --ref "session:<session name>"   # bin/convoy-advance: one resume counted, before the fresh author session is sent
./bin/convoy-state launch-resume af-convoy af-t1 --bead af-resume        # bin/convoy-advance, once the author session is sent
./bin/convoy-state park          af-convoy af-t1 --cause resumes_exhausted --detail "3 reprises, …"   # bin/convoy-advance, at the third resume
./bin/convoy-state lift-park     af-convoy af-t1 --request <answered request bead> [--option a]   # bin/convoy-advance, on the operator's answer
./bin/convoy-state record-grouped-request af-convoy --bead af-request [--signature sha256:<hex>] [--lift-option a --lifts af-t1]   # bin/convoy-advance
./bin/convoy-state clear-grouped-request  af-convoy     # bin/convoy-advance, once a ticket may advance again
./bin/convoy-state ticket af-t1                         # does this bead carry the mark? (bin/dispatch-door, the Mayor)
./bin/convoy-state record-incident af-convoy --bead af-incident [--signature sha256:<hex>]   # bin/convoy-advance
./bin/convoy-state clear-incident  af-convoy            # bin/convoy-advance, once the state is valid again
./bin/convoy-state record-integration-red af-convoy --commit <sha> --integration <sha> --protected <sha> --control "<line>" [--detail "<line>"] [--check fidelity] [--end-round]   # bin/spec-integration, bin/spec-end
./bin/convoy-state set-integration-repair af-convoy --ticket af-r1   # bin/convoy-advance, once the patch door published the repair
./bin/convoy-state clear-integration-red  af-convoy     # bin/spec-integration, once the control is green again
./bin/convoy-state record-spec-end af-convoy --commit <integration tip> --protected <protected tip> --file report.json   # bin/spec-end: three green verdicts, one commit
./bin/convoy-state open-outcome-evaluation    af-convoy --commit <commit of the gate> --file request.json   # bin/outcome-evaluation: the products launched, the roles
./bin/convoy-state launch-outcome-evaluation  af-convoy --bead af-e1          # bin/outcome-evaluation: the evaluation sent to an Evaluator session
./bin/convoy-state record-outcome-evaluation  af-convoy --file states.json    # bin/outcome-evaluation record: one state per user story; the verdict is computed
./bin/convoy-state release-outcome-evaluation af-convoy --state-file <launch record> [--withdraw]   # a stopped product; the open request withdrawn
./bin/convoy-state stop-outcome-evaluation    af-convoy --commit <sha> --reason story_unobservable --detail "…"   # or --raised once the operator was asked
./bin/convoy-state classify-finding   af-convoy af-t1 --item out_of_ticket.1 --as dismissed --recorded-by <session> --reason "…"   # bin/outcome-evaluation classify
./bin/convoy-state set-outcome-repair af-convoy --repair af-r3 --story 4      # bin/convoy-advance, once the patch door published a drafted repair (or --ticket af-t1 --item out_of_ticket.1)
./bin/convoy-state open-end-review        af-convoy --commit <commit of the gate> --file request.json   # bin/spec-end-review settle
./bin/convoy-state launch-end-review      af-convoy --bead af-review                 # bin/spec-end-review, once the reviewer is sent
./bin/convoy-state record-end-review      af-convoy --file result.json               # bin/spec-end-review record
./bin/convoy-state set-end-review-repair  af-convoy --finding F1 (--ticket af-r1 | --refused "<line>")   # bin/convoy-advance, after the patch door
./bin/convoy-state stop-end-review        af-convoy --reason end_review_no_result --detail "<line>"   # bin/spec-end-review settle
./bin/convoy-state end-review-stop-raised af-convoy --bead af-request                # bin/spec-end-review, once the escalation door accepted
```

Every answer is one JSON object on stdout.

| Exit | Meaning |
|---|---|
| 0 | done |
| 1 | refused, or could not run: nothing was written (`{"ok": false, "error": "refus : …"}`) |
| 3 | `show` or `ticket` found an « état sans règle »: the state is printed, with the reason |
| 4 | the convoy, or the ticket asked by `ticket`, does not carry the mark: « pas un convoi du nouveau flux » |

## Stored fields and closed lists

| Field | Key | On | Values |
|---|---|---|---|
| Mark | `gc.flow.mark` | convoy, ticket | `new-flow/v1` |
| Manual lifecycle | the label `owned` (Gas City's own: `gc convoy create --owned`) | convoy | added by `mark` in the same write as the mark, and again by a later `mark` if it was lost: `gc convoy check` leaves a convoy that carries it open once all its tickets are closed (T22) |
| Spec | `gc.spec_id` (read only: written by the publication door) | convoy | the id of the Spec the convoy delivers; the evidence store is filed under it (T09, `docs/EVIDENCE_STORE.md`) |
| Kind | `gc.ticket_kind` (read only: written by the publication door) | ticket | `vertical_slice`, `prefactoring`, `repair` |
| Demonstration line | `gc.flow.demonstration_line` | ticket (`vertical_slice`, `repair`) | one non-empty line, written once by `mark` |
| Covered user stories | `gc.flow.user_stories` | ticket (`vertical_slice`) | the numbers of the Spec's user stories the slice covers, at least one, each once; written once by `mark` |
| Launch recipe established here | `gc.flow.establishes_launch_recipe` | ticket (`vertical_slice`, at most one per convoy) | `true`, written with the mark; absent otherwise |
| Prototype Fold | `gc.flow.prototype_fold` | ticket (`vertical_slice`) | `true`, written with the mark; absent otherwise |
| Ticket branch | `gc.flow.branch` | ticket | branch name |
| Author session | `gc.flow.session` | ticket | `name`, `at`; the same write puts the ticket `in_progress` with `gc.session_name`. Refused for a session that already took another ticket of the convoy, for a ticket the dispatch door did not start, for a closed ticket |
| Ticket Exit | `gc.flow.exit` | ticket | `finished`, `planning_exception`, `operator_request`, `technically_blocked`, `interrupted` |
| Verdict | `gc.flow.verdict.<kind>` | ticket | kind: `test_review`, `code_review`, `evaluation`, `fidelity`; state: `favorable`, `unfavorable`; always with the full commit SHA it judged; `invalidated` (`tip`, `at`) once `invalidate-verdicts` wrote that a newer commit outdated it |
| Counter | `gc.flow.counter.<name>` | ticket: `resumes`, `correction_rounds`; convoy: `end_rounds` | integer ≥ 0 |
| Evidence fingerprint | `gc.flow.evidence.<piece>` | ticket | `sha256:<64 hex>` and the commit of the piece |
| Gate record | `gc.flow.gate.<gate>` | ticket | `dispatch`, `ticket_end` (written only by `close-ticket`, with the closing: the merged commit, the version of the list `ticket-end/v1` and its nine passing verdicts; T19, `docs/TICKET_END.md`), `withdrawn` (removed from the graph by a resolved Planning Exception) |
| Frozen criteria | `gc.flow.criteria` | ticket | `{digest, graph_digest, at}`: the fingerprint of the acceptance criteria of the ticket, in order, and the digest of the approved graph it was published under (`gc.graph_digest`, read only; null when the door wrote none). Written by `mark`; written again only when `gc.graph_digest` has changed since (a patch of the graph went through the publication door), never on a closed ticket (T19) |
| TDD step | `gc.flow.tdd.<step>` | ticket | step: `red`, `freeze`, `green`, `amendment`, `prefactoring`; always with the full commit SHA it was proven at; `red` and `prefactoring` with their start commit (`base`), `amendment` with its one-line reason |
| Stop | `gc.flow.stop` | ticket | reason: `criterion_already_green`, `amendment_exhausted`, `test_review_refused`, `test_review_no_result`, `code_review_no_result`, `evaluation_no_result`, `evaluation_outage`, `still_refused`; with a one-line detail, and `raised` once `stop-raised` wrote that the escalation door accepted it |
| Code review | `gc.flow.code_review` | ticket | `rounds`: each recorded round (`kind`: `review` / `judgement`, `commit`, `base`, `verdict`, `models`, `recorded_by`, `at`; a review with `findings` — `id`, `axis`: `standards` / `spec` / `tests`, `blocking`, `summary`, and `citation` (`source`: `spec` / `ticket` / `repo_rule`, `quote`, `path`), `demoted` or `question` — its `answers` (question id → `oui` / `non` and a reason) and its `responses` (finding id → `fixed` with a commit, or `contested` with a reason); a judgement with `judgements`: finding id → `favorable` / `unfavorable` and a reason); `request` while a round is open (`kind`, `commit`, `base`, `questions`, `models`, `launches`: at most two `{bead, at}`, `at`) |
| Ticket Evaluation | `gc.flow.evaluation` | ticket | `rounds`: each recorded round — kind `evaluation` (`commit`, `criteria`: one `{number, text, state, evidence, reason, cause}` per approved criterion, in order; `demonstration_line`: `{text, state, evidence, reason, cause}`; state: `observed` / `not_observed` / `unobservable`, a `reason` unless observed, a `cause` (`criterion` / `environment`) for an unobservable; `outcome`: `favorable` / `return_to_author` / `planning_exception` / `environment_outage`; `verdict`: `favorable`, `unfavorable`, or `null` for an outage; `roles`; `environment`: `{dataset, address}` per launched product; `recorded_by`, `at`) or kind `startup` (`commit`, `started`, then `evidence` and `environment`, or `detail`; `outcome`, `verdict`, `at`); `request` while an evaluation is open (`commit`, `criteria`, `demonstration_line`, `roles`: `{author, evaluator: {provider, supplier} or null, same_provider, other_declared}`, `environment`: `{dataset, address, state_file}` per launched product, `launches`: at most two `{bead, at}`, `at`); `live`: the launch records of the products still to stop |
| Models per role | `gc.flow.models` | ticket | role: `author`, `reviewer`, `evaluator`; each with `agent`, `provider`, `model`, `at` |
| Test review | `gc.flow.test_review` | ticket (`vertical_slice`, `repair`) | `rounds`: each recorded pass (`commit`, `files`: path → `sha256:`, `verdict`: `favorable` / `unfavorable`, `tests`: test id → `state` and, when unfavorable, `reason`, `recorded_by`, `at`); `request` while a review is open (`commit`, `files`, `criteria`: the criterion → test table, `launches`: at most two `{bead, at}`, `at`) |
| Ticket Handoff | `gc.flow.handoff` | ticket | `sections` (`done`, `deviations`, `not_done`, `out_of_ticket`: each `aucun` or a non-empty list of one-line items; an item of `not_done` may be `{what, paths}`), `partial`, the full commit SHA it was taken at, and the `records` written by code |
| Correction round | `gc.flow.correction` | ticket | `commit` (the full SHA both the code review and the evaluation answered at), `blocking_findings` (the ids of the Blocking Findings of that review), `not_observed` (what the evaluation did not observe there), at least one of the two not empty; `launches`: at most one `{bead, at}`; `at` |
| Overrides | `gc.flow.overrides` | ticket | `entries`, oldest first, one per overridden Blocking Finding: `finding`, `approver`, `words` (not empty, as given), `commit` (the one of the review), `at` |
| Parking | `gc.flow.park` | ticket | cause: `planning_exception`, `operator_request`, `resumes_exhausted` (T20); the ticket that caused it (`origin`: the one whose Ticket Exit parked it, or that is out of resumes); a one-line detail |
| Resumes | `gc.flow.resume` | ticket | `entries`, oldest first, one per resume code opened (T20): `cause` (`interrupted`, `returned`, `unblocked`, `answered`), `ref` (the one-line fact that asked for it), `session` (the author session it takes over from, or null), `exit` (the Ticket Exit it replaced, `{exit, at}`, or null), `launches`: at most one `{bead, at}`; `at` |
| Parkings lifted | `gc.flow.park_lifts` | ticket | `entries`, oldest first, one per parking lifted on the ticket that caused it (T20): `cause`, `detail`, `parked_at`, `request` (the bead of the answered request), `option` (the letter taken, or null), `resumes` (the counter at that moment), `at` |
| Grouped request | `gc.flow.grouped_request` | convoy | the bead that carries the one request of a convoy in which nothing but parked tickets is left (T20) and, once it reached the escalation door, the `sha256:` signature of the parkings it names, with `lift_option` (a letter) and `lifts` (the tickets that option lifts), both or neither |
| Fidelity result | `gc.flow.fidelity` | ticket | `commit`, `verdict` (`favorable` / `unfavorable`, computed), `piece` (the sealed record), `screens`, `states` (state → `viewports`, `anchors` compared), `deviations`: each `state`, `viewport`, `anchor`, `kind` (`absent`, `structure`, `style`, `token`), `property`; a `token` deviation has neither viewport nor anchor |
| Planning Exceptions | `gc.flow.planning_exceptions` | ticket | `entries`, oldest first: `kind` (`semantic`, `topology`), `summary`, `anchors` (the anchors whose deviation it asks to accept, possibly none), `accept_option` (the letter of the request's option that accepts it; with anchors or items only), `prior_response_at`, `at`, and `resolution` (`option`, `at`) once a later one was raised; T23: `items` (the tracked elements of the Ticket Handoff it names, `deviations.N` / `not_done.N`; absent when none) and `repair` (the `repair` ticket code published once the operator asked for one, with the answer frozen beside it) |
| Operator's answer | `gc.needs_benjamin`, `gc.escalation_response_option`, `gc.escalation_response_at` (read only: written by `bin/escalation-door`) | ticket | what resolves the last Planning Exception |
| Integration branch | `gc.flow.integration` | convoy | `branch`, the `protected` branch it takes up, and `base`, the full commit SHA of the protected branch it left from; written once |
| Merge | `gc.flow.merge` | ticket | outcome: `merged`, `conflict`, `red`; `ticket_commit` (the tip of the ticket that was taken), `integration` (the tip it was merged on), and `commit`, the merged result, for `merged` and `red` only |
| Declared Scope | `gc.scope_paths` (read only: written by the publication door) | ticket | the declared paths, comma-separated; they order tickets and bound nothing |
| Acceptance criteria | the bead's description (read only) | ticket | the checkbox lines under `## Acceptance criteria`, in order |
| Factory incident | `gc.flow.incident` | convoy | the bead that carries the open incident of a stopped convoy and, once it reached the escalation door, the `sha256:` signature of the anomalies it names |
| Red of the integration branch | `gc.flow.integration_red` | convoy | T21: the control that is red, quoted on one line (`control`), the commit it was red on (`commit`), the tips of the integration and of the protected branches then (`integration`, `protected`), the end of what the control printed (`detail`, optional) and, once code published it, the one `repair` ticket that restores it (`repair`); T23: `check` (`regression`, `fidelity`; absent means the regression command), what is red |
| Record of the end-of-Spec gate | `gc.flow.spec_end` | convoy | T23: `commit` (the one commit of the integration branch the three verdicts are tied to), `protected` (the tip of the protected branch that commit holds), `version` (`spec-end/v3`; a record under `spec-end/v1` or `spec-end/v2` is still read, and held outdated by the gate), `conditions` (`registry`, `tests`, `fidelity`, in that order, all `pass`, each with its `detail`), `records` (optional: what `tests` and `fidelity` read), `at` |
| Outcome Evaluation | `gc.flow.outcome_evaluation` | convoy | T24: `rounds` (each: `commit`, `stories` — one per numbered user story of the Spec, with `state` `observed` / `not_observed` / `unobservable` and its `evidence` piece —, `exploration`, `fidelity_deviations`, `repairs` — the `draft` of each story not observed and, once published, its `repair` —, `contradictions`, the computed `outcome` and `verdict`, `roles`, `environment`, `recorded_by`, `at`), the open `request` (`commit`, `stories`, `roles`, `environment`, `launches`, `at`), `live` (launch records of products still to stop) and `stop` (`commit`, `reason` among `outcome_evaluation_no_result`, `outcome_evaluation_outage`, `story_unobservable`, `detail`, `raised`) |
| Classification of the findings « hors ticket » | `gc.flow.findings` | ticket | T24: `entries`, one per classified finding of the Ticket Handoff: `item` (`out_of_ticket.N`), `handoff_at`, `classification` (`repaired`, `proposal`, `dismissed`), `commit`, `recorded_by`, `at`; `reason` (required for `dismissed`); `draft` (the drafted `repair`, required for `repaired`, with what it `restores`) and, once code published it, `repair` |
| End code review of the Spec | `gc.flow.end_review` | convoy | T25: `rounds`, oldest first, each `commit` (the commit of the gate it read), `base` (the tip of the protected branch that commit holds), `outcome` (`favorable`, `unfavorable`, `incomplete`; computed), `findings` (`id`, `axis`, `blocking`, `summary`, `citation`, `demoted`; a Blocking Finding with its `repair_draft`, then `repair` or `repair_refused`), `coverage` (`axes`, `files`, `missing`, `missing_count`), `extent` (`files`, `commits`, `insertions`, `deletions`, `digest`), `models` (`authors`, `reviewer`, `same_model`), `recorded_by`, `launched_at`, `duration_seconds`, `at`; `request` while a review is open (`commit`, `base`, `extent`, `models`, `launches`: at most two, each `bead`, `at`, and `result: incomplete`; `at`); `stop` (`reason`: `end_review_no_result`, `end_review_repair_refused`; `detail`, `commit`, `at`, then `bead` and `raised`) |
| Last round of the end counted | `gc.flow.end_round` | convoy | T25: `commit` (the tip of the integration branch the last round of the end was counted for), `source` (`end_review`), `at` |

`mark` is idempotent: it marks the tickets first and the convoy last, sets
each counter to an explicit `0`, and on a later run marks only the tickets
added since (a patch), leaving existing counters alone.

A ticket is marked with its entry fields or not at all (T05,
`docs/ENTRY_CONTRACT.md`): `mark` writes the demonstration line of a ticket
in the same tracker write as its mark, from `--demonstration-line
<ticket>=<line>` (repeatable). It refuses, before any write, a ticket whose
kind is absent or outside the closed list (no default kind), a
`vertical_slice` or a `repair` without a demonstration line, a line on a
`prefactoring`, a line for a ticket the convoy does not track, and a line
that differs from the one already written: it is frozen with the approved
graph.

The same holds for the user stories a `vertical_slice` covers (T06),
written from `--user-stories <ticket>=<n>,<n>` (repeatable): `mark` refuses
a `vertical_slice` without any, a list on a `prefactoring` or a `repair`
(neither covers a story), anything that is not a list of story numbers each
given once, and a list that differs from the one already written.
`--establishes-launch-recipe <ticket>` (repeatable) names the slice that
establishes the project's launch recipe: refused on anything but a
`vertical_slice`, on more than one ticket of the convoy, and on a ticket
that already carries the mark without it. `--prototype-fold <ticket>`
(T36) names the slice that is the Prototype Fold of the Spec's Validated
Prototype: refused on anything but a `vertical_slice` of the convoy and on
a ticket that already carries the mark without it. That a graph has one
Fold, and that the interface tickets wait for it, is the publication
door's check (`docs/ENTRY_CONTRACT.md`).

`add-evidence` is called by `bin/evidence-capture` (T09), which files the
piece in the evidence store and computes its fingerprint
(`docs/EVIDENCE_STORE.md`); a fingerprint written by hand for a piece the
tool did not produce is refused by `evidence-capture verify`.

`set-tdd` is called by `bin/tdd-step` (T10, `docs/TDD_STEP.md`) once the
check of a step has passed and its report is a piece of the evidence store.
The order of the steps is held here, under the lock: `freeze` needs a `red`
at the same commit; once frozen, a new `red` or `freeze` is accepted only at
the commit of the ticket's `amendment`; `amendment` needs a freeze and is
written once per ticket; `green` needs a freeze; `prefactoring` is the only
step of a `prefactoring` ticket and is refused on another kind. `stop-ticket`
writes why a script stopped the ticket (Spec §5: a criterion already green,
a second amendment); a stopped ticket takes no further step, and a second
stop is refused. Nothing here lifts a stop.

`open-test-review`, `launch-test-review` and `record-test-review` are called
by `bin/test-review` (T13, `docs/TEST_REVIEW.md`), which holds the review of
a ticket's criterion tests between red and freeze. `open-test-review` opens
a review of the tests proven red at `--commit`, with the fingerprints the
freeze will seal and the criterion → test table (`--file`, a JSON object
`{files, criteria}`); the same request again writes nothing, another one
replaces the request that was open. It refuses a `prefactoring`, a ticket
already frozen, a commit that is not the one of the `red` step, a request
without fingerprints or with a test whose file has none, tests a pass
refused and that did not change, and tests already reviewed favorably at
that commit. `launch-test-review` records each reviewer bead sent for the
open request: the first, then one relaunch; a third is refused.
`record-test-review` takes the answers of the reviewer (`--file`: `commit`,
`files`, `tests`, `recorded_by`) and refuses, with every reason listed, a
verdict when no review is open, on another commit or other fingerprints
than the request, with a test left out or unknown, a state outside the
closed list, or a refusal without a reason. The verdict is computed here:
`unfavorable` as soon as one test is. The pass is appended and the request
closed in one tracker write; a **second** unfavorable pass writes the stop
(`test_review_refused`) in that same write (Spec §8: one return to the
author). `set-tdd --step freeze` is refused unless the last pass is
favorable, was given at the commit being frozen, and no review is open; the
freeze that ends an amendment is exempt (Spec §6: the code review reads an
amended test). `stop-raised` records that the stop of a ticket reached the
operator, so the code that stopped it raises it once; it refuses a ticket
that is not stopped, and the same record again writes nothing.

`set-model`, `open-code-review`, `launch-code-review`, `record-code-review`
and `respond-code-review` are called by `bin/code-review` (T14,
`docs/CODE_REVIEW.md`), `set-model` also by `bin/ticket-author start`.
`set-model` writes the agent, provider and model a delivery role runs on
for this ticket; the same record again writes nothing.

`open-code-review` opens a round of the code review at the commit the author
finished at: it refuses a ticket whose Ticket Exit is not « terminé », whose
complete Handoff is not at `--commit`, or that is stopped. `--kind review`
takes the closed questions on the tests (`--file`, `{questions: [{id, kind,
subject, text}]}`); it is refused while Blocking Findings wait for their
judgement, and at a commit already reviewed favorably. `--kind judgement`
needs an unfavorable review as last round, an answer to every Blocking
Finding, and `--base` equal to the reviewed commit. After an unfavorable
judgement neither opens. The request carries `models` — the models of the
author and of the reviewer read on the ticket, and `same_model` (`null` when
one is not recorded): the mention is stored, never left out. The same
request again writes nothing; another one replaces it.
`launch-code-review` records each reviewer bead: the first, then one
relaunch; a third is refused.

`record-code-review` takes what the reviewer session hands in (`--file`) and
refuses, with every reason listed and nothing written: a record when no
round is open, on another commit, without the session, with a field it does
not know — a `verdict` first of all: it is computed here — an axis outside
the list, a summary that is not one line, a `blocking` that is not a
boolean, an answer left out, unknown, outside `oui` / `non`, or a « non »
without a reason. A finding given as blocking is **stored as non-blocking**,
with the reason under `demoted`, when its citation is absent, malformed,
from a source outside the list, or declared not found by the caller
(`citation_refused`, set by `bin/code-review record`, which reads the
sources). A « non » to a closed question is stored as a Blocking Finding of
axis `tests`. The verdict is `unfavorable` as soon as one finding blocks.
For a judgement the file gives one state per Blocking Finding of the
reviewed round, exactly; it is refused from the session that recorded the
review. The round, the closing of the request and
`gc.flow.verdict.code_review` at the reviewed commit go in one tracker
write.

`respond-code-review` writes on the last review the answer to each of its
Blocking Findings: the closed list, every one and nothing else, `fixed` with
a full commit SHA other than the reviewed one, or `contested` with a reason.
It is refused when the last round is not an unfavorable review, and once
the judgement is opened.

`show` renders `code_review` with a computed `state`: the `verdict` and the
`commit` of the last round, and `unsettled`, the Blocking Findings that have
no favorable verdict. It is what `bin/spec-integration` reads to refuse a
merge.

`open-evaluation`, `launch-evaluation`, `record-evaluation`,
`record-startup` and `release-evaluation` are called by
`bin/ticket-evaluation` (T15, `docs/TICKET_EVALUATION.md`).

`open-evaluation` opens the Ticket Evaluation of a ticket at the commit its
author finished at (Ticket Exit `finished`, complete Handoff at that
commit), on the products named in `--file` (`{roles, environment}`). The
criteria and the demonstration line are **read here, on the approved
ticket**, and frozen in the request: nobody hands them in. The same request
again writes nothing; the same commit on other products replaces them and
keeps the launches. It refuses a `prefactoring` (no Evaluator session), a
ticket without acceptance criteria, a commit already evaluated with a
verdict (an outage gave none, and is opened again), an environment that is
not a list of products each at its own `http://127.0.0.1:<port>` address
with its launch record, and roles outside their shape. `launch-evaluation`
records each Evaluator bead sent: the first, then one relaunch; a third is
refused.

`record-evaluation` takes what the Evaluator hands in (`--file`: `commit`,
`criteria`, `demonstration_line`, `recorded_by`). It refuses, and writes
nothing: a `verdict` or an `outcome` (computed here, never given); a state
outside the three; a state without a piece whose fingerprint
(`gc.flow.evidence.<piece>`) is on the ticket at the evaluated commit; a
criterion whose text is not the one of the request (« reformulé »), a
criterion without a state (« retiré »), a state for a criterion the ticket
does not have, or given twice; a demonstration line reworded; criteria that
changed on the ticket since the request; a `not_observed` or an
`unobservable` without a reason, an `unobservable` without its cause. The
outcome is computed from the states — `planning_exception` as soon as one
is unobservable by the criterion, else `return_to_author` as soon as one is
not observed, else `environment_outage` when the environment hid one, else
`favorable` — and written with the round; the verdict
`gc.flow.verdict.evaluation` goes in the same tracker write, except for an
outage, which is neither an agreement nor a refusal and writes none.

`record-startup` records what code saw when it launched the product from a
clean copy of `--commit`: with `--piece` (the captured answer of the probe,
a fingerprint of the ticket at that commit) and the launched products in
`--file`, a favorable round — accepted on a `prefactoring` only, for which
it stands for the evaluation; with `--detail`, a product that did not
start, an unfavorable round accepted on any kind, which also closes an open
request. `release-evaluation` removes from `live` the launch records of the
products code stopped (`--state-file`, repeatable); it refuses one an open
evaluation still runs on, unless the ticket is stopped, or `--withdraw` is
given: the open evaluation is then withdrawn with its products (the ticket
is no longer to be evaluated at that commit).

`show` renders `evaluation` with a computed `state`: the `verdict`, the
`outcome` and the `commit` of the last round, `not_observed` (what was not
observed) and `unobservable` (what could not be, with its cause). It is
what `bin/spec-integration` reads to refuse a merge.

The verdict of the test review is not a `gc.flow.verdict.test_review`: a
verdict of that family holds only while its commit is the tip of the branch,
and this one holds for the frozen tests. The kind stays in the closed list
of `set-verdict`, unused by the flow.

`set-handoff` is called by `bin/ticket-exit` (T11, `docs/TICKET_EXIT.md`)
with the Handoff it built, as a JSON file: the sections of the author and
the records it sealed. It refuses a section that is absent or empty (a
complete Handoff has the four, each with content or `aucun`; only a
`partial` one may leave some out), a section it does not know, a complete
Handoff without records, and records without a `handoff_records` evidence
fingerprint at the commit of the Handoff: the records are written by code,
never given. `set-exit` itself is unchanged: that `finished` needs a valid
Handoff is the exit tool's refusal.

`park` writes the parking on the ticket and on every ticket of the convoy
that waits for it, directly or through others, following the `blocks` edges
read on each ticket; the descendants first, the ticket last, so that the
same call completes an interrupted one. A descendant that is closed or
already parked is left as it is. It refuses a cause outside the list, a
missing detail, a closed ticket and a ticket already parked. The cause
`resumes_exhausted` (T20) is accepted only on a ticket that has no resume
left (`resumes_left` 0, below). `lift-park` is what lifts a parking.

`open-resume`, `launch-resume`, `lift-park`, `record-grouped-request` and
`clear-grouped-request` are called by `bin/convoy-advance` (T20,
`docs/CONVOY_ADVANCE.md`, « Resumes, their bound, parking and the grouped
request »).

`open-resume` counts one resume of a ticket that code sends back to a fresh
author session, on the same branch (Spec §8). `--cause` is one of
`interrupted`, `returned`, `unblocked`, `answered`; `--ref` is one line
naming the fact that asks for it. The record, one more `resumes` and the
removal of the Ticket Exit the resume replaces (a resumed ticket exits
again) go in **one tracker write**. The same cause and `--ref` as the last
resume write nothing and count nothing. It refuses a cause outside the list,
a missing `--ref`, a closed ticket, a ticket the dispatch door did not
start, a stopped ticket, a parked ticket, and a ticket that has no resume
left: that one is parked. `launch-resume` records the bead of the author
session the last resume was sent to: one per resume, a second is refused, as
is a launch on a stopped or a parked ticket or with no resume open.

The bound is K (Spec §8: a starting value, not a measure), every cause
together: `resumes` is the one counter that `open-resume`, `open-correction`
and `invalidate-verdicts` add to. K is not held in this command: it is
`bounds.resumes` of `config/delivery-flow.json` (3), the one place the
bounds of the flow are set (T21, `docs/CONVOY_ADVANCE.md`), read under
`FACTORY_ROOT` (default: the repository of the command) and, when that root
sets no `bounds`, in the Factory's own file. A missing or malformed value
is a refusal (« bounds.resumes absent ou invalide »), of `show` too: never
a default. `show` renders `resumes_left`: K minus the resumes counted since
the last lift of a `resumes_exhausted` parking of the ticket (since the
start when there is none), never below 0.

**The red of the integration branch (T21).** `record-integration-red`
writes that the integration branch of the convoy is red: the control,
quoted, and where it was red. It refuses a convoy without a recorded
integration branch, a malformed commit, a missing control, a `--detail` on
several lines. The same red again — same control, same commit — writes
nothing, so a red seen by several passes stays one red. A branch found red
elsewhere while it is red (its tips moved) updates the record and keeps its
repair; found red once that repair is closed, the record has no repair any
more. `set-integration-repair` names the repair code published for the red:
a tracked ticket of the convoy, of kind `repair`; it refuses a convoy that
is not red, a ticket that is not a repair, and a second repair while the
first is open (« un seul repair par rouge »). `clear-integration-red`
removes the record. The three refuse a convoy without the mark (exit 4).

**The end of the Spec (T23, `docs/SPEC_END.md`).** `record-integration-red
--check fidelity` says that what is red is the mechanical fidelity the
end-of-Spec gate measured, not the regression command; a `--check` outside
`regression`, `fidelity` is refused. `--end-round` adds one to the convoy
counter `end_rounds` **in the write that records the red**: the same red
again writes nothing and counts nothing. `record-spec-end` records the three
verdicts of the gate with the commit they are tied to. It refuses a convoy
without an integration branch, one whose integration branch is red, one
with a ticket left open or closed without a gate record (each named), a
version other than `spec-end/v3`, a list that is not `registry`, `tests`,
`fidelity` in order, a verdict that is not `pass`, an empty detail, an
unknown field, `records` other than `tests` and `fidelity`, a malformed
commit. Nothing compares the record to the branches here: `bin/spec-end
check` says whether it still holds. The record holds the three mechanical
verdicts only: conditions 4 and 5 of the list are read by the gate in
what the Evaluator of the end handed in, and the sixth, `end_review`, in
`gc.flow.end_review`, below.

**The end code review of the Spec (T25, `docs/SPEC_END_REVIEW.md`).**
`open-end-review`, `launch-end-review`, `record-end-review`,
`stop-end-review` and `end-review-stop-raised` are called by
`bin/spec-end-review`; `set-end-review-repair` by `bin/convoy-advance`. All
land on the convoy.

`open-end-review` opens the review on `--commit`, which must be the commit
of the record of the end-of-Spec gate, the integration branch not red: the
`base` is the protected tip of that record. `--file` gives the `extent` of
the diff, counted by the caller, and the `reviewer` (`agent`, `provider`,
`model`, or null). The models are stored with the request: the model of the
author of each ticket that was not withdrawn, the reviewer's, and
`same_model` — true when the reviewer runs on the model of an author, null
when a model is not recorded. The same request again writes nothing; a
request left on an earlier commit is replaced, and its stop with it. It
refuses a commit that already has a complete round, and a commit the review
is stopped on.

`launch-end-review` records each review bead: the first, then one relaunch;
a third is refused. `record-end-review` takes what the reviewer session
hands in and computes the outcome. It refuses a record without an open
request, on a stopped review, on another commit than the request's, with a
`verdict` or an `outcome` given by the reviewer, an unknown field, a
malformed `coverage`, a Blocking Finding without its drafted `repair` or
with a malformed one (the fields and the closed list of `restores.kind`:
`user_story`, `anchor`, `spec_line`, `repo_rule`). A finding given as
blocking whose citation does not hold (`citation_refused`, set by
`bin/spec-end-review record`, which reads the sources) is stored
non-blocking with `demoted`; a citation of a `ticket` names that ticket.
The outcome is `incomplete` when `coverage` leaves an axis or a file of the
`extent` out — the round is stored, the request stays open and its last
launch is marked `result: incomplete` —, else `unfavorable` with a Blocking
Finding, else `favorable`; a complete round closes the request. Each round
keeps `launched_at` and `duration_seconds`.

An **unfavorable** round adds one to the convoy counter `end_rounds` in the
same tracker write, and writes `gc.flow.end_round` with its commit: a tip
already counted there is not counted again, whichever source refuses it.

`set-end-review-repair` names, on a Blocking Finding of the last round, the
`repair` ticket published from its draft (`--ticket`: a ticket of the
convoy of kind `repair`) or the reason the patch door refused the draft
(`--refused`). Once per finding; the same value again writes nothing.
`stop-end-review` stops the review on the commit of its request (or of its
last round) with a reason of the closed list and a one-line detail;
`end-review-stop-raised` records the bead of the request once the
escalation door accepted it.

`lift-park` lifts the parking a ticket caused, once the request `--request`
(a bead id) was answered, with the letter of the option taken (`--option`,
optional). It removes the parking from every ticket parked behind it, then
from the ticket itself — those behind first, so that the same call
completes an interrupted one — and appends the lift to `park_lifts` with the
count of `resumes` at that moment: an exhausted ticket takes its three
resumes again from there, and the counter is not erased. A ticket behind
that still waits for another ticket that parks is parked behind that one
instead of being freed. It refuses a ticket that is not parked, a ticket
parked by another one (a parking is lifted on the ticket that caused it), a
`--request` that is not a bead id and an `--option` that is not one
lowercase letter. Whether the answer is one that lifts is the caller's
decision (`bin/convoy-advance`), not checked here. Nothing here lifts a
stop.

`record-grouped-request` writes on the convoy the bead of its grouped
request, first alone, then with `--signature`, `--lift-option` and `--lifts`
(repeatable) once the escalation door accepted it; it refuses a bead or a
ticket that is not a bead id, a signature that is not a `sha256:` digest,
and `--lifts` without `--lift-option` or the reverse.
`clear-grouped-request` removes it. Both are accepted on any convoy that
carries a mark, like `record-incident`.

`set-integration`, `set-merge` and `invalidate-verdicts` are called by
`bin/spec-integration` (T18, `docs/SPEC_INTEGRATION.md`). `set-integration`
writes the integration branch of the convoy's Spec once: the same record
again writes nothing, another branch, protected branch or start commit is
refused. `set-merge` writes what the merge command did of a ticket; it
refuses an outcome outside the list, a `merged` or a `red` without the
commit of the merged result, a `conflict` with one, a convoy without a
recorded integration branch, and a closed ticket. `invalidate-verdicts`
(Spec §8, « commit après verdict ») writes on each named verdict the tip
that outdated it and adds one to `resumes`, in one tracker write; a verdict
already invalidated is left as it is and counts nothing more, so repeating
the call is harmless. Verdicts that were all given at the commit of the
ticket's correction round (T17) are invalidated **without** a resume: the
commit that outdates them is that round, counted when it was opened. The
same holds (T20) for verdicts that were all given at the commit the merge
returned (`merge.outcome` `conflict` or `red`), once code opened a
`returned` resume for that return: `open-resume` counted it. A commit on a
returned ticket for which no resume was opened still counts one. It refuses a kind outside the list, a ticket that has
no such verdict, and a verdict that judged that very tip. `set-verdict`
writes a fresh verdict: replaying is what lifts an invalidation.

`open-correction`, `launch-correction` and `override-finding` are called by
`bin/correction-round` (T17, `docs/CORRECTION_ROUND.md`).

`open-correction` opens the single correction round of a ticket at the
commit its author finished at. It refuses a stopped or a parked ticket; a
ticket that already took its round (one per ticket, code review and Ticket
Evaluation together); a code review that has no round at that commit or has
one open; an evaluation that has no round at that commit, has one open, or
whose outcome there is neither `favorable` nor `return_to_author` (one
session receives every finding: both have answered); answers already judged
unfavorably; and a ticket neither of them refused. What was refused is read
here — the Blocking Findings of the review, the states the evaluation did
not observe — never given. The round, `resumes` and `correction_rounds` each
one more, go in **one tracker write**: the round counts among the resumes
(Spec §8). The same round again writes nothing. `launch-correction` records
the bead of the author session the round was sent to: one, a second is
refused.

`override-finding` records that the operator overrides a Blocking Finding
of the code review, with their words (Spec §8, « passer outre »). It refuses
a ticket that is not stopped; a `--finding` that is not a Blocking Finding
left without a favorable verdict (`code_review.state.unsettled`); anything
that is not a finding id — a criterion that was not observed is never
waived, and the refusal names the Planning Exception; a missing approver;
and words that are absent or blank. The same override again writes nothing;
other words for a finding already overridden are refused. That the approver
is the declared human approver of the project is the refusal of
`bin/correction-round override`, which reads the project. Nothing here
lifts the stop or the unfavorable verdict: `show` renders the override
beside them.

`set-fidelity` is called by `bin/prototype-fidelity` (T16,
`docs/PROTOTYPE_FIDELITY.md`) with what it compared at `--commit` (`--file`:
`screens`, `states`, `deviations`). The verdict is computed here —
`unfavorable` as soon as there is one deviation — and written with the
result, as `gc.flow.verdict.fidelity`, in one tracker write. It refuses, and
writes nothing: a file that carries a `verdict` or any other field; a result
without screen, without state, or with a state without viewport or anchor (a
result that compared nothing); a deviation outside its shape, of a kind
outside the list, on a state that was not compared, or without its anchor;
and a result whose record is not a piece of the evidence store captured at
that commit (`--piece`): it is written by code, never given.

`raise-planning-exception` is called by `bin/ticket-exit` (T16,
`docs/TICKET_EXIT.md`) before the request reaches the operator. It refuses a
kind outside the list, a summary that is not one line, a malformed anchor
name or one given twice, anchors without `--accept-option` and the reverse.
The answer the operator gave to the previous exception is stored with it;
the same exception again writes nothing; another one replaces the one that
was still open. **Nothing here resolves a Planning Exception**: the answer
is the operator's, written by `bin/escalation-door repondre`.

T23: with `--item` (repeatable), the exception names **tracked elements**
of the ticket's Ticket Handoff instead of anchors — `deviations.N` or
`not_done.N`, the N-th entry of that section. It is called by `bin/spec-end`
for elements left without a final state. It refuses an id of another shape,
one given twice, one the Handoff does not carry (a section that says
« aucun », a number past its end, a ticket without a Handoff), and items
without `--accept-option`. `set-item-repair` names, on the last Planning
Exception of a ticket, the `repair` code published for its elements. It
refuses when that exception names no element, has no answer of the operator,
or was answered by the option that accepts; when `--repair` is not a tracked
ticket of the convoy of kind `repair`; and a second repair for the same
request (« un seul repair par demande »). The same repair again writes
nothing. The operator's answer is frozen on the exception with the repair.

`show` renders `planning_exceptions` with, for each, a computed `state`
(`open`, `resolved`), the `response` and `accepted`: true when it names
anchors and was answered by its `accept_option`. The last one is resolved
when the ticket carries an answer (`gc.escalation_response_at`) given since
it was raised — not the one that was already there, and no request left
open (`gc.needs_benjamin` is `none`). `accepted_anchors` is the union of the
anchors of the accepted ones. `fidelity` is rendered with each deviation's
`status` — `accepté par Benjamin` when its anchor is one of them, else
`ouvert` — and a computed `state`: `vert` without deviation, `accepté par
Benjamin` when every deviation is, else `rouge`. The stored verdict is not
rewritten: a gate reads `fidelity.state`.

T23: `show` renders `tracked_items` on each ticket: one entry per deviation
and per « non fait » of its Ticket Handoff (`id`, `section`, `number`,
`text`, `state`, `request`, `repair`), an empty list when the ticket has no
Handoff or declares none. `state` is computed and stored nowhere: `accepté
par Benjamin` when the last Planning Exception that names the element since
that Handoff was answered by its `accept_option`; `réparé` when it was
answered otherwise and the `repair` named on it is a `repair` of the convoy
closed with a record of the ticket-end gate; else `ouvert`. A Handoff
rendered again starts its elements over: an exception raised before it does
not count. No command sets an element aside.

T24: `show` renders `findings` on each ticket: one entry per line of the
`out_of_ticket` section of its Ticket Handoff (`id` `TICKET:out_of_ticket.N`,
`ticket`, `item`, `number`, `text`, `state`, `classification`, and what the
classification holds). `state` is computed: `non classé` until
`classify-finding` named it since that Handoff; `proposition pour Benjamin`
and `écarté` are final; a finding classified `repaired` is `à réparer` until
the `repair` named on it is a `repair` of the convoy closed with a record of
the ticket-end gate, `réparé` then. `classify-finding` refuses `repaired`
without a drafted repair that cites what it restores, `dismissed` without a
reason, an item the Handoff does not hold, and a classification outside an
open Outcome Evaluation. `record-outcome-evaluation` refuses a story of the
Spec left without state, a story the Spec does not number, a `verdict`, an
`outcome` or a `contradictions` field handed in, a story `not_observed`
without a drafted repair that cites it, and any record while a finding is
`non classé`; it computes the outcome and writes a contradiction for each
story `not_observed` whose covering tickets were all favorably evaluated.
The `exploration` and `fidelity_deviations` sections are stored and change
no verdict. A piece of the end of the Spec is added with `add-evidence
CONVOY CONVOY`: its fingerprint goes on the convoy
(`docs/OUTCOME_EVALUATION.md`).

A piece name is made of letters, digits, `_` and `.` only: the tracker
refuses any metadata key outside `[a-zA-Z_][a-zA-Z0-9_.]*` (observed on bd
1.2.2), so a hyphen is refused here before it is tried.

## What a write refuses

Before anything is written: a verdict without a full commit SHA; a Ticket
Exit, verdict kind, verdict state, counter or gate outside its closed list;
a negative or non-integer counter; a ticket counter on the convoy or the
reverse; a counter write after which `correction_rounds` would exceed
`resumes` (a correction round counts among the resumes, Spec §8); an
evidence fingerprint without a `sha256:` digest or without a commit; a
Ticket Handoff, a parking, an integration branch, a merge or an invalidation
as described above; a
`record-gate --gate ticket_end` (that record is written by `close-ticket`
only); a `close-ticket` whose report is not the nine conditions of the known
version, in order, all passing, each with a one-line detail, or that names
no full commit SHA, or on a ticket already closed or carrying a closing
gate record; a TDD step outside its closed
list, without a full commit SHA, out of order, or on a stopped ticket; a
freeze without a favorable test review at the same commit; a request, a
launch or a verdict of the test review as described above, or on a stopped
ticket; a request, a launch, a record or an answer of the code review as
described above, or on a stopped ticket; a model for a role outside the
list; a stop whose reason is outside its closed list or that has no
detail; a correction round, its launch or an override as described above; a
resume, its launch, a lift or a grouped request as described above; a
ticket
that is not tracked by the convoy, or that does not carry the mark.

Writes on one convoy are serialised by a lock (`CONVOY_STATE_LOCK_DIR`,
default `$XDG_RUNTIME_DIR` or `/tmp`), so concurrent counter bumps are all
counted and a reviewer and an Evaluator can write the same ticket in parallel.

## What a read reports

T19: each ticket is rendered with `criteria_frozen` (the stored record plus
`current`, the fingerprint of the criteria read on the ticket now,
`current_graph_digest`, and `identical`: both equal to what was frozen),
`validated_prototype` (the reference the publication door posed under
`## Validated Prototype`: `branch`, `commit`, `path`, `states`; null when
the ticket has no such section) and `interface` (true when it has one: the
ticket touches a screen). Neither is written here.

`list` answers `{"convoys": [...]}`: the ids of the convoys that carry the
mark and are not closed. It is what `bin/convoy-advance` walks
(`docs/CONVOY_ADVANCE.md`); an unmarked convoy never appears in it.

`show` renders, per ticket: mark, kind, demonstration line, covered user
stories (`user_stories`, a list of numbers or `null`), whether it
establishes the launch recipe (`establishes_launch_recipe`), whether it is
the Prototype Fold (`prototype_fold`), tracker status,
branch and its tip, Ticket Exit, verdicts, counters, evidence fingerprints
and gate records, its acceptance criteria (`criteria`, the lines of its
description, numbered from 1 by `bin/tdd-step`), the proven steps of its
TDD (`tdd`, `{step: {commit, at, base?, reason?}}`), its stop (`stop`,
`null` when it is not stopped), the review of its criterion tests
(`test_review`, `null` before the first request), its code review
(`code_review`, `null` before the first request), its Ticket Evaluation
(`evaluation`, `null` before the first request) and the models per role
(`models`), its correction round (`correction`, `null` while none is
opened), the overrides of the operator (`overrides`, an empty list when
none, each with `state`: `dérogation enregistrée`), its Ticket Handoff
(`handoff`), its parking
(`park`; T20: with `answer`, `{option, at}`, the answer the operator gave to
the request of the ticket — `gc.escalation_response_option` and
`gc.escalation_response_at`, given since the parking and with no request
left open — rendered on the ticket that caused the parking only, `null` on
those behind it and while there is none) and its Declared Scope (`declared_scope`, a list of paths), each
`null` when the ticket has none, and what the merge command did of it
(`merge`, `null` while it did nothing), the Planning Exceptions it raised
(`planning_exceptions`, an empty list when none), the anchors whose
deviation a resolved one accepts (`accepted_anchors`) and the result of its
fidelity check (`fidelity`, `null` before the first one), the resumes code
opened (`resume`, `null` while there is none), the parkings lifted
(`park_lifts`, an empty list when none) and the resumes it may still take
(`resumes_left`; `null` when the counter or the lifts cannot be read, which
is flagged on its own); and for the convoy the Spec it
delivers (`spec`, `null` when it names none), its counters, its open factory
incident (`incident`, `null` when there is none), the integration branch
of its Spec (`integration`, `null` before it is opened), the red of that
branch (`integration_red`, `null` while it is not red), its grouped
request (`grouped_request`, `null` when there is none), the record of the
end-of-Spec gate (`spec_end`, `null` before three green verdicts were
recorded; T23), its Outcome Evaluation (`outcome_evaluation`, `null`
before one was opened, with `state`: the last `verdict`, `outcome`,
`commit`, the stories `not_observed` and `unobservable`, the `repairs` and
the `contradictions`; T24), the end code review of the Spec (`end_review`,
`null` before the first request, with a computed `state`: the `commit` and
the `outcome` of its last round and `unsettled`, its Blocking Findings; T25)
and the last round of the end counted (`end_round`, `null` before the first).

`ticket` answers whether one bead carries the mark, without naming its
convoy: exit 0 and `"new_flow": true`, or exit 4 and `"new_flow": false`.
With `--bead-json -` it reads the bead from stdin, as `gc bd show --json`
printed it, instead of reading the tracker again: `bin/dispatch-door` asks
it that way on every dispatch, so a bead without the mark costs no further
tracker read and is dispatched exactly as before.

**Verdict validity** (Spec §8, « commit après verdict »). A verdict carries
`"valid": true` only while its commit is the tip of the ticket's branch in
`--repo` (default: the current directory; the local branch is read first,
then `origin/<branch>`). A commit added to the branch after the verdict
makes it `"valid": false`: nothing is rewritten by a read, the verdict simply has
to be replayed on the new tip. The merge command is what writes it
(`invalidate-verdicts`): the verdict then carries `invalidated` and stays
`"valid": false` until a fresh one replaces it.

**« État sans règle »** (Spec §0 rule 5). A ticket in one of these states
carries `"signal": "état sans règle"` and one `{field, reason}` per anomaly
in `unruled`; the offending field is rendered as `{"unruled": reason, "raw":
stored value}` (a verdict keeps its state and commit but has no `valid`
key), never as a default value:

- closed without a `ticket_end` or `withdrawn` gate record (closed outside
  the gate);
- a `ticket_end` record that is not the version of the list and its nine
  passing verdicts (not written by the gate);
- a frozen-criteria record that cannot be read, or a `## Validated
  Prototype` section of the description without its branch, commit, path
  and states;
- in progress without a `dispatch` gate record (started outside the gate);
- a verdict whose commit is not on the ticket's branch, whose ticket has no
  recorded branch, or whose branch cannot be found in `--repo`;
- a counter that is absent, not an integer ≥ 0, or `correction_rounds`
  above `resumes`;
- a ticket without the mark in a marked convoy, or an unknown mark;
- a kind that is absent or outside the closed list (never rendered as a
  kind), a `vertical_slice` or a `repair` without a demonstration line, a
  demonstration line on a `prefactoring`;
- a `vertical_slice` without covered user stories, covered user stories or
  a launch recipe established on another kind, a Prototype Fold of another
  kind;
- any stored value this command would have refused to write, and any
  `gc.flow.*` key it does not know (a field invented outside the command).

A marked **convoy** found closed is one more « état sans règle », carried
by the convoy itself (`convoy.unruled`, field `status`, « convoi fermé hors
commande », with the closing reason it carries): a marked convoy closes only
by code, on the operator's words — accepted or abandoned (Spec §9). No
command of this flow closes a convoy yet (the acceptance and the abandon
come with T29 and T30, which add their record here); until then every
closed marked convoy is reported, and `list` names them under
`closed_outside`, apart from the open ones under `convoys`. An open marked
convoy whose tickets are all closed is a valid state.

`convoy-state` only signals. `bin/convoy-advance` stops the convoy and
raises the factory incident (`docs/CONVOY_ADVANCE.md`); it records that
incident here with `record-incident` (first the bead alone, then the
signature once the escalation door accepted it) and removes it with
`clear-incident` when the state is valid again. Both are accepted on a
convoy whose mark is unknown, which is itself an « état sans règle » to
report. An incident record, a grouped-request record or a record of the
red of the integration branch that this command would not have written is
one more anomaly of the convoy.

## Proof

`tests/convoy-state-test.py` drives the command line on a fake tracker
state (`tests/fixtures/convoy-state/gc`): one test per pass and per
refusal, each refusal re-reading the tracker to prove nothing was written.
Its T21 section covers the red of the integration branch (recorded, read
back, the same red again, a red found elsewhere, its one repair, a record
written outside the command) and the bound of the resumes read in the
settings of the flow: a smaller one parks sooner, a larger one later, a
malformed one is refused.
`tests/convoy-state-real-tracker-test.sh` (local-only) replays the same
contract on the real `gc`/`bd` in a disposable city, a Ticket Handoff of
20 kB, a parking along real `blocks` edges, and the integration branch, an
invalidated verdict and a merge (T18) included.
`tests/prototype-fidelity-demonstration-test.sh` (local-only) reads the
fidelity result and an answered Planning Exception back from the real
tracker (T16). `tests/correction-round-isolated-city-test.sh` (local-only)
reads the correction round, its counters, the stop and an override back
from the real tracker (T17). `tests/ticket-end-isolated-city-test.sh`
(local-only) reads the record of the ticket-end gate and the closed status
back from the real tracker (T19).
`tests/convoy-manual-lifecycle-isolated-city-test.sh` (local-only) has the
real `gc convoy check`, run by the city's own order, leave a marked convoy
open once all its tickets are closed, and close an unmarked one (T22).
T20: `tests/convoy-state-test.py` covers
`open-resume` (counted once per fact, every cause on the same counter, each
refusal), `launch-resume`, the parking for exhausted resumes, `lift-park`
(the record kept, the resumes given back without erasing the count, a ticket
left parked behind another one), the answer rendered on a parked ticket, the
grouped request, and a commit on a returned ticket counted once; on the real
tracker, `tests/convoy-advance-isolated-city-test.sh` (local-only) goes
through `open-resume` and `launch-resume` only; no trial there covers
`lift-park`, the parking for exhausted resumes or the grouped request.
T23: `tests/convoy-state-test.py` covers the tracked elements (rendered,
accepted by the accepting answer only, repaired once the gate closed the
repair, started over by a new Handoff), `--item` and `set-item-repair` with
each refusal, `record-spec-end` with each refusal, a record or a repair
written outside the command, `--check` and `--end-round` (counted in the
same write, once). `tests/spec-end-real-tracker-test.sh` (local-only)
replays these writes and their refusals on the real `gc`/`bd` in a
disposable city.
T24: the Outcome Evaluation commands and `classify-finding` are covered
through `bin/outcome-evaluation`, which is their only caller
(`tests/outcome-evaluation-test.py`, one test per refusal, the tracker
re-read), and `set-outcome-repair` through the pass
(`tests/convoy-stops-fixture-city-test.py`).
`tests/spec-end-real-tracker-test.sh` (local-only) replays these writes and
their refusals on the real `gc`/`bd`, the user stories read in a Spec bead
of the disposable city.
T25: `tests/convoy-state-test.py` covers each write of the end review with
its refusals — the request bound to the commit of the gate, the two
launches, the outcome computed (favorable, unfavorable, incomplete), the
citation rule, the drafted repair, the round of the end counted once per
tip, the repair named or refused once per finding, the stop and its
raising, a record written outside the command;
`tests/spec-end-review-isolated-city-test.sh` (local-only) goes through
them on the real `gc`/`bd`.
