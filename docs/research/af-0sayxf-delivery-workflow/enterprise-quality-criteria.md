# Enterprise delivery criteria for an autonomous software factory — sourced research

Research date: 2026-10-01. Scope: web apps, SaaS, internal tools; Java backends, web frontends, shell/Python tooling.
Purpose: replace an ad-hoc quality list by the criteria established software organisations actually apply, in a form usable as
(1) a per-ticket Definition of Done, (2) an outcome-level release/acceptance checklist, (3) a per-project profile of thresholds.

Reading conventions

- **[V]** = verified at the primary source during this research (page fetched and read).
- **[S]** = read through a secondary source or search snippet only; primary not reachable (paywall, 403/404).
- **[M]** = from model memory, not re-checked today; treat as a clue.
- "Analysis" paragraphs are my synthesis, not a quoted standard.

Headline finding (analysis): no standard gives "the list". What established organisations share is a **shape**:
a vocabulary of quality characteristics (ISO 25010), a small set of **automated gates on every change**, a **tiered
readiness review before launch** (tier chosen by risk/criticality), and a **human sign-off on the things machines cannot
judge** (fitness for purpose, design quality, risk acceptance). Thresholds are per-product, not universal.

---

## A. Sourced notes per topic

### A1. Quality models

**ISO/IEC 25010:2023 (SQuaRE — Product quality model), 2nd edition, replaces 25010:2011.**

- Nine product-quality characteristics: functional suitability, performance efficiency, compatibility, interaction
  capability, reliability, security, maintainability, flexibility, safety. [S — arc42 summary and ISO abstract as quoted by
  resellers; ISO page itself returned 403; standard text is paywalled]
- Changes vs 2011 [S]: **safety** added as a characteristic; **usability renamed interaction capability**;
  **portability renamed flexibility**; new sub-characteristics *inclusivity* and *self-descriptiveness* (interaction
  capability), *resistance* (security), *scalability* (flexibility); *user interface aesthetics* replaced by *user
  engagement*; *maturity* replaced by *faultlessness*. The quality-in-use model moved out to ISO/IEC 25019 and the
  overview to ISO/IEC 25002.
- Sub-characteristics per characteristic [M/S — not checked against the standard text]:
  functional suitability (completeness, correctness, appropriateness); performance efficiency (time behaviour, resource
  utilisation, capacity); compatibility (co-existence, interoperability); interaction capability (appropriateness
  recognisability, learnability, operability, user error protection, user engagement, inclusivity, user assistance,
  self-descriptiveness); reliability (faultlessness, availability, fault tolerance, recoverability); security
  (confidentiality, integrity, non-repudiation, accountability, authenticity, resistance); maintainability (modularity,
  reusability, analysability, modifiability, testability); flexibility (adaptability, scalability, installability,
  replaceability); safety (operational constraint, risk identification, fail safe, hazard warning, safe integration).
- Use (analysis): 25010 is a **vocabulary and completeness check**, not a set of thresholds. Its value here is to prove the
  criteria list has no blind spot. Safety is normally "not applicable" for business web apps and should be declared so
  explicitly in the project profile rather than silently dropped.
- Sources: https://quality.arc42.org/articles/iso-25010-update-2023 · https://www.iso.org/standard/78176.html (403 today)

**ISO/IEC 5055:2021 (CISQ Automated Source Code Quality Measures).**

- Measures internal structure of code on four factors — security, reliability, performance efficiency, maintainability —
  each defined as a set of CWE weaknesses detectable by static analysis. Supplements 25010 at source-code level. [V]
- Exact count of weaknesses not stated on the CISQ page read ([M]: roughly 138 CWEs). The CISQ page still says "4 of the 8"
  25010 characteristics, i.e. it is written against the 2011 model.
- Use (analysis): relevant as the justification for "static analysis finds a defined class of structural weaknesses";
  in practice you get it through SonarQube/CodeQL/Semgrep rule sets mapped to CWE, not by buying the standard.
- Source: https://www.it-cisq.org/standards/code-quality-standards/

### A2. Definition of Done, Definition of Ready, acceptance criteria

- **Scrum Guide 2020** [V]: the Definition of Done is the commitment attached to the Increment — a formal description of the
  state of the Increment when it meets the required quality measures. An item that does not meet it "cannot be released or
  even presented at the Sprint Review" and goes back to the backlog. The guide does **not** mention Definition of Ready nor
  acceptance criteria. https://scrumguides.org/scrum-guide.html
- **Definition of Ready** [S — scrum.org forum/blog material]: a complementary practice, not part of Scrum; commonly built on
  INVEST (independent, negotiable, valuable, estimable, small, testable). Known anti-pattern: DoR used as a contract/phase
  gate. Analysis: for unattended agents the anti-pattern argument is weaker — an agent cannot "refine in conversation",
  so a strict DoR (testable acceptance criteria, linked prototype screen, named contracts, out-of-scope stated) is the
  correct gate. It is the human-validated input side of the factory.
- **Given/When/Then** [V]: from Daniel Terhorst-North and Chris Matts (BDD); precondition / behaviour / expected outcome;
  equivalent to Arrange-Act-Assert. https://martinfowler.com/bliki/GivenWhenThen.html (2013)
