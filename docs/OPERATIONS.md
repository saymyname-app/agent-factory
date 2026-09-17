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

## Human Factory cockpit

The default one-glance view is the Factory-owned human cockpit:

```bash
cd ~/agent-factory
./bin/factory-cockpit open
./bin/factory-cockpit status
./bin/factory-cockpit snapshot | jq .
./bin/factory-cockpit phone-enable
./bin/factory-cockpit phone-status
./bin/factory-cockpit stop
```

It serves `http://127.0.0.1:8383` from a small Python standard-library process.
`open` starts it if necessary and opens the Windows default browser. The UI polls
a five-second cache of local `gc`, `bd`, workflow API, and product-queue signals.
Monitoring, search, filters, advice, tooltips, glossary, and copied summaries call
no model. There is no auto-refresh pause control today (docs drift, audit
2026-09-17): **Actualiser** is the only refresh, and it is always manual.
The one-glance state follows `agent-factory-human-state/v1` (schema in
`config/factory-human-status.schema.json`). It always separates infrastructure
health, delivery activity, result lifecycle and resume semantics. A healthy
controller may therefore coexist with no active delivery and a manual optional
launch action. Source disagreement degrades health and neutralizes resume advice
instead of being rendered as idle or as an empty queue.

When the Mayor-owned campaign is active, the same contract also exposes its
persistent state, continuation condition, owner, exact action, blocker kind and
notification idempotency. A blocked campaign is rendered as `BLOQUÉ` both in the
global navigation and on Today. This signal does not turn the cockpit into a
control surface: only the guarded CLI and the Mayor may change campaign lifecycle.

Progress is semantic and evidence-based: completed workflow steps, the current
phase, elapsed wall time, and age of the latest source signal. A session marked
active is not by itself presented as productive work. When sources disagree or
fail, the UI reports partial visibility. Infrastructure such as the deterministic
control dispatcher is collapsed under technical details by default.

Navigation prioritizes Today, Product graphs and source content, Roadmap,
Product/Project Decisions, PO, then the delivery Board. Enterprise and technical
Workflow/Agents/Tokens views remain directly accessible under `More / Factory`.
Enterprise decisions are collapsed by default and may be individually or wholly
ignored through a reversible browser-local preference. Ignore changes no Git or
Beads state and never edits, closes or resolves the durable decision.

Product references open actual configured Markdown sections as inert headings,
paragraphs, lists, tables, code and safe links. A table of contents, stable deep
links and search provide quick navigation; configured path, file modification
time and SHA-256 provenance make freshness explicit. Only schema-v2 allowlisted
repository sources are readable. Missing/empty sections, parse errors, traversal,
external files, unsafe links and active content fail visibly without fallback
content. Capability and journey nodes link to these sources, roadmap outcomes and
decisions; decision pages show the reverse relationships.

The Roadmap combines durable V1 outcomes, exact last-delivery PR/CI evidence,
the current immutable outcome, eligible-unscheduled and evidence-paused candidates, decision
gates and the separate Factory campaign. Under explicit RECORD interaction it
can add a candidate with what/why/acceptance, move it to an exact position, set
urgency independently, pause with reason, resume, and cancel after confirmation.
Keyboard/mobile buttons are the primary reorder mechanism. Success rereads Beads
and refreshes roadmap/capability projections immediately; lock, conflict,
confirmation, rollback and recovery states remain visible. The bridge delegates
only to `bin/saymyname-product-queue` and exposes no materialize, dispatch,
interrupt, arbitrary-command or merge path.

The Today attention card separates all open general decisions from effective
blockers explicitly projected by coordination. It preserves the exact
`gc.needs_benjamin` text and exposes a native keyboard-accessible action only
when the configured work reference resolves to exactly one open durable
decision; that action opens the decision's existing dedicated workspace in the
same cockpit. An unresolved target remains plain text and is never activatable.
This navigation creates no route, tab, session, or model call. Opening the
Roadmap resolves exact delivery evidence on demand through the existing
`bin/saymyname-product-status` contract, while an unavailable proof remains
explicit instead of being inferred from the live projection.

