# Operations

## Bootstrap policy

Pin versions; never auto-follow `latest` on an active factory.

Verified upstream baseline for this bootstrap on 2026-09-12:

- Gas City `v1.4.1`
- Beads `v1.2.2` (Gas City `v1.4.1` CI pin)
- Dolt `2.1.7` (Gas City `v1.4.1` CI pin)

These are bootstrap choices, not permanent upgrade policy.

## M1 preflight

Run in the intended WSL2 Linux distribution from a normal shell. The first goal is inventory, not mutation.

```bash
set -u
printf '== OS ==\n'
uname -a
printf '\n== WSL ==\n'
grep -iE 'microsoft|wsl' /proc/version || true
printf '\n== binaries ==\n'
for c in git gh tmux jq flock gc bd dolt codex claude ollama; do
  printf '%-8s ' "$c"
  command -v "$c" || echo MISSING
done
printf '\n== versions ==\n'
git --version || true
gh --version | head -n 1 || true
tmux -V || true
jq --version || true
command gc version || true
bd version || true
dolt version || true
codex --version || true
claude --version || true
ollama --version || true
printf '\n== GitHub auth ==\n'
gh auth status || true
printf '\n== repository ==\n'
if [ -d "$HOME/agent-factory/.git" ]; then
  git -C "$HOME/agent-factory" status --short --branch
else
  echo 'agent-factory not cloned at ~/agent-factory'
fi
```

Do not install/upgrade anything until this inventory has been reviewed against the pinned bootstrap versions.

## City initialization

Not yet CONFIGURED. After prerequisites are validated, initialize using Gas City's official `gc init` flow rather than hand-creating runtime config. Version generated/configurable City files only after inspection.

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
