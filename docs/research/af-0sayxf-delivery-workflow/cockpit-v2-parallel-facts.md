# Cockpit V2 (convoy `af-f71cgu`): parallel-work friction and host capacity — facts

Read-only study, 2026-10-05. Factory suspended; nothing was started, dispatched or edited. Factory root at
`112c286` (`git log -1`). All times Europe/Paris (CEST, UTC+2); sources in UTC were converted.

Evidence tags: **TR** = worker transcript `/home/benja/.claude/projects/-home-benja-agent-factory--gc-agents-factory-worker/<sid>.jsonl`
(session id given by its first 8 characters); **PR** = `gh pr view <n> --json files,commits,createdAt,mergedAt`;
**CI** = `gh api repos/saymyname-app/agent-factory/actions/runs/<id>/attempts/<n>` and the job log;
**BD** = `bd show <id> --json`; paths are relative to `/home/benja/agent-factory`.

Convoy window used everywhere: 30/09 17:55:21 (convoy `created_at`) to 01/10 04:42:41 (convoy `closed_at`) = 647 min (10 h 47).

---

## A. Friction of parallel work

### A.0 Three mechanisms that explain most of what follows

| Mechanism | Evidence |
|---|---|
| `main` requires the PR branch to be up to date with `main` before merge | Ruleset `AF-main-protection` (`gh api .../rulesets/23626687`): `required_status_checks.strict_required_status_checks_policy = true`, one required check `Tests`. `bin/pr-autopilot:171-181,881-896`: a BEHIND PR is never armed; at most one BEHIND PR per tick is updated through `PUT .../update-branch`. |
| Every merge to `main` therefore sends every other open PR through one more "merge main + full CI" cycle | 38 `Merge branch 'main' into …` commits on the 33 PRs #348-#380 (PR commit lists); e.g. T19 #373: 3, T16 #360: 3 kept after rebase plus `e946e18`, T11 #355: 2. CI run: median 6.1 min over 114 runs in the window (`gh run list --workflow "Factory CI"`). |
| A red required check after one automatic retry, or a DIRTY (conflicting) PR, reopens the ticket and a new worker session is dispatched | `bin/pr-autopilot:529-537,621,698-703,855`; bead metadata `gc.pr_rejection_count` / `gc.pr_rejection_reason`. |

### A.1 The 9 re-dispatches, one by one

Ticket-level counters (BD): T16 `af-53v22s` `gc.pr_rejection_count=5`; T19 `af-95l8ki` =1; T24 `af-j2mkpa` =1 plus two side beads
`af-6c0xm9` and `af-3hmxgn` ("[ci] PR #372 failed required checks on main", `source=pr-autopilot`).

