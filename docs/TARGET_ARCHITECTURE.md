# Target architecture

## Status legend

- **TARGET**: intended end state, not yet demonstrated.
- **CONFIGURED**: configuration exists.
- **OBSERVED**: seen in the live system.
- **PROVEN**: validated by reproducible evidence/canary.

## Control and execution

**TARGET**

```text
Benjamin / PO
  -> City-level Beads: goals, priorities, cross-rig capabilities
  -> Gas City: formulas, orders, events, supervisor
      -> rig: project A backend -> rig Beads -> writer/provider -> GitHub
      -> rig: project A frontend -> rig Beads -> writer/provider -> GitHub
      -> rig: project B          -> rig Beads -> writer/provider -> GitHub
```

A City has one active controller. Execution may later move to remote runtimes or Kubernetes, but this does not create a second active control plane.

## Authority by information type

| Information | Authority |
|---|---|
| Approved outcome / priority | City Beads; durable ADR/docs when structural |
| Executable task / dependency | Rig Beads |
| Historical product/backlog reference | Linear, read-only during retirement; never an execution trigger |
| Session/runtime state | Gas City |
| Code, branch, SHA, PR, CI, merge | Git/GitHub |
| Architecture/contracts | versioned docs + ADRs |
| Secrets/provider auth | host/provider secret store |
| Conversation | temporary reasoning only |

## Work topology

- City store: portfolio goals, multi-project coordination and cross-rig capabilities.
- Rig store: tasks that directly modify one repository.
- Cross-repo dependencies must be explicit; never infer them from chat or naming.
- Decompose just in time. Do not mirror an entire legacy backlog.
- Since the M6 cutover at `2026-09-12T16:38:00Z`, every new executable
  SayMyName task is created JIT in `smb` or `smf`. Linear history may inform a
  decision, but a Linear status or label cannot dispatch execution.

## Providers

The architecture is provider-neutral. Initial expected roles:

- writer: Codex CLI when available and authenticated;
- independent reviewer: Claude Code only where risk justifies it;
- cheap/local: Ollama through a compatible harness only for task classes with demonstrated quality;
- future/fallback: ACP/OpenCode/Gemini/other supported runtimes.

Gas City orchestration does not imply provider subscription, authentication or quota portability.

## Concurrency

V1 policy: one writer per rig.

Multiple writers in the same rig remain **TARGET, not PROVEN**, until a canary demonstrates isolated work directories/worktrees, deterministic branches, non-force pushes, serialized integration and scope enforcement.

## Delivery routes

Later M4 introduces only three initial routes:

- `FAST`: low risk, deterministic validation, no independent LLM review by default.
- `STANDARD`: normal feature/bug, one strong writer + tests/CI.
- `GUARDED`: significant contract/security/data risk, strong writer + CI + independent review/gate.

No additional route is added without measured need.

M4 is now proven at the factory-contract level. `DELIVERY.md` is authoritative for profile selection, evidence and gates. FAST delivery and scoped GUARDED gate isolation are proven; STANDARD CI remains target-rig-specific and must be observed during onboarding before it is claimed for a rig.
