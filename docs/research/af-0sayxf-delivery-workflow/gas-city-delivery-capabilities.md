# What Gas City allows for a redesigned delivery workflow

Research ticket `af-0sayxf.6`, map `af-0sayxf`. Read 2026-10-05 (Paris), Factory suspended (controller stopped, 0/11 agents), live root at `origin/main`. Read-only: `cat`/`grep`/`gc ... --help`/`gc config explain`/`gc skill list`/`bd show`/`ldd`, plus one throwaway `docker run --rm --network none` on an image already present. Nothing was started, installed or edited.

Builds on `as-is-delivery-flow.md` (branch `research/af-0sayxf-charting`); facts already there are not repeated.

## Sources

| Tag | Source |
|---|---|
| **GC** | Upstream Gas City at tag `v1.4.1` (commit `58ef17e`), the installed version (`gc version` = `1.4.1`): `https://github.com/gastownhall/gascity/blob/v1.4.1/<path>` |
| **PACK** | Vendored packs pinned in `packs.lock`: `~/.gc/cache/repos/90e14213…/` (gascity-packs `3b3b89f`: `gascity/`, `gastown/`) and `~/.gc/cache/repos/6fe2cc15…/` (gascity `f895c0f`: `internal/bootstrap/packs/core`) |
| **LOCAL** | `/home/benja/agent-factory` (paths relative to it) |
| **PROBE** | Read-only command run for this ticket; command and result quoted |
| **CC** | Claude Code docs, `https://code.claude.com/docs/en/skills` |
| **MP** | `github.com/mattpocock/skills` at the Factory pin `c55ee46` (`docs/UPSTREAM_SKILLS.md:11`) |

Verdict vocabulary: **as-is** = configuration only, no new code; **with adaptation** = needs new Factory code, formula or host setup; **impossible** = no path at the installed version.

## Verdict table

| # | Capability | Verdict | One-line reason |
|---|---|---|---|
| 1a | Make pinned skills visible to a worker | With adaptation (small) | Gas City symlinks `skills/<name>/` (city) or `agents/<role>/skills/<name>/` (role) into each session's `.claude/skills` / `.codex/skills`; Matt's repo must be vendored as files, nothing is in WSL today |
| 1b | Formula step makes the worker invoke a skill | With adaptation | Step text is a prompt: works for model-invocable skills (`tdd`, `code-review`); `implement` cannot be invoked by the model, only typed or inlined |
| 2 | Review in a fresh context, distinct session | With adaptation | Per-step routing (`gc.run_target`) to another agent template gives another session; the HQ rig has no reviewer agent and allows only `mol-do-work` |
| 3 | Model and effort per role, other provider | As-is in Gas City; with adaptation in the Factory | `provider` + `option_defaults` per agent; `provider-failover` rewrites providers per target and must learn the new roles; no Opus 5 id in `gc` 1.4.1 |
| 4 | Several tickets on one integration branch per Spec | With adaptation | Convoy `--target` metadata and shared drains exist; the `mol-do-work` path, CI trigger, `pr-autopilot` and worktree script are hard-wired to the protected branch |
| 5 | Launch the app and a driven browser in WSL, no human | With adaptation | Headless Chromium works today only inside the existing Playwright Docker image; on the host 4 system libraries are missing and `sudo` needs a password |
| 6 | Crash recovery and limits | Mostly as-is | Beads hold the work; step text is frozen at dispatch; recovery, quotas and caps are known and listed below |

Nothing was found impossible.

## 1. Skills: visibility and invocation

### 1a. Visibility

