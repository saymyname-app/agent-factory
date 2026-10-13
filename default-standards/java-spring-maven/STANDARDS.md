# Code standards — Java, Maven, Spring

Default Standards version 1. This file is copied into a project's repository
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
