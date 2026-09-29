# A6 "Parallel delivery" — fact sheet (read-only, 2026-09-29)

Paths are relative to `/home/benja/agent-factory` (AF) unless prefixed `SMN:` (C:\Dev\Projects\SayMyName).
Nothing was modified. Only `gc bd show`, `gc mail send --help`, `git log/show`, `gh api/pr view` (GET) and `ps/free` were run.

## 1. Worktree isolation (`bin/factory-do-work-workspace`, `formulas/mol-do-work.formula.toml`)
- **When:** `enter` isolates only if the repo's *current branch* equals the protected branch in `config/projects/*.toml` (via `lib/protected_rigs.sh:22-25`); otherwise it prints `.` and the work happens in the cwd (`bin/factory-do-work-workspace:124-140`). FACT
- HQ: `config/projects/agent-factory.toml` (rig_dir `.`, main, sling_target `factory-worker`); worker `work_dir = ".gc/agents/factory-worker"` sits inside the live root, which is on `main` → worktree. Product rigs: `rigs/saymyname-{backend,frontend}` checkouts are on `dev` (live: `git worktree list`) → worktree too since af-09hxz (header :16-22). So today **every mol-do-work dispatch on all 3 rigs gets a worktree**. FACT
- Other formulas allowed on product rigs (`mol-scoped-work`, `mol-polecat-commit`, `build-basic` → `bin/factory-shared-drain-workspace`) were not audited here. UNKNOWN
- **Path/branch:** `$HOME/.local/share/agent-factory-runtime-worktrees/<bead-id>`, branch `do-work/<bead-id>` (:142-143). One shared root for all rigs; bead prefixes differ (af/smb/smf) so no cross-rig name clash. FACT
- **Base:** branched off the *local* protected branch (`worktree add -b $BRANCH "$CURRENT_BRANCH"`, :160), not `origin/<base>`; the `fetch --prune` at :151 does not advance it. Freshness relies on factory-guard fast-forwarding the live root (`bin/factory-guard:195`) and rigs (:232). Live check now: root main = origin/main 6f20ca3, rigs dev = origin/dev. FACT
- **Concurrency of `enter`:** no lock at all (no `flock` in the script). FACT. Risks for 2 simultaneous calls on the same repo (inference, not observed):
  - concurrent `git fetch --prune origin` on one repo (:151) can hit ref-lock errors — swallowed by `|| true`;
  - `git config extensions.worktreeConfig true` writes the shared `.git/config` (:103) — a lock collision makes `install_post_commit_push_hook` return silently → **no auto-push hook** for that worktree (O04 guarantee lost silently);
  - same bead twice: check-then-create race on `[ -d "$WT" ]` (:145) → second call exits 1.
  - distinct beads → distinct dirs/branches: `worktree add` itself is safe.
- **Rebase before PR:** only when the branch push fails, up to 2 rebases on `origin/<base>` (:191-199). No pre-PR sync with base otherwise. FACT
- **Cleanup:** `finish` removes the worktree after a successful push (:233-235, never rm -rf); `restart <reason>` removes worktree + local/remote branch (:255-267); `factory-maintain clean-worktrees` removes clean+pushed+merged ones (`bin/factory-maintain:150-212`) but **no order schedules it** (grep `orders/`: none); factory-guard 6b backs up/reports, never removes (`bin/factory-guard:505-512`); guard also prunes dangling entries (:446-449) and removes idle worktrees pinning a branch to delete (:487). FACT
- **Live residue:** 9 `do-work/af-*` worktrees from 2026-09-18 + `autonomy-frontier-20260922` still under the runtime root. FACT

## 2. Test isolation from the live city
- Inventory: 72 tests (`tests/*.sh|*.py`); CI runs 67. Not in CI: `backup-freshness-order-test.sh`, `build-basic-fail-fast-runtime-test.sh`, `factory-watchdog-order-test.sh`, `local-only-tests-order-test.sh`, `orders-validate-test.sh`. FACT
- 3 of those run nightly via `orders/local-only-tests.toml` → `bin/local-only-tests:36-40` (build-basic runtime, watchdog-order, orders-validate). FACT
- Tests calling the **real** `gc` with no stub:
  - `factory-watchdog-order-test.sh:7`, `orders-validate-test.sh:31`: `gc order show … --city "$ROOT"` → read the live city (read-only). FACT
  - `build-basic-fail-fast-runtime-test.sh:44-62`: real `gc init` + `bd`/dolt on a throwaway TEST_CITY (default provider codex). FACT
  - `backup-freshness-order-test.sh`, `local-only-tests-order-test.sh`: real gc with `env -u GC_CITY -u GC_CITY_PATH …` (:73-82 / :65-74); since #268 (979c1a7) `codex` shadowed by a stub, `TMUX_TMPDIR` isolated, EXIT trap kills tmux. FACT
  - `coordination-pointer-doors`, `delivery-formula-contract`, `build-basic-publish-overlap-followup`: text greps only, no execution. FACT
