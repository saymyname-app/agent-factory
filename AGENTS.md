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

For a change:

1. Read the applicable `AGENTS.md` chain, including the nearest file in the target rig.
2. Read the relevant Bead with `gc bd show <id>` when work is tracked.
3. Use `docs/CONTEXT_INDEX.md` to locate the minimum durable contract.
4. Inspect only the affected code/config, then validate with deterministic evidence.

## Codex bridge contract

- Desktop Codex, CLI Codex, and Codex Remote are operator surfaces for the same local Factory.
- The Mayor remains the sole product-work orchestrator; do not create an independent competing queue.
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
- Do not extend the retired SayMyName Linear/PowerShell runner except for transition or safety work.
- Check Gas City, Beads, GitHub, the provider/runtime, and standards before inventing a proprietary primitive.
- Never put secrets in Git, Beads, logs, prompts, or responses.
- Architecture changes update durable documentation in the same change.
- Discoveries outside scope become separate Beads work, not silent scope expansion.

## Cost policy

Use the lowest sufficient level: L0 deterministic tool; L1 cheap/local model for a
proven low-risk class; L2 one strong writer; L3 writer plus independent review for
meaningful risk; L4 multi-agent only when decomposition has measured value. Never
load whole backlogs or histories by default.
