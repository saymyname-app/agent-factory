# Design standards held by code, not by designer review

Research date: 2026-10-12. Markers: **[V]** verified from the cited source, **[I]** inferred (reasoning or general knowledge, not read in a source today), **[NF]** not found. CI costs are all **[I]** orders of magnitude: no source publishes them for this app.

## Summary

| Standard family | Check by code | Tool | What stays human judgement | CI cost | Adoption on existing code |
|---|---|---|---|---|---|
| Colours, typography, spacing, shape, z-index | Refuse literals outside the theme file | ESLint `no-restricted-syntax` or a small custom rule (TSX); stylelint `declaration-property-value-disallowed-list` / `stylelint-declaration-strict-value` (CSS) | Whether the token chosen is the right one; whether the palette is good | seconds | ESLint bulk suppressions (count per file per rule) |
| Accessibility, static | JSX misuse | `eslint-plugin-jsx-a11y` | Everything needing a rendered DOM | seconds | bulk suppressions |
| Accessibility, rendered | WCAG A/AA rules on real pages, 2 widths | `@axe-core/playwright` | Meaning of alt text, focus order, keyboard logic, most WCAG 2.2 additions | ~1-3 min | fingerprint snapshot of known violations |
| Visual regression | Pixel diff at 390 and 1440 | Playwright `toHaveScreenshot`, baselines in git | Whether a changed baseline is an intended change | ~2-5 min | baselines start from today's state |
| Performance | Bundle size limit; lab metrics | `size-limit`; Lighthouse CI | Field Core Web Vitals (INP is field-only) | size: <1 min; LHCI: ~3-5 min | limit = current size + margin |
| Motion | Duration/easing literals refused; reduced-motion honoured | same lint rule; Playwright `emulateMedia` | Whether motion feels right | seconds / part of e2e | bulk suppressions |

## 1. Tokens and their single source

- The W3C Design Tokens Community Group format has a published version **2025.10**; the editor's draft is dated 2026-09-08. Files are `.tokens` / `.tokens.json`; types include color, dimension, fontFamily, fontWeight, duration, cubicBezier, number, and composites (typography, shadow, border, transition, gradient, strokeStyle). **[V]** [S1] It is a Community Group report, not a W3C Recommendation. **[I]**
- Style Dictionary has "first-class support for the DTCG format" since v4; 2025.10 is "a work in progress in v5". **[V]** [S2] It transforms one token source into per-platform outputs. **[I]**
- MUI can emit its theme as CSS custom properties ("CSS theme variables"): values become inspectable in dev tools, dark-mode SSR flicker is avoided; cost is larger HTML. **[V]** [S3] MUI's theme already carries motion tokens: durations `shortest` 150 ms to `complex` 375 ms and four easings, composed by `theme.transitions.create`. **[V]** [S4]
- Established practice **[I]**: one source of truth, everything else generated. For a single MUI app the theme file *is* the source (extend it with spacing, shape, motion, z-index). A DTCG JSON file plus Style Dictionary pays only when a second stack (non-MUI, native, plain CSS) must consume the same tokens.

## 2. Lint rules that refuse hard-coded values

- **No ready-made ESLint rule for MUI `sx` was found.** **[NF]** (one web search; closest hits target styled-components or React Native.)
- Named-team precedent: Atlassian ships `ensure-design-token-usage` in its ESLint plugin: hard-coded colours are violations by default, spacing and shape are opt-in domains, with partial autofix and an `exceptions` list. **[V]** [S5] It is tied to Atlassian's token package, so it is a model, not a drop-in. **[I]**
- Generic mechanism: ESLint `no-restricted-syntax` takes AST selectors with a custom message. **[V]** [S6] A selector matching string literals shaped like `#hex`, `rgb(`, `NNpx`, `NNms` under `sx`/`style` attributes is feasible. **[I]** (regex matching in selectors not confirmed on the page read.)
- CSS files: stylelint `declaration-property-value-disallowed-list` maps properties (regex allowed) to forbidden value patterns. **[V]** [S7] `stylelint-declaration-strict-value` (MIT) forces chosen properties to use a variable or function, with `ignoreValues`; autofix only if you write it. **[V]** [S8]
- Limits **[I]**: static rules see literals only. They miss values arriving through variables, imports, template strings, computed expressions and `styled()` unless each form is targeted; they cannot tell a legitimate literal (SVG asset, chart series, `1px` border) from a violation, hence an allow-list. Simplest robust form: forbid colour/px/ms literals in every file except the theme folder.

