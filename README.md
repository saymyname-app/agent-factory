# Agent Factory

Generic agentic software factory based on **Gas City + Beads/Dolt + GitHub** with interchangeable agent providers.

SayMyName is the first migration target, but this repository is deliberately project-agnostic.

## Current status

- **M0 — Freeze & inventory:** in progress
- **M1 — Linux/WSL bootstrap:** in progress
- No production City is configured or proven yet.
- The legacy SayMyName Automation runner remains available only to finish already in-flight work during cutover.

## Source of truth

1. Observed runtime state: Gas City, Beads/Dolt, Git and GitHub.
2. This repository and the repositories of managed projects.
3. Current official Gas City, Beads, Dolt and provider documentation/release notes.
4. Historical migration baseline: *Migration Gas City + Beads — Plan directeur A à Z V2*.
5. Chat history only as secondary context.

Never infer operational state from a conversation.

## Documentation

Start with [`docs/CONTEXT_INDEX.md`](docs/CONTEXT_INDEX.md).

Durable architecture, migration, operations, security and decisions live under `docs/`. Runtime work will live in Beads once the City is initialized.

## Core constraints

- One active controller per City.
- V1: one writer per rig until worktree isolation is proven.
- GitHub remains authoritative for code, branches, SHA, PR, CI and merge evidence.
- Beads becomes authoritative for executable work and dependencies.
- No new generic capability is added to the legacy Linear/PowerShell orchestrator except transition or safety work.
- Secrets never belong in Git, Beads or prompts.
