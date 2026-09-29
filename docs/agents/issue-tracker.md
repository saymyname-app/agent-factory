# Issue tracker: Beads (Other)

Written by `setup-matt-pocock-skills` (upstream `mattpocock/skills` c55ee46)
for Planning Run A6b. Its `## Agent skills` pointer is in `AGENTS.md`, not
`CLAUDE.md` as the skill says, so Codex reads it too (Benjamin, 2026-09-29).

Issues for this repo live as **Beads** in the Factory's HQ Beads database
(Dolt-backed). Use the `bd` CLI (v1.2.2), run **only from the live root**
`/home/benja/agent-factory`, with `--actor po-agent/<session-id>` (one actor per
operator session, see Claim) when the operator session writes. Never create a second tracker (GitHub Issues, `.scratch/`) for this repo.

## Conventions

- **Work Plane is mandatory** (see `CONTEXT.md`, "Work Plane"). Every bead a
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
- **Close**: `bd close <id> --reason "<one line>"`.

## When a skill says "publish to the issue tracker"

Create a planning-plane bead as above. Specs and Ticket Graphs for delivery
go through the Planning Run router (`docs/PLANNING_RUN_ROUTER.md`), not
through `bd create`.

## When a skill says "fetch the relevant ticket"

`bd show <id>` and `bd comments <id>`.

## Wayfinding operations

Used by `/wayfinder`. The **map** is one bead (the Planning Map Bead) with
**child** beads as tickets (Planning Decision Beads).

- **Map**: `bd create --type epic --title "<effort>" --labels wayfinder:map --metadata '{"gc.plane":"planning"}' --body-file map.md`. The description holds the Destination / Notes / Decisions so far / Not yet specified / Out of scope body; update it with `bd update <map> --body-file map.md`.
- **Child ticket**: `bd create --parent <map> --type task --title "<name>" --labels wayfinder:<type> --metadata '{"gc.plane":"planning"}' --body-file q.md`, where `<type>` is `research`/`prototype`/`grilling`/`task` and the body is `## Question`.
- **Blocking**: Beads' native `blocks` dependency: `bd dep add <blocked> <blocker>`. A ticket is unblocked when every blocker is closed.
- **Frontier query**: `bd ready --parent <map> --unassigned --json` (ready already drops blocked and in-progress beads); first by creation order wins.
- **Claim**: `bd --actor po-agent/<session-id> update <id> --claim`, the session's first write. Only `--claim` is atomic, and only between distinct actors: exit 1 ("already claimed") means take the next frontier ticket. Never claim with `--assignee` (last writer wins silently). Research: branch `research/a6b-beads-claim`, af-0aiero.2.
- **Resolve**: `bd comments add <id> -f answer.md`, then `bd close <id> --reason "<gist>"`, then append a context pointer (name + id + gist) to the map's Decisions so far. `bd update --body-file` replaces the whole description (last writer wins, no compare-and-set): re-read the map immediately before writing and keep one writer at a time on it.
- **Research assets**: the research subagent writes its cited file on a throwaway `research/<name>` branch of this repo (in a worktree, never in the live root) and the ticket's resolution comment links it.
