#!/usr/bin/env bash
#
# Workers dispatched via mol-do-work on the HQ (agent-factory) rig must work
# in a git worktree, never the live root -- af-ogg8z, same incident as
# tests/factory-live-root-guard-test.sh: on 2026-09-17 a worker running this
# formula committed af-lb3q straight into the live root (no branch, no PR).
#
# bin/factory-do-work-workspace is what mol-do-work's workspace-setup and
# push-and-pr steps call to fix that. This test drives the script directly
# (not the formula prose, which an LLM interprets, not a test harness) and
# proves: `enter` creates an isolated worktree on its own branch when cwd IS
# the live root, `finish` pushes that branch and removes the worktree, and
# both are a documented no-op anywhere else (a rig checkout, or a worktree
# that already exists).

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SCRIPT="$REPO_ROOT/bin/factory-do-work-workspace"
TMP=$(mktemp -d)
trap 'git -C "$TMP/root" worktree remove --force "$WT" 2>/dev/null || true; rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

[ -x "$SCRIPT" ] || fail "$SCRIPT is not executable"

# --- a throwaway "live root" with an origin ----------------------------------
git init -q --bare "$TMP/origin.git"
git init -q "$TMP/root"
cd "$TMP/root"
git config user.email t@t; git config user.name t; git config commit.gpgsign false
git remote add origin "$TMP/origin.git"
echo one > f && git add -A && git commit -qm one
git branch -M main
git push -q origin main

export FACTORY_ROOT="$TMP/root"
export HOME="$TMP/home"
mkdir -p "$HOME"

# ---------------------------------------------------------------------------
# 1. `enter` in the live root creates an isolated worktree on its own branch
# ---------------------------------------------------------------------------
WT=$("$SCRIPT" enter af-workspace-test)
[ -n "$WT" ] && [ "$WT" != "." ] || fail "enter did not return a worktree path in the live root"
[ -d "$WT" ] || fail "enter reported worktree path $WT but it does not exist"
[ "$WT" != "$TMP/root" ] || fail "enter returned the live root itself"
branch=$(git -C "$WT" rev-parse --abbrev-ref HEAD)
[ "$branch" = "do-work/af-workspace-test" ] \
  || fail "worktree is on branch '$branch', expected 'do-work/af-workspace-test'"

# the live root itself must be untouched
[ "$(git -C "$TMP/root" rev-parse --abbrev-ref HEAD)" = "main" ] \
  || fail "enter moved the live root off its own branch"

# ---------------------------------------------------------------------------
# 2. `enter` again (resume) reuses the same worktree, does not recreate it
# ---------------------------------------------------------------------------
WT2=$("$SCRIPT" enter af-workspace-test)
[ "$WT2" = "$WT" ] || fail "a second 'enter' for the same bead did not reuse the existing worktree"

# ---------------------------------------------------------------------------
# 3. `finish` pushes the branch and removes the worktree
# ---------------------------------------------------------------------------
echo work > "$WT/g"
git -C "$WT" add g
git -C "$WT" commit -qm "work"
"$SCRIPT" finish af-workspace-test "$WT" do-work/af-workspace-test main >finish.out 2>finish.err \
  || { cat finish.err >&2; fail "finish exited non-zero"; }

[ -d "$WT" ] && fail "finish did not remove the worktree"
git -C "$TMP/root" fetch -q origin
git -C "$TMP/root" show-ref --verify --quiet refs/remotes/origin/do-work/af-workspace-test \
  || fail "finish did not push the branch to origin"

# ---------------------------------------------------------------------------
# 4. `finish` is a no-op given enter's own "." marker (not an HQ dispatch)
# ---------------------------------------------------------------------------
"$SCRIPT" finish af-noop . do-work/af-noop main \
  || fail "'finish . ...' (enter's no-op marker) must exit 0, not fail"

# ---------------------------------------------------------------------------
# 5. `enter` is a documented no-op anywhere that is NOT the live root
# ---------------------------------------------------------------------------
mkdir -p "$TMP/some-rig"
(
  cd "$TMP/some-rig"
  git init -q
  out=$("$SCRIPT" enter af-other-rig)
  [ "$out" = "." ] || { echo "expected '.', got '$out'" >&2; exit 1; }
) || fail "enter created a worktree outside the live root -- it must be a no-op there"

echo "OK bin/factory-do-work-workspace isolates HQ dispatches in a worktree, pushes and cleans up on finish, and is a no-op elsewhere"
