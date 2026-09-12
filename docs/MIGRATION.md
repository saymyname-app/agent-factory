# Migration

Migration path: M0 -> M7. Keep dual-run short. Existing in-flight legacy work may finish on the legacy path; new work moves to Beads/Gas City only after cutover criteria are met.

## M0 — Freeze and inventory

**Status: IN PROGRESS**

Observed 2026-09-12:

- Backend `dev`: `15bfc27ec00f04ba1c5be1a301e8129d7c68b727`
- Frontend `dev`: `9743ded353ea32d31796b673c55b6df606a7dce6`
- Automation `main`: `eae2110d21a7118ca2ea5af66085ee319f26f0b3`
- Backend PR #23 / SMN-54: open, head `e9f0b4788def02ed60f90ba7f0cfe4f4213c30c3`; backend CI passed; Claude review did not complete because the reviewer hit its turn limit. Treat as in-flight.

Freeze rule effective immediately: no new generic orchestration feature goes into the legacy Linear/PowerShell runner except transition or safety work.

M0 exit still requires local proof that no other ledger/lock/session is in-flight and a live refresh of legacy work tracking before the relevant cutover step.

## M1 — Linux/WSL bootstrap

**Status: IN PROGRESS**

Upstream verified for bootstrap:

- Gas City latest stable observed on 2026-09-12: `v1.4.1`.
- Gas City `v1.4.1` CI dependency pins: Beads `v1.2.2`, Dolt `2.1.7`.
- Gas City requires Linux runtime dependencies including `tmux`, `jq`, `git`, `dolt`, `bd`, `flock`; `gh` is optional but needed by this factory for GitHub evidence/gates.

No City configuration is marked CONFIGURED until `gc init` generates/validates it locally. Do not hand-author speculative `city.toml`, `pack.toml` or `packs.lock` before that bootstrap.

M1 exit:

- dedicated/validated WSL2 Linux environment;
- pinned/recorded `gc`, `bd`, `dolt` versions;
- `gh` authenticated to the required repos;
- at least one writer provider CLI validated;
- `agent-factory` cloned locally;
- City initialized from this repo and `gc doctor` healthy;
- generated versionable config committed, host-local state excluded.

## M2 — Canary

Not started. One simple, non-critical rig/task only. Prove bead -> agent -> result -> durable state. No complex Formula.

## M3 — Durability

Not started. Prove backup/restore into a fresh location and controller restart/recovery.

## M4 — Delivery v1

Not started. FAST / STANDARD / GUARDED only, one writer per rig, GitHub CI retained, explicit human gate only where needed.

## M5 — SayMyName

Not started. Add backend/frontend and only then legacy automation as rigs if still useful. Migrate active/future work only; do not recreate Done history.

## M6 — Cutover/decommission

Not started. Stop legacy router/Scheduled Task only when there is no ambiguous or in-flight legacy dispatch. Preserve historical receipts/ledgers read-only.

## M7 — Cloud portability

Not started. Restore the same factory on a simple Linux VM after stopping the corresponding local controller. Re-provision provider auth explicitly.

## Cutover gate

Do not decommission the old path until all are PROVEN:

- healthy pinned Gas City/Beads/Dolt installation;
- real canary delivery;
- Beads backup + restore;
- controller restart without work loss;
- Git/CI/policy respected by the first delivery path;
- no legacy work ambiguous/in-flight.
