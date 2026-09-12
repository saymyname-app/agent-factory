# Delivery V1

## Status and authority

GitHub is authoritative for branches, commits, pull requests, checks and merges. Beads is authoritative for executable work, dependencies and gates. Gas City provides dispatch through existing formulas and provider configuration. V1 has one writer per rig; concurrent worktrees and multiple writers remain TARGET, not PROVEN.

The configured writer provider inherits `builtin:codex` and appends `-m gpt-5.6-sol`. M2 observed and proved that effective model on a real writer session. Mechanical decisions such as exit codes, diffs, SHAs, PR state and check conclusions are L0 deterministic work.

## Profiles

| Profile | Selection | Required path | LLM level | Gate |
|---|---|---|---|---|
| FAST | Documentation, formatting, or another small reversible low-risk change | one writer; task-specific deterministic validation; branch and PR; merge only when required deterministic gates pass | L0 plus at most one L2 writer | no independent LLM reviewer by default |
| STANDARD | Normal feature or bug with bounded impact | one strong writer; task tests; GitHub CI/checks defined by the target rig; PR; review only when change risk or repository policy requires it | L2; L3 only when justified | required checks and existing human/repository review policy |
| GUARDED | Production, secrets, irreversible/data/security operations, or substantive product decisions | prepare all reversible work automatically; create a Beads gate only on the dependent path; keep unrelated ready work dispatchable | minimum sufficient L0-L3 | explicit human or supported GitHub/Beads gate at the exact risky transition |

L4 multi-agent execution is not a delivery profile and requires a concrete, measured decomposition benefit. A paid reviewer is never added merely because a PR exists.

## Existing primitives

- `gc sling` routes a bead directly or through an existing formula. `mol-do-work` is the proven minimal one-writer lifecycle; it does not provide worktree isolation.
- Gas City packs/formulas/orders supply workflow compilation, dispatch and maintenance. Do not wrap them in a proprietary runner.
- `bd dep` represents prerequisites. `bd gate create` supports `human`, `timer`, `gh:run`, and `gh:pr`; `bd ready` is blocker-aware.
- `gc github pr` supplies GitHub PR monitoring where configured. GitHub remains authoritative for actual PR/check/merge state.
- Provider inheritance supplies the pinned writer model; profile selection does not silently replace it.

## Selection and completion contract

Choose the lowest-risk sufficient profile when creating the work bead and record the profile as a label (`delivery:fast`, `delivery:standard`, or `delivery:guarded`). The bead description names the repository, allowed scope, required deterministic validations and the merge authority. Risk escalation changes the profile before the risky step; it does not broaden the original authorization.

A delivery is complete only when the bead notes record the effective agent/session and model when an LLM ran, branch, commit SHA, PR URL/number, required checks and their conclusions, merge/final state, and deterministic validation. Closing a Bead never substitutes for GitHub merge evidence.

For GUARDED work, create the gate against only the bead that performs the protected transition:

```bash
gate_id=$(bd gate create --type human --blocks <dependent-bead> \
  --reason "Exact decision or irreversible transition requiring Benjamin" \
  --json | jq -r '.id')
bd ready --explain
```

The gate must state the decision and evidence required. Continue any independent ready beads. Resolve the gate only after the named authority decides; do not encode secrets in its reason or notes.

## Observed and proven baseline

- **PROVEN FAST:** M2 bead `af-v7a` used one Codex/Sol writer, deterministic diff validation, commit `77f206a85ab97352aa2e6f9bd2a4f2e653db6d69`, PR #9 and merge `43614760bce9a855a6aeecbfb38090461a905e70`.
- **OBSERVED GitHub:** this private repository currently has no Actions workflows and PR #9/#16 reported an empty check rollup. Repository rulesets and branch protection are unavailable on the current GitHub plan (API HTTP 403). Therefore checks cannot be claimed as configured here.
- **PROVEN scoped GUARDED gate:** gate `af-q4v` blocked only `af-wisp-2o0m`; independent `af-wisp-r31o` remained visible in `bd ready --include-ephemeral`. After resolution, the guarded bead became ready. All probe artifacts were closed.
- **CONFIGURED STANDARD contract:** target rigs must declare their own deterministic tests and GitHub CI/check requirements before STANDARD delivery is claimed. The Agent Factory repository currently proves PR transport/review, not CI execution.

These classifications are deliberately separate: the three contracts are durable and usable, FAST and gate isolation are proven, while target-repository CI remains to be observed during rig onboarding.

## SayMyName rig contracts

### Backend — `saymyname-backend` / `smb`

- **CONFIGURED:** default branch `dev`; one Codex/Sol writer; GitHub PR is the delivery boundary.
- **OBSERVED:** Java 21, Maven and Spring Boot 3.3.1; `Backend CI` executes `mvn -B -ntp -Pit verify` on pull requests to `dev`/`main`; Flyway and Testcontainers/MySQL are present. The `dev` branch has no GitHub branch protection observable through the API.
- **PROVEN locally:** unit test modules pass with Java 21. The web integration suite reaches Testcontainers but cannot start without a Docker endpoint in the current WSL environment; GitHub CI is authoritative for a STANDARD delivery.
- **FAST:** documentation or bounded test-only maintenance with task-specific deterministic validation. **STANDARD:** ordinary bounded backend changes with `-Pit verify` green in GitHub CI. **GUARDED:** Flyway/schema changes, persistent data changes, production actions, secrets, security-sensitive changes or irreversible transitions.

### Frontend — `saymyname-frontend` / `smf`

- **CONFIGURED:** default branch `dev`; one Codex/Sol writer; GitHub PR is the delivery boundary.
- **OBSERVED:** Node 22/npm; `Frontend CI` runs `npm ci`, non-blocking `npm run lint`, `npm test`, and `npm run build` on pull requests to `dev`/`main`. The `dev` branch has no GitHub branch protection observable through the API.
- **PROVEN:** baseline tests pass (108 unit and 2 component) and the production build passes with CI placeholders. Full lint is currently non-gating and reports 197 errors/31 warnings; a task must still avoid introducing a scoped lint regression.
- **FAST:** documentation, isolated tests or bounded low-risk maintenance. **STANDARD:** ordinary bounded UI bugs/features with tests and build green in GitHub CI. **GUARDED:** production deployment/configuration, secrets, irreversible operations, security-sensitive changes or substantive product decisions.

M5 provides the first **PROVEN STANDARD** path: `smf-0jx` -> workflow `smf-7og` -> session `af-4g6` on `gpt-5.6-sol` -> commit `ba6745cd7193f79811471c8956698c1929303f2c` -> Frontend PR #40 -> successful `Frontend CI` -> merge `aa82099a183c64e0b02af80979dc1e28353edc4c`. The existing Claude review workflow exhausted its own turn limit without comments; M4 does not promote that optional paid reviewer into a gate for this low-risk one-line change.
