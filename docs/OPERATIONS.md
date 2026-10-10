# Operations

> Retired systems (Cockpit V1, ntfy, campaign, product queue/status/preview,
> release contract, improvement axes) are documented only under `../legacy/`
> (untrusted; see `../legacy/README.md`).

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

## Detailed Gas City dashboard

Gas City `1.4.1` embeds its detailed dashboard SPA in the supervisor and serves
the UI and API from the same origin. Use it for engineering detail (Cockpit V1
is retired, see `../legacy/README.md`). In this City the Gas City URL is:

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

The Windows Tailscale client is installed separately from Docker Desktop.
Invoke it from WSL using its explicit path, and fail closed unless the Funnel
status explicitly says the route is tailnet-only:

```bash
TAILSCALE_EXE='/mnt/c/Program Files/Tailscale/tailscale.exe'
"$TAILSCALE_EXE" serve --bg --yes http://127.0.0.1:8372
"$TAILSCALE_EXE" serve status --json | jq .
FUNNEL_STATUS=$("$TAILSCALE_EXE" funnel status)
printf '%s\n' "$FUNNEL_STATUS"
case "$FUNNEL_STATUS" in
  *'(Funnel on)'*) echo 'ERROR: public Funnel exposure is enabled' >&2; exit 1 ;;
  *'(tailnet only)'*) ;;
  *) echo 'ERROR: could not prove that Funnel is disabled' >&2; exit 1 ;;
esac
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
and the loopback `/health` response. Then check both `serve status` and `funnel
status`, reapply the background Serve command if needed, prove the route still
says `(tailnet only)`, and verify the tailnet HTTPS health URL. Do not work
around a failure by enabling Funnel or a non-loopback listener.

### 2026-09-14 Tailscale Serve evidence

- **TARGET:** make the existing loopback-only dashboard available to authenticated tailnet operators over HTTPS without a public route.
- **CONFIGURED:** Tailscale Serve maps HTTPS port `443` for `benforge.tail9f1386.ts.net` to `http://127.0.0.1:8372`; the Gas City listener remains on `127.0.0.1:8372`.
- **OBSERVED:** the independently installed Windows Tailscale client reported version `1.102.4`, backend state `Running`, the node online, the HTTPS web proxy handler configured, and `funnel status` labeled the route `(tailnet only)`.
- **PROVEN:** both the loopback and tailnet `/health` endpoints returned the same healthy Gas City `1.4.1` service, while the client reported no public Funnel route. This proves the path at the time of verification, not durable availability after restart.

### 2026-09-13 evidence

- **TARGET:** use the dashboard embedded in the pinned Gas City supervisor, expose it on localhost only, and cover agents, beads, runs, activity/transcripts and health with a real SayMyName workflow as canary.
- **CONFIGURED:** `gc version` reported `1.4.1`; `gc dashboard --no-open` resolved `http://127.0.0.1:8372`; `ss` showed PID `14033` listening only on `127.0.0.1:8372` during the check. PIDs and live counts are observational and will change.
- **OBSERVED:** `/`, `/health`, and the city-scoped `/health`, `/agents`, `/beads`, `/runs/census`, `/events?limit=5`, `/workflow/smf-xir`, and current Mayor session transcript endpoints under `/v0/city/agent-factory` all returned HTTP `200`. The API reported six agents, 75 beads, five requested recent events, and a conversation-format Codex Mayor transcript with 1,597 turns at the instant of verification. The root response set `Cache-Control: no-store`, a same-origin `Content-Security-Policy` with `frame-ancestors 'none'`, `X-Frame-Options: DENY`, and `X-Content-Type-Options: nosniff`.
- **PROVEN:** City health returned `status=ok`, `version=1.4.1`, and `city=agent-factory`. The existing SayMyName frontend workflow `smf-xir` resolved from `rig:saymyname-frontend` with nine beads and `partial=false`. Windows PowerShell `Invoke-WebRequest` to the same localhost URL returned HTTP `200`. These checks prove current reachability and API/UI coverage, not durable availability; rerun them after supervisor or WSL recovery.

## Cockpit V2 operator access (Tailscale Serve)

Cockpit V2 (`bin/cockpit`, spec af-oohx2x, C01) is the approved operator
surface for the factory's day-to-day state — NEEDS BENJAMIN, proposals,
project/chantier status, Operator Actions. It listens on
`127.0.0.1:8173` (default; `COCKPIT_PORT`) inside WSL and refuses any
other bind address outright (`lib/cockpit/core/server.py`). After a merge
that changes it, the running process still runs the old code until
`bin/cockpit restart` (`COCKPIT.md`, "Process lifecycle"). The Gas City
dashboard on port `8372` (`gc`'s own API/UI, see "Detailed Gas City
dashboard" above) is a separate, engineering-only surface and is **never**
exposed to the tailnet: only the cockpit's own port gets a Tailscale Serve
entry.

Exposure follows the exact same pattern already proven for the dashboard
above, pointed at the cockpit's port instead:

```bash
TAILSCALE_EXE='/mnt/c/Program Files/Tailscale/tailscale.exe'
"$TAILSCALE_EXE" serve --bg --yes http://127.0.0.1:8173
"$TAILSCALE_EXE" serve status --json | jq .
FUNNEL_STATUS=$("$TAILSCALE_EXE" funnel status)
case "$FUNNEL_STATUS" in
  *'(Funnel on)'*) echo 'ERROR: public Funnel exposure is enabled' >&2; exit 1 ;;
  *'(tailnet only)'*) ;;
  *) echo 'ERROR: could not prove that Funnel is disabled' >&2; exit 1 ;;
esac
```

Hard rules (spec .94, .95 — enforced by `bin/cockpit-setup-wizard serve`,
not only documented here):

- **Tailscale Funnel is prohibited** for the cockpit, same as for the
  dashboard — Serve only, tailnet-only.
- **The gc supervisor's API/port (`8372`) is never given a Serve entry.**
  The only Serve route on this host is the cockpit's own port; any
  previous `443`/`8443` Serve entries pointed at the gc API have been
  removed by Benjamin.
- A request reaches the cockpit's write actions only with the
  `Tailscale-User-Login` header equal to Benjamin's configured login
  (`COCKPIT_BENJAMIN_LOGIN`); without it, or with any other login, the
  request is refused outright (`lib/cockpit/access/guard.py`) — never
  silently downgraded.
- Secrets (Pushover app token/user key/E2E key, the Healthchecks.io
  heartbeat ping URL) live in files outside this repository, on the
  Windows side, read by the cockpit through `/mnt/c` — never in git, never
  echoed in chat or logs. A missing or invalid secret file shows up in the
  cockpit's own health zone instead of failing silently
  (`lib/cockpit/notify/secrets.py`, `lib/cockpit/heartbeat/emitter.py`).

### First-time setup

`bin/cockpit-setup-wizard` walks through the parts of this setup that the
cockpit cannot do for itself: writing the Pushover secrets file, writing
the Healthchecks.io heartbeat ping-URL file, checking the "Usine muette"
Healthchecks.io check's parameters (period 5 min, grace 10 min, "up"
notification disabled), configuring Tailscale Serve to the cockpit's port
(refusing Funnel or the gc port outright), and recording the real-device
check that a time-sensitive Pushover push breaks through an allowed Focus
mode. Run each step with `--help` for its exact flags; `tests/cockpit-setup-wizard-test.sh`
is the executable spec for what it refuses and what it never prints.