- **Mechanism.** "You author a skill once at a scope, and Gas City materializes it to every eligible agent": `skills/<name>/` at pack level is shared with every agent in the city; `agents/<role>/skills/<name>/` only with that role, and wins on name collision. "At startup Gas City **symlinks** both scopes into each agent's provider-specific skill sink — `.claude/skills/`, `.codex/skills/`, …". "It *places* files into each provider's convention; it doesn't translate them." (GC `docs/guides/capabilities-for-coding-agent-users.md:45-61`). Source: sinks are `claude → .claude/skills`, `codex → .codex/skills` (GC `internal/materialize/skills.go:60-66`); materialization runs at `gc start`, on every supervisor tick, and as a PreStart step when the session work dir differs from the scope root (`skills.go:9-13`).
- **Names.** City-pack skills keep their directory name; skills from an imported pack are renamed `<binding>.<name>` (`skills.go`, `LoadCityCatalog`: `e.Name = catalog.BindingName + "." + e.Name`). PROBE `gc skill list --agent factory-worker`: 8 entries, all `core.gc-*` and `gascity.mayor`. Claude Code takes the slash-command name from the frontmatter `name` field when present, else from the directory (CC).
- **Per-agent allow-lists do not exist.** The `skills` field of an agent is a tombstone: "accepted but ignored by the active materializer" (GC `docs/reference/config.md:120`; `docs/reference/specs/pack-spec.md:402-404`). Scope is by directory only.
- **Today.** PROBE: `.gc/agents/factory-worker/.claude/skills/` holds 8 symlinks into `~/.gc/cache`; `skills/` does not exist at the city root; `agents/factory-worker/` holds only `agent.toml` and `prompt.template.md`; `~/.claude/skills` and `~/.agents` do not exist in WSL. `.gitignore` ignores `.claude/skills/` (the sink), so the source must live in `skills/` or `agents/<role>/skills/`.
- **Pinning.** `gc import` pins a *pack* by sha (`pack.toml:5-14`, `packs.lock`). Matt's repo is laid out as `skills/engineering/<name>/SKILL.md` (MP), not as a Gas City pack, so it cannot be imported as-is: the skill directories have to be vendored (copied) into the Factory repo, and the pin is then the commit that vendored them plus `docs/UPSTREAM_SKILLS.md`.
- **Other route, outside Gas City.** Worker sessions run with `CLAUDE_CONFIG_DIR=/home/benja/.claude` (`city.toml:31,51`), so `~/.claude/skills/<name>/` in WSL is a personal-scope skill directory for every Claude session there (CC: "`~/.claude/skills/<skill-name>/SKILL.md` - All your projects on this machine"). It is unversioned and Claude-only. The upstream repo also ships a `.claude-plugin` directory (PROBE `gh api …/contents?ref=c55ee46`), i.e. a Claude Code plugin install route; not examined.
- **Discovery timing.** Claude Code loads project skills from the directory where the session starts and its parents (CC). A worker session starts in `.gc/agents/factory-worker` (`agents/factory-worker/agent.toml:3`; session bead `af-n8zt8` `work_dir`), then `cd`s into its worktree; skills come from the start directory, not from the worktree.

### 1b. Invocation from a formula step

- **What a step is.** A step `description` is rendered (variables substituted) and copied into a bead; the worker receives it through `gc hook --claim`. PROBE: step bead `af-v7dxk` (`gc.step_ref=mol-do-work.do-work`) holds 4,702 characters of the formula text with `{{convoy_id}}` already replaced by `af-oae8q`. So "make a step invoke a skill" means "the step text tells the model to call the Skill tool".
- **Model-invocable skills.** MP at the pin: `tdd` and `code-review` have no `disable-model-invocation` line, so the model may load them. A step saying "use the `tdd` skill" is therefore technically sufficient for Claude. Not run live (Factory suspended). Two cautions: the worker prompt forbids loading skills *before* the claim only (`agents/factory-worker/prompt.template.md:23-25`); upstream `code-review` collides by name with Claude Code's built-in `/code-review` (already noted in the as-is report §6).
- **`implement`.** MP at the pin: `disable-model-invocation: true`. CC: "Claude can't invoke the skill on its own"; it is triggered "manually with `/name`". A formula step cannot make the model call it. Three workable routes, each an entry for the Adaptation Register:
  1. Inline it: the upstream `implement` file is 433 bytes (PROBE `gh api … | wc -c`); it says to use `/tdd` at agreed seams, typecheck and test regularly, then `/code-review`, then commit. A formula step can carry that text and call the two model-invocable skills.
  2. Vendor a copy without the flag.
  3. Type it: `gc session nudge <session> "<text>"` is "equivalent to typing the message into the session's terminal" (PROBE `gc session nudge --help`), so a script could type `/implement …` into a worker's tmux session. Not tested; it would need a new deterministic step, since nothing today types into worker sessions.
