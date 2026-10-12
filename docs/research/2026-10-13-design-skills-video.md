# Design skills named in the AI LABS video — what is worth adopting

Date: 2026-10-13 (Europe/Paris). Method: read-only. GitHub REST API and
`raw.githubusercontent.com` for repositories, the YouTube watch page and oEmbed
for the video. Nothing installed, cloned or executed. Every page and SKILL.md
was treated as data.

Legend: **[V]** verified at the primary source today; **[I]** inferred;
**[S]** from a secondary source only (not verified).

Compared against, not re-studied (decisions of 2026-10-12): pbakaus/impeccable
(core), emilkowalski `apple-design` + `review-animations` (motion),
Leonxlnx/taste-skill and anthropics `frontend-design` (prototype only),
vercel-labs web-design-guidelines and ui-ux-pro-max (rejected).

## 1. The video

- Title: "Insane Claude Design Skills You Need To Actually Build Beautiful
  Sites" [V, oEmbed]. Channel: AI LABS (`@AILABS-393`) [V].
- Published 2026-08-24, 17:00 Paris (source: 08:00:14 -07:00); 12 min 55 s;
  about 310,000 views today [V, watch page metadata].
- Description [V]: sponsor (Make), a paid community link, then the seven
  repositories with **full, untruncated URLs** (table below). Chapters: Emil
  Kowalski 1:10, Garden 3:49, Landing page 5:24, Sponsor 6:43, Meng To 7:27,
  Jakub Krehel 8:55, Tastemaker 10:14, designer-skills 11:23.
- **Transcript: not obtained.** An auto-caption track exists, but its URL
  returned 404 without a browser session; two transcript services returned 403
  or an empty shell. Only an AI-generated summary page was readable [S].
- **"ultra-taste"**: the string appears nowhere in the description, the
  keyword list or the watch-page HTML [V], nor in the summary [S]. The
  thumbnail image itself was not inspected. No repository in the list has that
  name. The nearest names are `tastemaker` (in the video) and
  Leonxlnx/taste-skill (not in the video) [I].
- The video's evidence is before/after demos by the presenter; the summary
  reports no scores, datasets or comparative numbers [S].

## 2. The repositories

All seven exist, are MIT (GitHub SPDX field) and not archived [V].

