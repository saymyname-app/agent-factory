# Parallel delivery — decisions log (grilling with Benjamin)

Working log of the A6 Planning Run (SayMyName roadmap A6, Factory #269,
reservation `parallel-delivery`). Times Europe/Paris. One session, two
rounds (2026-09-29 01:30-02:00), so a simple Planning Session (no
Wayfinding map). Inputs in this folder: `research.md` (2026-09-28,
sourced: Gas City pools, Gas Town Refinery, GitHub merge queue) and
`facts.md` (2026-09-29, read-only live facts).

## Origin — 2026-09-28 (SayMyName decision 19)

Intent (Benjamin, 2026-09-28): « il faut que l'usine soit conçue pour
pouvoir travailler sur des taches en parallèle même si ca touche le même
dépot … vérifier les conflits, travailler sur plusieurs branches avant de
merge » ; P1 « a », P2 « a et b pour la ram c'est ok », P3 « a », P4 « oui
mais on avait justement fait le changement car ca posait probleme ».
Mechanism (PO): run placed after A5 and before C01; design for N workers,
first 2 on the Factory rig; Factory + SayMyName by design, Factory first;
WSL memory not raised; `main` up-to-date rule only once pr-autopilot
updates BEHIND PRs itself.

## Round 1 — 2026-09-29

Intent (Benjamin, 2026-09-29): « Q1 A, Q2 B, Q3 B, Q4 A, Q5 Tu recommandes
quoi ?, Q6 B puis C du coup ? c'est bien ce que tu recommandes ? Suivons ta
recommandation ici, Q7 (a) + (c) si besoin ». Q5: PO answered « (a) »;
Benjamin confirmed the full recap with « ok ».
Mechanism (PO interpretation):
1. Q1 — the four open proposals join this run: af-i3prh (parallel
   delivery), af-elhn7 (red PR left behind), af-6675l (worker wake/stop
   loop), af-87f9u (ticket fixed through another ticket's PR not
   reconciled).
2. Q2 — publish as soon as the Spec and graph are approved. Accepted
   consequence: if an A6 merge makes an order fail before 2026-09-30 00:50,
   A5's "24 h without order.failed" proof restarts.
3. Q3 — agent identity (PO-agent mails read as Benjamin's) is in scope;
   the stray untracked `.config/` in the live root is a bounded repair
   outside the graph (decision 7), not a ticket.
4. Q4 — no spend: no GitHub merge queue (needs GitHub Enterprise Cloud on a
   private repo). Poor-man's queue: ruleset "require up to date" on `main`
   + pr-autopilot updates BEHIND PRs one per tick.
5. Q5 — conflict repair returns the ticket to the worker pool with its
   branch and a rejection reason; any free worker rebases and fixes;
   2 repair attempts, then Mayor, then NEEDS BENJAMIN. No dedicated
   integration agent (Refinery), no author-only repair.
6. Q6 — light prevention + repair: tickets declare their file scope at
   planning; publish serialises overlapping tickets; a short hot-file list
   is never held by two workers. Dynamic leases are NOT built: overlaps
   and conflicts are measured, and a proposal is filed automatically only
   if conflicts recur despite declarations.
7. Q7 — proof of done: a final batch of independent tickets delivered by
   2 workers over one day, topped up with A4 inventory "to redo" lines if
   the batch does not fill the day. Does NOT wait for C01.

## Round 2 — 2026-09-29

Intent (Benjamin, 2026-09-29): « Q8: A, Q9: A, Q10: A, Q11: ok, Q12: ok,
Q13: A, Q14: Vrai, je n'envoi jamais de mail au mayor, je passe toujours
pas un agent, Q15: B (apres correction A), Q16: A mais une autre
conversation (celle lancée pour la Verif A3) me propose des changements
d'allocation de la ram ». Recap confirmed: « ok ».
Mechanism (PO interpretation):
1. Q8 — worktree per ticket hardened: lock on creation, branch from a
   freshly fetched `origin/<base>`, mandatory for every work formula; a
   scheduled order cleans worktrees whose work is merged or pushed, never
   one holding unpushed commits.
2. Q9 — tests run in a sandbox by default (throwaway HOME / city / beads,
   fake `gc` `bd` `gh` and provider CLIs first on PATH); a CI check fails
   any test that names the live root or calls the real `gc` without an
   explicit opt-in.
3. Q10 — one return loop for conflicts AND red CI (same as Q5); a ticket
   is finished only when merged; no full local battery before push.
4. Q11 — append-style registries restructured (CI discovers tests, indexes
   generated or one file per entry); the hot-file list keeps only what
   cannot be restructured (`city.toml`, SQL migrations).
5. Q12 — activation order: safe `main` → isolation → prevention →
   2 workers → final batch. Each step is safe on its own.
6. Q13 — "require up to date" activated on the Factory repo only; the
   product repos (`Say-my-name-back`, `Say-my-name-front`) keep their
   settings until a separate decision when their delivery resumes; A6 still
   verifies pr-autopilot reads their check names correctly.
7. Q14 — Benjamin never mails the Mayor: every operator agent gets its own
   identity, and the Mayor treats every mail as an agent's request, never
   as a decision of Benjamin.
8. Q15 — fix the cause first (wake counts only claimable work; resolved
   mail-reply beads close themselves), then a generic detector (> 10
   wake/stop cycles per hour on one session → alert + pause).
9. Q16 — memory floor: no new worker session while WSL available memory
   is below 1.5 GiB; real RAM per worker measured during the final batch.
   The `.wslconfig` caps proposed by the A3 conversation are Benjamin's
   host setting and do not conflict: the floor reads available memory, not
   the cap. A CPU cap shortens factory-guard's margin (A3, 180 s); a
   `.wslconfig` change needs `wsl --shutdown`, so it is done while no
   ticket runs.

## Patch 1 — 2026-09-29 (P25)

Intent (Benjamin, 2026-09-29, live chat): « a, patche le graphe A6 » — choice
a of the SayMyName incident review of 2026-09-29: attack cause B (a fake
accepts what the real tool refuses, and the failure is swallowed) inside A6
rather than in a separate Planning Run after it.
Mechanism (PO agent): `ticket-graph-patch-1.yaml` revises the published graph
`sha256:1e3ee0b5…` with one new ticket, P25 (af-kiy7lm), no blocker (P10,
which built the fakes, is delivered). Applied through `ticket-graph-publish
patch` (author `po-agent`); result in `patch-1-result.json`; convoy
`af-dsygc` now carries digest `sha256:4ab72f84…`. P22's own blockers were not
changed (patch refuses delivered tickets, and P22's blocker chain reaches
them); P25 still gates A6 through the convoy. Out of scope by decision Q10:
no full local battery before push.
