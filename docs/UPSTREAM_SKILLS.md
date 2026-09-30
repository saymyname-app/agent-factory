# Upstream skills: pin and update procedure

W13 (A6b, spec-a6b-wayfinder-wiring-2026-09-30 user story 48, af-hxc8ra).
This is the single source of truth `bin/upstream-skills-check` reads to
know what the Factory is currently pinned to. Do not duplicate the pin
elsewhere; other docs (`docs/agents/issue-tracker.md`) reference this file
instead of carrying their own copy of the commit.

## Current pin

Pinned baseline commit: `c55ee46073ed923f86ce59a5eb3b6d895095d1b7`
Pinned baseline tag: none

`mattpocock/skills` had published no release tag at this commit when it was
pinned (Planning Run A6b, 2026-09-29/30). The Factory stays on this exact
commit until a deliberate update -- see `docs/CONTEXT.md`'s "Method
Baseline" and "Adaptation Register" entries for why a fixed comparison
point matters.

## Daily check (read-only)

`./bin/upstream-skills-check`, run daily by the `upstream-skills-check`
order, compares this pin against `mattpocock/skills`' published tags. It
never updates anything: on a tag newer than the last one it already
flagged, it files exactly one `proposal`-labelled bead (never built
without Benjamin, same discipline as `bin/overlap-conflict-log`'s "dynamic
leases" proposal) so it surfaces at the next session start through
`./bin/escalation-door list`'s pending-proposal count. Seeing the same tag
again on a later day never files a second proposal.

## Update procedure (by hand, deliberate)

Adopting a newer upstream commit or tag is never automatic. When Benjamin
decides to adopt one, the same change must cover all three of the
following, together, or the pin and the vendored skills silently diverge:

1. **Release tag only, first.** Confirm the new tag (or commit) is what is
   actually being adopted -- read its diff against the current pin
   upstream before touching anything here.
2. **Re-vendor the full skill directories.** Re-run the upstream skill
   installer (`setup-matt-pocock-skills`, referenced in
   `docs/agents/issue-tracker.md`) so every skill directory it manages,
   including each skill's `agents/` folder, is replaced wholesale from the
   new commit -- never hand-patched. Normalize line endings to LF: the
   installer's own output already uses LF, but a manual copy from a
   Windows checkout or an editor that rewrites line endings on save can
   silently introduce CRLF, which breaks skill parsing in ways that are
   easy to miss in a diff.
3. **Rewrite every pin reference in the same change.** At minimum:
   - This file's "Current pin" section (the authoritative copy).
   - `docs/agents/issue-tracker.md`'s opening line.
   - Any other live doc a `grep -rn` for the old commit surfaces (treat
     `docs/planning/**` and `docs/research/**` as historical archives --
     leave their pinned references alone; they describe what was true at
     the time they were written).

   After the rewrite, `./bin/upstream-skills-check` must observe the new
   pin as current (no proposal fires for a tag at or before it).

A change that does only one or two of the three above is incomplete: a
pin rewrite with no re-vendoring leaves the Factory claiming a baseline it
does not run; a re-vendor with no pin rewrite leaves the daily check
proposing an "upgrade" the Factory already made.
