# ADR-0006: Token-free human Factory cockpit

- Status: Accepted
- Date: 2026-09-14

## Context

The upstream Gas City dashboard is the correct detailed operational interface,
but its sessions, runs, Beads, and events do not answer Benjamin's one-glance
question: “what human outcome is the Mayor or each agent pursuing, and is it
working or waiting?”. This is now a demonstrated gap in the native bridge.

## Decision

Add a small read-only Python/browser cockpit owned by this Factory. It projects
existing Gas City, Beads, workflow, and product-queue state into human objectives,
semantic phases, measured elapsed time, signal freshness, completed workflow
steps, future candidates, decisions, and source-health warnings.

The cockpit uses only Python's standard library and deterministic local commands.
It never invokes a model, creates or updates work, dispatches an agent, or infers
a fictional completion percentage. It listens on loopback only. Technical
infrastructure stays collapsed by default but remains inspectable.

## Consequences

- `bin/factory-cockpit open` provides the simple local view; the upstream Gas City
  dashboard remains the detailed engineering view.
- A small separate loopback process is now accepted for the human projection,
  superseding only the “no factory-owned UI” statement in `OPERATIONS.md`.
- Missing or conflicting sources degrade visibly instead of producing a clean but
  invented story.
- Mobile/tailnet publication is not included. It requires a separate authenticated
  routing decision; the cockpit must never bind to a LAN or public interface.
- The view is not a control plane. Mayor and Beads ownership remain unchanged.
