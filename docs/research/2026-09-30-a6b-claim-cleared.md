# What silently cleared the af-0aiero.7 claim (af-0aiero.12)

**Answer.**
- **Cause.** Gas City's bundled core-pack order `orphan-sweep` (exec script, runs every 5 min) cleared the claim. It resets every `in_progress` bead whose assignee is not a configured gc agent, not a live gc session and not the literal `human`. An operator session's actor `po-agent/2dd241a3` is none of these, so the sweep treated the claim as an orphan. It ran `gc bd release-if-current af-0aiero.7 po-agent/2dd241a3` at 00:55:29 (Paris), 5 min 41 s after the claim. No sibling session, bd default, Dolt merge or Factory script was involved.
- **The af-0aiero.2 rule.** The rule still holds for what it describes: `--claim` is still an atomic compare-and-set between distinct actors, and the release is itself conditional. Its unstated premise is false in this city: a claim does **not** persist until its owner closes it. Every claim made by a non-gc actor is revoked at the next sweep, 5 to 10 min later. After that a sibling session can claim the same ticket, which is exactly the double work the rule was meant to prevent. The rule is incomplete, not wrong.
- **Class fix (mechanism).** Stop the sweep from treating operator identities as dead agents. Add `orphan-sweep` to `[orders] skip` in `city.toml` and replace it with a Factory-owned order that runs a copy of the upstream script with one added guard in `is_known_agent`: assignees in the operator namespace `po-agent/*` are known. A test pins the upstream script hash, so a gc upgrade that changes the upstream script fails loudly instead of drifting silently. The upstream behaviour is by design: "Reset beads assigned to dead agents". That makes it UPSTREAM and a local config matter; no upstream issue is needed.

Times are Europe/Paris (CEST, UTC+2). Dolt stores UTC, so 22:55:29Z = 00:55:29 on 30 Sep, Paris time.

## 1. The write that cleared the claim (Dolt history)

Beads DB: `/home/benja/agent-factory/.beads`, server mode, database `hq`. The data was read through the running server with SELECT-only queries: `dolt --host 127.0.0.1 --port <port> ... --use-db hq sql -q`.

These are **all** the commits that ever changed the row `af-0aiero.7`. The query was `select ... from dolt_diff_issues d join dolt_log l on l.commit_hash=d.to_commit where d.to_id='af-0aiero.7' or d.from_id='af-0aiero.7'`.

| Paris time | Commit | Message | status | assignee |
|---|---|---|---|---|
| 29 Sep 20:47:28 | `9bdhr2fp0o0vmmkckmcen6hssqebulog` | `bd: create af-0aiero.7` | → open | NULL |
| 30 Sep 00:49:48 | `tif6sscsre1bqdh9fhctgglg7n22s3ue` | `bd: claim af-0aiero.7` | open → in_progress | → `po-agent/2dd241a3` |
| 30 Sep 00:55:29.329 | `e5h5795erhv71dt3h71tookcauc3begn` | **`gc: release bead af-0aiero.7 if current`** | in_progress → open | `po-agent/2dd241a3` → `''` |
| 30 Sep 01:07:07 | `2md8t5ktbpqtbrud9isgjrnfl8h73kcu` | `bd: claim af-0aiero.7` | open → in_progress | → `po-agent/2dd241a3` |
| 30 Sep 01:07:59 | `p0rkuo68grhklns0ur4e681em870p6bm` | `bd: close af-0aiero.7` | → closed | unchanged |

- The clearing commit touched **only** table `issues`, and within it only `af-0aiero.7`. Checked with `select * from dolt_diff where commit_hash='e5h5795e…'` and `dolt_diff('uiti56f…','e5h5795e…','issues')`. That commit changed status and assignee only. It wrote no note and no metadata, and `metadata` stayed `{"gc.plane":"planning"}`. This matches what was observed.
- The assignee became the empty string `''`, not NULL. `bd` uses NULL for "never assigned". The Go store writes `''` explicitly (§3).
- Committer `beads <beads@local>` is shared by every writer, so the author cannot be identified from the commit. The message prefix `gc:` identifies the writer: every `bd` CLI write commits as `bd: <verb> <id>`.
- The claim lived **5 min 41 s**, not the 30 to 90 minutes estimated. The re-claim survived only because the ticket was closed 52 s later, before the next sweep.

## 2. Which gc component: the `orphan-sweep` order, not the reconciler

gc has two paths that end in the same commit message. Only one of them matches the evidence.

**Correlation with `orphan-sweep` runs.** In `.gc/events.jsonl`, `order.fired` for `orphan-sweep` was at 00:55:08.04 (seq 392156) and `order.completed` at 00:55:29.354 (seq 392166). The release commit is 00:55:29.329, which is 25 ms before the run completed. The same holds for **all 11** `gc: release bead … if current` commits in the database. Each one falls inside an `orphan-sweep` run window, and every one reset a `po-agent*` claim on a child of the map af-0aiero:

| Paris time | Bead | Cleared assignee | orphan-sweep run (fired → completed) |
|---|---|---|---|
| 29 Sep 20:50:04 / :07 / :09 | .2 / .3 / .1 | `po-agent` | → 20:50:09.49 |
| 29 Sep 21:39:42 | .4 | `po-agent/db9c7f3e` | 21:39:30 → 21:39:42.04 |
| 29 Sep 23:58:45 | .5 | `po-agent/f25b6012` | 23:58:08 → 23:58:45.42 |
| 30 Sep 00:49:39–00:49:55 | .11, .10, .8, .6 | `po-agent/513ac0c5…`, `po-agent/aff7dc9f…`, `po-agent/c0936b96`, `po-agent/77299ee9` | 00:49:19.99 → 00:49:55.52 |
| 30 Sep 00:55:29 | .7 | `po-agent/2dd241a3` | 00:55:08.04 → 00:55:29.35 |
| 30 Sep 01:12:00 | .12 (this ticket) | `po-agent/2dd241a3` | → 01:12:00.38 |

Queries: `select l.date, d.to_id, d.from_assignee from dolt_diff_issues d join dolt_log l on … where l.message like 'gc: release bead%'`, and `grep -a '"subject":"orphan-sweep"' .gc/events.jsonl`.

A plain `po-agent` actor (20:50) was reset the same way as `po-agent/<id>`. The trigger is "the actor is not a gc identity", not the per-session suffix.

The .7 claim was made at 00:49:48, *during* the 00:49:19 run. That run had already listed the in_progress beads, so .7 escaped it and was caught by the next run.

**The Go reconciler is ruled out.** `releaseOrphanedPoolAssignments` releases only pool-routed work. It skips a bead whose `gc.routed_to` / legacy workflow target is empty (`cmd/gc/pool_session_name.go`, `releaseOrphanedPoolAssignments`, `template := routedToOrLegacyWorkflowTarget(wb); if template == "" { continue }`; `cmd/gc/work_routing_metadata.go:20`). af-0aiero.7 had only `gc.plane=planning`. That reconciler also emits `bead.dead_assignee_reopened` for each release (`cmd/gc/dead_assignee_event.go`). None of the 18 such events in `events.jsonl` concerns an af-0aiero bead: all of them are dated 15 to 24 Sep and concern worker routes.

## 3. The mechanism in source (gascity v1.4.1, rev `58ef17e3bd685fd5cf7f21286277b208d3324590`)

The installed `gc` reports `1.4.1`, and its embedded build info says `vcs.revision=58ef17e3…`. The deployed pack copies under `~/.gc/cache/repos/*/internal/bootstrap/packs/core/` are byte-identical to that revision (`diff -q`). `gc order list` shows `orphan-sweep  exec  cooldown  5m`. The Factory `city.toml` `[orders] skip` list does not include it.

The chain from order to commit, with files at https://github.com/gastownhall/gascity/tree/58ef17e3bd685fd5cf7f21286277b208d3324590:

1. `internal/bootstrap/packs/core/orders/orphan-sweep.toml` declares `description = "Reset beads assigned to dead agents back to the work pool"`, `trigger = "cooldown"`, `interval = "5m"`, and runs `assets/scripts/orphan-sweep.sh`.
2. `internal/bootstrap/packs/core/assets/scripts/orphan-sweep.sh`:
   - L58 lists **all** HQ `in_progress` beads with `gc bd list --status=in_progress --json --limit=0`. There is no filter on routing, plane or label.
   - L106 gets the known agents from `gc config explain`. The Factory resolves 43 agents, and none is `po-agent`.
   - L138–158 build the live identities from `gc session list --json`. PO operator sessions are Claude/Codex sessions outside gc, so they are never listed.
   - L285–335 is `is_known_agent`. The only non-agent exemption is the exact string `human` (L295): "without this guard the sweep resets any in_progress human-assigned bead … silently wiping the operator's claim". Pool suffix `-N` and dotted forms are also accepted. `po-agent/2dd241a3` matches none of them.
   - L341–370: for an unknown assignee, the script re-reads the bead (L175–187), probes for a live session bead (L219–265), then calls `reset_orphan_if_current`.
   - L273 is that reset: `gc bd release-if-current "$bead_id" "$expected_assignee"`.
3. `cmd/gc/cmd_bd.go:232`, `:363` intercept `gc bd release-if-current <id> <assignee>` and call `doBdReleaseIfCurrent` (`:490`).
4. `internal/beads/native_dolt_store.go:1093–1125` is `ReleaseIfCurrent`. It runs one Dolt transaction with the message `fmt.Sprintf("gc: release bead %s if current", id)` (L1102). The transaction sets `status=open, assignee=""` only if the status is still `in_progress` and the assignee still equals the expected one. That is the exact commit message and the `''` value seen in §1.

