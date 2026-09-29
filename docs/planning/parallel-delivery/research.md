# Parallel delivery on one repo — research (2026-09-28)

Scope: N parallel workers on the same repo, with conflict handling. Read-only.
`AF:` = `/home/benja/agent-factory` (live, HEAD 979c1a7). `GC@1.4.1` =
gastownhall/gascity tag v1.4.1 (commit 58ef17e3; the Factory pins gascity
sha f895c0ff, an ancestor of v1.4.1). `PACKS@3b3b89f` = gastownhall/gascity-packs
at the sha the Factory pins (AF:packs.lock:3-11).

## 1. Gas City native support — FACTS

| Capability | Exists upstream? | Evidence | Factory state |
|---|---|---|---|
| Worker pool size | Yes: `max_active_sessions` / `min_active_sessions` at agent level ("Replaces pool.max"), rig level ("cap on total concurrent sessions across all agents in this rig"), workspace level | https://github.com/gastownhall/gascity/blob/v1.4.1/docs/reference/config.md#L106 , #L724 , #L975 | Capped on purpose: `claude`=2 city, 1 per rig, reviewer 1 (AF:city.toml:223-251); `factory-worker` `max_active_sessions = 1` (AF:agents/factory-worker/agent.toml:5), enforced by a test (AF:tests/factory-work-dispatch-test.sh:42) |
| Demand-driven scaling | Yes: `scale_check` reports unassigned demand, "bounded by all cap levels"; `probe_concurrency` (default 8) bounds bd probes | gascity docs/reference/config.md:94, :315 (pinned sha f895c0ff, local clone) | Not customised |
| Merge-queue role ("Refinery") | Not in the binary: "Post-processing is a workflow step, not a standing role type"; "Polecat" = a pool (`min`/`max_active_sessions`) | gascity docs/getting-started/coming-from-gastown.md:155-156 | — |
| Refinery as config | Yes, in the **gastown** pack: `gastown/agents/refinery/agent.toml` (`max_active_sessions = 1`, own worktree), polecat pool `max_active_sessions = 5` | https://github.com/gastownhall/gascity-packs/blob/3b3b89f2011e06d84459aa7bea1552382f13930a/gastown/agents/refinery/agent.toml#L8 , .../gastown/agents/polecat/agent.toml#L7-L8 | **Not imported**: AF:pack.toml:5-14 imports only `bd`, `core`, `gascity`; rigs import `gascity/roles` (AF:city.toml:131-136, 199-212). `gascity/roles` has no refinery (tree listing at 3b3b89f: design-author … publisher, run-operator, task-decomposer) |
| Conflict handling in refinery | "Sequential Rebase Protocol": "After every merge, main moves. Next branch MUST rebase on new baseline." On rebase conflict: `git rebase --abort`, reopen bead with `rejection_reason="Conflicts with $TARGET at <sha>"`, route back to polecat pool, keep branch; merge is `--ff-only` | refinery prompt L13, L37, L192-L209; mol-refinery-patrol.toml L224-L239, L713 (same PACKS@3b3b89f paths) | Absent |
| Rejection-aware resume | Polecat prompt: resume existing branch, "fix the rejection reason (rebase conflict, test failure…)" | gascity examples/gastown/packs/gastown/agents/polecat/prompt.template.md:180-190 (f895c0ff) | Absent |
| PR-mode refinery | `merge_strategy = mr/pr` pushes the rebased branch and opens/updates a GitHub PR, then closes the bead at PR publication | mol-refinery-patrol.toml L396-L421 | Factory rejected it: "closes the bead at 'Pull request ready' anyway, so importing it would not have given close-on-merge" (AF:docs/DELIVERY.md:248-262) |
| Convoy | In Gas Town a convoy is "how you track batched work"; parallelism comes from the pool, not the convoy | https://github.com/gastownhall/gastown/blob/main/docs/overview.md (L47) | Mayor dispatches convoy beads "in dependency order, one writer per rig" (AF:agents/mayor/prompt.template.md:51) |

