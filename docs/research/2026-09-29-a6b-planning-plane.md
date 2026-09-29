# A6b research: planning beads vs delivery consumers (af-0aiero.3)

- Ticket: af-0aiero.3 "Planning beads never reach a worker" (map af-0aiero, A6b).
- Date: 2026-09-29, 20:52 (Paris).
- Code read at `agent-factory` commit `8340d3dcef96e784e3ff17b8ad3f049391a50991` (= origin/main at research time). All `file:line` below refer to that commit.
- Runtime: gc 1.4.1 (`/usr/local/bin/gc`), live city `/home/benja/agent-factory`, read-only commands only (`bd show`, `bd ready`, `bd list`, `gc hook <agent>` without `--claim`, `gc config show`, `gc session list`).
- Bead shape tested: `gc.plane=planning` metadata, `wayfinder:*` labels, epic + tasks with parent-child edges, open/in_progress, assignee `po-agent` or unassigned. Live examples: af-0aiero (epic, open, unassigned), af-0aiero.1-.3 (in_progress, assignee `po-agent`), af-0aiero.7-.10 (open, unassigned).

## Answer

No code path (order, guard, wake script, gc work query, delivery proof) routes, dispatches, wakes a worker for, or counts as delivery a planning bead today. Two filters do this: explicit `gc.plane=delivery` checks where it matters (idle-ready-work-wake, deliver-close, delivery proof), and gc's pool work query, which only returns beads with `gc.routed_to`/assignee equal to a gc agent or session. Planning beads have neither, and `po-agent` is not a gc agent.

There is one gap, and it is not in code: **the Mayor**. Its prompt tells it to dispatch "ready, unassigned beads of an open convoy published by `bin/ticket-graph-publish` (`gc bd ready`)". That excludes planning beads only because the Mayor reads the prose correctly. The dispatch door has no plane check to back it up. The unassigned planning beads (af-0aiero, af-0aiero.7-.10) do show up in the root `bd ready` output the Mayor is told to read. Nothing mails or wakes the Mayor because of them, so the risk is latent: it only applies on a turn where the Mayor is already reading `gc bd ready`.

## Live evidence (read-only)

| Check | Result |
|---|---|
| `bd ready --json` (city root) | af-0aiero, .7, .8, .9, .10 listed (open, no assignee, `gc.plane=planning`), next to delivery bead af-a3ajo (`gc.plane=delivery`). |
| `bd list --assignee po-agent --status open,in_progress` | af-0aiero.1, .2, .3 (in_progress, planning). |
| `gc hook factory-worker / mayor / dog / bd.dog / claude / claude-standard / codex` | Only message beads (mail, routed or assigned to that agent). No af-0aiero.* bead in any. |
| `gc hook po-agent` | `agent "po-agent" not found in config`, so gc has no agent or session that could be woken for `po-agent`. |
| `gc session list` | Active: `mayor`, `core.control-dispatcher`. No factory-worker session. |
| `.beads/interactions.jsonl` for `af-0aiero*` | 7 interactions, all actor `po-agent`. No Mayor, order or guard has touched them. |
| `gc mail inbox mayor` grep `aiero` | Nothing. The latest idle-ready-work mail (19:51 Paris) counts 1 delivery-plane bead (af-a3ajo), not planning. |

## Consumer inventory

Verdict key: **SAFE+** requires `gc.plane=delivery` positively · **SAFE** filters on something planning beads never carry (explained) · **RISK** could pick up or alert on planning beads.

### Wake and dispatch