- **EARS** (Easy Approach to Requirements Syntax; Mavin et al., Rolls-Royce, IEEE RE'09) [S — Wikipedia and vendor
  summaries]: five patterns — ubiquitous, event-driven (When), state-driven (While), optional feature (Where), unwanted
  behaviour (If/Then) — with the general form "While <precondition>, when <trigger>, the <system> shall <response>".
  https://en.wikipedia.org/wiki/Easy_Approach_to_Requirements_Syntax
- Analysis — which format where: EARS for **requirements in the spec** (one rule, one sentence, includes unwanted behaviour,
  which is exactly where agents under-deliver); Given/When/Then for **acceptance examples** that become executable tests.
  Traceability = each EARS rule has at least one G/W/T example and each example maps to at least one automated test.
- The DoD is **one global standard** applied to every ticket; acceptance criteria are **per ticket**. Do not mix them.

### A3. Production readiness reviews, launch checklists, 12-factor

- **Google SRE — Production Readiness Review** [V]: a process identifying the reliability needs of a service. Areas
  reviewed: architecture and inter-service dependencies; instrumentation, metrics and monitoring; emergency response;
  capacity planning; change management; performance (availability, latency, efficiency). Google moved from late PRRs to
  early engagement and then to **frameworks that encode the best practices by default** — the most relevant lesson for a
  factory: put the criteria in the template/golden path, not in a review at the end.
  https://sre.google/sre-book/evolving-sre-engagement-model/
- **Google SRE — Launch coordination checklist (Appendix E)** [V]: architecture; machines and datacenters; volume, capacity
  and performance; reliability and failover; monitoring and server management; security; automation and manual tasks;
  growth; external dependencies; schedule and rollout planning. https://sre.google/sre-book/launch-checklist/
- **Mercari production-readiness-checklist** (MIT, public reference version) [V]: two checklists — *design* (before
  development) and *pre-production* — with requirements depending on a **Production Readiness Level A/B/C** (critical /
  standard / experimental) derived from the service's SLO. Pre-production categories: maintainability (unit tests, config
  in env vars, pinned image tags, dependency bot, automated build/deploy, gradual deploy, automated rollback),
  observability (tracing, dashboards, actionable alerts, on-call playbooks, JSON logs to stdout, error tracking),
  reliability (autoscale, resource limits, zero-downtime deploy, graceful shutdown/degradation, probes, timeouts, smart
  retry), security (security review, non-root, secrets, no sensitive data in logs), "accessibility" in the sense of
  discoverable docs (design doc, owner, repo, SLOs), data storage (replication, least privilege, recovery, point-in-time
  recovery). https://github.com/mercari/production-readiness-checklist
- **Gruntwork Production Readiness Checklist** [V, partially — page read gives domains, not every item]: server-side,
  client-side, CI, CD, architecture, security, monitoring; examples: encrypted secrets, tested backups/restore, no shared
  keys, multi-AZ with health checks. https://www.gruntwork.io/devops-checklist/
- **GitLab readiness review** [S]: readiness is tracked per service in the `gl-infra/readiness` project with a template whose
  sections are filled **up to the target maturity (Experiment / Beta / GA)**; goal is enough documentation, observability
  and reliability for production scale. The old handbook page appears in the navigation as "deprecated" and the URL I tried
  returned 404, so the current canonical page was not read. https://gitlab.com/gitlab-com/gl-infra/readiness
- **Spotify Golden Paths** [V]: the "opinionated and supported path" to build a given kind of component, with blessed tools
  and a step-by-step tutorial; created to stop "rumour-driven development".
  https://engineering.atspotify.com/2020/08/how-we-use-golden-paths-to-solve-fragmentation-in-our-software-ecosystem
- **Zalando RESTful API Guidelines** [V]: API-first (define the API in OpenAPI and get it reviewed before coding);
  MUST/SHOULD/MAY rules (RFC 2119); automated linting by Zally; examples: Problem JSON for errors, semantic versioning.
  https://opensource.zalando.com/restful-api-guidelines/
- **Twelve-Factor App** [V]: codebase, dependencies, config in environment, backing services, build/release/run separation,
  stateless processes, port binding, concurrency, disposability, dev/prod parity, logs as event streams, admin processes.
  https://12factor.net/
- Pattern common to Mercari, GitLab and ASVS (analysis): **tiering**. Nobody applies the full list to everything. The
  factory's "project profile" should therefore be a tier (e.g. experimental / standard / critical) that switches criteria on
  and sets thresholds — this is the established answer to "highest standards" without checklist bloat.

### A4. Security, supply chain, privacy

- **OWASP ASVS 5.0.0** (released May 2025) [V — preface in the OWASP repo; release date via secondary]: about 350
  requirements in 17 chapters; three levels — L1 first layer of defence / entry point, L2 comprehensive standard practice,
  L3 high assurance. 5.0 adds requirements to **document key security decisions** and focuses on outcomes rather than
  prescribed mechanisms. Chapters include encoding and sanitisation, validation and business logic, web frontend security,
  API and web service, file handling, authentication, session management, authorization, self-contained tokens, OAuth/OIDC,
  cryptography, secure communication, configuration, data protection, secure coding and architecture, security logging and
  error handling, WebRTC [chapter names: S]. Share of requirements per level not verified.
  https://owasp.org/www-project-application-security-verification-standard/
