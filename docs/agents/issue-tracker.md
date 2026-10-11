# Issue tracker: Beads (Other)

Written by `setup-matt-pocock-skills` (upstream `mattpocock/skills`, pinned
at tag `v1.3.1`/commit `24fe0ef`, see `docs/UPSTREAM_SKILLS.md`) for
Planning Run A6b. Its `## Agent skills` pointer is in `AGENTS.md`, not
`CLAUDE.md` as the skill says, so Codex reads it too (Benjamin, 2026-09-29).

Issues for this repo live as **Beads** in the Factory's HQ Beads database
(Dolt-backed). Use the `bd` CLI (v1.3.1), run **only from the live root**
`/home/benja/agent-factory`, with `--actor po-agent/<session-id>` (one actor per
operator session, see Claim) when the operator session writes. Never create a second tracker (GitHub Issues, `.scratch/`) for this repo.

## Conventions

- **Work Plane is mandatory** (see `GLOSSARY.md`, "Work Plane"). Every bead a
  skill creates here carries `gc.plane=planning` metadata. Delivery selectors
  (Mayor, `idle-ready-work-wake`, `deliver-close`) positively require
  `gc.plane=delivery`, so planning beads are never dispatched to workers.
  Delivery beads are created only by `bin/ticket-graph-publish` from an
  approved Ticket Graph, never by hand.
- **Create an issue**: `bd create --title "..." --type task --labels <l> --metadata '{"gc.plane":"planning"}' --body-file <file>`.
- **Read an issue**: `bd show <id>` then `bd comments <id>`.
- **List issues**: `bd list --status open --label <l> --json` (`--parent <id>` for children).
- **Comment**: `bd comments add <id> -f <file>`.
- **Labels**: `bd update <id> --add-label <l>`.
- **Close**: `bd --actor po-agent/<session-id> close <id> --reason "<one line>"`. Beads 1.3 refuses the close of an assigned bead to any actor but its assignee (exit 1, "cannot close"): without `--actor`, the session is not the actor that claimed.

## When a skill says "publish to the issue tracker"

Create a planning-plane bead as above. A Spec is published as a
planning-plane Spec bead (`bin/spec-approve bd-approve` approves it) and a
Ticket Graph Draft as a planning-plane bead linked to its Spec bead
(`bin/ticket-graph-publish bd-publish` publishes it) — see
`docs/PLANNING_RUN.md` for the whole chain.

## When a skill says "fetch the relevant ticket"

`bd show <id>` and `bd comments <id>`.

## Wayfinding operations

Used by `/wayfinder`. The **map** is one bead (the Planning Map Bead) with
**child** beads as tickets (Planning Decision Beads).

