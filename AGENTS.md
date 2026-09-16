# Agent Factory — Codex bootstrap

Keep this file small. Load only the context required by the current request.

## Start with the user's intent

Classify the request before touching state:

- **OBSERVE** or **DISCUSS**: read-only. Report product meaning before factory internals.
- **RECORD**: update the relevant Bead or durable documentation within the stated scope.
- **EXECUTE**: deliver through the Mayor and Beads workflow unless the task is explicitly bounded Factory maintenance.
- **ADMIN**: change the host, access, secrets, production, or recovery only with explicit authority.

For “where is SayMyName?”, first run `./bin/saymyname-product-status` and answer
with CURRENT, LAST DELIVERED, NEXT, NEEDS BENJAMIN, and any real risk. Do not
dump sessions, issues, Formula steps, or logs unless asked.

For “what is the Factory doing?” or one-glance visibility, use the read-only
`./bin/factory-cockpit snapshot` projection. Open its local UI with
`./bin/factory-cockpit open`. Its monitoring is zero-token; only an explicit
human send may message the PO or Mayor. Do not infer progress from session existence.

For a change:

1. Read the applicable `AGENTS.md` chain, including the nearest file in the target rig.
2. Read the relevant Bead with `gc bd show <id>` when work is tracked.
3. Use `docs/CONTEXT_INDEX.md` to locate the minimum durable contract.
4. Inspect only the affected code/config, then validate with deterministic evidence.

## Codex bridge contract

- Desktop Codex, CLI Codex, and Codex Remote are operator surfaces for the same local Factory.
- `bin/product-queue` is the deferred product-candidate projection over Beads,
  not an executable queue. A PO may manage candidates under RECORD authority;
  only the Mayor materializes the first eligible candidate as separate executable
  work. The Mayor remains the sole product-work orchestrator.
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
- Switch models only via the cockpit or `./bin/provider-failover set --by <you>`
  (ADR-0018), never by editing config.
- Stop/restart only per `docs/RUNBOOK_STOP_AND_RESTART.md`.
- Discoveries outside scope become separate Beads work, not silent scope expansion.

## Cost policy

Use the lowest sufficient level: L0 deterministic tool; L1 cheap/local model for a
proven low-risk class; L2 one strong writer; L3 writer plus independent review for
meaningful risk; L4 multi-agent only when decomposition has measured value. Never
load whole backlogs or histories by default.

Context engineering discipline (write / select / compress / isolate):
measured practice shows agent output quality degrades once a session's
context passes roughly half of its window, well before the hard limit —
treat that as the trigger for compaction/handoff, not the window's actual
ceiling (see the Mayor's session-budget guidance in its prompt template).
Assemble prompts and durable docs so the load-bearing instruction is at the
start or end, not buried mid-document — models attend to context edges more
reliably than the middle. Give each agent role the smallest tool/skill
surface that covers its job; a tool an agent never needs is still a standing
tax on every turn's context.

## Inter-agent mail format

`gc mail` (agent-to-agent and agent-to-human messages) is a notification and
coordination layer, not a second copy of durable state — Beads, Git, and PR
evidence remain authoritative, so a message should point at that evidence
rather than restate it. Prefer a compact **action-state record** over free
narrative for routine coordination mail — research on inter-agent
communication (PACT, 2026) shows this halves input tokens downstream with no
loss of task performance, because the recipient needs the resulting state
and what to do with it, not the story of how the sender got there:

```
ACTION: <what the sender did, one line>
STATE:  <resulting state — SHIPPED / PASS / FAIL / BLOCKED: <reason> / etc.>
EVIDENCE: <bead id(s), commit SHA(s), PR number(s) — references, not restatement>
NEXT:   <what happens next, or "none">
```

- **Reference, don't restate.** Cite a bead ID, commit SHA, or PR number and
  let the recipient pull detail on demand (`gc bd show <id>`) instead of
  re-describing full context they can already reach.
- **No exported reasoning.** Deliberation, dead ends, and internal scratch
  work stay in the sender's own session — mail carries only what the
  recipient needs to decide or act.
- Use the ACTION/STATE/EVIDENCE/NEXT shape above for routine status/verdict
  mail. A genuinely ambiguous escalation that needs human judgment may still
  read as prose — clarity for a human decision outweighs the token saving
  there — but keep it under a couple hundred words; treat more than that as
  a signal to split into a follow-up bead rather than one long message.
- **Keep the mailbox drained.** Archive or mark-read mail once acted on
  (`gc.retention_ttl` purges read mail after 7 days, but an unbounded unread
  backlog still buries the signal that actually needs a response).

This mirrors current multi-agent-systems practice: unrestricted context
sharing and verbose unstructured exchange are the documented drivers of
multi-agent token overhead relative to a single agent doing the same task,
while structured/compact message formats have shown large measured token
reductions with little accuracy loss.
