# Migration

Migration path: M0 -> M7. Keep dual-run short. Existing in-flight legacy work may finish on the legacy path; new work moves to Beads/Gas City only after cutover criteria are met.

## M0 — Freeze and inventory

**Status: IN PROGRESS**

Latest GitHub refresh on 2026-09-12:

- Backend `dev`: `5f9dce7714eabb1b060b725ae3c915f2450e866b` after merge of PR #23 / SMN-54.
- Frontend `dev`: `9743ded353ea32d31796b673c55b6df606a7dce6`.
- Automation `main`: `eae2110d21a7118ca2ea5af66085ee319f26f0b3`.
- Backend PR #23 / SMN-54 is merged and no longer in-flight.
- Backend PR #24 / SMN-50 is open/draft and runner-owned; treat as legacy in-flight work.
- Frontend PR #39 / SMN-78 is open and runner-owned; treat as legacy in-flight work.
- Automation has no open PR observed in this refresh.

Freeze rule remains effective: no new generic orchestration feature goes into the legacy Linear/PowerShell runner except transition or safety work.

M0 exit still requires local proof that no other ledger/lock/session is in-flight and a live refresh of legacy work tracking before the relevant cutover step. Do not stop the legacy dispatcher while PR #24 / PR #39 or any corresponding local ledger remains active.

## M1 — Linux/WSL bootstrap

**Status: IN PROGRESS**

Upstream verified for bootstrap:

- Gas City stable selected for bootstrap: `v1.4.1`.
- Gas City `v1.4.1` dependency pins: Beads `v1.2.2`, Dolt `2.1.7`.
- Gas City requires Linux runtime dependencies including `tmux`, `jq`, `git`, `dolt`, `bd`, `flock`; `gh` is used by this factory for GitHub evidence/gates.

Observed/proven host state on 2026-09-12:

- Dedicated `Ubuntu-24.04` WSL2 distribution provisioned for the factory; Docker Desktop's internal WSL distribution is not used as the City host.
- `Ubuntu-24.04` is the default WSL distribution.
- Kernel observed: `6.6.87.2-microsoft-standard-WSL2` on `x86_64`.
- `systemd` observed running.
- Base tooling verified: Git `2.43.0`, GitHub CLI `2.45.0`, tmux `3.4`, jq `1.7`, flock/util-linux `2.39.3`.
- Pinned factory binaries installed from verified release artifacts: Gas City `1.4.1`, Beads `1.2.2`, Dolt `2.1.7`.
- Release archive checksums passed before installation.
- GitHub CLI authentication inside Ubuntu is PROVEN for account `benjamin-hurand`; Git protocol is HTTPS.
- `agent-factory` was cloned into the Linux filesystem at `~/agent-factory` and was clean on `main` before City initialization.
- `gc init --template gascity --providers codex --default-provider codex --skip-provider-readiness --no-start --preserve-existing .` generated the runtime scaffold, hooks, default prompts, `pack.toml` and City configuration.
- Initialization then stopped before Beads/Dolt finalization because Dolt global author identity (`user.name`, `user.email`) is not configured. Gas City `v1.4.1` explicitly treats this as a startup blocker after the City files are created.
- No provider session was started and no Codex tokens were consumed by this bootstrap.

Current classification:

- Linux host: **PROVEN**.
- GitHub auth + local clone: **PROVEN**.
- City files: **CONFIGURED/PARTIALLY OBSERVED**, not yet committed or proven healthy.
- Beads/Dolt store initialization: **BLOCKED** on Dolt author identity.
- Controller/provider execution: **NOT STARTED**.

M1 remaining work:

- configure non-secret Dolt author identity;
- inspect the generated City files and Git diff before committing them;
- initialize/validate the Beads/Dolt store and run `gc doctor`;
- install and authenticate at least one writer provider CLI (Codex first);
- start the City and obtain a healthy `gc doctor`;
- commit only the versionable City configuration; keep `.gc`, credentials and local runtime state untracked.

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
