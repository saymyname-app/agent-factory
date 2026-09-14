# Agent Factory workspace — operator cockpit

This Windows folder is Benjamin's simple entrance for changing and observing the
Factory itself. The canonical Git repository and all runtime state remain in
Ubuntu WSL at `/home/benja/agent-factory`; do not create a second Windows clone.

## Start progressively

1. Classify the request as OBSERVE, DISCUSS, RECORD, EXECUTE, or ADMIN.
2. Run Factory commands through:
   `wsl -d Ubuntu-24.04 -u benja --cd /home/benja/agent-factory <command>`
3. For one-glance human visibility, use `./bin/factory-cockpit open`.
4. For detailed engineering work, read the canonical root `AGENTS.md` and the
   minimum document selected by `docs/CONTEXT_INDEX.md`.

This workspace is only a bridge. Source edits, branches, Beads, tests, commits,
and PRs belong to the WSL repository. Preserve untracked user files and use the
Factory's normal evidence and delivery rules.

## Human behavior

- Lead with product or operational meaning, not Bead IDs, Formula steps, or logs.
- The human cockpit is read-only and deterministic. It shows objectives, phases,
  elapsed time, signal freshness, agents, queue, decisions, and source warnings.
- Never invent a percentage or claim that a process is making progress merely
  because its session exists. Distinguish working, waiting, stale, and idle.
- The cockpit performs zero model calls. Do not add summarization, inference, or
  autonomous actions to its refresh path.
- The Mayor remains the only product-work orchestrator. UI visibility never
  grants the cockpit dispatch, retry, merge, or recovery authority.

## Useful requests

- “Ouvre le cockpit humain de la Factory.”
- “Est-ce que l'usine tourne et sur quel objectif ?”
- “Explique le signal ancien sans rien modifier.”
- “Montre les détails techniques de cette tâche.”
- “Améliore la Factory et livre la modification.”

ADMIN actions such as providers, credentials, network exposure, production,
host services, upgrades, spending, or destructive recovery require explicit
scope. Full host access is capability, not standing authority.
