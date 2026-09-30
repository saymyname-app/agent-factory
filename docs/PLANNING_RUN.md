# Planning Run (A6b: the wired flow)

## Status and purpose

Every Planning Run, for any project, is driven from the operator session
(Claude or Codex, the PO agent) with Benjamin, using the upstream Matt
Pocock skills (`mattpocock/skills`, pinned to `c55ee46` -- the Method
Baseline) as written, with Beads as the only tracker. This doc is the one
place that describes the chain end to end; `docs/agents/issue-tracker.md`
gives the exact `bd` commands each step uses.

This replaces `PLANNING_RUN_ROUTER.md` and `WAYFINDING_RUN.md`, which
described a router and a JSON-file Planning Map that read a hand-written
request file and trusted self-declared fields to decide whether a run was
"simple". Those tools are being retired (W10, W11); until then they remain
independently callable for their own tests, but they are no longer how a
Planning Run starts.

## The chain

1. **`/wayfinder` charts the run.** The operator session and Benjamin turn
   an intent into explicit decisions. If charting finds no fog, the run
   takes the **No-fog exit** and finishes in the same session as an
   **Unmapped Planning Run**: Benjamin's exact words and the date (Paris
   time) are recorded as `no_fog_evidence` in place of a Planning Graph.
2. **The overflow rule.** If charting instead finds fog, or the session
   outgrows itself, `/wayfinder` promotes the run into a **Planning Map
   Bead** with typed **Planning Decision Bead** children, all on the
   planning Work Plane -- see `docs/agents/issue-tracker.md` ("Wayfinding
   operations") and `docs/PLANNING_MAP.md` (`bin/planning-map`) for the
   exact shape and the tool that creates, checks, closes and safely
   updates the map. An Unmapped Planning Run that later surfaces fog or
   outgrows one session resumes `/wayfinder` at map creation instead of
   spanning several sessions unmapped.
3. **`/to-spec` writes the Spec.** A prose Spec, synthesized from the
   conversation and the finished map (or the No-fog exit), is published as
   a planning-plane Spec bead (`gc.plane: planning`) -- not a child of the
   map, so the map can reach zero open children. Its metadata carries
   `planning_run_target`, `planning_map` (the map bead id, or `"none"`),
   and `no_fog_evidence` when unmapped.
4. **Benjamin approves the Spec live**, through `bin/spec-approve
   bd-approve` (`docs/SPEC_APPROVE.md`, "Bead mode"). Before any write the
   door refuses unless, in order: the Spec is not already approved; its
   Planning Run target is allowed through by the active Planning Run
   Reservation; its named map is finished (or it names no map and carries
   non-empty No-fog evidence); the approver is the project's declared
   human approver; the evidence is non-empty. On success it freezes the
   Spec's exact content digest and closes the map in the same call.
5. **`/to-tickets` slices the approved Spec.** Benjamin approves the exact
   breakdown once -- title, blocked-by, what it delivers, acceptance
   criteria, target rig, scope paths if any -- exactly as it will be
   published. The approved breakdown is published as a Ticket Graph Draft
   bead linked to the Spec bead; target rigs and scope paths live in its
   metadata, never in ticket text.
6. **The publication door (`ticket-graph-publish`)** publishes the draft
   through `bin/ticket-graph-publish bd-publish` (or `bd-patch` to revise
   an already-published graph). It refuses unless the named Spec bead is
   still approved and its current digest still equals the approved one.
   On success, in the same door: delivery beads and the convoy are created
   atomically (one approved ticket becomes exactly one delivery bead), the
   Planning Run Reservation advances (to `next`, or clears) when the
   Spec's target is the active one, and the Mayor is woken by default.
7. **The Mayor executes the published Delivery Work Graph.** No planning
   bead is ever dispatched, woken for, or counted as delivery. When the
   convoy closes, the Spec and Ticket Graph Draft beads close with it
   (`bin/planning-artifacts-close`) -- both stay open and readable during
   delivery.

## Research and prototype tickets

A research or prototype ticket (a Planning Decision Bead labelled
`wayfinder:research` / `wayfinder:prototype`) blocks `/to-spec` like any
other map ticket.

- **Research**: a subagent of the operator session calls the research
  skill and writes its cited assets on a pushed, never-merged
  `research/<map>-<topic>` branch of the planned project's repo (in a
  worktree, never in the live root); the ticket's resolution comment links
  the branch.
- **Prototype**: assets go on a pushed, never-merged
  `prototype/<map>-<topic>` branch, shown to Benjamin as a private
  Artifact page -- the page is only a view, never where the decision
  lives. Benjamin chooses the variant in the live chat, and that choice is
  recorded verbatim in the ticket's resolution comment.
- Either way, the local worktree for the ticket is removed when the ticket
  closes, so finished planning leaves no worktree behind.

## Claims and concurrency

An operator session's claim on a planning ticket (`bd --actor
po-agent/<session-id> update <id> --claim`) holds until released or
closed; the Factory-owned orphan sweep treats `po-agent/*` claims and
planning-plane beads as owned and never drops them (see
`docs/agents/issue-tracker.md`).

## Reservation

`.gc/runtime/planning-run-reservation.json` (seeded from
`config/planning-run-reservation.json`) names the one Planning Run target
the Factory is currently reserving all new capacity for; `bin/spec-approve
bd-approve` checks it, `bin/ticket-graph-publish bd-publish` advances it.
It applies to mapped and Unmapped Planning Runs alike.

## Retiring paths

`bin/planning-run-router`, `bin/planning-run-to-spec-oracle`, the file
modes of `bin/spec-approve` and `bin/ticket-graph-publish`, and
`bin/wayfinding-run` are retired in W10/W11; each retirement is recorded
in `docs/ADAPTATION_REGISTER.md`. A6b's own Ticket Graph Draft was the
last one published through the old router path.
