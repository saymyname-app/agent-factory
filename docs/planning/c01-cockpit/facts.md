# C01 "Cockpit V2" — live facts (read-only, 2026-09-29 14:20-14:45 Paris)

Gathered by the PO agent and a read-only sub-agent. Nothing was changed
while collecting them. INFERRED marks what was not verified directly.

## Signals that exist today (all land at the Mayor or in gc mail, none on a phone)

| Signal | Producer | Lands in | Surfaced to Benjamin today |
|---|---|---|---|
| NEEDS BENJAMIN | `bin/escalation-door benjamin` / `sweep` (every 15 min, promotes a Mayor-first escalation after 2 h) | bead metadata `gc.needs_benjamin`, notes line, mail to `human` | only if an agent runs `escalation-door list` — no hook or instruction did (fixed as interim in SayMyName AGENTS.md, c6c35db) |
| Mayor-first escalation | `escalation-door mayor` (on-order-failed, factory-watchdog, session-loop-guard, mol-scoped-work) | Mayor mail, `gc.escalation_mayor_paged_at` | no |
| Proposals | Mayor, `bin/overlap-conflict-log` | open beads label `proposal` | count in `escalation-door list` |
| Rituals | SayMyName `tools/rituals-status.sh` | stdout DUE/ok | operator session start only |
| order.failed | gc controller | `.gc/events.jsonl`; `orders/on-order-failed.toml` pages the Mayor on repeats | no |
| Red / conflicted PR | `bin/pr-autopilot` (3 min), P06 return loop | `[ci]` bug bead, rejection reason; 3rd rejection → escalation door | via NEEDS BENJAMIN only |
| Wake/stop loop | `orders/factory-session-loop-guard.toml` (P14, >10 cycles/h: Mayor-first + pause), `spawn-storm-detect` | mail + `session.drain_acked_with_assigned_work` events | no |
| Idle Mayor with ready work | `orders/idle-ready-work-wake.toml` | Mayor mail (22 today) | no; blind while a worker counts as active |
| factory-guard / dispatch-guard / watchdog | orders every 5 min | self-heal, Mayor mail | no |
| Convoy progress | Beads (`bd show <convoy>`) | Beads | nothing pushes it |

Noise already measured: af-sqrri (3 near-identical mails in 43 s; a
watchdog mail repeated 4 times in 40 s despite a 5-min cooldown;
on-order-failed re-sending after clear), af-pgm3y (re-fire for an order
already skip-listed, attached to an unrelated closed bead → stale
`NEEDS BENJAMIN: af-fnew1` mail at 00:09), SayMyName incident review cause E
(two `[ci]` beads per PR). `.gc/runtime/factory-watchdog-signals.json` has no
writer any more (O06).

## Cockpit V1 and old ntfy (legacy, untrusted — evidence only)

`legacy/README.md` row 1 (2026-09-26). A 5-min order turned a cockpit
snapshot file into ntfy alerts (decision needed, resume required, campaign
blocked, guard warning, "back to normal", provider problems), digests at
08:00 and 20:00, and hourly reminders. Server: hosted `https://ntfy.sh`, a
private topic name as the only access control, configured in an untracked
local file or env var (value not read). Retired with the campaign because
the notifier read the V1 snapshot and V1 was its only writer. Benjamin
(C01 Q2): too noisy, unreliable, stale sections, did not say what to do.

## Platform facts

- Tailscale: PC `benforge` (Windows) and `iphone-11` (iOS) on Benjamin's
  tailnet; the iPhone was offline for 4 days on 2026-09-29. Not installed
  inside WSL.
- `config/projects/*.toml`: one file per repo/rig (agent-factory,
  saymyname-backend, saymyname-frontend) with technical fields only (rig
  dir, repo, protected branch, required CI/check, sling target, formulas).
  Nothing groups repos into a product or points to a roadmap.
- The SayMyName project repo (`C:\Dev\Projects\SayMyName`, knowledge,
  roadmap, state) is not a Factory rig.
- `config/operator.toml` holds the operator name and mail alias.
- Ticket titles are written in English by planning agents.

## ntfy options (facts; prices and limits not verified)

- Hosted ntfy.sh without account: a topic is public to whoever knows its
  name; rate-limited; content transits a third-party server.
- Hosted with a paid account: reserved topics with access control (spend).
- Self-hosted: needs a server the phone reaches; iOS instant delivery
  relies on the upstream ntfy.sh relay (UNVERIFIED).

## What must never reach a phone

SayMyName `knowledge/real-person-data.md`: no real person's name or photo
in any repo, fixture, log, bead or report; secrets and topic names never in
git or chat. Payloads carry level, event class, project and a cockpit link,
never bead bodies or product data.

## Night of 2026-09-28/29 (what the cockpit had to surface)

Worker wake/stop loops 03:05-04:48 and 05:15 (~60 cycles/h, ~3 h of
manual back-and-forth); Mayor idle 03:44-04:14 and claiming "fixed" from
session state; test mails leaking as real escalations 06:35-08:09;
pr-autopilot `order.failed` every tick 11:07-11:21 (broke A5's proof);
silent failure of the publish-time Mayor wake at 02:35; first 2-worker
conflict at 13:44 handled by the return loop.
