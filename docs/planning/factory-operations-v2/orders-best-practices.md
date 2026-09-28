# Orders: upstream semantics, retention, telemetry, best practices

Research 2026-09-28, read-only. `GC@f895` = `https://github.com/gastownhall/gascity/blob/f895c0ff47d6ee9334ed282a416387eb5b084d24`; `GC@141` = `.../gascity/blob/v1.4.1` (the installed `gc`: `1.4.1 (commit 58ef17e3…)`); `BD@122` = `https://github.com/gastownhall/beads/blob/v1.2.2` (installed `bd 1.2.2 (6c124203e)`).

**Pin vs. what runs.** `packs.lock` pins `bd` and `core` to f895c0f, and `~/.gc/cache/repos/6fe2…/.gc-bundled-pack-cache.toml` says the same commit. But the live `mol-dog-compactor` order is `interval = "2h"`. That matches v1.4.1 ([GC@141 examples/bd/dolt/orders/mol-dog-compactor.toml](https://github.com/gastownhall/gascity/blob/v1.4.1/examples/bd/dolt/orders/mol-dog-compactor.toml)), not f895c0f, where it is `24h` ([GC@f895 …/mol-dog-compactor.toml](https://github.com/gastownhall/gascity/blob/f895c0ff47d6ee9334ed282a416387eb5b084d24/examples/bd/dolt/orders/mol-dog-compactor.toml)). The running content comes from the binary's bundled packs. Between the two versions, only `mol-dog-compactor` and `reaper` differ (`git diff --stat f895c0f v1.4.1 -- …/orders`). Runtime behaviour below is checked against v1.4.1 where it matters.

## 1. Order semantics (upstream)

- **Tick.** The controller evaluates triggers every 30 s ([GC@f895 docs/tutorials/07-orders.md#L12-L15](https://github.com/gastownhall/gascity/blob/f895c0ff47d6ee9334ed282a416387eb5b084d24/docs/tutorials/07-orders.md#L12-L15)).
- **Five triggers** ([07-orders.md#L145-L245](https://github.com/gastownhall/gascity/blob/f895c0ff47d6ee9334ed282a416387eb5b084d24/docs/tutorials/07-orders.md#L145-L245), dispatched in [internal/orders/triggers.go#L61-L75](https://github.com/gastownhall/gascity/blob/f895c0ff47d6ee9334ed282a416387eb5b084d24/internal/orders/triggers.go#L61-L75)):
  - `cooldown` (`interval`): relative to the last run. Fires immediately if it has never run.
  - `cron` (`schedule`): 5 fields; supports only `*`, integers and comma lists. At most one firing per minute.
  - `condition` (`check`): **this is the threshold/criterion trigger.** `sh -c "<check>"` runs on every tick, and exit 0 fires the order. The timeout is 10 s. The check runs synchronously, so a slow check delays the other orders ([triggers.go#L196-L231](https://github.com/gastownhall/gascity/blob/f895c0ff47d6ee9334ed282a416387eb5b084d24/internal/orders/triggers.go#L196-L231); [07-orders.md#L194-L213](https://github.com/gastownhall/gascity/blob/f895c0ff47d6ee9334ed282a416387eb5b084d24/docs/tutorials/07-orders.md#L194-L213)).
    - `checkCondition` never consults the last-run time. A check that stays true re-fires on every tick once the previous run has closed, so the check itself needs hysteresis (for example "size > X", which becomes false after the action runs).
  - `event` (`on`): cursor-based, so each event is processed once. **The only filter is the event type** (`events.Filter{Type, AfterSeq}`), and payload filtering has to happen in the script ([triggers.go#L238-L260](https://github.com/gastownhall/gascity/blob/f895c0ff47d6ee9334ed282a416387eb5b084d24/internal/orders/triggers.go#L238-L260)).
  - `manual`: runs only via `gc order run`.
- **Timeouts.** The default is 300 s for exec orders and 30 s for formula orders ([internal/orders/order.go#L157-L168](https://github.com/gastownhall/gascity/blob/f895c0ff47d6ee9334ed282a416387eb5b084d24/internal/orders/order.go#L157-L168)). The struct comment at L50 says "60s for exec", which is stale. For exec orders the timeout kills the script; for formula orders it covers dispatch only. `[orders] max_timeout` caps every order ([07-orders.md#L275-L301](https://github.com/gastownhall/gascity/blob/f895c0ff47d6ee9334ed282a416387eb5b084d24/docs/tutorials/07-orders.md#L275-L301)).
- **Single flight.** An order with open work is skipped even when it is due ([07-orders.md#L440-L445](https://github.com/gastownhall/gascity/blob/f895c0ff47d6ee9334ed282a416387eb5b084d24/docs/tutorials/07-orders.md#L440-L445)).
  - `idempotent = true` makes the order *fail open* when that gate times out under store contention ([order.go#L54-L61](https://github.com/gastownhall/gascity/blob/f895c0ff47d6ee9334ed282a416387eb5b084d24/internal/orders/order.go#L54-L61)).
  - `[order.env]` passes thresholds to exec scripts without editing them ([order.go#L62-L68](https://github.com/gastownhall/gascity/blob/f895c0ff47d6ee9334ed282a416387eb5b084d24/internal/orders/order.go#L62-L68)).
- **Disable / override a pack order from `city.toml`** ([07-orders.md#L334-L411](https://github.com/gastownhall/gascity/blob/f895c0ff47d6ee9334ed282a416387eb5b084d24/docs/tutorials/07-orders.md#L334-L411); schema [internal/config/config.go#L1835-L1880](https://github.com/gastownhall/gascity/blob/f895c0ff47d6ee9334ed282a416387eb5b084d24/internal/config/config.go#L1835-L1880)):
  ```toml
  [orders]
  skip = ["nudge-mail-sweep"]          # removed from scanning entirely
  max_timeout = "300s"

  [[orders.overrides]]
  name = "jsonl-export"                # add rig = "<name>" or "*" for rig copies
  trigger = "condition"                # a pack cooldown can become a criterion trigger
  check = "test -n \"$(find … -newer …)\""
  # also: enabled, interval, schedule, on, pool, timeout, idempotent, [orders.overrides.env]
  ```
  - An override that targets an unknown name is an error. `gc start` logs it and skips it ([07-orders.md#L377-L381](https://github.com/gastownhall/gascity/blob/f895c0ff47d6ee9334ed282a416387eb5b084d24/docs/tutorials/07-orders.md#L377-L381)).
  - A same-named file in the city `orders/` directory replaces the pack definition completely ([07-orders.md#L521-L536](https://github.com/gastownhall/gascity/blob/f895c0ff47d6ee9334ed282a416387eb5b084d24/docs/tutorials/07-orders.md#L521-L536)).
- **History retention.** Tracking beads are deleted 7 days after close by default, configurable with `[beads.policies.order_tracking] delete_after_close` ([GC@141 internal/config/config.go#L3662-L3690](https://github.com/gastownhall/gascity/blob/v1.4.1/internal/config/config.go#L3662-L3690)).

## 2. Trace and event retention

| File (live size, 2026-09-28) | Built-in bound | Knobs |
|---|---|---|
| `.gc/events.jsonl` (203 MB, no archive yet) | Auto-rotates when the file reaches **256 MiB**. **Archives are kept forever** unless `archive_retain_age` is set. | `[events.rotation] enabled, max_size_bytes, check_interval_records, check_interval_seconds, archive_retain_age` ([GC@141 config.go#L1805-L1831](https://github.com/gastownhall/gascity/blob/v1.4.1/internal/config/config.go#L1805-L1831)). Env: `GC_EVENTS_ROTATION_ENABLED`, `_MAX_SIZE_BYTES`, `_RETAIN_AGE`, which warns below 168h ([GC@141 cmd/gc/providers.go#L1021-L1045](https://github.com/gastownhall/gascity/blob/v1.4.1/cmd/gc/providers.go#L1021-L1045)). Manual: `gc events rotate [--wait]`, which needs the supervisor ([GC@141 cmd/gc/cmd_events.go#L233](https://github.com/gastownhall/gascity/blob/v1.4.1/cmd/gc/cmd_events.go#L233)). |
| `.gc/runtime/session-reconciler-trace/` (604 MB, 48 segments since 2026-09-21) | Hard-coded: 16 MiB segments, pruned at **7 days or 1 GiB total**, checked every 5 min ([GC@141 cmd/gc/session_reconciler_trace_store.go#L23-L33](https://github.com/gastownhall/gascity/blob/v1.4.1/cmd/gc/session_reconciler_trace_store.go#L23-L33); prune logic [GC@f895 …#L508-L560](https://github.com/gastownhall/gascity/blob/f895c0ff47d6ee9334ed282a416387eb5b084d24/cmd/gc/session_reconciler_trace_store.go#L508-L560)) | No size or age config. `GC_SESSION_RECONCILER_TRACE=0` turns it off completely ([GC@141 session_reconciler_trace_collector.go#L97](https://github.com/gastownhall/gascity/blob/v1.4.1/cmd/gc/session_reconciler_trace_collector.go#L97)). |
| `.gc/runtime/core.control-dispatcher-trace.log` (66 MB) | v1.4.1 only (the file does not exist at f895c0f): rotates at **200 MiB**, keeps `.1`/`.2` (about 600 MiB maximum) ([GC@141 cmd/gc/workflow_trace_rotation.go#L16-L24](https://github.com/gastownhall/gascity/blob/v1.4.1/cmd/gc/workflow_trace_rotation.go#L16-L24), called from [dispatch_runtime.go#L177](https://github.com/gastownhall/gascity/blob/v1.4.1/cmd/gc/dispatch_runtime.go#L177)) | Package variables only, with no config. The path is chosen with `GC_WORKFLOW_TRACE` / `GC_CONTROL_DISPATCHER_TRACE_DEFAULT`. |

Neither gascity revision I read has a `retention_days` key. The only day-based retention knobs are `delete_after_close` and `archive_retain_age`. Conclusion: all three are already size-bounded upstream. The one unbounded item is **events archives**, which will start to accumulate at the first rotation.

## 3. Telemetry

- **bd 1.2.2.**
  - `metrics.disabled: false` sends one `cli_command` event per bd command to `https://gastownhall-eventsapi.com/mp/collect`. Each event carries the **command name** plus a machine-derived HMAC ID, the app name and version, and the OS. It sends **no issue content, arguments, or paths** ([BD@122 internal/metrics/metrics.go#L17-L20](https://github.com/gastownhall/beads/blob/v1.2.2/internal/metrics/metrics.go#L17-L20), [#L64-L69](https://github.com/gastownhall/beads/blob/v1.2.2/internal/metrics/metrics.go#L64-L69), [#L103-L111](https://github.com/gastownhall/beads/blob/v1.2.2/internal/metrics/metrics.go#L103-L111); disclosure in [cmd/bd/metrics.go](https://github.com/gastownhall/beads/blob/v1.2.2/cmd/bd/metrics.go)).
  - Events are queued in `~/.beads/eventsData`, currently 17 MB.
  - To disable: run `bd metrics off`, set `metrics.disabled: true`, or export `BD_DISABLE_METRICS=1`.
  - The Factory supervisor environment carries `GC_DISABLE_USAGE_METRICS=1` and no `BD_DISABLE_METRICS`, so bd subprocesses probably report.
  - `SECURITY.md` in the same tag still says beads has "no telemetry" and points only at Dolt's own metrics (`dolt config --global --add metrics.disabled true` or `DOLT_DISABLE_EVENT_FLUSH=1`) ([BD@122 SECURITY.md#L38-L52](https://github.com/gastownhall/beads/blob/v1.2.2/SECURITY.md#L38-L52)). That document is stale. No Dolt `metrics.disabled` setting is present in the global config.
- **gc 1.4.1.**
  - Separate "product metrics" send the command ID, version, OS, an installation ID and the hour (UTC) to `gastownhall-eventsapi.com/v1/gascity/command-events` ([GC@141 internal/productmetrics/event.go#L170-L176](https://github.com/gastownhall/gascity/blob/v1.4.1/internal/productmetrics/event.go#L170-L176), [release.go#L83](https://github.com/gastownhall/gascity/blob/v1.4.1/internal/productmetrics/release.go#L83)).
  - The upstream notice says these metrics are not collected in agent-managed sessions ([notice_content.go#L13-L26](https://github.com/gastownhall/gascity/blob/v1.4.1/internal/productmetrics/notice_content.go#L13-L26)).
  - To disable: `gc metrics off`, `DO_NOT_TRACK=1`, or `GC_DISABLE_USAGE_METRICS=1` ([execenv.go#L16](https://github.com/gastownhall/gascity/blob/v1.4.1/internal/execenv/execenv.go#L16)).
  - Live: `gc metrics` reports "enabled" for the interactive CLI.
  - Whether to opt out is a consent/data decision for Benjamin.

## 4. General best practices

- **Page on symptoms, not causes.** A page must be urgent, actionable and novel. "If a page merely merits a robotic response, it shouldn't be a page" ([SRE book, Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/)).
- **Flap control.** Prefer multiwindow alerting (a long window plus a short confirming window) to naive `for`-duration gating, which resets on any momentary recovery ([SRE workbook, Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/)).
- **Toil.** Manual, repetitive, automatable work with no enduring value should be automated ([SRE book, Eliminating Toil](https://sre.google/sre-book/eliminating-toil/)). The same logic applies to automations that run with nothing to do: they cost load and noise and produce no value.
- **Criterion-triggered retention.**
  - logrotate rotates on `size`/`maxsize`/`minsize` and bounds retention by `rotate N` and `maxage` ([logrotate(8)](https://man7.org/linux/man-pages/man8/logrotate.8.html)).
  - journald defaults to a disk-percentage cap (10 %, capped at 4G) rather than a clock ([journald.conf(5)](https://man7.org/linux/man-pages/man5/journald.conf.5.html)).
  - Dolt ≥1.75 auto-GCs when a database grows by about 125 MB ([Dolt GC docs](https://docs.dolthub.com/sql-reference/server/garbage-collection), [Dolt 1.75 blog](https://www.dolthub.com/blog/2025-10-20-dolt-1-75/)).
- **Event-driven over polling, with a rate limit.** systemd path units use inotify triggers (`PathChanged`, `DirectoryNotEmpty`) with `TriggerLimitIntervalSec`/`TriggerLimitBurst` ([systemd.path(5)](https://man7.org/linux/man-pages/man5/systemd.path.5.html)).
- **Idempotent sweeps and one owner per automation.** An upstream order comment already notes duplicated ownership: `nudge-mail-sweep` says "The controller watchdog runs this same sweep every 5 minutes automatically" ([GC@f895 core/orders/nudge-mail-sweep.toml](https://github.com/gastownhall/gascity/blob/f895c0ff47d6ee9334ed282a416387eb5b084d24/internal/bootstrap/packs/core/orders/nudge-mail-sweep.toml)).

## 5. Implications for this Factory (RECOMMENDATIONS, not facts)

Measured baseline, taken from the last 400k lines of `events.jsonl` covering 24 h:
- `order.fired` 7513 and `order.completed` 7508 out of about 17.5k events, so roughly 86 % of the event log is order bookkeeping.
- `bead.updated` 110 and `bead.closed` 1086.
- `order.failed` 5.

| Category | Orders | Recommendation |
|---|---|---|
| Health probes, 30 s | `dolt-health`, `beads-health` (+ `mol-dog-doctor` 5m) | Keep one fast liveness probe; they overlap. Consider 1–2m via `[[orders.overrides]] interval`. Page only on a sustained failure (symptom). |
| Mechanical sweeps, 30s–5m | `gate-sweep` (30s), `order-tracking-sweep` (1m), `orphan-sweep`, `spawn-storm-detect`, `cross-rig-deps` (5m) | Lengthen the intervals, or retrigger with `condition` where a cheap count exists (open gates > 0, stale tracking > 0). **`cross-rig-deps`**: its own comment makes it relevant only with cross-rig deps; skip it if unused. |
| Duplicate owner | `nudge-mail-sweep` | **Skip**: upstream says the controller watchdog already runs it. |
| Storage / Dolt | `mol-dog-compactor` (2h), `mol-dog-stale-db`, `mol-dog-phantom-db`, `wisp-compact`, `reaper` | The compactor duplicates Dolt auto-GC, which triggers on +125 MB. Change it to `condition` on journal size (the `vvvv…` file) or on Dolt version ≥1.75 auto-GC. The rest can stay on their clocks. |
| Backup / export | `mol-dog-backup` (6h), `jsonl-export` (15m), `dolt-remotes-patrol` (15m) | Keep the backups. Add a **symptom** check that pages when the newest backup is older than N h. Retrigger `jsonl-export`/`remotes-patrol` on the condition "commits since last export". |
| Git hygiene | `prune-branches` (6h) | Change to `condition`: stale branch or worktree count > threshold. |
| Event-driven | `cascade-nudge-on-blocker-close`, `nudge-on-route`, `on-order-failed`, `on-session-stranded` | Keep. Filtering by type only is cheap at the current volume. `on-order-failed` already dedups on repeated failure (good flap control). |
| Own clocks | `pr-autopilot` (3m), `provider-failover` (2m), `factory-guard`, `factory-watchdog` (5m), `convoy-parent-sweep` (15m), `model-staleness-check` (24h) | Keep `provider-failover` and `pr-autopilot`; their state is external and they have no event source. Consider merging guard and watchdog under one cadence and owner. Move `convoy-parent-sweep` to `event on = "bead.closed"`. Move `model-staleness-check` to `cron`. |
| Retention config | — | Set `[events.rotation] archive_retain_age = "720h"` before the first rotation at 256 MiB. No action is needed for the traces (already capped). Consider `delete_after_close` shorter than 7d. |
| Telemetry | — | Benjamin decides on `BD_DISABLE_METRICS=1` in the supervisor environment and `gc metrics off`. |

Before overriding any interval, check that the pack script tolerates the longer gap (read `$PACK_DIR/assets/scripts/*.sh`).