### Tailscale key expiry

The cockpit reads the Tailscale node key's expiry date from `tailscale
status --json` (`lib/cockpit/access/tailscale.py`) and raises an "À
faire" Operator Request 14 days before it (J-14), so renewal never
happens as an emergency after the tailnet has already gone dark.

## Secondary provider qualification

Gas City `v1.4.1` supplies both `builtin:claude` and `builtin:opencode`; use
provider inheritance rather than an adapter. The workspace default remains
`codex`/`gpt-5.6-sol`.

The host-local Claude provider uses CLI `2.1.290` (Opus 5.5 needs `2.1.280`
or newer), the existing Claude.ai subscription, `claude-opus-5-5`, and plan mode. Its authentication
configuration path is intentionally machine-local and contains no token in Git.
Verify configuration and subscription without repository writes:

```bash
gc config explain --provider claude --json
CLAUDE_CONFIG_DIR=/home/benja/.claude DISABLE_AUTOUPDATER=1 \
  /home/benja/.local/bin/claude -p --model claude-opus-5-5 \
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
  https://github.com/saymyname-app/agent-factory.git \
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

The 2026-09-12 drill restored `af-v7a`, its M2 commit/outcome metadata, the `af-c3u -> af-hhx` workflow dependency, and `issue_prefix=af`; the restored City survived restart. Canonical recovery ended at **79 passed, 4 warnings, 0 failed** with no data loss. At the time of this drill off-box backup was not configured because no existing DoltHub credential/private destination was available. Off-box backup is now configured: the `core/jsonl-archive` order exports the stores and pushes them to the private `saymyname-app/agent-factory-archive` repository every 15 minutes (`RUNBOOK_STOP_AND_RESTART.md` §5). That JSONL export is an interchange copy, not a Dolt-native backup, and it is still not a reason to push the raw runtime to GitHub.

## Product rig operations

A product rig uses a clean Linux clone under the host-local, Git-ignored `~/agent-factory/rigs/` directory. Its site-bound path remains in `.gc/site.toml`; `city.toml` versions only its name, unique prefix, default branch and pinned imports.

```bash
gc rig list
gc rig status <rig>
gc bd --rig <rig> config get issue_prefix
gc doctor
```

Gas City runtime paths generated inside an application clone must remain untracked. Each clone uses local `.git/info/exclude` entries for `.beads/`, `.codex/`, `.gc/` and `rigs/`; do not modify an application `.gitignore` merely to host a rig.

A product-specific toolchain, proven CI baseline, and per-rig Dolt backup remote are recorded in that rig's own repository, not here — see its `AGENTS.md` for the pointer (progressive disclosure).

Each rig has a registered Dolt backup remote at `.dolt-backup/<rig-prefix>`. Refresh it through the managed Dolt server before risky maintenance, using the port reported by `gc dolt status` and the official `CALL DOLT_BACKUP('sync', '<prefix>-backup')` primitive. This directory contains runtime data and remains excluded from Git.

`accept_startup_dialogs = true` is configured on the Codex provider. This is the supported Gas City option that lets a newly materialized ephemeral session pass Codex's startup trust dialog; it does not weaken repository, GitHub or human delivery gates.

## Closing the delivered-outcome Bead

`gc.last_delivered` must only ever point at a Bead that carries all six
ADR-0016 delivery-proof fields (`gc.delivery_status`, `gc.work_outcome`,
`gc.github_repo`, `gc.pr_number`, `gc.pr_head`, `gc.merge_commit`), because
the delivery-proof predicate (`lib/factory_delivery_proof.py`) requires every one of them and fails closed
otherwise. Never close that Bead by hand with `gc bd close` or a raw `gc bd
update --status=closed`; use the deterministic wrapper instead:

```bash
./bin/deliver-close <bead-id> --repo <owner/repository> --pr <number>
```

It independently verifies the named pull request is merged, resolves the
configured required GitHub Actions workflow, and requires its latest
`pull_request` run to be successful on the exact PR head. It then writes the
six ADR-0016 fields, `merge_result`/SHA/target, and the `gc.ci_*` proof while
closing the Bead in one call. Unknown repositories pass
`--required-workflow <name>` explicitly; the three Factory-managed repositories
are inferred. Unmerged, red-CI, missing-run, head-mismatch, or branch/base/URL
mismatch paths make no metadata change. `tests/deliver-close-test.sh` covers
those cases against `GC_BIN`/`GH_BIN` fixtures.

