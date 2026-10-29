# Convoy State (T33, T34, T10, T11, T13, T14, T15, T16, T17, T18, T19, T20, T22, T21, T23, T27, T26, Spec af-wf4w5r §0 rules 2 and 5)

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
./bin/convoy-state list                                 # the open marked convoys, and apart those closed by command and those closed outside acceptance or abandon (bin/convoy-advance, bin/planning-artifacts-close)
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
./bin/convoy-state raise-planning-exception af-convoy af-t1 --kind semantic --summary "…" [--anchor liste] --accept-option c   # bin/ticket-exit
./bin/convoy-state raise-planning-exception af-convoy af-t1 --kind semantic --summary "…" --item not_done.1 --accept-option b   # bin/spec-end: tracked elements left without a final state
./bin/convoy-state set-item-repair af-convoy af-t1 --repair af-r2   # bin/convoy-advance, once the patch door published the repair the operator asked for
./bin/convoy-state set-integration af-convoy --branch integration/af-spec --protected main --base <sha>   # bin/spec-integration open
./bin/convoy-state set-merge   af-convoy af-t1 --outcome merged --ticket-commit <sha> --integration <sha> --commit <sha>   # bin/spec-integration merge
./bin/convoy-state invalidate-verdicts af-convoy af-t1 --tip <sha> --kind code_review --kind evaluation   # bin/spec-integration merge
./bin/convoy-state open-correction   af-convoy af-t1 --commit <tip>          # bin/correction-round settle: a correction round
./bin/convoy-state launch-correction af-convoy af-t1 --bead af-correction    # bin/correction-round, once the author session is sent
./bin/convoy-state override-finding  af-convoy af-t1 --finding F1.1 --approver <human approver> --words "…"   # bin/correction-round override
./bin/convoy-state open-resume   af-convoy af-t1 --cause interrupted --ref "session:<session name>"   # bin/convoy-advance: one resume counted, before the fresh author session is sent
./bin/convoy-state launch-resume af-convoy af-t1 --bead af-resume        # bin/convoy-advance, once the author session is sent
./bin/convoy-state park          af-convoy af-t1 --cause resumes_exhausted --detail "reprises épuisées pour la cause …"   # bin/convoy-advance, at the bound of a same cause
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
./bin/convoy-state record-evidence-pack af-convoy --commit <integration tip> --digest sha256:<hex> --path <folder> (--conforming | --non-conforming) [--inadmissible N]   # bin/evidence-pack generate
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
./bin/convoy-state end-stop-raised  af-convoy --bead af-convoy                       # bin/convoy-advance, once the « non conforme » request reached the operator
./bin/convoy-state record-delivered af-convoy --commit <integration tip> --pack-digest sha256:<hex>   # bin/spec-end run: the seven conditions met on one commit
./bin/convoy-state acceptance-requested     af-convoy --bead af-convoy                 # bin/convoy-advance, once the Acceptance Request reached the operator
./bin/convoy-state acceptance-launch-failed af-convoy --commit <commit of the dossier> --detail "<line>"   # bin/acceptance-session open: the product did not start
./bin/convoy-state set-acceptance-repair    af-convoy --ticket af-r4                   # bin/convoy-advance, once the patch door published the repair of that outage
./bin/convoy-state record-proposition-verdict af-convoy --proposition af-t3:out_of_ticket.1 --verdict avant|plus_tard|sans_suite --approver benjamin --words "<his words>"   # bin/owner-answer verdict
./bin/convoy-state set-verdict-proposal     af-convoy --proposition af-t3:out_of_ticket.1 --bead af-p1   # bin/owner-answer, once the proposition door created it
./bin/convoy-state record-owner-answer      af-convoy --response accepted|findings|abandoned --approver benjamin [--words "<his words>" --commit <commit of the dossier> --pack-digest sha256:<hex>] [--file findings.json] [--reason "<line>"] [--repo <project repository>]   # bin/owner-answer record
./bin/convoy-state set-owner-repair         af-convoy --finding 1 --ticket af-r5       # bin/convoy-advance, once the patch door published the repair of that Owner Finding
./bin/convoy-state set-owner-proposal       af-convoy --finding 2 --bead af-p2         # bin/owner-answer, for a finding « plus tard »
./bin/convoy-state resolve-owner-exception  af-convoy --approver benjamin --words "<his words>"   # bin/owner-answer resolve-exception
./bin/convoy-state record-blocking-red af-convoy af-ticket --control "<the red control, one line>"   # bin/ticket-exit, « bloqué technique » (T40)
./bin/convoy-state clear-blocking-red  af-convoy af-ticket                                          # its repair was refused by the patch door
./bin/convoy-state record-promotion af-convoy --judged <accepted commit> --merged <merge commit> --protected <protected tip before> --tip <integration tip merged>   # bin/outcome-promote, once the protected branch took the merge
./bin/convoy-state void-acceptance  af-convoy --cause regression|fidelity|start|conflict   # bin/outcome-promote: the take-up after « accepté » is red or in conflict
./bin/convoy-state close-convoy     af-convoy            # bin/outcome-promote: the closed status and the record of the closing, in one write
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
| Digest of the Spec | `gc.spec_digest` (read only: written by the publication door) | convoy | T27: rendered as `convoy.spec_digest` for the header of the Evidence Pack; `null` when the convoy carries none or it is not a `sha256:` digest |
| Kind | `gc.ticket_kind` (read only: written by the publication door) | ticket | `vertical_slice`, `prefactoring`, `repair` |
| Demonstration line | `gc.flow.demonstration_line` | ticket (`vertical_slice`, `repair`) | one non-empty line, written once by `mark` |
| Covered user stories | `gc.flow.user_stories` | ticket (`vertical_slice`) | the numbers of the Spec's user stories the slice covers, at least one, each once; written once by `mark` |
| Launch recipe established here | `gc.flow.establishes_launch_recipe` | ticket (`vertical_slice`, at most one per convoy) | `true`, written with the mark; absent otherwise |
| Prototype Fold | `gc.flow.prototype_fold` | ticket (`vertical_slice`) | `true`, written with the mark; absent otherwise |
| Ticket branch | `gc.flow.branch` | ticket | branch name |
| Author session | `gc.flow.session` | ticket | `name`, `at`; the same write puts the ticket `in_progress` with `gc.session_name`. Refused for a session that already took another ticket of the convoy, for a ticket the dispatch door did not start, for a closed ticket |
| Ticket Exit | `gc.flow.exit` | ticket | `finished`, `planning_exception`, `operator_request`, `technically_blocked`, `interrupted` |
| Verdict | `gc.flow.verdict.<kind>` | ticket | kind: `code_review`, `evaluation`, `fidelity`; state: `favorable`, `unfavorable`; always with the full commit SHA it judged; `invalidated` (`tip`, `at`) once `invalidate-verdicts` wrote that a newer commit outdated it, or (`tip`, `contract`, `at`) when a newer code-review judgement contract invalidated it at the same tip |
| Counter | `gc.flow.counter.<name>` | ticket: `resumes`, `correction_rounds`; convoy: `end_rounds` | integer ≥ 0 |
| Evidence fingerprint | `gc.flow.evidence.<piece>` | ticket | `sha256:<64 hex>` and the commit of the piece |
| Gate record | `gc.flow.gate.<gate>` | ticket | `dispatch`, `ticket_end` (written only by `close-ticket`, with the closing: the merged commit, the version of the list `ticket-end/v1` and its nine passing verdicts; T19, `docs/TICKET_END.md`), `withdrawn` (removed from the graph by a resolved Planning Exception, or by `bin/outcome-promote` when the convoy is abandoned during delivery) |
| Frozen criteria | `gc.flow.criteria` | ticket | `{digest, graph_digest, at}`: the fingerprint of the acceptance criteria of the ticket, in order, and the digest of the approved graph it was published under (`gc.graph_digest`, read only; null when the door wrote none). Written by `mark`; written again only when `gc.graph_digest` has changed since (a patch of the graph went through the publication door), never on a closed ticket (T19) |
| TDD step | `gc.flow.tdd.<step>` | ticket | step: `red`, `freeze`, `green`, `amendment`, `prefactoring`; always with the full commit SHA it was proven at; `red` and `prefactoring` with their start commit (`base`), `amendment` with its one-line reason |
| Stop | `gc.flow.stop` | ticket | reason: `criterion_already_green`, `amendment_exhausted`, `test_review_no_result` (written before ADR-0030 L3, read only), `code_review_no_result`, `evaluation_no_result`, `evaluation_outage`, `still_refused`; with a one-line detail, and `raised` once `stop-raised` wrote that the escalation door accepted it |
| Code review | `gc.flow.code_review` | ticket | `rounds`: each recorded round (`kind`: `review` / `judgement`, `commit`, `base`, `verdict`, `models`, `recorded_by`, `conversation` when known, `at`; a review with `findings` — `id`, `axis`: `standards` / `spec` / `tests`, `blocking`, `summary`, and `citation` (`source`: `spec` / `ticket` / `repo_rule`, `quote`, `path`), `demoted` or `question`, and optionally `carries`, `location` (`path`, `line`), `finishing_pass` (ADR-0034) — its `scope` when targeted, its `answers` (question id → `oui` / `non` and a reason) and its `responses` (finding id → `fixed` with a commit, or `contested` with a reason); a judgement with `judgements`: finding id → `favorable` / `unfavorable` and a reason, optional `contract`, and `invalidated: {contract, at}` when superseded by a new judgement contract); `request` while a round is open (`kind`, `commit`, `base`, `questions`, `scope` for a targeted review, `models`, `launches`: at most two `{bead, at}`, each with `refused`: `{session, at}` once a session that already served answered it, `at`, and `contract` for a judgement) |
| Ticket Evaluation | `gc.flow.evaluation` | ticket | `rounds`: each recorded round — kind `evaluation` (`commit`, `criteria`: one `{number, text, state, evidence, reason, cause}` per approved criterion, in order; `demonstration_line`: `{text, state, evidence, reason, cause}`; state: `observed` / `not_observed` / `unobservable`, a `reason` unless observed, a `cause` (`criterion` / `environment`) for an unobservable; `outcome`: `favorable` / `return_to_author` / `planning_exception` / `environment_outage`; `verdict`: `favorable`, `unfavorable`, or `null` for an outage; `roles`; `environment`: `{dataset, address}` per launched product; `recorded_by`, `conversation` when known, `proven_by_test`: the items counted proven by their criterion test on the operator's answer (`park_lifts`), read as `observed` by the outcome, `at`) or kind `startup` (`commit`, `started`, then `evidence` and `environment`, or `detail`; `outcome`, `verdict`, `at`); `request` while an evaluation is open (`commit`, `criteria`, `demonstration_line`, `roles`: `{author, evaluator: {provider, supplier} or null, same_provider, other_declared}`, `environment`: `{dataset, address, state_file}` per launched product, `launches`: at most two `{bead, at}`, each with `refused`: `{session, at}` once a session that already served answered it, `at`); `live`: the launch records of the products still to stop |
| Models per role | `gc.flow.models` | ticket | role: `author`, `reviewer`, `evaluator`; each with `agent`, `provider`, `model`, `at` |
| Test review | `gc.flow.test_review` | ticket (`vertical_slice`, `repair`) | written before ADR-0030 L3 only, now read only: `rounds`: each recorded pass (`commit`, `files`: path → `sha256:`, `verdict`: `favorable` / `unfavorable`, `tests`: test id → `state` and, when unfavorable, `reason`, `recorded_by`, `conversation` when known, `at`); `request` while a review is open (`commit`, `files`, `criteria`: the criterion → test table, `launches`: at most two `{bead, at}`, each with `refused`: `{session, at}` once a session that already served answered it, `at`) |
| Ticket Handoff | `gc.flow.handoff` | ticket | `sections` (`done`, `deviations`, `not_done`, `out_of_ticket`: each `aucun` or a non-empty list of one-line items; an item of `not_done` may be `{what, paths}`), `partial`, the full commit SHA it was taken at, and the `records` written by code |
| Correction round | `gc.flow.correction` | ticket | `commit` (the full SHA both the code review and the evaluation answered at), `blocking_findings` (the ids of the Blocking Findings of that review), `not_observed` (what the evaluation did not observe there), at least one of the two not empty; `launches`: at most one `{bead, at}`; `at` |
| Overrides | `gc.flow.overrides` | ticket | `entries`, oldest first, one per overridden Blocking Finding: `finding`, `approver`, `words` (not empty, as given), `commit` (the one of the review), `at` |
| Parking | `gc.flow.park` | ticket | cause: `planning_exception`, `operator_request`, `resumes_exhausted` (T20); the ticket that caused it (`origin`: the one whose Ticket Exit parked it, or that is out of resumes); a one-line detail |
| Resumes | `gc.flow.resume` | ticket | `entries`, oldest first, one per resume code opened (T20): `cause` (`interrupted`, `returned`, `unblocked`, `answered`, `behind`, `evaluation_no_result`, `stage_removed`, `code_review_no_result`, `amendment_granted`, `inherited_change`), `ref` (the one-line fact that asked for it), `session` (the author session it takes over from, or null), `exit` (the Ticket Exit it replaced, `{exit, at}`, or null), `stop` (only for `evaluation_no_result`, and for `stage_removed` a stop `test_review_refused` or `test_review_no_result`, and for `code_review_no_result`, whose resume also drops the `request` of `gc.flow.code_review`, and for `amendment_granted` a stop `amendment_exhausted` the operator answered « a », which allows one amendment more: the stop it lifted, as it was), `launches`: at most one `{bead, at}`; `at` |
| Linked technical repairs | `gc.flow.technical_repairs` | ticket | `entries`, oldest first: `{id, at}` for each Factory-maintenance bead explicitly linked by `link-technical-repair` to this ticket's own `operator_request`; absent on ordinary operator, product, planning and human requests |
| Parkings lifted | `gc.flow.park_lifts` | ticket | `entries`, oldest first, one per parking lifted on the ticket that caused it (T20): `cause`, `detail`, `parked_at`, `request` (the bead of the answered or withdrawn request), `option` (the letter taken, or null), `resumes` (the counter at that moment), `at`; `repairs` (optional: every explicitly linked Factory-maintenance bead whose structural delivery proof released this technical request); `proven_by_test`: `{what, text}` per item the operator's answer `a` to an evaluation's Planning Exception judged proven by its criterion test (af-ten1sp) |
| Grouped request | `gc.flow.grouped_request` | convoy | the bead that carries the one request of a convoy in which nothing but parked tickets is left (T20) and, once it reached the escalation door, the `sha256:` signature of the parkings it names, with `lift_option` (a letter) and `lifts` (the tickets that option lifts), both or neither |
| Fidelity result | `gc.flow.fidelity` | ticket | `commit`, `verdict` (`favorable` / `unfavorable`, computed), `piece` (the sealed record), `screens`, `states` (state → `viewports`, `anchors` compared), `deviations`: each `state`, `viewport`, `anchor`, `kind` (`absent`, `structure`, `style`, `token`, `theme`), `property`; a `token` deviation has neither viewport nor anchor, a `theme` one (a theme not measurable on the prototype) a viewport and no anchor; past 100 deviations, the first 100 only, with `deviation_count` (all of them) and `deviation_anchors` (the anchors of all, `null` for a token deviation) |
| Planning Exceptions | `gc.flow.planning_exceptions` | ticket | `entries`, oldest first: `kind` (`semantic`, `topology`), `summary`, `anchors` (the anchors whose deviation it asks to accept, possibly none), `accept_option` (the letter of the request's option that accepts it; with anchors or items only), `prior_response_at`, `at`, and `resolution` (`option`, `at`) once a later one was raised; T23: `items` (the tracked elements of the Ticket Handoff it names, `deviations.N` / `not_done.N`; absent when none) and `repair` (the `repair` ticket code published once the operator asked for one, with the answer frozen beside it) |
| Operator's answer | `gc.needs_benjamin`, `gc.escalation_response_option`, `gc.escalation_response_at` (read only: written by `bin/escalation-door`) | ticket | what resolves the last Planning Exception |
| Integration branch | `gc.flow.integration` | convoy | `branch`, the `protected` branch it takes up, and `base`, the full commit SHA of the protected branch it left from; written once |
| Merge | `gc.flow.merge` | ticket | outcome: `merged`, `conflict`, `red`; `ticket_commit` (the tip of the ticket that was taken), `integration` (the tip it was merged on), and `commit`, the merged result, for `merged` and `red` only |
| Declared Scope | `gc.scope_paths` (read only: written by the publication door) | ticket | the declared paths, comma-separated; they order tickets and bound nothing |
| Acceptance criteria | the bead's description (read only) | ticket | the checkbox lines under `## Acceptance criteria`, in order |
| Factory incident | `gc.flow.incident` | convoy | the bead that carries the open incident of a stopped convoy and, once it reached the escalation door, the `sha256:` signature of the anomalies it names |
| Red of the integration branch | `gc.flow.integration_red` | convoy | T21: the control that is red, quoted on one line (`control`), the commit it was red on (`commit`), the tips of the integration and of the protected branches then (`integration`, `protected`), the end of what the control printed (`detail`, optional) and, once code published it, the one `repair` ticket that restores it (`repair`); T23: `check` (`regression`, `fidelity`; absent means the regression command), what is red |
| Red control of a technical block | `gc.flow.blocking_red` | ticket | T40: the red control the author of the ticket named when it left « bloqué technique » (`control`, one line; `at`), written by `bin/ticket-exit` (`record-blocking-red`) before the `repair` that cites it goes through the patch door, and withdrawn (`clear-blocking-red`) if the door refuses it. Rendered as `blocking_red` on the ticket and among `convoy.red_checks` |
| Record of the end-of-Spec gate | `gc.flow.spec_end` | convoy | T23: `commit` (the one commit of the integration branch the three verdicts are tied to), `protected` (the tip of the protected branch that commit holds), `version` (`spec-end/v4`; a record under `spec-end/v1`, `spec-end/v2` or `spec-end/v3` is still read, and held outdated by the gate), `conditions` (`registry`, `tests`, `fidelity`, in that order, all `pass`, each with its `detail`), `records` (optional: what `tests` and `fidelity` read), `at` |
| Outcome Evaluation | `gc.flow.outcome_evaluation` | convoy | T24: `rounds` (each: `commit`, `stories` — one per numbered user story of the Spec, with `state` `observed` / `not_observed` / `unobservable` and its `evidence` piece —, `exploration`, `fidelity_deviations`, `repairs` — the `draft` of each story not observed and, once published, its `repair` —, `contradictions`, the computed `outcome` and `verdict`, `roles`, `environment`, `recorded_by`, `at`), the open `request` (`commit`, `stories`, `roles`, `environment`, `launches`, `at`), `live` (launch records of products still to stop) and `stop` (`commit`, `reason` among `outcome_evaluation_no_result`, `outcome_evaluation_outage`, `story_unobservable`, `detail`, `raised`) |
| Classification of the findings « hors ticket » | `gc.flow.findings` | ticket | T24: `entries`, one per classified finding of the Ticket Handoff: `item` (`out_of_ticket.N`), `handoff_at`, `classification` (`repaired`, `proposal`, `dismissed`), `commit`, `recorded_by`, `at`; `reason` (required for `dismissed`); `draft` (the drafted `repair`, required for `repaired`, with what it `restores`) and, once code published it, `repair` |
| End code review of the Spec | `gc.flow.end_review` | convoy | T25: `rounds`, oldest first, each `commit` (the commit of the gate it read), `base` (the tip of the protected branch that commit holds), `outcome` (`favorable`, `unfavorable`, `incomplete`; computed), `findings` (`id`, `axis`, `blocking`, `summary`, `citation`, `demoted`; a Blocking Finding with its `repair_draft`, then `repair` or `repair_refused`), `coverage` (`axes`, `files`, `missing`, `missing_count`), `extent` (`files`, `commits`, `insertions`, `deletions`, `digest`), `models` (`authors`, `reviewer`, `same_model`), `recorded_by`, `conversation` when known, `launched_at`, `duration_seconds`, `at`; `request` while a review is open (`commit`, `base`, `extent`, `models`, `launches`: at most two, each `bead`, `at`, and `result: incomplete`; `at`); `stop` (`reason`: `end_review_no_result`, `end_review_repair_refused`; `detail`, `commit`, `at`, then `bead` and `raised`) |
| Evidence Pack | `gc.flow.evidence_pack` | convoy | T27: `commit` (the commit of the integration branch the pack is tied to), `digest` (the fingerprint of its page), `path` (its folder, absolute), `conforming` (whether every condition of the end of the Spec it reports was met), `inadmissible` (the number of pieces the evidence store refused), `version` (`evidence-pack/v1`), `at` |
| Last round of the end counted | `gc.flow.end_round` | convoy | T25: `commit` (the tip of the integration branch the last round of the end was counted for), `source` (what refused that tip first: `regression`, `fidelity`, `end_review`, `outcome_evaluation`; T26), `at`; T26, optional, for the early stops: `not_observed` (the user stories the Outcome Evaluation did not observe at that tip), `previous_not_observed` (those of the round before), `refused_before` (every story not observed at an earlier counted tip) — numbers of user stories, ascending, each once |
| Stop of the rounds of the end | `gc.flow.end_stop` | convoy | T26: `reason` (`end_rounds_exhausted`, `stories_not_reduced`, `story_refused_twice`), `detail` (one line), `commit` (the tip that was refused when the stop was written), `source` (as for `end_round`), `rounds` (the rounds counted then), `at`; then `request`, once the « non conforme » request reached the operator: `bead`, `commit` and `digest` (the Evidence Pack it carries), `page` (the absolute path of its page), `at` |
| Delivered Outcome | `gc.flow.delivered` | convoy | T26: `commit` (the one commit of the integration branch the seven conditions of the end of the Spec were met on), `protected` (the tip of the protected branch that commit holds), `pack` (the fingerprint of the Evidence Pack generated there), `version` (`spec-end/v4`), `at` |
| Acceptance | `gc.flow.acceptance` | convoy | T28: what the acceptance of the convoy holds before Benjamin's answer, tied to the one commit of the dossier he judges -- `commit`, `pack` (the fingerprint of that Evidence Pack), `at`; then `request`, once the Acceptance Request reached the operator: `bead`, `page` (the absolute path of the page of the pack), `at`; and `panne`, when the product of an Acceptance Session did not start at that commit: `detail` (one line), `at`, then `ticket` (the `repair` published for it) |
| Judgement | `gc.flow.judgement` | convoy | T29: what Benjamin answered to the Outcome he judged, written through `bin/owner-answer` -- `verdicts`, one per « proposition » of the dossier: `proposition` (`<ticket>:out_of_ticket.N`), `verdict` (`avant`, `plus_tard`, `sans_suite`), `approver`, `words`, `commit` (the Delivered commit it was given on), `at`, then `proposal` (the proposition created for « plus tard ») or `answer` (the number of the « constats rendus » answer that returned a proposition « à faire avant d'accepter »); `answers`, oldest first: `response` (`accepted`, `findings`, `abandoned`), `approver`, `commit` and `pack` (the dossier judged; an abandon during delivery carries `in_flight: true` and `words`, no `pack`, and as `commit` the tip of the integration branch when there was one), `at`, `words` (accepted, findings), `reason` (abandoned, one line), `findings` (findings: each `text`, `route` -- `repair`, `planning_exception`, `later` --, and `cites` `{kind, ref}`, `draft` (the repair to publish, route `repair` only), `ticket` (the `repair` published), `proposal` (route `later`), `proposition` (a returned proposition)), `exception` (the one Planning Exception of the batch: `findings`, the numbers of its findings, `at`, then `resolved` `{approver, words, at}`). Nothing follows an `accepted` or `abandoned` answer |

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
(T36; repeatable) names a slice that is the Prototype Fold of a Validated
Prototype of the Spec: refused on anything but a `vertical_slice` of the
convoy and on a ticket that already carries the mark without it. That a
graph has one Fold per Validated Prototype (T46), and that the interface
tickets of each wait for it, is the publication door's check
(`docs/ENTRY_CONTRACT.md`).

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

The review of the criterion tests before the freeze (T13) left the flow in
ADR-0030 L3, and `bin/test-review` with the commands that wrote it in L7:
nothing writes `gc.flow.test_review` any more. A record left on a ticket in
flight is still read (`show`, the fresh-session check below, the Evidence
Pack) and holds nothing: the freeze does not read it.

`record-code-review` and `record-evaluation` first refuse what a session
hands in when that session already rendered a code review or a Ticket
Evaluation on a ticket of the convoy, or a review of tests recorded before
L3 (Spec §5, T42). A session is its name (`recorded_by`) and its
conversation (`conversation`): `c:` + the `CLAUDE_CODE_SESSION_ID` Claude
Code exports to its child processes — the conversation itself, new for a
fresh one, kept by a resumed one. A provider that does not set it (Codex,
stubs) gives `g` + Gas City's `GC_RUNTIME_EPOCH`, the session generation,
which gc 1.5.0 raises on every wake: one conversation only because the roles
that render use `wake_mode = "fresh"`, and a relaunch in the warm tmux box
(respawn-pane) keeps it, so such a relaunch is refused as the same session.
`GC_CONTINUATION_EPOCH` is not used: it rises only after a drain-ack, so a
session woken fresh after an idle sleep or a crash keeps it (af-bb69uq).
Start the supervisor outside Claude Code (as its systemd unit does): one
started from a Claude Code shell hands that shell's id to non-Claude
sessions, which are then refused as the same conversation. Rounds recorded
before carry the epoch, which no `c:` or `g` value equals. A round without
`conversation` (recorded before it was, or by a session that does not know
it) is recognized by the name alone. The last launch of the open request is marked
`refused` — the only write — and counts as a launch without result for
`bin/code-review` and `bin/ticket-evaluation`.

`stop-raised` records that the stop of a ticket reached the operator, so the code that stopped it raises it once (`bin/convoy-advance`
itself for `amendment_exhausted`, which `bin/tdd-step` writes from the
author's session); it refuses a ticket
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
request again writes nothing; another one replaces it. A review after the
first round of the ticket may carry a targeted `scope` in the same file
(ADR-0034: `from`, `unsettled`, `changed`); it is refused on a first review,
from another commit than the last round's, or naming a finding that round
did not leave unsettled. `record-code-review` then stores a finding given
as blocking that neither `carries` an unsettled finding nor has a
`location` in `changed` as non-blocking, `demoted` and `finishing_pass`.
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
left for one cause (`resumes_left` 0, below). `lift-park` is what lifts a parking.

`open-resume`, `launch-resume`, `lift-park`, `record-grouped-request` and
`clear-grouped-request` are called by `bin/convoy-advance` (T20,
`docs/CONVOY_ADVANCE.md`, « Resumes, their bound, parking and the grouped
request »).

`open-resume` counts one resume of a ticket that code sends back to a fresh
author session, on the same branch (Spec §8). `--cause` is one of
`interrupted`, `returned`, `unblocked`, `answered`, `behind` (T44: the
finished branch does not contain the tip of the integration branch,
`docs/CONVOY_ADVANCE.md`); `--ref` is one line
naming the fact that asks for it. The record, one more `resumes` and the
removal of the Ticket Exit the resume replaces (a resumed ticket exits
again) go in **one tracker write**. The same cause and `--ref` as the last
resume write nothing and count nothing. It refuses a cause outside the list,
a missing `--ref`, a closed ticket, a ticket the dispatch door did not
start, a stopped ticket (but the cause `returned` on a stop `still_refused`
whose every Blocking Finding is overridden: lifted and kept on the entry,
af-n4bn62), a parked ticket, and a ticket that has no resume
left for one cause: that one is parked. `launch-resume` records the bead of the author
session the last resume was sent to: one per resume, a second is refused, as
is a launch on a stopped or a parked ticket or with no resume open.

The bound is K (Spec §8: a starting value, not a measure), **per cause**
(ADR-0030 L2): each cause of `open-resume`, and `commit_after_verdict` (a
commit after a verdict, which `invalidate-verdicts` counts without an
entry), has its own bound, and the ticket is out of resumes once one cause
reaches its bound. A resume an answer of the operator opened
(`answered`, `amendment_granted`) has no bound: each one needs a new request
and a new answer, so the answer bounds it; it is recorded and counted in
`resumes` like any other (af-npz9v1.41: R2, af-cifk1e, was parked on
28/10/2026 at its third answer). `resumes` stays the one counter that `open-resume`,
`open-correction` and `invalidate-verdicts` add to; the count per cause is
derived, never stored apart: the resume entries by their cause, and
`commit_after_verdict` the rest of the counter once the entries and
`correction_rounds` are taken out. A `behind` entry is left out of its
cause the first time its fact names a tip of the integration branch
(`integration:<tip>/…`): the factory moved that tip, the ticket did not;
a second `behind` entry on the same tip is counted (af-npz9v1.36,
Benjamin 27/10/2026 16:27 Paris: « Oui : une mise à jour behind causée par l'usine ne compte plus dans les reprises d'un ticket. », after « oui les 6 » at 15:45; `docs/CONVOY_ADVANCE.md`).
The counter `resumes` still holds every resume recorded. The correction round counts against no
cause: its own bound is one round, held by `open-correction`. K is not held
in this command: it is `bounds.resumes` of `config/delivery-flow.json`
(3 for each cause; an object naming exactly the bounded causes, or one
integer for every cause, as a trial root may set), the one place the
bounds of the flow are set (T21, `docs/CONVOY_ADVANCE.md`), read under
`FACTORY_ROOT` (default: the repository of the command) and, when that root
sets no `bounds`, in the Factory's own file. A missing or malformed value
is a refusal (« bounds.resumes absent ou invalide »), of `show` too: never
a default. `show` renders `resumes_left_by_cause`: for each cause, its
bound minus the resumes of that cause counted since the last lift of a
`resumes_exhausted` parking of the ticket (since the start when there is
none), never below 0; and `resumes_left`, the fewest of them. `lift-park`
keeps on the lift what the ticket had taken per cause (`taken`); a lift
written before L2 has none, and what it had taken is read from the entries
older than the lift and the counter it kept. Without `--option`, a
`resumes_exhausted` parking is lifted only while the ticket has resumes left
under the bounds of now (`bin/convoy-advance`, af-npz9v1.41); that lift
keeps `taken` as the last such lift kept it, so it gives no resume back.

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
again writes nothing and counts nothing; once the rounds are consumed that
write counts none and records the stop of the rounds with the red (T26,
below). `record-spec-end` records the three
verdicts of the gate with the commit they are tied to. It refuses a convoy
without an integration branch, one whose integration branch is red, one
with a ticket left open or closed without a gate record (each named), a
version other than `spec-end/v4`, a list that is not `registry`, `tests`,
`fidelity` in order, a verdict that is not `pass`, an empty detail, an
unknown field, `records` other than `tests` and `fidelity`, a malformed
commit. Nothing compares the record to the branches here: `bin/spec-end
check` says whether it still holds. The record holds the three mechanical
verdicts only: conditions 4 and 5 of the list are read by the gate in
what the Evaluator of the end handed in, and the sixth, `end_review`, in
`gc.flow.end_review`, below.

**The Evidence Pack (T27, `docs/EVIDENCE_PACK.md`).** `record-evidence-pack`
is called by `bin/evidence-pack generate` once the page is written: the
commit it is tied to, the fingerprint of the page, its folder, whether it
is conforming, and the number of pieces the store refused. It refuses a
convoy without an integration branch, a malformed commit or digest, a
folder that is not an absolute path on one line, a record without
`--conforming` or `--non-conforming`, and a count that is not an integer
≥ 0. The same pack again writes nothing; another page replaces the record.
Nothing compares it to the branches here: `bin/evidence-pack check` says
whether it still holds.

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
Once the rounds are consumed it counts none and stops them (T26, below).

`set-end-review-repair` names, on a Blocking Finding of the last round, the
`repair` ticket published from its draft (`--ticket`: a ticket of the
convoy of kind `repair`) or the reason the patch door refused the draft
(`--refused`). Once per finding; the same value again writes nothing.
`stop-end-review` stops the review on the commit of its request (or of its
last round) with a reason of the closed list and a one-line detail;
`end-review-stop-raised` records the bead of the request once the
escalation door accepted it.

**The rounds of the end: one counter, one bound, the stop (T26, Spec §8).**
Every refusal of a tip at the end of a Spec goes through one place,
whatever refuses it: a mechanical red (`record-integration-red --end-round`,
source `regression` or `fidelity`), an unfavorable end review
(`record-end-review`, source `end_review`), and an Outcome Evaluation that
leaves a user story not observed or a finding « hors ticket » classified
`repaired` still « à réparer » (`record-outcome-evaluation`, source
`outcome_evaluation`). There is one counter, `gc.flow.counter.end_rounds`:
one round per refused tip, counted by the source that refuses it first, in
the write that records the refusal. The end review and the Outcome
Evaluation count nothing on a tip `gc.flow.end_round` already names; an
Outcome Evaluation recorded there adds its stories `not_observed` to that
record. A mechanical red is counted as it is recorded: once per red.

The bound is `bounds.end_rounds` of `config/delivery-flow.json` (2; a
starting value, not a measure), read as `bounds.resumes` is, and only by the
write that would count one more round: a missing or malformed value refuses
that write (« bounds.end_rounds absent ou invalide »), which then writes
nothing; a red recorded without `--end-round` reads no bound.

When a tip is refused and the bound is consumed, no round is counted: the
same write records `gc.flow.end_stop` with `reason: end_rounds_exhausted`,
the tip, the source, the rounds counted and one line of `detail` that quotes
what refused. Two **early stops** come before the bound, and before the
round they would otherwise count; they are defined on the user stories an
Outcome Evaluation did not observe, and on nothing else (Spec, Further
Notes 7):

| `reason` | Written when |
| --- | --- |
| `story_refused_twice` | a story not observed at this tip was already not observed at an earlier counted tip (`refused_before`) |
| `stories_not_reduced` | the round before left stories not observed, and as many or more are not observed now (`previous_not_observed`) |
| `end_rounds_exhausted` | neither of the two, the tip is not counted yet, and the counter has reached the bound |

They are tried in that order. A convoy that carries `end_stop` has nothing
more counted and no other stop written: a later refusal records what it
records (the red, the round of the review, the evaluation) and nothing of
the rounds.

`end-stop-raised` records, in `end_stop.request`, that the « non conforme »
request reached the operator: `--bead` (the bead the escalation door wrote
it on) and, read on the convoy, the Evidence Pack it carries — `commit`,
`digest`, and `page`, the `index.html` of its folder. It refuses a convoy
whose rounds are not stopped, a missing or malformed bead, a convoy with no
Evidence Pack generated since the stop, and a pack that is conforming: the
request carries a dossier whose header says « non conforme ». The same bead
again writes nothing; another bead once raised is refused.

`record-delivered` is called by `bin/spec-end run` once its seven
conditions are met on one commit (`docs/SPEC_END.md`), with that commit and
the fingerprint of the pack. The gate decides; what is refused here, each
cause named and nothing written, is a record the tracker contradicts: a
ticket left open or closed without a gate record, a red integration branch,
stopped rounds, and, **at that commit**, mechanical verdicts not recorded
under `spec-end/v4`, an Outcome Evaluation that is open, elsewhere or not
favorable, a finding « hors ticket » `non classé` or `à réparer`, an end
review that is open, elsewhere or not favorable, an Evidence Pack that is
not the conforming one of that digest with no inadmissible piece. The same
record again writes nothing. `gc.flow.delivered` is **withdrawn in the same
write** by any refusal of the end that counts a round or stops the rounds,
and by `record-spec-end` at another commit: one commit more outdates every
verdict.

Not done here, on purpose: no command withdraws `end_stop` — what the
operator answers to the request (another round, back to planning, abandon)
is handed to the escalation door by `bin/acceptance-session record` (T28)
and read by nothing: T29 records his answer to a Delivered Outcome only
(`docs/OWNER_ANSWER.md`, Limits); and `set-counter --counter end_rounds
--value 0` resets the counter only, it clears neither `end_round` nor
`end_stop`.

### The acceptance record (T28)

Spec §11. `gc.flow.acceptance` (`convoy.acceptance` in `show`) holds what
happened between a dossier and Benjamin's answer, and is tied to the commit
of **the dossier he judges**: the Evidence Pack of the Delivered Outcome,
or the one the « non conforme » request of stopped rounds carries. What was
noted at another commit went with that commit: the first write at a new
dossier starts a new record. Recording Delivered again at the same commit
keeps it. Three commands write it (`docs/ACCEPTANCE_SESSION.md`):

`acceptance-requested` records, in `acceptance.request`, that the
Acceptance Request reached the operator: `--bead` (the bead the escalation
door wrote it on) and, read on the convoy, the `index.html` of the Evidence
Pack. It refuses a missing or malformed bead, a convoy that is not
Delivered, and an Evidence Pack that is not the one of the Delivered
Outcome (commit and fingerprint). One request per Delivered Outcome: the
same bead again writes nothing; another bead is refused.

`acceptance-launch-failed` records, in `acceptance.panne`, the outage of an
Acceptance Session: `--commit` and one line of `--detail`. It refuses a
commit that is not the one of the dossier Benjamin judges (and a convoy
with no such dossier). An outage is no judgment: nothing else of the convoy
changes — it stays Delivered, its request stays noted. The same outage
again writes nothing.

`set-acceptance-repair` names, in `acceptance.panne.ticket`, the ticket
code published for that outage. It refuses a convoy with no outage noted, a
ticket the convoy does not track, and a ticket that is not of kind
`repair`. One repair per outage: the same ticket again writes nothing;
another is refused.

A stored `gc.flow.acceptance` these commands would have refused to write is
an « état sans règle ». Benjamin's answer itself (accepté, constats rendus,
abandonné) is not part of this record: it is the judgement record below.

### The judgement record (T29)

Spec §11. `gc.flow.judgement` (`convoy.judgement` in `show`) holds
Benjamin's verdicts on the propositions of the dossier and each of his
answers, oldest first. Six commands write it; `bin/owner-answer` calls the
first two and the last, and names the propositions it creates
(`docs/OWNER_ANSWER.md`); the pass names the repairs
(`docs/CONVOY_ADVANCE.md`). **Whether `--approver` is the declared human
approver, whether the commit is still the tip of the integration branch and
whether the dossier still holds are the caller's refusals**
(`bin/owner-answer`), as for `override-finding`: this command reads neither
the project nor its repository.

`record-proposition-verdict` records one verdict (`--verdict avant`,
`plus_tard` or `sans_suite`, `--approver`, `--words`) on a « proposition »:
a finding « hors ticket » of the current Handoff classified `proposal`,
named `<ticket>:out_of_ticket.N`. It refuses a convoy that is not
Delivered, an id that is not such a proposition, empty words. One verdict
per proposition: the same again writes nothing; another replaces it, unless
the first already had its follow-up (`proposal` or `answer`).

`set-verdict-proposal` names, on a verdict `plus_tard`, the bead the
proposition door created (`--bead`). One per verdict: the same again writes
nothing; another is refused.

`record-owner-answer` appends one answer (`--response accepted`, `findings`
or `abandoned`, `--approver`):

- `accepted` and `findings` take `--words`, `--commit` and `--pack-digest`,
  and refuse a convoy that is not Delivered, a commit or a fingerprint that
  is not the one of the Delivered Outcome.
- `accepted` refuses while a proposition has no verdict, or has the verdict
  `avant` and was not returned. It writes the answer and nothing else: the
  convoy stays Delivered and open (what follows it: « The promotion and
  the closing » below).
- `findings` reads `--file` (`{"findings": [{text, cites?, repair?,
  later?}]}`) and gives each finding its route: `later` when it says so; a
  `repair` when it cites a `user_story` whose number the Spec holds or an
  `anchor` — its drafted `repair` is then required, and stored as `draft`;
  `planning_exception` otherwise, never a repair. Each proposition of
  verdict `avant` not yet returned is added as a `planning_exception`
  finding, and its verdict names the answer. Every `planning_exception`
  finding joins the one `exception` of the batch. It refuses a batch with
  no finding and no such proposition. **In the same write** it withdraws
  `gc.flow.delivered`, `gc.flow.acceptance` and `gc.flow.end_round` and
  sets `gc.flow.counter.end_rounds` to 0. It closes nothing.
- `abandoned` takes `--reason`, one line, and is recorded with the commit
  and the fingerprint of the dossier Benjamin judges (the Delivered
  Outcome, or the one of the « non conforme » request); it refuses a convoy
  that has neither.

`set-owner-repair` names, on finding `--finding N` of the last « constats
rendus », the ticket code published for it (`--ticket`): a tracked ticket
of the convoy, of kind `repair`, on a finding of route `repair`. One repair
per finding. `set-owner-proposal` names, on a finding of route `later`, the
bead of its proposition (`--bead`). For both the same value again writes
nothing; another is refused.

`resolve-owner-exception` records, with `--approver` and `--words`, that
the Planning Exception of the last batch is resolved. It refuses an answer
that carries none. The same call again writes nothing. T40 (af-o6tu3z): the
exception keeps, as `spec_digest`, the `gc.spec_digest` of the convoy when
it was raised — the approved Spec its graph is published from —, and the
call is refused while the convoy still carries that digest (the patch door
writes the digest of the amended Spec once it is approved and the revised
graph published). The refusal names the missing step (T52, af-ezqgma),
read on the Spec bead: not amended; amended and not approved again
(`bin/spec-approve`); approved and the revised graph not published
(`bin/ticket-graph-publish bd-patch`). An exception without
`spec_digest` is resolved on the words alone.

`record-owner-answer --repo DIR` (T40) names the repository of the project:
an Owner Finding that cites an `anchor` is a `repair` only if a prototyped
state of a Validated Prototype of the Spec holds an anchor of that name
(`bin/prototype-conformance anchors`, at the commit the Spec names);
otherwise it joins the Planning Exception of the batch. A prototype that
cannot be read, or no `--repo` while an anchor is cited, refuses the answer.

`show` renders `convoy.red_checks` (T40): the red controls the convoy
carries a record of, each as `{name, source}` — `integration` (the
`control` of `gc.flow.integration_red`, with its `check`),
`acceptance_session` (the outage of `gc.flow.acceptance`),
`technically_blocked` (with `ticket`: the `control` of its
`gc.flow.blocking_red`) and `tracked_items` (with `ticket`: the tracked
elements of that ticket the operator asked to have repaired). `name` is what a `repair` cites
(`restores: {kind: red_check, ref: <name>}`): the patch door refuses any
other. It is derived at each `show` and stored nowhere.

**Nothing reopens an accepted or an abandoned Outcome**:
`record-proposition-verdict` and `record-owner-answer` refuse once the last
answer is one of the two, and name the way in — new work, through a
Planning Run. An « accepté » that carries `voided` (T30, below) is not such
an answer: Benjamin answers again after it.

`record-delivered` also refuses while the last « constats rendus » has a
finding of route `repair` whose ticket is not a tracked ticket of the
convoy, or an `exception` that is not resolved.

A stored `gc.flow.judgement` these commands would have refused to write —
an answer after an accepted one that is not voided, a `voided` on another
answer than « accepté » or with a cause outside the list, a route that
contradicts what the finding carries, an `exception` that does not cover
its findings — is an « état sans règle ».

### The promotion and the closing (T30)

Spec §9 and §11. Three commands write what follows Benjamin's « accepté »
or « abandonné »; `bin/outcome-promote` is their only caller
(`docs/OUTCOME_PROMOTE.md`). The answer that **ends the judgement** is the
last one of `gc.flow.judgement` when it is `accepted` or `abandoned` and
carries no `voided`.

`record-promotion` writes `gc.flow.promotion` (`convoy.promotion` in
`show`): `{judged, merged, protected, tip, at}` — the commit Benjamin
judged, the one merge commit the protected branch received, the tip that
branch had before, and the tip of the integration branch that was merged
(the judged commit, or the one that took the protected branch up). It
refuses a convoy on which no « accepté » stands, a `--judged` that is not
the commit of that answer, a value that is not a full commit SHA, and a
second promotion. **That the merge exists and holds the judged commit is
the caller's proof**: this command reads no repository.

`void-acceptance` records that the acceptance no longer stands: the take-up
of the protected branch after « accepté » was red, or in conflict
(`--cause regression`, `fidelity`, `start` or `conflict`). **In one tracker
write** it sets `voided: {cause, at}` on the last answer — which stays in
the judgement —, withdraws `gc.flow.delivered`, `gc.flow.acceptance` and
`gc.flow.end_round`, and sets `gc.flow.counter.end_rounds` to 0, as
« constats rendus » does: the Outcome passes the end of its Spec again and
Benjamin judges it again. It refuses a convoy on which no « accepté »
stands, a cause outside the list, and a convoy whose promotion is recorded
(« son acceptation tient »). It records no red: the red of the integration
branch is `record-integration-red`'s.

`close-convoy` closes the convoy on Benjamin's words. The status `closed`
and `gc.flow.closed` — `{how: accepted|abandoned, said, approver, at}`,
`said` being his words of acceptance or the reason of the abandon — go in
**one tracker write**. It refuses a convoy without an answer that ends the
judgement; an accepted convoy whose promotion is not recorded for the
accepted commit (« la fermeture suit la fusion »); an abandoned convoy that
carries a promotion; and a convoy already closed outside the command
(« cette fermeture se signale, elle ne se régularise pas »). **Nothing else
closes a marked convoy, and nothing reopens one closed here.**

**Every write of the flow refuses a convoy closed by command**, on the
convoy and on each of its tickets, `mark` included:

> refus : l'Outcome du convoi <id> est accepté et son convoi est fermé :
> rien ne le rouvre, ni lui ni ses tickets ; un défaut ou un souhait trouvé
> après entre comme travail nouveau, par un Planning Run

The refusal reads `gc.flow.closed`, so it also holds on a convoy someone
reopened by hand. Four writes are not concerned, the ones accepted on any
convoy that carries a mark so that an anomaly can still be raised:
`record-incident`, `clear-incident`, `record-grouped-request` and
`clear-grouped-request`.

`show` renders three fields from these records: `convoy.promotion`;
`convoy.closed`, the record of the closing when the convoy is closed and
that record is the one its judgement calls for, `null` otherwise; and
`convoy.outcome` — `accepted` or `abandoned` on a convoy closed by command,
`delivered` on one that carries a Delivered Outcome, `null` otherwise.
Delivered and Accepted are two states: an Outcome is Accepted once merged
and its convoy closed on his words, not when « accepté » is recorded.

`link-technical-repair` accepts only a ticket parked by its own
`operator_request` and a repair bead governed by the PR+CI delivery
contract. Repeating the same link writes nothing. The link neither closes,
launches nor changes either bead; it gives `bin/convoy-advance` the durable
identity it needs to wait for delivery proof without guessing from a title,
option or ticket code.

`lift-park` lifts the parking a ticket caused, once the request `--request`
(a bead id) was answered, with the letter of the option taken (`--option`,
optional), or once every repeatable `--repair` exactly matches the linked
technical repairs and carries structural merge and exact-head CI proof. It
removes the parking from every ticket parked behind it, then
from the ticket itself — those behind first, so that the same call
completes an interrupted one — and appends the lift to `park_lifts` with the
count of `resumes` at that moment: an exhausted ticket takes its three
resumes again from there, and the counter is not erased. A ticket behind
that still waits for another ticket that parks is parked behind that one
instead of being freed. It refuses a ticket that is not parked, a ticket
parked by another one (a parking is lifted on the ticket that caused it), a
`--request` that is not a bead id and an `--option` that is not one
lowercase letter. Whether a human answer is one that lifts is the caller's
decision (`bin/convoy-advance`); linked repair delivery is checked here and
fails closed. Nothing here lifts a stop.

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

`open-correction` opens a correction round of a ticket at the commit its
author finished at. It refuses a stopped or a parked ticket; a ticket that
already took its rounds (`bounds.correction_rounds` per ticket, code review
and Ticket Evaluation together, one when unset; two since af-bv0ikr). A
later round replaces the record of the one before (its `grants` kept); when
the review at that commit is a judgement, its Blocking Findings are the
answers it judged unfavorably. `grant-correction` lifts the stop
`still_refused` of a ticket that has a round left (stopped when the bound
was lower), with the approver's words, kept under `grants` of the round;
bin/correction-round grant calls it. `grant-correction --exceptional`
(ADR-0034) does the same on a ticket at its bound, once: the grant carries
`exceptional: true` and the bound of that ticket is one more; a second one,
or one on a ticket with a round left, is refused. `grant-correction
--arbitrated --target NAME...` (ADR-0035) is the round the Mayor grants at
the bound: the grant carries `arbitrated: true` and its `targets`, each
adds one to the bound of that ticket, at most `ARBITRATED_ROUNDS_MAX` (2)
per ticket; refused on a ticket with a round left, or without a target.
It also refuses a code review that has no round at that commit or has
one open; an evaluation that has no round at that commit, has one open, or
whose outcome there is neither `favorable` nor `return_to_author` (one
session receives every finding: both have answered); answers already judged
unfavorably before any round; and a ticket neither of them refused. What was refused is read
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
that commit (`--piece`): it is written by code, never given. Every deviation
is checked, but the ticket keeps the first 100 only, with
`deviation_count` and `deviation_anchors`; the full list stays in the
sealed piece. A tracker write is one command line, and the kernel refuses
one argument above 128 KiB (af-m0hvif: 22,313 deviations on one ticket, a
2.7 MB result; `gc bd` refuses `--metadata @file`).

`raise-planning-exception` is called by `bin/ticket-exit` (T16,
`docs/TICKET_EXIT.md`) before the request reaches the operator. It refuses a
kind outside the list, a summary that is not one line, a malformed anchor
name or one given twice, and anchors without `--accept-option`. An
exception naming no anchor carries its `--accept-option` too (ADR-0030 L5,
`bin/ticket-exit` always offers one): answered by that option it is
`accepted`, which accepts no anchor but lets `bin/convoy-advance` lift its
parking. One raised before L5 carries none. The answer the operator gave to the previous exception is stored with it;
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
Benjamin` when every deviation is — for a cut result, when every anchor of
`deviation_anchors` is accepted —, else `rouge`. The stored verdict is not
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
request, a
launch or a verdict of the test review as described above, or on a stopped
ticket; a request, a launch, a record or an answer of the code review as
described above, or on a stopped ticket; a model for a role outside the
list; a stop whose reason is outside its closed list or that has no
detail; a correction round, its launch or an override as described above; a
resume, its launch, a lift or a grouped request as described above; a
ticket
that is not tracked by the convoy, or that does not carry the mark; and
(T30) any write on a convoy closed by command or on one of its tickets,
the incident and the grouped request apart.

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

`list` answers three lists of ids of convoys that carry the mark:
`convoys`, those that are not closed; `closed` (T30), those closed by
`close-convoy` with a record consistent with their judgement; and
`closed_outside`, those found closed any other way. `bin/convoy-advance
--all` walks `convoys` and `closed_outside`, never `closed`
(`docs/CONVOY_ADVANCE.md`); `bin/planning-artifacts-close` leaves alone the
Spec and the draft of a convoy under `closed_outside`. An unmarked convoy
never appears in any of the three.

`show` renders, per ticket: mark, kind, demonstration line, covered user
stories (`user_stories`, a list of numbers or `null`), whether it
establishes the launch recipe (`establishes_launch_recipe`), whether it is
the Prototype Fold (`prototype_fold`), tracker status,
branch and its tip, Ticket Exit, verdicts, counters, evidence fingerprints
and gate records, its acceptance criteria (`criteria`, the lines of its
description, numbered from 1 by `bin/tdd-step`), the proven steps of its
TDD (`tdd`, `{step: {commit, at, base?, reason?}}`), its stop (`stop`,
`null` when it is not stopped), the review of its criterion tests recorded
before ADR-0030 L3 (`test_review`, `null` on any other ticket), its code review
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
(`resumes_left`, and per cause `resumes_left_by_cause`; `null` when the
counter or the lifts cannot be read, which is flagged on its own); and for the convoy the Spec it
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
the last round of the end counted (`end_round`, `null` before the first),
the stop of the rounds of the end (`end_stop`, `null` while they are not
stopped; T26), the Delivered Outcome (`delivered`, `null` while none is
recorded; T26),
the Evidence Pack (`evidence_pack`, `null` before the first generation; T27),
the promotion, the closing and the state of the Outcome (`promotion`,
`closed`, `outcome`; T30, « The promotion and the closing »)
and the digest of the Spec the publication door wrote (`spec_digest`). An
`end_stop` or a `delivered` that cannot be read is an « état sans règle »
like the others: rendered with `unruled` and its raw value, exit 3.

`ticket` answers whether one bead carries the mark, without naming its
convoy: exit 0 and `"new_flow": true`, or exit 4 and `"new_flow": false`.
With `--bead-json -` it reads the bead from stdin, as `gc bd show --json`
printed it, instead of reading the tracker again: `bin/dispatch-door` asks
it that way on every dispatch, so a bead without the mark costs no further
tracker read and is dispatched exactly as before.

**Verdict validity** (Spec §8, « commit après verdict »). A verdict carries
`"valid": true` only while its commit is the tip of the ticket's branch in
`--repo` (default: the current directory; the local branch is read first,
then `origin/<branch>`) and no coded door invalidated it. A commit added to
the branch after the verdict makes it `"valid": false`: nothing is rewritten
by a read, the verdict simply has to be replayed on the new tip. The merge
command writes that invalidation through `invalidate-verdicts`. A newer
code-review judgement contract may likewise invalidate an unfavorable
judgement at the same tip through `open-code-review`; `invalidated` names
that contract. In both cases the verdict stays invalid until a fresh one
replaces it.

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

A marked **convoy** closed otherwise than by `close-convoy` is one more
« état sans règle », carried by the convoy itself (`convoy.unruled`, field
`status`, « convoi fermé hors commande (ni acceptation ni abandon
enregistré) », with the closing reason it carries): a marked convoy closes
only by code, on the operator's words — accepted or abandoned (Spec §9).
T29 records Benjamin's answer in `gc.flow.judgement`
(`docs/OWNER_ANSWER.md`); T30 closes the convoy on it (`close-convoy`, « The
promotion and the closing »). A closed convoy is **ruled** — no anomaly,
exit 0 — only when it carries a `gc.flow.closed` whose `how` is the answer
that ends its judgement and, for `accepted`, a promotion for the accepted
commit (for `abandoned`, none). Closed by hand, it stays « fermé hors
commande » whatever answer it carries: a closing is reported, never
regularised. `list` names the first kind under `closed` and the second
under `closed_outside`, apart from the open ones under `convoys`.

Two more anomalies of the convoy come with T30: a convoy that carries
`gc.flow.closed` and is **no longer closed** (field `status`, « convoi
rouvert hors commande après sa fermeture sur les mots de l'approbateur »),
and a stored `gc.flow.promotion` `record-promotion` would have refused to
write. An open marked convoy whose tickets are all closed is a valid state.

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
T30: the same trial closes one marked convoy on « abandonné » and one on
« accepté » with `close-convoy` on the real tracker — the status and the
record in one `gc bd update`, the convoy under `closed` and ruled, every
later write refused, the bead unchanged by the controller afterwards — the
judgement written by hand and the commits of the promotion being
placeholders.
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
T27: `tests/convoy-state-test.py` covers `record-evidence-pack` (recorded
and read back, the same pack again, each refusal, a record written outside
the command) and `spec_digest`; no trial on the real tracker covers it.
T26: `tests/convoy-state-test.py` covers the rounds of the end — the tip
and the source of a counted round, one counter whatever the source (a
mechanical red, the end review, a red again), a refusal once the two rounds
are consumed that counts none and records the stop in the write of the red
or of the review, nothing more on a stopped convoy, the bound read in
`config/delivery-flow.json` and refused when missing or malformed,
`end-stop-raised` with each refusal, a stop written outside the command;
`record-delivered` and its refusals are covered through the gate
(`tests/evidence-pack-test.py`), the early stops through the pass
(`tests/convoy-stops-fixture-city-test.py`). No trial on the real tracker
covers them.
T28: `tests/acceptance-session-test.py` covers the acceptance record — the
request noted once on the Delivered Outcome with the page of its pack,
refused on a convoy that is not Delivered and on another bead, kept when
Delivered is recorded again; the outage noted at the commit of the dossier
and refused at another, one repair of the convoy per outage. No trial on
the real tracker covers it.
T29: `tests/owner-answer-test.py` covers the judgement record through
`bin/owner-answer` — the three verdicts, the three answers, the route of
each finding of a batch, Delivered refused while a repair is unpublished or
the Planning Exception of the batch is open, the repair named once and only
by a repair of the convoy, nothing recorded after an accepted Outcome. No
trial on the real tracker covers it.
T30: `tests/convoy-close-test.py` covers `record-promotion` (the two
commits read back, the commit Benjamin judged kept on a taken-up tip,
refused without an « accepté », for another commit, a second time),
`void-acceptance` (Delivered and the request withdrawn, an answer following
a voided one, refused without an « accepté », for an unknown cause, once
promoted) and `close-convoy` (accepted with his words in one write and
ruled, not before its merge, abandoned with the reason and without a merge,
not without an answer that ends the judgement; a convoy closed or reopened
by hand still unruled; no write of the flow on a closed convoy or on its
tickets). `tests/outcome-promote-test.py` goes through the three with a
real repository (`docs/OUTCOME_PROMOTE.md`).

## Replacement of a withdrawn launch-recipe ticket

Intent (Benjamin, live chat, 2026-10-13): « Corrigeons le tir à la main pour cette fois […] lançons la livraison des tickets cockpits ».
Mechanism (agent interpretation): when an approved graph patch replaces the launch-recipe slice, its withdrawn predecessor stays in history with its flags, verdicts and counters. Marking counts only non-withdrawn predecessors for launch-recipe uniqueness. Closing alone is insufficient; the existing withdrawal gate is required. Two active establishing slices remain refused. Regression: `test_mark_replaces_only_a_withdrawn_launch_recipe_slice`. Incident and manual recovery: af-ed6lez.
