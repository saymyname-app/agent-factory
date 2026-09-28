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
