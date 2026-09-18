#!/usr/bin/env bash
#
# A repository hook must refuse git commit/checkout/switch/reset/merge in the
# LIVE agent-factory root -- but never in a worktree, never for factory-
# guard's own pinned-branch restore or fast-forward, and never for a plain
# `git branch`/`git worktree add -b` (which is exactly the sanctioned escape
# hatch and must keep working).
#
# af-ogg8z: on 2026-09-17, 23:05-23:08, the Mayor ran `git commit`, `git
# checkout` and `git reset --hard` directly in the live root instead of a
# worktree. AGENTS.md already said "never edit the live root" -- this test
# proves that rule is now mechanical, via .githooks/reference-transaction
# (covers commit/reset/merge/checkout -b/switch -c) and .githooks/post-
# checkout (covers a plain checkout to an EXISTING branch, which only moves
# HEAD's symbolic ref and never reaches reference-transaction at all --
# verified against git 2.43; see the header comment in that hook for detail).

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
RT_HOOK="$REPO_ROOT/.githooks/reference-transaction"
CO_HOOK="$REPO_ROOT/.githooks/post-checkout"
TMP=$(mktemp -d)
trap 'git -C "$TMP/root" worktree remove --force "$TMP/wt" 2>/dev/null || true; rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

[ -x "$RT_HOOK" ] || fail "$RT_HOOK is not executable"
[ -x "$CO_HOOK" ] || fail "$CO_HOOK is not executable"

# --- a throwaway "live root" with the real hooks installed ------------------
git init -q --bare "$TMP/origin.git"
git init -q "$TMP/root"
cd "$TMP/root"
git config user.email t@t; git config user.name t; git config commit.gpgsign false
git remote add origin "$TMP/origin.git"
mkdir -p .githooks .gc
cp "$RT_HOOK" .githooks/reference-transaction
cp "$CO_HOOK" .githooks/post-checkout
chmod +x .githooks/reference-transaction .githooks/post-checkout
git config core.hooksPath .githooks
echo main > .gc/factory-guard.branch
echo one > f && git add -A && git commit -qm one
git branch -M main
git push -q origin main
git branch other

export FACTORY_ROOT="$TMP/root"

# ---------------------------------------------------------------------------
# 1. git commit is refused in the live root
# ---------------------------------------------------------------------------
echo two >> f
if git commit -qam two >out1.txt 2>&1; then
  fail "a commit in the live root was NOT refused"
fi
grep -q "REFUSED" out1.txt || { cat out1.txt >&2; fail "commit refusal did not explain why"; }
grep -q "git worktree add" out1.txt || fail "commit refusal did not name the worktree alternative"
[ "$(git rev-parse HEAD)" = "$(git rev-parse main)" ]  # no-op sanity
git checkout -q -- f

# ---------------------------------------------------------------------------
# 2. git checkout -b (a real ref creation) is refused
# ---------------------------------------------------------------------------
if git checkout -qb newbranch >out2.txt 2>&1; then
  fail "'git checkout -b' in the live root was NOT refused"
fi
grep -q "REFUSED" out2.txt || { cat out2.txt >&2; fail "checkout -b refusal did not explain why"; }
git show-ref --verify --quiet refs/heads/newbranch && fail "checkout -b created the branch despite being refused"

# ---------------------------------------------------------------------------
# 3. git reset --hard is refused
# ---------------------------------------------------------------------------
if git reset -q --hard HEAD >out3.txt 2>&1; then
  fail "'git reset --hard' in the live root was NOT refused"
fi
grep -q "REFUSED" out3.txt || { cat out3.txt >&2; fail "reset refusal did not explain why"; }

# ---------------------------------------------------------------------------
# 4. git checkout to an EXISTING branch is auto-reverted (the exact incident)
# ---------------------------------------------------------------------------
git checkout other >out4.txt 2>&1 || true
grep -q "REFUSED" out4.txt || { cat out4.txt >&2; fail "switching to an existing branch was not refused"; }
grep -q "Reverted automatically" out4.txt || { cat out4.txt >&2; fail "the live root was not reverted after the switch"; }
now=$(git rev-parse --abbrev-ref HEAD)
[ "$now" = "main" ] || fail "the live root was left on '$now' instead of being reverted to 'main'"

# ---------------------------------------------------------------------------
# 5. factory-guard's own operations are exempt (FACTORY_GUARD_INTERNAL=1)
# ---------------------------------------------------------------------------
FACTORY_GUARD_INTERNAL=1 git checkout -q other \
  || fail "factory-guard's own internal checkout was refused"
[ "$(git rev-parse --abbrev-ref HEAD)" = "other" ] \
  || fail "factory-guard's own internal checkout was reverted -- it must not be"
FACTORY_GUARD_INTERNAL=1 git checkout -q main
echo three >> f
FACTORY_GUARD_INTERNAL=1 git commit -qam three \
  || fail "factory-guard's own internal commit was refused"

# ---------------------------------------------------------------------------
# 6. the sanctioned escape hatch keeps working: plain `git branch` and
#    `git worktree add -b` (both only create an unrelated ref -- neither
#    moves the live root's own HEAD/current branch) are never refused
# ---------------------------------------------------------------------------
git branch justabranch \
  || fail "a plain 'git branch' in the live root was refused -- it must not be"
git worktree add -q "$TMP/wt" -b feat/worktree-alt main \
  || fail "'git worktree add -b' from the live root was refused -- it is the sanctioned escape hatch"

# ---------------------------------------------------------------------------
# 7. and normal work inside that worktree is completely unaffected
# ---------------------------------------------------------------------------
(
  cd "$TMP/wt"
  export FACTORY_ROOT="$TMP/root"
  echo work > g
  git add g
  git commit -qm "work in the worktree"
) || fail "a commit inside a worktree was refused -- the hook must only guard the live root"

echo "OK live-root guard refuses commit/checkout-b/reset in the live root, reverts a plain checkout, exempts factory-guard's own ops, and never touches worktrees"
