# Design standards — React and TypeScript

Default Standards version 4. This proposed design becomes the project's own
standard when adopted at its first interface work. Its palette is a starting
point to judge on real screens, not an approval of the app's taste.

| Family | Guaranteed | Benefit | Cost | Configuration |
| --- | --- | --- | --- | --- |
| Theme | Colours, type size, spacing, radius and duration come from one theme; no literals outside it | Consistent screens and easy changes | Tokens must be chosen and maintained | `src/theme/tokens.css`, `bin/check-design-css`, `bin/check-design-source.mjs` |
| Contrast | Text and action contrast pass in light and dark modes | Readable in both modes | Palette edits may need adjustment | `bin/check-design-tokens` |
| Accessibility | Common static JSX errors are refused; keyboard and focus need screen evaluation | Fewer inaccessible controls | Screen review remains required | `bin/check-design-source.mjs` |
| Text | Direct JSX literals and common label attributes are refused; a rendered pseudo-language check covers indirect text | Another language can be added | The static check alone cannot prove translated text | `bin/check-design-source.mjs`, rendered bench |
| Motion | The theme turns duration off for reduced-motion preference | Less unwanted motion | Custom motion needs its own screen check | `src/theme/tokens.css` |
| Rendered bench | 390/1440 px, light/dark captures, axe, reduced motion and pseudo-language | Visual and user-facing regressions fail a PR | First baselines and page routes must be recorded | `design-bench/bench.spec.mjs` |
| Bundle | Built JS/CSS assets stay under a byte budget | Size growth is visible | Set a measured initial limit | `design-bench/check-bundle.mjs` |

## Rules cited by the reviewer

- The visual hierarchy makes the primary action and the current state clear on each screen.
- A changed visual reference matches the visual intent declared by its ticket.
- Focus order follows the task order, focus remains visible, and every task is operable by keyboard.
- An image description communicates its purpose rather than repeating its filename.
- Text uses short, direct sentences and identifies the action a person can take.
- Product-defined server and database messages are codes translated at the edge; user-entered text is never translated.

## Tone examples to validate once per app

| Write | Avoid |
| --- | --- |
| “Enregistrer les modifications” | “Soumettre” |
| “Impossible d’enregistrer. Réessayez.” | “Une erreur est survenue.” |

These are proposed examples, not Benjamin's validated words.

## Choices

- Palette, typography, density and tone: recommended starting theme — par défaut, non confirmée. Present on real screens at the first interface work.
- Component library: no library selected — par défaut, non confirmée.

## Derogations

None.

## Rendered bench setup

At the first interface work, set `design-bench/bench.config.json` to the real routes and a measured bundle budget (current built bytes plus an explicit margin). A screen entry has an `id`, a route `path`, and a `readySelector` visible only after the app has rendered its content. The app supplies `npm run build` and `npm run preview`, or sets `DESIGN_PREVIEW_COMMAND` in the copied workflow. Its `?lang=zz` route renders every product-defined string as `[zz:key]`; user-entered content carries `data-user-content` and stays unchanged. The browser test waits for each screen, runs at 390 and 1440 px in light and dark mode, scans rendered accessibility violations, compares committed captures, checks CSS and Web Animations motion after reload under reduced motion, then checks pseudo-language text. Initial captures are generated in the pinned Playwright 1.64.0 Noble image and committed with the first interface PR. A new capture is an initial reference. A changed or deleted reference requires a fresh entry in
`design-bench/visual-changes.json`: the PNG path, the ticket ID, and the intended visual change.
The PR and merge queue compare this declaration to the base commit and refuse an undeclared
reference change. The Evaluator compares the before/after render to the ticket intent;
the Acceptance Session shows the before/after summary.