- **Map**: `bin/planning-map create-map --project <project-id> --title "<effort>" --body-file map.md` (never a raw `bd create`: the map receives its project key at creation, T05, and refuses a `--project` not declared by a `config/project-descriptors/*.json` file). The description holds the Destination / Notes / Decisions so far / Not yet specified / Out of scope body; update it with `bin/planning-map update --map <map> --expected-description-file <what you read> --body-file map.md` (or `bd update <map> --body-file map.md` when you have not read a prior description to compare against).
- **Child ticket**: `bd create --parent <map> --no-inherit-labels --type task --title "<name>" --labels wayfinder:<type> --metadata '{"gc.plane":"planning"}' --body-file q.md`, where `<type>` is `research`/`prototype`/`grilling`/`task` and the body is `## Question`. `--no-inherit-labels` is required: `bd create --parent` copies the parent's labels by default, which would tag every ticket `wayfinder:map` (seen on af-0aiero).
- **Blocking**: Beads' native `blocks` dependency: `bd dep add <blocked> <blocker>`. A ticket is unblocked when every blocker is closed.
- **Frontier query**: `bd ready --parent <map> --unassigned --json` (ready already drops blocked and in-progress beads); first by creation order wins.
- **Claim**: `bd --actor po-agent/<session-id> update <id> --claim`, the session's first write. Only `--claim` is atomic, and only between distinct actors: exit 1 ("already claimed") means take the next frontier ticket. Never claim with `--assignee` (last writer wins silently). Research: branch `research/a6b-beads-claim`, af-0aiero.2.
- **Benjamin-invoked skills**: `/wayfinder`, `/to-spec` and `/to-tickets` (Method Baseline, as written) carry `disable-model-invocation: true`: only Benjamin starts them, by typing the slash command in a session. An agent's Skill tool call is refused, and the agent must not replay the skill's steps by hand instead (seen on the C01 `/to-spec` chip, 2026-09-30). So a launch chip or ready-to-paste prompt for one of them does the Take over and the reads (`bd show`, `bd comments`), then asks Benjamin to type the command (e.g. `/to-spec <map>`) in that session; it never tells the agent to call the Skill tool or to invoke the skill itself.
- **Offer (launch chip)**: a session that proposes a ready ticket for another session to run (a launch chip or a ready-to-paste prompt) reserves it first, because a chip lives only in its own conversation and the frontier keeps showing the ticket until someone claims it (duplicate chips seen on af-arlph5, 2026-09-30). Run `bd --actor po-agent/<own-session-id> update <id> --claim`; only on exit 0, run `bd --actor po-agent/<own-session-id> update <id> --set-metadata wayfinder.offered_by=po-agent/<own-session-id>` and create the chip, whose prompt names that offerer. Exit 1 means another session offered or runs it: no chip.
- **Take over**: the launched session's first write replaces Claim. `bd show <id> --json`: if the assignee is the offerer its prompt names and `wayfinder.offered_by` is set, run `bd --actor po-agent/<own-session-id> update <id> --if-assignee po-agent/<offerer-session-id> --assignee po-agent/<own-session-id> --unset-metadata wayfinder.offered_by`: one compare-and-set write, accepted while the offerer's claim is live. Exit 0: the ticket is yours. Exit 13 ("assignee mismatch", nothing written), or an assignee that is not the offerer at the read: another session took it, stop and say so. Never the bare `--assignee`: Beads 1.3 refuses to reassign a bead another actor holds in progress (exit 1, "cannot reassign ... held by"), whatever the state of the lease. Never `--force`: it cannot be combined with `--if-assignee`, so it takes the ticket from whoever holds it (measured on Beads 1.3.1, af-tql60u). A ticket reached without an offer (a plain `/wayfinder <map>`) uses Claim.
- **Offered, not started**: `bd list --parent <map> --status in_progress --json`, entries whose metadata has `wayfinder.offered_by`, plus the map itself when `bd show <map> --json` carries `wayfinder.offered_by` (a `/to-spec` offer, see Map handoff), plus approved Spec beads offered for `/to-tickets` (see Spec handoff): `bd list --status in_progress --has-metadata-key wayfinder.offered_by --json` lists all three kinds at once. Any session listing the frontier also lists these with the time of the offer, so a dismissed chip is never lost; re-offer one only when Benjamin asks, by running Take over for yourself as offerer (the same `--if-assignee po-agent/<previous-offerer-session-id>` write, with `--set-metadata wayfinder.offered_by=po-agent/<own-session-id>` in place of `--unset-metadata wayfinder.offered_by`) and creating the new chip.
- **Resolve**: `bd comments add <id> -f answer.md`, then `bd --actor po-agent/<own-session-id> close <id> --reason "<gist>"` (the actor that claimed it: any other is refused), then append a context pointer (name + id + gist) to the map's Decisions so far with `bin/planning-map update --map <map> --expected-description-file <what you read> --body-file <new>`: it refuses to write when a sibling session changed the map since your read (plain `bd update --body-file` is last writer wins); on refusal, re-read and append again.
- **Map handoff (`/to-spec` launch chip)**: right after Resolve, run `bin/planning-map check --map <map>`. When it reports `"finished": true`, the map is ready for `/to-spec` (`docs/PLANNING_RUN.md`, step 3) and the session that just closed a ticket offers it, using Offer on the map bead itself: `bd --actor po-agent/<own-session-id> update <map> --claim`; only on exit 0, `--set-metadata wayfinder.offered_by=po-agent/<own-session-id>` on the map and one `/to-spec <map>` launch chip whose prompt names that offerer, starts with Take over on the map, reads the map (`bd show <map>`, `bd comments <map>`), then asks Benjamin to type `/to-spec <map>` (see Benjamin-invoked skills). Exit 1 means a sibling that closed the last tickets at the same time, or a running `/to-spec`, already holds the map: no chip. Every closing session runs the check, so the one that closes the last ticket always sees the map finished, and the atomic claim lets exactly one session offer (Benjamin, 2026-09-30: one `/to-spec` chip per finished map, never two). The map stays claimed until `bin/spec-approve bd-approve` closes it, whoever holds it and from any session (`bin/planning-map close`).
- **Spec handoff (`/to-tickets` launch chip)**: a session that hands an approved Spec (after `bin/spec-approve bd-approve`) to another session for `/to-tickets` (`docs/PLANNING_RUN.md`, step 5) uses Offer on the Spec bead itself, as done for af-oohx2x on 2026-09-30: `bd --actor po-agent/<own-session-id> update <spec> --claim`; only on exit 0, `--set-metadata wayfinder.offered_by=po-agent/<own-session-id>` on the Spec and one `/to-tickets <spec>` launch chip whose prompt names that offerer, starts with Take over on the Spec, reads it (`bd show <spec>`, `bd comments <spec>`), then asks Benjamin to type `/to-tickets <spec>`. Exit 1 means another session already offered or runs it: no chip. The Spec stays claimed (`in_progress`, assigned) through delivery: `bin/ticket-graph-publish` checks only its approval and digest, never its status or assignee, and `bin/planning-artifacts-close` closes it when its convoy closes, whoever holds it (`bd update --if-assignee <holder> --status closed`: a plain `bd close` is refused to any actor but the assignee).
- **Research assets**: the research subagent writes its cited file on a pushed, never-merged `research/<map>-<topic>` branch of the planned project's repo (in a worktree, never in the live root) and the ticket's resolution comment links it.
- **Prototype assets**: pushed, never-merged `prototype/<map>-<topic>` branch, shown to Benjamin as a private Artifact page — the page is only a view, never where the decision lives. Benjamin chooses the variant in the live chat; that choice is recorded verbatim in the ticket's resolution comment. The session then freezes the chosen variant on that branch as the Validated Prototype and runs `bin/prototype-conformance check --prototype <dir>` before showing it (`docs/VALIDATED_PROTOTYPE.md`).
- **Spec shape `bin/spec-approve` requires**: numbered user stories under a `User Stories` heading; each story that describes an interface tagged `[interface]`; then a `Validated Prototype` section with the reference (branche, commit, chemin, états) and one state inventory table per screen (`docs/SPEC_APPROVE.md`, "Entry contract").
- **Worktree cleanup**: the local worktree for a research or prototype ticket is removed when the ticket closes.
