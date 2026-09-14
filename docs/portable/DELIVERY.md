# Portable delivery contract

The Mayor is the sole dispatcher. The PO prepares outcomes, acceptance and
dependencies; it never launches workers or becomes a second orchestrator.

Before release work, read the project's onboarding and readiness report.
Definition-ready means the scope is sufficiently defined, not that the product
works or that delivery has been authorized.
Require a human-approved campaign mandate naming included outcomes, exclusions,
budget/time bounds, merge/deployment authority, and stop conditions. Record the
source of approval. No checkbox grants this authority.

For every executable outcome, create an upstream Bead with the repository,
scope, dependencies, deterministic validation and merge policy.
Use native Gas City formulas and Beads dependencies/gates. Never infer
completion from a session or closed ticket: require commit, PR, checks and
delivery evidence.

FAST: small reversible changes; one writer and focused deterministic checks.
STANDARD: normal implementation; relevant tests/build and configured PR checks.
GUARDED: substantive product, persistent data, access, production, cost or
irreversible transitions; prepare reversible work and gate the exact transition.
Keep unrelated ready work eligible only with evidence that an unresolved
decision cannot invalidate it.

Require a rig-specific default branch and test/build/CI contract.
Use the lowest sufficient model effort; no automatic paid reviewer or agent
fanout. Provider/model selection belongs to the local installation profile.
Research external facts only when material and unavailable from local evidence;
record RUN/SKIP/UNAVAILABLE and rationale in the work Bead.

Reopen affected definition requirements if implementation exposes contradictions.
Do not interrupt existing deliveries merely because a new onboarding starts.
