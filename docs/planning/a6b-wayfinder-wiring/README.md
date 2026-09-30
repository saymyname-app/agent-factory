# A6b — Wayfinder wiring: planning records

**Last run through the old path.** A6b's Ticket Graph was published on
2026-09-30 at 03:06 (Paris) through `bin/planning-run-router`, which expects a
`planning-session.json` and a file Spec from the to-spec oracle. It is the last
Planning Run published this way: the graph's own tickets W09-W12 retire the
router, `wayfinding-run`, the oracle and the planning prototypes.

- Source Spec: Planning bead **af-3s8prq** (`bd show af-3s8prq`), written by
  upstream `/to-spec` (mattpocock/skills c55ee46) from map **af-0aiero**.
  `spec-source.md` is its verbatim copy.
- Ticket Graph: `/to-tickets af-3s8prq`, 13 tickets W01-W13, convoy
  **af-59qjgh** (`publish-result.json`).
- Reservation: promoted from A6b to C01 by this publication
  (`config/planning-run-reservation.json`).

## Mechanical translation to the old path

Approved by Benjamin with the ticket text (live chat, 2026-09-30 03:04 Paris,
« J'approuve le texte, points 1-4 avec ADR comme archives, et la traduction »).

- `planning-session.json`: each oracle topic is a verbatim Spec section, with
  `confirmed_by: Benjamin`. behavior ← Problem Statement, Solution, User Stories.
  decision ← Implementation Decisions. acceptance_evidence ← Testing Decisions.
  non_objective ← Out of Scope. boundary ← the "Target rig" and the "parallel
  sessions" notes. provenance ← the Spec's opening paragraph, the Intent note
  and the "last run" note. experiment ← the research branches note.
  `complexity: complex`, `wayfinder_ceremony_invoked: true`,
  `interview_rounds: 7` (the map's 7 grilling tickets).
- `work-graph.json`: an export of map af-0aiero and its 15 tickets. The
  `owner` fields (GitHub noreply addresses) were removed before commit, per
  the no-personal-data rule.
- Spec approval evidence: Benjamin's approval of af-3s8prq (02:41 Paris).
  Ticket Graph approval evidence: the sentence above.

## Interpretations approved with the tickets (read these before W09-W12)

1. W09: the router doc and the wayfinding-run doc are each reduced to a
   one-line pointer to the new Planning Run doc. W10 then deletes the router
   doc, and W11 keeps the wayfinding-run pointer.
2. W10-W12, "except archives": archives are `docs/planning/**`, the
   reservation note naming the archived B12 plan, **and accepted ADRs**. ADRs
   are not rewritten; the only change is ADR-0027's planned one-line amendment.
3. W04 and W05 keep the file-Spec and file-draft modes only for the router,
   until W10 retires both.
4. Tool names in the scope paths (`planning-map`, `planning-run-reservation`,
   `planning-artifacts-close`, `factory-orphan-sweep`, `upstream-skills-check`)
   are proposals, not decisions.
