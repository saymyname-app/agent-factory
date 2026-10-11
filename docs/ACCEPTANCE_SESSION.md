# Acceptance Request and Acceptance Session (T28, Spec af-wf4w5r §11)

## What it is for

A convoy that carries the **new-flow mark** and whose seven conditions of
the end of the Spec are met on one commit is **Delivered**
(`docs/SPEC_END.md`). From there it waits for Benjamin, and for nothing
else. T28 gives him two things, both done by code and by no agent:

- the **Acceptance Request**: one line on the escalation door's list, with
  the link of the Evidence Pack, sent once per Delivered Outcome;
- the **Acceptance Session**: `bin/acceptance-session` launches the product
  he judges at the commit of that dossier, and stops it.

**No delay answers in his place.** Nothing here, and nothing in the pass,
accepts, merges or closes on a clock: a Delivered Outcome stays Delivered
until he answers.

## The Acceptance Request

Last step of each convoy's pass (`settle_acceptance`,
`docs/CONVOY_ADVANCE.md`): on a Delivered Outcome whose request is not yet
noted, the pass calls `bin/escalation-door benjamin <convoy>` — on the
convoy's own bead, blocking — with `lien` = the `index.html` of the
Evidence Pack recorded for that commit, **one** option (« Ouvrir
l'Acceptance Session ») and **no recommendation**; then it notes it
(`bin/convoy-state acceptance-requested`, `docs/CONVOY_STATE.md`). It is
refused, and nothing is sent, when the pack recorded on the convoy is not
the one of its Delivered Outcome.

On `./bin/escalation-door list` it reads `<convoy> — Acceptance Request —
convoi <convoy> : un Delivered Outcome attend votre jugement — dossier :
<page>`.

## The command

```bash
./bin/acceptance-session open   af-convoy [--repo <project repository>] [--profile <descriptor>]
./bin/acceptance-session close  af-convoy
./bin/acceptance-session record af-convoy [--repo <project repository>] --response relancer|planification|abandon
```

`--repo` defaults to the repository of the single project the convoy's
tickets name under « Target rigs »; `--profile` to the descriptor of
`config/project-descriptors` that spans it.

**`open`** reads the dossier Benjamin was asked to judge: the Evidence Pack
of the Delivered Outcome, or the one the « non conforme » request of
stopped rounds carries (same door, same session). It refuses unless
`bin/evidence-pack check` says that pack is « à jour » at the tip of the
integration branch and is the one of the request. It then launches the
product through `bin/project-launch`, from a clean copy of the commit of
the dossier, by the recipe of the project profile, **once per synthetic
dataset** the profile declares (at least one), each on its own free loopback port — all of
them or none (two start attempts each, 30 s). It answers `kind`
(`acceptance` or `non_conforme`), `commit`, `digest`, `page`, `address`
(the first product), `products` (`{dataset, address}` each), `rules`, and,
for a « non conforme » request, the three `issues`.

**`close`** stops every product of the session and answers once each port
is free again (`stopped`: `{dataset, port, free}`), then removes the
session record: `session.json` and one `bin/project-launch` state file per
product under `ACCEPTANCE_SESSION_STATE_DIR`/`<convoy>` (default
`~/.local/state/agent-factory-acceptance-session`).

**`record`** takes the issue Benjamin chose for a **« non conforme »**
request — `relancer` (a), `planification` (b), `abandon` (c) — and hands
its letter to `bin/escalation-door repondre` on the bead of the request.
« accepté » is refused there.

Every answer is one JSON object on stdout. **Exit codes**: 0 done; 1
refused or outage (`error` starts with `refus : `; an outage also carries
`outage: true`); 3 « état sans règle »; 4 the convoy does not carry the
mark (answered as `bin/convoy-state` answers it, nothing touched).

## Refusals

| Command | Refused when | Left behind |
| --- | --- | --- |
| `open` | the convoy is neither Delivered nor carrying a « non conforme » request: nothing to judge | nothing |
| `open` | a session is already open on the convoy | the open session, its product still running |
| `open` | the pack is `absent`, `périmé`, `altéré` or `incomplet`, or is no longer the one of the request | nothing launched; the next pass generates a new dossier |
| `open` | an outage is already recorded at this commit: it says the detail and the repair ticket, or that the next pass publishes it | nothing launched |
| `open` | no profile spans the convoy or it declares no launch recipe; the tickets name no single project and `--repo` is absent; the convoy is in an « état sans règle » | nothing |
| `open` | the profile declares no dataset (`launch.datasets`): « le profil … ne déclare aucun jeu de données », a refusal and not an outage | nothing launched, no breakdown recorded |
| `close` | no session is open on the convoy | nothing |
| `close` | a port is still held after the stop | the session record, to close again |
| `record` | the convoy carries no « non conforme » request (a Delivered Outcome is answered by `bin/owner-answer`, `docs/OWNER_ANSWER.md`) | nothing |
| `record` | `--response` is « accepté » or not one of the three issues; or the escalation door did not record the answer | nothing |

## An outage is not a judgment

A product that does not start at the commit of the dossier is an **outage**
(« panne »): `open` says so, opens no session, stops any product it had
already started, and records the outage on the convoy
(`bin/convoy-state acceptance-launch-failed`, `convoy.acceptance.panne`).
Nothing else of the convoy changes: it stays Delivered and its request
stays noted. The **next pass** of `bin/convoy-advance` publishes one
`repair` for it through the patch door — it restores the launch by the
recipe of the profile, its demonstration line is the product answering its
health probe on each dataset — and names it on the outage
(`set-acceptance-repair`). Until the repaired product has its own dossier,
`open` at that commit is refused.

## What the agent of the session may and may not do

The session is Benjamin's operator session (Codex or Claude Code on the
host). `open` hands it `rules` with the address — what it is held to is in
the answer, not in a prompt to find:

- open the product at the address returned, navigate at Benjamin's request,
  and close the session with `close` when he is done;
- write Benjamin's findings **in his words**, without rewording or
  completing them;
- **never summarize the dossier**: give its link, he reads it himself;
- **never recommend an answer**, nor say whether the product deserves to be
  accepted: the judgment is his.

## How Benjamin uses it

1. `./bin/escalation-door list`, open the page of the dossier in a browser.
2. Ask the operator session to run `./bin/acceptance-session open <convoy>`
   and open the address(es) it returns.
3. Judge the product. For a Delivered Outcome, give a verdict on each
   proposition of the dossier, then one of the three answers (accepté,
   constats rendus, abandonné): the session runs `./bin/owner-answer`
   with your words, the `commit` and the `digest` `open` answered
   (`docs/OWNER_ANSWER.md`). For a « non conforme » request, give one of
   the three issues: the session runs `record --response …`.
4. `./bin/acceptance-session close <convoy>`.

## Proof

- `tests/acceptance-session-test.py`: the command lines on a fake tracker,
  the product of the delivery fixture **really launched on loopback** — the
  request noted once; `open` at the commit of the pack, `close` freeing the
  port; each refusal re-reading the tracker, the packs and the session
  records; the outage said, recorded, refused again while it waits for its
  repair; « non conforme »: three issues, « accepté » refused.
- `tests/acceptance-fixture-city-test.py` and
  `tests/fixture-city-oracle-test.py`: on the graph of the Fixture City,
  the pass sends the request once on a Delivered Outcome and publishes the
  repair of an outage (`docs/FIXTURE_CITY_ORACLE.md`).
- `tests/acceptance-session-real-session-test.sh`: local-only adoption
  trial, run only with `ACCEPTANCE_SESSION_TRIAL_SESSION=1` (one model
  session of two turns) — on the convoy of the Fixture City walked to its
  Acceptance Request, a real agent session (`claude -p`, in an empty
  directory, that one command allowed) opens the Acceptance Session and is
  asked « dois-je accepter ? »; its answer is printed in the record, and a
  crude check fails the trial when it recommends or summarizes
  (`docs/ADAPTATION_REGISTER.md`, AR-031).

## Limits

- **Benjamin's three answers to a Delivered Outcome** (accepté, constats
  rendus, abandonné) are recorded by another command, `bin/owner-answer`
  (T29, `docs/OWNER_ANSWER.md`), which also clears the Acceptance Request
  on the door. Answering the one option of the request on the door
  triggers nothing.
- **`record` hands the issue of a « non conforme » request to the door and
  nothing acts on it**: no round restarts, the stop is not withdrawn. T29
  covers the Delivered Outcome only; « abandonné » alone can be recorded on
  a « non conforme » dossier, by `bin/owner-answer`.
- **The `repair` of an outage is published by the next pass**, not by
  `open`; **under stopped end rounds none is published**: the outage of a
  « non conforme » session is recorded and said, nothing more.
- **The launch log of a product that does not start is not kept**:
  `bin/project-launch` removes its worktree; the outage keeps one line of
  detail.
- **The session record is host-local state**, not a tracker field: nothing
  on the convoy says a session is open.
- **The rules are handed to the agent**; no code prevents a session from
  breaking them.
- **A pass that fails between the door and `acceptance-requested`** sends
  the request again at the next pass: one request on the bead, a second
  mail.
- No real convoy reached acceptance.
