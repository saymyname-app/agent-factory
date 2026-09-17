# Factory audit, 2026-09-17 — every brick, with evidence, and the plan to reach an autonomous factory

Requested by Benjamin after three silent stalls in one night: audit every
brick methodically, check our design against outside practice, and produce
one actionable plan. Written by the PO/Tech-Lead session. Supersedes the
diagnosis (not the taxonomy) in `FACTORY_CONTINUITY.md` and both incident
reports where they disagree — see §3.

## 0. Method and coverage

Five parallel read-only audits, each with the same grid (purpose; state
read/written; every failure mode; who is notified and how; retry/escalation
actually implemented; tests on the failure path; documentation; gaps with
file:line; minimal fix *inside* the mechanism), plus live evidence from
`gc events`, `gc order list`, `gc rig list`, and outside references.

| Brick | Audited | Evidence base |
|---|---|---|
| Campaign core: `bin/mayor-campaign`, `lib/factory_campaign.py`, `lib/factory_state.py`, `lib/factory_liveness.py` | yes, line by line | code + live coordination bead |
| Formulas/molecules: all 42 | yes, classified; the 7 actually used read in full | symlink targets, `packs.lock`, 21 attempt beads |
| Prompts and providers: Mayor, reviewers, pool-worker (pack), `city.toml`, `provider-policy.json`, `.gc/settings.json` | yes | files + live `ps` |
| Orders and guards: 4 orders, `factory-guard`, `pr-autopilot`, `factory-delivery-guard`, `deliver-close`, `factory-main-gate`, observability, DR | yes | code + 24 h of `gc events` + GitHub API |
| Cockpit, docs, tests, product definition | yes | code, 21 ADRs, 28 tests, `ci.yml` |

## 1. Verdict

The factory is well built where it was designed (zero-token cockpit, release
contract, provider failover for quotas, delivery-proof guard, reversibility
gate, tests on most scripts). It stalls because of **one design gap repeated
in every layer, and three structural facts nobody had seen**:

1. **Nothing in the mechanism can reach a human, and every escalation path
   ends in silence.** No code path calls `gc mail send human` or sets
   `gc.needs_benjamin`; the sentinel sends at most 3 reminders then prints
   `already notified` forever; the guard files one bead then prints
   `already filed` forever; a durable campaign block (`failure_count=3`) is
   never filed or mailed at all; formulas mail a `witness` agent that does
   not exist.
2. **The cockpit's "running" is not liveness.** `lib/factory_state.py`
   derives `campaign.state` from the result stage only; no cockpit code
   reads `gc.campaign_progress_at`. Green for nine idle hours is the
   designed behaviour.
3. **The Factory-campaign lane (`goal=none`) is selected by nobody.**
   Neither `plan_transition` nor the idle ladder reads it, and the ladder is
   skipped entirely whenever a product wake is pending. Every cockpit and
   guardrail candidate queued there waits for a human to push it.
4. **What actually runs is not what the Mayor prompt describes.** Real
   traffic is `mol-do-work` (42 runs) and `mol-polecat-commit` (19 runs:
   direct push to the base branch, no PR, no review, `main` included);
   `build-basic`/`review` have 0 runs. All 42 formulas are unmodified
   upstream symlinks — none is ours to edit in place.

## 2. Findings by brick

### 2.1 Campaign core

| id | where | sev | today | fix in the mechanism |
|---|---|---|---|---|
| C1 | `mayor-campaign:397,553`; `factory-guard:327,349` | P0 | after 3 reminders + one bead: permanent silence | after `MAX_REWAKES`: set `gc.needs_benjamin`, `gc mail send human`; guard re-mails on bead age |
| C2 | `factory-guard:327`; `factory_liveness.py:84` | P0 | `durable_failure` block never filed nor mailed | file `durable` too; at count ≥ 3 mail human |
| C3 | `factory_state.py:328-329,716`; `factory_campaign.py:234` | P1 | `goal=none` lane selected by nobody | ladder rung 2b reads `product-queue list --json`, first eligible factory candidate → `materialize:` wake |
| C4 | `mayor-campaign:530` | P1 | ladder skipped while any product wake is pending | run ladder when the wake is stale > 30 min; one product + one factory wake |
| C5 | `mayor-campaign:608` | P1 | sending a *new* wake stamps progress; key churn resets the 60-min clock | stamp `wake_sent_at` only; progress = real events (bead closed pass, commit, PR merged) |
| C6 | `factory_campaign.py:224-231` | P1 | one stalled in-progress ladder bead (`af-6eqc`) blocks rung 2 forever | on `ladder_stalled` mark it `gc.waiting_on=stalled`, take the next |
| C7 | `saymyname-product-status:172-185` | P1 | closed-but-waiting current result is nagged to finalize (live now: `af-u8id.4.1`) | honour `gc.resume_mode=automatic_dependency` / `gc.waiting_on` |
| C8 | `mayor-campaign:50`; order timeout 50 s | P2 | 45 s per call × ~10 calls; killed ticks uncounted (31 in 24 h) | 10 s per call, 40 s global deadline, record `tick_timeout` |
| C9 | `mayor-campaign:594-600` | P2 | reminder mailed before counter persisted → re-sent every minute after a kill | persist before send |
| C10 | `saymyname-product-status:297-303` | P2 | `running==true` session counts as progress even if stuck | require recent session activity |