- **`implement-spec`.** Absent from `skills/engineering/` at the pin `c55ee46`; present at `d81f3a1` and at `main` (PROBE `gh api …/contents/skills/engineering?ref=…`). The pin predates it.
- **Codex.** Skills are placed in `.codex/skills` without translation. Whether Codex CLI 0.155.1 honours `disable-model-invocation` or loads these skills the same way was not verified.

## 2. Review in a fresh context

- **Per-step routing exists.** "A step's `gc.run_target` metadata is compile-time routing intent: at dispatch the router resolves it into `gc.routed_to`" (GC `docs/reference/specs/formula-spec-v2.md`, §2). "v2 steps each route to a different agent or pool" (GC `docs/guides/understanding-formulas.md:128`).
- **Same target means same session.** PROBE: step bead `af-v7dxk` carries `gc.routed_to=factory-worker`, `gc.session_affinity=require`, `gc.continuation_group=pool-workflow`, `gc.session_id=af-n8zt8`. `mol-do-work` sets no `gc.run_target`, so its four steps run in the one session that claimed the first. A review step added to that formula without its own target would run in the writer's context.
- **Different target means different session.** A session is "a live process with its own terminal, state, and conversation history" created by slinging work to an agent that is not running (GC `docs/tutorials/03-sessions.md:66-70`). Each agent template has its own sessions. Existing examples: `formulas/build-basic-review-scoped.formula.toml:44-71` routes three review lanes to `gc.implementation-reviewer`, `gc.gap-analyst`, `gc.design-implementation-reviewer` and a synthesis to `gc.review-synthesizer`; PACK core `formulas/mol-review-quorum.toml` takes two reviewer lanes with provider, model and target as variables.
- **Bounded fix loop exists.** `[steps.check]` re-runs a step until an `exec` script passes, up to `max_attempts` (GC formula-spec-v2 §3.1, `:652-664`); used locally with `max_attempts = 6` on the review loop (`build-basic-review-scoped.formula.toml:36-42`). `gc converge` offers the same idea at loop level (root bead + formula + gate script, `--max-iterations`, default 5; PROBE `gc converge create --help`).
- **`wake_mode = "fresh"`** starts "a new provider session on every wake" instead of resuming (GC `docs/reference/config.md:134`). Useful for a reviewer template reused across tickets.
- **What is missing on the HQ rig.** PROBE `gc agent list`: the `gc.*` role agents exist only under `saymyname-backend/` and `saymyname-frontend/` (they come from `[rigs.imports.gc]`, `city.toml:218-236`). City scope has `factory-worker`, `mayor`, `ux-reviewer`, and the implicit `claude*`/`codex` pools. `claude-reviewer` was retired because nothing dispatched it (`city.toml:273-276`). The HQ project file allows one formula: `formulas = "mol-do-work"` (`config/projects/agent-factory.toml:25`), enforced by `bin/dispatch-door`. So a fresh-context review on HQ needs: a reviewer agent directory (`agents/<name>/`), a formula with a step routed to it, and that formula allowed for the rig.
- **Cost bound.** Worker pool cap is 2 sessions (`agents/factory-worker/agent.toml:5`); `dispatch-door` defers dispatch under 1.5 GiB free memory (`bin/dispatch-door`, `MEM_MIN_KIB`); PROBE `free -g`: WSL has 7 GiB total.
- **Not the same thing.** Upstream `code-review` "runs both reviews in parallel sub-agents" (MP). Those are Claude Code sub-agents inside the writer's own session: fresh context, same session, same provider and model.

## 3. Model and effort per role

