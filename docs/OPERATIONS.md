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

`wsl --shutdown` stops the whole WSL VM set, including Docker Desktop's internal WSL distribution. Docker Desktop may therefore report that its WSL distro terminated abruptly after such a command. This is expected operational impact, not evidence that the factory Ubuntu distribution conflicts with Docker Desktop.

For a factory-only restart while Docker should remain available, prefer a distribution-scoped restart from Windows, for example:

```powershell
wsl --terminate Ubuntu-24.04
wsl -d Ubuntu-24.04 --user benja --cd ~
```

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

On the observed host, this created the runtime scaffold, hooks, prompts, `pack.toml` and City configuration, then stopped on the Gas City Dolt-author preflight because Dolt global `user.name` and `user.email` were absent.

This is a recoverable bootstrap blocker. Configure a non-secret Dolt author identity before store finalization:

```bash
dolt config --global --add user.name "<author name>"
dolt config --global --add user.email "<author email>"
```

Prefer reusing the operator's normal Git author identity if it is already configured and appropriate. Do not put credentials or tokens in these values.

After setting identity, inspect before starting anything:

```bash
cd ~/agent-factory
git status --short --branch
printf '\n--- city.toml ---\n'
cat city.toml
printf '\n--- pack.toml ---\n'
cat pack.toml
printf '\n--- packs.lock ---\n'
cat packs.lock 2>/dev/null || echo 'packs.lock absent'
printf '\n--- doctor ---\n'
gc doctor || true
```

Do not start provider sessions until the generated configuration has been inspected and at least one provider CLI has been installed/authenticated.

Host-local runtime state, credentials, local paths and caches must remain untracked.

## Doctor

M1 is not complete until `gc doctor` is healthy in the actual City. Record command output/evidence in the migration bead or a durable operational note where appropriate; do not rely on chat memory.

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
