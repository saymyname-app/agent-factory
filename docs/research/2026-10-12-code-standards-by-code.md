# Code standards held by code: what tools verify, what stays judgement (Java, TypeScript)

Research note, 2026-10-12. Marks: **[V]** verified from the cited source today; **[I]** inferred or from general knowledge, not confirmed in a source; **not found** where no source was located. CI costs are orders of magnitude for a six-module Maven backend and a mid-size React app; all are **[I]** unless marked.

## Summary

| Standard family | Check by code | Tool Java | Tool TypeScript | Stays reviewer judgement | CI cost | Adoption on existing code |
|---|---|---|---|---|---|---|
| Formatting | Yes, fully | Spotless + google-java-format or palantir-java-format | Prettier or Biome | Nothing | seconds | Spotless `ratchetFrom` (changed files only), or one reformat commit listed in a blame-ignore file |
| Bug patterns | Mostly | Error Prone (+ NullAway); SpotBugs optional | typescript-eslint type-checked sets; `tsc --strict` | Whether the logic is right | +10 to 30 % compile; lint tens of seconds | Error Prone: per-check severity; ESLint: `eslint-suppressions.json` |
| Layering, dependencies | Yes | ArchUnit, Spring Modulith, Maven Enforcer | dependency-cruiser or eslint-plugin-boundaries | Whether a boundary is the right one; module depth | seconds to 1 min | `FreezingArchRule`; dependency-cruiser `--baseline-mode shrink-only` |
| Naming | Shape only | Checkstyle `google_checks.xml`, ArchUnit suffix rules | `@typescript-eslint/naming-convention` | Whether the name tells the truth | seconds | same baselines as above |
| Tests | Quantity, partly quality | JaCoCo `check`, diff-cover, PIT | Vitest/Jest thresholds, diff-cover (lcov), Stryker | Whether assertions test behaviour | coverage ~free; mutation minutes to hours | diff-coverage on changed lines only |
| Security | Known patterns | Dependabot, CodeQL, Semgrep, secret scanning | same | Authorization logic, data exposure | 2 to 15 min, parallel job | diff-aware scans; alerts triaged once |
| Performance | Narrow | Hibernate statistics assertions in integration tests | bundle size budget | Algorithmic and query design | seconds | new tests only |
| Design smells | Weakly | PMD/Sonar complexity metrics | ESLint `complexity`, `max-lines` | Fowler smells, duplication of intent | seconds | threshold on new code |

## 1. Formatters

- Spotless supports google-java-format (styles GOOGLE, AOSP) and palantir-java-format (PALANTIR, AOSP, GOOGLE) **[V]** (Spotless Maven README).
- `ratchetFrom origin/main` applies Spotless "only to files which have changed since" that ref **[V]**. Trap: shallow CI clones fail with `No such reference`; fetch the branch first **[V]**.
- Alternative: one whole-repo reformat commit, its hash listed in a file read by `git blame --ignore-revs-file` / `blame.ignoreRevsFile` **[V]** (git-blame docs). GitHub's blame view honouring `.git-blame-ignore-revs`: **[I]**.
- Trade-off **[I]**: ratchet keeps history quiet but leaves two styles in the repo and makes every first touch of an old file a noisy diff for the agent reviewer; one commit is noisy once, then never. With agents as the only writers, the single commit is cheaper.
- google vs palantir **[I]**: Google is the more widely recognised; Palantir uses 120 columns and reads better with lambdas and chained calls. No behavioural consequence.
- Prettier vs Biome **[I]**: Biome is one binary for format and lint and much faster; Prettier is the default most tools assume. Biome linter: 568 rules; project-level rules (`noFloatingPromises`, `noImportCycles`) need an opt-in scanner, about 2 s for 2k files **[V]** (Biome docs).

## 2. Static analysis

