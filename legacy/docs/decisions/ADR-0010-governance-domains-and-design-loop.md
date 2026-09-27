# ADR-0010: Governance domains and reusable design loop

## Status

Accepted — 2026-09-14

## Decision

The cockpit separates three decision domains. Enterprise owns customer, tester,
channel, buyer, pricing and company objectives. Product owns user value, behavior,
scope and data lifecycle. Project owns view architecture, design workflow and
safe delivery choices. Each open decision has exactly one primary domain.

Add a deterministic enterprise-objective projection, a reviewed view catalogue
and a live delivery-flow graph. These read versioned configuration plus existing
Factory signals and make zero model calls during refresh.

Adopt code-first design governance with an explicit bounded UX role before Mayor
delivery. Reuse existing components and automated accessibility/responsive/visual
checks by default. Use Figma only for ambiguous or high-impact exploration, and
only mirror a mature code design system through Variables/Code Connect or MCP.

## Consequences

- Benjamin can distinguish market decisions from product and delivery choices.
- The PO owns the design-ready outcome; the Mayor remains the sole executor.
- Low-risk known-pattern UI changes may pass automatically when deterministic
  checks are green. Novel, privacy-sensitive, commercial or navigation changes
  require PO or Benjamin + PO validation according to the documented tier.
- View inventory and graphs remain cheap projections, not parallel truth stores.
