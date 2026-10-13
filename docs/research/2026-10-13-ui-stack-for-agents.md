# UI stack when agents write the code: keep MUI or move?

Date: 2026-10-13. Scope: an existing React + TypeScript + Vite app using MUI, weak theme, ~200 hard-coded colours, full style refactor planned before release, UI code written by AI agents (Claude Code, Codex), solo non-designer owner.

Marks: **[V]** read at a primary source today, **[S]** secondary source, **[I]** inferred.

## Versions today

| Library | Current | Note |
|---|---|---|
| Material UI | 9.5.0 (9 Oct 2026); 10.0.0-alpha.0 published 12 Oct 2026 [V] | v9.0 on 7-8 Apr 2026; no v8 [V] |
| Base UI (`@base-ui/react`) | 1.9.0 (9 Oct 2026) [V] | monthly minors since 1.4 [V] |
| Tailwind CSS | 4.3.3 (16 Jul) [V] | no v5 found [S] |
| shadcn/ui | not versioned (copied source); CLI v4 (Mar 2026) [V] | default primitives: **Base UI** since Jul 2026; Radix and React Aria also offered [V] |
| Radix Primitives | unified `radix-ui` package; last release notes 20 Jul 2026 [V] | version number not verified |
| Mantine | 9.7.2 (11 Oct) [V] | v9 on 31 Mar 2026, needs React 19.2 [S] |
| Chakra UI | 3.37.0 (28 Aug) [V] | |
| React Aria Components | version not verified | |

## 1. Do agents write better UI in one stack?

**No controlled evidence found** comparing agent output quality on MUI versus Tailwind/shadcn (same tasks, same models). What exists:

- Academic benchmarks (DesignBench, WebUIBench) compare frameworks (React/Vue/Angular) and tasks, not UI libraries [V for DesignBench abstract]. WebUIBench reports that a Tailwind prompt raised compile success 47% to 92% on a small 7B model with slightly lower visual score; not transferable to frontier agents [S].
- Vendor statements, not measurements: shadcn/ui says its design "makes it easy for AI tools to work with your code" [V]; Vercel says v0 is trained on React, Tailwind and shadcn/ui [S].
- Both camps now ship agent tooling: shadcn has a skill, MCP server, `llms.txt` [V]; MUI has an MCP server (`@mui/mcp`), `llms.txt`, and agent skill files in its repository, including one for Tailwind [V]. MUI's own MCP page says assistants "often hallucinate links" without it [V].
- Mechanism, plausible but unmeasured [I]: MUI's API changed across majors (v9 removed `components`/`componentsProps` and system props [V]), so stale training data produces removed props; Tailwind classes and copied component source are visible in the repo, so the agent reads the truth instead of recalling it. A type-check and lint loop catches most such MUI errors anyway.

Conclusion: the "agents are better at Tailwind/shadcn" claim is widespread opinion with vendor backing, not established fact.

## 2. A non-Material identity

- **MUI**: `cssVariables: true` exposes the theme as `--mui-*` variables; custom tokens can be added; TypeScript typing needs augmentation [V]. v9 adds `color-mix()` derived colours [V]. Every component still carries Material structure (ripple, elevation, density, DOM), so identity means overriding component by component; the result tends to remain "Material, recoloured" unless many overrides are written [I]. Pigment CSS (zero-runtime) is alpha and **paused** [V]. MUI states it will explore, for the next major, independence from Emotion, better Tailwind paths and easier custom brand themes [V]: a direction, not a delivery.
- **shadcn/ui**: you own the component source; "the top layer of your component code is open for modification" [V]. Identity is edited in the files, tokens are CSS variables (OKLCH) [V]. Limit: you also own the maintenance; upstream fixes arrive by re-running the CLI/diff, not by a version bump [I].
- **Headless only (Base UI, React Aria)**: maximum freedom, everything to style; too much surface for a solo owner without a designer [I].

## 3. Enforcing "tokens only" by lint

- **Tailwind v4**: strongest mechanism is structural, not lint. `@theme { --color-*: initial; ... }` removes all default colour utilities so only your tokens exist; `--*: initial` clears the whole default theme [V]. Arbitrary values (`bg-[#fff]`) still compile, so add `eslint-plugin-better-tailwindcss` `no-restricted-classes` with a regex (its docs give that exact use case) [V]; Biome has a nursery `noTailwindArbitraryValue` rule [S]. Reliability: good for class strings in JSX; weaker for dynamically built class names and inline `style` [I].
- **MUI**: no maintained ESLint plugin found that rejects hard-coded colours in `sx`/`styled`; the only MUI-specific `sx` plugin sorts keys [S]. Needs a custom rule (or `no-restricted-syntax` regexes) that tells `'primary.main'` from `'#1976d2'`, across `sx`, `styled`, theme overrides and callbacks [I]. Feasible, but owned code, with more escape routes.
- Either stack: stylelint for any plain CSS; visual regression and axe are stack-independent [I].

