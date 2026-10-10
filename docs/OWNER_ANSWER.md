# Benjamin's answer and the route of each Owner Finding (T29, Spec af-wf4w5r §11)

## What it is for

A convoy that carries the **new-flow mark** and is **Delivered**
(`docs/SPEC_END.md`) waits for Benjamin, who judges the product in an
Acceptance Session (`docs/ACCEPTANCE_SESSION.md`). `bin/owner-answer` is
the **one tool that records what he answers**. The rules it holds:

- **Only the declared human approver answers**: `--approved-by` must be the
  `human_approver` of `config/projects/<rig>.toml`, read through
  `bin/project-planning-profile human-approver`.
- **Three answers, no other**: « accepté », « constats rendus »,
  « abandonné ». « refusé » is not an answer, and there is **no partial
  acceptance**.
- **« accepté » is tied to one dossier**: his words, the commit and the
  fingerprint of the Evidence Pack he judged, that commit still being the
  tip of the integration branch and the pack still « à jour ».
- **Each Owner Finding is routed by code**, on what it cites, never by the
  agent of the session: a `repair`, the one Planning Exception of the batch,
  or a proposition for later.
- **A refusal writes nothing.** One exception is stated under Limits (a
  proposition door that fails after the answer is written).
- **Nothing reopens an accepted or abandoned Outcome**: a defect or a wish
  found afterwards is new work, through a Planning Run.
- **It closes and merges nothing itself.** Once « accepté » or
  « abandonné » is recorded, the next pass of the Factory's order follows
  it through `bin/outcome-promote`: the one merge into the protected branch
  and the closing of the convoy, or the closing alone (T30,
  `docs/OUTCOME_PROMOTE.md`).

Everything is written through `bin/convoy-state`, in one convoy field,
`gc.flow.judgement` (`docs/CONVOY_STATE.md`).

## The commands

```bash
./bin/owner-answer verdict af-convoy --proposition <ticket>:out_of_ticket.N \
    --verdict "à faire avant d'accepter"|"plus tard"|"sans suite" \
    --approved-by NAME --words TEXT [--repo DIR]
./bin/owner-answer record af-convoy --response accepté|"constats rendus"|abandonné \
    --approved-by NAME [--words TEXT] [--commit SHA --pack-digest DIGEST] \
    [--findings FILE] [--reason LINE] [--repo DIR]
./bin/owner-answer resolve-exception af-convoy --approved-by NAME --words TEXT [--repo DIR]
./bin/owner-answer proposals af-convoy [--repo DIR]
```

The project is the single one the convoy's first ticket names under
« Target rigs »; `--repo` defaults to its `rig_dir`. Accents and case are
ignored in `--verdict` and `--response`.

**`verdict`** records his verdict on one « proposition » of the dossier (a
finding « hors ticket » the Evaluator of the end kept as a proposal,
rubric 2 of the Evidence Pack), on a Delivered Outcome:

| Verdict | Effect |
| --- | --- |
| « sans suite » | recorded; no longer blocks « accepté » |
| « plus tard » | recorded; code creates a proposition through `bin/proposal-door create` and names it on the verdict (`proposal`); does not block. If the door fails the verdict stays recorded and the answer names it under `proposals_pending` (see `proposals`) |
| « à faire avant d'accepter » | recorded; **blocks « accepté »** until the proposition has been returned with a « constats rendus » answer |

A verdict may be changed until code acted on it (its proposition created,
or returned with an answer). The same verdict again writes nothing.

**`record --response accepté`** takes `--words`, `--commit` and
`--pack-digest`. It appends the answer and nothing else: the Outcome stays
Delivered and the convoy stays open until the next pass of
`bin/convoy-advance`, which merges the integration branch into the
protected branch and closes the convoy (`docs/OUTCOME_PROMOTE.md`). If the
protected branch moved since and its take-up is red or in conflict, that
pass merges nothing and **voids the acceptance**: the answer stays in the
record with `voided`, the Outcome goes back through the end of its Spec,
and he answers again on a new dossier.

**`record --response "constats rendus"`** takes the same three, and
`--findings`, a JSON file:

```json
{"findings": [
  {"text": "…", "cites": {"kind": "user_story", "ref": "user story 3"},
   "repair": {"title": "…", "what_it_delivers": "…", "demonstration_line": "…",
              "acceptance_criteria": [{"entry_point": "…", "observable": "…", "false_if": "…"}]}},
  {"text": "…"},
  {"text": "…", "later": true}
]}
```

`text` is one line, Benjamin's words. The file may be left out when a
proposition « à faire avant d'accepter » is waiting: it is the batch.

