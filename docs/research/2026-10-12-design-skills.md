# Design skills for a factory that ships web UI without a designer

Research date: 2026-10-12. Times are Europe/Paris. Marks: **[V]** verified from the
primary source (repository, raw file, GitHub API, official docs) on that date;
**[I]** inferred by the researcher. Nothing was installed or executed.

## Verdict

| Skill | Source | Licence | Retain? | For which role | Why |
|---|---|---|---|---|---|
| `/impeccable` | `pbakaus/impeccable` | Apache-2.0 | Yes, core | Author (`polish`, `harden`, `layout`), reviewer (`audit`, `critique`, `detect`) | Only one with a deterministic, model-free detector and a project design file (`DESIGN.md`) |
| `/apple-design` | most likely `emilkowalski/skills` (`apple-design`) | MIT | Yes, narrow | Author and reviewer, motion and gesture work only | Concrete motion physics; no theme opinion, so no conflict with MUI |
| `/taste` | most likely `Leonxlnx/taste-skill` (`design-taste-frontend`) | MIT | Prototype only | Prototype session, marketing pages | States itself it is not for product UI; prescribes Tailwind |
| `/ultra-taste` | **not identified** | n/a | No decision possible | n/a | No public skill of that name found |
| `frontend-design` | `anthropics/skills` | Apache-2.0 | Optional | Prototype session, greenfield | Short brief, invents fresh tokens per task |
| `review-animations` and siblings | `emilkowalski/skills` | MIT | Yes, with `apple-design` | Reviewer | Same repository, review-shaped |
| `web-design-guidelines` | `vercel-labs/agent-skills` | none declared | No (as is) | n/a | No licence; fetches its rules from the network at run time |
| `ui-ux-pro-max` | `nextlevelbuilder/ui-ux-pro-max-skill` | MIT | No | n/a | Needs Python scripts; generates its own design system; MUI not listed |

## `/impeccable`

- Origin: Paul Bakaus, <https://github.com/pbakaus/impeccable>, `Apache-2.0`, created 2025-11-16, last push 2026-10-12 19:13, about 80k stars, tags of the form `skill-v4.5.2` **[V, GitHub API]**. README states it started from Anthropic's `frontend-design` **[V]**.
- Contents: one skill, 24 commands (`craft`, `init`, `document`, `extract`, `shape`, `critique`, `audit`, `polish`, `bolder`, `quieter`, `distill`, `harden`, `onboard`, `animate`, `colorize`, `typeset`, `layout`, `delight`, `overdrive`, `clarify`, `adapt`, `optimize`, `live`, `generate`); `reference/` and `scripts/` folders; a CLI (`npx impeccable detect|install|update|telemetry`); hooks; a browser extension **[V, README]**. The source file is `skill/SKILL.src.md`; installable copies are built per harness (`dist/claude-code/.claude`, `dist/agents/.agents`) **[V]**.
- Invocation: `/impeccable <command>` in Claude Code; `$impeccable` or `/skills` in Codex, installed under `.agents/skills/` plus `.codex/hooks.json` **[V]**. Both harnesses supported **[V]**.
- Verifiable gain: `detect` runs 59 deterministic rules with no model and no API key, `--json` output, exit codes `0` clean, `2` findings, `1` scan failure **[V]**. This is a gate a factory can run in CI.
- Project design file: `init` writes `PRODUCT.md`; `document` generates `DESIGN.md` from existing code; `extract` pulls tokens and components; state lives in `.impeccable/` **[V]**.
- Limits: (1) telemetry is on by default and each "new design" sends a request to `impeccable.style`; opt-out via `DO_NOT_TRACK=1`, `IMPECCABLE_NO_TELEMETRY=1` or `"telemetry": false`, and the request is still sent when opted out **[V]**. (2) It installs hooks and executable launchers, so "copied unchanged" means vendoring code, not only prose **[V]**. (3) `live` runs a `package.json` script in a shell **[V]**. (4) Very active repository: high drift between pins **[I]**. (5) The author's stance on MUI specifically was not found **[not verified]**.

## `/apple-design`

- Identification: the exact name `apple-design` exists in <https://github.com/emilkowalski/skills> (`skills/apple-design/SKILL.md`) **[V]**. Other candidates with close names: `dickwu/apple-design-skill` (HIG-based reviewer, README says it answers to `/apple-design`, per search result **[not verified at source]**), `raintree-technology/apple-hig-skills`, `ebuntario/apple-hig`. The Kowalski one is the likeliest because it targets the web **[I]**.
- Origin: Emil Kowalski, `MIT`, created 2026-03-16, last push 2026-10-11 15:58, about 46k stars, **no tags** **[V, GitHub API]**.
- Contents: a single `SKILL.md`, about 3,000 words, 17 sections: response on pointer-down, 1:1 drag, interruptible animation, springs, velocity handoff, momentum projection, rubber-banding, `backdrop-filter` materials, reduced motion, typography; no bundled files or scripts **[V]**. Examples use Motion (Framer Motion) and plain CSS **[V]**.
- Moment: description says "building or reviewing" **[V]**. The repository holds 14 other skills, among them `review-animations`, `improve-animations`, `animation-performance`, `break-ui`, `prototype` **[V]**.
- Limits: says nothing about project tokens or theme **[V]**; rules are judgment, not machine-checkable **[I]**; Apple translucency can clash with a Material-styled theme **[I]**. Works in Codex as a plain `SKILL.md` **[I]**; the README names no harness **[V]**.

## `/taste`

