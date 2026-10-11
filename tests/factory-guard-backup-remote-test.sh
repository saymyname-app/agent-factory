#!/usr/bin/env bash
#
# factory-guard's snapshots must not land on a repository strangers can read
# (af-996mmd). A snapshot holds uncommitted files and commits nobody
# reviewed. When the repository names a remote `backup`, the working-tree
# snapshot and the worktree backups go there and origin receives nothing;
# tests/factory-guard-dirty-tree-test.sh and
# tests/factory-guard-runtime-worktree-test.sh hold the case without it.
#
# Second thing held here: the ten worktree backups that sat beside the dated
# snapshots on 2026-10-11 sort after every date, so "keep the ten most
# recent" deleted each new snapshot the moment it was pushed.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/factory-guard"
TMP=$(mktemp -d)
FAKE_HOME="$TMP/home"
RUNTIME_WT_ROOT="$FAKE_HOME/.local/share/agent-factory-runtime-worktrees"
mkdir -p "$RUNTIME_WT_ROOT"
cleanup() {
  git -C "$TMP/repo" worktree remove --force "$RUNTIME_WT_ROOT/detached-wt" 2>/dev/null || true
  rm -rf "$TMP"
}
trap cleanup EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

git init -q --bare "$TMP/origin.git"
git init -q --bare "$TMP/backup.git"
git init -q "$TMP/repo"
cd "$TMP/repo"
git config user.email t@t; git config user.name t; git config commit.gpgsign false
git remote add origin "$TMP/origin.git"
git remote add backup "$TMP/backup.git"
mkdir -p .gc
printf '.gc/\n' > .gitignore
echo one > file; git add -A; git commit -qm one
git branch -M main; git push -q origin main; git fetch -q origin

# Ten worktree backups already on the private remote, as on 2026-10-11.
for i in 0 1 2 3 4 5 6 7 8 9; do
  git push -q backup "HEAD:refs/factory-guard/snapshots/worktree/old-$i"
done

# A dirty working tree, and a runtime worktree whose commit exists nowhere else.
echo secret-draft > NOTES.md
git worktree add -q --detach "$RUNTIME_WT_ROOT/detached-wt" main
(cd "$RUNTIME_WT_ROOT/detached-wt" && echo two > file && git commit -qam two)
DETACHED_SHA=$(git -C "$RUNTIME_WT_ROOT/detached-wt" rev-parse HEAD)

out=$(HOME="$FAKE_HOME" FACTORY_ROOT="$TMP/repo" "$GUARD" 2>&1 || true)

# --- nothing of it reaches origin -----------------------------------------------
[ -z "$(git ls-remote --refs origin 'refs/factory-guard/*')" ] \
  || { printf '%s\n' "$out" >&2; fail "a snapshot was pushed to origin although the repository names a backup remote"; }
git -C "$TMP/origin.git" cat-file -e "$DETACHED_SHA" 2>/dev/null \
  && fail "the worktree's unreviewed commit was pushed to origin"

# --- the working tree is recoverable from the backup remote ---------------------
grep -q "snapshotted 1 working-tree entr(y|ies) to backup refs/factory-guard/snapshots/" <<<"$out" \
  || { printf '%s\n' "$out" >&2; fail "guard did not say the snapshot went to the backup remote"; }
snap=$(git ls-remote --refs backup 'refs/factory-guard/snapshots/*' | awk '{print $2}' | grep -v '/worktree/' || true)
[ -n "$snap" ] || fail "the dated snapshot is not on the backup remote: deleted by the ten worktree backups beside it?"
[ "$(wc -l <<<"$snap")" = "1" ] || fail "expected exactly one dated snapshot on the backup remote"
git fetch -q backup "+$snap:refs/remotes/snap"
grep -q secret-draft <<<"$(git show refs/remotes/snap:NOTES.md 2>/dev/null)" \
  || fail "the untracked file is not recoverable from the backup remote"

# --- so is the worktree's commit, and no worktree backup was pruned -------------
grep -q "FIXED: backed up worktree.*detached-wt.*to backup refs/factory-guard/snapshots/worktree/detached-wt" <<<"$out" \
  || { printf '%s\n' "$out" >&2; fail "guard did not back the worktree up to the backup remote"; }
git -C "$TMP/backup.git" cat-file -e "$DETACHED_SHA" 2>/dev/null \
  || fail "the worktree's commit is not on the backup remote"
[ "$(git ls-remote --refs backup 'refs/factory-guard/snapshots/worktree/*' | wc -l)" = "11" ] \
  || fail "a worktree backup was pruned with the dated snapshots"

echo "OK factory-guard snapshots go to the backup remote, never to origin, when one is named"
