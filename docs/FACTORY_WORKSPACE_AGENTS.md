# Agent Factory workspace — operator cockpit

This Windows folder is Benjamin's simple entrance for changing and observing the
Factory itself. The canonical Git repository and all runtime state remain in
Ubuntu WSL at `/home/benja/agent-factory`; do not create a second Windows clone.

## Start progressively

1. Classify the request as OBSERVE, DISCUSS, RECORD, EXECUTE, or ADMIN.
2. Run Factory commands through:
   `wsl -d Ubuntu-24.04 -u benja --cd /home/benja/agent-factory <command>`
3. For one-glance human visibility, use `./bin/factory-cockpit open`; use
   `./bin/factory-cockpit phone-enable` once for private tailnet phone access.
4. For detailed engineering work, read the canonical root `AGENTS.md` and the
   minimum document selected by `docs/CONTEXT_INDEX.md`.

This workspace is only a bridge. Source edits, branches, Beads, tests, commits,
and PRs belong to the WSL repository. Preserve untracked user files and use the
Factory's normal evidence and delivery rules.

## Human behavior

- Lead with product or operational meaning, not Bead IDs, Formula steps, or logs.
- The human cockpit's monitoring path is read-only and deterministic. It shows
  objectives, phases, product Beads, signal freshness, agents, queue, explainable
  decision aids, integrated help, and source warnings.
- Never invent a percentage or claim that a process is making progress merely
  because its session exists. Distinguish working, waiting, stale, and idle.
- The cockpit refresh performs zero model calls. Do not add model summarization,
  inference, or autonomous actions to that path. Only Benjamin explicitly
  pressing send may submit a bounded message to the Mayor or persistent PO, and
  the UI must state that this can consume tokens. The PO defaults to DISCUSS;
  RECORD persists only the approved product decision.
- The Mayor remains the only product-work orchestrator. UI visibility never
  grants the cockpit interrupt, dispatch, retry, merge, or recovery authority.
- The reusable product adapter is `config/products/<slug>.json`, validated
  against `config/product-cockpit.schema.json`. It selects durable context,
  workspace, status/queue commands, and the conceptual project graph without
  forking the cockpit implementation.
- Keep its product-memory projection sourced from the versioned SayMyName
  `PRODUCT_STRATEGY.md` and `DECISIONS.md`. Do not scrape chat databases or make
  conversation history a source of truth.
- Preserve the Enterprise/Product/Project decision split. Design work follows
  `DESIGN_GOVERNANCE.md`: code-first and automatic for proven low-risk patterns,
  PO review for new compositions, Benjamin + PO for novel or sensitive journeys.
- Token observability must identify provider, scope and confidence. Load detailed
  counters and session activity only on demand, redact credentials, and never
  present hidden reasoning or an inferred monetary cost as fact.

## Useful requests

- “Ouvre le cockpit humain de la Factory.”
- “Est-ce que l'usine tourne et sur quel objectif ?”
- “Explique le signal ancien sans rien modifier.”
- “Prépare cette question pour le Mayor sans l'envoyer.”
- “Discute cette décision avec mon PO sans rien enregistrer.”
- “Acte ma réponse à cette décision.”
- “Montre les détails techniques de cette tâche.”
- “Améliore la Factory et livre la modification.”

ADMIN actions such as providers, credentials, network exposure, production,
host services, upgrades, spending, or destructive recovery require explicit
scope. Full host access is capability, not standing authority.