**`record --response abandonné`** takes `--reason`, one line. It is
recorded with the commit and the fingerprint of the dossier he judged — the
Delivered Outcome, or the one of a « non conforme » request. The next pass
closes the convoy with that reason and merges nothing.

**`resolve-exception`** records, on his words, that the Planning Exception
of the last batch is resolved — once the Spec is amended (T40, af-o6tu3z;
Spec §11, « Spec amendée et graphe révisé »). The exception keeps the
digest of the approved Spec the convoy was published from when it was
raised (`exception.spec_digest`); while the convoy still carries that
digest (`convoy.spec_digest` in `bin/convoy-state show`), the call is
refused. The digest changes when the amended Spec is approved
(`bin/spec-approve`, which approves again an approved Spec whose text
changed) and the revised graph is published from it
(`bin/ticket-graph-publish bd-patch`, which writes it on the convoy). The
refusal names the step that is missing, read on the Spec itself (T52,
af-ezqgma): the Spec has not been amended; its text changed but the new
version is not approved (`bin/spec-approve`); or it is approved and the
revised graph is not published from it (`bin/ticket-graph-publish
bd-patch`).

**`proposals`** creates the proposition of each « plus tard » he gave — a
verdict on a proposition, an Owner Finding of his last answer — that has
none yet, and answers `created` and `proposals_pending` (each names the
`proposition` or the number of the `finding`; a pending one carries the
`detail` of the door). It takes no `--approved-by`: it records nothing he
did not say. A proposition door that fails is **not a refusal of his
answer**: `verdict` and `record` have already written it, exit 0, and name
what is missing under `proposals_pending`; each pass of
`bin/convoy-advance` then runs `proposals` until nothing is missing
(`acceptance.owner_proposals`, `docs/CONVOY_ADVANCE.md`).

Every answer is one JSON object on stdout. **Exit codes**: 0 done; 1
refused (`error` starts with `refus : `); 3 the convoy is in an « état sans
règle » (`unruled` carries the anomalies `bin/convoy-state show` found;
nothing is recorded on such a convoy); 4 the convoy does not carry the mark
(answered as `bin/convoy-state` answers it, nothing touched).

## How code routes an Owner Finding

| The finding | Route | What follows |
| --- | --- | --- |
| carries `later: true` | `later` (« plus tard ») | a proposition created at once through the proposition door, named on the finding (`proposal`); outside this Outcome, blocks nothing. A `repair` with it is refused |
| cites (`cites.kind`) a `user_story` whose number the Spec holds, or an `anchor` that a prototyped state of a Validated Prototype of the Spec holds (T40: read by `bin/prototype-conformance anchors` in the repository of the project, at the commit the Spec names; `cites.ref` is the name of the anchor) | `repair` (« réparation ») | the drafted `repair` is **required** — refused without it; it is stored as `draft`, restoring what the finding cites, and published by the next pass |
| anything else: no citation, a story the Spec does not have, an anchor no prototyped state holds (or a Spec that names no Validated Prototype), another kind of citation | `planning_exception` | joins the **one** Planning Exception of the batch (`exception.findings`); **never a repair**: Benjamin asks for what the Spec does not require |
| a proposition whose verdict is « à faire avant d'accepter » | `planning_exception` | added by code to the batch, with its text; the verdict then names the answer and no longer blocks |

## What « constats rendus » triggers

1. `bin/owner-answer` checks the approver, the words and the dossier (same
   refusals as « accepté » on the commit, the tip, the fingerprint and the
   state of the pack).
2. `bin/convoy-state record-owner-answer` routes each finding and, **in one
   tracker write**: appends the answer; withdraws `gc.flow.delivered` and
   `gc.flow.acceptance`; withdraws `gc.flow.end_round` and sets
   `gc.flow.counter.end_rounds` to 0 — the batch gets its own rounds of the
   end. Nothing is closed.
3. `bin/owner-answer` creates one proposition per `later` finding
   (`set-owner-proposal`), then clears the Acceptance Request on the
   escalation door (`bin/escalation-door clear`): it no longer waits for
   him. The same clearing follows « accepté » and « abandonné ». A door
   that fails is said under `door`; the answer stays recorded.
4. **The next pass** of `bin/convoy-advance` (`settle_acceptance`) publishes
   one `repair` per finding of route `repair`, through the patch door, and
   names it on the finding (`set-owner-repair`): `acceptance.owner_repairs`.
5. **The end of the Spec is held** while a `repair` finding has no published
   ticket or the Planning Exception of the batch is open
   (`acceptance.owner_hold`): the end-of-Spec gate does not run, and
   `record-delivered` refuses.
6. Each repair goes through the unchanged flow: started by the pass, the
   ticket-end gate, merged into the integration branch.