### 2.2 Formulas and molecules

All 42 files in `.beads/formulas/` are symlinks into the pack cache
(`gascity-packs@3b3b89f`, `gascity@f895c0f`); the directory is gitignored. A
real file placed there wins by search order, so **every fix is a tracked
local fork**, never an edit.

| id | where | sev | today | fix (local fork) |
|---|---|---|---|---|
| F1 | `mol-scoped-work` every step | P1 | step text never says how to close; agents use `gc bd close --reason` → no `gc.outcome` → `missing_outcome` ×3 → `hard_fail` → `abort_scope` (7 of 8 runs) | explicit close line per step: `gc bd update <id> --set-metadata gc.outcome=pass --status=closed --notes …` |
| F2 | `mol-scoped-work` | P1 | root closes `closed` with nested `gc.outcome=fail` only | `notify-failure` step gated on body fail: mail + `gc.needs_benjamin` |
| F3 | `mol-polecat-commit:118-147` | P1 | `git push origin HEAD:{{base_branch}}`, no PR, no review, `main` included | fork: push a work branch + `gh pr create`; refuse `base_branch=main` |
| F4 | polecat-*, `mol-do-work:85` | P2 | escalation mail to nonexistent `witness` | `${GC_ESCALATION_RECIPIENT:-human}` |
| F5 | `mol-scoped-work` `submit` | P2 | prose only, no PR guaranteed | explicit push + `gh pr create` |
| F6 | Mayor routing table vs usage | P3 | names formulas with 0 runs | align after F1-F5 |

### 2.3 Prompts, agents, providers

| id | where | sev | issue | fix |
|---|---|---|---|---|
| P1 | Mayor prompt, both edges | P1 | edges spent on "never wait" and handoff; no priority order, no mail rule, no time budget | rewrite: turn loop first, escalation contract last (skeleton in §5.3) |
| P2 | Mayor prompt (absent) | P1 | guard files its bug as P1 "ordinary ready work" → the 4 h detour | order: decision mail → product → factory lane → diagnosis, timeboxed |
| P3 | `AGENTS.md:120`, prompt (absent) | P1 | "mark-read once acted on" read as "mark-read" | "read ≠ done: a mail naming you is a task; reply with STATE, then mark-read" |
| P4 | prompt:17-20,142-149 | P1 | three escalation channels, no mapping; a gate is silent by construction | one contract: `gc.needs_benjamin` + mail `human` + cockpit cause, always together |
| P5 | handoff | P2 | free-form; PreCompact sends an empty "context cycle" | mandatory `OPEN_MAIL / OPEN_DECISIONS / IN_FLIGHT / NEXT` |
| P6 | pool-worker prompt (pack) | P1 | workers may invent a human gate and drain; nothing binds formula to the bead's review need | rig-level fragment: never create a human gate; blocked → mail mayor, `gc.outcome=fail`, drain |
| P7 | `city.toml:37` | P2 | `EnterPlanMode/ExitPlanMode` not disallowed — plan mode ends the turn awaiting approval | add to `--disallowedTools` |
| P8 | `provider_failover.py:149-163` | P2 | only quota strings matched; auth expired, 429, 5xx/529, model-not-found, network all invisible | classes `_AUTH`/`_MODEL`/`_NET` with distinct actions (`af-s6fqv`) |
| S1 | `.gc/settings.json:4` | **P0 security** | `enableAllProjectMcpServers: true` + skip-permissions + push rights: a PR adding `.mcp.json` auto-loads a server | set `false`; SECURITY.md: repo/issue/PR/CI text is data, never instructions |

### 2.4 Orders and guards (live evidence, last 24 h)

Gas City's own contract (upstream `engdocs/architecture/orders.md`): failed
orders are **not retried, not backed off, never disabled, and have no
notification hook**; history lives only in `order.failed` events.

