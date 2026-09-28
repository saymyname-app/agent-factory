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