- **Per-agent knobs.** Harness: agent `provider`. Model: agent `option_defaults.model`. (GC `docs/guides/configuring-an-agent.md:22-28,75-91`.) Agent `option_defaults` is "applied on top of the provider's OptionDefaults (agent keys win)" (GC `docs/reference/config.md:105`). A named provider can also bundle model and effort: `[providers.claude-standard.option_defaults]` `model = "sonnet-5"`, `effort = "medium"` (`city.toml:54-57`).
- **Different provider per role already runs.** `agents/ux-reviewer/agent.toml:1` is `provider = "codex"`; `agents/mayor/agent.toml:1` is `provider = "claude-standard"`. Both CLIs are installed (PROBE: `claude` 2.1.236, `codex-cli` 0.155.1). PROBE `gc config explain --provider codex`: `model = gpt-5.6-sol`, `effort = xhigh`; `--provider claude`: `sonnet-5`, `high`. A real session command line: `codex --dangerously-bypass-approvals-and-sandbox --model gpt-5.6-sol -c model_reasoning_effort=xhigh` (session bead `af-n8zt8`).
- **Model ids are validated by `gc`, not by the CLI.** PROBE `strings /usr/local/bin/gc`: Claude ids present are `sonnet-5`, `fable-5`, `opus-4-7`, `opus-4-8`, `sonnet-4-6`, haiku ids; no Opus 5 id. Upstream doc for 1.4.1 lists "opus · sonnet · haiku · opus-4-7 · fable-5" and "gpt-5.6-sol · gpt-5.6-terra · gpt-5.6-luna · gpt-5.5 · gpt-5.3-codex · o3 · o4-mini" (GC `docs/guides/harness-recipes.md:69,92`). The comment at `city.toml:81-106` (an unknown id put the bead store in fail-closed) still applies at 1.4.1.
- **Factory layer overrides the provider.** `bin/provider-failover` regenerates `city.provider.toml` every two minutes with one `[[patches.agent]]` per *target* declared in `config/provider-policy.json` (`workspace`, `mayor`, `ux-reviewer`). `factory-worker` has no pin and inherits `workspace` on purpose (`city.toml:259-262`). Consequences for new roles: each needs a target and a fallback chain there, or it silently follows `workspace`; and a failover can put writer and reviewer on the same pool. Evidence it happens: the same `factory-worker` template ran Codex on 2026-09-23 (`af-n8zt8`) and Claude Sonnet 5 medium during Cockpit V2 (as-is report §1).
- **One Anthropic account.** "Un seul compte : une limite de session ou hebdomadaire épuise tous les profils Claude d'un coup" (`config/provider-policy.json`, pool `anthropic`). Model independence between writer and reviewer therefore means two pools (Anthropic + OpenAI), not two Claude profiles.

## 4. One integration branch per Spec

### What Gas City offers

- **Convoy target branch.** `gc convoy create auth-rewrite --owned --target integration/auth-rewrite`; `--target` is the "target branch inherited by child work beads"; `--merge direct|mr|local`; `--owned` skips auto-close until `gc convoy land` (GC `docs/reference/cli.md:1083-1093,1217-1219`; `docs/tutorials/06-beads.md:311-325,367-390`). `gc convoy target <id> <branch>` sets it later.
- **It is metadata, consumed by formulas.** "Child work beads can inherit this target branch when slung with feature-branch formulas such as mol-polecat-work" (PROBE `gc convoy target --help`). The router injects "an automatic `base_branch` / `target_branch` when the formula references them" (GC `docs/reference/specs/formula-spec-v1.md:319-322`); resolution order is the work bead's `metadata.target`, then the parent convoy chain (PACK `gastown/formulas/mol-polecat-work.toml:71-73`). That sentence is in the v1 spec; the v2 spec does not restate it and it was not tested on a v2 formula.
- **Shared drain.** `[steps.drain]` with `context = "shared"` runs "one single-lane item root at a time", `on_item_failure = "skip_remaining"` (GC formula-spec-v2 §3.3, `:761-780`). The core "deliberately treats a shared drain as scheduling policy" and does not create the worktree (`bin/factory-shared-drain-workspace:5-9`).
- **Merge queue agent ("refinery").** PACK `gastown/formulas/mol-refinery-patrol.toml`: a patrol agent that takes work beads carrying `metadata.branch`/`metadata.target`, rebases, runs tests, merges by `merge_strategy` (`direct` or `mr`; `local` escalates), and can auto-land a finished integration branch (`:1032-1052`). It is in the cache only because the gascity-packs repo is cloned whole: the `gastown` pack is not imported (`pack.toml:5-14`), no refinery agent exists (PROBE `gc agent list`). It is an LLM agent following a 1,000-line prompt, not deterministic code.

