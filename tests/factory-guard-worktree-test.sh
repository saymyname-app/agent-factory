#!/usr/bin/env bash
#
# factory-guard must notice a worktree left behind by a finished session.
#
# This is not hypothetical. On 2026-09-16 two of them (`c-config-worktree`,
# `pr40-worktree`) still pinned branches whose PRs were merged and closed.
# A pinned branch cannot be deleted, so `gh pr merge --delete-branch` exits
# non-zero AFTER merging, and pr-autopilot used to read that as "direct merge
# failed — left for a human" on a PR that had in fact merged.
#
# The subtle part, and the reason this test exists: a SQUASH merge does not
# make the branch an ancestor of main, so `git merge-base --is-ancestor` alone
# detects nothing. The guard must ask for the PR state. A first version of the
# check shipped a broken repo slug, reported "none", and would have been
# believed.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/factory-guard"
TMP=$(mktemp -d)
trap 'git -C "$TMP/repo" worktree remove --force "$TMP/wt" 2>/dev/null || true; rm -rf "$TMP"' EXIT

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

# --- a throwaway repo with an origin, a main, and a merged-then-abandoned branch
git init -q --bare "$TMP/origin.git"
git init -q "$TMP/repo"
cd "$TMP/repo"
git config user.email t@t; git config user.name t; git config commit.gpgsign false
git remote add origin "$TMP/origin.git"
echo one > file; git add file; git commit -qm one
git branch -M main; git push -q origin main
git checkout -qb feat/squashed
echo two > file; git commit -qam two; git push -q origin feat/squashed
git checkout -q main
# main advances WITHOUT feat/squashed as an ancestor: that is what squash does.
echo three > file; git commit -qam three; git push -q origin main
git fetch -q origin

git worktree add -q "$TMP/wt" feat/squashed

# --- stub gh: the branch's PR is merged --------------------------------------
mkdir -p "$TMP/bin"
cat > "$TMP/bin/gh" <<'STUB'
#!/usr/bin/env bash
# Behaves like the real gh in the one way that matters here: a --repo it
# cannot resolve is an error, not a silent empty answer. Without this the
# stub would happily answer MERGED for a bogus slug and the test would bless
# the broken-slug bug it exists to catch.
prev=""; repo=""
for arg in "$@"; do
  [ "$prev" = "--repo" ] && repo="$arg"
  prev="$arg"
done
if [ -n "$repo" ] && [ "$repo" != "test/fixture" ]; then
  echo "GraphQL: Could not resolve to a Repository with the name '$repo'." >&2
  exit 1
fi
case "$*" in
  *"pr list"*"feat/squashed"*) echo MERGED ;;
  *) exit 1 ;;
esac
STUB
chmod +x "$TMP/bin/gh"
export PATH="$TMP/bin:$PATH"

out=$(FACTORY_ROOT="$TMP/repo" "$GUARD" --check-only 2>&1 || true)

grep -q "merge-base" <<<"$out" && fail "guard leaked an internal error"
if ! grep -q "still pins 'feat/squashed'" <<<"$out"; then
  printf '%s\n' "$out" >&2
  fail "guard did not flag the worktree pinning a squash-merged branch"
fi
grep -q "its PR is merged" <<<"$out" || fail "guard did not name why the worktree is stale"
grep -q "git worktree remove $TMP/wt" <<<"$out" || fail "guard did not print the exact fix"

# --- and it must go quiet once the worktree is gone --------------------------
git worktree remove --force "$TMP/wt"
out=$(FACTORY_ROOT="$TMP/repo" "$GUARD" --check-only 2>&1 || true)
grep -q "still pins" <<<"$out" && fail "guard still complains after the worktree was removed"
grep -q "worktrees — 0 human worktree" <<<"$out" || {
  printf '%s\n' "$out" >&2
  fail "guard did not report a clean worktree state"
}

# --- --check-only must not mutate the repo -----------------------------------
before=$(git worktree list | wc -l)
FACTORY_ROOT="$TMP/repo" "$GUARD" --check-only >/dev/null 2>&1 || true
[ "$(git worktree list | wc -l)" = "$before" ] || fail "--check-only changed the worktree list"

echo "OK factory-guard worktree hygiene"