| Consumer | file:line | What it reads | Verdict |
|---|---|---|---|
| idle-ready-work-wake (order, 5 m condition) | `bin/idle-ready-work-wake:52-66`, mail `:102-117`; `orders/idle-ready-work-wake.toml:9-12` | `bd ready --json`, counts only `metadata["gc.plane"] == "delivery"` (`:65`) | SAFE+ |
| gc pool work query / scale_check (factory-worker, dog, claude*, codex) | not configured in repo: `agents/factory-worker/agent.toml:1-6` has no `work_query`; `gc config show` shows none, so the gc default applies | Default query returns beads routed (`gc.routed_to`) or assigned to that agent/session. Upstream gastown pack prompt: `gc sling` "sets gc.routed_to metadata for controller scale_check" (`gastown/agents/mayor/prompt.template.md:26,31` in `~/.gc/cache/repos`); labels do not trigger scale_check (`:225`). | SAFE (empirical: `gc hook` per agent above). Source of the default query not read: UNVERIFIED at source level |
| gc wake for assignee `po-agent` | gc runtime | `po-agent` is not a configured agent (`gc hook po-agent` → not found) | SAFE |
| factory-worker claim protocol | `agents/factory-worker/prompt.template.md:15-19, 34-35` | Only `gc hook --claim --json`; forbids broad `bd ready`/`bd list` | SAFE |
| **Mayor prompt, turn step 2** | `agents/mayor/prompt.template.md:49-57` | "Dispatch the ready, unassigned beads of an open convoy published by `bin/ticket-graph-publish` (`gc bd ready`)". Prose filter, no `gc.plane` mention anywhere in `agents/`. Also `:172` "Monitor: `gc bd list`". | **RISK (latent, LLM judgment only)** |
| Mayor prompt, work sources | `agents/mayor/prompt.template.md:102-107, 114-118` | Only 3 sources: published convoy, mail naming it, guard-filed bead. A planning bead is none of these. | Mitigates the risk above, as prose |
| dispatch-door (the one sling door) | `bin/dispatch-door:218-222` (label check), `:192` (sling) | Refuses only label `proposal`, provider exhaustion, low memory, hot-path overlap. **No `gc.plane` check.** | **RISK (no hard gate)**: if the Mayor passes a planning id, the door slings it to factory-worker with `--reassign` (which also overwrites assignee `po-agent`). |
| factory-work-dispatch | `bin/factory-work-dispatch:56-63` | Only checks `af-*` id and formula, then calls dispatch-door | Same RISK as the door (planning ids are `af-*`) |
| ticket-graph-publish | `bin/ticket-graph-publish:301-343`, `:359-365` | Writes `gc.plane=delivery` on convoy and tickets; `graph_members` filters on `gc.graph_digest` | SAFE (planning beads have no digest) |
| on-session-stranded (event) | `bin/on-session-stranded:62-76` | Only bead ids from a stranded gc session's `work_bead_ids` | SAFE (no gc session ever holds a planning bead) |

### Guards that list open/in_progress beads

| Consumer | file:line | Filter | Verdict |
|---|---|---|---|
| factory-guard rig-dispatch | `bin/factory-guard:456-484` | `gc bd ready` inside `rigs/$rig` for product rigs only (`project_registry_rig_names` = saymyname-backend, saymyname-frontend). Only prints the count; alerts only on a suspended rig or a gc timeout (`:476-479`). | SAFE (af-0aiero lives in the city root store, which is never counted; and the count does not trigger an alert) |
| factory-dispatch-guard | `bin/factory-dispatch-guard:137-138, 174-178` | `--has-metadata-key gc.routed_to` | SAFE |
| dispatch-door-guard | `bin/dispatch-door-guard:81-82` | `--has-metadata-key gc.routed_to` | SAFE |
| factory-waiting-guard | `bin/factory-waiting-guard:108-109` | `--has-metadata-key gc.waiting_on` | SAFE |
| factory-planning-exception-guard | `bin/factory-planning-exception-guard:106-118, 142-151` | Closed beads with `gc.work_outcome` blocked/abandoned + classification; open beads with `gc.redecomposes` | SAFE |
| escalation-door list / sweep | `bin/escalation-door:148, 188-191` | `gc.escalation_mayor_paged_at`, `gc.needs_benjamin`, label `proposal` | SAFE |
| dispatch-door hot-path check | `bin/dispatch-door:240` | in_progress with `gc.scope_paths` | SAFE |
| pr-autopilot | `bin/pr-autopilot:192-204, 427-432, 566` | Open beads of each rig (agent-factory root included), but matched by PR number, `gc.work_branch`, `gc.delivered_via_pr`, `gc.waiting_on`, or a `blocks` dep on a PR bead | SAFE (planning beads have none of these keys, and their `blocks` edges point to planning beads) |
| factory-delivery-guard | `bin/factory-delivery-guard:132, 191` | Closed + label `product-goal`, or closed + `gc.pr_url` | SAFE (closing a planning bead with `bd close` does not trigger it) |
| factory-watchdog | `bin/factory-watchdog:102, 159, 263`; title lookups `:131, 213, 271, 306` | Gates, `gc.kind=workflow`, `gc:control-quarantined`, its own titles | SAFE |
| factory-session-loop-guard | `bin/factory-session-loop-guard:76, 130, 163` | Its own titles (`--title-contains`) | SAFE |
| on-order-failed, backup-freshness, factory-maintain | `bin/on-order-failed:61`, `bin/backup-freshness:80`, `bin/factory-maintain:167` | Their own titles | SAFE |
| mail-reply-reap sweep (order) | `bin/mail-reply-reap:71-74`; `orders/mail-reply-reap.toml:11-12` | `--type message` only | SAFE |
| mail-reply-reap should-wake | `bin/mail-reply-reap:99-104` | `bd list --assignee X --status open,in_progress` with no plane filter: would count `po-agent` planning beads as "claimable" for `--assignee po-agent`. | SAFE today: no caller in bin/, orders/, city.toml, and nobody would pass `po-agent`. Latent if it is ever wired to a wake. |

