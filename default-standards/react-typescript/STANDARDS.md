# Code standards — React and TypeScript

Default Standards version 2. This file becomes the project's own written
standard when copied. Tool-held rules live only in their configuration.

| Family | Guaranteed | Benefit | Cost | Configuration |
| --- | --- | --- | --- | --- |
| Format | Prettier refuses unformatted source | Reviews focus on behaviour | One reformat of existing files | `.prettierrc.json`, `package.json` |
| Bug patterns and names | TypeScript strict mode and typed ESLint refuse unsafe code; type names use PascalCase | Fewer runtime faults, consistent code shape | Type annotations and lint fixes | `tsconfig.json`, `eslint.config.mjs` |
| Architecture | Domain code cannot import UI or app code | Changes stay local | Folder convention | `.dependency-cruiser.cjs` |
| Coverage | 80% of changed source lines are exercised | New work gets test evidence | More tests and CI time | `.github/workflows/code-standards.yml` |
| Security | PR scans refuse newly introduced vulnerable dependencies and discovered secrets | Known risks surface early | Alert triage and CI time | `.github/workflows/code-standards.yml` |
| Frozen List | ESLint suppressions and recorded exceptions can only decrease; probable bugs are never frozen | Existing code can be adopted without growing debt | Record the first counts per rule and file | `eslint-suppressions.json`, `.factory/frozen-list.json`, `.factory/never-frozen.json`, `.github/workflows/code-standards.yml` |

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

A bounded exception is one table row under this heading with columns `Standard | Endroit | Intent | Date | Fin`. Intent contains Benjamin's exact words in French guillemets, Date is `YYYY-MM-DD HH:MM Paris`, and Fin is an expiry date. Record and review that decision in a separate PR first; the ratchet accepts an increase only when the exception is already on the target branch for that rule and path and remains current. A new photo instead uses `.factory/ratchet-snapshot.json` for one rule and names the configuration file changed by the same PR.

After code adoption, run `npm ci` then `.factory/bin/standards-ratchet --initial-photo --target .` once in the project worktree. It records existing ESLint and dependency-cruiser violations without asking Benjamin to sort them. Commit `.factory/baseline-record.json`, `eslint-suppressions.json`, and `.dependency-cruiser-known-violations.json` with the adoption PR. CI refuses an adoption without this initial photo; unsafe typed lint findings remain never frozen and must be corrected.
