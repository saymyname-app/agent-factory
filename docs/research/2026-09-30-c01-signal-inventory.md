# C01 Cockpit V2: signals readable without model tokens (live inventory)

Research for wayfinder ticket af-arlph5.3 (map af-arlph5, "C01 — Cockpit V2
de l'usine"). Measured live, read-only, on 2026-09-30 between 12:02 and 12:12
(Paris). Starting input: `po/c01-cockpit:docs/planning/c01-cockpit/facts.md`
(2026-09-29). Every row below was re-run against the running Factory. The only
write was the bead claim. "Token-free" means no model call: plain CLI, file or
HTTP reads.

Sources: the live root `/home/benja/agent-factory` (HEAD `c74e95a`), `origin/main`
(`d493373`), `gc` 1.4.1 (`gc <cmd> --help`, the supervisor's `/openapi.json`),
`bd` 1.2.2, `gh`, `.gc/events.jsonl`, `.gc/runtime/*`, `orders/*.toml`, and
SayMyName `tools/rituals-status.sh`. Latencies are wall-clock times from two
consecutive runs in WSL (run1/run2).

## 0. Finding that changes the picture: the live root is not running A6b

- The live root is **12 merged commits behind `origin/main`**
  (`git status -sb`: `main...origin/main [behind 12]`). Its last
  fast-forward was 03:26 (Paris) (`git reflog`). PRs #329-#340 (A6b W03-W13 and
  the #340 guard fix) are merged but **not running**.
- Cause: three files from W08 (#330) sit **untracked in the live root**:
  `bin/factory-orphan-sweep` (03:42), `orders/factory-orphan-sweep.toml` (03:31)
  and `tests/factory-orphan-sweep-order-test.sh` (03:35). They are not ignored,
  and `origin/main` adds the same paths. `git merge --ff-only` refuses to
  overwrite untracked files. `factory-guard` section 3a ("live-root-sync") only
  checks tracked changes (`--untracked-files=no`), tries the merge, fails, and
  reports `bad "... fast-forward failed"` in its order output. It emits no
  event and pages no one: `.gc/events.jsonl` has no factory-guard entry
  other than fired/completed.
- Consequence, observed live: the `skip = [..., "orphan-sweep"]` that
  `origin/main:city.toml:165` adds is not loaded. gc's **core `orphan-sweep`
  still runs** every 5 min (09:59:08Z, 10:04:27Z) next to the untracked
  `factory-orphan-sweep`. Between 12:02 and 12:08 (Paris), the po-agent claims
  on af-arlph5.1, .3 and .4 were reset to `open` / unassigned. They had been
  `in_progress` / `po-agent/45bb6680-r*` at 12:02. That is the exact failure W08
  was meant to prevent: the wayfinder frontier (`bd ready --parent af-arlph5
  --unassigned`) now offers tickets already in work. The events for these
  beads carry `actor: cache-reconcile`, so the event log does not name the
  writer. Attributing the reset to core `orphan-sweep` is INFERRED from its
  timing and its description ("Reset beads assigned to dead agents").
- The root itself was not touched. Verdict: bug class "a merged fix is not
  running and nothing says so". The cockpit needs a **live-root drift** signal
  (row 13).

## 1. Inventory

Latency is run1 / run2. "Items" is what came back at 12:03-12:08 (Paris).

| # | Signal | Token-free read | Latency | Freshness | Now | Known noise / duplicates | Missing |
|---|---|---|---|---|---|---|---|
| 1 | NEEDS BENJAMIN | `bin/escalation-door list`, which runs `gc bd list --status open,in_progress --has-metadata-key gc.needs_benjamin --json` | 1.65 / 2.30 s (script); 0.87 / 1.07 s (raw bd) | live Dolt read | none | stale mails "NEEDS BENJAMIN: af-sqrri" / "af-qij75" are still unread in the `human` mailbox although both beads are closed. The mail never expires | the reason text is on the bead, but there is no "since when" field (`gc.needs_benjamin` holds the reason, not a timestamp) and no "what to do" field |
| 2 | Mayor-first escalations (pending, promoted after 2 h) | `gc bd list --all --has-metadata-key gc.escalation_mayor_paged_at --json`, filtered to open beads without `gc.needs_benjamin` (same logic as `cmd_sweep`) | 1.39 / 1.39 s | live; promotion runs every 15 min | 4 beads carry the key, all closed, so 0 pending | `--all` returns closed history (246 lines), so filter on status. `escalation-door clear` leaves the value `none`, not empty | no "still unresolved" list: only `sweep` computes age, and it writes. The cockpit must reimplement the age check (read-only, 5 lines of jq) |
| 3 | Proposals | `gc bd list --status open --label proposal --json` (count only in `escalation-door list`) | 1.31 / 1.12 s | live | 3 (af-r2y2w9, af-75gtq, af-pgm3y) | af-r2y2w9's fix merged as #340 but the bead is still open (#340 not running, section 0). Proposals also appear as `chore` rows inside `bd ready` | no state beyond open/closed (for example "accepted, in delivery") |
| 4 | Rituals | `bash /mnt/c/Dev/Projects/SayMyName/tools/rituals-status.sh` | **11.6 / 8.9 s** | computed on each run | 0 DUE (arch back/front ok, factory paused, incidents 0/5, alignment 0/5) | none | slowest read: 3 `gh pr list --state merged --limit 500` + 3 full `gc bd list --all --limit 0` + a scan of Windows transcript files over `/mnt/c`. Needs caching (for example every 30 min). Its factory spec still names `benjamin-hurand/agent-factory`, which resolves to `saymyname-app/agent-factory` through a GitHub redirect: it works but is fragile |
| 5 | Convoys / tickets progress | `gc convoy list --json` (closed/total per convoy) or HTTP `GET /v0/city/agent-factory/convoys`; detail with `gc convoy status <id>` | CLI 3.97 / 3.56 s; **HTTP 16 ms** | live | 10 open convoys | **mostly stale**: pre-refactor product convoys (`smf-*`, `smb-*`, parked), "input convoy for ..." and "drain unit N for ..." wrappers, A6 `af-dsygc` 23/24 (P22 af-a3ajo still open). `gc convoy stranded` (3.4 s) lists 14 rows, nearly all parked beads | no plan, project or roadmap grouping on a convoy; no filter for "parked" (it is a label on the child, not on the convoy) |
| 6 | Ready / in-progress work | `bd ready --json`; `bd list --status in_progress --json` | 1.33 / 1.70 s; 0.48 / 0.72 s | live | ready: 112 (capped at 100), of which **95 are `order:*` tracking chores**, 2 planning, 1 delivery (af-a3ajo) | order-tracking chores drown the ready list; `bd ready` silently caps at 100 (`--limit 0` to lift) | filter by `gc.plane=delivery` client-side (no server-side metadata filter in `bd ready`) |
| 7 | PRs and CI | `gh pr list -R <repo> --state open --json number,title,headRefOid,mergeable,updatedAt,autoMergeRequest` per repo in `config/projects/*.toml`; CI with `gh run list -R <repo>` or `bin/factory-gh-rollup` | 0.4-0.7 s per repo; runs 1.0-1.2 s | live GitHub | 0 open PRs on the 3 repos; Factory CI green; **frontend `frontend-e2e.yml` failed on `dev` on 2026-09-28 22:20 (Paris)**, not a required check | the PAT cannot read `statusCheckRollup` (factory-gh-rollup header): rebuild it from workflow runs. Rate limit 5000/h, 0 used, so polling 3 repos every 3 min costs about 60-120 calls/h | red non-required workflows on `dev` (like frontend-e2e) reach no one; `[ci]` bug beads: 0 open |
| 8 | order.failed | HTTP `GET /v0/city/agent-factory/events?type=order.failed&since=24h` or `gc events --type order.failed --since 24h`; **cheap path**: resume from a cursor, `GET /v0/city/.../events?index=<last>` (7 ms) or SSE `/events/stream` | since-filter: HTTP 3.8 s, CLI 6.1-6.5 s (scans the whole log); cursor 7 ms | live (SSE pushes within 1 s) | 2 in 24 h, both `pr-autopilot` "context deadline exceeded" (2026-09-29 23:58 and 2026-09-30 00:05, Paris) | historic bursts: factory-guard 258/day and pr-autopilot 228/day on 2026-09-24; 1-9/day since 2026-09-27. `mayor-campaign` and `ntfy-notify` failures (retired orders) are still in the log | the event carries only `subject` and `message`, with no link to the paging bead from `on-order-failed`; repeat detection lives in `on-order-failed` state, not in the event |
| 9 | Orders health (all 31) | `gc order list --json` (0.39 s, or HTTP `/orders` 12 ms); history `gc order history --json` | history **10.0-10.6 s, 5.5 MB, 43,926 entries** | live | 16 Factory orders + 15 upstream (core and dolt packs) | `backup-freshness` (condition, no interval) records **2,706 runs in 24 h** (about one per 32 s) with empty output, 30 % of history; wisp order-tracking beads | no "last success / last failure" per order in one call: derive it from events (`order.completed`/`order.failed` by subject) through a cursor |
| 10 | Sessions and loops | HTTP `GET /v0/city/agent-factory/sessions` (91 ms) or `gc session list --json` (1.3-1.5 s); loop events `session.woke` / `session.stopped` / `session.drain_acked_with_assigned_work` from the event stream | see left | live | 2 active: mayor (last nudge 11:54 Paris) and core.control-dispatcher; 24 h: 37 woke / 34 stopped / 4 draining / 1 drain_acked | `factory-session-loop-guard` computes cycles/h but writes no state file; pausing a session suspends it with no summary signal | no "cycles per session per hour" read-only surface: recompute from events |
| 11 | Idle Mayor with ready work | `.gc/runtime/idle-ready-work-state.json` (instant file read) | <1 ms | written by the order (5 min) | `idle_since` 06:36, `notified_at` 11:54 (Paris), while P22 af-a3ajo is ready | 35 runs/24 h; Mayor "Re: idle-ready-work" replies pile up in the `human` mailbox (3 in 90 s on 2026-09-29 14:20-14:22 Paris) | none beyond the file; not an event |
| 12 | Wayfinder maps in progress | `bd list --status open,in_progress --label wayfinder:map --json` (0.44-0.55 s); children `bd list --parent <map> --all --json` (0.31 s); frontier `bd ready --parent <map> --unassigned --json` (0.56 s) | see left | live | 1 open map: af-arlph5 (12 children, .2 and .4 closed at 12:08 Paris) | **claims reset by core orphan-sweep** (section 0): frontier and in-progress are wrong until the root is fast-forwarded | no map-level progress count; resolutions sit in comments. The map's "Decisions so far" is free text |
| 13 | **Live-root drift** (new) | `git -C /home/benja/agent-factory rev-list --count HEAD..origin/main` after `git fetch` (or `git status -sb`); untracked blockers with `git status --porcelain` | <0.1 s local (+fetch) | on demand | **behind 12**, 3 untracked files | factory-guard reports "fast-forward failed" only in its quiet order output | **no event, no mail, no bead**: the most damaging state today has no signal |
| 14 | Mail to human / Mayor | HTTP `GET /v0/city/agent-factory/mail/count` (41 ms: 279 total, 278 unread, all mailboxes); `gc mail inbox human --json` (1.0 s, 5 unread); `gc mail count mayor` (2.7 s) | see left | live | human 5 unread | unread counts are meaningless: nothing marks mail read when the bead resolves; duplicates (Mayor→factory-worker "Escalation (Mayor first): af-oihx" 5× in 3 min on 2026-09-29 03:03-03:06 Paris) | mail is an agent channel, not a cockpit source: prefer the bead state |
| 15 | City / controller health | HTTP `/v0/city/agent-factory/health` (8 ms), `/status` (1.7 s), `/provider-readiness` (5 ms), `/maintenance/status` (8 ms); `gc status --json` (**7.8-8.8 s**) | see left | live | controller running (supervisor mode), 11 agents / 1 running, Dolt store 630 MB, last GC 07:32 (Paris) | `/runs/census` returned 503 "warming" after 5 s | provider quota state lives in `.gc/provider-state.json` (not read here) |
| 16 | factory-observe | `bin/factory-observe status --json` (53-57 ms) | instant | only as fresh as the last `observe --snapshot` | `areas_observed: []`, never fed | none | built for "Cockpit V2 once it exists" (its header) but has no snapshot producer: a candidate cockpit back-end, not a source today |
| 17 | Legacy watchdog signals | `.gc/runtime/factory-watchdog-signals.json` | n/a | frozen at 2026-09-28 16:11 (Paris) | `alerts: []` | the only reference is a stale `lib/__pycache__/factory_cockpit.cpython-312.pyc` | dead file (confirms facts.md O06): do not read |

## 2. Read paths, by cost

1. **HTTP API of the gc supervisor: the cheapest path.** `http://127.0.0.1:8372`,
   OpenAPI at `/openapi.json` (700 KB), **no security scheme**
   (`components.securitySchemes` is null). It is bound to 127.0.0.1, so a
   phone cannot reach it directly (that question belongs to af-arlph5.2/.9).
   Useful GETs: `/v0/city/agent-factory/{events, events/stream, beads,
   beads/ready, beads/graph/{root}, convoys, convoy/{id}, sessions, orders,
   orders/history, mail, mail/count, status, health, readiness}`. Events take
   `index`/`wait` (blocking query, response header `X-Gc-Index`), `cursor`,
   `limit`, `type`, `actor`, `since`. SSE `/events/stream` pushed each new
   event within a second. The supervisor stream `/v0/events/stream` carries
   full bead payloads (`bead.created` with description).
2. **Local files**: `.gc/runtime/*.json` and `git` state, under 1 ms. Do not
   read `.gc/controller.token` or `.gc/ntfy-topic.local` (secrets).
3. **`gc` / `bd` CLI**: 0.3-4 s per call (each spawns a process and opens
   Dolt). Worst: `gc order history` (10 s, 5.5 MB), `gc status` (8 s),
   `gc events --since` (6 s, full scan of `.gc/events.jsonl`: 250 MB,
   402k lines, never rotated since 2026-09-12; `gc events rotate` exists).
4. **`gh`**: 0.4-1.2 s per call, 5000/h budget.
5. **`rituals-status.sh`**: 9-12 s, the only multi-second composite.

A cockpit that reads through one SSE subscription and a cursor, plus a few
bead queries every minute, stays near zero cost. Polling the CLI for every
tile would cost about 30-40 s of CPU per refresh.

## 3. Changes since facts.md (2026-09-29)

- Orders not listed in facts.md (not all new): `factory-orphan-sweep` (W08; untracked, running next to core
  `orphan-sweep`), `mail-reply-reap`, `backup-freshness`, `convoy-parent-sweep`,
  `on-session-stranded`. `spawn-storm-detect` is an upstream core order.
- `escalation-door`: unchanged interface (`benjamin | mayor | sweep | clear |
  list`); `list` is the only read-only command.
- Planning flow: on `origin/main`, W10/W11 **delete** `bin/planning-run-router`
  and `bin/wayfinding-run`. The live root still has them (section 0).
  Wayfinding is now beads-native (`wayfinder:map` epic plus children;
  `docs/agents/issue-tracker.md`).
- `order.failed` dropped from hundreds per day (2026-09-24) to 1-9 per day since
  2026-09-27.
- Pending proposals: 3 (af-r2y2w9 is new).

## 4. Gaps: signals with no token-free read path today

1. **Live-root drift / merged-but-not-running**: no signal at all (section 0).
2. **Pending Mayor-first age**: only `escalation-door sweep`, which writes,
   computes it.
3. **NEEDS BENJAMIN age and action**: the reason is a string, with no
   timestamp or expected action.
4. **Per-order last success / failure and per-session cycle rate**: not
   stored. Derive them from the event stream (cheap through a cursor).
5. **Project / roadmap grouping of convoys**: nothing ties a convoy to a
   project plan (facts.md "Platform facts" still holds). That question belongs
   to af-arlph5.4.
6. **Resolution-aware mail**: unread mail does not reflect bead state. Use
   beads, not mail.
7. **Non-required red CI on product `dev`** (frontend-e2e): no bead, no page.
8. **Actor attribution in events**: bead updates appear as `cache-reconcile`,
   so the cockpit cannot say "who changed this" from events alone.
