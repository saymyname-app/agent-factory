# Agent Factory refactor — grilling checkpoint

**Checkpoint date:** 2026-09-22  
**Status:** shared-understanding interview in progress; target configuration and implementation are not yet approved.  
**Source conversation:** `6ab0ddc5-3870-83eb-8e5d-09275d8d69e5` plus its Codex continuation.  
**Working branch:** `research/autonomy-frontier-2026-09-22`  
**Working tree:** `/home/benja/.local/share/agent-factory-runtime-worktrees/autonomy-frontier-20260922`

This checkpoint exists so a fresh conversation can resume the design tree without reconstructing it from chat memory. It records decisions and hypotheses, not permission to implement the refactor.

## Validated decisions

1. **Optimization order.** Improve confidence and maintainability first; increase autonomy and throughput only inside a verified envelope.
2. **Scope.** Refactor the project-agnostic Software Factory and its contracts with project repositories. Do not refactor SayMyName product code without a demonstrated need.
3. **Migration posture.** Reconstruct the Intent & Design Workflow while the existing Delivery Workflow may continue consuming already-created Beads. A planned interruption of delivery is acceptable later when migration safety or efficiency requires it.
4. **Project agnosticism.** Keep universal safety principles, but adapt autonomy and gates to project state (greenfield/brownfield/maturity) and change class (risk, novelty, oracle quality, reversibility).
5. **Design dossier.** Build the target progressively from observed state, principles, target workflow, gaps, then migration slices.
6. **Architecture presumption.** Retain Gas City, Beads/Dolt and the Mayor unless evidence falsifies their fit. They are not sacred.
7. **Planning entry hypothesis.** Use `grill-with-docs` as the provisional normal entry and promote to Wayfinder when the work exceeds one healthy session. Benjamin remains doubtful; test this against a Wayfinder-first alternative on real simple and complex requests.
8. **Questions and unknowns.** Questions discovered and resolved inside one grilling session need no Bead. Multi-session planning decisions need durable work. Implementation surprises that change intent, scope, approved boundaries or acceptance return the affected slice to planning; local factual or tactical discoveries do not automatically become Decision Beads.
9. **Canonical specification.** Adapt Matt Pocock's `to-spec`; its output is the canonical Spec. Confirmation of Shared Understanding changes that same artifact to Approved Spec. Do not create a separate Release Contract that repeats it.
10. **Work decomposition.** Adapt `to-tickets` to create tracer-bullet/vertical-slice work with explicit dependency edges in Beads. Inspect and apply `setup-matt-pocock-skills` prerequisites where relevant.
11. **Planning belongs inside the Gas City topology.** Keep one Mayor as execution/co-ordination authority, but not as the only planning context. Model independent Planning Runs in Gas City, with on-demand interactive planning sessions and formula-driven specialist agents. Codex, Claude and the Cockpit are operator surfaces/adapters, not a second factory above Gas City.
12. **Human review of the Spec.** Do not require Benjamin to reread a faithful summary by default. Require targeted review only for a semantic delta, contradiction, unresolved choice, lost traceability or a newly introduced test seam.

## Q11 configuration deliberately left open

Validation of the architecture does **not** select the exact Gas City configuration yet. The following remain design and prototype questions:

- which capabilities belong in formulas, agents, named sessions, ad-hoc sessions, orders, skills or deterministic code;
- which providers and models should serve grilling, research, prototyping, synthesis, review and implementation;
- whether interactive Planning Runs use one provider-specific template per provider or another topology;
- concurrency, resource caps, session retention and one-writer ownership for planning artifacts;
- how Codex, Claude and mobile/Cockpit surfaces submit to and resume Gas City sessions;
- how planning methodology artifacts map onto the official `planning-base` contract;
- which Mayor responsibilities remain after removing duplicated PO/Release Contract behavior.

The leading implementation candidate is a unique Mayor authority plus provider-specific planning templates and ad-hoc sessions per topic. Pools are suitable for fungible throughput work, not stable human conversations. This is a candidate to prototype, not a final configuration.

## Baseline adoption strategy to evaluate

Benjamin proposes starting by reproducing Matt Pocock's workflow as faithfully as practical, even though Sandcastle is not implemented on Gas City, then changing it only from observed needs through experiments, prototypes and canaries.

Treat this as a strong candidate strategy with two safeguards:

1. Copy the **method and observable contracts** before copying Sandcastle's implementation topology. Gas City already supplies different orchestration primitives.
2. Preserve an explicit deviation register: each difference from Matt's baseline must name the Gas City constraint, project-agnostic requirement, safety need or experimental evidence that motivates it.

This strategy still needs an explicit grilling decision before it becomes the migration plan.

## Durable terminology

Use `CONTEXT.md` as the canonical glossary. In particular:

- **Software Factory** is the entire socio-technical system.
- **Gas City** is the orchestration platform/runtime used by the Factory.
- **City** is one configured Gas City workspace.
- **Mayor** is the unique orchestration authority, not the whole Factory and not necessarily the only human-facing agent.
- **Planning Run** is a bounded, independently resumable instance of the Intent & Design Workflow. This term is provisional until added to the glossary through the ongoing domain-modeling process.
- **Cockpit** is an operator interface; it must not become a second orchestrator.

## Resume protocol for a fresh conversation

1. Work from the branch and worktree named above; do not restart from `main`.
2. Read this checkpoint, `/CONTEXT.md`, and `docs/research/2026-09-22-agentic-factory-autonomy-frontier.md` before asking questions.
3. Inspect upstream or the local Factory for facts; ask Benjamin only for decisions.
4. Treat validated decisions as settled unless new evidence exposes a contradiction.
5. Recompute the remaining design-tree frontier and continue `grill-with-docs` in rounds.
6. Do not implement the refactor until the frontier is empty and Benjamin confirms Shared Understanding.
7. When planning is complete, use the adapted `to-spec`, obtain targeted confirmation if needed, then adapt `to-tickets` to materialize migration slices.

## Remaining lifecycle after grilling

The intended sequence is:

1. finish the design-tree interview;
2. synthesize the Approved Spec;
3. decompose it into small migration experiments and vertical slices;
4. prototype uncertain Gas City session/provider/formula behavior before committing architecture;
5. run canaries against non-critical Factory work;
6. compare results with the current baseline using explicit quality, rework and operability measures;
7. expand successful classes gradually and repair the harness from observed failures;
8. repeat the plan → prototype/canary → measure → adapt cycle.

No chat transcript is the authoritative runtime state. Gas City, Beads/Dolt, Git, GitHub and versioned Factory documentation remain authoritative in their respective domains.