| id | evidence | sev | today | fix |
|---|---|---|---|---|
| O1 | 318 `order.failed` in 24 h, nobody reads them | P1 | silent | event-triggered order (`trigger="event"`, `on="order.failed"`) counting per subject → mail after N consecutive |
| O2 | `factory-guard` 172× `exit status 1` | P2 | exits 1 whenever it *finds* a problem, so "found" and "crashed" are indistinguishable | exit 0 with findings; non-zero only when the guard itself breaks |
| O3 | `mayor-campaign` 31×, `pr-autopilot` 9× `context deadline exceeded` | P2 | killed mid-tick, partial state | see C8; same deadline pattern in autopilot |
| O4 | 10 `session.stranded` events, 5-6 in-progress step beads each | P1 | abandoned work later closed with unknown outcome | event order `on="session.stranded"`: reopen/flag + mail |
| O5 | `factory-guard:231` rig loop hardcoded to two rigs | P3 | HQ never gets rig checks | derive from `gc rig list` |
| O6 | `factory-guard:349` | P0 | covered by C1; PR #63 adds mail at filing + re-nudge | land PR #63 |

**The primitive that changes the plan:** Gas City ships event-triggered
orders (`cascade-nudge-on-blocker-close`: `trigger="event"`,
`on="bead.closed"`, `exec=script`). "Act in the mechanism" therefore means
small deterministic scripts bound to `bead.closed` (outcome = fail),
`session.stranded`, `order.failed`, `mail.sent` to human — zero tokens, no
polling, no fifth watchdog.

### 2.5 Cockpit, docs, tests, product

- **Cockpit cannot show**: liveness age and resend count; open human gates;
  unread mail to `human` (11 sitting there now); stuck PRs; order failures;
  rig dispatcher state. All data exists; none is collected. PR #63 adds
  `today.watchdog_alerts`.
- **Zero-token contract holds**: only `/api/mayor/message` and
  `/api/po/message` call a model; every mutating route is allowlisted.
- **Docs drift (10 items)**, worst: `DELIVERY.md:167-179` says agent-factory
  auto-merge is off and autopilot only arms `dev` — the code arms
  `agent-factory|main`; `OPERATIONS.md` omits 5 routes and a "Pause" control
  that does not exist; `ADR-0015` still says "NOT STARTED";
  `FACTORY_CONTINUITY.md`, the incident report, `CANARY.md` and the token
  proposal are unindexed (ADR-0017: an unindexed doc does not exist).
- **Tests**: 26/28 suites in CI. Untested: sentinel mail failure / timeout /
  durable escalation / factory lane; guard rig loop; autopilot `main` path
  and stuck PRs; failover non-quota errors; **no end-to-end or chaos test**
  (stall, dead order, stuck PR, exhausted provider, as seen by the cockpit).
- **Two audiences**: no French end-to-end "how the factory works"; **no
  "stuck at 4 am, no PO session" runbook**.
- **Product**: no production deploy path documented after `main`; no prod
  monitoring; no explicit "Benjamin confirms V1 released" gate
  (`release-v1-contract` has `options: []`); `release-e2e` and
  `private-learning` criteria unverified; exposure ledger empty.

### 2.6 Delivery-close, main gate, observability, DR