## 3. Accessibility (WCAG 2.2 AA)

- axe-core (MPL-2.0): "find on average 57% of WCAG issues automatically"; "zero false positives (bugs notwithstanding)"; uncertain results are returned as "incomplete" for manual review. **[V]** [S9] The 57% is Deque's own figure, counted by **issue volume** over 2,000+ audits, not by share of success criteria. **[V]** [S10]
- Independent counterweight: the GOV.UK tool audit planted 142 barriers; best tool found 40%, aXe 29%. **[V]** [S11] (older audit; date not checked.)
- WCAG 2.2 adds six A/AA criteria (Consistent Help, Redundant Entry, Focus Not Obscured, Dragging Movements, Target Size Minimum, Accessible Authentication). **[V]** [S12] axe-core has **one** `wcag22aa` rule, `target-size`, **disabled by default**. **[V]** [S13] So "WCAG 2.2 AA by code" means: axe with tags `wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22aa` covers the 2.0/2.1 machine-testable part plus target size; the other five 2.2 additions are not automated by axe. **[I]**
- Playwright documents `@axe-core/playwright`, `withTags`, `disableRules`, `exclude`, and a **fingerprint snapshot** (rule id + selectors) for known violations; it states "many accessibility problems can only be discovered through manual testing". **[V]** [S14]
- `eslint-plugin-jsx-a11y` (MIT): "only catches errors in static code"; custom components need `settings.components` / `polymorphicPropName` mapping. **[V]** [S15] With MUI, unmapped components are invisible to it. **[I]**
- Lighthouse and pa11y: not researched separately; Lighthouse's accessibility category runs axe rules. **[I]**
- Stays manual **[I]**: quality of text alternatives, focus order and visibility, keyboard operability of custom widgets, reading order, error wording, cognitive criteria. Part is scriptable as Playwright keyboard walkthroughs per critical flow.
- False positives **[I]**: colour contrast over gradients/images lands in "incomplete"; fail on `violations` only.

## 4. Visual regression at two widths

- Playwright `toHaveScreenshot`: baselines live next to the test and are committed; names include browser and platform; "Browser rendering can vary based on the host OS, version, settings, hardware…", so baselines must be produced in the environment that checks them. Options: `threshold` (default 0.2), `maxDiffPixels`, `maxDiffPixelRatio`, `mask`, `stylePath`; animations are disabled by default (finite ones fast-forwarded). Widths are set per project via `viewport`. **[V]** [S16][S17][S18]
- Zero-cost self-hosted route: Playwright alone, baselines in git, generated in CI or a pinned container, never on a laptop. **[I]**
- Hosted: Chromatic free 5,000 snapshots/month, then $179/month; billed as tests x builds x browsers x modes. **[V]** [S19] Argos Hobby free 5,000 screenshots/month, Pro $100/month for 35,000; repository is MIT. **[V]** [S20] Self-hosting Argos: **[NF]**. Percy pricing: **[NF]**.
- **Lost Pixel is archived and being sunset** (team joining Figma): do not adopt. **[V]** [S21] reg-suit (MIT) only compares images you supply and needs S3/GCS storage. **[V]** [S22]
- Flakiness sources **[I]**: fonts not loaded, live data, dates, animations, anti-aliasing across machines. Mitigations: seeded data, masks, fixed clock, same container.
- Who approves a changed baseline without a human: **[NF]** in any primary source. Proposal **[I]**: a baseline may change only in a PR whose ticket declares a visual change; the authoring agent regenerates, a different reviewing agent compares before/after images against the ticket intent; undeclared diffs fail.

## 5. Performance budgets

- `size-limit` (MIT): limit per path in bytes or time, errors when exceeded; docs suggest about 25% above current size for apps. **[V]** [S23] Deterministic, so no flakiness. **[I]**
- Lighthouse CI: eslint-style assertions (`off`/`warn`/`error`, `maxNumericValue`), `budgetsFile`, 3 runs by default. **[V]** [S24] Lighthouse itself warns scores vary with hardware and contention; "median… of 5 runs is twice as stable as 1 run"; avoid shared-core runners. **[V]** [S25] On hosted CI runners, timing assertions are a known false-failure source; byte and count budgets are stable. **[I]**
- Core Web Vitals "good": LCP <= 2.5 s, INP <= 200 ms, CLS <= 0.1 at the 75th percentile; INP cannot be measured in the lab, TBT is the proxy. **[V]** [S26]