Upstream `main` (`9f9c2e30…`, 2026-09-29 22:19 UTC) has the same `is_known_agent` rule, with the `human`-only exemption and no plane or namespace opt-out. Only comments and a zero-session-rows guard changed. An upgrade will not fix this.

## 4. Hypotheses ruled out

| Hypothesis | Verdict | Evidence |
|---|---|---|
| A parallel Claude session wrote to .7 (wrong id, `--status open --assignee ""`, close…) | **No** | Only the 5 commits in §1 ever changed the row. Between claim and release, the other commits (22:53–22:55 UTC) were `bd: comment af-0aiero.11/.1/.10`, `bd: close af-0aiero.11`, `bd: update af-0aiero`, `bd: update af-jzg31`, and none touched .7. Searching the transcripts for a `bd … update/close/reopen/assign/release … af-0aiero.7` command finds only session 2dd241a3 itself and one prompt template placeholder (`po-agent/<your-session-id>`) in `f25b6012-….jsonl`, which is not an executed command. |
| A side effect of updating the parent map (`bd update af-0aiero --body-file`, `bd create --parent`, `bd dep add`) | **No** | `bd: update af-0aiero` at 22:53:51 UTC left the .7 row unchanged (`dolt_history_issues` shows the same `updated_at` 22:49:48 before and after). |
| Dolt sync/merge overwrote the row | **No** | The change is a single ordinary commit with a `gc:` message. Every other release is the same pattern. |
| Factory scripts (`bin/on-session-stranded`, `bin/factory-dispatch-guard`) | **No** | They write through `bd` with notes/metadata (`bd:` commits). The Factory `bin lib orders formulas config` contain no `release-if-current`. |
| Codex sessions | **No** | A Codex `bd` write would show as a `bd:` commit. There is none on .7. |
| `.beads/interactions.jsonl` audit | n/a | It records only the final close (01:07:59 Paris, actor `po-agent/2dd241a3`). bd does not log gc's in-transaction release there. |

## 5. Consequences for the af-0aiero.2 claim rule

- **What still holds.** `bd update --claim` is an atomic compare-and-set between distinct actors (af-0aiero.2, verified on bd 1.2.2 `@6c124203e`). The sweep's release is also conditional, so a claim made *after* the sweep's re-read is not lost; see the 00:49:48 claim that survived the 00:49 run.
- **What breaks.** The rule assumed a claim lasts until its owner closes or unclaims it. In this city, a claim by any actor gc does not know (`po-agent`, `po-agent/<id>`, anything except `human`, a configured agent or a live gc session) is revoked at the next `orphan-sweep`, within 5 min plus run time. The revocation writes no note, comment or event: the order logs only `order.completed`. A sibling session can then claim the ticket successfully, and the first session keeps working, unaware.
- **This is live now.** af-0aiero.12, this research ticket, was itself released at 01:12:00 Paris and currently shows `open` with assignee `''`.

## 6. Recommended class fix

The goal is that operator claims survive the sweep, and dead gc-agent claims keep being recovered.

| Option | Mechanism | Verdict |
|---|---|---|
| A. Skip `orphan-sweep` and ship a Factory copy with an operator exemption | `[orders] skip += "orphan-sweep"`. A new Factory order `factory-orphan-sweep` (cooldown 5m) runs a vendored copy of the upstream script with one added line in `is_known_agent`: `case "$name" in po-agent/*) return 0;; esac`. A test asserts the sha256 of the upstream `orphan-sweep.sh` in the gc cache equals the pinned one, so a gc upgrade forces a re-vendor. | **Recommended.** It is reversible (drop the skip) and local. Dead-agent recovery is kept. The exemption is scoped to the namespace that the af-0aiero.2 rule already mandates. |
| B. Exempt by plane instead of actor | Same fork, but skip beads whose `metadata["gc.plane"] == "planning"`. | Also protects planning beads claimed by a non-namespaced actor. It fails to protect operator claims on delivery beads. It could be combined with A. |
| C. Claim as `human` | Uses the upstream exemption. | **Rejected.** Every session becomes the same actor, so `--claim` becomes idempotent across sessions and loses its protection (af-0aiero.2). |
| D. Register a fake `po-agent` agent in config | `agent_exists` would match only the exact `po-agent` string, not `po-agent/<id>`, and it pollutes the agent roster. | Rejected. |
| E. Only skip `orphan-sweep` | This loses dead-agent recovery for non-routed gc work. The Go reconciler covers only pool-routed work (§2). | Not recommended. |

Trade-off of A and B: an operator claim then never expires by itself. That is acceptable under af-0aiero.2, because a sibling's `--claim` on it fails with exit 1 and the stale claim is visible. A dead PO session's claim still has to be released deliberately. If automatic expiry is later wanted, the forked guard can require `updated_at` to be younger than N hours before exempting.

Classification: UPSTREAM behaviour working as designed, "beads assigned to non-existent agents get reset". The fix is local Factory configuration. No upstream issue or PR is needed.