mol-do-work's own work bead uses the lighter door instead, before any PR
exists to verify:

```bash
./bin/deliver-close <bead-id> --outcome shipped --commit <sha> --branch <branch>
./bin/deliver-close <bead-id> --outcome no-op|blocked|abandoned
```

This form writes the ADR-0009 work-record outcome (`gc.outcome=pass`,
`gc.work_outcome=<outcome>`) for explicit non-PR work. A bead governed by
`gc.delivery_contract=pr-ci-merged-v1` (including an approved delivery-graph
ticket) cannot use `--outcome shipped` before its PR is linked. If the bead
already names `gc.pr_url`, the same merge+exact-head-CI verification runs and
the shipped path records full proof. It refuses the close on any failed proof
(af-fzlp2, 2026-09-18:
af-jj9u7/PR #120 was closed shipped while still open with red CI, af-cwitl/PR
#123 while it had unresolved merge conflicts — both caught only afterward by
`factory-delivery-guard`, never blocked at close time before this check).

The `--outcome shipped` door only ever runs when a commit really is the end
of the work: a non-HQ-rig dispatch, or a no-op/blocked/abandoned outcome.
When `workspace-setup` isolated the dispatch into an HQ worktree, a PR is
still to come — `do-work` defers the close instead of calling this door
(af-6scsz, 2026-09-19: af-hyls9 had closed shipped via this path while PR
#159 was still open with CI in_progress). `push-and-pr` records the PR and
waiting contract but leaves the bead `in_progress`; `mol-polecat-commit` and
`mol-scoped-work` do the same. `pr-autopilot` later calls `deliver-close`, and
only that verified write closes the PR-backed bead (ADR-0026).

`push-and-pr` opens nothing when there is nothing left to deliver (af-cjaj8o,
2026-10-08). The worktree's post-commit hook pushes every commit, so on a
re-dispatch the ticket's open PR can pass CI and merge before `push-and-pr`
runs: on af-cbp84n, `finish` then opened a second, empty PR #445 after #444
had merged, and the step rewrote the closed ticket to `waiting` on it, which
failed pr-autopilot five times. `bin/factory-do-work-workspace finish` now
exits 4 — no push, no PR, no URL, worktree removed — when the branch's head is
exactly the head of a PR already merged into the base, or when its tree has no
difference with the base; the step then only drops `work_dir` and leaves
`gc.pr_url`, `gc.delivery_status` and the notes as they are. New commits made
after the merge are still delivered through a new PR.

`push-and-pr` can be run again after a failed `finish` (af-hmqlf5,
2026-10-08). When `finish` exits non-zero other than 4 — 3, PR sections
missing; 1, the push failed — the step writes nothing on the work bead and
keeps `work_dir`. It used to drop `work_dir` in that case, so the re-run read
`.`, printed "nothing to do", and the work stayed unpublished.

The SayMyName legacy-automation cutover boundary and its temporary M6
rollback procedure are dead, product-specific history now retired to
`legacy/docs/products/saymyname/CUTOVER_AND_M6_ROLLBACK.md`.

## Factory CI cost and the Actions quota (af-mzuprx)

Intent (Benjamin, his words, 2026-10-08): « il faut que l'usine consomme
moins de minute github action »
Mechanism (agent interpretation): measure where the minutes go, cut the
largest avoidable shares, leave the merge gate as it is. It does not mean
fewer tests, a merge without CI, or a runner on the host.

`saymyname-app/agent-factory` is private: every minute of a GitHub runner is
billed, each job rounded up to the minute. On 2026-10-08 the organization
reached 100% of its included minutes: from 02:37 (Paris) every job ended
"not started because recent account payments have failed or your spending
limit needs to be increased" and no pull request could merge until Benjamin
raised the spending limit.

**Read the figure:** `./bin/ci-minutes` (billed minutes per day and per run,
read-only). The quota left and the amount billed are only on the
organization's GitHub usage page: the billing API wants an `admin:org` token
the Factory does not hold, and the run `timing` API answers 0.

### What was measured (Paris days)

| When | Runs | Billed minutes | Merged PRs | Minutes per merged PR | One green run |
|---|---|---|---|---|---|
| 2026-10-06 | 104 | 991 | 35 | 28 | 7 min (morning) to 19 min (night) |
| 2026-10-07 | 46 | 1,546 | 13 | 119 | 16 min (01:00) to 50 min (20:00) |
| 2026-10-08, before this change | | | | about 230 (same mix of runs as 10-07) | 63 to 72 min, green after 18 to 20 min |
| 2026-10-08, after (runs of PR #437) | | | | about 100 (same mix) | 50 min, green after 15 min |
| 2026-10-08, measured (the whole day) | 70 | 2,656 | 31 | 86 | 43 to 49 min from 15:07; billed nothing from 19:07 (the host's own runner) |

On 2026-10-07 a merged pull request cost 3.5 runs: 2.5 on the pull request
(a branch is often pushed twice in a minute, then caught up with `main`) and
one on `push` after the merge. After the change it costs the 2.5 pull request
runs at 50 minutes, less the replaced runs that are now cancelled: a little
over half less.

Measured on 2026-10-08 instead of projected (runs started and pull requests
merged in each window): 123 billed minutes per merged pull request until
13:56 (2,218 minutes, 18 merged), then 63 from 13:56 to 19:07 (438 minutes,
7 merged), once reduced runs (af-5mw6z0) and cheaper tests (af-xhryl7, on
`main` at 15:50) were in. The morning stayed above the projection of about
100: a full run went from 50 to 59-69 minutes when tests were merged and the
lots went uneven, and three sessions pushed CI changes run after run. No
full day exists with these changes on GitHub's runners: from 19:07 Factory
CI runs on the host's own runner and is billed nothing ("Factory CI on the
host's own runner" below), so that window of 7 pull requests is all there is.

| Cause | Measured share | What was done |
|---|---|---|
| The run on `push` to `main` repeated the pull request's run. The ruleset requires a branch up to date with `main`, so that run had already tested the tree the merge puts on `main`; nothing read the second one (`bin/deliver-close` and `bin/pr-autopilot` read `pull_request` runs). | 30% of all minutes (331 of 991, 453 of 1,546) | No run on `push`. `workflow_dispatch` starts one on `main` by hand. |
| A run on a commit already replaced by a newer one kept going. | 16% of pull request minutes on 10-06, 30% on 10-07 | One `concurrency` group per pull request, `cancel-in-progress`. |
| Each runner ran one test file at a time on its two cores. | Two files at once need 1.3 to 1.4 times fewer runner seconds, not 2: two long files side by side slow each other (`ticket-evaluation-test.py`: 481 s next to short files, 824 s next to `code-review-test.py`). | `bin/ci-run-tests --jobs "$(nproc)"`. |
| The lots were dealt by file size, which does not follow duration (`spec-integration-test.py`: 908 lines, 628 s; `convoy-state-test.py`: 2,978 lines, 273 s). The job named `Tests` is billed while it waits for the longest lot. | 8 to 11 minutes of waiting per run with four lots by size; 12 with two | Lots dealt by the seconds each file took in a real run: `config/ci-test-seconds.tsv`, written by `./bin/ci-test-seconds`. Still 6 minutes of waiting on the first run: runners are not equally fast. |
| The tests themselves grew: 391 s of test time on 10-06 at 03:00, 3,284 s on 10-08 at 01:40. Fourteen files of the new delivery flow (`ticket-evaluation`, `spec-integration`, `convoy-advance`, `convoy-state`, `code-review`, `correction-round`, ...) are 88% of it. One of them, `tests/convoy-state-test.py`, starts 5,404 Python processes (2,013 calls of `bin/convoy-state`, 3,391 of the fake `gc`), 40 to 90 ms each. | The reason a run went from 7 to 65 minutes | Each line of `bin/ci-run-tests` ends with the seconds the file took, so the next growth is visible in the job log. Since af-xhryl7 each start costs less, with every assertion kept: the code of `bin/convoy-state` is the module `lib/convoy_state.py` (Python compiles a program given by path on every start and keeps the compiled form only of what it imports), `bin/evidence-capture` loads its HTTP client only for a screenshot, and the fake `gc` of the tests starts without `site`. Measured on the host, the fourteen files four at once: 3,289 s of processor time before, 2,006 s after; another battery ran during part of the first pass, so the gain is between 23% (`tests/convoy-state-test.py` alone, old and new side by side) and 39%. Billed on GitHub's runners: a full run went from 59 to 69 minutes (62 at 15:02) to 43 to 49 (six complete runs from 15:07 to 18:18), 23 to 31% less than the run of the same hour. Still the largest share: about 1% of the processes of a file are the tool it tests, the rest builds a finished ticket again for every test. |
| A change to docs only ran every test. | 4 of 51 merged PRs | Since af-5mw6z0 it runs without the long tests, which do not read the docs; the tests that do (catalogues, registration, prompts) are short and still run. See "Long tests left out" below. |

Since af-97io9q (2026-10-09) the finished ticket a suite asks
`tests/lib/ticket_proofs.py` for is walked through the real tools once per
distinct request and per test process, and copied afterwards: 230 requests
for 32 distinct ones in the four files that use it most. Measured side by
side on a loaded host: 1,297 s before, 870 s after (-33%), no test file
changed. What that measure also showed: one long file starts about 14,000
Python processes, each near its floor (11 ms for the fake `gc`, 40 ms for
`bin/convoy-state`); `bin/convoy-advance` and the simulated deliveries of
the oracle have no step to shorten, only fewer processes would
(af-9wznku, to be planned).

`tests/ci-workflow-cost-test.sh` fails if the workflow runs on `push` again,
stops cancelling a replaced run, or stops using every core.

### Long tests left out when the change cannot reach them (af-5mw6z0)

Intent (Benjamin, his words, 2026-10-08): « y'a pas moyen aussi de ne pas
tester toute l'usine comme ça à chaque fois ? »
Mechanism (agent interpretation): Factory CI still runs on every pull
request and `Tests` is still the required check; inside it the long tests
are left out only when every changed file is in an area they cannot reach.
It does not mean a merge without CI, a selection guessed from file names, or
a test left out when the selection is unsure: unsure is a full run.

| Question | Answer |
|---|---|
| Which tests are the long tests? | The files `config/ci-test-seconds.tsv` gives 30 seconds or more, less those that are themselves in an area or carry a `# ci: every-run — <reason>` line: 18 files, 4,412 of the 4,836 test seconds of a run (91%), all of the new delivery flow. The other files (about 130, 424 s) run on every pull request. |
| Which areas? | The closed list `config/ci-long-test-blind-areas.txt`: `docs/`, `lib/cockpit/`, `bin/cockpit*`, `tests/cockpit-*`, `tests/fixtures/cockpit/`. 38 of the last 100 merged pull requests changed nothing else (measured 2026-10-08). |
| When is a run reduced? | A `pull_request` run whose merge commit differs from its first parent (`main`) only by files of those areas (`bin/ci-run-tests --changed-since 'HEAD^1'`). |
| When is it a full run? | One changed file outside the list (the list itself, a test, a tool the Cockpit calls such as `bin/proposal-door` or `bin/convoy-state`), a file moved into or out of an area, no changed file, a commit that cannot be read, uncommitted changes, a run started by hand, the switch below. The battery run by hand and the main-landing gate pass no `--changed-since`: always full. |
| What does the run say? | Every lot starts with `ci-run-tests: 18 long test(s) NOT run: ...` and one `not run: tests/x (824s ...)` line per test, or with `ci-run-tests: full run: <file> changed, and it is outside the areas ...`. |
| How is an area held instead of believed? | Whenever a long test runs, it runs in its own mount namespace (`bwrap`) where each area is a private copy with the same content, on a tmpfs no other process has; afterwards an entry of the copy whose access time moved was opened or listed by that test or by a process it started, and the test fails with the paths. A pull request that makes a long test depend on an area changes that test or a tool, so its own run is full and fails. A long test that has to read an area stays in every run with a `# ci: every-run — <reason>` line: `tests/evidence-capture-test.py` (66 s) asks Git for the state of the whole repository. |
| What does that not see? | A path only tested for existence, and content read through Git objects (`git show`, `git ls-files`) instead of the files. |

**Force a full run:**

- every run: set `CI_RUN_TESTS_FULL: '1'` in `.github/workflows/ci.yml`
  (the one switch back), or empty the list of areas;
- one branch, by hand: `gh workflow run ci.yml --ref <branch>` (full, but it
  is not the `pull_request` run the ruleset reads);
- locally: `bin/ci-run-tests --jobs 4` is always full;
  `bin/ci-run-tests --jobs 4 --changed-since origin/main` is the reduced one.

No full run is scheduled on `main`: about six in ten pull requests run
everything, and the one change that could make a reduced run wrong (a long
test that starts reading an area) cannot come from a reduced run. A daily
run would cost about 50 billed minutes a day: Benjamin's decision (spend).

`bin/ci-test-seconds` keeps the seconds of a test the run it reads did not
execute: read from a reduced run alone, the long tests would look unmeasured,
stop being long tests, and run on every pull request again.
`tests/ci-run-tests-selection-test.sh` proves the selection (a change
outside the list runs everything, any doubt too) and the blindfold (a long
test that opens or lists an area fails the run).

Measured 2026-10-08 (`./bin/ci-minutes`, Paris times):

| Run | Billed minutes |
|---|---|
| Full run before the change (06:49 to 07:17) | 46 to 52 |
| Full run with the blindfold on, the two runs of pull request #441 (07:24, 08:42) | 50 and 47: the blindfold costs nothing measurable, and its nested namespaces start on a GitHub runner |
| First reduced run, pull request #450 (docs only, 13:56): 18 long tests not run | 9 (`Tests` 3, each of the three other lots 2): 82 to 86% less than a full run of the same day |
| Full run from 11:18, after the tests merged that day | 59 to 69: one lot at 20 minutes against 9 to 15 for the others, `config/ci-test-seconds.tsv` is stale ("Keeping the lots even" below) |

38 of the last 100 merged pull requests stay inside the areas, so about 30%
fewer billed minutes per merged pull request were expected overall. Measured
from 13:56 to 19:07 on 2026-10-08: 2 of the 7 merged pull requests ran
reduced, 17 billed minutes together instead of about 120. That is about half
of what the window saved; the other half is the cheaper full run
(af-xhryl7). One afternoon, not a full day: since 19:07 the runs are on the
host's own runner, where a reduced run saves host time, not billed minutes.

Adding an area: a place pull requests often change alone, one line in the
list; the pull request that adds it is a full run and says at once whether a
long test reads it.

### Keeping the lots even

A lot costs about one billed minute of setup and rounding; uneven lots cost
more, because `Tests` waits. When its "Wait for the other lots" step waited
more than 3 minutes it prints a warning in the run. Then, from a work tree:

```bash
./bin/ci-test-seconds          # rewrites config/ci-test-seconds.tsv from the latest green run
```

and land the file through a pull request. A file the list does not name is
weighed by its size, and a stale list changes only the balance, never which
files run (`tests/ci-test-seconds-test.sh`).

### What did not change

The job named `Tests` is still the one status check ruleset
`AF-main-protection` requires and `bin/pr-autopilot` waits on. It exists from
the first second of a run and is green only when its own lot and every other
lot passed, on a reduced run as on a full one. A cancelled run belongs to a commit that is no longer the head of
its pull request, so it could not have let anything merge.

### When the quota is reached

Signs: every job of every run fails within seconds with the sentence quoted
above, `./bin/ci-minutes` shows runs at 0 minutes, open pull requests stay
unmerged with a red `Tests`.

1. It is not a test failure: do not re-run, do not retry in a loop, do not
   merge around the check.
2. Only Benjamin can lift it (spend): the spending limit or the plan, on the
   organization's billing page. Raise it to him through
   `./bin/escalation-door`, with the day's figure from `./bin/ci-minutes`.
3. Once runs start again, re-run the failed runs of the open pull requests
   (`gh run rerun <id> --failed`); `bin/pr-autopilot` then merges them as
   usual.
4. The included minutes come back at the start of the billing month.

Benjamin's decisions, never taken by an agent: making the repository public
(free minutes, public code), a paid plan, the spending limit. The
self-hosted runner on the WSL host was his decision of 2026-10-08: "Factory
CI on the host's own runner" below.

## Factory CI on the host's own runner (af-r1ymfm)

Intent (Benjamin, his words, 2026-10-08): « Je suis aussi ok pour mettre test
sur pc aussi », then « runner sur le pc d'abord alors on oublie le repo
public et oauth les secrets etc, pour le moment. »
Mechanism (agent interpretation): the repository stays private and the jobs
of Factory CI run on a self-hosted runner of the WSL host, so they are not
billed; the job named `Tests` is still the one required check. It does not
mean a runner on a public repository, pull request code running as the
operator, or a PC he cannot use while CI runs.

What he chose on 2026-10-08, each among options put to him in the live chat:

| Question | His choice | How it is held |
|---|---|---|
| The runner is down while the Factory runs | The pull request waits; switching back to GitHub's billed runners is one command, by hand | `bin/factory-doctor` reports the runner down; `./bin/ci-runner mode github` |
| Share of the PC | 4 cores (8 since 2026-10-09, "The job's cores" below), 4 GB, one job at a time, low priority; pause and resume in his hand, no automatic game detection | The limits of `factory-ci-runner.service`; `./bin/ci-runner pause` and `resume` |
| Where pull request code runs | An ephemeral container per job, started by a dedicated unprivileged user, rootless Podman (not Docker Desktop) | `config/ci-runner/runner-loop`; `docs/SECURITY.md`, same title |
| Root in WSL (`sudo` asks a password, `wsl -u root` does not) | Three gestures: Podman, the user, the service | `config/ci-runner/root-install` |

### How it runs

| Piece | Runs as | What it does |
|---|---|---|
| `factory-ci-runner.service` (system service, `config/ci-runner/runner-loop`) | `factory-ci`: no password, no shell, no sudo, no group but its own | Waits for a one-job runner configuration, starts a rootless container, lets GitHub's runner serve one job in it, throws the container away, starts again. Rebuilds the image (`config/ci-runner/Containerfile`) every 7 days, between 05:00 and 07:00, with the latest runner of GitHub and the system's fixes ("While the image is built", below). |
| `factory-ci-runner-broker.service` (user service, `bin/ci-runner broker`) | the operator | Each time the runner's loop is free, asks GitHub for one just-in-time runner (it serves one job, then GitHub forgets it) and writes its configuration on the pipe `/run/factory-ci-runner/handoff`. The operator's token never reaches the runner's user; the configuration is never printed, logged or stored. |
| `.github/workflows/ci.yml` | | Goes to the label `factory-ci` only when the repository variable `FACTORY_CI_RUNNER` is `self-hosted`; without it, GitHub's runners as before. On the host the run is one lot, `Tests` alone: the runner takes one job at a time, and four lots would wait on each other for ever. Its first step there is `config/ci-runner/isolation-probe.sh`. |

The image holds what the workflow installs on a GitHub runner (Python 3.12
with PyYAML 6.0.2, bubblewrap, Node.js 22 in `/usr/local/bin`, `gh`, `jq`)
and no sudo. The long tests' nested `bwrap` starts in it with Podman's
default rights: nothing is widened for it.

### Read the state

```bash
./bin/ci-runner status      # the services, where runs go, the runner at GitHub, runs waiting for a runner
./bin/factory-doctor        # "ci-runner" is ACTIONABLE when the runner is down
journalctl -u factory-ci-runner.service -n 50          # the runner's loop
journalctl --user -u factory-ci-runner-broker -n 50    # the hand-off
./bin/ci-minutes --runs 5   # a run on the host is 0 billed minute
```

### Pause for a game, resume

```bash
./bin/ci-runner pause        # a job that runs ends by itself, a runner that only waits is stopped, no new job starts
./bin/ci-runner pause --now  # also kills the running job: its run ends red
./bin/ci-runner resume
```

Paused, pull requests wait with `Tests` "queued"; `bin/factory-doctor` lists
the pause as ADVISORY and nobody resumes it for the operator. After
`pause --now`, re-run the killed run: `gh run rerun <id> --failed`. A pause
does not survive a restart of WSL.

### When the runner is down

Signs: pull requests stay open with `Tests` waiting for a runner;
`./bin/ci-runner status` and `bin/factory-doctor` say which half is down.

| What is down | Who repairs | How |
|---|---|---|
| The broker (user service) | Any operator session | `systemctl --user restart factory-ci-runner-broker`, then its journal. "GitHub gave no runner configuration" is the token, the network or GitHub. |
| The service (system service) | Root: ADMIN | `journalctl -u factory-ci-runner.service -n 50`; from Windows `wsl -d Ubuntu-24.04 -u root -- systemctl restart factory-ci-runner.service`. It restarts by itself after a failure and starts with WSL. |
| No image and none can be built | Nobody: it retries every minute | The journal names the step (the network, most often). |
| The PC is off or asleep | Nobody | The Factory is on the same PC: no pull request is produced either. GitHub drops a job that waited 24 hours; re-run it. |

Going back to GitHub's billed runners is spend, so it is Benjamin's call and
never automatic: `./bin/ci-runner mode github`, then for each run already
waiting `gh run cancel <id>` and `gh run rerun <id>`. `./bin/ci-runner mode
self-hosted` comes back. The Actions budget is capped (20 dollars, his words,
2026-10-08): "When the quota is reached" above still applies to that mode.

### A battery by hand and a CI job at the same time

A job does not wait behind a battery started by hand, and a battery does not
wait behind a job (`bin/ci-run-tests` skips the host's lock under
`GITHUB_ACTIONS`, and the job's `/tmp` is not the host's). What bounds the
sum is the service: 8 named cores and 4 GB for the job whatever else runs,
at a lower priority than the Factory and the batteries.

### The job's cores: 8 of the 20 WSL sees (af-guzs0o)

The share of the PC: the job may take 8 of the 20 processors WSL sees
(`nproc` on the host: 20; the PC has 24, and Windows keeps 4). WSL saw 12
until 2026-10-09, 17:50 Paris (`processors=` in the Windows user's
`.wslconfig`, 12 then 20): the measures below dated before that hour were
taken on 12, and say so. The job's own share did not change with it.

Intent (Benjamin, his words, 2026-10-09, about 01:45 Paris): « Ok pour plus
de coeurs », in answer to "plus de coeurs pour la CI (4 -> 8) [...] C'est ta
décision (part du PC)".
Mechanism (agent interpretation): the job gets 8 named cores instead of 4
(the figure shown to him; he named none himself) and runs eight test files
at once (`--jobs "$(nproc)"`). It does not mean more than one job at a time,
another priority, more memory (4 GB still), a change of the merge gate, or
automatic game detection.

| Where the figure lives | What |
|---|---|
| `config/ci-runner/factory-ci-runner.service` | `AllowedCPUs=4-11` |
| `config/ci-runner/isolation-probe.sh` | fails the run when the job sees more than 8 cores |
| `tests/ci-runner-test.sh` | holds both |

The service runs its installed copy: the figure changes on the host at the
root install ("Install, stop, remove" below), not at the merge. Back to 4:
`AllowedCPUs=8-11` in the service file and the test, through a pull request,
then the root install again.

Measured 2026-10-09 (Paris times), two full runs of the same 161 tests the
same night, the Factory delivering beside them (no battery by hand):

| What | 4 cores (pull request #469, 02:58 to 03:25) | 8 cores (run 37872828394 on `main`, 04:04 to 04:24) |
|---|---|---|
| The job | 27 min 11 s | 19 min 43 s: 27% less, not the half that was estimated |
| Load of the host (1-minute load, 12 cores) | 13.4 on average, 21.1 at most | 14.6 on average, 23.1 at most; 14.7 on average over the 20 minutes before the run |
| Memory of the job (sampled every 15 s; the control group's own peak) | 0.66 GB | 0.79 GB sampled, 0.97 GB peak, of its 4 GB: the limit stays (Benjamin, his words, 2026-10-09: « ok, on laisse 4 Go ») |
| Orders of the Factory that failed during the run | none; one, `escalation-door-sweep`, during the next 4-core run (03:36, load 25) | one: `escalation-door-sweep` at 04:07, "context deadline exceeded" |
| The isolation probe | 4 cores seen | 8 cores seen, every attempt refused |

Why not half: the run cannot be shorter than its longest file, and the long
files slow each other. On 8 cores `tests/convoy-advance-test.py` took 923 s
of the job's 1,183 s, `tests/fixture-city-oracle-test.py` 796 s; four more
took 400 to 600 s. More cores no longer help until those files are cheaper
or cut in two (af-97io9q). The 15 min 23 s of 2026-10-08 is not the
reference any more: on the same 4 cores a full run took 25 to 32 minutes on
the night of 2026-10-09, with six more tests and a busier Factory.

The failed order is not the cores: `escalation-door-sweep` (60 s to answer,
every 15 minutes) failed five times in the 12 hours before 04:30, once
before the host's runner existed (2026-10-08 16:52) and three times during
runs on 4 cores. It fails when the host is loaded, whatever loads it. The
cause was the sweep itself (af-io8tb7): it read again, one `gc bd show`
each, every bead that ever carried a Mayor-first escalation, settled ones
included (25 on 2026-10-09: 32 s for nothing due on an idle host, half its
60 s before any load). It now reads one list, then only the escalations
still pending.

What the PC feels during a run: for about 20 minutes, 8 of the 20
processors WSL sees (12 when this was measured; the PC has 24) can be busy with the job at low priority (cores 4 to 11; 0 to 3 are never the
job's), instead of 4 for about 27 minutes. Nothing was measured with a game
running: `./bin/ci-runner pause` before one, as before.

### Measured 2026-10-08 (pull request #457, Paris times)

| What | Measure |
|---|---|
| First full run on the host, 18:04 to 18:20 | 155 tests green in 15 min 23 s on 4 cores; billed 0 (`./bin/ci-minutes`: "on the host: 16 min, not billed"). A full run on GitHub's runners that day: 43 to 48 billed minutes. `ci-minutes` applies GitHub's rule (a self-hosted runner is not billed); the amount billed itself is only on the organization's usage page. |
| Load of the host (1-minute load, 12 cores), the Factory running | 7.7 on average over the 20 minutes before the run, 11.6 during it, 15.7 at most |
| Memory of the job (sampled every 15 s) | 1.2 GB at most of its 4 GB; 1.9 GB while the image is built |
| Orders of the Factory that failed during the run | none (`gc events --type order.failed`) |
| The isolation probe | every attempt refused, 4 cores seen. The very first job (17:58) failed on it for a false reason, the base image's own empty `/home/ubuntu`, since removed from the image |
| Runner paused, then a push (18:42) | `Tests` "queued", `ci-runner status`: "waiting for a runner since 18:42", `factory-doctor`: ADVISORY "the operator paused the runner" |
| `mode github`, `gh run cancel`, `gh run rerun` (18:44) | the same run started on `ubuntu-latest`, four lots, 30 s later; cancelled at once |
| `mode self-hosted`, `resume` | a runner online and idle again within 20 s |
| Building the image | about 2 minutes, once a week and after an install that changes its recipe; calls of `wsl.exe` hang meanwhile (below) |

### While the image is built, calls of `wsl.exe` from Windows hang (af-uw246a)

Intent (Benjamin, his words, 2026-10-08): « Je suis aussi ok pour mettre test
sur pc aussi » -- and, from the mechanism recorded with it above, not a PC he
cannot use while CI runs.
Intent (Benjamin, his words, 2026-10-09): « ok pour ta reco, fenêtre
05:00-7:00 , réinstallation root au bon moment », the recommendation being
the weekly build kept to night hours, and allowed at any hour past 14 days.
Mechanism (agent interpretation): know why a build of the image freezes his
sessions, build it as seldom as possible, and keep the weekly build to hours
when he is not at the PC. It does not mean a changed kernel setting of the
guest, a wider share of the PC for the build, or a Factory that pauses at
night: inside WSL nothing waits on a build.

What you see: once or twice per build, for about 30 s each time, every new
call of `wsl.exe` from Windows waits (an operator session, a terminal), and
one of them fails with `Wsl/Service/0x8007274c`. Inside WSL nothing stops:
the Factory, its orders and the processes already started go on.

| Link of the chain | Seen |
|---|---|
| Each new call of `wsl.exe` opens a Hyper-V socket to the guest, and the guest's kernel needs one free block of 512 KB in one piece for it | `vmbus_alloc_ring` under `hvs_probe`, an allocation of order 7 (kernel 6.18.33.2-microsoft-standard-WSL2) |
| A build writes about 1.5 GB of layers through the disk cache in two minutes | The guest still has 100 to 700 MB free, but in pieces of 256 KB or less: no block of 512 KB for 2 to 24 seconds of a build (`/proc/buddyinfo`, every second) |
| The allocation fails | `journalctl -k`: `kworker: page allocation failure: order:7`; the socket is not opened and `wsl.exe` gives up after 30 s |
| Windows serves the calls one after the other | Every call started behind the failed one waits for its 30 s, then answers |

It is the build, not the service: the same recipe built by the operator's own
rootless Podman, outside every limit of the service, does it too. It is not
one step either: the end of the `apt-get install` layer, Node.js unpacked,
GitHub's runner unpacked. The allocation is the WSL kernel's (third party):
nothing of ours to repair there. Since the boot of 2026-10-07 the kernel
journal holds this failure at the builds of the image and at 06:00 to 06:22
on 2026-10-08 (three batteries at once: `docs/DELIVERY.md`, "One battery at a
time on the host"), and at no other time -- not during a CI job, not during
one battery.

Measured 2026-10-08, 21:48 to 23:48 (Paris), the Factory running: the same
build by the operator's Podman, a call of `wsl -d Ubuntu-24.04 -u benja -e
true` every 4 s, each timed on its own (0.12 to 0.3 s when all is well):

| Build | Seconds with no block of 512 KB | Failed allocations | Calls of `wsl.exe` |
|---|---|---|---|
| As the service builds it | 24 | 4 | 2 failed after 30 s, 14 waited behind them: two hangs of 30 s |
| Podman's own processes held to 512 MB (`MemoryHigh` on their unit; the build's steps were outside it) | 2 | 0 | none over 1.1 s |
| `vm.compaction_proactiveness` 0 -> 100 | 18 | 4 | 4 failed, 27 waited: a hang of 2 minutes |
| `vm.min_free_kbytes` 45056 -> 262144 and `vm.watermark_scale_factor` 10 -> 200 | 7 | 1 | 1 failed, 7 waited: one hang of 30 s |

No kernel setting removed the hang, so none is kept: the three are back to
the guest's own values (root, with Benjamin's word for that test, 2026-10-08).
The ceiling on memory is the one lever that worked, measured once and outside
the service; inside it, it needs a control group of its own under the
service's and is not built.

What holds today (`config/ci-runner/runner-loop`):

| The image is built when | At what hour |
|---|---|
| It is older than 7 days | Between 05:00 and 07:00 on the host's clock (`BUILD_HOURS`). A runner that only waits for a job is stopped for the build; one that serves a job is never stopped, the build follows the job if the hour still holds |
| It is older than 14 days (the PC was off those nights) | Any |
| Its recipe changed (`Containerfile`, `entrypoint.sh`) | At the install, whatever the hour: the operator is there. `root-install` leaves an unchanged recipe its date, so installing a new `runner-loop` or service file builds nothing |
| There is none | At once |

A job is killed 2 hours after the runner took it (`JOB_MAX_SECONDS`, seen
within a minute); the wait for a job does not count (af-rqovxb). The loop
tells the two apart by one process, `Runner.Worker`, which GitHub's runner
starts for a job only; it looks for it by name (`pgrep -x`), since a look by
command line matched the shell that ran it and every runner read as serving a
job (af-7i1q2r).

A build that fails is tried again an hour later; the old image serves
meanwhile. A waiting runner stopped at the very second GitHub hands it a job
would end that run red: re-run it (`gh run rerun <id> --failed`). To tell this from a guest that is down: `uptime` inside WSL is
unchanged, and

```bash
journalctl -k --since -10min | grep -c 'page allocation failure: order:7'
journalctl -u factory-ci-runner.service --since -10min | grep 'building the image'
```

### Install, stop, remove

Install (ADMIN, once; from a checkout of `main`):

```bash
# from Windows, as root in WSL: Podman, the user factory-ci, the service
wsl -d Ubuntu-24.04 -u root -- /home/benja/agent-factory/config/ci-runner/root-install install benja
# as the operator, from the live root: the broker, then send CI to the host
./bin/ci-runner install
./bin/ci-runner mode self-hosted
```

The operator's token must be admin of the repository (it asks for the
just-in-time runners). After a change to `config/ci-runner/` or to
`bin/ci-runner` has merged, run the same two installs again: the service
runs the copy in `/usr/local/lib/factory-ci-runner`, not the checkout. The
image is built again only when `Containerfile` or `entrypoint.sh` changed.

Stop without removing: `./bin/ci-runner pause` (above), or `./bin/ci-runner
mode github` to keep CI running elsewhere.

Remove:

```bash
./bin/ci-runner remove      # CI back to GitHub's runners, the broker, the runners registered at GitHub
wsl -d Ubuntu-24.04 -u root -- /home/benja/agent-factory/config/ci-runner/root-install remove
```

The second line removes the service and the user `factory-ci` with its
images; Podman itself stays (`apt-get remove podman`, root). The runner must
be removed before this repository ever becomes public (af-5vjm1h): on a
public repository anyone could run code on the PC through a pull request.

`tests/ci-runner-test.sh` holds the variable, the single lot, the limits of
the service, the container's options, the hand-off and the hours of the
weekly build;
`config/ci-runner/isolation-probe.sh` proves the box on every run.

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
