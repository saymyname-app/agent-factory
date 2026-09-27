# ADR-0001 — Factory foundation decisions

- Status: Accepted
- Date: 2026-09-12
- Origin: Plan directeur V2, now maintained here as durable repository policy.

## Decisions

1. **Gas City + Beads is the chosen orchestration/work substrate.** Do not run an installation benchmark before adoption; reconsider only on a concrete reproducible blocker.
2. **GitHub remains authoritative for code/PR/CI.**
3. **One City has one active controller.** Multi-host execution does not mean active-active control planes.
4. **V1 uses one writer per rig.** Same-rig parallelism requires a successful isolation canary first.
5. **Formula v2 typed gates are not assumed to auto-enforce conditions.** Use proven Beads/GitHub/manual gates until the deployed upstream behavior is verified.
6. **WSL2 is compatibility, not a sandbox.** Use stronger boundaries such as a dedicated VM/container/runtime when the risk requires them.
7. **Cloud migration starts with a simple Linux VM.** Kubernetes is added only for a measured need.
8. **Durability must use a real Beads/Dolt backup/restore mechanism appropriate to the deployed mode.** JSONL alone is not accepted as proof of full historical restore.
9. **City-level Beads coordinates; rig-level Beads executes.** Cross-rig dependencies are explicit.
10. **Versioned Git documentation is authoritative for durable architecture.** The ChatGPT Project and historical DOCX are reasoning/reference layers, not operational state stores.

## Consequences

- The legacy SayMyName Linear/PowerShell orchestrator is being decommissioned, not generalized further.
- Provider authentication/quota portability is validated separately from infrastructure portability.
- New layers, agents, reviewers and formulas require either measurable productivity benefit or concrete risk reduction.
- Changes to these decisions require an ADR update/superseding ADR in the same repository change.