- Stub usage: `GC_BIN` in 13 tests, `PATH=` override in 24, `FACTORY_ROOT` in 31, `HOME=` in 3 (`factory-do-work-workspace-test`, `factory-guard-runtime-worktree-test`, `factory-maintain-test`), `BEADS_DIR` in 1. FACT
- Shared fixture: `tests/fixtures/fake-gc.py` (and `fake-gh.py`) — at `tests/fixtures/`, **not** `shared-drain/`; used by one test only (`factory-shared-drain-workspace-test.sh`). Fixture City oracle runs sandboxed in bwrap (`tests/fixture-city-oracle-test.py`, `config/fixture-city-bwrap.apparmor`, ci.yml "Ensure fixture sandbox runtime"). FACT
- Live root path hard-coded in 5 tests: backup-freshness-order, factory-watchdog-order, local-only-tests-order, operator-context-test.sh, factory-doctor-test.py. FACT
- **No guard fails a test that touches the live city** (grep found none). The only live guard is the git hook refusing commit/checkout -b/reset in the live root (`tests/factory-live-root-guard-test.sh:50-136`). Past leaks fixed one by one: #265 (router test mailed the Mayor), #268 (real Codex sessions held the escalation-door flock 40+ min), #279 (ticket-graph-publish notify). FACT
- **Worker vs CI:** mol-do-work `do-work` step says "run the verification commands requested by the bead … else the smallest relevant local test/build check" (formula, do-work step ¶2) — no fixed battery; the full suite runs only in CI (`.github/workflows/ci.yml`, job `Tests`, on PR→main and push main). FACT

## 3. pr-autopilot and GitHub merge rules
- Order: cooldown 3 m, timeout 120 s (`orders/pr-autopilot.toml`). FACT
- **Red checks:** retry once (`retry_ci_failure`, `bin/pr-autopilot:365-368`), then file P1 bead `[ci] PR #n failed required checks`, do not arm (:370-383); closes that bead when checks recover (:362). FACT
- **DIRTY / BEHIND / BLOCKED-with-nothing-pending / no checks:** `stuck_reason` (:201-213); pass 1 labels `autopilot-stuck`, pass 2 files `[autopilot] PR #n stuck` bead + PR comment (:245-270); "never resolves a conflict or forces a check" (:258). Evaluated independently of arming (:386-390) → a BEHIND PR is still armed and, strict being off, merges. **No `update-branch` / rebase anywhere.** FACT
- `allow_update_branch: false` on all 3 repos (`gh api repos/…`); `allow_auto_merge: true`, `delete_branch_on_merge: true`. FACT
- Rulesets (all `strict_required_status_checks_policy: false`, no merge-queue rule): FACT
  - agent-factory `AF-main-protection` (23626687): main, check `Tests`.
  - Say-my-name-back `SMN-back-dev-protection` (22629508): dev, check `Maven verify`; plus classic protection on `main` (contexts [], strict false).
  - Say-my-name-front `SMN-front-dev-protection` (22629678): dev, check `Tests and build`.
- **Why strict off on 2026-09-17:** nothing in AF git log/docs (searched `strict`, `up to date`, `update_branch`). UNKNOWN in the Factory repo. Only source: `SMN:knowledge/decisions.md:157-160` — "a behind PR stayed stuck with nothing to update it" (Benjamin, 2026-09-28); proposal bead `af-i3prh` is open. FACT (as recorded recollection)

## 4. Product repos
- `rigs/saymyname-backend` → `saymyname-app/Say-my-name-back`, `rigs/saymyname-frontend` → `saymyname-app/Say-my-name-front`; base `dev` (`city.toml:198-212` `default_branch = "dev"`, `config/projects/*.toml protected_branch = "dev"`, GitHub default_branch dev). FACT
- `gh` reads their settings and rulesets fine (see §3). FACT
- Naming drift: `config/projects` `required_ci` = workflow names ("Backend CI"/"Frontend CI"/"Factory CI") vs ruleset contexts (`Maven verify`/`Tests and build`/`Tests`). Whether pr-autopilot maps them correctly was not checked. UNKNOWN