- **OWASP Top 10:2025** [V — list read on the OWASP site; exact final-release date not verified]:
  A01 Broken Access Control; A02 Security Misconfiguration; A03 Software Supply Chain Failures; A04 Cryptographic Failures;
  A05 Injection; A06 Insecure Design; A07 Authentication Failures; A08 Software or Data Integrity Failures; A09 Security
  Logging & Alerting Failures; A10 Mishandling of Exceptional Conditions. New vs 2021: A03 (broadened from vulnerable
  components) and A10 (error handling). https://top10.owasp.org/2025/0x00_2025-Introduction
  Analysis: the Top 10 is an awareness list, ASVS is the verification standard. Use ASVS for the checklist and the Top 10
  as a coverage sanity check. A10 matters specifically for agent-written code (happy-path bias).
- **NIST SSDF, SP 800-218** [V]: version 1.1 is the final version on the CSRC project page (page updated 2026-04-13). Four
  practice groups: Prepare the Organization (PO), Protect the Software (PS), Produce Well-Secured Software (PW), Respond to
  Vulnerabilities (RV). **Version 1.2 (SP 800-218 Rev. 1)** was published as an initial public draft on 2025-12-17, comments
  closed 2026-01-30; **I could not confirm a final 1.2 as of today** — check before citing a version.
  https://csrc.nist.gov/projects/ssdf · https://csrc.nist.gov/pubs/sp/800/218/r1/ipd
- **SLSA v1.2** [V]: Build track L1 (provenance exists, generated by the build platform), L2 (hosted build platform signs
  the provenance), L3 (hardened platform: isolated runs, signing material unreachable from build steps). v1.2 adds a
  **Source track** (version control, history integrity, enforced controls, two-party review).
  https://slsa.dev/spec/v1.2/build-track-basics · https://slsa.dev/blog/2025/11/announce-slsa-v1.2
  Analysis: for a solo operator, Build L2 is obtainable for free with hosted CI attestations; the Source track's two-party
  review maps to "agent author + independent reviewer agent + protected branch", which is weaker than two humans — say so.
- **Secret scanning** [V]: GitHub push protection blocks a push containing a recognised secret before it lands; alerts are
  after the fact. https://docs.github.com/en/code-security/secret-scanning/introduction/about-push-protection
- **Threat-model-lite** [V]: the four questions of the Threat Modeling Manifesto as relayed by the OWASP cheat sheet — what
  are we working on, what can go wrong, what are we going to do about it, did we do a good enough job; STRIDE as the prompt
  list; do it at design time and keep it alive.
  https://cheatsheetseries.owasp.org/cheatsheets/Threat_Modeling_Cheat_Sheet.html
- **GDPR Article 25** [V — unofficial consolidated copy]: data protection by design (measures such as minimisation built in
  from the start, proportionate to risk and cost) and by default (only data necessary for each purpose is processed; no
  open-ended accessibility by default). https://gdpr-info.eu/art-25-gdpr/
- **CNIL GDPR developer's guide** [V]: 17 sheets — identify personal data, prepare development, secure the dev environment,
  manage source code, choose architecture, secure sites/apps/servers, minimise collection, manage user profiles, control
  libraries and SDKs, code quality and documentation, test, inform users, prepare exercise of rights, retention periods,
  legal basis in the implementation, analytics. The best single practical source for an EU solo founder.
  https://www.cnil.fr/en/gdpr-developers-guide
- **European Accessibility Act (Directive (EU) 2019/882)** [S]: applicable since 2025-06-28 to listed products and services
  including e-commerce; **microenterprises providing services are exempt (Art. 4(5))** — fewer than 10 persons and at most
  EUR 2 M turnover/balance sheet. National transposition governs; not legal advice.
- **Cyber Resilience Act** [S — law-firm summaries]: reporting obligations from 2026-09-11, main obligations from
  2027-12-11; pure SaaS is generally out of scope except as a "remote data processing solution" of a product. Not verified
  at EUR-Lex; a decision for Benjamin per project, not a factory default.

### A5. Code and architecture quality

- **Google engineering practices — code review** [V]: approve a change once it clearly improves overall code health, even
  if not perfect; facts and style guides over preference. Reviewers look at design, functionality, complexity (including
  over-engineering for hypothetical needs), tests, naming, comments (why, not what), style, consistency, documentation,
  every line, and the wider context. https://google.github.io/eng-practices/review/reviewer/standard.html ·
  https://google.github.io/eng-practices/review/reviewer/looking-for.html
- **Architectural fitness functions** [M — Ford, Parsons, Kua, Sadalage, *Building Evolutionary Architectures*, 2nd ed.;
  publisher page not reachable today]: any mechanism giving an objective integrity assessment of an architecture
  characteristic — i.e. architecture rules expressed as executable tests in CI.
- **ArchUnit** [V]: Java library checking layer rules, cycles, package/class dependencies, naming, annotations; ships
  layered/onion rule templates; `FreezingArchRule` records existing violations and fails only on new ones (user guide
  shows version 1.5.1). https://www.archunit.org/userguide/html/000_Index.html
  Equivalents [M]: dependency-cruiser / eslint-plugin-boundaries (JS/TS), import-linter (Python), Spring Modulith verify.
- **Static-analysis quality gate** [V]: SonarQube's default "Sonar way" gate applies to **new code**: no new issues, all new
  security hotspots reviewed, coverage on new code >= 80 %, duplication on new code <= 3 %.
  https://docs.sonarsource.com/sonarqube-server/quality-standards-administration/managing-quality-gates/introduction-to-quality-gates
  Complexity limits [M]: Sonar's cognitive-complexity rule defaults to 15 per function; Checkstyle cyclomatic default 10.
