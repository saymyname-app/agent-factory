# ADR-0018: Automatic model-provider failover, adjustable from the cockpit

- Status: Accepted
- Date: 2026-09-16
- Decided by: Benjamin, in conversation, 2026-09-16: « repli auto vers autre
  fournisseur de modèle : oui et il faut pouvoir paramétrer ça dans le cockpit.
  Parfois les limites bloquent l'utilisation de GPT ou Claude, et il faut que ça
  soit géré automatiquement ou facilement par moi si on ne peut pas
  automatiser. » Implemented by the PO/Tech Lead the same day.
- Implements: ADR-0016 §7 row "All providers out of quota" (bead af-ogyq).
- Extends: ADR-0006 (token-free human cockpit), ADR-0013 (campaign).

## Context

Quota walls are routine, not exceptional. On 2026-09-15 the standard Codex pool
ran out until 2026-09-21 and a Claude session limit stopped a batch of review
agents the same day. Both were handled by a human:

- `city.toml` carried `REVERT TO provider = "codex" WHEN THE CODEX QUOTA
  RESETS`. Someone had to notice the wall, edit the file, reload, and then
  remember — six days later — to edit it back.
- A worker that hits a wall does not crash. It sits at its prompt showing the
  limit message, looking alive to every health check.

Gas City has no native failover. It does have what failover needs:

- a top-level `include = [...]` in `city.toml`, whose later file overrides
  `workspace.provider` and, through `[[patches.agent]]`, an agent's pinned
  provider — verified on a copy of this city;
- config-drift handling: when a running session's provider changes in the
  effective config, the controller replaces that session on the new provider —
  verified live on 2026-09-16, the reviewer moved from `claude` to
  `claude-standard` and back within 15 s each way.

## Decision

### 1. Three layers, one writer

| layer | file | versioned | who writes |
|---|---|---|---|
| policy | `config/provider-policy.json` | yes | a human, by commit |
| state | `.gc/provider-state.json` | no | `bin/provider-failover` only |
| overlay | `city.provider.toml` | no (gitignored) | `bin/provider-failover` only |

`city.toml` includes the overlay as its first key. The cockpit never edits a
file: it calls the tool, which holds a lock, rewrites the overlay atomically and
reloads the city only when the overlay actually changed.

### 2. Quotas belong to pools, not providers

Every Claude profile shares one Anthropic account, so one session limit
exhausts `claude`, `claude-standard` and `claude-cheap` together. The standard
Codex pool and the Spark allocation are separate. The policy maps each provider
to its pool, and exhaustion is recorded per pool.

### 3. One ordered chain per target

Targets are `workspace` (every rig worker) and each agent under `agents/`. Each
has an ordered fallback chain. Resolution picks the first provider that is
available; a pool reported *low* (≤ 5 % left) is used only when nothing
healthier remains. The default chains encode two existing rules: Codex is the
proven primary writer (`docs/DELIVERY.md`), and a reviewer should not review
work written by its own model, so reviewers fall back to the writer's family
only as a last resort.

### 4. Detection from what the session actually shows

Every two minutes the `provider-failover` order reads the tail of each live
model session's pane — through tmux in milliseconds, `gc session peek` as the
fallback — and matches the messages observed on this host:

- Codex: *"You've hit your usage limit … try again at Sep 21st, 2026 7:22 AM"*
  and the early warning *"less than 5% of your weekly limit left"*;
- Claude: *"You've hit your session limit · resets 6:50pm (Europe/Paris)"*.

Only the last 25 lines count, and a wall whose stated reset is already past is
ignored: history is not state. A wall with no stated reset is retried after 1 h,
then 2, 4 and 8 h.

A session found stuck on a wall is restarted with `gc session reset` once its
target resolves to another provider.

### 5. Coming back is automatic too

Exhaustion carries its reset time. When it passes, the pool is available again
and the chain's preferred provider comes back on the next tick. Nobody has to
remember to revert anything; the `REVERT TO codex` note is gone from
`city.toml`.

### 6. Only total exhaustion parks the campaign — and it resumes by itself

If no worker provider is left, the tool blocks the campaign with kind `limit`,
owner `Mayor`, a cause starting `[provider-failover]` and the earliest reset. It
never sets `gc.needs_benjamin`. When a worker provider is available again, it
resumes exactly the blocks it set, and no other.

### 7. The human controls, from the cockpit (desktop and phone)

