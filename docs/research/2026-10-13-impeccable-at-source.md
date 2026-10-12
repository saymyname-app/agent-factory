# Impeccable design skill, verified at source (2026-10-13)

Repository: `pbakaus/impeccable` (Apache-2.0). Tag read: **`skill-v4.5.2`**, commit **`d631a8827f99414d2b6daba4ef08b7f8701751d7`** (2026-10-09 06:19 Paris; also tagged `cli-v4.5.2`; engine `0.1.14`). Method: GitHub API and raw files only; nothing installed or executed. `[V]` = read in the files at that commit today; `[I]` = inferred.

## Corrections to the README-based pass (2026-10-12)

| Earlier claim | At source |
|---|---|
| 24 commands | `[V]` 24 rows in the Commands table (one is `craft`, a deprecated alias), plus management verbs `pin`, `hooks`, `doctor`. |
| `reference/` and `scripts/` folders | `[V]` Yes. |
| Scripts are a Node CLI | **Wrong now.** `[V]` Every verb runs one prebuilt **Rust binary** (~20.7 MB on linux-x64). It is **not in the skill folder**: the launcher downloads it on first use. |
| CLI `detect, install, update, telemetry` | `[V]` `detect`, `ignores`, `install`, `update`, `check`, `link`, `help` and ~25 internal verbs exist. **No `telemetry` verb** in the router (`crates/cli/src/main.rs`). |
| Hooks, browser extension | `[V]` Both exist (`plugin/hooks/hooks.json`, `.codex/hooks.json`, `extension/`). |
| Telemetry "still sent when opted out" | **Partly right**, see Network. Opt-out stops the choice ping; the "roll" GET is not gated by it. It fires only in the new-work flow, not on every design task. |
| 59 rules, exit codes 0/2/1 | `[V]` 59 rules (31 `slop`, 28 `quality`) in `crates/live/assets/antipatterns.json`; exit codes as documented in `README.md` L468 (doc, not traced in code). |
| Source `skill/SKILL.src.md` | `[V]` Yes. |
| Built copies under `dist/...` | **Wrong path.** `[V]` No `dist/` in the repo (build output only). Committed built copies: `.claude/skills/impeccable/` and `.agents/skills/impeccable/` (plus 18 other harness folders). The README still shows `cp -r dist/claude-code/.claude` (L187). |

## 1. Built skill folder

`[V]` **Claude Code** `.claude/skills/impeccable/`: 57 files, ~2.1 MB.
- Prose: `SKILL.md` (12.5 KB) + 45 files under `reference/` (~424 KB; largest `new-work.md` 61 KB, `critique.md` 43 KB, `live.md` 36 KB).
- `scripts/` (11 files, ~1.7 MB): `impeccable` (POSIX `sh` launcher, 8.5 KB, the only file with mode 755), `impeccable.cmd`, `VERSION` (`0.1.14`), `command-metadata.json`, `data/font-index.json` (1.1 MB data), and five browser-side JS files for live mode (`live-browser.js` 548 KB, `modern-screenshot.umd.js`, ...). No Node scripts run on the host.
- Outside the folder: 4 sub-agent definitions in `.claude/agents/`, hooks in `plugin/hooks/hooks.json`.

`[V]` **Codex** `.agents/skills/impeccable/`: same content, 62 files; adds `agents/*.toml` (4 sub-agents) and `agents/openai.yaml`. Hooks: `.codex/hooks.json`.

## 2. Executable pieces

- **Launcher** `scripts/impeccable` `[V]`. Triggered by `SKILL.md` Setup step 1 (`impeccable context`, "once per session"), by every verb in the reference files, and by hooks. Resolution order: `$IMPECCABLE_BIN`, `scripts/bin/<os>-<arch>/impeccable`, `~/.impeccable/bin/impeccable`, `~/.impeccable/bin/<version>/`, `PATH`, then **download** with `curl`/`wget` from `https://github.com/pbakaus/impeccable/releases/download/engine-v0.1.14/impeccable-linux-x64` plus its `.sha256`, into `~/.impeccable/bin/0.1.14/`, then `exec` (L121-196). The checksum comes from the same origin: integrity, not authenticity `[I]`.
- **Hooks** `[V]`. Claude: `SessionStart`, `PostToolUse` (matcher `Edit|Write`, 5 s), `Stop` (30 s). Codex: `PostToolUse` (`Edit|Write|apply_patch`), `Stop`. All run `<launcher> hook`. The hook reads the event JSON on stdin, the edited UI file, `.impeccable/config*.json`, `DESIGN.md`; writes `.impeccable/hook.cache.json`, `hook.pending.json`, optional audit log; returns a reminder to the agent. `crates/hook`, `detect`, `html`, `core`, `foundation` contain no HTTP client and spawn no process (grep at the tag).
- **`context`** reads `PRODUCT.md`, `DESIGN.md`, surface briefs; runs the daily version check (below); writes `~/.impeccable/update-check.json`.
- **Process spawns elsewhere** `[V]`: `git` (signals, live), installed Chrome/Chromium/Edge over CDP (URL scans, captures), `claude` CLI and `node` (live mode copy edits), `/bin/sh` for `package.json` `scripts["impeccable:manual-edit-validate"]` (live mode; README warns about it), `xdg-open`.
- **Local servers** `[V]`: live mode, `serve-question`, `component-review`, capture service; all bind `127.0.0.1`.

