# Context index

Use progressive disclosure. Do not read every document by default.

| Need | Read |
|---|---|
| Factory invariants / agent bootstrap | `../AGENTS.md` |
| Durable target architecture | `TARGET_ARCHITECTURE.md` |
| Current migration state, cutover and rollback | `MIGRATION.md` |
| Install/start/stop/doctor/backup/restore/recovery | `OPERATIONS.md` |
| Operator dashboard URL, lifecycle and recovery | `OPERATIONS.md` |
| FAST / STANDARD / GUARDED delivery contracts and gates | `DELIVERY.md` |
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

Verified from GitHub after M5 delivery on 2026-09-12:

- SayMyName backend `dev`: `297cbd87d02b86120644ea3542c10e6688cc3ae6`
- SayMyName frontend `dev`: `aa82099a183c64e0b02af80979dc1e28353edc4c`
- Legacy automation `main`: `eae2110d21a7118ca2ea5af66085ee319f26f0b3`
- Backend and Frontend have no open PR; all PRs referenced by the legacy ledger are merged.
- Windows Scheduled Task `SayMyName-LocalCodexRunner` is disabled; historical receipts and worktrees remain preserved.

This snapshot is not a substitute for live refresh before mutation.