| Tool | Catches | Noise reputation |
|---|---|---|
| Error Prone | Bug patterns at compile time | Policy: ERROR checks, "essentially no cases" of intended code; WARNING, real issue at least 90 % of the time **[V]** |
| NullAway | Null dereferences via `@Nullable`; Error Prone plugin, JDK 17+ | Overhead "usually less than 10%"; scoped by `AnnotatedPackages` or `OnlyNullMarked` **[V]**; needs annotation work on old code **[I]** |
| SpotBugs (+ find-sec-bugs) | Bytecode bug patterns, some security | Overlaps Error Prone; noisier at low confidence **[I]**; filter files by class, pattern, rank, confidence **[V]** |
| PMD | Smells, complexity, unused code | Noisy unless the ruleset is hand-picked **[I]**; no built-in baseline file **[V]** |
| Checkstyle | Style and naming shape | Redundant with a formatter except naming and Javadoc **[I]** |
| SonarQube | Aggregates all of the above, "new code" gate | Community Build without PR analysis: **not verified** (pages fetched did not state it) |
| typescript-eslint | `recommended`, `strict`, `stylistic`, each with a `-type-checked` variant **[V]** | `strict` is not semver-stable; upstream advises it only for teams proficient in TypeScript **[V]**; typed linting costs a TypeScript build, "negligible" on small projects **[V]** |

Overlap **[I]**: Error Prone + NullAway cover what matters most from SpotBugs/PMD for new code; adding all four multiplies triage without a matching gain. Google's own account (Sadowski et al., CACM 2018) is that analysis succeeds when it runs in the compiler and reviewers' workflow with under 10 % effective false positives: **[I]**, page returned 403 today.

## 3. Architecture rules as tests

- ArchUnit: `layeredArchitecture()` with per-layer access rules; `slices()...beFreeOfCycles()`; naming via `haveSimpleNameEndingWith` **[V]**. This encodes "controllers -> services -> repositories" and "entities never appear in controller signatures" **[I]** on the exact rule.
- `FreezingArchRule` records existing violations in a store; "only new violations will be reported"; fixed ones are removed automatically; line-number shifts are ignored by default **[V]**. This is a shrinking baseline by construction.
- Spring Modulith `verify()`: no cycles between modules, no access to module-internal packages, optional explicit allowed dependencies; optional jMolecules rules (hexagonal, DDD) **[V]**. Fits a package-by-feature layout better than six technical Maven modules **[I]**.
- Maven modules already enforce direction at compile time (a module cannot import one it does not depend on) **[I]**; Enforcer adds `bannedDependencies`, `dependencyConvergence`, `requireUpperBoundDeps`, `banDynamicVersions` **[V]**.
- TypeScript: dependency-cruiser (forbidden-dependency rules, cycles, orphans) with a known-violations file and `--baseline-mode shrink-only` **[V]**; eslint-plugin-boundaries (element types by folder pattern, allow/disallow policies) **[V]**; Nx `enforce-module-boundaries` works on tagged Nx projects **[V]**, so it presumes an Nx workspace **[I]**. `import/no-restricted-paths`: not fetched.

## 4. Naming

Checkstyle ships `google_checks.xml`; it covers package, type, method, field, parameter, local and type-variable names, but cannot check "noun-based" wording or tell a constant from a `static final` field **[V]**. So tools verify shape (case, suffix, placement: `*Controller` in the web package); meaning stays with the reviewer.

## 5. Coverage and mutation

- `jacoco:check` fails the build on rules per BUNDLE/PACKAGE/CLASS with LINE/BRANCH counters; it has no changed-lines mode **[V]**.
- diff-cover reads JaCoCo XML or lcov against `git diff`, with `--fail-under` and `--compare-branch` **[V]**: a threshold on new or modified lines only, which matches the "new code" decision.
- PIT incremental analysis reuses earlier results and is labelled experimental **[V]**; Stryker incremental mode reruns only changed code, with blind spots (dependencies, snapshots) **[V]**. Google runs mutation only on changed lines at review, with mutant filtering, across 24,000+ developers **[V]** (Petrovic et al. 2021).
- Value **[I]**: coverage shows code was executed, mutation shows tests would notice a change, which is the precise weakness of agent-written tests. Cost: full runs are minutes to hours; scope to changed classes or run nightly.

