# Agent Factory — Codex bootstrap

Keep this file small. Load only the context required by the current request.

## Start with the user's intent

Classify the request before touching state:

- **OBSERVE** or **DISCUSS**: read-only. Report product meaning before factory internals.
- **RECORD**: update the relevant Bead or durable documentation within the stated scope.
- **EXECUTE**: deliver through the Mayor and Beads workflow unless the task is explicitly bounded Factory maintenance.
- **ADMIN**: change the host, access, secrets, production, or recovery only with explicit authority.

For “where is <project>?”, read that project's own repository and the live
Beads/GitHub state, then answer with CURRENT, LAST DELIVERED, NEXT, NEEDS
BENJAMIN, and any real risk. Do not dump sessions, issues, Formula steps, or
logs unless asked.

For “what is the Factory doing?”, use `gc status` and the Beads/GitHub state.
Cockpit V1 is retired to `legacy/` (untrusted); Cockpit V2 is Planning Run C01.
ADR-0001..0024 are pre-refactor (`legacy/docs/decisions/`): where their
mechanism still runs it is active but not re-validated — re-decide it through
the Planning Run flow when you touch it.
Do not infer progress from session existence.

For a change:

1. Read the applicable `AGENTS.md` chain, including the nearest file in the target rig.
2. Read the relevant Bead with `gc bd show <id>` when work is tracked.
3. Use `docs/CONTEXT_INDEX.md` to locate the minimum durable contract.
4. Inspect only the affected code/config, then validate with deterministic evidence.

## Codex bridge contract

- Desktop Codex, CLI Codex, and Codex Remote are operator surfaces for the same local Factory.
- New work enters through the Planning Run flow (`bin/planning-run-router`);
  the Mayor executes approved ticket graphs. The pre-refactor product queue is
  retired to `legacy/`.
- A remote/mobile session has the same authority as its request, not broader authority because the host is reachable.
- “Full access” means the tools may be available. It never means blanket permission to mutate, publish, expose, spend, handle secrets, or perform destructive operations.
- Follow `docs/OPERATOR_BRIDGE.md` for the human protocol and access boundaries.

## Adaptive context and durable learning

- Factory-wide rules belong here or in `docs/`; project-specific rules belong in that project's nearest `AGENTS.md` and repository docs.
- Keep transient observations in Beads/evidence, not in `AGENTS.md`.
- Promote a learning into `AGENTS.md` only when it is stable, reusable, and changes how future agents should work.
- When a task exposes stale context, repair the authoritative document in the same bounded change and add a deterministic check when practical.
- Never silently rewrite policy from chat memory. Resolve conflicts using live state, Git, Beads, and the authority order in `docs/CONTEXT_INDEX.md`.
- After instruction changes, use a fresh Codex session to verify the effective instruction chain.

## Invariants

- Distinguish **TARGET / CONFIGURED / OBSERVED / PROVEN**.
- GitHub is authoritative for code, branch, SHA, PR, CI, and merge state.
- Beads is authoritative for executable work and dependencies.
- One active Gas City controller per City.
- HQ Factory work uses `bin/factory-work-dispatch <af-bead-id>`: its fixed
  `factory-worker` inherits `workspace`; never sling `workspace` or `bd.dog`.
- V1 allows one writer per rig until worktree isolation is proven by canary.
- Branch work happens in a `git worktree`, never by checking out in the live
  root (the root is the running city). Remove the worktree when its PR merges
  or closes: one left pinning a merged branch makes `gh pr merge
  --delete-branch` exit non-zero after merging, which reads as a failed merge.
  `factory-guard` names any that are left; it does not remove them for you.
- Do not extend the retired SayMyName Linear/PowerShell runner except for transition or safety work.
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
- **One escalation contract.** Only Benjamin can decide (ADR-0016 effect
  tests): set `gc.needs_benjamin=true` AND mail `human` AND state the cause,
  then keep working on what is eligible. Anything else: mail `mayor` BLOCKED,
  `gc.outcome=fail`, drain. Never create a `human` gate: it notifies nobody.
- **Standing ADMIN allowlist:** the routine upkeep gestures ADR-0016 §7
  exempts from the escalation contract above are run only through
  `bin/factory-maintain <gesture>` — `restart-service`, `prune-merged-branches`,
  `clean-worktrees`, `rotate-logs`, `reload-city-config` — never by hand; each
  gesture checks its own refusal criteria, logs what it did to
  `var/factory-maintain.log`, and is undoable. No other free-text upkeep
  action is in scope; anything else stays ADMIN. Background in
  `legacy/docs/decisions/ADR-0016-standing-delegation-and-non-stop-campaign.md` §7.
- **No direct push to `main` or `dev`:** land through a pull request.

## Cost policy

Use the lowest sufficient level: L0 deterministic tool; L1 cheap/local model for a
proven low-risk class; L2 one strong writer; L3 writer plus independent review for
meaningful risk; L4 multi-agent only when decomposition has measured value. Never
load whole backlogs or histories by default.

Context engineering discipline (write / select / compress / isolate):
quality degrades past roughly half a session's context window, well
before the hard limit — treat that as the compaction/handoff trigger
(see the Mayor's session-budget guidance). Put load-bearing instructions
at the start or end of prompts and docs, not buried mid-document —
models attend to edges more reliably than the middle. Give each agent
role only the tool/skill surface its job needs; an unused tool still
taxes every turn's context.

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
