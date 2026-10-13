# Code standards — React and TypeScript

Default Standards version 1. This file becomes the project's own written
standard when copied. Tool-held rules live only in their configuration.

| Family | Guaranteed | Benefit | Cost | Configuration |
| --- | --- | --- | --- | --- |
| Format | Prettier refuses unformatted source | Reviews focus on behaviour | One reformat of existing files | `.prettierrc.json`, `package.json` |
| Bug patterns and names | TypeScript strict mode and typed ESLint refuse unsafe code; type names use PascalCase | Fewer runtime faults, consistent code shape | Type annotations and lint fixes | `tsconfig.json`, `eslint.config.mjs` |
| Architecture | Domain code cannot import UI or app code | Changes stay local | Folder convention | `.dependency-cruiser.cjs` |
| Coverage | 80% of changed source lines are exercised | New work gets test evidence | More tests and CI time | `.github/workflows/code-standards.yml` |
| Security | PR scans refuse newly introduced vulnerable dependencies and discovered secrets | Known risks surface early | Alert triage and CI time | `.github/workflows/code-standards.yml` |

## Rules cited by the reviewer

- A public API name describes its behaviour rather than its implementation.
- An authorization decision is made at the boundary that owns the protected resource.
- A data request has an explicit plan for its expected size and frequency.

## Choices

- Formatting style: Prettier (technical default).
- Typed lint: recommendedTypeChecked; existing violations can be captured per file and rule in `eslint-suppressions.json`, and the normal lint command refuses new or stale suppressions (technical default).
- Folder rule: `src/domain` cannot import `src/ui` or `src/app` (technical default).

## Derogations

None.