## 6. Security and performance

- GitHub: code scanning and secret scanning are enabled by default on public repositories; private repositories need paid Code Security / Secret Protection; Dependabot alerts are in all plans **[V]**. CodeQL covers Java/Kotlin and JavaScript/TypeScript **[V]**.
- Semgrep diff-aware scans report only findings "newly introduced" after the baseline **[V]**; free-tier limits: not found.
- OWASP dependency-check: without an NVD API key updates are "extremely slow", and CI needs caching **[V]**; CPE matching false positives **[I]**. Redundant with Dependabot for a solo developer **[I]**.
- Performance **[I]**: realistic checks are query-count assertions in the existing Testcontainers tests and a frontend bundle budget. Load testing in CI is not proportionate at this scale.

## 7. Shrinking baseline, per tool

| Tool | Mechanism |
|---|---|
| Spotless | `ratchetFrom` **[V]** |
| ESLint | `--suppress-all` writes `eslint-suppressions.json`; new violations fail; fixed ones must be pruned (`--prune-suppressions`) or the run exits non-zero **[V]** |
| Biome | `biome lint --suppress --reason` inserts comments **[V]** |
| ArchUnit | `FreezingArchRule` **[V]** |
| dependency-cruiser | `--ignore-known` + `shrink-only` **[V]** |
| Error Prone / NullAway | per-check severity, package scoping **[V]**; no baseline file **[I]** |
| SpotBugs | filter file **[V]**; `excludeBugsFile` exists, baseline semantics not documented **[V]** |
| PMD, Checkstyle | suppressions only **[V]** for PMD; **[I]** for Checkstyle |
| Coverage | diff-cover **[V]** |

## 8. Default sets a factory can offer at registration

| Default | Explained by consequence |
|---|---|
| Google Java Style via formatter | No effect on behaviour; removes style from every review and diff |
| Error Prone defaults as errors | Each check is a real bug nine times in ten: reliability |
| NullAway on new packages | Removes the most common Java production crash |
| Layer rules (ArchUnit) | Keeps a change in one layer from leaking into others: cost of change |
| typescript-eslint `recommended-type-checked` + `stylistic` | Catches unhandled promises and unsafe `any`: reliability |
| `strict-type-checked` | More bugs caught, but rules change between minor versions **[V]**: occasional upgrade work |
| Airbnb | Not verified today; **[I]** predates flat config and is largely stylistic, superseded by formatter + typescript-eslint |

## 9. AI agents and guardrails

- Controlled evidence: Gloaguen et al. (ETH, 2026) find repository context files do not generally improve task success, raise inference cost by over 20 %, but agents do follow the instructions they contain; recommended use is non-standard practices only **[V]**.
- Anthropic's Claude Code guidance: give the agent a check that returns pass or fail (tests, build, linter); instruction files are "advisory", hooks "deterministic"; cut any line the agent would follow anyway, or convert it to a hook **[V]**.
- OpenAI's "harness engineering" write-up reports custom linters and structural tests enforcing a layered architecture plus recurring drift clean-up **[V]** via Böckeler (martinfowler.com, 2026-04-02), who notes no metrics are given; the original returned 403.
- A measured study showing that strict linters or architecture tests improve agent output quality: **not found**. The direction is supported by vendor and practitioner reports, not by a controlled result.
- Consequence **[I]**: every rule a tool can hold leaves the instruction file; the file keeps only how to run the checks and the standards code cannot see.

## Recommended minimal set for a solo developer (value per day of work)

