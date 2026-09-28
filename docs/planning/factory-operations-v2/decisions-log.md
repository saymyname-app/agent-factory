# Factory operations v2 — decisions log (grilling with Benjamin)

Working log of the A5 Planning Run; the durable map is `planning-map.json`
(`bin/wayfinding-run`). Times Europe/Paris.

## framing — 2026-09-28

Intent (Benjamin, 2026-09-28): Q1 « B », Q2 « A », Q3 « Je te laisse choisir »,
Q4 recommendation followed, Q5 « C », Q6 « Oui je suis d'accord ».
Mechanism (PO interpretation):
1. Run as a Wayfinding Run: one Planning Decision per theme, resumable from this map.
2. The router runs with `--repo-root` on a `po/*` worktree of `main`; the
   reservation file it rewrites on publish reaches `main` through a normal PR.
   The durable fix of the live-root rewrite (F18) is a ticket of this graph.
3. Gas City pack orders (20): configure only (enable/disable/tune); an
   unfit one is disabled and replaced by our own order; never forked (PO choice, delegated).
4. Themes, in order: dispatch & wake; escalation & alerts; work preservation;
   project-agnostic; hygiene; planning doors.
5. The Factory (Mayor + workers) delivers the graph; the PO agent intervenes
   only when a defect of the Factory's own mechanics blocks, and that defect
   becomes an A5 finding.
6. Done = graph delivered and closed + a written verdict for every order (28)
   and every Mayor manual operation, versioned in `docs/INVENTORY.md` + no
   `order.failed` over the 24 h after the last merge.

## t1-dispatch-wake — 2026-09-28

Intent (Benjamin, 2026-09-28): « Q1.1 a+c, Q1.2 a, Q1.3 a (je valide tes recommandations) ».
Mechanism (PO interpretation):
1. Wake: `ticket-graph-publish` itself notifies the Mayor at the end of a
   publish (the only door approved work enters by). Safety net: ready work
   idle > 15 min with no active worker re-wakes the Mayor.
2. One dispatch door for every rig and every formula (validates target,
   formula, `--reassign`); raw `gc sling` is forbidden to the Mayor and a
   check reports any dispatch that bypassed the door. Resolves F16
   (`build-basic` has no valid door today).
3. Resume, don't redo: on re-dispatch the door finds the ticket's branch, PR
   and notes and the worker must continue them; a re-planned ticket carries
   a "supersedes <old id>" link and inherits the existing work. Starting over
   only when the worker records in the ticket why the old work is unusable.
Does NOT mean: the Mayor picks work on its own (decision 7 stands).

## t2-escalation-alerts — 2026-09-28

Intent (Benjamin, 2026-09-28): « Q2.1 b, Q2.2 : OK pour toute ta recommandation, Q2.3 A, Q2.4: OK ».
Mechanism (PO interpretation):
1. One "À TOI" (NEEDS BENJAMIN) list in the Factory, fed by one escalation
   door; the operator session (Claude/Codex) shows it first at session start.
   C01 later adds the phone channel on top of this same list (decision 6
   keeps ntfy for C01).
2. Straight to Benjamin: a decision only he owns (consent, personal data,
   spend, production, behaviour/acceptance change); Factory stopped (Mayor
   down > 10 min, all providers exhausted); a plan fully delivered.
   Mayor first, Benjamin only if unresolved after 2 h: an order failing
   repeatedly; a stuck PR or repeated red CI.
3. Total provider exhaustion: stop dispatching new work, resume by itself at
   quota reset, one line on the list.
4. Plumbing: `campaign-pointer` replaced by the escalation door; the ~40 dead
   `gc.campaign_*` fields on af-1vr4 cleared; the unread watchdog signals
   file replaced by the list (C01 reads it); no escalation may fail silently
   (F14 `>/dev/null || true`).
Does NOT mean: a phone channel before C01.

## t3-work-preservation — 2026-09-28

Intent (Benjamin, 2026-09-28): « Q3.1 : OK », « Q3.2: Je ne sais pas ».
Mechanism (PO interpretation):
1. Workers push their branch from the first commit and after each commit;
   the branch name is recorded on the ticket at claim time (feeds t1 resume).
2. factory-guard's local-commit backup also covers the product rigs,
   detached HEADs included.
3. No `rm -rf` fallback in worktree cleanup (`mol-scoped-work`,
   `factory-do-work-workspace`): a worktree holding unpushed work is kept
   and the Mayor is alerted.
4. A fresh branch with no own commit is spared 24 h by factory-guard §6.
5. No build/test as root in worker worktrees; the guard reports any
   root-owned file there. Origin of the 2026-09-27 root files unknown (a root
   WSL shell opened 2026-09-27 14:09, author unknown) — no operator rule added.

## t4-project-agnostic — 2026-09-28

Intent (Benjamin, 2026-09-28): « Q4.1: A »; Q4.2 « OK mais faut pas encombrer
AGENTS.md betement, utilisons (si et seulement si y'a besoin) index et
documents exterieurs au md principal pour les elements de contextes qui sont
pas utiles à chaque fois … (c'est qu'une intuition) »; Q4.3 « j'ai
l'impression que B suffirait. Plutôt B. ».
Mechanism (PO interpretation):
1. One project file per project in the Factory (e.g.
   `config/projects/saymyname.toml`: repos, protected branch, required CI);
   every script reads it; a check fails when a rig known to Gas City has no
   project file. Product rules stay in the product repos.
2. SayMyName sections of Factory docs move to dedicated files in the product
   repos (progressive disclosure): the main `AGENTS.md` gets at most a
   one-line pointer, only if an agent needs it to find them. Host operations
   (Dolt backups) become a generic Factory doc; dead sections (old cutover,
   M6 rollback) go to `legacy/`. Tests use a synthetic operator
   (`operator-1`); runtime messages name "the operator" from config. A setup
   script enables `.githooks` on a fresh clone. The two local-only tests run
   in a nightly order; failure pages the Mayor.
3. PII guard retired (code + hook calls): it was INACTIVE everywhere (no
   identifier list on the machine). The written rule in the SayMyName repo
   `knowledge/real-person-data.md` stays.
Does NOT mean: bigger `AGENTS.md` files.