## 3. Network requests (engine source)

| Destination | Trigger | Payload |
|---|---|---|
| `github.com/.../releases/download/engine-v<ver>/...` | Launcher, first use without a local binary | none (GET) |
| `impeccable.style/api/version` | `impeccable context`, at most once per 24 h | none (GET); off with `IMPECCABLE_NO_UPDATE_CHECK` or `updateCheck:false` |
| `impeccable.style/api/roll` | `concept-seed` (new-work flow, only after `PRODUCT.md` exists, only when no local catalog; none is shipped) | query: `scope`, `key`, `reroll`, optional `mode`, `grain`, `platform` |
| `impeccable.style/api/chosen` | agent reruns `concept-seed --kind ...` after the user chooses | JSON: `chosenId`, `key`, `scope`, `mode`, `kind`, `register` |
| `impeccable.style/api/commands`, `/api/download/bundle/universal` (redirects to a GitHub release; Ed25519 signature checked) | `help`, `install`, `update`, `check` | none |
| `api.openai.com/v1/images/...` | `generate-image`, **only if `OPENAI_API_KEY` is set** | the image prompt and reference images |
| `fonts.googleapis.com` | loaded by the browser from generated scaffold/decision pages | font family names |

`[V]` `key` is a random 8-hex value unless overridden (`concept_seed.rs` L646-650: `.unwrap_or_else(random_hex8)`). No call site sends file contents, paths, repository names or conversation text to impeccable.style. The exception by design is `generate-image` to OpenAI.

**Opt-out, exact code** (`crates/context/src/concept_seed.rs`):
- L180-181: `fn telemetry_disabled(env) { env.get("IMPECCABLE_NO_TELEMETRY")... || env.get("DO_NOT_TRACK")... }`
- L186: `if telemetry_disabled(env) { return false; }` sits inside `ping_chosen` only.
- L150-166 `fetch_roll` has no such check: `let url = format!("{}/roll?{}", api_base(env), qs.join("&"));`.

So the earlier claim is accurate for the roll GET: with telemetry disabled it is still sent, carrying scope, mode, the random key and a re-roll counter (the upstream text at `seed_text.rs` L29 says the same). It discloses the VM's IP and that a new-work round started; nothing about the project.

## 4. The detector

- Code: `crates/detect` (file walk, config, regex engine), `crates/html` (static HTML/CSS cascade), `crates/core` (rules), `crates/browser` (URL engine) `[V]`.
- Dependencies: the npm package `impeccable` has **0 dependencies** and 5 optional platform packages carrying the binary `[V registry]`. Rust: `Cargo.lock` lists 209 packages for the whole workspace; notable: `ureq`+`rustls`, `tiny_http`, `tungstenite`, `html5ever`/`scraper`/`cssparser`, `image`, `ring`, `zip`.
- Reads: source files or directories (`.html`, `.css`, `.jsx/.tsx`, `.vue`, `.svelte`, `.astro`, ...). No browser and no network for file scans `[V by grep]`. URL scans need an installed Chrome/Chromium/Edge.
- Output: human text on stderr, `--json` on stdout.
- React/MUI: source-text heuristics cover JSX, Tailwind classes, styled-components and `sx={{...}}` props `[V, tests in regex_matchers.rs, detect_text.rs]`. No `createTheme` handling found (zero hits). "Design-system" rules compare against `DESIGN.md` / `.impeccable/design.json`, not a MUI theme. For a MUI app, rendered truth needs the URL scan `[I]`.
- Offline at a pinned version: yes `[V launcher L41-62]`. Put the binary at `scripts/bin/linux-x64/impeccable` or set `IMPECCABLE_BIN`; the launcher then never downloads. `docs/ENGINE.md` also states it builds offline from source (`cargo build --release -p impeccable`).

## 5. Prose only (B): what still works

- **Pure instructions** `[V, no engine verb in the file]`: `shape`, `init`, `extract`, `audit`, `bolder`, `quieter`, `distill`, `harden`, `onboard`, `animate`, `colorize`, `typeset`, `layout`, `delight`, `overdrive`, `clarify`, `adapt`, `optimize`, plus `craft-floor.md` (bans and quality floor).
- **Degraded**: `critique` (requires `detect --json` and `critique-storage`; treats a missing detector as tolerated), `polish` (`critique-storage`), `document` `[I]`, routing menu (`signals`).
- **Do not work**: `live`, `generate`, `hooks`, `doctor`, `pin`, component review, and the new-work decision pipeline (`concept-seed`, `serve-question`, `build-phase`, `comp-spec`, `comp-diff`, `font-match`, `generate-image`, `embed-prompt`). `new-work.md` L48 calls the roll "No substitute, no skip", so B needs a local override note.
- `SKILL.md` step 1 calls the launcher; it documents a fallback ("Launcher unavailable": read `PRODUCT.md`/`DESIGN.md` directly).