The product-work view queries product-marked Beads across the City and registered
rigs, then removes sessions, workflows, convoys, gates, synthetic work, order
tracking, and maintenance. Beads states what should be done, Gas City states who
is executing it, and GitHub/CI proves delivery. An empty product queue does not
stop infrastructure or current work, but no next product result can start.

The **Parler au Mayor** and **Mon PO** panels are the only write capabilities.
A typed and explicit Mayor send uses `gc session submit mayor`; a typed and
explicit PO send starts or resumes a local authenticated Codex session in the
configured product workspace. Both may consume model tokens. The PO supports
DISCUSS (no durable mutation) and RECORD (persist only the specifically approved
decision). EXECUTE is handed once to the Mayor: the PO never becomes a second
delivery orchestrator. Advice buttons only prefill text. The server never exposes
interrupt, dispatch, retry, merge, or recovery controls; it requires same-origin
bounded JSON, a purpose-specific confirmation header, and a five-second send
interval. Conversation views contain only cockpit-origin exchanges and never
expose system prompts or hidden reasoning.

The listener remains loopback-only. `phone-enable` configures a dedicated
Tailscale Serve HTTPS endpoint on port `8443`, reachable only by devices in
Benjamin's tailnet, while preserving the existing Gas City mapping on port 443.
It never enables Tailscale Funnel or binds the cockpit to the LAN. Do not publish
port `8383` or replace this private endpoint with public exposure without a new
security review. Runtime PID/log state is under
`${XDG_RUNTIME_DIR:-/tmp}/agent-factory-cockpit-<uid>-8383` and contains no
credentials or transcripts.

If startup fails, inspect the exact log path printed by the lifecycle command,
check `python3`, `curl`, port `8383`, and then run `./bin/factory-cockpit restart`.
Stopping the cockpit does not stop Gas City or its agents. Its HTTP surface is:

- `GET /api/snapshot`: deterministic monitoring snapshot;
- `GET /api/mayor/conversation`: recent cockpit-origin Mayor exchange;
- `GET /api/item?store=<store>&id=<bead>`: bounded Bead detail loaded on click;
- `GET /api/agent?id=<session>`: active session messages and sanitized local
  activity loaded on click; hidden reasoning is not exposed;
- `GET /api/tokens`: on-demand local provider counters, including exact scope
  and confidence labels; this read makes zero model calls;
- `GET /api/po/conversation?decision_id=<id>`: the persistent workspace for one decision, without creating a session;
- `GET /api/po/conversation?key=<key>`: one general PO discussion plus the conversation index;
- `POST /api/mayor/message`: explicit bounded human message to the Mayor;
- `POST /api/po/message`: explicit DISCUSS or RECORD message; first send creates the selected decision thread;
- `POST /api/po/new`: prepare a fresh general workspace without creating a model session;
- `GET /api/preview/status`: zero-model-call preview health and exact repository SHAs;
- `POST /api/preview/action`: guarded `start`, `restart`, or `stop` through `bin/saymyname-preview`.
- `GET /api/reference?id=<configured-id>`: allowlisted structured Markdown with
  contents anchors and freshness provenance;
- `GET /api/delivery-evidence`: on-demand exact last-delivery evidence through
  `bin/saymyname-product-status` (Beads, Gas City and GitHub), with zero model calls;
- `POST /api/product-queue`: same-origin, `human-queue-record` confirmed RECORD
  action limited to add/move/urgency/pause/resume/confirmed cancel.

## Detailed Gas City dashboard

Gas City `1.4.1` embeds its detailed dashboard SPA in the supervisor and serves
the UI and API from the same origin. Use it for engineering detail; the human
cockpit above is a separate read-only projection. In this City the Gas City URL is:

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

### Deterministic product status

From the canonical Factory checkout, print one product-oriented SayMyName
snapshot with:

```bash
cd ~/agent-factory
./bin/saymyname-product-status
```