1. Formatter in CI, both stacks, one reformat commit each (half a day).
2. Free GitHub security: Dependabot, secret scanning with push protection, CodeQL where free (an hour).
3. ArchUnit test for the prose layering rule, frozen (half a day); it replaces the prose.
4. ESLint blocking, `recommended-type-checked`, with bulk suppressions (half a day).
5. Error Prone at default severity; NullAway on new packages only (one day).
6. Diff-coverage gate on changed lines (half a day).
7. Later, on evidence of weak tests: PIT/Stryker on changed code, nightly.

Skip for now: SonarQube, PMD, Checkstyle beyond naming, OWASP dependency-check, Nx, load tests.

## Open questions for Benjamin

1. One reformat commit (noisy once, uniform after) or ratchet (quiet history, mixed style for months)?
2. Is the product repository public or private? Private means CodeQL and push protection are paid; the free route is Semgrep + gitleaks.
3. Diff-coverage threshold: higher blocks more agent PRs and costs more tokens per feature; lower lets untested branches merge.
4. Null-safety on new code only, or also annotate existing code (several agent-days, fewer production crashes)?
5. TypeScript `strict-type-checked`: more bugs refused, occasional breakage on linter upgrades. Accept?
6. Mutation testing: pay nightly CI minutes for proof that tests detect changes, or wait for a first escaped bug?

## Sources

- Spotless Maven: https://github.com/diffplug/spotless/blob/main/plugin-maven/README.md
- git blame: https://git-scm.com/docs/git-blame
- Biome linter: https://biomejs.dev/linter/
- Error Prone criteria: https://errorprone.info/docs/criteria
- NullAway: https://github.com/uber/NullAway
- SpotBugs filters: https://spotbugs.readthedocs.io/en/stable/filter.html ; Maven plugin: https://spotbugs.github.io/spotbugs-maven-plugin/spotbugs-mojo.html
- PMD suppression: https://pmd.github.io/pmd/pmd_userdocs_suppressing_warnings.html
- Checkstyle Google style coverage: https://checkstyle.org/google-style.html
- typescript-eslint configs: https://typescript-eslint.io/users/configs/ ; typed linting: https://typescript-eslint.io/getting-started/typed-linting/
- ESLint bulk suppressions: https://eslint.org/docs/latest/use/suppressions
- ArchUnit user guide: https://www.archunit.org/userguide/html/000_Index.html
- Spring Modulith verification: https://docs.spring.io/spring-modulith/reference/verification.html
- Maven Enforcer rules: https://maven.apache.org/enforcer/enforcer-rules/index.html
- dependency-cruiser CLI: https://github.com/sverweij/dependency-cruiser/blob/main/doc/cli.md
- eslint-plugin-boundaries: https://github.com/javierbrea/eslint-plugin-boundaries
- Nx module boundaries: https://nx.dev/docs/features/enforce-module-boundaries
- JaCoCo check: https://www.jacoco.org/jacoco/trunk/doc/check-mojo.html
- diff-cover: https://github.com/Bachmann1234/diff_cover
- PIT incremental: https://pitest.org/quickstart/incremental_analysis/ ; Stryker incremental: https://stryker-mutator.io/docs/stryker-js/incremental/
- Petrovic et al., mutation testing at Google: https://research.google/pubs/practical-mutation-testing-at-scale-a-view-from-google/
- GitHub Advanced Security availability: https://docs.github.com/en/get-started/learning-about-github/about-github-advanced-security ; CodeQL: https://docs.github.com/en/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning-with-codeql
- Semgrep CI: https://docs.semgrep.dev/semgrep-ci/overview
- OWASP dependency-check: https://github.com/dependency-check/DependencyCheck
- Gloaguen et al., Evaluating AGENTS.md: https://arxiv.org/abs/2602.11988
- Claude Code best practices: https://code.claude.com/docs/en/best-practices
- Böckeler, Harness engineering: https://martinfowler.com/articles/exploring-gen-ai/harness-engineering.html
- Not retrievable today (403): https://openai.com/index/harness-engineering/ ; https://cacm.acm.org/research/lessons-from-building-static-analysis-tools-at-google/