Why the Factory serialises (FACTS):
- Resource incident 2026-09-18: four workers + reviewer + Maven/Testcontainers left ~500 MB free, load 15-20 on 12 vCPU; Benjamin: restrict to what the machine has "until RAM is added" (AF:city.toml:223-233). Live now: 12 vCPU, 7 GiB RAM in WSL (`nproc`, `free -g`, 2026-09-28).
- Policy: "V1 concurrency policy — One writer per rig", with 5 canary conditions incl. "integration/merge contention is serialized" (AF:docs/SECURITY.md:10-20); same in AF:AGENTS.md:60, AF:docs/DELIVERY.md:5 ("multiple writers remain TARGET, not PROVEN"), AF:legacy/docs/TARGET_ARCHITECTURE.md:61-63.
- Mayor justification: "a second writer on the same rig shares its checkout" (AF:agents/mayor/prompt.template.md:114-115). This is literally true for product rigs today: `mol-do-work` creates a worktree `do-work/<bead>` **only when the rig checkout is on a protected branch**; otherwise it works in place (AF:formulas/mol-do-work.formula.toml:54, 110-130).
- `docs/ADAPTATION_REGISTER.md` and `legacy/README.md`: no entry about refinery, merge queue or pools (grep, 2026-09-28). No written reason for not importing the gastown pack other than DELIVERY.md:248-262.

Doc inconsistency (FACT): the upstream recipe still shows `[rigs.patches.pool] max = 10` for polecats (gascity docs/guides/gastown-config-recipes.md:57-61) while the reference says `max_active_sessions` "Replaces pool.max". Use `max_active_sessions`.

## 2. GitHub merge queue — FACTS