| # | Session (Paris) | Ticket / PR | Trigger recorded on the bead | What it actually was | Files / counterpart |
|---|---|---|---|---|---|
| 1 | `05d20efa` 30/09 21:00-22:01 (61 min) | T16 #360 | `gc.pr_rejection_reason: conflict with main@a8c5817fe5ab` (count 1) — `a8c5817` is the merge of T12 #359 (20:27) | **Textual merge conflict.** `git rebase origin/main` at 21:02: `CONFLICT (content)` in 4 files. 55 of the 61 minutes were spent waiting for a local full-suite run that the worker finally killed (21:07 to 21:59; its text: "heavy system contention from many concurrent agent sessions"). | `lib/cockpit/core/process.py` (vs T13 #361), `lib/cockpit/core/readmodel.py` (vs T12 #359), `lib/cockpit/core/server.py` (vs T12 and T13), `lib/cockpit/ui/base/page.py` (vs T12). `config.py` auto-merged. |
| 2 | `ef7b5d31` 22:39-22:56 (17 min) | T16 #360 | `required check Tests failed after one retry` (count 2) | **Two causes at once.** (a) CI run `36769743453` on `e946e18` (the update-branch merge made at 22:01 after T14 #363 merged at 21:52) failed on `tests/cockpit-actions-test.py::test_a_faire_reported_hides_then_returns_at_deadline` — the flaky test. (b) By 22:41 the PR was also `mergeable: CONFLICTING`. | (b) `lib/cockpit/ui/base/page.py` vs T25 #367 (merged 22:35): T16's `extra_sections_html`/`extra_css` parameters vs T25's disconnected banner. |
| 3 | `ba332bf2` 23:11-23:35 (24 min) | T16 #360 | same reason (count 3) | **Semantic collision, not textual.** CI runs `36776660984` (head `ac2935b`, update-branch merge of 23:01) and `36779093671` failed on 3 tests of `tests/cockpit-health-test.py`. Cause found by the worker at 23:29: #368 (`fix/cockpit-closed-needs-benjamin`, merged 22:59, a maintenance PR outside the convoy) made the beads source issue a second `bd list --all --has-metadata-key gc.needs_benjamin` call; T16's fixture `tests/fixtures/cockpit/health/fake-bd-health` did not answer it. The merge was textually clean. The session first followed the dispatch text ("harden a flaky `wait_until()`") and pushed a timeout change `66623dc` that failed CI again (23:31) before the real fix `fbe8399` (CI green 23:41). | `lib/cockpit/core/beads_source.py`, `lib/cockpit/core/process.py` changed by #368; fixture owned by T16. |
| 4 | `fd2333c9` 23:34-23:40 (6 min) | T16 #360 | same reason (count 4) | **Duplicate dispatch.** The rejection counted was the red run on `66623dc`, an intermediate commit of session 3, which was still running (overlap 23:34-23:35). The session found the work already pushed, re-ran tests, changed nothing. | none |
| 5 | `1a8b70db` 23:49-00:02 (14 min) | T16 #360 | same reason (count 5) | **Flaky test.** Run `36780468813` attempt 1 on `7c42596` (update-branch merge after T04 #356 merged 23:31) failed on the same `cockpit-actions` test. The worker re-ran the job: attempt 2 green at 00:00. One more update-branch (`36600d2`, after T15 #369 at 00:00), green 00:10, merged 00:16. | no code change |
| 6 | `f087f260` 01/10 01:29-01:37 (8 min) | T19 #373 | same reason (count 1) | **Flaky test.** Run `36789609245` on `05e0438` failed on the same `cockpit-actions` test. The worker confirmed 2/2 local passes and that its diff does not touch the file; no change. The PR then stayed red and untouched from 01:37 to 03:06, until the operator-side fixes #374/#375/#378 landed; 3 update-branch merges (03:06, 03:12, 03:22), merged 03:31. | no code change |
| 7 | `540f09fd` 01:29-01:50 (21 min) | T24 #372 | same reason (count 1) | **Flaky test.** Run `36788068757` on `6a97166` (update-branch merge after T05 #371) failed on the same test; the worker re-ran it (attempt 2, failed again 01:46), then closed the step as blocked (`gc.blocked_classification=repair`) and mailed. | no code change |
| 8 | `ac7cfb88` 02:07-02:17 (9 min) | side bead `af-6c0xm9` on PR #372 | pr-autopilot CI-failure bead | **Flaky test, first repair attempt.** Widened the test's waits to 15 s (`4266a75`), pushed onto T24's branch. CI run `36795195349` failed again on the same test (02:21). | `tests/cockpit-actions-test.py` (declared scope of T13, not of T24) |
| 9 | `8645ef70` 02:34-02:50 (16 min) | side bead `af-3hmxgn` on PR #372 | second pr-autopilot CI-failure bead for the same PR | **Flaky test, second repair attempt** (`a2d0544`: force `/api/health/recheck` before polling). CI green 02:55, merged 02:55. A second bead for one PR is the class fixed afterwards by #374 ("one CI-failure bead per PR"). | `tests/cockpit-actions-test.py` |

