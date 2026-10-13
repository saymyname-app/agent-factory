# Impeccable in real use: field reports (2026-10-13)

Question: what do users of `pbakaus/impeccable` report in real use, as distinct from what its author publishes? Scope: skill + Rust engine + hooks, current tag `skill-v4.5.2`.

Method: GitHub issue tracker read through the GitHub API (388 issues: 57 open, 331 closed; Discussions are disabled), Hacker News via the Algolia API, blog posts via web fetch. Nothing installed or executed. Dates are UTC as given by the source.

Marks: **[V]** read at the source today, **[S]** secondary, **[I]** inferred.
Who: A = author/maintainer, T = third party.

## 1. Observed gain on UI quality

- **No independent eval or controlled comparison exists** against taste-skill, Anthropic frontend-design, emilkowalski/skills or jakubkrehel/skills. Every "comparison" found is a roundup without method. [V] Composio (vendor, 2026-05-05), claudeskills.info (directory, 2026-07-25, states no testing), ruoqijin.com (synthesis, 2026-06-26), viblo.asia (README-based).
- Best third-party hands-on account: Steven Sacks (T, 2026-05-29) calls it "excellent as a finisher but fairly ordinary from a blank page"; started first on another project it was only slightly better than `/frontend-design`. [V]
- Mejba Ahmed (T, sells consulting; 2026-04-30): `critique` scored his site 25/40, 32/40 after fixes; he judged the findings correct. Self-graded by the tool, so weak evidence. He loads it only in design sessions because of context cost. [V]
- HN launch thread (2026-01-12, 103 points, 64 comments) was mostly negative about the author's own before/after examples: several readers preferred "before"; one said the "after" ignored the brand guidelines. The author agreed the examples were rushed and removed them. [V] This predates v3/v4.
- Later HN comments (T) are mixed: helpful for consistency and accessibility (yokuze 2026-09-16; mstkllah 2026-07-26), but output "converges across skills" (mstkllah), still looks AI-made (sixtyj 2026-07-26), imposes someone else's taste (cat-whisperer 2026-09-10), misses plain eyebrow labels (bargainbin 2026-09-02). [V]
- Issue #149 (T, 2026-05-12): `typeset`/`layout` needed several runs and a checking subagent to catch basics such as a 12.5px font size. A second user confirmed the "fixed the rules, we're good" bias. [V]

## 2. Detector and hooks day to day