7. Once every ticket is closed and nothing is held, the **whole**
   end-of-Spec gate runs at the new tip: mechanical verdicts, a fresh
   Outcome Evaluation and end code review (freshness is commit equality), a
   new Evidence Pack — which opens with **rubric 0 « Depuis ton dernier
   jugement »** (`docs/EVIDENCE_PACK.md`): his words, the dossier he
   judged, and per returned finding its route, what was done, the proof —
   then Delivered and a **new Acceptance Request**.

## Refusals

| Command | Refused when | Written |
| --- | --- | --- |
| all | `--approved-by` is not the declared human approver of the project, or that approver cannot be read (tickets naming no single project) | nothing |
| all | the convoy is in an « état sans règle »: exit 3, not a refusal | nothing |
| `verdict`, `record` | the last answer is « accepté » or « abandonné » and no red replay voided it: nothing reopens it | nothing |
| `verdict`, `record`, `resolve-exception` | the convoy is closed by command (`convoy.closed`): « rien ne le rouvre, ni lui ni ses tickets ; un défaut ou un souhait trouvé après entre comme travail nouveau, par un Planning Run » | nothing |
| `verdict` | the verdict is not one of the three; the convoy is not Delivered; the id is not a proposition of the convoy; no words; the verdict already had its follow-up and another one is given | nothing |
| `record` | `--response` is « refusé » (return findings or abandon instead), a partial acceptance (`--stories`, « accepté partiellement »…), or unknown | nothing |
| `record` accepté, constats rendus | no words; no `--commit` or `--pack-digest`; the convoy is not Delivered | nothing |
| `record` accepté, constats rendus | the commit is not the one of the dossier; it is no longer the tip of the integration branch (`bin/evidence-pack check`, `tip`); the fingerprint is not the dossier's; the pack is not « à jour » (périmé, altéré, absent, incomplet) | nothing; the next pass generates a new dossier |
| `record` accepté | a proposition has no verdict; a proposition « à faire avant d'accepter » has not been returned | nothing |
| `record` constats rendus | no finding and no proposition to do first; a malformed finding; a finding that cites a held story or an anchor without its drafted `repair`; `later` with a `repair`; a finding that cites an anchor while the Validated Prototype cannot be read (the commit is neither in the repository nor on its `origin`): nothing is routed on a citation that cannot be checked | nothing |
| `record` abandonné | no `--reason`, empty or on several lines; the convoy is neither Delivered nor carrying a « non conforme » request | nothing |
| `resolve-exception` | the last answer carries no Planning Exception; no words; the convoy still carries the digest of the approved Spec the exception was raised on — the refusal says which step is missing: the amendment of the Spec, its new approval, or the revised graph | nothing |

Refused by `bin/convoy-state` itself, whoever calls it: `set-owner-repair`
with a ticket the convoy does not track or that is not a `repair`, or a
second repair for a finding; `set-owner-proposal` and
`set-verdict-proposal` with a second proposition.

## State written

`gc.flow.judgement`, shown as `convoy.judgement` by `bin/convoy-state show`:

- `verdicts`: `{proposition, verdict: avant|plus_tard|sans_suite, approver,
  words, commit, at}`, then `proposal` (« plus tard ») or `answer` (the
  number of the « constats rendus » answer that returned it);
- `answers`, oldest first: `{response: accepted|findings|abandoned,
  approver, commit, pack, at}` with `words` (accepted, findings), `reason`
  (abandoned), `findings` — each `{text, route, cites?, draft?, ticket?,
  proposal?, proposition?}` — and `exception`: `{findings: [n…], at,
  resolved?: {approver, words, at}}`. An « accepté » may carry `voided`:
  `{cause: regression|fidelity|start|conflict, at}`, written by
  `bin/convoy-state void-acceptance` and never by this tool
  (`docs/OUTCOME_PROMOTE.md`).

## Environment

| Variable | Default | Used for |
| --- | --- | --- |
| `FACTORY_ROOT` | the parent of `bin/` | `config/projects/<rig>.toml` and the project's `rig_dir` |
| `GC_BIN` | `gc` | reading the tickets (`gc bd show`) |
| `PROJECT_PLANNING_PROFILE_BIN` | `bin/project-planning-profile` | the declared human approver |
| `PROPOSAL_DOOR_BIN` | `bin/proposal-door` | creating the propositions « plus tard » |

## A session