- **Test shape** [V]: test pyramid — many fast unit tests, some integration tests, very few end-to-end tests covering the
  highest-value journeys; consumer-driven contract tests between services; push tests down and delete redundant high-level
  ones (Vocke, 2018). Testing trophy — static checks at the base, emphasis on integration tests; the more tests resemble
  real usage the more confidence they give (Dodds).
  https://martinfowler.com/articles/practical-test-pyramid.html ·
  https://kentcdodds.com/blog/the-testing-trophy-and-testing-classifications
- **Coverage as a signal** [V/S]: Google's guidance — 60 % acceptable, 75 % commendable, 90 % exemplary as *guidelines*,
  no top-down mandate; high coverage does not prove good tests, low coverage does prove missing ones; focus on coverage of
  **changed lines**; use mutation testing to check that tests assert something.
  https://testing.googleblog.com/2020/08/code-coverage-best-practices.html
- **Mutation testing at scale** [V]: Google runs it diff-based, on covered and "interesting" lines only, and surfaces
  surviving mutants in code review (Petrovic and Ivankovic, 2018).
  https://research.google/pubs/state-of-mutation-testing-at-google/ — tools: PIT (Java), Stryker (JS/TS), mutmut/cosmic-ray
  (Python) [M].

### A6. UI/UX, design system, design-to-code fidelity

- **WCAG 2.2** [V]: W3C Recommendation (document dated 12 December 2024; first published as Recommendation October 2023 [M]).
  New at A/AA: 2.4.11 Focus Not Obscured (AA), 2.5.7 Dragging Movements (AA), 2.5.8 Target Size Minimum (AA), 3.2.6
  Consistent Help (A), 3.3.7 Redundant Entry (A), 3.3.8 Accessible Authentication Minimum (AA). 4.1.1 Parsing removed.
  https://www.w3.org/TR/WCAG22/
- **Automation ceiling for accessibility** [V]: Deque's 2021 study of 2 000+ audits found automated testing (axe-core)
  catches about 57 % of issues **by volume**; the rest needs manual checks (keyboard path, focus order, meaningful alt
  text, screen-reader sense).
  https://www.deque.com/blog/automated-testing-study-identifies-57-percent-of-digital-accessibility-issues/
- **Design tokens** [V]: Design Tokens Format Module **2025.10**, first stable version, published 2025-10-28 by the W3C
  Design Tokens Community Group; it is a Community Group report, **not a W3C Standard** nor on the standards track. Covers
  theming/multi-brand, modern colour spaces, aliases. https://www.w3.org/community/reports/design-tokens/CG-FINAL-format-20251028/
- **Nielsen's 10 usability heuristics** (1994, reviewed 2024) [V]: visibility of system status; match with the real world;
  user control and freedom; consistency and standards; error prevention; recognition rather than recall; flexibility and
  efficiency; aesthetic and minimalist design; help users recognise, diagnose and recover from errors; help and
  documentation. https://www.nngroup.com/articles/ten-usability-heuristics/
- **Core Web Vitals** [V]: LCP <= 2.5 s, INP <= 200 ms, CLS <= 0.1, each at the 75th percentile of page loads, mobile and
  desktop. https://web.dev/articles/vitals — field metrics; in CI you only get lab proxies (Lighthouse: LCP, CLS, TBT).
- **Performance budgets** [V]: limits on quantity metrics (bytes, requests), milestone timings, or rule-based scores;
  enforced with Lighthouse CI, bundlesize, bundler budgets. https://web.dev/articles/performance-budgets-101
- **Design QA as a named step** [V — one engineering-org write-up]: HubSpot runs design QA after development on a staging
  build: the designer checks design-system adherence, edge cases, error states, localisation, responsive behaviour and
  accessibility against a checklist, assigns severity to defects, and blocking ones go back to the engineer.
  https://product.hubspot.com/blog/avoid-design-debt-with-better-design-qa
- **Visual regression tooling** [V]:
  - Playwright `toHaveScreenshot`: baseline generated on first run and committed; per-pixel `threshold` default 0.2 in YIQ
    colour space; `maxDiffPixels` / `maxDiffPixelRatio` unset by default; animations disabled and caret hidden by default;
    `mask` and `stylePath` to neutralise volatile regions; docs warn rendering varies with OS, version, hardware, headless
    mode, so baselines must be produced in the same environment as the comparison.
    https://playwright.dev/docs/test-snapshots · https://playwright.dev/docs/api/class-pageassertions
  - Chromatic/Storybook: every story becomes a visual test; `diffThreshold` default 0.063; anti-aliased pixels ignored by
    default. https://www.chromatic.com/docs/threshold/ · https://storybook.js.org/docs/writing-tests/visual-testing
  - BackstopJS: `misMatchThreshold` default 0.1 %; `requireSameDimensions` default true; a scenario can take a
    **`referenceUrl` different from the tested `url`**; `--docker` for stable rendering. https://github.com/garris/BackstopJS
  - Percy: not read today [M: cloud service, perceptual diff, similar role to Chromatic].
