# ADR-0022: Mechanical enforcement of "never edit the live root, use a worktree"

- Status: Accepted
- Date: 2026-09-18
- Decided by: Claude Code, acting under `gc.authorized_by`: Benjamin, live
  chat 2026-09-18 ("root-cause every bug observed on the Factory run, check
  for a pending fix, otherwise request a root-cause fix") — af-ogg8z.
- Applies to: `saymyname-app/agent-factory` (the live Factory root) and its
  `mol-do-work` formula.

## Context

Between 23:05 and 23:08 on 2026-09-17 the Mayor session ran `git commit`,
`git checkout` and `git reset --hard` directly in
`/home/benja/agent-factory` instead of a worktree (reflog: commit `7017aa2`,
checkout `fix/mayor-campaign-stale-wake-clear`, `reset --hard origin/main`
×3). One side effect: `bin/provider-failover` lost its executable bit. It
still existed on disk — `factory-guard`'s runtime-files check only ever
tested `-e` — so it silently failed exit 126 every tick from 23:08:17 to
01:01:11: **no provider failover for 2 hours**, and nothing noticed. It
stopped only because an unrelated PO pull happened to rewrite the file. A
second symptom of the same cause: at 00:14 a worker running `mol-do-work`
committed `af-lb3q` directly in the live root the same way, no branch, no
PR — the HQ rig gave that formula the live root as its working directory
with no isolation at all.

`AGENTS.md` already said "Branch work happens in a `git worktree`, never by
checking out in the live root" before this incident. That prose did not
stop it. Mechanical enforcement is the fix, not another sentence.

## Decision

Three independent mechanisms, one per way the live root gets modified:

**1. `factory-guard` verifies executable bits, not just existence.** A new
check (`bin/factory-guard`, "exec-bits") compares `git ls-files -s -- bin/`
mode `100755` against the actual mode on disk for every run, and repairs a
drifted bit with `chmod +x`, logging the same `FIXED:` convention every
other self-heal in that script uses. This is the check that was missing on
2026-09-17 — existence alone was never enough.

**2. A `reference-transaction` git hook refuses commit/checkout/switch/
reset/merge in the live root.** `.githooks/reference-transaction` (wired
via the `core.hooksPath = .githooks` already set for this repo, see
ADR-0020) inspects its own parent process's `/proc/$PPID/cmdline` to find
the git subcommand actually being run, and refuses `commit`, `checkout`,
`switch`, `reset`, or `merge` when the working tree is the live root itself
(`git rev-parse --show-toplevel` equals `$FACTORY_ROOT`, default
`/home/benja/agent-factory` — never a worktree). It reads argv rather than
the ref-transaction payload alone because `git worktree add -b <name>` and
a plain `git branch <name>` produce an *identical-looking* single-ref
creation event to `git checkout -b <name>` — and the first two are the
sanctioned escape hatch that must keep working from the live root, while
the third is exactly the dangerous case. `bin/factory-guard` sets
`FACTORY_GUARD_INTERNAL=1` around its own two live-root git calls (the
pinned-branch restore and the fast-forward-only sync) so this hook can tell
its self-heal apart from anyone else's git command.

**Coverage gap, documented rather than hidden:** `git checkout
<existing-branch>` / `git switch <existing-branch>` — the exact command
that started the 2026-09-17 incident — only repoints HEAD's *symbolic*
ref. `man githooks` documents that `reference-transaction` "does not cover
symbolic references", and this was verified empirically against git 2.43:
the hook never fires at all for that case. Stock git has no pre-checkout
hook to veto it before it happens. `.githooks/post-checkout` (already
existed as a warning-only hook, see ADR before this one) now instead
reverts the live root back to its pinned branch immediately and reports
the refusal — "refuse" here means "never actually stays there", which is
the invariant that matters (2026-09-17: it stayed there for hours, not
seconds). Like every hook in `.githooks`, this is a local convenience
gate (ADR-0020's framing), not a security boundary: `git commit
--no-verify` or editing `.git` directly still bypass it, same as any other
hook here.

**3. `mol-do-work` isolates HQ dispatches in a worktree.** The formula's
new `workspace-setup` step calls `bin/factory-do-work-workspace enter
<bead-id>`, which creates (or reuses) a worktree at
`$HOME/.local/share/agent-factory-runtime-worktrees/<bead-id>` on branch
`do-work/<bead-id>` **only** when the caller's cwd is the live root — a
documented no-op everywhere else, so every other rig using this formula
keeps its exact prior behavior. The new `push-and-pr` step calls
`factory-do-work-workspace finish` to push that branch, open a PR with
`gh` if available, and remove the worktree — again a no-op if
`workspace-setup` found nothing to isolate. `$HOME/.local/share/
agent-factory-runtime-*` is the prefix `bin/factory-guard`'s stale-worktree
check (section 6) already excludes as "the city's own; leave them" — these
worktrees are this script's responsibility to remove, not factory-guard's
to flag.

## Consequences (ADR-0017's four conditions)

1. **Verified, not asserted** —
   `tests/factory-guard-exec-bit-test.sh` (chmod -x a tracked `bin/` file,
   prove `--check-only` reports it and a normal run repairs it with a
   `FIXED:` line);
   `tests/factory-live-root-guard-test.sh` (replays the 2026-09-17
   sequence in a throwaway repo: commit/checkout-b/reset are refused, a
   plain checkout to an existing branch is auto-reverted, factory-guard's
   own `FACTORY_GUARD_INTERNAL=1` operations are exempt, a plain `git
   branch`/`git worktree add -b` keep working, and none of this touches an
   actual worktree);
   `tests/factory-do-work-workspace-test.sh` (`enter` creates an isolated
   worktree on its own branch in the live root and reuses it on a second
   call, `finish` pushes the branch and removes the worktree, both are a
   no-op outside the live root).
2. **Increases autonomy** — the live root can no longer silently drift
   under an agent's own git commands; a worker no longer needs a human to
   notice a stray direct commit or a dead `provider-failover`.
3. **Optimises** — removes the 2-hour provider-failover blackout class of
   incident, and the af-lb3q class of un-reviewed live-root commit, at
   zero model-token cost (pure local git/bash checks and hooks).
4. **Documented for both audiences** — this ADR and `docs/CONTEXT_INDEX.md`
   for agents; `AGENTS.md`'s existing "never checkout in the live root"
   bullet now points here for the mechanism.

## Deliberately out of scope

The bead that opened this work (af-ogg8z) also named an `[Event]`
criterion — factory-guard paging the Mayor once when the live root has
tracked modifications older than 30 minutes with no owning session — as a
fourth acceptance criterion. That is a distinct liveness/staleness check
(closer in shape to factory-guard's existing liveness section) rather than
enforcement of "don't edit the live root directly", and was out of the
scope handed to this change; it remains open on af-ogg8z for separate
follow-up.

## Related

- ADR-0017 — four conditions every factory improvement must meet.
- ADR-0020 — the pre-push main-landing gate; established that
  `core.hooksPath = .githooks` is already set for this repo, and that a
  local git hook here is a convenience gate, not a security boundary.
- `bin/factory-guard` — the exec-bit check, and the two internal git calls
  now marked `FACTORY_GUARD_INTERNAL=1`.
- `.githooks/reference-transaction`, `.githooks/post-checkout` — the two
  hooks that make this mechanical.
- `bin/factory-do-work-workspace`, `formulas/mol-do-work.formula.toml` —
  the HQ-only worktree lifecycle for dispatched work.
