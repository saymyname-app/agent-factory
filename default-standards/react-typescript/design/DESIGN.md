# Design standards — React and TypeScript

Default Standards version 1. This proposed design becomes the project's own
standard when adopted at its first interface work. Its palette is a starting
point to judge on real screens, not an approval of the app's taste.

| Family | Guaranteed | Benefit | Cost | Configuration |
| --- | --- | --- | --- | --- |
| Theme | Colours, type size, spacing, radius and duration come from one theme; no literals outside it | Consistent screens and easy changes | Tokens must be chosen and maintained | `src/theme/tokens.css`, `bin/check-design-css`, `bin/check-design-source.mjs` |
| Contrast | Text and action contrast pass in light and dark modes | Readable in both modes | Palette edits may need adjustment | `bin/check-design-tokens` |
| Accessibility | Common static JSX errors are refused; keyboard and focus need screen evaluation | Fewer inaccessible controls | Screen review remains required | `bin/check-design-source.mjs` |
| Text | Direct JSX literals and common label attributes are refused; a rendered pseudo-language check covers indirect text | Another language can be added | The static check alone cannot prove translated text | `bin/check-design-source.mjs`, rendered bench |
| Motion | The theme turns duration off for reduced-motion preference | Less unwanted motion | Custom motion needs its own screen check | `src/theme/tokens.css` |

## Rules cited by the reviewer

- The visual hierarchy makes the primary action and the current state clear on each screen.
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
