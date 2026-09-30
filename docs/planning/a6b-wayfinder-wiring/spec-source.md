# Spec — A6b: wire the upstream wayfinder into the Planning Run (Spec bead af-3s8prq, verbatim)

Spec for Planning Run A6b, synthesized by upstream /to-spec (mattpocock/skills c55ee46) from the finished Planning Map Bead af-0aiero (15/15 Planning Decision Beads closed, no fog). Each decision below cites the ticket it comes from.

## Problem Statement

Benjamin plans Factory and SayMyName work through a Planning Run, and wants that run to follow Matt Pocock's upstream chain as written: /wayfinder charts a map of decisions, /to-spec writes the Spec from it, /to-tickets slices it, and the Factory publishes the result. Today the Factory's Planning Run does not do that:

- Its only entry point, the Planning Run router, needs a hand-written planning-session.json and a request file, and trusts self-declared fields (complexity, wayfinder_ceremony_invoked, interview_rounds) to decide whether a map was used.
- Its Spec is synthesized by a 7-topic oracle from that JSON file, not by /to-spec from the conversation and the map.
- Its map lives in a JSON-file registry (wayfinding-run) that has no ticket types, blocking edges, fog or out of scope, while upstream keeps the map on the issue tracker (Beads here).
- The publication door never opens the Spec it publishes from, so a Spec edited after approval can still be sliced and published.
- Nothing stops a new Planning Run from being approved in place of the reserved one except the router, which is the piece being replaced.
- A claim on a planning ticket by an operator session is silently dropped after 5-10 minutes by Gas City's orphan-sweep, so two parallel sessions can work the same decision.
- Several planning prototypes (P02, P03, P04 resume oracle, P06) encode an allocation nobody will build and contradict how planning is now done.

C01 (Cockpit V2) was set aside because its first attempt was planned without the wayfinder method; it waits behind A6b.

## Solution

Every Planning Run, for any project, is driven from the operator session (Claude or Codex, the PO agent) with Benjamin, using the upstream skills as written, with Beads as the only tracker:

1. /wayfinder charts the run: a Planning Map Bead with typed Planning Decision Beads, all on the planning Work Plane. If charting finds no fog, the run takes the No-fog exit and finishes in the same session.
2. /to-spec writes a prose Spec from the conversation and the finished map (or the No-fog exit) and publishes it as a planning-plane Spec bead.
3. Benjamin approves the Spec live. The approval door checks the reservation, the finished map (or the No-fog evidence) and the declared human approver, freezes the Spec's digest and closes the map.
4. /to-tickets slices the approved Spec; Benjamin approves the exact breakdown once; the publication door (ticket-graph-publish) checks the Spec is still the approved one, creates the delivery beads and convoy atomically, advances the reservation and wakes the Mayor.
5. The Mayor executes the published graph; when the convoy closes, the Spec and draft beads close with it.

The router, wayfinding-run, the to-spec oracle, planning-session.json and the planning prototypes are retired, and each retirement is recorded in the Adaptation Register. Claims by operator sessions hold until released. A6b's own graph is the last one published through the old router path.

## User Stories