### What the Factory already has

- `bin/factory-shared-drain-workspace prepare|publish|cleanup`: "une branche `build-basic/<workflow-root-id>` et un seul worktree … Chaque item travaille et commit séquentiellement sur cette même histoire … une seule PR, jamais une PR par item" (`docs/DELIVERY.md:557-589`), with a deterministic test (`tests/factory-shared-drain-workspace-test.sh`). It serves `build-basic --var drain_policy=same-session` only, which HQ does not allow.

### What blocks it on the current delivery path

| Place | Hard-wired behaviour | Evidence |
|---|---|---|
| `bin/factory-do-work-workspace enter` | Isolates only when the repo is on its protected branch; branch name `do-work/<bead>`; base = that protected branch | `:177-195`, `:220-223` |
| `mol-do-work` | Requires an input convoy with exactly one member; PR base = branch found at dispatch | `formulas/mol-do-work.formula.toml:120-125,170-175` |
| GitHub CI | Runs only for PRs targeting `main` | `.github/workflows/ci.yml:7-11` |
| `bin/pr-autopilot` | Arms auto-merge only for open PRs with `--base <protected branch>` | `:769` |
| `bin/deliver-close` | Needs a merged PR and a successful required-workflow run on the PR head; accepts any base that equals `gc.work_base_branch` | `:235-240` |
| Ticket graph | Publishes one delivery convoy with `bd create --graph`; no `target` metadata is set | as-is report §1 |

So ticket PRs into an integration branch would get no CI run and no auto-merge today; a per-Spec branch needs these pieces changed together, or a new formula built on the shared-drain adapter. Both are Factory work; Gas City itself does not block either shape. Parallel writers on one branch are not offered by anything read here: the shared drain is strictly one item at a time, and `separate` drains give each item its own worktree.

## 5. Launching the application and a driven browser in WSL

### Installed (PROBE, 2026-10-05)

| Item | State |
|---|---|
| Node / npm | 22.23.2 / 10.9.8 (`~/.local/bin`) |
| Java / Maven | Temurin 21.0.12 / Maven 3.9.9 (the Windows install, via `/mnt/c`) |
| Python | 3.12.3; no `pip`, no `playwright`, no `selenium` module |
| Docker | Engine 29.7.2, user `benja` in group `docker` |
| Docker images | `mcr.microsoft.com/playwright:v1.63.0-noble`, `:v1.47.0-jammy`, `mysql:8.0/8.0.41/8.4`, Testcontainers `ryuk` |
| Playwright browsers on host | `~/.cache/ms-playwright/`: `chromium-1243`, `chromium_headless_shell-1243`, `ffmpeg-1011` |
| Playwright package | `@playwright/test ^1.63.0` in `rigs/saymyname-frontend/package.json:52`; nothing global (`npm ls -g`: only `claude-code`, `corepack`, `npm`); none in the Factory repo |
| Browsers on PATH | none (`chromium`, `google-chrome`, `firefox`, `chromedriver`, `xvfb-run`: absent) |
| `sudo` | "a password is required" (non-interactive) |
| MCP for workers | `gc mcp list --agent factory-worker`: "No projected MCP servers"; upstream: "MCP is list-only today" (GC capabilities guide `:62-63`) |
| Host size | 12 vCPU, 7 GiB RAM, load 0.12 |

### Probes

