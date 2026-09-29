# A6b research: can Codex load the Matt Pocock skills? (af-0aiero.1)

Date: 2026-09-29. Author: po-agent (Claude). Map: af-0aiero (A6b).

## Question

Can Codex (desktop app and CLI on Windows 11) load skills from `~/.agents/skills`
(`C:\Users\benja\.agents\skills`)? If not, where does it load them from? Does it
honour `disable-model-invocation: true` in SKILL.md and/or
`agents/openai.yaml` `policy.allow_implicit_invocation: false`?

## Answer

- **Yes.** `$HOME/.agents/skills` is Codex's documented **user-scope** skills
  location, for the CLI, the IDE extension and the desktop app. The
  `~/.codex/skills` folder (only `.system` here) is the deprecated location,
  still scanned for compatibility. Nothing to move or link.
- **`disable-model-invocation` is ignored by Codex.** Its SKILL.md parser reads
  only `name`, `description` and `metadata.short-description`.
- **`policy.allow_implicit_invocation: false` in `agents/openai.yaml` is
  honoured.** The skill is hidden from the model's skill catalog, so Codex never
  selects it by itself. The user can still call it explicitly with
  `$skill-name`, per the docs.
- **Gap found:** the installed copies in `~/.agents/skills` have **no**
  `agents/openai.yaml`. So on Codex today, wayfinder, setup-matt-pocock-skills,
  to-spec and to-tickets can all be invoked implicitly, which is not what the
  upstream author intended.

## Evidence

### 1. Skill locations (official docs)

The docs page https://learn.chatgpt.com/docs/build-skills was read 2026-09-29.
It is the 308 redirect target of https://developers.openai.com/codex/skills.
It lists these scan locations, in order:

- `$CWD/.agents/skills`
- `$CWD/../.agents/skills`
- `$REPO_ROOT/.agents/skills`
- `$HOME/.agents/skills` (user scope)
- `/etc/codex/skills` (admin scope)
- the skills bundled with Codex (system scope)

The same page also says:

- Codex "supports symlinked skill folders and follows the symlink target".
- Skills apply to the Codex CLI, the IDE extension and the desktop app.
- There are two ways to invoke a skill. **Explicit:** `$skill-name` in the
  CLI or IDE. **Implicit:** Codex picks the skill that matches its
  `description`.
- `agents/openai.yaml` is optional. `policy.allow_implicit_invocation: false`
  "prevents automatic selection".
- `[[skills.config]]` with `enabled = false` in `~/.codex/config.toml`
  disables a skill. Codex must be restarted after a `config.toml` change.

### 2. Skill locations (source)

Source read in github.com/openai/codex at `main` ed9e5a26a88b (2026-09-29) and
at tag `rust-v0.154.0` (36eab010), the version installed here. The same code is
present in both.

The file is `codex-rs/ext/skills/src/host_roots.rs`, in the user config layer.
It pushes three roots:

- `$CODEX_HOME/skills`. The source comments it as "Deprecated user skills
  location (`$CODEX_HOME/skills`), kept for backward compatibility".
- `home_dir().join(".agents").join("skills")`, with `SkillScope::User`.
- The system cache root.

`home_dir()` comes from the `dirs` crate. Repo roots come from each
`.agents/skills` folder between the cwd and the repo root.

### 3. Frontmatter: `disable-model-invocation` is not read

In `codex-rs/skills/src/parser.rs`, `struct SkillFrontmatter` has three fields:

- `name`
- `description`
- `metadata: { short-description }`

The struct has no `deny_unknown_fields`. So any other key, such as
`disable-model-invocation`, `user-invocable` or `allowed-tools`, is silently
ignored.

A code search of the repo for `disable-model-invocation` finds a single hit, in
a memories prompt template
(`codex-rs/memories/write/templates/memories/consolidation.md`). That is text
given to the model, not parsing logic. A search for `disable_model_invocation`
finds nothing.

### 4. `agents/openai.yaml` policy is enforced

Three places in the source show this:

- `codex-rs/ext/skills/src/loader/metadata.rs` deserialises
  `policy.allow_implicit_invocation: Option<bool>`.
- `codex-rs/skills/src/model.rs` has `allows_implicit_invocation()`, which
  defaults to `true` when the field is absent.
- In `codex-rs/ext/skills/src/provider/host.rs`:
  `if !skill.allows_implicit_invocation() { entry = entry.hidden_from_prompt(); }`.
  So the skill is still loaded and enabled, but it is left out of the catalog
  the model sees.

### 5. Local state (read-only, 2026-09-29)

- `codex --version` returns `codex-cli 0.154.0`. `~/.codex/config.toml` has no
  `skills` entries, so no skill is disabled.
- `~/.claude/skills/*` are NTFS junctions to `~/.agents/skills/*`. Codex reads
  `~/.agents/skills` directly and does not need them.
- Upstream mattpocock/skills at c55ee46 has `agents/openai.yaml` with
  `allow_implicit_invocation: false` for only two skills:
  - `skills/engineering/wayfinder`
  - `skills/engineering/setup-matt-pocock-skills`

  `to-spec` and `to-tickets` carry only `disable-model-invocation: true`, so
  upstream leaves them implicitly invocable on Codex.
- The installed `~/.agents/skills/{wayfinder,setup-matt-pocock-skills}` have
  **no `agents/` folder**. The install step copied SKILL.md but dropped
  `agents/openai.yaml`.
- Older Codex sessions (2026-09-23) read skills from the repo-scope
  `C:\Dev\Projects\SayMyName\.agents\skills\...`. The latest Codex session is
  from 2026-09-24, before the Matt skills were installed (2026-09-25/29). So
  there is no live proof yet of the user scope on this machine.

## Implications for wiring the Planning Run for Codex

1. No path work is needed: Codex sees the same `~/.agents/skills` tree as
   Claude.
2. To keep the user-only skills user-only on Codex:
   - Restore upstream `agents/openai.yaml` for wayfinder and
     setup-matt-pocock-skills. This is a fix to the install step.
   - Decide whether to add an equivalent `openai.yaml` for to-spec and
     to-tickets. That would be a local divergence from upstream.
   - Alternatively, accept implicit invocation on Codex.
3. Name any skill explicitly in Codex prompts (`$wayfinder`, `$to-spec`, and
   so on) rather than relying on its description.

## UNVERIFIED

- Codex 0.154.0 actually listing the `~/.agents/skills` skills on this
  machine. The code and docs say it should; a live check in Codex is still
  needed (type `$` or `/skills` in a new session). The resolution of
  `home_dir()` to `C:\Users\benja` on Windows is inferred from the documented
  behaviour of the `dirs` crate and was not observed.
- Whether Codex follows **NTFS junctions** as well as symlinks. This is moot,
  because Codex reads the real folders, not the Claude junctions.
- That an explicit `$name` call works for a skill that is
  `hidden_from_prompt`. The docs imply it; I did not trace the
  explicit-mention path in the source.