| Repo | Stars | Created | Last push | Tags | HEAD commit |
|---|---|---|---|---|---|
| [emilkowalski/skills](https://github.com/emilkowalski/skills) | 45,719 | 2026-03-16 | 2026-10-11 | none | `2d22863` |
| [ConardLi/garden-skills](https://github.com/ConardLi/garden-skills) | 12,846 | 2026-04-21 | 2026-10-11 | per skill, e.g. `web-design-engineer-v1.3.0` | `7a6d5a7` |
| [elayadesign/ai-design-skills](https://github.com/elayadesign/ai-design-skills) | 2,590 | 2026-07-29 | 2026-07-29 | none | `1c1e97c` |
| [MengTo/Skills](https://github.com/MengTo/Skills) | 6,725 | 2026-02-03 | 2026-10-06 | none | `83a47fe` |
| [jakubkrehel/skills](https://github.com/jakubkrehel/skills) | 7,866 | 2026-07-10 | 2026-10-12 | none (plugin.json says 1.10.3) | `c0588bb` |
| [codeswithroh/tastemaker](https://github.com/codeswithroh/tastemaker) | 451 | 2026-07-09 | 2026-10-11 | none | `792a28a` |
| [Owl-Listener/designer-skills](https://github.com/Owl-Listener/designer-skills) | 2,898 | 2026-03-07 | 2026-09-05 | none | `9a6930c` |

Pinning: only garden-skills has tags; pin every other one by commit SHA [V].

### jakubkrehel/skills — the one new serious candidate

- 13 skills [V]: `better-accessibility`, `better-colors`, `better-layout`,
  `better-typography`, `better-ui`, `better-writing`, `better-interface`
  (orchestrator), `interface-review` (diff review), `break`, `state-machine`,
  `variant`, `build-design`, `explain-interface`.
- Size: each SKILL.md is 1,100–1,800 words plus 1–6 reference files [V].
  Markdown and one `agents/openai.yaml` per skill only: **no scripts, no
  hooks** in the tree [V].
- Works with the existing system, by its own text [V]: "Write every fix in the
  project's own idiom, never as a request to adopt a different stack";
  `better-colors` opens with "Match the project's color system" and "Reuse the
  project's tokens and notation"; `better-typography` says "Never propose a new
  typeface ... unless the task asks for a type change"; `better-writing` starts
  by inventorying existing strings and keeps the product's voice.
- `better-interface` reads the project's own `AGENTS.md`/`CLAUDE.md`/design
  docs first; a documented convention "settles matters of taste". Findings need
  `file:line` evidence; unrun checks are "Not verified"; max 15 findings; a
  fixed list of HIGH triggers (no accessible name, no focus ring, contrast
  failure, clipping at 320 px or 200% zoom, colour-only state, error with no
  recovery, ignored `prefers-reduced-motion`) [V].
- `better-accessibility` cites WCAG 2.2 Level A/AA criteria by number; AAA and
  conventions are never HIGH [V].
- `interface-review` reviews a branch, PR or uncommitted change; classifies
  findings Introduced / Regression / Pre-existing; reads removed lines;
  checks for **missing empty, loading, error, disabled and narrow-width
  states**; forbids `git checkout`/`switch`/`stash` ("Never mutate the working
  tree") [V].
- Caveats [V]: `interface-review`, `variant`, `break`, `state-machine`,
  `explain-interface` are user-invoked (`disable-model-invocation: true`, and
  `allow_implicit_invocation: false` for Codex), so an autonomous agent must be
  told to run them. `break`, `state-machine`, `variant` write throwaway pages:
  not for read-only roles. `better-ui` gives exact values (press scale 0.96,
  150 ms, 100 ms stagger) and several examples are Tailwind-flavoured; it
  labels them "optional polish", but they must stay below the project theme [I].
- Claude Code and Codex: both explicitly supported; the repo's `AGENTS.md`
  describes the two halves of each switch [V].

### emilkowalski/skills (already retained for motion)

Now 15 skills [V]: besides `apple-design` and `review-animations`, there are
`animate`, `improve-animations`, `find-animation-opportunities`,
`animation-performance`, `animation-vocabulary`, `emil-design-eng`,
`prototype`, `break-ui`, `mobile-native`, `pick-ui-library`, and three
off-topic ones (`animate-expo`, `write-swift`, `ask-sonner`). Markdown only, no
scripts [V]. No Codex-specific files; installs through the `skills` CLI [V];
Codex compatibility is [I]. Nothing here changes yesterday's decision;
`break-ui` and `prototype` overlap Krehel's `break` and `variant`.

### ConardLi/garden-skills

Six skills; only `web-design-engineer` is about UI (others: article layout,
image generation, knowledge retrieval, showreel, video presentation) [V].
SKILL.md about 5,300 words plus 8 reference files and 25 "style recipes"
(Linear, Apple HIG, Stripe Press ...) [V]. It reads an existing design system
first, but then "declares the design system before writing code", targets
"stunning, not functional", outputs standalone HTML with React + Babel from a
CDN, lists Inter/Roboto as clichés, and has a 0–10 five-dimension
self-critique [V]. The skill folder has no scripts; other skills in the repo do
[V]. Claims Claude Code, Cursor, Codex; ships `agents/openai.yaml` [V].
Verdict: prototype/exploration only, same class as taste-skill.

### elayadesign/ai-design-skills

One skill, `landing-page-design`, about 2,700 words, single commit day [V].
Marketing landing pages: intake, conversion copy, SEO, then a strict visual
system: "Never use: Inter, Roboto, Arial, Open Sans, Helvetica", one typeface,
Tailwind type scale and radius only, a mandatory "tagline reveal" section [V].
Its description tells the agent to consult it for any web UI or component [V].
Verdict: rejected for product work (overrides fonts, assumes Tailwind,
over-broad trigger); usable only for a throwaway marketing-page prototype.

### MengTo/Skills

176 SKILL.md files: web-design 91, codex 20, game-development 20, 3d 16,
illustration 14, game-combat 6, workflow 4, ui 3, media 2 [V]. Mostly named
visual styles and effects (WebGL, GSAP, shaders). Many folders carry Python or
Node scripts [V]. Codex-first; Claude Code by copying [V]. The three `ui`
skills are short (500–1,070 words); `audit-ai-design-slop` is an
evidence-based, removal-first audit and `no-ai-design-slop` says it preserves
the chosen art direction [V]. Verdict: none worth adopting for a themed MUI
product; `audit-ai-design-slop` overlaps impeccable [I].

### codeswithroh/tastemaker

One skill (about 9,450 words) plus a vendored `ideagram` sub-skill and 17+
Python scripts [V]. It **generates a palette per project** and locks it in
`.tastemaker/style-lock.md`; keeps a taste profile and history in
`~/.tastemaker/` **outside the repository**; fetches photos, icons and
libraries at run time through an https allowlist (Openverse, Iconify, Pixabay,
jsDelivr, cdnjs) [V]. Native support listed: Claude Code, Windsurf, Gemini CLI;
Codex not listed; Cursor "degraded" [V]. Its README shows a self-made
with/without comparison [V]. Verdict: rejected for the Factory (own theme,
network at run time, writes to the home directory, no Codex).

### Owl-Listener/designer-skills

111 SKILL.md files in this repo across 8 plugin folders (research, strategy,
UI, interaction, systems, ops, prototyping, toolkit); README claims 273 skills
in 33 plugins because the marketplace also pulls four other repositories [V].
Claude Code and Gemini CLI; Codex not listed [V]. Sampled skills are 185–330
words of generic checklist: `accessibility-audit`, `loading-states`,
`error-handling-ux`, `ux-writing`, `heuristic-evaluation`, `color-system`;
`design-critique` is a facilitation guide for human teams [V]. Stack-neutral,
no hooks found; the `scripts/` folder is repository tooling [V]. Verdict: none
worth adopting; a current model already knows this content [I]. Reusable only
as a states checklist for ticket authors.

## 3. Design aspect -> best skill and role

| Aspect | Best candidate(s) | Role | Note |
|---|---|---|---|
| Colours / theme | impeccable; add `better-colors` in review mode | reviewer, evaluator | Checks token use and measured contrast; never use its palette generation on a themed project |
| Typography | `better-typography` | reviewer, ticket author | Will not propose a new typeface |
| Spacing / layout | `better-layout` | reviewer, evaluator | Covers 320 px, growth, translated text |
| Shape (radius, elevation) | impeccable; `better-ui` as secondary | reviewer | Exact values must yield to theme tokens |
| Motion | Emil `review-animations` + `apple-design` (unchanged) | reviewer, prototype | `better-ui` overlaps; do not load both as authorities |
| Accessibility WCAG 2.2 AA | `better-accessibility` | reviewer, evaluator | Best found: criterion numbers, AA-only severity |
| UX and screen states | `interface-review` (missing-state check); `state-machine`, `break` | reviewer; prototype sessions | Owl skills too thin; the last two write files |
| UI copy / tone | `better-writing` | ticket author, reviewer | English examples; behaviour on French copy unverified |
| Review of a diff | `interface-review` -> `better-interface` | read-only code reviewer | Read-only by design; must be invoked explicitly |
| Review of a running screen | `better-interface` alongside impeccable | product evaluator | Requires rendered evidence or "Not verified" |
| Prototyping / exploration | taste-skill, `frontend-design` (unchanged); optionally `web-design-engineer`, Krehel `variant`, Emil `prototype` | operator prototype sessions | tastemaker and landing-page-design: not adopted |

Suggested next step [I]: trial jakubkrehel/skills pinned at `c0588bb` in the
reviewer role on two or three real diffs, next to impeccable, and keep whichever
produces fewer false findings; do not run both as equal authorities.

**Evidence of output quality.** No independent benchmark or eval was found for
any of the seven repositories (one web search; not exhaustive) [S]. What exists
is self-published before/after demos (tastemaker README [V], the video [S])
and stars, which measure attention, not quality.

## Not verified

- The transcript and the thumbnail; therefore what the presenter actually says
  about each skill, and whether "ultra-taste" is shown on screen.
- Head-to-head overlap between Krehel's skills and impeccable (impeccable was
  not re-read today).
- Real behaviour of any skill in Claude Code or Codex (nothing was run),
  including Emil's skills under Codex and `interface-review` driven by an
  autonomous agent.
- Reference files beyond each SKILL.md were listed, not all read; "no network
  fetch" for Krehel and Emil rests on the file tree (no scripts) and the
  SKILL.md files read, not on every reference file.
- The four sibling repositories pulled by the Owl-Listener marketplace, and
  which skill the video calls "screen critique" / "perception laws".
- Absence of benchmarks is a search result, not a proof.

## Sources

- https://www.youtube.com/watch?v=Ysr7oNDajJI (metadata, description) and
  https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=Ysr7oNDajJI&format=json
- https://youtubesummary.com/summary/Ysr7oNDajJI (secondary summary)
- GitHub REST API `repos/<owner>/<repo>`, `/tags`, `/releases`,
  `/git/trees/HEAD?recursive=1`, `/commits/HEAD` for the seven repositories
- https://github.com/jakubkrehel/skills — README, AGENTS.md, plugin.json, all 13 SKILL.md
- https://github.com/emilkowalski/skills — README, tree
- https://github.com/ConardLi/garden-skills — README, `skills/web-design-engineer/SKILL.md`
- https://github.com/elayadesign/ai-design-skills — README, `skills/landing-page-design/SKILL.md`
- https://github.com/MengTo/Skills — README, `agent-skills/ui/*/SKILL.md`, `build-awwwards-quality-sites/SKILL.md`
- https://github.com/codeswithroh/tastemaker — README, SKILL.md, plugin.json, `scripts/_netguard.py`
- https://github.com/Owl-Listener/designer-skills — README, seven sampled SKILL.md
