# Upstream skills: pin and update procedure

W13 (A6b, spec-a6b-wayfinder-wiring-2026-09-30 user story 48, af-hxc8ra).
This is the single source of truth `bin/upstream-skills-check` reads to
know what the Factory is currently pinned to. Do not duplicate the pin
elsewhere; other docs (`docs/agents/issue-tracker.md`) reference this file
instead of carrying their own copy of the commit.

## Current pin

Pinned baseline commit: `24fe0ef7737efae15c87225755e9f6f5965e4888`
Pinned baseline tag: `v1.3.1`

Adopted at Planning Run D01 (Spec af-wf4w5r, T02, 2026-10-06), replacing
the prior `c55ee46` pin (no release tag, Planning Run A6b, 2026-09-29/30).
Reason and raised reference: Adaptation Register entry AR-008. The
Factory stays on this exact tag until a deliberate update -- see
`GLOSSARY.md`'s "Method Baseline" and "Adaptation Register" entries for
why a fixed comparison point matters.

## Vendored copy

Unlike the prior pin, the skills are recopied unchanged into this repo at
`skills/` (one `skills/<category>/<skill-name>/` directory per upstream
skill, same relative layout as `mattpocock/skills`' own `skills/`
directory at the pinned tag) instead of only into `~/.agents/skills` on
the host. `./bin/upstream-skills-check compare` is the mechanical proof
that this copy is unchanged.

## Daily check (read-only)

`./bin/upstream-skills-check`, run daily by the `upstream-skills-check`
order, compares this pin against `mattpocock/skills`' published tags. It
never updates anything: on a tag newer than the last one it already
flagged, it files exactly one `proposal`-labelled bead (never built
without Benjamin, same discipline as `bin/overlap-conflict-log`'s "dynamic
leases" proposal) so it surfaces at the next session start through
`./bin/escalation-door list`'s pending-proposal count. Seeing the same tag
again on a later day never files a second proposal.

## Comparison check (CI, read-only)

`./bin/upstream-skills-check compare` diffs the vendored `skills/`
directory, file for file, against this pin's tag fetched fresh from
`mattpocock/skills`. Exit 0 names the tag when every vendored file is
byte-identical to it; a changed, added, or removed file (inside a
vendored skill directory, by hand or by a PR) makes it exit non-zero and
name the offending file. It also refuses (non-zero exit) when the
Adaptation Register (`docs/ADAPTATION_REGISTER.md`) carries no entry for
the current pinned tag: the comparison tool is itself one of the "added
controls" that entry must name. `bin/ci-run-tests` runs this as
`tests/upstream-skills-check-compare-test.sh`, so a PR that edits a
vendored skill file is red.

## Update procedure (by hand, deliberate)

Adopting a newer upstream commit or tag is never automatic. When Benjamin
decides to adopt one, the same change must cover all three of the
following, together, or the pin and the vendored skills silently diverge:

1. **Release tag only, first.** Confirm the new tag (or commit) is what is
   actually being adopted -- read its diff against the current pin
   upstream before touching anything here.
2. **Re-vendor the full skill directories.** Replace the `skills/`
   directory wholesale from the new tag's `skills/` subtree -- a full
   `rm -rf skills && cp` of the upstream tree, including each skill's
   `agents/` folder, never hand-patched. Normalize line endings to LF: a
   manual copy from a Windows checkout or an editor that rewrites line
   endings on save can silently introduce CRLF, which breaks skill
   parsing in ways that are easy to miss in a diff.
3. **Rewrite every pin reference in the same change.** At minimum:
   - This file's "Current pin" section (the authoritative copy).
   - `docs/agents/issue-tracker.md`'s opening line.
   - A new `docs/ADAPTATION_REGISTER.md` entry naming the old and new
     pin and its reason -- `./bin/upstream-skills-check compare` refuses
     without one.
   - Any other live doc a `grep -rn` for the old commit surfaces (treat
     `docs/planning/**` and `docs/research/**` as historical archives --
     leave their pinned references alone; they describe what was true at
     the time they were written).

   After the rewrite, `./bin/upstream-skills-check` must observe the new
   pin as current (no proposal fires for a tag at or before it), and
   `./bin/upstream-skills-check compare` must exit 0.

A change that does only one or two of the three above is incomplete: a
pin rewrite with no re-vendoring leaves the Factory claiming a baseline it
does not run; a re-vendor with no pin rewrite leaves the daily check
proposing an "upgrade" the Factory already made.