- **Analysis — what is realistic when the reference is an HTML prototype (not Figma).** An HTML reference is a *better*
  machine oracle than Figma because both sides render in the same engine, so the comparison can be layered:
  1. **Token conformance (deterministic, per ticket)**: no raw colour/spacing/font literals outside the token files
     (stylelint/eslint rules); computed styles of key elements equal between prototype and build.
  2. **Structure conformance (deterministic, per ticket)**: same landmarks, headings, controls, labels — compare
     accessibility-tree snapshots of prototype and build; bounding boxes of named regions within a tolerance.
  3. **Pixel comparison prototype vs build (advisory)**: same container, viewport, fonts, fixture data; expect differences
     wherever real data, real states or real components differ from the mock; use a looser threshold and send the diff
     image to an agent judge for triage (intended / defect). Not a hard gate.
  4. **Human design acceptance (per outcome)**: Benjamin looks at build vs prototype side by side once per outcome.
  5. **After acceptance the build's own screenshots become the baseline**, and from then on pixel diffs are a strict
     regression gate (this is what visual regression tools are designed for; they detect change, not correctness).
  Preconditions: the prototype must cover the states (empty, loading, error, long content, narrow viewport) or the spec
  must say which states are "derive from design system"; otherwise fidelity is undefined for those states.

### A7. Integration and assembly practice

- **Walking skeleton** (Cockburn) [S — quoted consistently in secondary sources; original in *Crystal Clear*]: a tiny
  implementation of the system performing a small end-to-end function, linking the main architectural components; it need
  not use the final architecture; architecture and functionality then grow in parallel.
- **Tracer bullets** (Hunt and Thomas) [V — 2003 Artima interview; book tip "Use tracer bullets to find the target"]: thin
  but real end-to-end code kept and extended, as opposed to prototypes, which "are designed to be thrown away".
  https://www.artima.com/articles/tracer-bullets-and-prototypes
- **Continuous Integration in the original sense** (Fowler, revised 2024-01-18) [V]: everyone integrates into mainline at
  least daily; every integration verified by an automated self-testing build; a broken build is fixed immediately; build
  kept fast (about ten minutes); unfinished work hidden behind flags; test in a production-like environment; automated
  deployment. https://martinfowler.com/articles/continuousIntegration.html
  Analysis: CI is about **integration frequency on one mainline**, not about "having a pipeline". For parallel agents this
  means small tickets merged to the integration branch continuously, each merge re-running the end-to-end smoke suite — the
  ticket graph is not done ticket by ticket in isolation and assembled at the end.
- **Contract tests** [V]: consumer-driven contracts (Pact) or, for a single team, provider verification against the OpenAPI
  document (source: practical test pyramid, Zalando API-first).
- **DORA metrics** (guide updated 2026-01-05) [V]: five metrics — change lead time, deployment frequency, failed deployment
  recovery time (throughput group); change fail rate, deployment rework rate (instability group). Speed and stability are
  not a trade-off. https://dora.dev/guides/dora-metrics/
- **DORA on AI-assisted delivery** [V for the qualitative statement; S for numbers]: the 2024 report states AI adoption
  raises individual productivity but harms delivery stability and throughput, and that small batches and robust testing
  remain essential. Secondary sources give -1.5 % throughput and -7.2 % stability per 25 % more AI adoption, and summarise
  the 2025 report as "AI amplifies what is already there". https://dora.dev/research/2024/dora-report/
  Analysis: for an agent factory the relevant DORA signals are **change fail rate and rework rate** (how often a merged
  ticket needed a follow-up fix), measured per ticket class.
- **Increment-level demo/acceptance**: Scrum's Sprint Review inspects a Done increment [V via Scrum Guide]; in the factory
  this is the outcome-level acceptance by Benjamin on a running, deployed build.

### A8. Operability

- **Four golden signals** [V]: latency, traffic, errors, saturation; alert on symptoms, keep paging rules few and
  actionable. https://sre.google/sre-book/monitoring-distributed-systems/
- **Logs**: event stream to stdout (12-factor XI) [V]; structured JSON, no sensitive data (Mercari items) [V].
- **Error handling**: OWASP Top 10:2025 A10 and A09 [V]; Problem JSON for API errors (Zalando) [V].
- **Rollback / gradual deploy / automated rollback; graceful shutdown; probes; timeouts and retries** (Mercari) [V].
- **Backups with tested restore, point-in-time recovery** (Mercari data storage, Gruntwork) [V].
- **Runbooks / on-call playbooks, owner, SLOs documented** (Mercari, Google PRR emergency response) [V].
- **Performance budgets** — see A6.
- [M] OpenTelemetry is the vendor-neutral default for traces/metrics/logs; not re-verified today.

---

## B. Proposed criteria framework

Thirteen criteria in five groups. Each is a named, stable heading; the rows below it are the checkable items.

Verification legend: **D** = deterministic tool (pass/fail in CI); **A** = agent judge (independent reviewer agent with a
rubric and evidence; advisory or gating depending on profile); **H** = human (Benjamin).
Level legend: **T** = every ticket (Definition of Done); **O** = outcome/release checklist; **P** = set once in the project
profile (threshold or applicability).

