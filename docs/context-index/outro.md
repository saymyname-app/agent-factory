
## Authority order

1. Observed runtime state: Gas City, Beads/Dolt, Git, and GitHub.
2. Versioned Factory documentation and the affected project repositories.
3. Current official upstream documentation and release notes.
4. Historical Plan directeur V2.
5. Chats and model memory as secondary context only.

When sources conflict, report the conflict and repair the highest durable source
within scope. A dated snapshot, chat summary, or generated status is never a
replacement for a live refresh before mutation.

## Minimal session bootstrap

- Project question: read that project's own repository (its rig `AGENTS.md`) and live Beads/GitHub.
- Factory health question: read `OPERATOR_BRIDGE.md`, then run its read-only health check.
- Host capacity, unsaved work, or "is the factory safe to touch": run `./bin/factory-guard --check-only` and `./bin/factory-resources`; see `FACTORY_TOOLS.md`.
- Health triage: run `./bin/factory-doctor` rather than reading raw `gc doctor` — it separates what we can fix from upstream and advisory noise.
- One-glance Factory activity: `gc status`, then Beads/GitHub.
- Tracked change: read the root and nearest project `AGENTS.md`, the relevant Bead, and only the linked contract needed by the change.
- Architecture or policy change: also read the relevant ADRs and update/supersede them in the same change.

## Durable versus live context

Durable facts include architectural decisions, safety boundaries, commands, and
project contracts. They belong in Git. Current work, dependency state, and
coordination pointers belong in Beads. Processes, sessions, branches, commits,
PRs, and checks must be observed from their live systems. Do not embed volatile
SHAs, PIDs, open-task lists, or “currently running” claims in this index.

## Historical baseline

The DOCX *Migration Gas City + Beads — Plan directeur A à Z V2* is the approved
conceptual baseline dated 2026-09-12. It is historical/reference material now
that this repository contains verified operational documentation.