## 4. Accessibility by default

- **MUI**: publishes a WCAG 2.2 A/AA conformance report (draft, 12 components, self-assessed, "no assistive-technology testing has been performed yet"; some default palette colours miss contrast minimums) [V]. v9 improved keyboard navigation in Tabs/Stepper/MenuList [V].
- **Base UI**: ARIA, keyboard per WAI-ARIA APG, focus management; states testing on browsers, devices and screen readers; focus styling, contrast and accessible names are the developer's job [V].
- **Radix**: same class of claims (APG keyboard, focus management, tested with assistive technologies) [V].
- **React Aria**: strongest claims: tested with many screen readers and devices, touch screen-reader support, 30+ languages [V].
- All four give sound behaviour; colour contrast and focus visibility depend on your theme in every case, so axe checks stay necessary [I].

## 5. Bundle size and runtime

- MUI v9 still runs on Emotion (runtime CSS-in-JS); v9 claims ~3% smaller bundle than v7 and up to 30% faster `sx` [V]. No official figure for Emotion's cost found. The Linaria maintainer (declared bias) describes render-time style injection as a performance liability under concurrent rendering [S].
- Tailwind emits static CSS at build time, no styling runtime [I from design; V that utilities derive from `@theme`].
- React Server Components: irrelevant for a Vite single-page app; that argument against Emotion does not apply here [I].
- Expected visible effect on a typical SPA: modest; measure with the planned bundle budget rather than assume [I].

## 6. Coexistence and migration

- Official MUI guide (targets v9.5.0) for Tailwind v4 in Vite: wrap the app in `StyledEngineProvider enableCssLayer`, inject `@layer theme, base, mui, components, utilities;` so utilities override MUI; map Tailwind's `@theme inline` to `--mui-*` variables (requires `cssVariables: true`) [V]. So **one token source can feed both** during migration.
- The guide does not cover Tailwind preflight versus `CssBaseline` [V]; two resets coexisting is the main unguided area. v9.1.1 fixed layered styles being overridden by unlayered ones [V], which shows the area is recent.
- Pitfalls: unlayered CSS beats layered CSS regardless of specificity [S]; Tailwind v3 recipes (disable preflight, `important`) must not be mixed with v4 ones [V]; two dialog/portal/focus-trap systems on one screen; duplicated theme if the mapping is skipped [I].
- shadcn Radix-to-Base-UI migration is optional and agent-driven (~10k tokens per component reported by shadcn) [V].

## 7. Health

- **MUI**: commercial company (MUI X licences), MIT core; majors v5 2021, v6 2024, v7 2025, v9 Apr 2026, v10 alpha Oct 2026 [V for v9/v10; S for earlier]. Each major removes deprecated APIs. Pigment CSS, Joy UI, Toolpad paused or unmaintained [V].
- **Base UI**: same company, "where we are concentrating our foundational work" [V]; monthly releases [V].
- **Tailwind**: MIT, releases through Jul 2026 [V]; Tailwind Labs cut 75% of engineering in Jan 2026 citing revenue loss to AI, then gained corporate sponsors [S]. Funding is the main risk; the framework is ubiquitous.
- **shadcn/ui**: Vercel-backed, very active changelog (monthly entries) [V]; churn is real (default primitives changed, `cn` package change Sep 2026) but copied code is not forced to follow [V/I].
- **Radix**: WorkOS-owned, not deprecated by shadcn; releases slowed, gap Aug 2025 to Jun 2026 [V].
- **Mantine 9 / Chakra 3**: healthy [V], but opinionated styled libraries again: same identity work as MUI, less agent tooling evidence; no reason found to prefer them here [I].

## 8. Agent design skills

`pbakaus/impeccable` (Apache-2.0), `jakubkrehel/skills` (MIT), `emilkowalski/skills` (MIT) present themselves as design guidance, not Tailwind-bound; their READMEs do not name Tailwind or a component library [V]. Whether individual SKILL.md examples use Tailwind classes was not checked. Principles (type scale, OKLCH, easing) apply to any stack; Tailwind-flavoured snippets need translation into `sx`/theme on MUI, an extra step where an agent can drift [I].