## 6. Motion

- Tokens: MUI `theme.transitions` (above); DTCG has `duration`, `cubicBezier`, `transition`. **[V]** [S1][S4]
- Reduced motion: MUI `theme.motion.reducedMotion` accepts `never` (default), `system`, `always`; it covers MUI transition components; "for custom CSS transitions, you must add the reduced-motion overrides yourself". **[V]** [S4] (read on docs for MUI v9.5; availability in the app's MUI version not checked.)
- WCAG: 2.3.3 Animation from Interactions is **AAA**; `prefers-reduced-motion` is its sufficient technique C39. **[V]** [S27] So reduced motion is beyond AA: a chosen standard, not an AA obligation. **[I]**
- Checkable: (a) lint refuses `ms`/`s`/`cubic-bezier` literals outside the theme **[I]**; (b) Playwright `emulateMedia({ reducedMotion: 'reduce' })` **[V]** [S28] then assert computed transition/animation durations are ~0 **[I]**. Not checkable: whether motion is tasteful.

## 7. Switching checks on over existing code

- **ESLint bulk suppressions** (built in): `eslint --suppress-all` / `--suppress-rule` writes `eslint-suppressions.json`, one **count per file per rule**; only `error` rules; if a file exceeds its count, ESLint "will report all of them"; fixed violations leave unused suppressions that make the run exit non-zero until `--prune-suppressions`. **[V]** [S29][S30] That is a shrink-only list by construction, provided CI refuses any PR that raises a count. **[I]** Introduced in ESLint 9.24: **[I]** (version not on the pages read).
- Trade-off **[I]**: granularity is the file, not the line. Touching a legacy file without adding violations passes; adding one surfaces all of that rule's violations in the file.
- **Betterer**: stores results in `.betterer.results`, fails when worse, updates when better. **[V]** [S31] Maintenance status and built-in ESLint test: **[NF]**. Redundant with bulk suppressions for ESLint. **[I]**
- **Changed-lines-only**: `eslint-plugin-diff` v3 (MIT) reports only diagnostics overlapping changed lines; requires ESLint 10+ and flat config. **[V]** [S32] Weaker guarantee: nothing records the debt or proves it shrinks. **[I]**
- Non-ESLint checks **[I]**: axe uses the fingerprint snapshot [S14]; screenshots and size limits baseline at today's state.

## 8. Starting themes and licences

| Theme | Licence | Fit |
|---|---|---|
| MUI free templates (dashboard, marketing, sign-in…), each with a shared custom theme plus a Material Design 2 default | MIT (MUI repository) **[V]** [S33][S34] | Direct: same stack |
| Material Color Utilities (schemes from one source colour, HCT, contrast) | Apache-2.0 **[V]** [S35] | Generates a palette from a brand colour; Material Design 3 support status in Material UI: **[NF]** |
| Radix Themes (`accentColor`, `grayColor`, `radius`, `scaling`) | MIT **[V]** [S36][S37] | Other component library: replaces MUI |
| shadcn/ui themes (CSS variables, OKLCH, copied into the project) | MIT **[V]** [S38][S39] | Tailwind stack |
| Open Props (colours, sizes, easings, animations, shadows, z-index; ships DTCG-style and Style Dictionary JSON) | MIT **[V]** [S40][S41] | Stack-neutral token values |

Per-product identity **[I]**: keep the token *names* and the checks common to all products; each product supplies only *values* (brand colour to generated palette, font pair, radius, density). The rules never change per product.

## Recommended minimal set for a solo developer

Ordered by value per day of work. **[I]**

1. **Make ESLint blocking with bulk suppressions** (half a day). Unlocks every later rule; turns the red baseline into a counted, shrink-only list.
2. **Complete the theme, then one "no literals outside the theme" rule** for colours, px, ms, z-index (one day). Addresses the ~240 colours and ~190 px literals directly.
3. **`eslint-plugin-jsx-a11y` strict, with MUI component mapping** (a few hours).
4. **Playwright on PRs at 390 and 1440: axe scan (with `wcag22aa`) plus screenshots of 5-10 key screens**, baselines in git, pinned container (one to two days). One harness, three standards.
5. **`size-limit`** on the built bundle (one hour).
6. **Reduced-motion**: theme setting plus one Playwright assertion (a few hours).

Parked: Lighthouse CI timing assertions (flaky on shared runners), DTCG + Style Dictionary (until a second stack exists), hosted visual services, Betterer.

## Open questions for Benjamin

1. **Baseline changes.** If a reviewing agent may approve changed screenshots, an unintended visual change can merge with no human seeing it. If you approve them, every visual PR waits for you. Middle path: agents approve, you get a periodic before/after digest.
2. **Hosted visual service.** Staying on Playwright alone costs nothing but gives no review interface. A hosted free tier (5,000 screenshots/month) adds one, and a third party that receives screenshots of the app.
3. **"WCAG 2.2 AA" wording.** Automation covers a minority-to-half of issues. Either the standard is stated as "automated AA checks pass" or a manual audit per release is added.
4. **Reduced motion.** It is AAA, not AA. Making it mandatory costs a few hours now and one rule on every future animation.
5. **File-level granularity.** With bulk suppressions, an agent adding one violation to a legacy file sees all of that file's violations for that rule and will likely fix them all: debt shrinks faster, PRs grow larger.
6. **Starting theme.** Adopting an MUI template theme gives a credible look in a day, and a look shared with many other sites; generating a palette from a brand colour takes longer and is distinct.

## Sources

- [S1] https://www.designtokens.org/tr/drafts/format/
- [S2] https://styledictionary.com/info/dtcg/
- [S3] https://mui.com/material-ui/customization/css-theme-variables/overview/
- [S4] https://mui.com/material-ui/customization/transitions/
- [S5] https://atlassian.design/components/eslint-plugin-design-system/ensure-design-token-usage/usage
- [S6] https://eslint.org/docs/latest/rules/no-restricted-syntax
- [S7] https://stylelint.io/user-guide/rules/declaration-property-value-disallowed-list/
- [S8] https://github.com/AndyOGo/stylelint-declaration-strict-value
- [S9] https://github.com/dequelabs/axe-core
- [S10] https://www.deque.com/blog/automated-testing-study-identifies-57-percent-of-digital-accessibility-issues/
- [S11] https://alphagov.github.io/accessibility-tool-audit/
- [S12] https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/
- [S13] https://github.com/dequelabs/axe-core/blob/develop/doc/rule-descriptions.md
- [S14] https://playwright.dev/docs/accessibility-testing
- [S15] https://github.com/jsx-eslint/eslint-plugin-jsx-a11y
- [S16] https://playwright.dev/docs/test-snapshots
- [S17] https://playwright.dev/docs/api/class-pageassertions
- [S18] https://playwright.dev/docs/emulation
- [S19] https://www.chromatic.com/pricing and https://www.chromatic.com/docs/billing/
- [S20] https://argos-ci.com/pricing and https://github.com/argos-ci/argos
- [S21] https://github.com/lost-pixel/lost-pixel
- [S22] https://github.com/reg-viz/reg-suit
- [S23] https://github.com/ai/size-limit
- [S24] https://github.com/GoogleChrome/lighthouse-ci/blob/main/docs/configuration.md
- [S25] https://github.com/GoogleChrome/lighthouse/blob/main/docs/variability.md
- [S26] https://web.dev/articles/vitals
- [S27] https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html
- [S28] https://playwright.dev/docs/api/class-page#page-emulate-media
- [S29] https://eslint.org/docs/latest/use/suppressions
- [S30] https://eslint.org/blog/2025/04/introducing-bulk-suppressions/
- [S31] https://phenomnomnominal.github.io/betterer/docs/introduction
- [S32] https://github.com/paleite/eslint-plugin-diff
- [S33] https://mui.com/material-ui/getting-started/templates/
- [S34] https://raw.githubusercontent.com/mui/material-ui/master/LICENSE
- [S35] https://github.com/material-foundation/material-color-utilities
- [S36] https://www.radix-ui.com/themes/docs/theme/overview
- [S37] https://raw.githubusercontent.com/radix-ui/themes/main/LICENSE
- [S38] https://ui.shadcn.com/docs/theming
- [S39] https://raw.githubusercontent.com/shadcn-ui/ui/main/LICENSE.md
- [S40] https://github.com/argyleink/open-props
- [S41] https://raw.githubusercontent.com/argyleink/open-props/main/LICENSE