- Mechanism: a queued PR is tested "when applied to the latest version of the target branch and any pull requests already in the queue"; it gives the benefits of "Require branches to be up to date" without the author re-updating (https://github.com/github/docs/blob/main/data/reusables/pull_requests/merge-queue-overview.md). Temporary branches `gh-readonly-queue/{base}`; settings: build concurrency 1-100, min/max group size, merge method, check timeout, "only merge non-failing PRs" (https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue).
- CI: workflows "must use the `merge_group` event"; otherwise "status checks will not be triggered … The merge will fail" (https://github.com/github/docs/blob/main/data/reusables/actions/merge-group-event-with-required-checks.md).
- Failure: on failed checks "or conflicts with the base branch, the pull request will be removed from the queue" (…/merge-queue-reject.md). No automatic rebase-and-retry.
- Auto-merge: `gh pr merge` on a queue-protected branch adds the PR to the queue, or enables auto-merge if checks are pending; web "Merge when ready" enqueues when requirements pass (https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/merging-a-pull-request-with-a-merge-queue).
- Configured "under branch protection rules or rulesets" (managing page).
- **Availability**: "any public repository owned by an organization, or in private repositories owned by organizations using GitHub Enterprise Cloud" (https://github.com/github/docs/blob/main/data/reusables/gated-features/merge-queue.md).

This repo (read-only `gh api`, 2026-09-28):
- `saymyname-app/agent-factory`: **private**, org-owned, `allow_auto_merge: true`, `allow_update_branch: false`. Org plan not readable with the token (`plan: null`) → merge queue requires GHE Cloud; **likely unavailable** unless the org is on it (UNKNOWN).
- Ruleset `AF-main-protection` (id 23626687): required check `Tests`, `strict_required_status_checks_policy: false`, no merge-queue rule. Consequence: a PR can merge while BEHIND main, so two PRs each green against an older main can combine into a red main (semantic conflict without textual conflict).
- CI triggers only `pull_request` and `push` (AF:.github/workflows/ci.yml:5-10) — no `merge_group`.
- `pr-autopilot` runs every 3 min (AF:orders/pr-autopilot.toml:3-4), arms `gh pr merge --auto --squash --delete-branch` (AF:bin/pr-autopilot:406), and only *flags* DIRTY/BEHIND PRs as stuck (AF:bin/pr-autopilot:201-209); it never rebases.
- Product repos: not visible to this token (404) — UNKNOWN.

## 3. Established practices — FACTS (sourced)

1. **Worktree per agent.** Claude Code: each worktree has its own files and branch, sharing history; `claude --worktree`, subagent `isolation: worktree`. Caveat: a worktree is a fresh checkout — dependencies and gitignored `.env` must be set up (`.worktreeinclude`); worktrees share `.git` (https://code.claude.com/docs/en/worktrees). The Factory's own SECURITY.md adds that a worktree "is not a security boundary" (AF:docs/SECURITY.md:6).
2. **Serialised integration against the moving tip.** Gas Town Refinery merges "one at a time" after rebasing on the new baseline (PACKS refinery prompt L192-L209; glossary: Refinery "Manages the Merge Queue … handling conflicts", https://github.com/gastownhall/gastown/blob/main/docs/glossary.md). GitHub merge queue does the same with CI on the combined result (§2). Uber SubmitQueue guarantees an always-green master at thousands of commits/day using speculation plus a conflict analyzer over changes (EuroSys 2019, https://dl.acm.org/doi/10.1145/3302424.3303970).
3. **Conflict → return to author with branch intact, not blind retry.** Gas Town rejects to the pool with `rejection_reason` and keeps the branch (§1). GitHub removes conflicted PRs from the queue (§2).
4. **Epic integration branches** so dependent children start from sibling work; the Refinery merges children there, then lands the branch (https://github.com/gastownhall/gastown/blob/main/docs/concepts/integration-branches.md). This is the Gas Town analogue of stacked PRs.
5. **Task claiming/leases + partitionable work.** Anthropic's 16-agent C-compiler run: agents lock a task by writing `current_tasks/<task>.txt`; git sync forces a colliding agent to choose another; "Merge conflicts are frequent", agents resolve them; a monolithic task made "every agent … hit the same bug … and overwrite each other's changes", fixed by partitioning work with an oracle; the verifier must be "nearly perfect" (https://www.anthropic.com/engineering/building-c-compiler).
6. **Test isolation.** Required, and currently violated here: SayMyName state commits record order tests leaking real Codex sessions holding the escalation lock (commit 7cec5c1) and worker tests reaching the live city mail (a936ecd). With N workers these leaks become cross-worker interference.
7. **Resource caps.** Gas City caps are hierarchical (agent → rig → workspace) (§1). Host evidence says 7 GiB RAM is the binding constraint for Maven/Testcontainers rigs (AF:city.toml:223-233).

Not verified from a primary source (UNKNOWN, left out of the facts): stacked-PR tooling details, planning-time file-scope conflict prediction as a published agent practice (only SubmitQueue's build-target conflict analyzer is sourced).

## 4. Implications for this Factory — RECOMMENDATION

Frame: collisions are cheap to prevent before dispatch, expensive after. Layer them.

| Layer | When | Mechanism | Built on |
|---|---|---|---|
| L0 Isolation precondition | always | Every dispatch gets its own worktree `do-work/<bead>` from a fresh `origin/<base>`, on every rig, not only when on a protected branch; no worker ever works in the rig checkout | extend `bin/factory-do-work-workspace` (AF:formulas/mol-do-work.formula.toml:110-130) |
| L1 Planning-time overlap avoidance | ticket-graph publish | Each ticket declares `scope.paths` (globs); publish computes pairwise overlap; overlapping tickets get a dependency edge (serialised) or merged | `bin/ticket-graph-publish` |
| L2 Dispatch-time leases | Mayor dispatch | Before slinging, take a lease bead/metadata on the ticket's declared paths + a static hot-file list (lockfiles, migrations `V*__*.sql`, `city.toml`, CI files); a ready ticket whose paths are leased waits. Lease released on merge/close | Beads metadata (like `current_tasks/` in Anthropic's run) |
| L3 Integration on the combined result | merge | Prefer GitHub merge queue if the org plan allows it (needs `merge_group` in ci.yml + ruleset rule). Otherwise cheap equivalent: set ruleset `strict_required_status_checks_policy: true` and let `pr-autopilot` update BEHIND PRs one at a time (`gh pr update-branch`) — a poor-man's queue, zero tokens | ruleset + `bin/pr-autopilot` |
| L4 Conflict-repair loop | DIRTY / red after update | `pr-autopilot` reopens the bead with `rejection_reason` + keeps the branch, routes to a worker that rebases and resubmits (the Gas Town contract, PACKS mol-refinery-patrol L224-L239); bounded retries, then escalate | existing stuck-PR detection (AF:bin/pr-autopilot:201-209) |
| L5 Capacity | always | Raise `max_active_sessions` stepwise per rig (1→2), keep reviewer 1; test isolation fixed first | AF:city.toml:235-251 |

**Smallest first step (RECOMMENDATION):** L3-lite on `agent-factory` only — flip the ruleset to strict ("require up to date") and teach `pr-autopilot` to `update-branch` one BEHIND PR per tick. Zero tokens, reversible (one ruleset toggle), and it makes main safe *before* any parallelism is enabled. Then L0 (worktree always), then raise the HQ worker cap to 2 as the canary SECURITY.md:14-20 requires. L1/L2 once the canary shows real overlaps.

Decisions for Benjamin: ruleset change on the Factory repo (ADMIN tier per his rules); any spend (GHE Cloud for merge queue); raising caps vs RAM.

## Unknowns
- Org plan for `saymyname-app` (merge queue availability); product repos' names/visibility/rulesets (token got 404).
- Whether `bin/factory-do-work-workspace` is safe for concurrent `enter` calls from one rig checkout (not read).
- Load-test af-48sx3 result (cited in DELIVERY.md:5; not found).
- Whether gastown-pack refinery works with gc 1.4.1 + the Factory's formula set without conflicts (not tested; pack not imported).
- Real overlap rate between ready tickets (no data; measure before building L1/L2).
