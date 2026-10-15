# Code standards — Java, Maven, Spring

Default Standards version 2. This file is copied into a project's repository
and becomes that project's own written standard. Tool-held rules live in their
configuration, not here.

| Family | Guaranteed | Benefit | Cost | Configuration |
| --- | --- | --- | --- | --- |
| Format | Google Java Format rejects unformatted Java at `mvn verify` | Reviews focus on behaviour | One reformat of existing files | `pom.xml` |
| Bug patterns and nulls | Error Prone rejects bug patterns; NullAway rejects null errors throughout the new rig's root Java package | Fewer production failures | Longer compilation and explicit nullable annotations | `pom.xml`, `.mvn/jvm.config` |
| Names | Checkstyle rejects invalid package, type, member, method and local variable names | Consistent code shape | Some renames | `pom.xml`, `checkstyle.xml` |
| Architecture | Persistence cannot depend on web classes | Changes stay local | An architecture test | `src/test/java` |
| Coverage | 80% of changed Java lines are exercised | New work gets test evidence | More tests and CI time | `.github/workflows/code-standards.yml` |
| Security | PR scans refuse newly introduced vulnerable dependencies and discovered secrets | Known risks surface early | Alert triage and CI time | `.github/workflows/code-standards.yml` |
| Frozen List | Existing architecture violations can only decrease; probable bugs are never frozen | Old code can be adopted without growing debt | Record the initial count per rule and file | `.factory/frozen-list.json`, `.factory/never-frozen.json`, `.github/workflows/code-standards.yml` |

## Rules cited by the reviewer

- A public API name describes its behaviour rather than its implementation.
- An authorization decision is made at the boundary that owns the protected resource.
- A query that loads a collection has an explicit plan for its size and number of database round trips.

## Choices

- Formatting style: Google Java Style (technical default).
- Null safety scope: the new rig's Java root package; for an existing rig, integrate only newly added packages (technical default).
- Architecture package convention: `persistence` cannot depend on `web` (technical default).

## Derogations

None.

A bounded exception is one table row under this heading with columns `Standard | Endroit | Intent | Date | Fin`. Intent contains Benjamin's exact words in French guillemets, Date is `YYYY-MM-DD HH:MM Paris`, and Fin is an expiry date. Record and review that decision in a separate PR first; the ratchet accepts an increase only when the exception is already on the target branch for that rule and path and remains current. A new photo instead uses `.factory/ratchet-snapshot.json` for one rule and names the configuration file changed by the same PR.

After code adoption, run `.factory/bin/standards-ratchet --initial-photo --target .` once in the project worktree. It records the current ArchUnit violations without asking Benjamin to sort them. Commit `.factory/baseline-record.json` and `.factory/archunit-freeze/` with the adoption PR. CI refuses an adoption without this initial photo. Error Prone and NullAway findings remain never frozen and must be corrected.
