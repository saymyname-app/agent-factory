# Agent Factory — agent bootstrap

Read only what the current task needs.

1. Read the relevant Bead with `bd show <id>` once Beads is initialized.
2. Use `docs/CONTEXT_INDEX.md` to locate the minimum durable contract.
3. Inspect only the code/config needed for the task.
4. Validate with deterministic commands and Git/GitHub evidence.

## Invariants

- Distinguish **TARGET / CONFIGURED / OBSERVED / PROVEN**.
- GitHub is authoritative for code, branch, SHA, PR, CI and merge state.
- Beads is authoritative for executable work/dependencies once initialized.
- One active Gas City controller per City.
- V1 allows one writer per rig until worktree isolation is proven by canary.
- Do not add generic features to the legacy SayMyName Linear/PowerShell runner except transition/safety fixes.
- Do not implement a proprietary primitive before checking Gas City, Beads, GitHub, provider/runtime or standards.
- Do not put secrets in Git, Beads, logs or prompts.
- Architecture changes update durable documentation in the same change.
- Discoveries outside scope become separate Beads work, not silent scope expansion.

## Cost policy

Use the lowest sufficient level:

- L0: deterministic script/API, no LLM.
- L1: cheap/local model for proven low-risk classes.
- L2: one strong writer.
- L3: writer + independent review for meaningful risk.
- L4: multi-agent only when decomposition provides measured value.

Do not load whole backlogs or histories by default.