| # | Criterion (named) | What it means in one line | Source standard | Level | Verification | Typical tools |
|---|---|---|---|---|---|---|
| **G1** | **Conformance** | | | | | |
| 1 | **Spec fidelity and traceability** | Every acceptance criterion is implemented and proven by a test; nothing unrequested is added | ISO 25010 functional suitability; Scrum DoD; EARS; Given/When/Then | T + O | D: each criterion ID maps to >= 1 passing test. A: diff vs ticket scope (missing / extra behaviour). H: outcome demo | Test tags carrying criterion IDs, Cucumber/JUnit/Playwright, traceability script |
| 1a | Unwanted-behaviour coverage | Each "if error/invalid/unauthorised" rule in the spec has a test | EARS unwanted-behaviour pattern; OWASP Top 10:2025 A10 | T | D (tests exist and pass) + A (were the error paths in the spec all covered?) | Same |
| 2 | **Prototype fidelity and design-system conformance** | The built UI matches the validated prototype and uses only design-system tokens and components | Design QA practice (HubSpot); Design Tokens 2025.10; Storybook/Chromatic practice | T + O | D: token lint, structure/aria snapshot vs prototype, visual regression vs accepted baseline. A: triage of prototype-vs-build pixel diffs. H: side-by-side acceptance per outcome | stylelint/eslint token rules, Playwright `toHaveScreenshot` + aria snapshots, BackstopJS `referenceUrl`, Storybook |
| 2a | All UI states exist | Empty, loading, error, success, long-content and disabled states are implemented | Nielsen #1, #9; design QA checklists | T | D: a story/test per state. A: state inventory vs prototype | Storybook, Playwright |
| **G2** | **Quality in use** | | | | | |
| 3 | **Accessibility** | Meets WCAG 2.2 level AA | WCAG 2.2; EAA where applicable; ISO 25010 inclusivity | T (auto) + O (manual) | D: axe rules with zero violations (covers roughly half the issues by volume). A: keyboard path and focus order walkthrough via browser automation. H: screen-reader spot check per outcome | axe-core / @axe-core/playwright, Lighthouse, pa11y |
| 4 | **UX quality and responsiveness** | Usable at the profile's breakpoints; follows usability heuristics; clear feedback and error recovery | Nielsen heuristics; ISO 25010 interaction capability; WCAG 1.4.10 reflow | T (breakpoints) + O (heuristic review) | D: screenshots at each breakpoint, no horizontal overflow, target sizes. A: heuristic evaluation with the 10 heuristics as rubric. H: judgment on the outcome | Playwright viewports, agent rubric |
| 5 | **Performance efficiency** | Stays inside the declared budgets (web vitals, bundle size, API latency) | Core Web Vitals; performance budgets; ISO 25010 performance efficiency; SRE PRR capacity | T (budgets) + O (load check) + P (numbers) | D | Lighthouse CI, bundlesize, k6/Gatling, JMH where relevant |
| **G3** | **Engineering integrity** | | | | | |
| 6 | **Code health** | Readable, simple, consistent code with no new static-analysis issues | Google code review guide; ISO 5055; Sonar "new code" gate | T | D: formatter, linter, type check, analyser gate on new code, complexity and duplication limits. A: review against the Google "what to look for" list | Spotless/Checkstyle/ErrorProne/SpotBugs, ESLint/tsc, ruff/mypy, shellcheck/shfmt, SonarQube, Semgrep |
| 7 | **Architecture conformance** | The change respects declared module boundaries, dependency direction and API contracts | Fitness functions (Building Evolutionary Architectures); ArchUnit; Zalando API-first; 12-factor | T + P (the rules) | D: architecture tests, API lint, contract verification, schema-migration check. A: "does this belong in this module?" | ArchUnit / Spring Modulith, dependency-cruiser, import-linter, Spectral or Zally, Pact or OpenAPI validation, Flyway/Liquibase validate |
| 8 | **Test adequacy** | Tests would fail if the behaviour broke; the suite has the right shape and is not flaky | Test pyramid/trophy; Google coverage guidance; mutation testing at Google | T + P (thresholds) | D: changed-line coverage floor, mutation score on changed code, flake detection by re-run, no skipped tests. A: are assertions meaningful? | JaCoCo/Istanbul/coverage.py with diff-cover, PIT/Stryker/mutmut, Playwright |
| **G4** | **Trust** | | | | | |
| 9 | **Application security** | Meets the ASVS level chosen for the project; no Top 10 class left unaddressed | OWASP ASVS 5.0; OWASP Top 10:2025; NIST SSDF PW practices | T (SAST, authz tests) + O (ASVS checklist, DAST) + P (level) | D: SAST, security headers, authz negative tests, DAST baseline. A: ASVS checklist walk with evidence per requirement, threat-model delta for the ticket. H: accepts residual risk | Semgrep, CodeQL, OWASP ZAP baseline, custom authz test matrix |
| 9a | Threat model kept current | The four questions answered for the outcome; new trust boundaries flagged | Threat Modeling Manifesto / OWASP cheat sheet; ASVS 5.0 documented security decisions; Top 10 A06 | O | A drafts, H validates | Markdown threat model in repo |
| 10 | **Supply chain and secrets** | Dependencies known, pinned and free of known exploitable vulnerabilities; no secret in the repo; build is attested | Top 10:2025 A03; SLSA v1.2; SSDF PS/PW; 12-factor II/III | T | D | gitleaks or push protection, OSV-Scanner / Dependabot / Renovate / OWASP Dependency-Check, lockfiles, CycloneDX SBOM, build provenance attestation, licence check |
| 11 | **Privacy and data protection** | Personal data is inventoried, minimised, protected, erasable and has a retention rule | GDPR Art. 25 and 32; CNIL developer guide | T (flag) + O (review) | D: schema diff flags new personal-data fields; no personal data in logs (lint/test). A: drafts data-inventory delta. H: decides purpose, legal basis, retention, sub-processors | Schema annotations, log scrubber tests, record of processing in repo |
| **G5** | **Run** | | | | | |
| 12 | **Integration and releasability** | The change is merged to mainline, the whole system still works end to end, and it can be deployed and rolled back by script | Fowler CI; walking skeleton; tracer bullets; 12-factor V and X; DORA | T + O | D: full build green on the integration branch, end-to-end smoke suite, clean-environment deploy, migration up (and down or forward-fix) rehearsal, rollback rehearsal | CI, Playwright smoke, Testcontainers, docker compose, Flyway |
| 13 | **Operability and recoverability** | Someone other than the author can run, observe, diagnose and restore it | Google SRE PRR and golden signals; Mercari checklist; Top 10 A09; 12-factor XI | T (logs, errors, health) + O (alerts, backup restore, runbook) | D: health/readiness endpoints, structured logs, error tracking wired, restore test, alert rules exist. A: runbook completeness review by "cold start" (a fresh agent follows it). H: accepts SLO and on-call reality | OpenTelemetry, Sentry-type tracker, uptime probe, backup/restore script, README/runbook/ADR |

