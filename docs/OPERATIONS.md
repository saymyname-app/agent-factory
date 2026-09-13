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

### 2026-09-13 stability remediation

- **TARGET:** stable WSL `2.7.13` and Docker Desktop `4.90.0`, with the existing `Ubuntu-24.04` distribution, Docker Desktop WSL2 architecture, 10 GB memory, 6 GB swap, `autoMemoryReclaim=gradual`, and Resource Saver disabled for unattended operation.
- **CONFIGURED:** WSL `2.7.13.0` in place with kernel `6.18.33.2-2`; Docker Desktop `4.90.0.238679` in place; `Ubuntu-24.04` integration enabled; `UseResourceSaver=false`; Claude Code uses Linux-native `CLAUDE_CONFIG_DIR=/home/benja/.claude`. The Windows Claude configuration is retained only as rollback.
- **OBSERVED:** the former pair was WSL `2.6.3.0` / kernel `6.6.87.2-1` and Docker Desktop `4.34.3`, with Resource Saver enabled. A genuine WSL VM/session failure was captured independently of the interactive shell. Docker causality was not proven. Claude and `bd` processes were also observed waiting in `p9_client_rpc` while using Windows-backed paths.
- **PROVEN:** 20 repeated Windows-to-Ubuntu probes passed; Docker `hello-world` passed; `CourseKnowledgeTenantIsolationIT` passed 2/2 with Ryuk, MySQL 8.0.41 and Flyway V1-V9; 15- and 30-minute idle windows passed; a 60.9-minute factory canary passed 13/13 independent WSL, Docker and Beads probes with zero timeouts and zero observed D-state `p9_client_rpc` backlog. Eight-hour unattended reliability remains unproven until an actual eight-hour run completes.

Docker Engine `29.7.2` rejects the API `1.32` default used by the pinned Testcontainers/docker-java client. The reversible host-local compatibility setting is `~/.docker-java.properties` with `api.version=1.44`; do not encode this machine compatibility setting in an application repository. No native Ubuntu Docker daemon is used alongside Docker Desktop.

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

## Operator dashboard

Gas City `1.4.1` embeds its dashboard SPA in the supervisor and serves the UI and API from the same origin. Use this upstream dashboard; there is no separate dashboard process or factory-owned UI to install, start or upgrade. In this City the operator URL is:

```text
http://127.0.0.1:8372
```

Keep the listener on loopback. The dashboard exposes operational data including beads and provider transcripts, so do not bind it to a LAN interface, publish the port from WSL, or place it behind a network proxy without a separately reviewed authentication and transport design. Windows access through WSL localhost forwarding does not require changing the bind address.

### Start, open and stop

Start the City and resolve the supervisor-owned URL from Ubuntu:

```bash
cd ~/agent-factory
gc start
gc dashboard --no-open
```

`gc dashboard serve` is a compatibility command that also prints the supervisor URL; in `1.4.1` it does not start another static server. To open the dashboard in a Windows browser or verify the Windows-to-WSL path from PowerShell:

```powershell
Start-Process http://127.0.0.1:8372
(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8372/).StatusCode
```

The second command should return `200`. Stop this City with `gc stop`; this stops its sessions and Dolt runtime. The machine-wide supervisor and root dashboard listener may remain available for other registered cities, while `agent-factory` data and API views show the stopped or unavailable City state. There is no dashboard-only stop command.

### Health and recovery

Check the supervisor, loopback listener and both health layers from Ubuntu:

```bash
gc status --json
ss -ltnp 'sport = :8372'
curl --fail --silent --show-error http://127.0.0.1:8372/health
curl --fail --silent --show-error \
  http://127.0.0.1:8372/v0/city/agent-factory/health | jq .
```

The listener must be `127.0.0.1:8372`, not `0.0.0.0:8372`. The City health response should report `status: ok`, `version: 1.4.1`, and `city: agent-factory`.

If the URL is unavailable:

1. Run `gc status --json` and confirm that the controller is running and City health is usable.
2. Run `gc start` if the City is stopped.
3. Run `gc restart` if the City is registered but the supervisor-owned UI or API remains unavailable, then repeat both health checks.
4. If Ubuntu itself is unavailable, use the distribution-scoped WSL recovery in [WSL and Docker Desktop coexistence](#wsl-and-docker-desktop-coexistence); do not add a replacement dashboard server.

### Tailnet HTTPS access with Tailscale Serve

Tailscale Serve is the approved remote operator path for this host. It leaves
the Gas City supervisor on loopback and publishes that loopback service only
inside the authenticated tailnet. Tailscale Funnel is prohibited for the
dashboard.

Docker Desktop currently supplies the Windows Tailscale client, so invoke it
from WSL using its explicit path:

```bash
TAILSCALE_EXE='/mnt/c/Program Files/Tailscale/tailscale.exe'
"$TAILSCALE_EXE" serve --bg --yes http://127.0.0.1:8372
"$TAILSCALE_EXE" serve status --json | jq .
curl --fail --silent --show-error http://127.0.0.1:8372/health
curl --fail --silent --show-error \
  https://benforge.tail9f1386.ts.net/health
```

The browser URL is `https://benforge.tail9f1386.ts.net/`. Tailnet identity and
ACL policy are the access boundary; never add `tailscale funnel`, change the
supervisor bind address, or expose port `8372` directly.

Stop this node's Serve configuration only after confirming it contains no
other routes that must remain available:

```bash
"$TAILSCALE_EXE" serve status --json | jq .
"$TAILSCALE_EXE" serve reset
```

After a supervisor, WSL, or Tailscale interruption, first restore `gc status`
and the loopback `/health` response. Then check `serve status`, reapply the
background Serve command if needed, and verify the tailnet HTTPS health URL.
Do not work around a failure by enabling Funnel or a non-loopback listener.

### 2026-09-14 Tailscale Serve evidence

- **TARGET:** make the existing loopback-only dashboard available to authenticated tailnet operators over HTTPS without a public route.
- **CONFIGURED:** Tailscale Serve maps HTTPS port `443` for `benforge.tail9f1386.ts.net` to `http://127.0.0.1:8372`; the Gas City listener remains on `127.0.0.1:8372`.
- **OBSERVED:** the Windows Tailscale client reported version `1.102.4`, backend state `Running`, the node online, and the HTTPS web proxy handler configured.
- **PROVEN:** both the loopback and tailnet `/health` endpoints returned the same healthy Gas City `1.4.1` service. This proves the path at the time of verification, not durable availability after restart.

### 2026-09-13 evidence

- **TARGET:** use the dashboard embedded in the pinned Gas City supervisor, expose it on localhost only, and cover agents, beads, runs, activity/transcripts and health with a real SayMyName workflow as canary.
- **CONFIGURED:** `gc version` reported `1.4.1`; `gc dashboard --no-open` resolved `http://127.0.0.1:8372`; `ss` showed PID `14033` listening only on `127.0.0.1:8372` during the check. PIDs and live counts are observational and will change.
- **OBSERVED:** `/`, `/health`, and the city-scoped `/health`, `/agents`, `/beads`, `/runs/census`, `/events?limit=5`, `/workflow/smf-xir`, and current Mayor session transcript endpoints under `/v0/city/agent-factory` all returned HTTP `200`. The API reported six agents, 75 beads, five requested recent events, and a conversation-format Codex Mayor transcript with 1,597 turns at the instant of verification. The root response set `Cache-Control: no-store`, a same-origin `Content-Security-Policy` with `frame-ancestors 'none'`, `X-Frame-Options: DENY`, and `X-Content-Type-Options: nosniff`.
- **PROVEN:** City health returned `status=ok`, `version=1.4.1`, and `city=agent-factory`. The existing SayMyName frontend workflow `smf-xir` resolved from `rig:saymyname-frontend` with nine beads and `partial=false`. Windows PowerShell `Invoke-WebRequest` to the same localhost URL returned HTTP `200`. These checks prove current reachability and API/UI coverage, not durable availability; rerun them after supervisor or WSL recovery.

## Secondary provider qualification

Gas City `v1.4.1` supplies both `builtin:claude` and `builtin:opencode`; use
provider inheritance rather than an adapter. The workspace default remains
`codex`/`gpt-5.6-sol`.

The host-local Claude provider uses pinned CLI `2.1.236`, the existing
Claude.ai Pro subscription, `claude-sonnet-5`, and plan mode. Its authentication
configuration path is intentionally machine-local and contains no token in Git.
Verify configuration and subscription without repository writes:

```bash
gc config explain --provider claude --json
CLAUDE_CONFIG_DIR=/home/benja/.claude DISABLE_AUTOUPDATER=1 \
  /home/benja/.local/bin/claude -p --model claude-sonnet-5 \
  --permission-mode plan --output-format json \
  'Do not use tools. Reply exactly CLAUDE_SUBSCRIPTION_CANARY_OK'
```

Complete the supported Claude Code OAuth/onboarding flow inside Linux; never
copy, print, or migrate credential material manually. The direct Linux-native
probe on 2026-09-13 returned `CLAUDE_LINUX_NATIVE_CANARY_OK` using the Claude.ai
Pro subscription. Gas City session `af-wisp-a1rvl` then returned
`GAS_CITY_CLAUDE_LINUX_NATIVE_CANARY_OK` in plan mode. Normal Claude mutable
configuration, plugin and cache paths resolve under `/home/benja`, not `/mnt/c`.
No API key was introduced.

Windows Ollama `0.33.3` exposes installed model `qwen3:8b` (~5.2 GB). A direct,
tool-free synthetic canary returned `LOCAL_CANARY_OK` and selected `README.md`
correctly in about 66 seconds on a cold load. WSL could not reach TCP 11434 on
loopback or the WSL adapter. A narrowly scoped Windows firewall change was not
authorized, so no Gas City `local-*` provider is configured and no repository
read-only claim is made. The supported future path is `builtin:opencode` plus
OpenCode's Ollama provider and explicit denial of edit, bash, task, and external
directory access, after the network boundary is separately authorized and
tested. Do not add port proxies, firewall rules, or a custom adapter silently.

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

Use Beads `1.2.2` Dolt-native backup, not JSONL export. JSONL is an interchange format and does not preserve Dolt branches, commit history, working sets, or non-issue tables.

Create and refresh the local backup while the City is suspended so the work snapshot is stable:

```bash
cd ~/agent-factory
gc suspend
mkdir -p .gc/backups
bd backup init "$PWD/.gc/backups/m3-beads"
bd backup sync
bd backup status
```

The configured path is host-local and ignored by Git. It contains the complete Dolt-native backup and may contain durable factory data; never commit or upload it as a generic Git artifact. A supported DoltHub destination can replace the filesystem path when separately authenticated, private, and verified. GitHub CLI authentication is not DoltHub authentication.

For a recovery drill, keep exactly one controller and restore into a fresh clone whose basename and City identity remain `agent-factory`:

```bash
gc stop ~/agent-factory
git clone --branch main --single-branch \
  https://github.com/benjamin-hurand/agent-factory.git \
  /tmp/m3-restore/agent-factory

# Let Gas City create its managed .beads/dolt/hq layout. With Beads 1.2.2,
# this bootstrap may stop when refs/dolt/data already exists; unregister it
# before completing the offline restore.
gc start /tmp/m3-restore/agent-factory || true
gc unregister /tmp/m3-restore/agent-factory || true

cd /tmp/m3-restore/agent-factory/.beads/dolt
dolt backup restore --force \
  file://$HOME/agent-factory/.gc/backups/m3-beads hq

gc register /tmp/m3-restore/agent-factory --yes
gc start /tmp/m3-restore/agent-factory
gc status
gc bd config get issue_prefix
gc bd show af-v7a
gc doctor
gc restart
gc status
gc doctor
```

`--force` above is scoped only to the newly created disposable `hq` target; it is not a generic repair and must never target the canonical store. Do not use `bd init --force` or `bd init --reinit-local`, and never delete `.beads/embeddeddolt`.

Return to the canonical City before removing any temporary recovery clone:

```bash
gc stop /tmp/m3-restore/agent-factory
gc start ~/agent-factory
gc resume
gc status
gc bd config get issue_prefix
gc bd show af-v7a
gc doctor
git -C ~/agent-factory status --short --branch
```

The 2026-09-12 drill restored `af-v7a`, its M2 commit/outcome metadata, the `af-c3u -> af-hhx` workflow dependency, and `issue_prefix=af`; the restored City survived restart. Canonical recovery ended at **79 passed, 4 warnings, 0 failed** with no data loss. Off-box backup is not yet configured because no existing DoltHub credential/private destination was available; this is a durability limitation, not a reason to push the raw runtime to GitHub.

## SayMyName rig operations

The two application rigs use clean Linux clones under the host-local, Git-ignored `~/agent-factory/rigs/` directory. Their site-bound paths remain in `.gc/site.toml`; `city.toml` versions only names, unique prefixes, default branches and pinned imports.

```bash
gc rig list
gc rig status saymyname-backend
gc rig status saymyname-frontend
gc bd --rig saymyname-backend config get issue_prefix  # smb
gc bd --rig saymyname-frontend config get issue_prefix # smf
gc doctor
```

Gas City runtime paths generated inside application clones must remain untracked. Each clone uses local `.git/info/exclude` entries for `.beads/`, `.codex/`, `.gc/` and `rigs/`; do not modify an application `.gitignore` merely to host a rig.

The host toolchains proven during M5 are Temurin Java `21.0.12.1`, Maven `3.9.9`, Node `22.23.2` and npm `10.9.8`. Backend Docker/Testcontainers integration is now proven locally through the scoped `CourseKnowledgeTenantIsolationIT` canary; the existing GitHub `Backend CI` remains authoritative before merge. Frontend full lint is a known non-gating baseline; require tests/build and task-scoped lint evidence rather than claiming the baseline is clean.

Each rig has a registered Dolt backup remote at `.dolt-backup/smb` or `.dolt-backup/smf`. Refresh them through the managed Dolt server before risky maintenance, using the port reported by `gc dolt status` and the official `CALL DOLT_BACKUP('sync', '<prefix>-backup')` primitive. These directories contain runtime data and remain excluded from Git.

`accept_startup_dialogs = true` is configured on the Codex provider. This is the supported Gas City option that lets a newly materialized ephemeral session pass Codex's startup trust dialog; it does not weaken repository, GitHub or human delivery gates.

### Deterministic local product preview

Run the latest merged Backend and Frontend `dev` branches from the canonical
Factory checkout with:

```bash
cd ~/agent-factory
./bin/saymyname-preview start
./bin/saymyname-preview status
./bin/saymyname-preview restart
./bin/saymyname-preview stop
```

The host prerequisites are Docker Desktop WSL integration, Java 21, Maven,
Node/npm, and `curl`, `jq`, `flock`, `openssl`, `ss`, and `git`. Both application
rigs must be suspended, with no active rig writer. Their canonical Linux clones
must be on `dev`, clean including untracked files, no commits ahead of
`origin/dev`, and their only registered worktree. The command verifies the
canonical GitHub remotes, fetches, and uses only
`git merge --ff-only origin/dev`; it fails closed on dirty, wrong-branch, ahead, diverged,
multi-worktree, or active-writer state.

Each successful start builds both applications and creates a new preview-only
runtime under `/run/user/<uid>/agent-factory/saymyname-preview` (or a guarded
Linux `/tmp` fallback). It generates synthetic credentials and Spring config
there without printing them. MySQL is pinned to `mysql:8.0.41`, stores its data
on container `tmpfs`, and publishes a random loopback port. Backend and Frontend
listen only on `127.0.0.1:8080` and `127.0.0.1:5173`; the browser URL is:

```text
http://127.0.0.1:5173/
```

This is a local preview, not a production deployment. It never uses a
persistent database, production credentials, or production mail: the Backend
runs its existing `dev` profile and console mailer with a synthetic Google
audience. `status` prints the exact source SHAs and health without secrets; it
returns `0` when healthy, `1` when degraded, and `3` when stopped.

`stop` validates the run marker, process start times, process-group ownership,
container label, and run ID before removing anything. On a degraded or stale
run, inspect `status` and the runtime logs, then use `stop` and fix the reported
repository, rig, port, Docker, or toolchain condition before `start` or
`restart`. Never kill an arbitrary PID, free a port, or delete a similarly
named container to make the preview pass; ownership uncertainty intentionally
requires manual investigation.

#### 2026-09-14 preview evidence

- **TARGET:** provide one deterministic Factory-owned command that previews the latest merged application `dev` branches without mutating persistent application data.
- **CONFIGURED:** the wrapper pins the canonical application remotes, `dev` branches, MySQL `8.0.41`, loopback application ports, an ephemeral database `tmpfs`, and generated preview-only configuration.
- **OBSERVED:** Backend resolved to `2cba440d2815ded53dfea7bfd3beecdf57355c50` and Frontend to `b98e1ee176b7ed8af62987fdd84b35065b49c9e1`; MySQL used loopback-only random ports and both application repositories remained clean on `dev`.
- **PROVEN:** clean start and restart cycles reached Backend HTTP `204` at `/api/auth/csrf` and Frontend HTTP `200`; independent status reported both healthy with the exact SHAs. Stop removed the owned process groups, container, and runtime state, after which status returned `3` and the preview listeners were absent. Eight deterministic safety tests also proved the repository, writer, and runtime-directory fail-closed checks.

### Legacy cutover boundary

The cutover occurred at `2026-09-12T16:38:00Z`. The Windows repo at
`/mnt/c/Dev/Projects/SayMyName/Automation` is not a Gas City rig. Its GitHub
repository is archived and its Scheduled Task `SayMyName-LocalCodexRunner`
remains installed but disabled. The archived repository is the reversible
write barrier for the former GitHub queue; do not unarchive it for ordinary
history access.

Preserve `.runner/state`, receipts, recovery receipts, logs and historical
worktree registrations for audit/rollback. Do not clean the dirty Windows
checkout, prune worktrees, delete the task, edit `config/runner.json`, or rotate
secrets merely as part of decommissioning.

New work procedure:

```bash
gc bd create "<bounded backend task>" --rig saymyname-backend --labels delivery:standard
gc bd create "<bounded frontend task>" --rig saymyname-frontend --labels delivery:standard
```

Create only actually ready tasks; never bulk-copy Linear Done/Todo history.

### Temporary M6 rollback

Rollback is an emergency choice, not a routine retry:

1. prove no Backend/Frontend Bead is assigned or in progress and no application
   PR has ambiguous ownership;
2. suspend both new paths with `gc rig suspend saymyname-backend` and
   `gc rig suspend saymyname-frontend`;
3. re-check that the legacy ledgers and queue contain no in-flight item;
4. unarchive `saymyname-app/Say-my-name-automation` in GitHub;
5. verify the retained task still has URI `\\SayMyName-LocalCodexRunner`, source
   `SayMyNameAutomationPhase4`, the expected script/config paths, and remains
   disabled;
6. run the legacy manager's `Status`, then `Resume` only after those proofs;
7. never resume either Gas City rig while the legacy dispatcher is enabled.

To return to the new path, pause the managed Scheduled Task first, prove its
process has exited and no queue item is in flight, archive Automation again,
then resume both rigs. Do not test rollback by enabling both systems.

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
