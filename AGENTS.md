# Agent Factory — agent bootstrap

Keep this file small. Load only the context required by the current request.

## Start with the user's intent

Classify the request before touching state:

- **OBSERVE** or **DISCUSS**: read-only. Report product meaning before factory internals.
- **RECORD**: update the relevant Bead or durable documentation within the stated scope.
- **EXECUTE**: deliver via the Mayor and Beads workflow unless explicitly bounded Factory maintenance or Direct Delivery.
- **ADMIN**: change the host, access, secrets, production, or recovery only with explicit authority.

For “where is <project>?”, read that project's own repository and the live
Beads/GitHub state, then answer with CURRENT, LAST DELIVERED, NEXT, NEEDS
BENJAMIN, and any real risk. Do not dump sessions, issues, Formula steps, or
logs unless asked.

For “what is the Factory doing?”, use `gc status` and the Beads/GitHub state.
Cockpit V1 is retired (code in Git history); Cockpit V2 is Planning Run C01.
ADR-0001..0024 are pre-refactor (`docs/decisions/PRE_REFACTOR.md`): where their
mechanism still runs it is active but not re-validated — re-decide it through
the Planning Run flow when you touch it.
Do not infer progress from session existence.

For a change:

1. Read the applicable `AGENTS.md` chain, including the nearest file in the target rig.
2. Read the relevant Bead with `gc bd show <id>` when work is tracked.
3. Use `docs/CONTEXT_INDEX.md` to locate the minimum durable contract.
4. Inspect only the affected code/config, then validate with deterministic evidence.

## Codex bridge contract

- Desktop Codex, CLI Codex, and Codex Remote are operator surfaces for the same Factory.
- New work enters through the Planning Run flow (`docs/PLANNING_RUN.md`);
  the Mayor executes approved ticket graphs. The pre-refactor product queue is
  retired (Git history).
- A remote/mobile session has the same authority as its request, not broader authority because the host is reachable.
- “Full access” means the tools may be available. It never means blanket permission to mutate, publish, expose, spend, handle secrets, or perform destructive operations.
- Follow `docs/OPERATOR_BRIDGE.md` for the human protocol and access boundaries.

## Adaptive context and durable learning

- Factory-wide rules belong here or in `docs/`; project-specific rules belong in that project's nearest `AGENTS.md` and repository docs.
- Keep transient observations in Beads/evidence, not in `AGENTS.md`.
- Promote a learning into `AGENTS.md` only when it is stable, reusable, and changes how future agents should work.
- When a task exposes stale context, repair the authoritative document in the same bounded change and add a deterministic check when practical.
- Never silently rewrite policy from chat memory. Resolve conflicts using live state, Git, Beads, and the authority order in `docs/CONTEXT_INDEX.md`.
- After instruction changes, use a fresh session to verify the effective instruction chain.

## Invariants

- Distinguish **TARGET / CONFIGURED / OBSERVED / PROVEN**.
- GitHub is authoritative for code, branch, SHA, PR, CI, and merge state.
- Beads is authoritative for executable work and dependencies.
- One active Gas City controller per City.
- HQ Factory work uses `bin/factory-work-dispatch <af-bead-id>`: its fixed
  `factory-worker` inherits `workspace`; never sling `workspace` or `bd.dog`.
- V1 caps writers per rig instead of fixing one: `agent-factory` allows 2,
  each isolated in its own worktree with declared-scope/hot-file
  serialization ahead of dispatch; other rigs stay at 1 until proven by canary.
- Branch work happens in a `git worktree`, never by checking out in the live
  root (the root is the running city). Remove the worktree when its PR merges
  or closes: one left pinning a merged branch makes `gh pr merge
  --delete-branch` exit non-zero after merging, which reads as a failed merge.
  `factory-guard` names any that are left; it does not remove them for you.
