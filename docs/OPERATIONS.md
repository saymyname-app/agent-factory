# Operations

## Bootstrap policy

Pin versions; never auto-follow `latest` on an active factory.

Verified upstream baseline for this bootstrap on 2026-09-12:

- Gas City `v1.4.1`
- Beads `v1.2.2` (Gas City `v1.4.1` pin)
- Dolt `2.1.7` (Gas City `v1.4.1` pin)

These are bootstrap choices, not permanent upgrade policy.

## M1 preflight

The factory host is the dedicated `Ubuntu-24.04` WSL2 distribution, not Docker Desktop's internal `docker-desktop` distribution.

Observed base versions:

- Git `2.43.0`
- GitHub CLI `2.45.0`
- tmux `3.4`
- jq `1.7`
- flock/util-linux `2.39.3`
- Gas City `1.4.1`
- Beads `1.2.2`
- Dolt `2.1.7`

GitHub CLI auth inside Ubuntu is required before repository operations.

## WSL and Docker Desktop coexistence

Docker Desktop and the factory Ubuntu distribution can coexist. They are separate WSL2 distributions.

Important Docker Desktop setting: if **Enable integration with my default WSL distro** is enabled and `Ubuntu-24.04` is the Windows default WSL distribution, Docker integrates with Ubuntu even when the per-distro `Ubuntu-24.04` toggle under "additional distros" is disabled. During M1 bootstrap, disable the default-distro integration as well so the City host is isolated from Docker's distro proxy. Re-enable Docker integration later only when a project needs it (for example Testcontainers) and after a dedicated canary proves WSL stability.

`wsl --shutdown` stops the whole WSL VM set, including Docker Desktop's internal WSL distribution. Docker Desktop may therefore report that its WSL distro terminated abruptly after such a command. This is expected operational impact, not evidence that the factory Ubuntu distribution conflicts with Docker Desktop.

For a factory-only restart while Docker should remain available, prefer a distribution-scoped restart from Windows:

```powershell
wsl --terminate Ubuntu-24.04
wsl -d Ubuntu-24.04 --user benja --cd ~
```

If the distribution hangs with `HCS_E_CONNECTION_TIMEOUT`, a restart of `WslService` recovered the observed host non-destructively:

```powershell
Restart-Service WslService -Force
Start-Sleep -Seconds 10
wsl -d Ubuntu-24.04 --user benja --exec /bin/echo WSL_OK
```

A successful `WSL_OK` proves the distro can start non-interactively. Do not use `wsl --unregister` as a recovery step; it deletes the distribution.

Use global `wsl --shutdown` only when intentionally stopping all WSL consumers, then restart Docker Desktop if needed.

## City initialization

The first City bootstrap uses Gas City's official flow and deliberately avoids provider execution:

```bash
gc init \
  --template gascity \
  --providers codex \
  --default-provider codex \
  --skip-provider-readiness \
  --no-start \
  --preserve-existing \
  .
```

Dolt author identity is required before managed storage finalization. Use a non-secret stable factory identity or the operator's normal Git author identity where appropriate.

Beads maintainer role is explicit for this HTTPS clone:

```bash
git config --global beads.role maintainer
```

The observed deterministic repair after first bootstrap is:

```bash
cd ~/agent-factory
gc doctor --fix
gc doctor
```

On the current host this installed/synchronized four remote imports, generated `packs.lock`, and registered all 13 Gas City-required custom bead types. Initial post-fix doctor result: **81 passed, 5 warnings, 0 failed**. Long-window verification after restart/materialization shows the hook fix is overwritten again; the stable result is **79 passed, 4 warnings, 0 failed**.

Do not start provider sessions until generated configuration is inspected and at least one provider CLI is installed/authenticated.

Host-local runtime state, credentials, local paths and caches must remain untracked.

## Split-store warning

The current bootstrap reports:

- active store: `.beads/dolt` (`endpoint_origin=managed_city`);
- inactive store: `.beads/embeddeddolt`, containing one Dolt repository.

Gas City upstream issue `gastownhall/gascity#1436` is open and documents a parasitic `.beads/embeddeddolt` store created by some bootstrap/recovery paths. Treat this as an upstream limitation, not permission to delete data.

Before deleting or reconciling an inactive store:

1. inspect its repository path and tables;
2. determine whether it contains any issues/data not present in the active store;
3. if data exists, export to JSONL, review with `bd import --dry-run`, then import into the active store;
4. keep both directories until reconciliation is proven.

Do **not** use `bd init --force` or `bd init --reinit-local` as a generic bootstrap fix; upstream issue reports show those paths can create the parasitic embedded store and disturb custom types.

## Proven M1 lifecycle

The following lifecycle was executed successfully on 2026-09-12:

```bash
gc suspend
gc session suspend mayor
gc restart
gc resume
gc start
gc status
gc session list
bd config get issue_prefix
gc doctor --fix
gc doctor
```

The supervisor was replaced (`PID 8443` to `PID 70035`) and remained systemd/supervisor-managed. The canonical Dolt store remained accessible, `issue_prefix` remained `af`, and the always-on Mayor rematerialized as session/bead `af-hkb`.

The configured provider pin is not sufficient evidence by itself. Verify both the session metadata and the live process:

```bash
gc bd show <mayor-session-bead>
pgrep -af 'codex.*gpt-5.6-sol'
codex exec --skip-git-repo-check --sandbox read-only -m gpt-5.6-sol \
  'Reply with exactly: SOL_AUTH_OK'
```

M1 observed the effective Mayor command as `codex --dangerously-bypass-approvals-and-sandbox --model gpt-5.6-sol -c model_reasoning_effort=xhigh`, the matching process was live, and the authenticated probe returned `SOL_AUTH_OK`.

Gas City `v1.4.1` restages an older pinned-pack Codex hook after the official fix, including after configuration and sessions appear settled. Repeated 20–45 second windows reproduced the rollback from corrected hash `3234b7de…` to stale hash `cabcf576…`. Official fix/restart, runtime-source alignment, provider aliasing, and local-overlay experiments did not converge. Do not patch the pinned pack/binary or make the file immutable as a bootstrap workaround; require a pinned upstream fix or supported remediation before closing M1.

WSL/Windows operator interop was proven non-destructively with:

```bash
powershell.exe -NoProfile -NonInteractive -Command \
  "Write-Output ('POWERSHELL_INTEROP_OK ' + [System.Environment]::OSVersion.VersionString)"
```

## Doctor

M1 is not complete until the actual City has no unresolved hard failures and remaining warnings are understood/documented.

Final M1 warning interpretation after controller restart:

- `formula-requirements`: upstream pack warnings; no local rewrite during M1 unless they block the canary.
- `bd-split-store`: the inactive embedded repository was inspected and contains zero issues, wisps, comments, dependencies, labels, and events. The active managed store is healthy. Preserve the inactive store until an upstream-supported cleanup path exists; never auto-delete it.
- `jsonl-archive`: local-only mode is accepted for M1. Configure and prove off-box backup plus fresh-location restore in M3 rather than adding an unvalidated remote during bootstrap.

`codex-hooks-drift` remains non-convergent as described above. `agent-sessions`, `orphan-sessions`, and `beads-store` are healthy after startup.

## Backup / restore

M3 will define and prove the exact commands for the deployed Beads mode. Do not claim backup is complete merely because JSONL exports exist. A fresh-location restore test is mandatory before cutover.

## Upgrade

Before every active-factory upgrade:

1. Read relevant release notes/issues.
2. Capture deployed versions.
3. Back up Beads/Dolt.
4. Stop or isolate the controller as required.
5. Upgrade pinned versions deliberately.
6. Run doctor.
7. Run a FAST canary.
8. Keep a rollback path to the previous binary/config/store state.