### How the table becomes the three artefacts

**(1) Definition of Done — per ticket (all D, fast, no human).** Acceptance criteria each have a passing test (1, 1a);
token lint + state coverage + visual regression vs baseline (2, 2a); axe clean (3); breakpoints render (4); budgets hold
(5); formatter/linter/types/analyser gate (6); architecture tests + contract checks (7); changed-line coverage and
mutation floor, no flaky/skipped tests (8); SAST + authz negative tests (9); secret scan + dependency scan + lockfile (10);
personal-data flag raised if schema touched (11); merged to integration branch with smoke suite green (12); logs/errors/
health follow the conventions (13); docs touched when behaviour changed. Plus one **independent agent review** (not the
author) using the Google review list, gating on correctness and scope only.

**(2) Outcome acceptance / release checklist (D + A, ending with H).** End-to-end journeys from the spec pass on a
deployed build; prototype-vs-build design QA report; manual accessibility checks; heuristic review; load/budget check;
ASVS checklist at the profile level with evidence; threat model updated; SBOM and provenance produced; privacy review;
clean deploy, rollback and restore rehearsed; runbook passes a cold-start test; then **Benjamin's demo and sign-off**.

**(3) Project profile (P) — thresholds and applicability chosen once per project.** Suggested fields, with defaults that
come from the sources (to be confirmed by Benjamin, not asserted as "the standard"):

| Profile field | Source-backed default | Notes |
|---|---|---|
| Tier | experimental / standard / critical | Mercari A/B/C, GitLab maturity, ASVS levels |
| ASVS level | L1 internal tools; L2 anything holding personal data or money | ASVS 5.0 |
| WCAG target | 2.2 AA | Legal duty depends on EAA scope and size |
| Core Web Vitals (lab proxy) | LCP <= 2.5 s, CLS <= 0.1, INP <= 200 ms in the field | web.dev |
| Coverage on changed lines | 80 % (Sonar default); overall 60/75/90 are Google's descriptive bands | Signal, not target |
| Mutation score on changed code | project-chosen; start by reporting, gate later | No authoritative number exists |
| Complexity / duplication | cognitive complexity 15 per function; duplication on new code <= 3 % | Sonar defaults |
| Visual diff thresholds | Playwright threshold 0.2, `maxDiffPixelRatio` small and explicit; Backstop 0.1 % | Tool defaults; tune per project |
| Breakpoints | list declared per project | No standard list |
| SLSA build level | L1 minimum, L2 on hosted CI | SLSA v1.2 |
| Architecture rules | layer/module map as ArchUnit-style tests | Per project |
| SLO, RPO/RTO, retention periods | per project | Human decisions |
| Not applicable | safety; i18n; multi-region; etc., stated explicitly | ISO 25010 completeness |

---

## C. Universal versus project-type dependent

**Universal (every deliverable, including shell/Python tooling):** spec fidelity and traceability (1); code health (6);
test adequacy (8); supply chain and secrets (10); integration and releasability (12); the logging/error-handling/README
part of operability (13); architecture conformance in its minimal form (declared boundaries, no cycles) (7).

**Depends on project type:**

| Criterion | Applies when | Varies how |
|---|---|---|
| 2 Prototype fidelity / design system | There is a UI | CLI/tooling: replaced by "CLI contract" (help text, exit codes, stable output format) |
| 3 Accessibility | There is a UI | Public-facing: full AA plus manual checks; internal tool: AA automated plus keyboard path |
| 4 UX / responsive | There is a UI | Breakpoint list per project; internal desktop-only tools may declare a single breakpoint |
| 5 Performance | Always, but the metric changes | Web: Core Web Vitals and bundle size; API: latency percentiles and throughput; batch/CLI: runtime and memory |
| 7 API contracts | There is a network API or more than one deployable | OpenAPI lint and contract tests; monolith with no external consumers: internal module rules only |
| 9 Application security level | Always, level varies | L1 internal behind SSO; L2 internet-facing with accounts or personal data; L3 rarely |
| 11 Privacy | Personal data is processed | None processed: one-line declaration; otherwise full review, human-owned |
| 13 Operability depth | Long-running service vs run-to-completion tool | Service: health, alerts, backup/restore, runbook; tool: exit codes, logs, idempotence, dry-run |
| Safety (ISO 25010) | Physical or financial harm possible | Normally declared not applicable |
| Regulatory overlays (EAA, CRA, sector rules) | Market and business model | Human decision per project |