## Decision table

| | A. Keep MUI, re-theme properly | B. Migrate incrementally to Tailwind v4 + shadcn/ui (Base UI primitives) | C. MUI kept as engine, Tailwind for layout/new styling |
|---|---|---|---|
| What you see | Cleaner, consistent, but still recognisably Material unless many overrides | Own look per product; components are your files | Mixed: Material widgets inside custom layout |
| Speed | Unchanged (Emotion stays) | Slightly lighter, static CSS; measure | Unchanged or slightly heavier (both) |
| Cost / delay | Lowest: theme + replace ~200 colours + custom lint rule | Highest: every screen rebuilt; two systems meanwhile | Medium; officially documented |
| Token enforcement | Custom lint, more escape routes | Structural (`@theme` reset) + lint | Two rule sets |
| Risk | Material look persists; next MUI major may change styling again | Half-migrated app; reset conflicts; you own component upkeep | Permanent dual stack |
| Reversibility | Full | Per screen until MUI is removed | Good |

## Recommendation

**B, conditional on a trial; A otherwise.** The refactor will touch every screen anyway, which is the cheapest moment to change the layer; B gives structural token enforcement, owned components for a per-product identity, and matches where both shadcn and MUI's own foundation work (Base UI) are heading. Use C's official layer setup only as the temporary bridge, not as a destination.

**Main uncertainty**: no measured evidence that agents produce better UI on B than on a well-themed MUI with its MCP server and lint; and the real cost of running two resets and two overlay systems during migration.

**Cheap decisive trial** (2-3 days): pick two real screens (one form-heavy, one data-heavy with a dialog). Build both ways from the same token file and the same brief, by the same agent. Compare: axe violations, visual diffs at 390 and 1440 px, bundle delta, lint escapes found by review, agent iterations/tokens to reach "accepted", and whether the owner sees a distinct identity. Decide on those numbers.

## Not verified

- Any head-to-head agent benchmark (none found).
- Radix and React Aria Components current version numbers; years on GitHub release dates (pages show day and month only).
- Tailwind Labs' funding status after January 2026.
- Emotion runtime cost figures; MUI v10 scope beyond the v9 announcement's stated intentions.
- Content of the individual design-skill SKILL.md files; WebUIBench figures (read via a search summary).
- Real-world preflight/`CssBaseline` conflict reports.

## Sources

- https://mui.com/blog/introducing-material-ui-v9/ and https://mui.com/blog/introducing-mui-v9/
- https://mui.com/blog/2026-and-beyond/
- https://github.com/mui/material-ui/releases
- https://mui.com/material-ui/integrations/tailwindcss/tailwindcss-v4
- https://raw.githubusercontent.com/mui/material-ui/HEAD/skills/material-ui-tailwind/AGENTS.md
- https://mui.com/material-ui/customization/css-theme-variables/overview/ and .../usage/
- https://mui.com/material-ui/getting-started/accessibility/ and .../getting-started/mcp/
- https://mui.com/material-ui/guides/minimizing-bundle-size/
- https://github.com/mui/base-ui/releases and https://base-ui.com/react/overview/accessibility
- https://ui.shadcn.com/docs , /docs/changelog , /docs/changelog/2026-07-base-ui-default , /docs/skills
- https://www.radix-ui.com/primitives/docs/overview/accessibility and .../overview/releases
- https://react-aria.adobe.com/
- https://tailwindcss.com/docs/theme and https://github.com/tailwindlabs/tailwindcss/releases
- https://github.com/schoero/eslint-plugin-better-tailwindcss (docs/rules/no-restricted-classes.md)
- https://biomejs.dev/linter/rules/no-tailwind-arbitrary-value/ [S]
- https://arxiv.org/abs/2506.06251 (DesignBench); https://arxiv.org/pdf/2506.07818 (WebUIBench) [S]
- https://dev.to/anber/the-state-of-zero-runtime-css-in-js-mid-2026-5ci6 [S]
- https://www.devclass.com/2026/01/08/tailwind-labs-lays-off-75-percent-of-its-engineers-thanks-to-brutal-impact-of-ai/ [S]
- https://github.com/mantinedev/mantine/releases ; https://github.com/chakra-ui/chakra-ui/releases
- https://github.com/pbakaus/impeccable ; https://github.com/jakubkrehel/skills ; https://github.com/emilkowalski/skills