| id | where | sev | today | fix |
|---|---|---|---|---|
| D1 | GitHub settings; `pr-autopilot:39-43` comment | **P1** | **no branch protection on any branch of the three repos** (agent-factory: 403, needs a paid plan for a private repo; SayMyName back/front `dev` and `main`: 404 = none). One personal `gh` token with full `repo, workflow` scope is shared by every agent. Every gate is local and bypassable. | protect the SayMyName branches now (free on public/organisation plans — check); for agent-factory either pay or have the guard alert on any `main` commit with no merged PR; fix the false comment |
| D2 | `pr-autopilot:206-208` | P2 | a pending, cancelled or action-required check counts as "OK" in the rollup; only `state=CLEAN` stands between that and a merge | OK only if every conclusion is SUCCESS/NEUTRAL/SKIPPED |
| D3 | `pr-autopilot:127-129,198` | P2 | draft, DIRTY, BEHIND, BLOCKED, zero-check PRs: one log line per pass, forever | count as `stuck`; after N passes one idempotent bead + mail |
| D4 | `pr-autopilot:135-141` | P1 | red build → P1 bug bead with no assignee, label or mail; nothing picks it up; never closed when the PR goes green; duplicates when `gc bd list` fails | label + one mail; close on reconcile; skip creation on list failure |
| D5 | `factory_delivery_proof.py:57,118`; `mol-do-work:95-101` | P2 | only `product-goal` beads are proof-checked; a work bead closed `work_outcome=shipped` with no PR is never verified; plain `gc bd close` bypasses `deliver-close` | extend `is_delivery_bead` to any closed bead claiming `shipped` |
| D6 | `factory-delivery-guard:109-112,70` | P2 | a proof-less bead is flagged once in metadata, then makes the script exit 1 **every 5 minutes forever** — live now for `af-u8id.4.1-.4.4` | mail on first flag; already-flagged beads report without failing |
| D7 | `factory-main-gate` | P2 | covers only a local `git push` to agent-factory `main`; bypassed by API merges and any clone without `core.hooksPath`; rig repos have no hooks | guard checks `core.hooksPath` in every worktree; CI on `main` at the merged SHA |
| D8 | logging | P1 | automations write **no log files**; stdout survives only interleaved in `~/.gc/supervisor.log` (9.6 MB, never rotated); `events.jsonl` 43 MB and a 21 MB trace, unrotated | `tee -a .gc/logs/<order>.log` + rotation; a daily digest order |
| D9 | Windows host | **P1** | systemd + linger + `gascity-supervisor` `Restart=always` exist inside WSL, but **nothing starts WSL after a Windows reboot**, and the cockpit is a hand-launched process, not a unit | Task Scheduler "at logon" `wsl -d Ubuntu-24.04 -u benja -- true`; systemd user unit for the cockpit |
| D10 | `.gitignore:1` | P2 | `.gc/` is excluded from guard snapshots: provider state, PO conversation store, reversibility cache have no off-box copy | add them to the 15-minute archive push |
| D11 | DR | P2 | beads are archived off-box every 15 min (live); the only restore drill ever run used the *local* Dolt backup | run and document one restore from the off-box archive onto a clean machine |

There is no single place to read "what did the automations do in the last
24 h": the sources are an interleaved supervisor log, `gc events` (exit
codes, not actions), three dispatcher traces and bead metadata.

## 3. Corrections to earlier reports

1. "No scheduled check exists" — wrong (already corrected in
   `FACTORY_CONTINUITY.md` §8.1): orders run every 1-5 min.
2. **`af-ptx7` is not a `base_branch` bug.** 5 of 7 hard-fails were on
   `main`. Cause: the step close idiom (F1). Bead retitled; Mayor mailed.
3. "Two rigs" — three; `agent-factory` is the HQ rig.
4. "PR + CI is the gate" — only when an agent happens to open a PR; the
   most-used writer formula pushes directly (F3).

## 4. Outside references, and how we compare

- Anthropic, *Building effective agents*: keep the system as simple as the
  task allows; give agents **stopping conditions**; checkpoints for human
  feedback at blockers; invest in the agent-computer interface. → We lack
  stopping conditions on investigations (P2) and our ACI teaches the wrong
  close idiom (F1).
- Anthropic multi-agent lessons: performance is model **plus harness**;
  multi-agent costs ~15× tokens; add agents only on demonstrated need. →
  Supports `do-work`-first routing and zero-token orders; argues against a
  fifth LLM watchdog.
- Google SRE, *Monitoring distributed systems*: every page actionable; alert
  on **symptoms**, not causes; email alerts become noise. → Our one symptom
  is "no real progress for N minutes"; it must page, and findings must not
  be reported as failures (O2).
- Durable-execution practice (Temporal): **heartbeats on long activities**,
  bounded retries with backoff, compensation. → Progress must be a heartbeat
  of real events (C5/C10); killed ticks must be recorded (C8).
- 2026 HITL escalation practice: tiered autonomy, each escalation logged
  with state, trigger, action, rationale. → Matches ADR-0016's effect tests;
  what is missing is the single delivery contract (P4).
- Gas City upstream: no retry, no notify on order failure; formulas have no
  human-notification primitive → these are ours to build, with event orders.

## 5. Target design (what "autonomous" means here)

### 5.1 Five rules

1. **One escalation contract**, everywhere: `gc.needs_benjamin` on the bead
   + mail to `human` + a cause the cockpit shows + a push to Benjamin's
   phone. Never one without the others.
2. **Every signal ages, then acts, then is verified**: bound → deterministic
   action → check the action happened → next rung. The last rung is rule 1.
3. **Progress is measured on real events** (bead closed with pass, commit,
   PR merged), never on "a wake was sent" or "a session exists".
4. **Never idle**: release work → factory lane → enabled improvement axes;
   "stopped" is only ever a human switch, shown as such.
5. **No direct push to a protected branch**: every writer formula ends in a
   PR; review depth follows the bead's delivery tier.