1. As Benjamin, I want every Planning Run to start with /wayfinder charting, so that I never have to decide up front whether a run is "simple".
2. As Benjamin, I want a run whose charting finds no fog to stop and ask me how to proceed, so that I choose the No-fog exit myself.
3. As Benjamin, I want my exact words and the date (Paris time) recorded when I choose the No-fog exit, so that an Unmapped Planning Run carries evidence instead of a self-declared flag.
4. As Benjamin, I want an Unmapped Planning Run that surfaces fog or outgrows one session to resume /wayfinder at map creation, so that no unmapped run spans several sessions.
5. As the operator session, I want the map and its tickets to live only in Beads, so that Claude and Codex read and write the same map with native bd commands.
6. As the operator session, I want a tool that creates a correctly shaped child ticket (parent, no inherited labels, wayfinder:<type>, planning plane), so that no ticket is created with the wrong labels or plane again.
7. As the operator session, I want a tool that checks a map (ticket shapes, labels, open children), so that I know deterministically whether the map is finished.
8. As the operator session, I want a safe map update that refuses when the map's description changed since I read it, so that a sibling session's decision line is never silently lost.
9. As the operator session, I want the map closed automatically when its Spec is approved, so that a map never outlives its Spec.
10. As Benjamin, I want to abandon a map by closing it and its open tickets with a reason I give, so that abandoning needs no special command.
11. As the operator session, I want my claim on a planning ticket (actor po-agent/<session>) to hold until I release or close it, so that a parallel session never takes the same ticket minutes later.
12. As the Factory maintainer, I want the orphan-sweep replacement to fail loudly when Gas City's upstream sweep script changes, so that a gc upgrade cannot silently reintroduce dropped claims.
13. As the Factory maintainer, I want the replacement sweep to keep releasing genuinely orphaned delivery claims, so that the original protection against stranded work is not lost.
14. As the operator session, I want research tickets resolved by a subagent of my session calling the research skill, so that research follows upstream and never reaches a Factory worker.
15. As Benjamin, I want research results kept on a pushed, never-merged research/<map>-<topic> branch of the planned project's repo, so that the Factory never holds project content and the why stays findable.
16. As Benjamin, I want prototypes kept on a pushed, never-merged prototype/<map>-<topic> branch and shown to me as a private Artifact page, so that I can review them from my phone.
17. As Benjamin, I want to choose a prototype variant in the live chat, recorded verbatim in the ticket's resolution comment, so that the decision is readable by Claude and Codex and never lives only in a page.
18. As the operator session, I want prototype tickets to block /to-spec like any other map ticket, so that no prototype is pushed into the delivery graph after approval.
19. As the operator session, I want the local worktree of a research or prototype ticket removed when the ticket closes, so that finished planning leaves no worktree behind.
20. As Benjamin, I want the Spec written by upstream /to-spec as prose from our conversation and the map, so that I review a readable document and not a JSON-derived one.
21. As the operator session, I want the Spec published as a planning-plane bead that is not a child of the map, so that the map can reach zero open children.
22. As the operator session, I want the Spec bead linked to its map (or marked planning_map: none with the No-fog evidence), so that the approval door can find what to check.
23. As the operator session, I want the Spec bead to carry its Planning Run target, so that the reservation check needs no request file.
24. As Benjamin, I want Spec approval to be possible only with my words from a live conversation, so that no agent approves on my behalf.
25. As Benjamin, I want the approval door to refuse any approver other than the project's declared human approver, so that a wrong approved_by is rejected mechanically.
26. As the operator session, I want the approval door to refuse a Spec whose map is not finished, so that no decision is skipped.
27. As the operator session, I want the approval door to refuse a Spec whose target is not the active reservation, before any irreversible effect, so that a Planning Run cannot jump the queue.
28. As Benjamin, I want the approved Spec's digest frozen, so that any later edit voids the approval and needs my re-approval.
29. As Benjamin, I want /to-tickets to show me the breakdown exactly as it will be published (title, blocked by, what it delivers, acceptance criteria, target rig, scope paths if any), so that I approve the real thing once.
30. As Benjamin, I want one approval of the breakdown to authorize its publication, so that I am not asked twice for the same decision.
31. As the operator session, I want the Ticket Graph Draft stored as a planning-plane bead linked to the Spec bead, so that no draft file sits in the Factory repo.
32. As the operator session, I want target rigs and scope paths kept in the draft's metadata, never in the ticket text, so that tickets stay free of file paths as upstream requires.
33. As Benjamin, I want the publication door to refuse when the Spec is not approved or its current digest differs from the approved one, so that an edited Spec is never sliced.
34. As Benjamin, I want one approved ticket to become exactly one published ticket, so that there is no second decomposition.
35. As the operator session, I want publication to advance the reservation (A6b to C01, or clear it), so that the next reserved run is unblocked without a separate step.
36. As the Mayor, I want to be woken by default when a graph is published, so that approved work never waits for a manual nudge.
37. As the Factory maintainer, I want tests to switch the Mayor wake-up off explicitly, so that the default in production is to wake.
38. As the operator session, I want the publication door to work from any directory, so that it no longer depends on being run from a po/* worktree.
39. As Benjamin, I want the Spec and draft beads to stay open and readable during delivery and close when the convoy closes, so that delivery can consult them and they do not linger after.
40. As Benjamin, I want planning beads never dispatched, woken for, or counted as delivery, so that the Mayor only executes published graphs.
41. As the Factory maintainer, I want the router, wayfinding-run, the to-spec oracle and planning-session.json retired with their tests, fixtures and docs, so that only one Planning Run path exists.
42. As the Factory maintainer, I want each retirement recorded in the Adaptation Register, with AR-001 replaced by the operator-session allocation, so that the register matches how planning actually works.
43. As the Factory maintainer, I want the P02, P03, P04 resume oracle and P06 prototypes deleted with their index entries and comments repointed to Git history, so that no executable oracle describes an allocation nobody will build.
44. As the Factory maintainer, I want historical planning records (router-request.json files, A5 planning-map.json, the approved refactor ticket graph draft) kept as archives, so that history is not rewritten.
45. As the Factory maintainer, I want the legacy_path fence to be structural and ADR-0027 amended to say so, so that no path can reach planning-base, the Release Contract or Cockpit V1 without a selector to check.
46. As any agent, I want the tracker instructions to say how Specs and drafts are published as planning beads, where research and prototype assets go and how choices are recorded, so that I follow one documented path.
47. As any agent, I want the glossary to define No-fog exit and Unmapped Planning Run and to drop "simple run", so that the vocabulary matches the new entry rule.
48. As Benjamin, I want the Factory to stay pinned to mattpocock/skills c55ee46 until a deliberate update, so that the method is a fixed comparison point.
49. As Benjamin, I want a read-only check that tells me when upstream publishes a new release tag, so that I decide when to update and nothing updates on its own.
50. As the operator session, I want a documented update procedure (full skill directories, LF, agents/ folders, every pin reference rewritten together), so that no install drops a skill's Codex policy file again.
51. As Benjamin, I want the CONTEXT.md to GLOSSARY.md rename and the removal of resolving-merge-conflicts to happen in the same change as the v1.3 bump, so that no skill reads a glossary that is not there.
52. As Benjamin on Codex, I want to-spec and to-tickets to be user-only as on Claude, so that neither model starts them without me.
53. As Benjamin, I want A6b's own Ticket Graph published through the current router and recorded as "last run through the old path", so that the switch-over is explicit.
54. As Benjamin, I want C01 to restart from zero as the first Planning Run through the wired flow, so that the cockpit is planned with the right method.

## Implementation Decisions

Planning map check tool (new; af-0aiero.4)
- A small stateless command-line tool over Beads with four functions: create a correctly shaped child ticket; check a map (exists, label wayfinder:map, children shaped as wayfinder:<type> on the planning plane, count of open children); close a map (used by Spec approval; also closes it on abandon with the given reason); safe map update (re-read, refuse if the description changed since the caller's read, else write).
- Claim, resolve, comment and blocking stay native bd commands as written in the tracker doc. No pause/resume.
- Proposed name: planning-map (agent interpretation; the map left the name to the Spec).

Spec bead and the approval door (spec-approve; af-0aiero.5, .8, .9)
- A Spec is a planning-plane bead published by /to-spec, not a child of any map. Its description is the prose Spec. Its metadata carries: planning_run_target (e.g. A6b), planning_map (the map bead id, or none), no_fog_evidence (only when planning_map is none: Benjamin's exact words and date, Paris time), and the approval state (draft / approved), approved_by, approval evidence and approved digest.
- The Spec is linked to its map by a Beads dependency as well as the metadata.
- spec-approve works on a Spec bead by id. Before any write it refuses unless: the target equals the active Planning Run Reservation (when one is active); the map is finished per the check tool (or planning_map is none with no-fog evidence present); approved_by equals the project's declared human approver; evidence is non-empty. On success it records approval and the digest of the Spec's current content, then closes the map.
- Any later change to the Spec content makes the current digest differ from the approved one; status reports the approval as void, publication refuses, and a new approval with new evidence is required.
- No check of the Spec's template headings; no unverified_fact signal (af-0xoj26 covered by "map finished" and Benjamin's review).
- The declared human approver is a field of the Project Planning Profile of each project (agent interpretation: the map left "how the approver is declared" to the Spec).
- The file-Spec contract (agent-factory-planning-run-spec/v1) and subcommands that only serve it are retired with the oracle.

Ticket Graph Draft and the publication door (ticket-graph-publish; af-0aiero.6, .9)
- /to-tickets step 5 ("publish to the tracker") is defined by the tracker doc: the approved breakdown is written as a Ticket Graph Draft, a planning-plane bead linked to the Spec bead; its structured tickets in the description, target_rigs (required) and scope paths (optional, omitted when unsure) plus approval and digest in metadata.
- One approval: approved_by (declared human approver only) and evidence (his exact words and date, Paris time) authorize publication; the former APPROVED + publication_authorized pair collapses into it.
- publish reads the draft by bead id, opens the Spec bead named by the draft and refuses unless it is approved and its current digest equals the approved digest.
- The graph digest covers the tickets' content; the legacy_boundary marker is removed.
- On success, in the same door: delivery beads and convoy created atomically as today (gc.plane=delivery, one approved ticket = one bead); the reservation advanced (active to next, or cleared) when the Spec's target is the active one; the Mayor woken by default. Only tests disable the wake-up, explicitly.
- The door resolves the Factory root the same way other Factory tools do and makes no assumption about the caller's working directory (the po/* worktree assumption goes).
- patch keeps its current rules and reads the draft from its bead like publish.
- Direct bd create of delivery beads stays forbidden.

Closing planning artifacts with the convoy (af-0aiero.6)
- When a convoy closes, the Factory closes the Spec bead and the draft bead it was published from, with a reason naming the convoy. They stay open during delivery.

Planning Run Reservation (af-0aiero.9)
- Location unchanged: tracked read-only seed in config, runtime copy under .gc/runtime, same contract and nesting of next.
- Checked by spec-approve (refusal before any effect), advanced by ticket-graph-publish. Applies to mapped and Unmapped Planning Runs alike.

Claim durability: Factory-owned orphan sweep (af-0aiero.12, .2)
- Gas City's core orphan-sweep order is skipped in the city configuration and replaced by a Factory order running a copy of the upstream sweep script plus one guard: beads claimed by po-agent/* actors and planning-plane beads are treated as owned.
- A test pins the hash of the upstream script the copy is taken from, so a gc upgrade that changes it fails CI.
- Claim rule stays: bd --actor po-agent/<session-id> update --claim, one actor per session, exit 1 = take the next ticket.

Plane gate (af-0aiero.3, .13)
- dispatch-door already refuses planning-plane beads (agent-factory#321); unchanged. No dispatch formula for planning beads; research runs as an operator-session subagent calling research, on the driving session's provider and model.

Retirements (af-0aiero.4, .8, .9, .14, .15), done after A6b's own graph is published
- Router: tool, test, fixtures and its doc. Historical router-request.json files stay as archives.
- wayfinding-run: tool, test, fixtures, JSON map/request contracts; its doc becomes a one-line pointer to the new Planning Run doc. A5 planning-map.json stays as archive, no migration.
- planning-run-to-spec-oracle, the planning-session.json contract, check_ceremony and the request fields complexity, wayfinder_ceremony_invoked, interview_rounds.
- Prototypes P02 (planning allocation), P03 (map concurrency), P04 (resume oracle), P06 (role qualification): bin, config, test and doc deleted; context-index entries 0360, 0370, 0380, 0390 and their index/inventory lines removed; code comments that cite them repointed to the Git commits. The approved refactor ticket graph draft stays intact. Other graphs' P03/P06 identifiers are untouched.
- Adaptation Register: AR-001 marked replaced by the operator-session allocation (upstream skills as written, Beads, Factory doors spec-approve / ticket-graph-publish / planning map check, Mayor executes only); its review row goes with it; each retirement above recorded.
- legacy_path: no selector remains; ADR-0027 gets a one-line amendment saying the fence is now structural. The fixture-city oracle and its legacy_path test are unchanged.

Documentation and glossary (af-0aiero.5, .7, .8, .9)
- Tracker doc: Specs and drafts published as planning beads (replaces "go through the router"); research and prototype assets in the planned project's repo on pushed never-merged research/<map>-<topic> and prototype/<map>-<topic> branches; the Artifact page is only a view; worktree removed at ticket close; variant choice recorded verbatim in the resolution comment.
- One Planning Run doc replaces the router and wayfinding-run docs: the chain /wayfinder, /to-spec, spec-approve, /to-tickets, ticket-graph-publish; No-fog exit and overflow rule; getting-started section updated to this entry point.
- "router publication" becomes "the publication door (ticket-graph-publish)"; "router" gets no glossary entry.
- Glossary: remove "simple run" from Planning Run (and Planning Session); add No-fog exit (fr. sortie sans brouillard) and Unmapped Planning Run (fr. cadrage sans carte). Planning Run Reservation and Planning Artifact are already updated (agent-factory#323, #324).

Upstream version (af-0aiero.10, .11, .1)
- Method Baseline stays mattpocock/skills c55ee46. Deliverables in A6b: a read-only check that signals a new upstream release tag (never updates), and a documented update procedure (release tags only, full skill directories with LF and agents/ folders, every pin reference rewritten in one change).
- The CONTEXT.md to GLOSSARY.md rename, its references and the removal of resolving-merge-conflicts happen in the same change as the v1.3 bump, when upstream tags v1.3; not before.
- agents/openai.yaml for to-spec and to-tickets is already installed (agent-instructions 7806f67); nothing to deliver.

## Testing Decisions

- A good test drives a door through its command-line interface against the fake bd and asserts on its public output and on the beads it leaves; it never reaches into internal functions. CI has no Beads/Dolt, so every Beads-touching test uses the fake-tool pattern.
- Main seam, one test module: the Planning Run lifecycle over fake bd. Given a finished map and a Spec bead, spec-approve then ticket-graph-publish reach a published convoy; the map is closed, the reservation advanced, the Mayor wake-up recorded. The same module covers the refusals: unfinished map, wrong target while reserved, wrong approver, Spec edited after approval (approval void and publish refused), missing no-fog evidence on an unmapped Spec, and a valid unmapped run. This replaces the router's end-to-end tests as the proof of the whole path.
- Door seams, existing modules extended: spec-approve tests for bead mode; ticket-graph-publish tests for draft-by-bead, the single approval, the Spec digest binding, the tickets-content digest, default wake-up and cwd independence.
- Planning map check tool: its own test over fake bd (child shape, check verdicts, close, safe update refusing a changed description).
- Orphan sweep: a test of the Factory order over fixture beads (a po-agent/* claim and a planning bead survive; a claim by an unknown delivery actor is released) plus the upstream-script hash pin.
- Upstream tag check: a test with a faked remote tag list (new tag signalled, no write).
- Retirement: tests of retired tools are deleted with them; the CI runs every tests file automatically, so a dangling reference breaks the build.
- Prior art: the router's end-to-end test, spec-approve-test, ticket-graph-publish-test, fake-tool-contract-test (fake bd), dispatch-door-test, and the order tests (e.g. the backup-freshness order test).

## Out of Scope

- A Factory agent (Mayor or planning agent) charting a map without the operator session (contradicts Benjamin's 3A).
- Showing the map, the Spec or the reservation in a cockpit: C01 (Cockpit V2).
- Moving the Method Baseline before upstream tags v1.3; the rename and removal that go with that bump.
- A worker path for research tickets, a pinned model tier, and any resume mechanism for a session that dies mid-research.
- Changing the delivery workflow after publication (Mayor, workers, PR autopilot) beyond waking the Mayor and closing the planning artifacts with the convoy.
- Migrating A5 or earlier planning records to Beads.
- Upstream issues or PRs (mattpocock/skills#476 stays upstream).

## Further Notes

- Intent (Benjamin, his words, 2026-09-29, live chat): « first a Planning Run "wayfinder wiring" for the Factory, itself run with the real wayfinder, then C01 »; « Le planning run n'est pas uniquement pour cockpit C01 ». Mechanism (agent interpretation): this Spec; map af-0aiero; every decision above traced to its ticket.
- Target rig: agent-factory. Planning Run target: A6b (active reservation; C01 next).
- Last run through the old path: A6b's Ticket Graph is published through the current router, which expects a planning-session.json and a file Spec from the oracle. That publication is recorded as "last run through the old path"; the retirements above happen only after it.
- Until the Factory-owned sweep ships, parallel operator sessions each work a ticket Benjamin names, so a dropped claim cannot cause double work (Benjamin, 2026-09-30).
- Research branches of this map: research/a6b-codex-skills, research/a6b-beads-claim, research/a6b-planning-plane, research/a6b-claim-cleared (Factory repo), archives of why.