## 5. "One writer per rig" — every place to change for N workers
Enforcement is **only** the pool caps; `bin/dispatch-door` has no busy-rig check (grep). FACT
| Place | Content |
|---|---|
| `agents/factory-worker/agent.toml` | `max_active_sessions = 1` (HQ writer singleton) |
| `tests/factory-work-dispatch-test.sh:56` | asserts `max_active_sessions = 1` ("factory-worker is not a singleton") |
| `city.toml:241` | `[[patches.agent]] claude` city pool `max_active_sessions = 2` |
| `city.toml:245-246` / `:250-251` | claude pool for backend / frontend `= 1` |
| `city.toml:227-237` | rationale comment (2026-09-18 RAM incident) |
| `agents/mayor/prompt.template.md:51` | "in dependency order, one writer per rig" |
| `agents/mayor/prompt.template.md:125-126` | "One writer per rig at a time — a second writer on the same rig shares its checkout" (now false for mol-do-work: worktree per bead) |
| `formulas/mol-do-work.formula.toml:6-11` | "single-agent work; for multi-agent … use mol-polecat-commit" |
| `docs/DELIVERY.md:5`, `:40` | V1 one writer; multiple writers "TARGET, not PROVEN" |
| `docs/SECURITY.md:12` (+14-20 canary rule per prior research) | "One writer per rig." |
| `AGENTS.md:60`, `README.md:65` | one writer per rig until isolation proven by canary |

## 6. Conflict hotspots and A5 PRs
- Last 100 first-parent commits on origin/main (2026-09-21..29), files by PR count: `ci.yml` 41, `docs/CONTEXT_INDEX.md` 31, `docs/FACTORY_TOOLS.md` 17, `bin/factory-guard` 17, `docs/DELIVERY.md` 12, `bin/pr-autopilot` 12, then 9 each `tests/provider-failover-test.py`, `bin/planning-run-router`, `bin/factory-watchdog`; 8 each `tests/ticket-graph-publish-test.py`, `tests/mayor-campaign-test.py`, `lib/factory_watchdog.py`, `bin/ticket-graph-publish`, `agents/mayor/prompt.template.md`, `AGENTS.md`. FACT
  → the 3 append-style registries (ci.yml step list, CONTEXT_INDEX, FACTORY_TOOLS) are the structural hot files.
- A5 PRs #257-#282 (merged 2026-09-28 15:29 → 2026-09-29 00:49 Paris, serially, 1 worker): 25 merged, #263 closed (duplicate of af-mbpt1, superseded by #258). FACT
  - #258 and #263 contain a "Merge remote-tracking branch 'origin/main'" commit → caught up with main by hand (behind/conflict likely). #274 force-pushed once. #277 has a `capture remaining work` commit. FACT
  - No PR ever got the `autopilot-stuck` label → none stayed DIRTY/BEHIND/BLOCKED for 2 passes. FACT
  - Per-PR historical mergeStateStatus (was it BEHIND at merge time?) is not kept by GitHub. UNKNOWN

## 7. Mail sender shows `human`
- Decided inside the external `gc` binary (`/usr/local/bin/gc`, not in the repo): `gc mail send --help` — sender defaults to `$GC_SESSION_ID`, `$GC_ALIAS`, `$GC_AGENT`, else `"human"`; `--from` is validated against live sessions or `human` (`bin/pr-autopilot:577-583`). FACT
- An operator/PO agent reaching WSL via `wsl … bash -l` has no `GC_*` env (checked: none set) → `human`. Same for pr-autopilot since af-4ruvv dropped `--from`. FACT
- Drift: `docs/DELIVERY.md:176` still says the sender is explicitly `pr-autopilot`, never `human` — false since af-4ruvv. FACT

## 8. Per-worker RAM
- No per-worker measurement exists. FACT. The 2026-09-18 load test (af-48sx3 → af-liak1, PR #133, `docs/LOAD_TEST_2026-09-18.md`, now moved to legacy by #249) measured host load, deferred the N=6/8 sweep, gave no per-session RSS.
- Available data: `city.toml:227-231` (4 workers + reviewer + Maven/Testcontainers → ~500 MB free, load 15-20 on 12 vCPU); `SMN:knowledge/decisions.md:154-157` (WSL capped at 8 GB, 5.4 GiB available with 1 worker).
- Snapshot now (2026-09-29, no worker active): WSL total 7940 MiB, available 5219 MiB; Mayor `claude` CLI RSS ≈ 476 MiB; `dolt sql-server` ≈ 1.27 GiB; `gc supervisor` ≈ 133 MiB. So one agent CLI ≈ 0.5 GiB **before** its test runs; Maven/Testcontainers cost per product worker is UNKNOWN.