Totals: 1 textual conflict alone (#1), 1 conflict + flaky (#2), 1 semantic collision with a non-convoy maintenance PR (#3),
1 duplicate dispatch (#4), 5 flaky-test only (#5-#9). Sum of the 9 sessions: 176.8 min.

The flaky test: `test_a_faire_reported_hides_then_returns_at_deadline`, added by T13 #361 (merged 20:59). It failed 8 CI attempts in
the window, all with that single failure: on `main` itself twice (push runs `36765160206` after T17 at 21:22 and `36776497723` after
#368 at 23:00) and on PRs of T16 (2), T24 (3), T19 (1). It was fixed for good by #375 (03:20, "no longer races a sub-second
window"). It is a timing race inside one test process; none of the failing diffs touched the code under test.

Not a re-dispatch but the same order of delay: T04 #356 was open 19:45 to 23:31 (226 min) because pr-autopilot holds any PR adding a
project descriptor for Benjamin (label `project-declaration-needs-benjamin`; draft `out_of_graph`: "Benjamin, pendant la livraison :
revue et fusion du PR retenu de T04"). T04 blocks T05 and T15, hence T19, T20, T22, T23, T24.

### A.2 Files touched by more than one ticket

From the merged PR file lists of the 24 ticket PRs (script over `gh pr view --json files`):

| Count | File | Tickets | In whose declared scope |
|---|---|---|---|
| 4 | `lib/cockpit/core/config.py` | T11, T13, T14, T16 | T11 only (`lib/cockpit/core/**`) |
| 4 | `lib/cockpit/core/process.py` | T11, T13, T14, T16 | T11 only |
| 4 | `lib/cockpit/core/server.py` | T11, T12, T13, T16 | T11 only |
| 4 | `lib/cockpit/ui/base/page.py` | T11, T12, T16, T25 | T11 and T25 (`lib/cockpit/ui/base/**`) |
| 3 | `lib/cockpit/ui/base/tokens.py` | T11, T13, T25 | T11, T25 |
| 3 | `docs/COCKPIT.md` | T11, T18, T23 | T11 |
| 3 | `lib/cockpit/ui/projects/page.py` | T19, T20, T22 | T19, T20 |
| 2 | `core/readmodel.py` (T11, T12), `core/freshness.py`, `core/polling_source.py` (T11, T16), `requests/builder.py`, `requests/model.py`, `ui/home/page.py` (T12, T13), `actions/registry.py`, `ui/actions/render.py` (T13, T14), `tests/cockpit-actions-test.py` (T13, T24), `projects/{builder,model,stage}.py` (T19, T20), `ui/projects/tokens.py` (T19, T22), `stop/driver.py`, `ui/stop/render.py` (T23, T24), `bin/escalation-door`, `agents/mayor/prompt.template.md` (T06, T07), `tests/factory-orphan-sweep-order-test.sh` (T09, T10) | | |

Non-convoy PRs merged in the same window also touched hot files: #368 (`core/process.py`, `requests/builder.py`, `core/beads_source.py`),
#375 (`tests/cockpit-actions-test.py`).

Were the sharing tickets concurrent? Window of a ticket = first session start to PR merge. Of the 23 ticket pairs that share at least
one file, **4 overlap in time, and all 4 involve T16**: T16×T12 (24 min), T16×T13 (29 min), T16×T14 (30 min), T16×T25 (39 min).
The other 19 pairs were already sequential through `blocked_by` (e.g. T11→T12→T13→T14, T19→T20→T22, T23→T24). T16's own window was
265 min (19:51 to 00:16) because of the re-dispatches, which is what exposed it to four successive merges.

### A.3 The publish-time overlap mechanism, and why it did not catch these

How it decides (`bin/ticket-graph-publish:163-225`, introduced by `a204b45`, P11, 2026-09-29):

- `scopes_overlap(a_paths, b_paths)`: true if any pattern of A equals a pattern of B, or `fnmatch(pattern_a, pattern_b)` or
  `fnmatch(pattern_b, pattern_a)`. It compares the **declared pattern strings** of two tickets against each other; it never looks
  at a file list.
- `add_scope_overlap_edges`: for each ticket, against each earlier ticket in declaration order, skip if either has no scope or if
  one already reaches the other through `blocked_by` (transitively); otherwise, if scopes overlap, the later ticket becomes
  `blocked_by` the earlier one.
- A second, dispatch-time mechanism exists: `bin/dispatch-door:232-256` defers a ticket whose declared scope touches a path of
  `config/hot-paths.json` already held by an in-progress ticket. That file lists only `city.toml` and `**/V*__*.sql`; no cockpit path.

What happened for C01:

- **The mechanism added zero edges.** The draft bead `af-i67vl0` (YAML) and the published beads carry identical `blocked_by` for all
  25 tickets; every pair with overlapping declared patterns (T06/T07, T11/T25, T12/T15, T13/T14, T13/T25, T18/T23, T19/T20, T23/T24)
  was already ordered by an authored `blocked_by`.
- **The conflicting pairs had no declared overlap.** T16 declared `lib/cockpit/health/**, lib/cockpit/ui/health/**,
  tests/cockpit-health-test.py, tests/fixtures/cockpit/health/**`; T12 `requests/**, text/**, ui/home/**`; T13 `actions/**, access/**,
  ui/actions/**`. None of the three declared `lib/cockpit/core/**`; only T11 did.
- **The collisions were on files outside the declared scopes of both sides** (except `ui/base/page.py`, inside T25's scope):
  out-of-scope files in the merged PRs — T16: 6 (`core/config.py`, `core/freshness.py`, `core/polling_source.py`, `core/process.py`,
  `core/server.py`, `ui/base/page.py`); T13: 7 (`core/config.py`, `core/process.py`, `core/server.py`, `requests/builder.py`,
  `requests/model.py`, `ui/base/tokens.py`, `ui/home/page.py`); T12: 3 (`core/readmodel.py`, `core/server.py`, `ui/base/page.py`);
  T14: 2 (`core/config.py`, `core/process.py`). These are the "wiring" edits already described in `r-worker.md` §5.4.
- So both statements hold: the scopes as declared did not contain the files that wiring a module into the served app requires, and
  the workers that wired touched undeclared files. The 9 tickets that stayed inside their scope (not wired) produced no conflict.
- The Factory's own measurement recorded it: `.gc/runtime/overlap-conflict-log.jsonl` line 4, `kind: conflict`, `ticket_a: T12`,
  `ticket_b: T16`, `declared_overlap: false`, sha `3951b73` (T16's head), ts 30/09 20:32. That entry crossed the threshold
  "3 conflits PR sans chevauchement déclaré en 7 jours" and filed proposal `af-n4buwy` ("Proposer des leases dynamiques"),
  `gc.proposal_state: a_planifier`, answered by benjamin 01/10 03:48.

### A.4 How much was actually parallel

35 `factory-worker` sessions in the window (transcript first/last timestamp):

| Workers active | Minutes | Share of 647 min |
|---|---|---|
| 2 | 178.8 | 27.6 % |
| 1 | 269.6 | 41.7 % |
| 0 | 198.8 | 30.7 % |

- Sum of all session durations: 627.3 min. First runs (25): 449.8 min. Re-dispatches (9): 176.8 min. Drain-only (1): 0.7 min.
- Idle stretches with no worker (≥ 15 min): 22:22-22:39, 22:56-23:11, 01:10-01:29, 01:50-02:07, 02:17-02:34, 02:50-03:35 (44 min),
  03:57-04:18. From 22:22 to 23:31 everything not yet started was behind T04's human hold; from 01:10 to 03:31 everything left
  (T20, T22) was behind T19, itself stuck on the flaky test.
- Ready-but-not-started wait (ticket's last blocker merged → first session start), summed over tickets: 498 min, almost all before
  21:56 on 30/09 (T03 65, T09 57, T11 55, T08 51, T07 42, T25 34, T10 27, T14 24 min): at 18:09 six tickets were ready for 2 slots.
- PR created → merged, for the 20 tickets with one session and no hold: median 6.2 min, mean 7.3 min.

Estimate of a strictly sequential run (**estimate**, not a measurement):

- Method: sum of the 25 first-run session durations = 449.8 min, plus, for the 24 tickets with a PR, the median clean create→merge
  latency 6.2 min (one CI run, no update-branch since nothing else merges meanwhile) = 149 min. Total ≈ **600 min (10 h 00)**, against
  647 min observed with 2 workers. If the next ticket were started while the previous PR's CI runs, the floor is ≈ 450 min (7 h 30).
- Not included in either figure: T04's human hold (226 min observed; in a sequential run it stops everything after T04 except
  T06-T14, T16-T18, T25), and any flaky-test retries (the flaky test failed on `main` itself, so a sequential run would also have met it).
- Same method replayed on the dependency graph (durations = first run + 6.2 min, greedy by declaration order, no conflicts, no
  flaky test): 1 worker 597 min, 2 workers 304 min, 3 workers 208 min, 4 workers 177 min, unbounded 176 min (critical path). With
  T04's hold kept at its observed length: 815 / 413 / 388 / 388 min. This is a model; it ignores the update-branch cost per merge.

### A.5 Semantic (non-textual) collisions

| Finding | Concurrent? | Evidence |
|---|---|---|
| #368 changed the beads-reading contract (second `bd` call); T16's fake `bd` fixture, written before, broke 3 tests after a clean merge | Yes: #368 was written by an operator-side session (branch `fix/…`, Co-Authored-By Claude Opus 5.5) while T16's PR was open | re-dispatch #3 above; `git log -1 a339d0a` |
| T16 and T13 each added an HTTP JSON helper and POST handling to `server.py`; the rebase had to remove a "duplicate recheck/404/`_send_json` section" and keep one `_send_json(payload, status=200)` | Yes (T13 ran 20:30-20:54 while T16's PR was open) | TR `05d20efa` 21:03:13 |
| T16 and T25 both extended `render_home`/`page.py` with different extra parameters | Yes (T25 21:56-22:22) | TR `ef7b5d31` final summary |
| One test from T13 broke CI of T16, T19, T24 and `main` | Not a parallelism effect: it failed on `main` pushes too | A.1 |
| Each module has its own fake `bd`: 5 fixtures (`tests/fixtures/cockpit/{core,requests,actions,operator-actions}/fake-bd`, `health/fake-bd-health`); `def wait_until` is copied in 5 cockpit test files | T16's copy diverged from the `requests` one, which is what #368 exposed | `ls`, `grep -l '^def wait_until' tests/cockpit-*.py` |
| Same name defined in several modules of `lib/cockpit` (AST scan of top-level defs): `PARIS` ×5, `_hhmm` ×4, `SECTION_TITLE` ×4, `EMPTY_TEXT` ×3, `CSS` ×3, `NEEDS_BENJAMIN_KEY` ×3, `_stepper` ×2, `DRAFT_GRAPH_LABEL`/`APPROVED_GRAPH_LABEL` ×2, `PROPOSAL_LABEL` ×2 | Mostly between tickets that ran one after the other (T19/T20/T22, T12/T15), so this is per-ticket isolation, not concurrency; `health/` (T16) vs `ui/home` (T12) copies of `PARIS`/`_hhmm` were written concurrently | script output, 2026-10-05 tree |

No case was found of two concurrently running tickets defining the same public thing with different behaviour that survived to
`main`; whether the duplicated constants hold identical values was not compared.

---

## B. Capacity for more parallel writers on this host

### B.1 Where the cap of 2 comes from

| Place | Value | Why (as written) |
|---|---|---|
| `agents/factory-worker/agent.toml:5` | `max_active_sessions = 2` | Raised 1→2 by `395ca8e` (#309, P17 `af-puf4p`, 2026-09-29 13:08): "factory-worker's pool cap goes from 1 to 2 concurrent sessions on the agent-factory rig (product rigs stay at 1) … isolated worktree per dispatch, declared-scope/hot-file serialization ahead of dispatch (P08/P16), and pr-autopilot's return loop (P06) — so a rig's writer cap can rise once its isolation canary is proven, instead of being fixed at one." Created at 1 by `13435be` (#185, 2026-09-21). |
| `city.toml:259-271` | implicit `claude` pool: 2 at city scope, 1 per product rig | `5ba0ec5` (#103, 2026-09-18): pools were unlimited; "four city workers plus a reviewer and the rigs' Maven/Testcontainers runs left the Windows host ~500 MB of free RAM, WSL at load 15-20 on 12 vCPU". "Why 2 and not 1: max_active_sessions=1 makes Gas City run the pool as a canonical singleton session, a semantics change for every script that reads `claude-<bead>` session names." `cae18e6` (#105, same day): "Benjamin, 2026-09-18: restrict the Factory to what the machine has until RAM is added." |
| `bin/dispatch-door:45-48,73,216-218` | defers (exit 75) when `MemAvailable` < 1.5 GiB (`MEM_MIN_KIB=1572864`) | P12 `af-8j7tb`: "starting one more worker session costs about the same regardless of the ticket". |
| `agents/mayor/prompt.template.md:49-57,136-142` | "two concurrent writers on the agent-factory rig, one on each product rig" | prose mirror of the config. |

No ADR or document gives a measured reason for 2 rather than 3 on the HQ rig; the number in #309 is stated, not derived.

### B.2 Memory and CPU

| Item | Value | Source |
|---|---|---|
| Windows host RAM | 16,827,002,880 bytes (15.7 GiB) | `(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory` |
| Host CPU | i7-14650HX, 16 cores / 24 logical | `Get-CimInstance Win32_Processor` |
| WSL limits | `memory=8GB`, `processors=12`, `swap=6GB`, `autoMemoryReclaim=gradual` | `C:\Users\benja\.wslconfig`; its comment (2026-09-16): "was 10GB, which left Windows almost no reserve. Observed guest peak was ~3.7 GiB" |
| Guest now (Factory suspended) | 7,940 MiB total, 875 used, 7,065 available; swap 312 / 6,144 MiB; `nproc` 12; load 0.08 | `free -m`, `/proc/loadavg`, 2026-10-05 |
| Largest processes now | `dolt sql-server` 180 MiB RSS, `gc supervisor` 32 MiB, `bin/cockpit run` 10 MiB | `ps -eo rss,args --sort=-rss` |
| RSS per `claude`/`codex` worker session | **no recorded data found** | searched `.gc/runtime`, `.gc/system`, `.gc/events.jsonl`, docs; `bin/factory-resources` reports guest totals, not per session |
| Memory deferrals during the convoy | **none observed** | `grep 'dispatch-door: '` over the Mayor transcripts of the window (`~/.claude/projects/-home-benja-agent-factory/*.jsonl`): only "formula 'mol-dog-stale-db' is not valid" (2 hits); dispatch-door writes no log file of its own |
| `order.failed` during the convoy | none before 02:57; 7 × `pr-autopilot` 02:57-03:16 and 2 × `escalation-door-sweep` 04:13, 04:43 | `.gc/events.jsonl` |
| Local CPU contention reported by a worker | a local full-suite run started 21:07 was still unfinished at 21:59 and was killed; the same suite ran in about 9.5 min at 22:45-22:54 with one worker active ("All 99 tests pass") | TR `05d20efa`, `ef7b5d31` |

### B.3 Other things that scale with the number of workers

| Dimension | Fact | Evidence |
|---|---|---|
| Provider quota | One Anthropic account for every Claude profile ("une limite de session ou hebdomadaire épuise tous les profils Claude d'un coup"); all three targets are forced to `claude-standard`; OpenAI pool recorded exhausted since 2026-09-15 (manual mark) | `config/provider-policy.json` pools; `.gc/provider-state.json` `forced`, `pools.openai` |
| Quota events during the convoy | none: 0 entries in `provider-state.json` `history` between 30/09 and 01/10 (last entry 2026-09-23); 0 API-error messages in the 35 worker transcripts | script over both |
| Tokens consumed by the 35 worker sessions (incl. subagents) | 1.72 M output tokens, 395.8 M cache-read input tokens, 6.2 M cache-creation tokens, 2,790 model messages | sum of `message.usage` deduplicated by message id. `.gc/usage.jsonl` holds no `factory-worker` line for the window (1 line on 30/09) |
| CI | no `concurrency:` key in `.github/workflows/ci.yml`, GitHub-hosted `ubuntu-latest`; so runs do not queue on this host. But strict up-to-date + one update-branch per pr-autopilot tick (3 min order) makes merging serial: each merge costs every other open PR one more run of ~6 min | A.0 |
| CI volume in the window | 114 runs (74 PR success, 32 push success, 6 PR failure, 2 push failure) for 33 merged PRs | `gh run list` |
| Ports | cockpit tests take an ephemeral port (`free_port()` binds port 0, `tests/cockpit-core-test.py:37-39,87`) and pass `COCKPIT_PORT`; the default 8173 (`lib/cockpit/core/config.py:14,32`) is used only by the real `bin/cockpit`. No worker launched the app (`r-worker.md` §4c), so no port collision was observed; a launched app per worktree would need a port per worker | files cited |
| Beads / Dolt | 2 `bead.claim_rejected` events in the window (17:57 and 19:52: two workers started in the same minute tried the same step bead; the loser re-claimed); no Dolt contention note found in `docs/*.md`; one `dolt sql-server` serves everything | `.gc/events.jsonl`; `grep -i dolt` |
| Duplicate work from the return loop | 1 duplicate dispatch on T16 and 2 CI beads for one PR (A.1 #4, #8, #9) | A.1 |

### B.4 What Gas City offers for parallel items inside one workflow

- `[steps.drain]` (upstream `docs/reference/specs/formula-spec-v2.md` at tag `v1.4.1`, §3.3, lines 761-804; fetched with `gh api`, the
  file is not in `~/.gc/cache/repos`): "scatters the input convoy into one-member unit convoys and runs an item formula per unit".
  `context = "separate"` is the default: "all item roots created in parallel". `context = "shared"`: "one single-lane item root at a
  time", requires `item.single_lane = true`. `member_access = "exclusive"` records a per-member reservation and "fails if another
  drain owns it". `max_units` 1-100 (hard cap 100). `on_item_failure`: `continue` by default for separate, `skip_remaining` for shared.
- A separate drain creates the item roots in parallel; how many run at once is still bounded by the target pool's
  `max_active_sessions` (pool cap, B.1). The spec text read here gives no per-drain concurrency limit other than `max_units`.
- §3.4 `[steps.on_complete]` is the other fan-out (`parallel` default, or `sequential`), driven by a step's structured output.
- Existing use in the Factory: only `formulas/build-basic.formula.toml`. `:125-128` step `implement`: `context = "separate"`,
  `formula = "do-work"`, `member_access = "exclusive"` (default `drain_policy=separate`); `:138-145` step `implement-same-session`:
  `context = "shared"`, `formula = "do-work-item"`, `on_item_failure = "skip_remaining"`, `single_lane = true`, with the Factory's
  shared-worktree adapter. Its header (`:8-22`) records a live incident of a separate drain starting a dependent item in parallel
  with its prerequisites (`smb-ugkm`/`smb-gjts`, 2026-09-20), fixed by wiring `bd dep` edges between items.
- `build-basic` is not allowed on the HQ rig (`config/projects/agent-factory.toml:25`, `formulas = "mol-do-work"`). C01 did not use a
  drain: the Mayor dispatched each ready bead with `mol-do-work` (`agents/mayor/prompt.template.md:49-57`), one input convoy of one
  member per dispatch.

---

## Not verified

- Per-session RSS of a `claude` process: no measurement exists and none could be taken (Factory suspended, starting a session forbidden).
- Host load during the convoy (`/proc/loadavg` history, a game running on the Windows side): not recorded anywhere found.
- The first T16 commits before the rebases (`b45a811`, `3951b73`) were not inspected; the T16×T12/T13 conflict content is taken from
  the worker's tool output and text in TR `05d20efa`, not from a replayed merge.
- T16×T14 share `config.py`/`process.py` and overlapped in time; the update-branch merge `e946e18` succeeded, so it is counted as a clean auto-merge, not checked hunk by hunk.
- Who dispatched each re-dispatch (Mayor by hand vs `idle-ready-work-wake`) and the Mayor's reasoning: Mayor transcripts were only grepped for `dispatch-door:` lines.
- Why `pr-autopilot` failed 7 times in a row 02:57-03:16 (event payloads are null).
- "First CI attempt + one automatic retry": several rejected heads show a single run attempt in the API; how pr-autopilot counted its retry was not traced.
- The sequential and N-worker figures in A.4 are a model built on observed first-run durations; they are not measurements.
- Identity of values behind the duplicated constants/helpers (A.5) was not compared.
- Whether a `separate` drain honours a concurrency limit below the pool cap was read from the spec only; Gas City source was not read.
- `bin/ticket-graph-publish` was read at `112c286`; the function is unchanged since `a204b45`/`b25fbb9` per `git log -S`, but the exact file at publish time (17:55, before #364 and T05 #371) was not diffed.