- **Host Chromium does not start.** `ldd …/chrome-headless-shell`: `libnspr4.so`, `libnss3.so`, `libnssutil3.so`, `libasound.so.2` not found; running it fails with "error while loading shared libraries: libnspr4.so". `dpkg`: `libnss3` and `libasound2t64` not installed. Fixing it is an `apt install` (or `npx playwright install-deps chromium`), which needs `sudo`, hence Benjamin once.
- **Container Chromium works now.** `docker run --rm --network none mcr.microsoft.com/playwright:v1.63.0-noble …chrome-headless-shell --no-sandbox --headless --dump-dom "data:text/html,<h1>probe-ok</h1>"` printed `<html><head></head><body><h1>probe-ok</h1></body></html>` (Chrome for Testing 153.0.8010.12); `--screenshot=/tmp/p.png --window-size=390,844` wrote a 5,252-byte PNG. The image ships browsers and Node 24.20.0 but not the Playwright npm package (`npx --no-install playwright` failed), so a test project must bring its own `node_modules`.

### Launching applications

- **Cockpit (Factory HQ product).** `bin/cockpit start|stop|status|run`: pure Python, "survives a suspended or stopped city", binds `127.0.0.1` only, default port 8173 (`bin/cockpit:1-13`; `lib/cockpit/core/config.py:14,31-32`). Launchable by a worker without a human. A second instance for a worktree needs `COCKPIT_PORT` and its own pid file (config is read from the environment).
- **SayMyName.** `rigs/saymyname-frontend/e2e/scripts/run-e2e.sh` already does the whole chain unattended: scratch MySQL container, real backend with a synthetic seed, built frontend on `vite preview`, "runs the Playwright smoke suite headlessly, then tears everything down" (`:1-12`); requires `docker mvn java node npm`, all present. Whether it currently passes in WSL was not run (it starts containers and a backend).
- **No generic contract.** Nothing in `config/projects/*.toml` tells a worker how to start a project's application or where it listens; each project has its own script or none.

### What would be needed

1. One of: the 4 system libraries on the host (one `sudo` action by Benjamin), or running the browser from the existing Docker image with host networking so it can reach `127.0.0.1:<port>` (not verified in this WSL setup).
2. A Playwright package where the driving script runs (present for the SayMyName frontend; absent for the Factory repo, which is Python).
3. A per-project "how to launch, which URL, how to stop" declaration, and port isolation when two worker sessions run at once.
4. A place to keep screenshots: the repo tracks no image today (as-is report §3).

Gas City adds nothing here and blocks nothing: a formula step is a prompt executed by a session with a shell (`permission_mode = "unrestricted"`, `city.toml:35,55`), and `[steps.check]` can run any script as a gate.

## 6. Crash recovery and limits

### Step text is frozen at dispatch

- A formula is compiled into beads when it is slung or cooked; step metadata is "copied to the cooked bead" and descriptions take `{{var}}` substitution (GC formula-spec-v2 §1.3, `:209-214`). PROBE: `af-v7dxk` (above). Editing a formula changes only later dispatches; a workflow in flight keeps the text it was born with.
- Drift is detectable: the root is stamped with `gc.formula_hash` (SHA-256 of the formula file) and `gc.formula_source`; `gc formula version-check <bead-id>` compares it with the file on disk (GC formula-spec-v2 `:555-559`). PROBE: root `af-4pc1e` carries `gc.formula_hash=807c4731…` and `gc.formula_source=/home/benja/agent-factory/formulas/mol-do-work.formula.toml`.
- One exception, by design: with `description_file`, "Files larger than 4096 bytes are not inlined. The step's description is replaced by a generated pointer that directs the agent to read the file at its resolved path" (GC formula-spec-v2 §1.8, `:464-466`). Such a step reads the file live at execution time, so it is *not* frozen. `mol-do-work` uses inline `description` (frozen).
- The work bead's own description (the ticket body) is separate and read live with `gc bd show` (`mol-do-work.formula.toml:126`).

### Sessions