- **False positives are the largest issue class** (39 issues match "false positive"). Most are closed quickly. Strongest: #633 (T, 2026-08-22) — on a ~400-file React/Tailwind codebase, `gray-on-color` gave 39 findings, 39 false (opacity modifiers, ternaries). Others: #837 Tailwind spinner, #882 23 false findings from one closed `<details>` nav, #881 contrast 17.6:1 reported as 1.2:1 (open), #988 mixed `@media` blocks (open), #963 `cramped-padding` (open), #1001 `design-system-font` (open). [V]
- **False negatives are worse for a gate.** #884 (T, open, 2026-09-29): byte-identical markup yields fewer rules in `.jsx/.astro/.svelte/.vue` than in `.html`; a second user confirmed for `.tsx` with Tailwind arbitrary values (CLI `[]`, browser scan found issues). #795 (T, open): `detect` sends only `.html` to the DOM engine, so contrast/a11y rules never run on Vue/Svelte/Blade, exit 0; the hook path routes differently from `detect`. [V]
- **Agent looping:** #400 (T, 2026-07-22): Stop hook re-blocked a turn ~20 times on a false positive until Claude Code's safety cap. Fixed in 4.0.2 (A). [V]
- **Noise on non-design work:** #522 (T, 2026-08-06): Stop pass flagged a pre-existing font after a one-line import deletion. Maintainer reported a baseline-based fix (#754); issue closed 2026-09-10. #305: hook recreated `.impeccable/` on any edit (fixed in v4). The owner himself opened #497 "Make hooks denoise themselves" (2026-08-03). [V]
- **Hook duplication:** #784 (T, 2026-09-08): user-scope install appended an identical hook group on every update, so the detector ran N times per edit. Closed, but the reporter posted that it still reproduced on 4.3.1; no later confirmation found. #604 same family on Windows. [V]
- **Disabling:** #512/#667: `hooks reset` after `hooks off` re-armed the hook (fixed, #668). [V]
- **Context cost:** #375 (T, open): ~120-word description loaded into every session, about 3x the next largest skill in the reporter's setup. #542: always-loaded rule block (resolved). #1018 (T, open, 2026-10-12): with a 54 KB DESIGN.md, `impeccable context` printed ~61K characters, Claude Code truncated it, and across ~40 sessions agents never reached the trailing directives (no detector run). [V]
- **Slowness:** no user complaint about hook latency found, other than the duplication bugs. [V]
- **CI:** one feature request for `--quiet` for CI/pre-commit (#238, closed 2026-06-19). No account of anyone running `detect` as a CI gate was found. [V]

## 3. Behaviour by stack

- **MUI, Chakra, Mantine: no report found** anywhere (issues, HN, blogs). Zero issues mention MUI, `createTheme`, `sx`, Emotion or styled-components in a relevant way. Absence of reports, not evidence of good behaviour. [V]
- **Tailwind + React + shadcn/ui** is the stack behind most detailed reports (#633, #625, #875, #837), so it is the best exercised. Tailwind v4 `oklch` colours broke the contrast path once (#592, fixed). [V]
- **shadcn/ui (live mode):** #875 (T, open) — rendered `input` not matched to source `<Input>`; fallback could delete the original element. #852: live accept wrote invalid TSX on Next 16/React 19. Live mode is the least stable part; Mejba also calls it alpha-quality. [V]
- **Existing design system:** enforcement depends on `DESIGN.md`. #367 (T): hooks never loaded a per-app `DESIGN.md` in monorepos, so `design-system-*` rules were silently off; maintainer said still relevant after the Rust merge (2026-09-04). #570 same class. #846: sidecar reported stale after a worktree checkout. No report of a fixed theme being overridden, apart from the January HN remark. [V]
- **Vue/Svelte/Astro:** scanned, with reduced rule coverage (#884, #795); Vue preview not shipped (#386). [V]
- **Mobile:** React Native asked in #99; NativeWind (#144, open, 14 comments) still pipeline. #1017 (open): critique/audit contradict each other on native targets. [V]
- **Plain CSS:** author says library-independent (#19, 2026-03-10). No third-party confirmation. [V]

## 4. Problems

- **Rust engine transition (2026-09-04) was rough.** 117 of 388 issues were filed since; 14 engine releases in five weeks. [V]
  - Antivirus: unsigned Windows binary flagged as trojan by ESET and Defender (#740, #758, #814). Signed from engine 0.1.2; a third party posted VirusTotal 0/71 for the signed build. [V]
  - Install/update outages: #857 and #871 — `install`/`update` failed with HTTP 404 for about a week (2026-09-25 to 10-02) because the download pointed at an unpublished release. #691/#815 zero-byte zip. [V]
  - Networks: #757 updater rejected OS-trusted corporate CAs; #823 ignored proxy variables (both closed). [V]
  - Version confusion: `scripts/VERSION` said 0.1.5 while the binary reported 4.0.0 (#884 comment). [V]
- **Supply chain:** #813 (T, open, 2026-09-12), from a team reviewing a re-pin 4.0.4 → 4.3.1: checksum fetched from the same release as the binary, no re-check after first download, hardcoded upstream URL, engine not matching the tagged commit. They fixed it on a fork; one maintainer reply, unresolved. #479 (bundle integrity) closed with signature verification. Live-mode security bugs #304, #478, #507 fixed. [V]
- **Non-interactive hosts:** #736 (T): under `claude -p` the skill never activated, silently; the model finished from general knowledge, "so the transcript looks like a success". Fixed in 4.2.1. #744 (T, open): with 4.2.1, 55 of 55 launcher calls refused, reference files unread; with 4.2.2 `craft-floor.md` loaded before only 6 of 29 UI-editing activations. Maintainer: "partially addressed, not resolved". [V]
- **Worktrees:** #1016 (T, open, 4.5.2): wrong `MANUAL_DETECTOR_REQUIRED` inside `.claude/worktrees/`. #887 fixed. [V]
- **Codex vs Claude Code:** Codex has had more hook breakage — Stop hook output shape invalid (#603, #643, fixed); Windows Codex hooks written in cmd syntax but run in PowerShell, so both hooks failed on every trigger (#848, closed 2026-10-05); skill frontmatter rejected by Codex's validator (#513, #701). Claude plugin hooks on Windows PowerShell: #878 open. [V]
- **User scope:** #982 (T, open, 2026-10-08): `update --user` writes hooks to `~/.claude/settings.local.json`, which Claude Code does not read. [V]
- **Telemetry:** only #216 — privacy page said "no network requests" despite the daily version check; wording fixed. No other telemetry concern found. [V]
- **Licence:** Apache-2.0; no user concern found. [V]
- **Linux/sandbox/read-only install:** no specific report found. [V]

## 5. How people configure it

- Thin evidence. #813's team pins by commit SHA, reviews each re-pin and forked to add a checksum manifest. #744's reporter pins versions for measurement. #857 users worked around the outage with `gh release download` plus manual sha256 check. [V]
- No user write-up found on `IMPECCABLE_BIN`, vendoring the binary, or disabling the update check in a team or pipeline; these exist in the repo docs only. [V]

## What this means for adopting it with the engine in an agentic factory

- Expect value as a **finisher and reviewer** on existing UI, not as a guarantee of distinctive design; nobody has measured it against the alternatives. [I]
- **"0 findings" is not a pass** on `.tsx`/`.jsx`/`.vue` sources (#884, #795). A read-only evaluator should scan the rendered page (URL mode), not only source files. [I]
- **MUI is unreported territory.** Run a first trial on the MUI app with a written `DESIGN.md`, and read every finding by hand before letting agents act on them. [I]
- **Headless and worktree sessions are the weak spot** (#736, #744, #1016, #1018). Verify per session type that the skill actually loaded its references and that hooks fired; a transcript that looks successful is not proof. [I]
- **Pin and control updates.** Releases are near-daily, the download endpoint has broken for a week, and the binary's integrity model is disputed (#813). Pin a tag, keep a copy of the verified binary, update deliberately. [I]
- **Watch for noise on non-design tickets**: pre-existing findings, duplicated hook groups after updates, findings on files the ticket did not mean to restyle. Give agents a rule for declining a finding. [I]
- **Codex needs its own check**, especially on Windows; its hook path has broken more often than Claude Code's. [I]
- Keep `DESIGN.md` small, or check that the context output is not truncated (#1018). [I]

## Not verified

- Reddit (fetch blocked; search surfaced no thread), X/Twitter and YouTube comments: not readable. Community sentiment there is unknown.
- Medium "9 Best UI Skills… I Tested Them All" (HTTP 403) and uxplanet (paywalled) were not read.
- Whether #784, #522 and #848 are truly fixed in 4.5.2: closure read, behaviour not tested.
- Any behaviour with MUI, Chakra, Mantine, CSS-in-JS: no source.
- Hook latency and token cost per edit: no measurement found.
- Issue counts come from GitHub search and may be slightly off.

## Sources

- Issues: `https://github.com/pbakaus/impeccable/issues/<n>` for 19, 99, 144, 149, 216, 238, 304, 305, 367, 375, 386, 400, 478, 479, 497, 507, 512, 513, 522, 542, 570, 592, 603, 604, 625, 633, 643, 667, 691, 701, 736, 740, 744, 757, 758, 784, 795, 813, 814, 815, 823, 837, 846, 848, 852, 857, 871, 875, 878, 881, 882, 884, 887, 963, 982, 988, 1001, 1016, 1017, 1018
- Releases: https://github.com/pbakaus/impeccable/releases
- HN launch thread: https://news.ycombinator.com/item?id=46587284
- HN comments: `https://news.ycombinator.com/item?id=<id>` for 49533455, 49062523, 49059235, 49651296, 49725193, 49294522
- https://react-japan.dev/articles/three-design-tools-one-model
- https://www.mejba.me/blog/impeccable-claude-code-design-skill (self-promotional)
- https://composio.dev/blog/top-design-skills (vendor)
- https://claudeskills.info/blog/frontend-design-vs-impeccable-vs-ui-ux-pro-max/ (directory)
- https://ruoqijin.com/blog/frontend-design-skills-ai-agents (synthesis)
- https://viblo.asia/p/impeccable-vs-taste-skill-hai-truong-phai-chong-ai-slop-trong-vibe-coding-G24B8G2ELz3 (no testing)
- https://latent.space/p/skill-engineering-design (author interview, 2026-07-02)