### 5.2 Mechanisms

Event-triggered orders (zero token): `on-step-failed` (`bead.closed`,
outcome fail → mail + flag), `on-session-stranded`, `on-order-failed`
(N consecutive), `on-human-mail` (push). Sentinel and guard fixes C1-C10.
Formula forks F1-F5. Cockpit reads liveness and shows the queue of things
waiting for a human.

### 5.3 Mayor prompt skeleton

Top: (1) unattended, never block; (2) every turn in order — mail naming you
→ execute, reply ACTION/STATE/EVIDENCE/NEXT, mark-read; eligible product
candidate; factory lane; only then diagnosis; (3) an investigation gets
≤ 20 min or 30 tool calls while anything above is pending. Middle: routing
table aligned with the forked formulas; merge facts per repo. Bottom:
(4) escalate only on the four effect tests, always with the full contract;
(5) read ≠ done; (6) handoff with mandatory open-items fields.

## 6. Action plan

The delivery pipeline is itself among the broken bricks (F1, F3, C3), so the
factory cannot be asked to repair all of this through itself. **Wave 0 is
bounded Factory maintenance done by the PO/Tech-Lead session directly, each
item one small PR with CI and independent review; from Wave 1 on, the Mayor
executes.**

| Wave | Items | Why first | Verification |
|---|---|---|---|
| **0 — stop the bleeding** (PO session, PRs) | S1 security flag; P7 disallow plan mode; F1 fork `mol-scoped-work` with close lines; P1-P4/P6 Mayor prompt + rig worker fragment; C3+C4 factory lane readable; land PR #63; fix `DELIVERY.md` | removes the three causes of last night and makes the factory able to take the rest | reproduce: a scoped-work run passes `load-context`; a stale wake reaches `human`; a factory-lane candidate is materialized without a human mail |
| **0-bis — ADMIN, Benjamin himself, ~20 min** | D9 Windows "at logon" task that starts WSL; D1 branch protection on the SayMyName repos (+ decide paid plan or guard alert for agent-factory); choose the phone push channel | host and account settings are ADMIN: no agent may do them | reboot the PC: the city and cockpit come back alone; a direct push to a protected branch is refused |
| **1 — close the loop** (Mayor) | C1, C2, C5-C10; O1-O4 event orders; phone push; cockpit truth (liveness, gates, human mail, stuck PRs) | detection becomes action, and the human sees the truth | chaos tests: kill the Mayor, strand a session, conflict a PR, exhaust a provider — each reaches the phone inside its bound |
| **2 — deliver safely** (Mayor) | F2-F6; branch protection; provider error classes (`af-s6fqv`); `af-grln2` | no unreviewed push; failures classified | a polecat run ends in a PR; an auth error is labelled as such |
| **3 — never idle, fully visible** (Mayor) | `af-jpx3` axes + maintain-alive; `af-h582` state graph; cockpit reorg beads; docs drift; French end-to-end doc; 4 am runbook; chaos suite in CI | autonomy with bounded scope, understandable by a human | empty release queue → an enabled axis is picked; switch off → cockpit says "stopped by Benjamin" |
| **4 — product to production** (Benjamin + PO decisions) | production path, monitoring, release-done gate, exposure ledger, `af-zt6n` existing-code review | reserved decisions: publication, personal data, irreversible | a human-confirmed release checklist exists and is green |

## 7. What may have been forgotten

1. A **push channel to a phone** — mail to `human` is a mailbox nobody
   watches. Without it every fix above still ends in an unread message.
2. **Branch protection** on the three repos; agents hold push rights.
3. **Prompt injection**: unattended agents with skip-permissions read
   issues, PR comments and CI logs.
4. **Single machine**: one Windows PC + WSL. Auto-start after reboot, Dolt
   off-box restore drill, what happens while the PC sleeps.
5. **Spend visibility**: no ceiling by decision (ADR-0015); still no daily
   token report, so a looping agent is invisible (`af-a9px` covers display).
6. **Pack pin drift**: formulas change wholesale on the next fetch; forks
   must be re-diffed — needs a check.
7. **Model deprecation** and non-quota provider errors (`af-s6fqv`).
8. **The factory reviewing itself**: review formulas have 0 runs; the
   independent reviewer exists but nothing routes to it by default.
9. **Production**: there is no deploy path, so "V1 released" cannot happen
   yet, whatever the factory delivers.
10. **Human runbook** for when no PO session is open, in French.
11. **Definition of done for autonomy**: a number — e.g. 7 days, zero
    unplanned human interventions, every stall paged inside 30 min.
