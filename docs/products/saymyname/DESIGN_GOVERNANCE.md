# SayMyName design governance

## Default: code-first, system-first

The product repositories are the implementation truth. Maintain a small set of
versioned design tokens, reusable components, interaction/state rules, responsive
breakpoints and accessibility constraints. New work reuses these primitives and
includes realistic loading, empty, error, permission and recovery states.

Figma is optional, not the default state store. Use it for a genuinely ambiguous
new journey, brand exploration, or a high-impact interaction that Benjamin and
the PO need to compare before implementation. If a stable shared component
library later exists, Figma Variables and Code Connect/MCP may mirror code tokens
and components; they must not create a second conflicting design system.

## Design loop

1. PO defines the user, job, outcome, constraints and acceptance evidence.
2. A bounded UX role inventories existing patterns and produces the smallest
   inspectable flow: annotated states in code by default, Figma only when useful.
3. Approval tier is applied before the Mayor receives the outcome.
4. Mayor owns delivery; implementation uses the approved system and states.
5. Automated checks cover types, tests, accessibility rules, responsive layout
   and visual regressions where stable. A human checks only the risky difference.

## Approval tiers

- **Automatic** — existing component/pattern, copy or spacing adjustment, no new
  personal-data exposure, permissions or irreversible action; all deterministic
  tests and visual baselines pass.
- **PO** — new composition of known patterns or a reversible journey variation;
  the PO validates user outcome and states before delivery.
- **Benjamin + PO** — new navigation model, brand language, collection or
  exposure of personal data, purchase, invitation/consent, destructive action,
  or a materially new customer journey.

## Definition of design-ready

The work names the target user and success moment, entry and exit, all essential
states, content hierarchy, mobile behavior, keyboard/focus behavior, reused or
new components, analytics evidence and approval tier. “Make it beautiful” is not
a sufficient design contract.