The command is a read-only L0 projection. `--json` emits the canonical
`agent-factory-human-state/v1` contract; the default French text is only its
human rendering plus exact delivery evidence. It reads coordination pointers
from parent Bead `af-1vr4` (`gc.current_jit`, `gc.last_delivered`,
`gc.next_outcome`, `gc.needs_benjamin`, and any explicit resume policy). It
also reads the live product-queue projection and fails closed unless
`gc.next_outcome` identifies the same first eligible product candidate. A
`goal=none` Factory campaign never counts as `NEXT`. It resolves the referenced current
and delivered Beads through prefix-aware `gc bd` routing, so an outcome may be
attached to a durable product goal or stored in an application rig rather than
being a direct child of `af-1vr4`. It derives an active delivery phase from the
current Beads workflow and prints a current agent only when `gc status --json`
confirms that workflow's exact session is running. For the last delivery, it
requires `gc.github_repo` in `owner/repository` form and passes that repository
to `gh pr view` while validating the PR number, head SHA, merge SHA, merged
state, and check rollup. An empty rollup is reported as `CI not configured`,
never as green. The output is emitted only after every required source agrees.

Health uses `ok`, `running`, `health.usable`, and `health.degraded` independently
from delivery activity. Resume is automatic only for an active delivery or when
durable coordination explicitly configures an automatic dependency/campaign and
its condition. Otherwise an idle eligible candidate is “Éligible · non
programmé”; Benjamin may optionally ask “Lance le prochain résultat”. This is
not a blocking `NEEDS BENJAMIN` decision.

The normal exit code is `0`; invalid usage returns `2`; an unavailable,
missing, or inconsistent Beads, Gas City, or GitHub source returns `1` with a
specific error on stderr and no partial snapshot. For recovery, inspect only
the named authoritative source:

```bash
gc bd show af-1vr4 --json
gc status --json
gh auth status
gh pr view <number> --repo <gc.github_repo from the delivered Bead> \
  --json number,state,mergedAt,mergeCommit,headRefOid,statusCheckRollup,url
```

Restore source availability or correct the parent coordination pointer at its
authoritative Bead; do not copy product state into the wrapper or treat its
output as a second backlog. `GC_BIN` and `GH_BIN` are injectable for the
deterministic fixture suite, while the operator defaults remain `gc` and `gh`;
Bead reads intentionally go through `gc bd` for store routing.

#### Closing the delivered-outcome Bead

`gc.last_delivered` must only ever point at a Bead that carries all six
ADR-0016 delivery-proof fields (`gc.delivery_status`, `gc.work_outcome`,
`gc.github_repo`, `gc.pr_number`, `gc.pr_head`, `gc.merge_commit`), because
`derive_delivery()` above requires every one of them and fails closed
otherwise. Never close that Bead by hand with `gc bd close` or a raw `gc bd
update --status=closed`; use the deterministic wrapper instead:

```bash
./bin/deliver-close <bead-id> --repo <owner/repository> --pr <number>
```

It independently verifies with `gh pr view` that the named pull request is
merged, then writes all six fields from that verified evidence and closes the
Bead in the same call. If the PR cannot be verified as merged it refuses to
close the Bead and makes no metadata change at all — never a bead that looks
closed but is silently missing its proof. `tests/deliver-close-test.sh` covers
the merged/not-merged/mismatched-evidence/GitHub-failure paths against
`GC_BIN`/`GH_BIN` fixtures.

If a delivered result is closed by hand anyway while it is still the
coordination's `gc.current`, the projection reports it as **finalizing**
(`mayor_finalization`), not as an agentless materialized result, and the
campaign wakes the Mayor with `finalize:<id>` spelling out the three steps:
`deliver-close`, then `gc.last_delivered`, then `gc.current`. Until they are
done the next eligible candidate cannot start (af-7700, 2026-09-16).

#### 2026-09-15 product-status and human-state evidence

- **TARGET:** expose infrastructure health, delivery activity, result lifecycle,
  exact delivery evidence, the next eligible product candidate, and explicit
  resume owner/action without confusing an optional launch with a blocker.
- **CONFIGURED:** `bin/saymyname-product-status` uses only deterministic local
  `bd`, `gc`, `gh`, `jq`, product-queue, and pure Python projection primitives;
  it has no database, model, scheduler, or write path.