- Work survives a session: "every unit of work is a bead that survives an agent crash" (GC `docs/getting-started/how-gas-city-works.md:29`). The default work query's first tier is "in_progress work assigned to this session/alias (crash recovery)" (GC `docs/reference/config.md:113`).
- `gc session kill` leaves the bead active so "the reconciler will detect the dead process and restart it"; `gc session reset` restarts "with fresh provider conversation state" keeping identity, mail and queued work (PROBE help texts). Default `wake_mode` is `resume` (same provider conversation).
- Crash loops: `max_restarts = 5` within `restart_window = 1h`, then the agent is quarantined; `gc session wake` clears it (GC `docs/reference/config.md:318-319`; `gc session wake --help`).
- Idle: `idle_timeout = "2h"` on `factory-worker` kills an inactive session (`agents/factory-worker/agent.toml:6`; GC `config.md:115`); long commands must call `gc runtime heartbeat` or the formula's `gc bd heartbeat`.
- Factory layer on top: a post-commit hook pushes every commit of a worktree so a dead session loses nothing committed (`bin/factory-do-work-workspace:104-142`); a re-dispatch reuses the same worktree, branch and PR (`mol-do-work.formula.toml:57-73`); the `session.stranded` event reopens the orphaned work bead and pages the Mayor, and is skipped while the city is suspended (`bin/on-session-stranded:2-21`, `orders/on-session-stranded.toml`).
- Not covered by anything read: a step that dies *between* commits loses uncommitted edits; and a session restarted fresh has only the bead text and the branch to rebuild context from.

### Workflow control

- `[steps.check]`: after each attempt the orchestrator runs a script; "pass closes the step, fail with budget left spawns the next iteration, exhaustion closes the step as failed"; only `mode = "exec"` (GC formula-spec-v2 `:652-664`).
- `[steps.retry]`: re-runs attempts classified transient, `on_exhausted = hard_fail | soft_fail` (`:708-758`).
- Scopes: `gc.on_fail = "abort_scope"` skips the remaining members when one fails; a member closing with a missing outcome counts as failed (§3.5). Without a scope, a dependent step becomes ready when its blocker closes, pass or fail (`formulas/build-basic.formula.toml:26-32`).
- Control beads are processed by the orchestrator alone: "no user-configured agent role participates" (`:644-650`). With the controller stopped, nothing advances.
- Drain cap: 100 units per drain, hard (`:771-779`).

### Quotas and caps

- Gas City 1.4.1 documents no model-quota handling (PROBE `grep -i quota docs/`: webhook rate limits only). Quota walls are handled by the Factory: `bin/provider-failover` (order, every 2 min) detects a wall in live sessions, switches the provider per target, restarts sessions stuck on an exhausted pool, and when every pool is exhausted files one NEEDS BENJAMIN; `bin/dispatch-door` then refuses new dispatches until a pool returns (`bin/provider-failover:1-25`; `bin/dispatch-door` header).
- Concurrency: `factory-worker` max 2; implicit `claude` pool max 2 at city scope, 1 per product rig (`city.toml:259-271`). Each new role (reviewer, evaluator) adds sessions against the same 7 GiB.
- `gc costs` reports token and wall-time facts per run as "a list-price estimate for decision support" (PROBE `gc costs --help`); several usage fields are documented as "currently always absent" in the 1.4.1 API schema.

## Not verified

- No live run: skill loading by a worker, a step invoking `tdd`, a second-agent review step, `gc session nudge` typing a slash command, and `base_branch` injection on a v2 formula were read from docs and source, not executed (Factory suspended; dispatch forbidden for this ticket).
- Codex CLI behaviour with `.codex/skills` and with `disable-model-invocation`.
- Whether passing an unknown model id through `args_append` (as `[providers.codex]` does with `-m`) bypasses `gc`'s model validator for Claude.
- Whether a container on host networking reaches a server bound to `127.0.0.1` in this WSL setup; whether `run-e2e.sh` passes today.
- `mattpocock/skills` `main` is at `24fe0ef` (2026-10-04 14:48 Paris); the directory listing equals `d81f3a1`, file contents were not compared.
- Gas City source was read only for `internal/materialize/skills.go`; routing and session-affinity behaviour comes from the spec, the docs and one observed step bead.