### Delivery proof

| Consumer | file:line | Verdict |
|---|---|---|
| deliver-close `requires_pr_contract` | `bin/deliver-close:155-165` | SAFE+: PR contract only for `gc.delivery_contract=pr-ci-merged-v1`, or `gc.plane=delivery` + `sha256:` digest, or PR/CI fields. A planning bead is closed without a PR claim. |
| `lib/factory_delivery_proof.py` `requires_pr_delivery_proof` / `delivery_readiness` | `:153-180`, `:227-254` | SAFE+: same rule. A closed planning bead is `closed-non-pr`, `ready: True` (`:246-247`), so it releases a `blocks` edge like any plain bead. It never counts as a PR delivery. |
| goal-delivery-pairs | `bin/goal-delivery-pairs:112-118` | SAFE: `gc.goal` + `gc.delivery_status` |

### Non-live / test-only

- `bin/fixture-city-oracle:452-468`: fixture oracle that fails when "planning-plane work became routable". It encodes the intended invariant but runs in tests only, not against the live city.
- `bin/wayfinding-run:150-152, 188, 389-402`: writes `plane: planning` into its JSON map; `route-check` reports delivery-routable only for `plane == "delivery"`. It does not read Beads.
- `bin/factory-observe`, `lib/factory_observe.py`: no order calls them (not in `orders/`); they wake from a snapshot file, not from Beads.
- `bin/operator-mail:45-51`: `po-agent` is the operator's mail sender alias. It is not an agent and not an assignee query.

## Risks

1. **R1: no hard plane gate at the dispatch door** (`bin/dispatch-door:218-222`). The only thing keeping planning beads away from factory-worker is the Mayor's reading of `agents/mayor/prompt.template.md:49-57`. af-0aiero, af-0aiero.7-.10 are in the root `gc bd ready` output right now. If the Mayor slings one, `--reassign` also takes the bead's assignee away (for example `po-agent` on af-0aiero.1-.3). Not an immediate wake: nothing mails the Mayor about them (idle-ready-work-wake is SAFE+), and no Mayor or guard interaction on af-0aiero* exists so far. Code-first fix, as a class and not per bead: dispatch-door refuses anything without `gc.plane=delivery` (or at least refuses `gc.plane=planning`), the same way it refuses `proposal`. Optionally, add one line to the Mayor prompt ("dispatch only `gc.plane=delivery`").
2. **R2 (minor, latent)**: `bin/mail-reply-reap should-wake` counts every non-infra assigned bead with no plane filter. It has no caller today.

## UNVERIFIED

- gc's built-in default `work_query` / `scale_check` text (gc 1.4.1 source not read). The behaviour was verified empirically with `gc hook <agent>` for every city-scope agent, and it matches the upstream gastown pack prompt (routing via `gc.routed_to`). Product-rig role agents (`saymyname-*/gc.*`) were not hooked individually; they only see their rig store, not the city root.
- Whether the Mayor LLM would actually pick a planning bead. This is a behaviour question, and it has not happened (no interactions).