- **PROVEN:** the fixture suite covers active and agentless materialized work,
  Mayor finalization, automatic dependency/campaign policy, manual idle, all
  paused, empty queue, Benjamin decision, explicit blocker, healthy/degraded/down
  infrastructure, exact GitHub evidence, routed Beads, queue/source failure, and
  pointer divergence. Live verification must be repeated from the merged head.

### Versioned product release contract

Git, not the Product view or the campaign, owns the versioned SayMyName
release target. From the canonical Factory checkout:

```bash
cd ~/agent-factory
./bin/product-release validate                     # config/releases/saymyname-v1.json
./bin/product-release project
./bin/product-release transition --to approved
./bin/product-release start-next --version V2
```

`lib/product_release.py` is a pure module: it reads no live state, writes no
files, and never calls a model. `validate_release_contract` enforces the
invariants JSON Schema (`config/product-release.schema.json`) cannot express —
every capability, journey, criterion, dependency, and `work_graph` node must be
schema-valid and cross-referenced; `work_graph` node IDs and dedupe keys are
globally unique and acyclic; every node is traceable to at least one approved
criterion; and `af-cm1l` can never be recorded as a V1 product capability,
only as a Factory improvement. `transition_release` and `start_next_version`
are idempotent and fail-closed: `draft → approved → executing → frozen` is the
only path, a `frozen` contract is immutable, and starting `V2` first freezes
`V1` and returns its frozen evidence rather than mutating it in place.

`select_campaign_work` is the only function the Mayor campaign may call to
pick work from a release. It returns exactly one deduplicated, criterion-
traceable, dependency-satisfied, proven-independent candidate, or an explicit
stop reason (`release_not_executable`, `independence_unknown`,
`blocked_<decision|admin|limit|durable_failure|dependency>`,
`release_target_proven`, or `no_proven_independent_work`) with an owner and an
exact recovery action. It never reorders the product queue and never
materializes work itself. `project_release` adds human-facing status labels
and the campaign/intervention projection for the Product view;
`project_operational_release` overlays only the runtime `truth_state` versus
`operational_state` distinction — an `approved`/`executing` release with the
campaign enabled shows as executing, a `draft` release can never be reported
as campaign-executing, and a `frozen` release stays frozen regardless of
campaign state.

- **TARGET:** one schema-validated, versioned release contract per product
  drives the Product view, the campaign, and V1→V2 freeze semantics, with no
  second orchestrator, queue, or UI.
- **CONFIGURED:** `config/product-release.schema.json` plus
  `lib/product_release.py`/`bin/product-release`; `config/releases/saymyname-v1.json`
  is the current SayMyName V1 contract, referenced from
  `config/products/saymyname.json#release_contract`.
- **PROVEN:** `tests/product-release-test.py` covers schema-required-field
  parity, semantic validation edge cases (dangling references, duplicate IDs,
  graph cycles, self-dependency, blocker/decision consistency, the `af-cm1l`
  guard), the full transition state machine including frozen immutability and
  V2 freeze, and campaign graph selection (order tie-break, an
  unknown-independence node not blocking a later proven candidate, dependency
  gating, and blocker tie-break by kind then cause). It also loads and
  projects the real `config/releases/saymyname-v1.json` contract. Live
  verification through the Product view must be repeated from the merged head.

### Ordered product candidates

Keep future SayMyName outcomes out of the executable worker queue with:

```bash
cd ~/agent-factory
./bin/saymyname-product-queue list
./bin/saymyname-product-queue next
./bin/saymyname-product-queue --help
```

Candidates are durable Beads in `deferred` status. The command rejects malformed
or duplicate ranks and serializes local mutations. Use `list --json` or
`next --json` for compact automation. The PO may mutate candidates only after a
RECORD request. The Mayor follows `docs/PRODUCT_QUEUE.md` to create a separate
execution Bead and materialize only the first eligible candidate. Never change a
candidate to `open` or dispatch it directly.

### Mayor-owned continuous campaign

The campaign is persistent Beads policy plus a deterministic Gas City Order; it
is not another worker or orchestrator. Confirm installation after deploying the
merged Factory head:

```bash
gc order show mayor-campaign
gc order check --json | jq '.orders[] | select(.name == "mayor-campaign")'
./bin/mayor-campaign status | jq .
```

Activation is a two-step Mayor guard. Materialize the first eligible candidate
in the distinct Factory-campaign lane, then activate its already-linked execution
Bead:

```bash
./bin/saymyname-product-queue materialize <campaign-candidate> <execution-bead> --mayor
./bin/mayor-campaign activate <campaign-candidate> <execution-bead> --mayor
gc order run mayor-campaign
```

All five mutation paths (`activate`, `block`, `resume`, `complete`, `sentinel`)
share one host-local flock. Repeating the exact active activation is a no-op;
activation refuses to overwrite a blocked/completed campaign or to bypass
`NEEDS BENJAMIN`, a blocked result, or an existing automatic resume condition.

The Order runs `./bin/mayor-campaign sentinel` every minute. It performs one
canonical status read, no model call, and sends durable mail only when the Mayor
must materialize the next result, resume an agentless materialized result,
finalize the current result, or record an empty campaign. It never invokes queue
materialization, dispatch, GitHub, merge, or Bead closure itself. An observed
current result suppresses next-result notification, preserving one-at-a-time
delivery across controller restarts.

Record a real stop with its owner and exact action; do not put ADMIN failures in
`gc.needs_benjamin`:

```bash
./bin/mayor-campaign block --kind admin --cause "<cause>" \
  --owner Benjamin --action "<exact authorized action>" --mayor
./bin/mayor-campaign resume --mayor
./bin/mayor-campaign complete --mayor
```

`decision` requires an effective `gc.needs_benjamin`; `admin`, `limit`,
`result_blocker`, `all_paused`, and `durable_failure` remain separate typed
causes. Queue/source contention is retried. A local reason never produces a
global stop (ADR-0016 §7): when three consecutive sentinel failures are
attributable to one candidate/node (its ID comes from the same status read
that failed to plan a transition), the sentinel quarantines that node alone —
`gc.queue_state=blocked_durable_failure` plus a pause reason on the node's own
Bead — and opens a repair Bead referencing it (`gc.repair_for=<node id>`); the
coordination Bead's `gc.campaign_state` is left `active` and the campaign keeps
selecting other eligible work. Only a failure that cannot be tied to a
candidate — the coordination store itself unavailable, or its own metadata
malformed — still persists `blocked + durable_failure + Mayor + exact resume
command` on the shared coordination Bead; repair the named source and run
`resume --mayor`. A restart in `wake_state=pending` safely resends the same
durable mail before marking it `sent`; duplicate mail cannot bypass the
first-eligible materialization guard.

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

`status` and `stop` derive the City root from this Factory checkout, so they
remain available when the Gas City API is down. `start` still requires usable
Gas City health and suspended application rigs with no active writer. A custom
`SAYMYNAME_PREVIEW_STATE_DIR` must be absolute and end with
`/agent-factory/saymyname-preview`; the wrapper rejects broader targets before
creating directories, changing permissions, or writing ownership state.

#### 2026-09-14 preview evidence

- **TARGET:** provide one deterministic Factory-owned command that previews the latest merged application `dev` branches without mutating persistent application data.
- **CONFIGURED:** the wrapper pins the canonical application remotes, `dev` branches, MySQL `8.0.41`, loopback application ports, an ephemeral database `tmpfs`, and generated preview-only configuration.
- **OBSERVED:** Backend resolved to `2cba440d2815ded53dfea7bfd3beecdf57355c50` and Frontend to `b98e1ee176b7ed8af62987fdd84b35065b49c9e1`; MySQL used loopback-only random ports and both application repositories remained clean on `dev`.
- **PROVEN:** clean start and restart cycles reached Backend HTTP `204` at `/api/auth/csrf` and Frontend HTTP `200`; independent status reported both healthy with the exact SHAs. Stop removed the owned process groups, container, and runtime state, after which status returned `3` and the preview listeners were absent. Deterministic safety tests also prove the repository, writer, port, state-target, runtime-directory, and Gas-City-outage recovery checks.

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
