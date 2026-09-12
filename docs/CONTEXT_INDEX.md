# Context index

Use progressive disclosure. Do not read every document by default.

| Need | Read |
|---|---|
| Factory invariants / agent bootstrap | `../AGENTS.md` |
| Durable target architecture | `TARGET_ARCHITECTURE.md` |
| Current migration state, cutover and rollback | `MIGRATION.md` |
| Install/start/stop/doctor/backup/restore/recovery | `OPERATIONS.md` |
| Trust boundaries, secrets and concurrency | `SECURITY.md` |
| Structural decisions | `decisions/ADR-0001-foundation.md` |

## Authority order

1. Observed runtime state: Gas City, Beads/Dolt, Git and GitHub.
2. Versioned repository documentation and the affected project repositories.
3. Current official upstream documentation and release notes.
4. Historical Plan directeur V2.
5. Chats/memory as secondary context only.

## Historical baseline

The DOCX *Migration Gas City + Beads — Plan directeur A à Z V2* is the approved conceptual baseline dated 2026-09-12. It becomes historical/reference material as this repository gains verified operational documentation.

## Current bootstrap snapshot

Verified from GitHub on 2026-09-12 before bootstrap:

- SayMyName backend `dev`: `15bfc27ec00f04ba1c5be1a301e8129d7c68b727`
- SayMyName frontend `dev`: `9743ded353ea32d31796b673c55b6df606a7dce6`
- Legacy automation `main`: `eae2110d21a7118ca2ea5af66085ee319f26f0b3`
- Backend PR #23 / SMN-54 remains open and therefore in-flight.

This snapshot is not a substitute for live refresh before mutation.