Stack-specific tooling is a *mapping*, not a different criterion: Java (ErrorProne, SpotBugs, ArchUnit, JaCoCo, PIT),
TypeScript (tsc strict, ESLint, dependency-cruiser, Vitest/Playwright, Stryker), Python (ruff, mypy, import-linter, pytest,
mutmut), shell (shellcheck, shfmt, bats).

---

## D. Known traps

1. **Coverage as a target (Goodhart).** A mandated percentage produces assertion-free tests; agents are especially good at
   this. Countermeasures from the sources: gate on changed lines only, treat low coverage as the signal, and use mutation
   testing or a reviewer agent to check that tests can fail. Never let the authoring agent adjust the threshold.
2. **Tests written by the same agent that wrote the code.** They encode the implementation's misunderstanding. Derive
   tests from the acceptance criteria (ideally before or by a different agent), and keep the outcome-level end-to-end suite
   owned by the spec, not by tickets.
3. **Pixel-diff flakiness.** Fonts, anti-aliasing, GPU, OS, animations, dynamic data. Mitigations stated by the tool
   docs: same container for baseline and test, animations disabled, masks for volatile regions, explicit small tolerance.
   A raised threshold to "make it green" hides real layout regressions (Chromatic warns about this explicitly).
4. **Visual regression mistaken for design fidelity.** A baseline proves "unchanged", not "correct". If the first baseline
   is auto-approved by an agent, the tool certifies whatever was built. First baseline needs comparison to the prototype
   and a human acceptance; baseline updates must be a reviewed, attributable action.
5. **Checklist theatre.** Boxes ticked without evidence. Every item needs a machine-checkable artefact (report, log, test
   ID) attached; items that can only be answered "yes" by assertion should be deleted or moved to the human list. Google's
   own trajectory (PRR checklists -> frameworks) says to encode criteria in templates and CI rather than in reviews.
6. **One-size-fits-all rigour.** Applying the critical-tier list to an internal script wastes budget and trains everyone
   to ignore the list. Use tiers (Mercari, GitLab, ASVS all do).
7. **Agent judge marking its own homework / judge drift.** An LLM judge is non-deterministic and agreeable. Use it for
   triage and for rubric-based review with cited evidence, make it independent of the author, calibrate it on known-bad
   samples, and never let it be the only gate for anything in the human column.
8. **Automated accessibility overclaim.** Zero axe violations is not WCAG conformance (roughly half the issues by
   volume are out of reach of automation). Report "automated checks pass" and "manual checks done" separately.
9. **Lab performance mistaken for field performance.** Core Web Vitals are defined on real-user data at the 75th
   percentile; CI numbers are proxies (INP cannot be measured in lab; TBT is the stand-in).
10. **Big-bang integration.** Tickets individually "done" but never assembled until the end — the failure walking skeleton
    and continuous integration exist to prevent. With parallel agents, batch size grows silently; DORA's data on AI
    adoption points at exactly this (stability drops when batches grow).
11. **Definition of Ready as bureaucracy / Definition of Done as wish list.** DoR should contain only what an unattended
    agent cannot ask for; DoD only what is checked on every ticket. Everything else goes to the outcome checklist.
12. **Suppression creep.** `@SuppressWarnings`, `eslint-disable`, skipped tests, frozen architecture violations, widened
    thresholds. Count them and gate on the delta; a suppression added by an agent needs a stated reason and review.
13. **Scanner noise treated as security.** Dependency scanners report unreachable vulnerabilities; SAST reports false
    positives. Without triage rules the gate is either ignored or blocks everything. Conversely, clean scans say nothing
    about authorisation logic (Top 10 A01), which needs explicit negative tests.
14. **Standards cited at the wrong version.** ISO 25010 (2011 vs 2023 names), ASVS (4.0.3 vs 5.0 numbering), OWASP Top 10
    (2021 vs 2025), SSDF (1.1 final vs 1.2 draft), DORA (four keys vs five metrics). Pin versions in the profile.

---

## E. What could not be verified at the source

- ISO/IEC 25010:2023 full text (paywalled; ISO page 403). Characteristic names and changes come from arc42 and reseller
  abstracts; the full sub-characteristic list is from memory/secondary.
- ISO/IEC 5055 weakness count.
- ASVS 5.0 chapter list and the share of requirements per level (project page and preface read; "Using the ASVS" page 404).
- OWASP Top 10:2025 final publication date (the list itself was read on the OWASP site).
- SSDF 1.2 final status as of 2026-10-01 (draft confirmed; final not found on CSRC).
- GitLab's current production-readiness handbook page (404; described from search snippets and the readiness project).
- Gruntwork checklist item-level content (domains only).
- Cockburn's walking-skeleton wording (secondary quotations); *Building Evolutionary Architectures* definition (memory).
- EARS primary paper (secondary summaries).
- EAA Article 4(5) and CRA dates/scope (secondary legal summaries; EUR-Lex page returned empty). Not legal advice.
- DORA numeric effects of AI adoption (secondary); Percy, OpenTelemetry, complexity defaults (memory).
- 12factor.net shows no update note; I recall the methodology being opened to community maintenance in late 2024 but did
  not verify it.