- Identification: most likely `design-taste-frontend` in <https://github.com/Leonxlnx/taste-skill> (Claude Code plugin namespace `taste-skill:`) **[I]**. The exact command `/taste` was not found in that repository **[V]**.
- Origin: Leonxlnx, `MIT`, created 2026-02-19, last push 2026-10-12 01:06, about 95k stars, **no tags** **[V, GitHub API]**.
- Contents: 13 skill folders (default v2 "experimental", v1, `gpt-taste`, `redesign-existing-projects`, `high-end-visual-design`, `minimalist-ui`, `industrial-brutalist-ui`, `full-output-enforcement`, image-generation ones) **[V]**. The main `SKILL.md` is about 10,000 words, with three dials (`DESIGN_VARIANCE: 8`, `MOTION_INTENSITY: 6`, `VISUAL_DENSITY: 4`) and a mandatory pre-flight checklist **[V]**.
- Limits: the file states "Not dashboards, not data tables, not multi-step product UI." **[V]**. It defaults to Tailwind v4, Motion, GSAP, bans Inter as default font; MUI is never named **[V]**. It asks to check `package.json` before importing and holds "one system per project" **[V]**, but in a MUI application it pulls toward a second styling system **[I]**. About 10,000 words loaded per use **[I]**.
- Harnesses: Claude Code plugin and `npx skills add`; `gpt-taste` is the variant written for Codex/GPT **[V]**.

## `/ultra-taste`

Not identified. GitHub repository search and web search returned no skill of that name **[V]**. Candidates, none confirmed: `gpt-taste` (the stricter variant of taste-skill), `/impeccable overdrive`, a locally renamed or private skill, or a paid/private pack. Benjamin's source for the name is needed.

## `frontend-design` (Anthropic)

<https://github.com/anthropics/skills/tree/main/skills/frontend-design>, `LICENSE.txt` is Apache License 2.0, last change 2026-09-03 **[V]**. Two files: `SKILL.md` (about 1,300 words) and the licence **[V]**. It frames the agent as design lead, plans a fresh token set per brief, lists AI tells to avoid, sets an accessibility floor **[V]**. It does not read an existing design system **[V]**: fine for greenfield, redundant next to impeccable **[I]**.

## Others looked at

- `web-design-guidelines` (<https://github.com/vercel-labs/agent-skills>): review skill with `file:line` output, but GitHub reports no licence, and it fetches rules from `raw.githubusercontent.com/vercel-labs/web-interface-guidelines` at each run **[V]**: cannot be pinned by copying.
- `ui-ux-pro-max` (<https://github.com/nextlevelbuilder/ui-ux-pro-max-skill>, `MIT`, about 135k stars): CSV data plus Python search scripts, writes `design-system/<project>/MASTER.md`; MUI not in its stack list **[V]**.

## How we would use them

- Roles **[I]**: author gets `impeccable` (build commands) and, on motion tickets only, `apple-design`. Reviewer gets `impeccable audit`/`critique`, `review-animations`, and the `detect` exit code as a hard gate. Prototype sessions get `frontend-design` or taste-skill, where output is thrown away.
- Theme and tokens **[I]**: none of these skills reads an MUI theme natively. The per-project theme stays the authority; run `impeccable document` once to derive `DESIGN.md` from the existing code, review it by hand, and add one factory rule in the project instructions: "tokens come from the theme; a skill never introduces a font, colour or styling library". Taste-skill and `frontend-design` conflict with a fixed theme by design (they invent one).
- Copy and pin **[I]**: impeccable has tags, so pin `skill-vX.Y.Z` and copy the built skill folder; decide whether hooks and CLI are vendored or only the prose. `emilkowalski/skills` and `Leonxlnx/taste-skill` have no tags: pin a commit SHA. Codex reads `.agents/skills` (repository) and `$HOME/.agents/skills` (user), invoked by `$name` or implicitly **[V, OpenAI docs]**; the same folder format serves Claude Code under `.claude/skills`.
- Cheapest first slice **[I]**: `npx impeccable detect --json` as a reviewer gate on one project, telemetry disabled, before adopting any authoring skill.

## Open questions for Benjamin

1. Where did `/ultra-taste` and `/taste` come from (video, post, pack)? Without it `/ultra-taste` stays unidentified.
2. Is `/apple-design` the Kowalski web-motion skill, or an Apple HIG reviewer?
3. Impeccable contacts `impeccable.style` and ships hooks and a CLI: accept vendored executable code and that request, or prose only?
4. Is MUI the lasting choice? Taste-skill and several others assume Tailwind.
5. Should a design finding block a merge (detector exit code) or only inform?

## Sources

- <https://github.com/pbakaus/impeccable>, its `README.md`, `skill/` tree, GitHub API `repos/pbakaus/impeccable` and `/tags`
- <https://github.com/emilkowalski/skills>, `skills/apple-design/SKILL.md` (raw), GitHub API
- <https://github.com/Leonxlnx/taste-skill>, `skills/taste-skill/SKILL.md` (raw), GitHub API
- <https://github.com/anthropics/skills/tree/main/skills/frontend-design> (`SKILL.md`, `LICENSE.txt`, commit history via API)
- <https://github.com/vercel-labs/agent-skills> (`skills/web-design-guidelines/SKILL.md`), GitHub API
- <https://github.com/nextlevelbuilder/ui-ux-pro-max-skill> (`README.md`), GitHub API
- OpenAI Codex skills documentation: <https://learn.chatgpt.com/docs/build-skills> (redirect from `developers.openai.com/codex/skills`)
- Secondary, used only to locate candidates: <https://open-design.ai/skills/apple-design/>, <https://github.com/dickwu/apple-design-skill>