Seven reversible, zero-token controls: mark a pool exhausted (for a duration or
until a date), restore it, disable or re-enable a provider, force a provider on
a target, reorder a chain, and switch automatic mode off. With automatic mode
off, detections are shown but not acted on; manual marks still apply. A manual
mark outranks detection. Every control is recorded in the history.

The cockpit writes `by: "cockpit"`, not a person's name: it cannot know who
clicked, and a named attribution would be false whenever an agent tests the
page (see the PO mail attribution trap).

### 8. Safety

- A missing overlay makes the whole city config fail to load. It is
  regenerated by `factory-guard` (check 1b) and by any tool run; `bin/provider-failover`
  and its order are critical runtime files.
- A missing or corrupt state degrades to the policy defaults.
- With nothing available, the overlay keeps what was running rather than
  silently falling back to whatever `city.toml` says.

## Consequences

- A quota wall no longer needs Benjamin, and neither does its end.
- The cockpit shows, in French, which model each part of the factory runs on
  and why.
- Cost: one tick is ~1 s and < 1 s CPU every two minutes (measured after
  replacing `gc session peek` with tmux; the first version cost 54 s and 22 s
  CPU per tick, and was caught before it shipped).
- Known limit: detection reads what a session prints. A provider that fails
  silently — no message, no exit — is not detected here; the liveness watchdog
  (ADR-0016 §5.3) is what notices a factory that stops advancing.

### 9. A credential problem self-heals fast, not slowly (af-zdiln, 2026-09-20)

The provider_error backoff added for af-s6fqv (§4) climbs 10min → 20 → 40 …
capped at 8h, on the assumption that a non-quota failure is closer to a rate
limit than a quota wall. On 2026-09-20 Claude's login expired at ~12:10Z; the
pool was marked `error`/`auth`, and because every tick that still found the
banner counted as another strike, the hold reached its 8h cap. Benjamin fixed
the login at ~17:34Z, but nothing re-tested the provider before the hold
expired, so the factory sat idle until a human ran `set --action clear` by
hand at ~17:45Z.

An expired credential is a fixed fault, not a rate limit: waiting longer does
not make it less broken, and a fix does not need to wait out a stale hold to
take effect. So `category=auth` now:

- never grows past `policy.auth_hold_minutes` (10 by default), however many
  strikes accumulate -- every other category keeps the existing exponential
  backoff unchanged;
- is probed for free every tick: the first detection of an episode records a
  cheap fingerprint (mtime + size, never content) of the provider's local
  credential file (`~/.claude/.credentials.json` for `anthropic`,
  `~/.codex/auth.json` for the Codex pools). The next tick that finds the
  fingerprint changed clears the marking immediately -- no API call, so a
  genuinely broken or rate-limited provider is never hammered. If the file
  has not changed, the marking stays and the hold (still capped at 10min) is
  the only path back until it does.

This is additive: quota exhaustion and every other `provider_error` category
are untouched, and a human can still `set --action clear` at any time.

### 10. codex-spark removed (af-i6018, 2026-09-21)

Intent (Benjamin, 2026-09-20): « Il faut proprement enlever Spark. » — remove
the `codex-spark` provider and its `openai-spark` pool everywhere, leaving no
dead config and no fallback path that can reach it.

Mechanism: with a ChatGPT-account login the server rejects the model
(`"gpt-5.3-codex-spark is not supported when using Codex with a ChatGPT
account"`, HTTP 400) even under Pro x20, although the quota was displayed
(af-88za4; openai/codex#45590, closed not planned; #45972 open, no OpenAI
answer). It is not in the public API either. Its generated launch command was
also invalid — two conflicting model flags — which put every session that
tried it into a start-fail loop on 2026-09-20. `codex-spark` and
`openai-spark` are removed from `config/provider-policy.json`, `city.toml`,
`config/model-catalog.json`, `bin/factory-guard`'s config-sanity list, and the
`_REAUTH_HINT` map in `lib/ntfy_notify.py`; §2 and §3 above describe the pool
design as it stood at ADR authoring time and are left as written. A stale
`.gc/provider-state.json` still naming `codex-spark` is silently ignored by
`normalize_state` (§1/§4), never an error — `test_a_stale_state_naming_codex_spark_cannot_resolve_to_it`
(`tests/provider-failover-test.py`) asserts it can never make an agent
resolve to the removed provider.

Condition to re-add: a passing live test of the exact launch command against
this host's ChatGPT-account login, documented here, before Spark is reintroduced
anywhere in policy or chains.

