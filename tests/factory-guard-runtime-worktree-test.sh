#!/usr/bin/env bash
#
# factory-guard's local-commit backup must cover runtime worktrees opened
# against ANY repo, not just $FACTORY_ROOT's own -- exactly the shape a
# product-rig dispatch takes (O05, spec-factory-operations-v2-2026-09-28):
# bin/factory-do-work-workspace opens a worktree against whichever repo was
# current, so a detached-HEAD commit or an uncommitted file inside one used
# to be invisible to every backup check factory-guard had.
#
# Four guard behaviors, one fixture:
#   1. an unpushed commit on a detached HEAD in a runtime worktree is backed
#      up to an origin ref.
#   2. a worktree with uncommitted work is never removed, and is reported.
#   3. a fresh branch sitting exactly on origin/main is left alone.
#   4. a root-owned file in a worktree is reported (simulated via a `find`
#      stub -- creating a real root-owned file needs privilege this test
#      cannot assume).

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/factory-guard"
TMP=$(mktemp -d)
FAKE_HOME="$TMP/home"
mkdir -p "$FAKE_HOME"
RUNTIME_WT_ROOT="$FAKE_HOME/.local/share/agent-factory-runtime-worktrees"
mkdir -p "$RUNTIME_WT_ROOT"

cleanup() {
  git -C "$TMP/repo" worktree remove --force "$RUNTIME_WT_ROOT/detached-wt" 2>/dev/null || true
  git -C "$TMP/repo" worktree remove --force "$RUNTIME_WT_ROOT/dirty-wt" 2>/dev/null || true
  git -C "$TMP/repo" worktree remove --force "$RUNTIME_WT_ROOT/fresh-wt" 2>/dev/null || true
  git -C "$TMP/repo" worktree remove --force "$RUNTIME_WT_ROOT/root-owned-wt" 2>/dev/null || true
  rm -rf "$TMP"
}
trap cleanup EXIT

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

# --- a throwaway repo standing in for a product rig's own checkout ----------
git init -q --bare "$TMP/origin.git"
git init -q "$TMP/repo"
cd "$TMP/repo"
git config user.email t@t; git config user.name t; git config commit.gpgsign false
git remote add origin "$TMP/origin.git"
echo one > file; git add file; git commit -qm one
git branch -M main; git push -q origin main

# 1. a runtime worktree, detached HEAD, one commit that exists nowhere else.
git worktree add -q --detach "$RUNTIME_WT_ROOT/detached-wt" main
(cd "$RUNTIME_WT_ROOT/detached-wt" && echo two > file && git commit -qam two)
DETACHED_SHA=$(git -C "$RUNTIME_WT_ROOT/detached-wt" rev-parse HEAD)

# 2. a runtime worktree with uncommitted work.
git worktree add -q "$RUNTIME_WT_ROOT/dirty-wt" -b feat/dirty main
echo wip > "$RUNTIME_WT_ROOT/dirty-wt/draft"

# 3. a fresh branch sitting exactly on origin/main -- nothing of its own yet.
git worktree add -q "$RUNTIME_WT_ROOT/fresh-wt" -b do-work/fresh main

# 4. a worktree with a "root-owned" file, simulated via a `find` stub: this
# test cannot assume it can actually chown a file to root.
git worktree add -q "$RUNTIME_WT_ROOT/root-owned-wt" -b do-work/root-owned main
mkdir -p "$RUNTIME_WT_ROOT/root-owned-wt/build-cache"
: > "$RUNTIME_WT_ROOT/root-owned-wt/.root-owned-marker"

mkdir -p "$TMP/bin"
cat > "$TMP/bin/find" <<'STUB'
#!/usr/bin/env bash
# Stand-in for the root-owned-file check. factory-guard only ever calls
# `find <dir> -user root ...` -- anything else falls through to the real
# find so nothing else in the guard breaks.
is_user_filter=0
for a in "$@"; do [ "$a" = "-user" ] && is_user_filter=1; done
if [ "$is_user_filter" = "1" ]; then
  target="$1"
  [ -f "$target/.root-owned-marker" ] && printf '%s/build-cache/output.bin\n' "$target"
  exit 0
fi
exec /usr/bin/find "$@"
STUB
chmod +x "$TMP/bin/find"
export PATH="$TMP/bin:$PATH"

out=$(HOME="$FAKE_HOME" FACTORY_ROOT="$TMP/repo" "$GUARD" --check-only 2>&1 || true)

grep -q "$DETACHED_SHA" <<<"$out" && fail "guard printed a raw sha instead of naming the worktree/check-only outcome"
grep -q "has commit(s) on branch 'detached'.*exist nowhere but this machine" <<<"$out" \
  || { printf '%s\n' "$out" >&2; fail "guard did not flag the detached-HEAD commit as unbacked-up"; }

grep -q "has uncommitted work (branch 'feat/dirty')" <<<"$out" \
  || { printf '%s\n' "$out" >&2; fail "guard did not flag the dirty worktree"; }

grep -q "fresh-wt" <<<"$out" && fail "guard flagged a fresh branch sitting exactly on origin/main"

grep -q "root-owned-wt.*root-owned file.*build-cache/output.bin" <<<"$out" \
  || { printf '%s\n' "$out" >&2; fail "guard did not report the root-owned file"; }

# --- a real (non-check-only) run backs the detached commit up, and removes
# nothing --------------------------------------------------------------------
out=$(HOME="$FAKE_HOME" FACTORY_ROOT="$TMP/repo" "$GUARD" 2>&1 || true)
grep -q "FIXED: backed up worktree.*detached-wt.*to origin refs/factory-guard/snapshots/worktree/detached-wt" <<<"$out" \
  || { printf '%s\n' "$out" >&2; fail "guard did not back up the detached-HEAD commit"; }
git -C "$TMP/origin.git" cat-file -e "$DETACHED_SHA" 2>/dev/null \
  || fail "the detached commit was not actually pushed to origin"

[ -d "$RUNTIME_WT_ROOT/dirty-wt" ] || fail "guard removed a worktree with uncommitted work"
[ -f "$RUNTIME_WT_ROOT/dirty-wt/draft" ] || fail "guard deleted uncommitted content instead of leaving it alone"
[ -d "$RUNTIME_WT_ROOT/detached-wt" ] || fail "guard removed the detached worktree after backing it up (it only backs up, never removes)"

echo "OK factory-guard runtime-worktree audit"
