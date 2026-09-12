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

**Status: DONE**

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
- `agent-factory` was cloned into the Linux filesystem at `~/agent-factory`.
- `gc init --template gascity --providers codex --default-provider codex --skip-provider-readiness --no-start --preserve-existing .` generated the runtime scaffold, hooks, default prompts, `pack.toml` and City configuration.
- Dolt author identity is configured with a non-secret factory identity.
- `git config --global beads.role maintainer` is configured.
- `gc doctor --fix` installed 4 remote imports, wrote `packs.lock`, and registered all 13 required Gas City custom bead types.
- Post-fix `gc doctor`: **81 passed, 5 warnings, 0 failed**.
- Managed Dolt is reachable on `127.0.0.1:44632` and reports no user data yet.
- Controller/provider execution remains not started.

Current classification:

- Linux host: **PROVEN**.
- GitHub auth + local clone: **PROVEN**.
- City files: **CONFIGURED and OBSERVED**, not yet committed.
- Pack imports / `packs.lock`: **CONFIGURED and OBSERVED**.
- Managed Dolt endpoint: **OBSERVED reachable**.
- Doctor hard failures: **0**.
- City health: **NOT YET PROVEN** because the inactive split store and provider/controller startup remain unresolved/unproven.

Known warnings requiring bounded handling:

- `formula-requirements`: 34 warnings from the selected upstream Gas City pack; do not patch locally during M1 unless they block the canary.
- `agent-sessions` / `orphan-sessions`: expected while the controller/tmux sessions are not started.
- `bd-split-store`: active `.beads/dolt`; inactive `.beads/embeddeddolt` contains one Dolt repo. Gas City upstream issue #1436 remains open and documents a parasitic embedded store as a bootstrap/recovery side effect. Do not delete either store before explicit inspection/reconciliation.
- `beads-store`: native store preflight is unavailable because `.beads/metadata.json` is absent; current operations fall back to BdStore fork-per-op. Re-evaluate after store reconciliation/start rather than inventing a custom metadata file.

Final proof collected on 2026-09-12:

- local `main` divergence was inspected and preserved: the local `bd init` commit contained only six Beads/Dolt ignore rules; it was rebased without force over GitHub `main` at `f1562a5`;
- `gc restart` replaced supervisor PID `8443` with PID `70035`, rematerialized the always-on Mayor as session/bead `af-hkb`, and retained access to the canonical store and `issue_prefix=af`;
- the rematerialized Mayor command and live OS process both use `--model gpt-5.6-sol`; an independent authenticated `codex exec -m gpt-5.6-sol` returned `SOL_AUTH_OK`;
- `gc doctor --fix` upgraded the managed Codex hook after the final configuration restart/materialization; the corrected hash remained current in the settled runtime and the final result is **80 passed, 3 warnings, 0 failed**;
- a non-mutating WSL-to-Windows call returned `POWERSHELL_INTEROP_OK Microsoft Windows NT 10.0.26200.0`;
- the inactive `.beads/embeddeddolt/beads` repository contains zero issues, wisps, comments, dependencies, labels, and events. It is a known side effect of the upstream managed-store re-init bug. It remains preserved because the doctor remediation explicitly says to keep both stores until reconciliation is proven; the canonical managed store remains active and healthy.

Remaining doctor warnings are understood and non-blocking for M1:

- `formula-requirements`: 34 warnings in the pinned upstream pack; no local fork or patch;
- `jsonl-archive`: local-only archive accepted for M1; off-box backup and a fresh-location restore are M3 exit criteria;
- `bd-split-store`: inactive, empty-of-work parasite preserved pending an upstream-supported cleanup path.

`codex-hooks-drift` can reappear transiently when v1.4.1 reloads or rematerializes provider overlays. The proven procedure is to finish configuration changes and session materialization first, then run `gc doctor --fix` and verify a following doctor. No pack or binary patch and no filesystem immutability workaround is used.

M1 exit:

- dedicated/validated WSL2 Linux environment;
- pinned/recorded `gc`, `bd`, `dolt` versions;
- `gh` authenticated to the required repos;
- at least one writer provider CLI validated;
- `agent-factory` cloned locally;
- City initialized and versionable config committed;
- split-store state reconciled or explicitly proven harmless;
- controller start/restart works;
- `gc doctor` has no unresolved hard failures and remaining warnings are understood/documented.

## M2 — Canary

**Status: DONE**

Proven on 2026-09-12 with one city-scoped Codex writer and the minimal `mol-do-work` formula:

- work bead `af-v7a`, workflow `af-c3u`, input convoy `af-6zq`, writer session `af-iil` (`codex-1`);
- effective writer command used `--model gpt-5.6-sol` with `model_reasoning_effort=xhigh`;
- branch `canary/m2-e2e`, commit `77f206a85ab97352aa2e6f9bd2a4f2e653db6d69`;
- GitHub PR #9 targeted `main`, was `CLEAN`/mergeable, had no configured automated checks, passed operator diff review, and merged as `43614760bce9a855a6aeecbfb38090461a905e70`;
- the only delivery artifact was the three-line `docs/CANARY.md`; `git diff --check` passed;
- work bead, formula workflow, formula steps, and convoy closed with `gc.outcome=pass`; writer drained cleanly;
- post-canary configuration experiments restaged the pinned pack hook after each reload. After restoring the canonical provider config, completing the final restart/materialization, and running the official fix last, the settled doctor is **80 passed, 3 warnings, 0 failed** and `codex-hooks-drift` is healthy.

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