## 6. State written into a project

`[V README L354-394]` `PRODUCT.md`, `DESIGN.md`, and `.impeccable/`: tracked `config.json`, `design.json`, `surfaces/*.md`, `critique/*.md`, `live/config.json`; ephemeral `config.local.json`, `hook.cache.json`, `hook.pending.json`, `questions/roll.json`, screenshots, live sessions. Also `~/.impeccable/` (binary cache, update cache). None of it is uploaded by any call site found; `generate-image` is the only path that sends project-derived content off the machine.

## 7. Maintenance signals

- `[V]` Cadence of `skill-v*` tags: June 4, July 7, August 3, September 7, October 4 so far. Fifteen `engine-v*` tags exist.
- `[V]` Diff 4.5.1 to 4.5.2: 12 commits, 171 files, +848/-273 repo-wide, but only 5 files, +7/-7 inside `.claude/skills/impeccable/`. 4.4.0 to 4.5.0: 9 skill files, +78/-14. (4.5.0 to 4.5.1: 448 commits; the API caps the file list at 300.)
- `[V]` Maintainers: one dominant author (pbakaus, 1,808 commits), one regular contributor (216), bots. npm: a single maintainer account.
- `[V]` Published security advisories: 0. No `SECURITY.md` on `main`. Open issues and PRs: 76; one mentions "security" and is not a vulnerability.
- `[V]` npm `impeccable@4.5.2` and `@impeccable/cli-linux-x64@0.1.14`: registry signatures only, **no provenance attestation**. Engine release built by GitHub Actions; `release-engine.yml` signs the Windows binary only; no build attestation step found.

## What Benjamin needs to decide

**A. As is (hooks + launcher).** A 20 MB third-party binary runs on the VM on every UI edit and at every stop, with the session's file access, next to private source. It leaves: a daily version check, the roll GET and choice ping in new-work, and prompts/images to OpenAI if a key is present. Gain: automatic detector feedback, decision pages, live mode. Cost: the read-only reviewer and evaluator sandboxes cannot download or write the cache `[I]`; a new binary to re-trust roughly weekly; the binary itself was not verified against the source.

**B. Prose only.** Nothing runs, nothing leaves. Gain: the 18 instruction commands and the craft floor, reviewable as text, small diffs between tags. Loss: the detector, hooks, live mode, and the new-work decision flow. Upkeep: re-pin and diff ~440 KB of Markdown when wanted; delete `scripts/` and add a short local note so agents take the documented fallback instead of calling the launcher.

**C. Not at all.** No cost, no gain.

**Recommendation: B**, pinned at `d631a882`, without `scripts/`. Main risk: the prose assumes the engine, so agents may still try the launcher or follow the "no skip" roll instruction; the local note must say plainly that the engine is absent. Later option `[I]`: vendor the binary for the builder role only and run `detect --json` on files, offline via `IMPECCABLE_BIN`, as an explicit step.

## Not verified

- That the released binary matches the source (no reproducible build or attestation checked).
- What impeccable.style logs server-side.
- Exit codes and hook behaviour in execution (read, not run).
- Whether `document` needs the engine; behaviour inside Codex read-only sandboxes.
- Dates of `engine-v*` tags; dependency vulnerability status of the 209 crates.

## Sources (all at `skill-v4.5.2` / `d631a882` unless noted)

`README.md`, `package.json`, `Cargo.toml`, `Cargo.lock`, `ENGINE_VERSION`; `skill/scripts/impeccable`; `cli/bin/cli.js`; `.claude/skills/impeccable/SKILL.md` and `reference/*.md`; `skill/reference/hooks.md`, `new-work.md`; `.claude/settings.json`, `.codex/hooks.json`, `plugin/hooks/hooks.json`; `crates/cli/src/main.rs`; `crates/context/src/{concept_seed,seed_text,context_cli,generate_image,http,serve_question}.rs`; `crates/skills/src/{bundle,commands,engine_binary,providers}.rs`; `crates/hook/src/{hook,hook_lib}.rs`; `crates/detect/src/{cli,engines,design_system,regex_matchers}.rs`; `crates/live/assets/antipatterns.json`; `docs/{ENGINE,CLI-CONTRACT,BUNDLE-SIGNING}.md`; `.github/workflows/release-engine.yml`. Live on 2026-10-13: GitHub API (tags, compare, contributors, security-advisories, release `engine-v0.1.14`), `registry.npmjs.org/impeccable`.
