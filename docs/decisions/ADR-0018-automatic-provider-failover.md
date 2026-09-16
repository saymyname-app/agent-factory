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

## Evidence

- `tests/provider-failover-test.py` — detection on the real messages, pools,
  chains, backoff, manual controls, overlay, and the end-to-end acceptance
  scenario of af-ogyq: a Codex wall switches workers and restarts the stuck
  one without touching the campaign; total exhaustion parks with the earliest
  reset and resumes by itself three hours later; a block this tool did not set
  is never lifted.
- `tests/factory-guard-provider-overlay-test.sh` — the guard regenerates a
  missing overlay, and reports a failure to do so.
- `tests/factory-cockpit-test.py` — the bridge only calls the tool, and the
  route requires its own confirmation header.
- Live, 2026-09-16: overlay activated with no session restart; a forced switch
  moved a running session and back; mark and restore round-tripped from the
  cockpit on desktop and at phone width.