- Check Gas City, Beads, GitHub, the provider/runtime, and standards before inventing a proprietary primitive.
- Never put secrets in Git, Beads, logs, prompts, or responses.
- Architecture changes update durable documentation in the same change.
- **Every factory improvement is verified, adds autonomy, optimises something,
  and is documented for agents and humans** (ADR-0017), or it is unfinished.
- Switch models only via `./bin/provider-failover set --by <you>` (ADR-0018),
  never by editing config.
- Stop/restart only per `docs/RUNBOOK_STOP_AND_RESTART.md`.
- Discoveries outside scope become separate Beads work, not silent scope expansion.
- **Close a formula step with its outcome:** `gc bd update <step-id>
  --set-metadata gc.outcome=pass --status=closed --notes "..."` (`fail` if it
  failed). `gc bd close --reason` leaves no `gc.outcome`: the dispatcher reads
  `missing_outcome`, retries, hard-fails and skips the rest (af-ptx7).
- **One escalation contract.** For a decision only Benjamin can make
  (ADR-0016 effect tests), use `bin/escalation-door` with the cause; its
  human route owns state and notification. Other blockers use
  `bin/escalation-door mayor`. Never set `gc.needs_benjamin` manually or
  create an unnotified `human` gate.
  Keep working on eligible items; failed formula steps retain `gc.outcome=fail`.
- **Standing ADMIN allowlist:** the routine upkeep gestures ADR-0016 §7
  exempts from the escalation contract run only through `bin/factory-maintain
  <gesture>` — `restart-service`, `prune-merged-branches`, `clean-worktrees`,
  `rotate-logs`, `reload-city-config` — never by hand; each logs to
  `var/factory-maintain.log` and is undoable. Anything else stays ADMIN
  (`docs/decisions/ADR-0016-standing-delegation-and-non-stop-campaign.md` §7).
- **No direct push to `main` or `dev`:** land through a pull request.

## Cost policy

Use the lowest sufficient level: L0 deterministic tool; L1 cheap/local model for a
proven low-risk class; L2 one strong writer; L3 writer plus independent review for
meaningful risk; L4 multi-agent only when decomposition has measured value. Never
load whole backlogs or histories by default.

Context discipline: select the relevant contract, save durable outcomes and
isolate unrelated work. Follow the Mayor session-budget compaction/handoff
threshold as an operating heuristic, not a universal model-quality law.
Give each role only the tools/skills its job needs. Keep routing entries
short; procedures and exceptions belong in their target contracts.

## Inter-agent mail format

`gc mail` is notification, not durable state: Beads, Git, and PR evidence
remain authoritative. Routine coordination uses compact action-state records:

```
ACTION: <what the sender did, one line>
STATE:  <resulting state — SHIPPED / PASS / FAIL / BLOCKED: <reason> / etc.>
EVIDENCE: <bead id(s), commit SHA(s), PR number(s) — references, not restatement>
NEXT:   <what happens next, or "none">
```

- **Reference, don't restate.** Cite a bead ID, commit SHA, or PR number;
  let the recipient pull detail on demand (`gc bd show <id>`).
- **No exported reasoning.** Deliberation and dead ends stay in the
  sender's own session — mail carries only what the recipient needs to
  decide or act.
- Use the ACTION/STATE/EVIDENCE/NEXT shape above for routine status/verdict
  mail. A genuinely ambiguous escalation that needs human judgment may still
  read as prose — clarity for a human decision outweighs the token saving
  there — but keep it under a couple hundred words; treat more than that as
  a signal to split into a follow-up bead rather than one long message.
- **Read is not done.** A mail whose NEXT names you is a task: execute it this
  turn, reply ACTION/STATE/EVIDENCE/NEXT, then mark it read.
- **Keep the mailbox drained.** Archive or mark-read mail once acted on
  (`gc.retention_ttl` purges read mail after 7 days, but an unbounded unread
  backlog still buries the signal that actually needs a response).

## Agent skills

Matt Pocock skills: tracker = Beads, see `docs/agents/issue-tracker.md`;
domain docs, see `docs/agents/domain.md`.