### 11. Codex restored to first choice (af-wpjgu, 2026-09-21)

Intent (Benjamin, 2026-09-18): the 2026-09-18 provisional switch to
Claude-first for `workspace`, `mayor`, and `ux-reviewer` was explicit and
temporary — « codex vient en secondaire... pour l'instant », not a
permanent architecture change. It was to be revisited once Codex's standard
quota was confirmed reset and `codex-spark` was either confirmed usable
again or removed from the chain.

Mechanism: both conditions in the original bead are now met — Codex's
standard quota reset at 2026-09-21T05:22Z and `provider-failover status`
confirms the `openai` pool `available` as of 08:15Z; `codex-spark` was
removed outright rather than restored (§10, af-i6018). `config/provider-
policy.json`'s three affected chains (`workspace`, `mayor`, `ux-reviewer`)
are restored to Codex-first, Claude as fallback, per each target's original
design intent — `ux-reviewer` in particular regains its intended
reviewer/author model independence now that `workspace`/`mayor` are back on
Codex. `claude-reviewer`'s chain was never part of this provisional change
and is untouched.

### 12. The HQ writer inherits `workspace`; it is not named `workspace` (af-41ahv, 2026-09-21)

`workspace` is a provider-policy target, not a configured Gas City agent.
Treating it as an agent failed at dispatch; routing the same work to `bd.dog`
because that pool happened to inherit the resolved Codex provider then split
one `mol-do-work` graph across three fresh Dolt-maintenance sessions. The
first session created a worktree, a later one refused implementation, and the
workflow root nevertheless finalized pass. Provider resolution was healthy;
provider class and execution role had been conflated.

HQ implementation now has one named role, `factory-worker`. Its local agent
configuration deliberately contains no `provider`, so both effective config
and `target_of()` classify it under `workspace`; it follows cockpit changes,
quota failover, and automatic restoration without a second chain to drift.
`max_active_sessions = 1` plus the upstream implementation-worker claim and
continuation protocol keep a graph on one resumable session. The only
supported ordinary-HQ dispatch command is `bin/factory-work-dispatch`, whose
target and formula are fixed before it invokes `gc sling`; it cannot offer an
implementation graph to `bd.dog` or to a raw provider name.

This removes manual relaunch and worktree rescue, and avoids the extra model
turns consumed when several fresh pool sessions re-read the same graph. The
reversal is local: revert the role and dispatch door; provider policy and its
state remain unchanged.

The first live canary (`af-3l8hn`) found one more handoff bug before product
work resumed: `mol-do-work.workspace-setup` marked the target in progress with
`--claim`, leaving that target assigned to the session. The conventional
worker query prioritizes its assigned in-progress beads, so the continuation
hook selected the target itself ahead of `mol-do-work.do-work` and recorded a
premature shipped outcome before any PR. The local formula now immediately
clears only the target's assignee after the claim while preserving its
`in_progress` state and explicit session evidence. Routed formula steps remain
bound to the same session and therefore win the next continuation claim.

## Evidence

- `tests/provider-failover-test.py` — detection on the real messages, pools,
  chains, backoff, manual controls, overlay, and the end-to-end acceptance
  scenario of af-ogyq: a Codex wall switches workers and restarts the stuck
  one without touching the campaign; total exhaustion parks with the earliest
  reset and resumes by itself three hours later; a block this tool did not set
  is never lifted. `test_af_zdiln_auth_hold_is_capped_and_a_credential_refresh_self_heals_within_two_ticks`
  replays the 2026-09-20 incident: 7 error detections never push the hold past
  `auth_hold_minutes`, and a credential-file refresh clears the marking and
  regenerates the overlay within the very next tick.
- `tests/factory-work-dispatch-test.sh` — the HQ door has one fixed
  implementation target, refuses infrastructure/formula substitutions,
  keeps one active session, carries the continuation protocol, and pins no
  provider. It also locks the target-assignee release after workspace setup;
  `tests/provider-failover-test.py` proves that live sessions of this role map
  back to `workspace`.
- `tests/factory-guard-provider-overlay-test.sh` — the guard regenerates a
  missing overlay, and reports a failure to do so.
- `tests/factory-cockpit-test.py` — the bridge only calls the tool, and the
  route requires its own confirmation header.
- Live, 2026-09-16: overlay activated with no session restart; a forced switch
  moved a running session and back; mark and restore round-tripped from the
  cockpit on desktop and at phone width.
