# Agent Factory

Generic agentic software factory based on **Gas City + Beads/Dolt + GitHub** with interchangeable agent providers.

SayMyName is the first managed product, but this repository is deliberately project-agnostic.

## Current status

- The local WSL Factory has been delivered and proven through migration milestones M2–M6.
- Gas City, the Mayor, Beads/Dolt, both SayMyName rigs, and tailnet dashboard access are configured. Product status and the local preview are retired (see below).
- The old SayMyName Linear/PowerShell runner is retired and preserved only as historical evidence.
- M7 remains a future cloud-placement decision; no cloud resource is implied by this repository.

Runtime state is volatile. Confirm it from the host rather than inferring it from this summary.

## New to this Factory?

Installing an independent Factory from Git, registering a generic project,
starting its City, and reaching the first Planning Run: see
[`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md).

## Pilot it with Codex

Open Codex on host **BenForge** with `/home/benja/agent-factory` as the working
folder, or start it from PowerShell:

```powershell
wsl -d Ubuntu-24.04 -u benja --cd /home/benja/agent-factory
codex
```

Then speak in product terms, for example: `Où en est SayMyName ?`, `Discutons de
la prochaine priorité sans rien modifier`, or `Fais réaliser ce bug par la
Factory`. The same workflow can be resumed from a phone through Codex Remote
while BenForge and its Codex app remain available.

The complete protocol, authority levels, and recovery checks are in
[`docs/OPERATOR_BRIDGE.md`](docs/OPERATOR_BRIDGE.md).

Project status lives in each project's own repository, not here. Cockpit V1,
its ntfy push, the campaign and the SayMyName product queue, status and preview
are retired to [`legacy/`](legacy/README.md) (untrusted); Cockpit V2 is the
Planning Run C01. Detailed operation and recovery procedures are in
[`docs/OPERATIONS.md`](docs/OPERATIONS.md).

## Source of truth

1. Observed runtime state: Gas City, Beads/Dolt, Git, and GitHub.
2. This repository and the repositories of managed projects.
3. Current official Gas City, Beads, Dolt, provider, and runtime documentation.
4. Historical migration baseline: *Migration Gas City + Beads — Plan directeur A à Z V2*.
5. Chat history and model memory only as secondary context.

Never infer operational state from a conversation.

## Documentation

Start with [`docs/CONTEXT_INDEX.md`](docs/CONTEXT_INDEX.md). It provides a
progressive-disclosure map so Codex does not load the whole Factory history.
Architecture, migration, operations, delivery, security, and accepted decisions
live under `docs/`; executable work and dependencies live in Beads.

## Core constraints

- One active controller per City and one writer per rig until isolation is proven.
- The Mayor is the product-work orchestration entry point.
- GitHub remains authoritative for code and delivery evidence; Beads is authoritative for work.
- Access capability is not standing authorization: production, secrets, public exposure, spend, and destructive actions remain explicit decisions.
- Secrets never belong in Git, Beads, prompts, logs, or responses.