```bash
# one proposition in the dossier: it needs its verdict first
./bin/owner-answer verdict af-convoy --proposition af-t3:out_of_ticket.1 \
    --verdict "sans suite" --approved-by benjamin --words "Pas utile."
# he returns one finding that cites user story 3
./bin/owner-answer record af-convoy --response "constats rendus" --approved-by benjamin \
    --words "Il manque le JSON." --commit <commit of the dossier> \
    --pack-digest sha256:<fingerprint> --findings findings.json
# … the pass publishes the repair, delivers it, runs the whole end again;
# a new Acceptance Request arrives, its dossier opens with rubric 0
./bin/owner-answer record af-convoy --response accepté --approved-by benjamin \
    --words "C'est bon pour moi." --commit <new commit> --pack-digest sha256:<new fingerprint>
# … the next pass of the order merges the integration branch into the
# protected branch and closes the convoy (bin/outcome-promote)
```

The commit and the fingerprint are the ones `bin/acceptance-session open`
answers (`commit`, `digest`).

## The Cockpit

For a convoy that carries the mark, the one-click « Accepter »
(`accepter_chantier`) is refused with a message pointing here, and the
stage « Accepté » is read from the recorded answer, not from
`gc.cockpit_chantier_accepted` (`docs/COCKPIT.md`). Unmarked convoys are
unchanged.

## Proof

- `tests/owner-answer-test.py` (fake tracker, Delivered Outcome of the
  delivery fixture, about 2 min): « accepté » recorded with words, commit
  and fingerprint, and each of its refusals re-reading the tracker, the
  packs and the calls to the proposition door; the three verdicts; the
  routing of a batch and the Outcome back in delivery; Delivered refused
  while a repair is unpublished or the exception open; the request cleared;
  rubric 0 of the next dossier; « abandonné » and its reason; « refusé »
  and partial acceptance; a convoy without the mark.
- `tests/convoy-stops-fixture-city-test.py`, class
  `OwnerAnswerOnTheFixtureCity`: on the graph of the Fixture City, with the
  real passes — « accepté » waits for the verdicts, a returned finding is
  repaired, delivered and judged again, then accepted
  (`docs/FIXTURE_CITY_ORACLE.md`).
- `tests/cockpit-chantiers-test.py`: the click refused on a marked convoy,
  « Accepté » read from the recorded answer.

## Limits

- **The answer is not the merge.** Between « accepté » and the pass that
  follows it the Outcome is accepted and unmerged, and it stays so while
  that pass cannot merge (`docs/OUTCOME_PROMOTE.md`, Limits). An
  « accepté » can also be voided by that pass, and nothing tells Benjamin
  when it happens: a new Acceptance Request arrives once the repair is
  delivered, and the record keeps the cause.
- **The Planning Exception of a batch is recorded and holds the end of the
  Spec, nothing more.** Amending the Spec and revising the graph is a
  Planning Run done by hand: no code starts it and nothing notifies the
  Mayor. `resolve-exception` checks that the convoy is published from
  another approved Spec than the one the exception was raised on (T40);
  that the amendment answers the findings is Benjamin's word. The whole
  passage — `bin/spec-approve` on the amended Spec, `bd-patch`, then
  `resolve-exception` — is walked by the real doors in
  `tests/owner-exception-amended-spec-fixture-city-test.py` (T52). An exception
  recorded before T40, or on a convoy that carries no Spec digest, keeps no
  digest and is resolved on his words alone.
- **The issue of a « non conforme » request is still read by nothing**
  (`bin/acceptance-session record`: relancer, planification, abandon):
  T29's acceptance criteria cover the Delivered Outcome only. « abandonné »
  can be recorded here on a « non conforme » dossier, and takes that
  request off the door's list as it does an Acceptance Request; « relancer
  un tour » does not withdraw `end_stop`, and its request stays listed.
- **Nothing prevents an agent from inventing Benjamin's words** or passing
  his name in `--approved-by`, as the Spec assumes: the record makes it
  visible afterwards.
- **Routing reads the citation, not the meaning**: a finding that cites an
  existing story while asking for behaviour beyond it is routed as a
  repair. The patch door and the review of the ticket are the next guard.
- **A proposition door that creates the proposition but whose name is not
  written on the convoy afterwards** (`bin/convoy-state` failing between
  the two) leaves it pending: the next `proposals` creates a second one.
- **A proposition door that keeps failing holds nothing**: the Outcome can
  be Delivered and accepted while a « plus tard » still has no proposition;
  every pass says so (`acceptance.proposals_pending`) and nothing else
  reports it. Once « accepté » or « abandonné » is recorded the pass no
  longer runs `proposals` (it only follows the answer,
  `docs/CONVOY_ADVANCE.md`), and on the closed convoy the proposition can
  no longer be named: a « plus tard » still pending at that moment is to
  create by hand through `bin/proposal-door`.
- **The Cockpit still shows « Accepter »** on a closed marked convoy whose
  last answer is not « accepté »: one closed by hand with no recorded
  answer, and one closed by command on « abandonné » (T30), which it
  renders as delivered and waiting for him. The click is refused.
- No real convoy reached an answer.
