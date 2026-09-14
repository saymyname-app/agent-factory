# Agent Factory

Generic agentic software factory based on **Gas City + Beads/Dolt + GitHub** with interchangeable agent providers.

SayMyName is the first managed product, but this repository is deliberately project-agnostic.

## Current status

- The local WSL Factory has been delivered and proven through migration milestones M2–M6.
- Gas City, the Mayor, Beads/Dolt, both SayMyName rigs, product status, local preview, and tailnet dashboard access are configured.
- The old SayMyName Linear/PowerShell runner is retired and preserved only as historical evidence.
- M7 remains a future cloud-placement decision; no cloud resource is implied by this repository.

Runtime state is volatile. Confirm it from the host rather than inferring it from this summary.

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

For a read-only SayMyName snapshot without Factory noise:

```bash
./bin/saymyname-product-status
```

For a one-glance browser view of the Mayor, active agents, real step progress,
filtered product Beads, decision aids, and the human product queue, run:

```bash
./bin/factory-cockpit open
```

This loopback-only cockpit performs zero model calls while monitoring. Its one
explicit Mayor message box may consume model tokens; it cannot interrupt or
orchestrate work itself.

For the deterministic local product preview, use `./bin/saymyname-preview start`
and `./bin/saymyname-preview stop`. Detailed operation and recovery procedures
are in [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

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

## Portable installation and project onboarding

Use [the portable installation guide](docs/portable/INSTALL.md) to export a clean
distribution and prepare a new or imported project. Export never copies this
installation’s runtime, credentials or product dossiers and never starts agents.
