#!/usr/bin/env bash
#
# factory-guard must notice work that exists only in the WORKING TREE.
#
# This is not hypothetical. On 2026-09-16 the guard printed
#   "✓ work-backup — nothing exists only on this machine"
# while 20 entries existed nowhere but that disk, ADR-0015 and ADR-0016 among
# them — both Accepted. The check compared refs/heads/ to origin and never
# looked at the working tree at all. It was believed, because a green check
# is believed.
#
# The subtle part, and the reason this test exists: the fix must not "help" by
# committing. The guard runs unattended against a live root whose HEAD, index
# and working tree belong to whoever is working in it. A snapshot that moved
# HEAD, staged files, or left the real index dirty would be a worse failure
# than the one it replaces. So this test asserts the repo is byte-for-byte
# unchanged afterwards, not just that the snapshot exists.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/factory-guard"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

# --- a throwaway repo, fully pushed: the guard must be quiet ----------------
git init -q --bare "$TMP/origin.git"
git init -q "$TMP/repo"
cd "$TMP/repo"
git config user.email t@t; git config user.name t; git config commit.gpgsign false
git remote add origin "$TMP/origin.git"
mkdir -p .gc   # the guard keeps its pinned-branch state here
# Mirror the live root: .gc/ is host-local Gas City state and is ignored
# there too. The guard writes its own pinned-branch file into it.
printf '.gc/\nignored-dir/\n*.log\n' > .gitignore
echo one > file; git add -A; git commit -qm one
git branch -M main; git push -q origin main; git fetch -q origin

out=$(FACTORY_ROOT="$TMP/repo" "$GUARD" --check-only 2>&1 || true)
grep -q "working tree clean" <<<"$out" || {
  printf '%s\n' "$out" >&2; fail "guard did not report a clean tree as clean"; }

# --- now dirty it exactly the way 2026-09-16 was dirty ----------------------
echo two >> file                      # modified, tracked
echo adr > ADR-0015.md                # untracked, NOT ignored — the lost class
mkdir -p ignored-dir; echo x > ignored-dir/junk
echo noise > debug.log                # ignored — must stay out of scope

out=$(FACTORY_ROOT="$TMP/repo" "$GUARD" --check-only 2>&1 || true)
grep -q "exist only in this working tree" <<<"$out" \
  || { printf '%s\n' "$out" >&2; fail "guard did not see the dirty working tree"; }
grep -q "ADR-0015.md" <<<"$out" || fail "guard did not name the untracked file"
grep -q "debug.log" <<<"$out"     && fail "guard flagged a .gitignore'd file"
grep -q "ignored-dir" <<<"$out"   && fail "guard flagged a .gitignore'd directory"
grep -q "nothing exists only" <<<"$out" \
  && fail "guard still claimed nothing exists only on this machine"
grep -q "^UNRESOLVED" <<<"$out" || fail "--check-only did not fail on a dirty tree"

# --- --check-only must change absolutely nothing ---------------------------
head_before=$(git rev-parse HEAD)
idx_before=$(git status --porcelain --untracked-files=all)
FACTORY_ROOT="$TMP/repo" "$GUARD" --check-only >/dev/null 2>&1 || true
[ "$(git rev-parse HEAD)" = "$head_before" ] || fail "--check-only moved HEAD"
[ "$(git status --porcelain --untracked-files=all)" = "$idx_before" ] \
  || fail "--check-only changed the working tree"
[ -z "$(git ls-remote --refs origin 'refs/factory-guard/*')" ] \
  || fail "--check-only pushed a snapshot"

# --- the default run must SNAPSHOT, and still touch nothing ----------------
out=$(FACTORY_ROOT="$TMP/repo" "$GUARD" 2>&1 || true)
grep -q "snapshotted" <<<"$out" \
  || { printf '%s\n' "$out" >&2; fail "guard did not snapshot the dirty tree"; }

snap=$(git ls-remote --refs origin 'refs/factory-guard/snapshots/*' | awk '{print $2}')
[ -n "$snap" ] || fail "no snapshot ref reached origin"
[ "$(wc -l <<<"$snap")" = "1" ] || fail "expected exactly one snapshot ref"

[ "$(git rev-parse HEAD)" = "$head_before" ] || fail "the snapshot moved HEAD"
[ "$(git status --porcelain --untracked-files=all)" = "$idx_before" ] \
  || fail "the snapshot dirtied the real index or working tree"

# --- and the snapshot must actually CONTAIN the work, not just exist -------
git fetch -q origin "$snap:refs/remotes/snap" 2>/dev/null \
  || git fetch -q origin "+$snap:refs/remotes/snap"
grep -q adr <<<"$(git show "refs/remotes/snap:ADR-0015.md" 2>/dev/null)" \
  || fail "the untracked file is not recoverable from the snapshot"
grep -q two <<<"$(git show "refs/remotes/snap:file" 2>/dev/null)" \
  || fail "the modified file is not recoverable from the snapshot"
git show "refs/remotes/snap:debug.log" >/dev/null 2>&1 \
  && fail "the snapshot swept in a .gitignore'd file"

# --- a clean tree afterwards must go quiet again ---------------------------
git add -A; git commit -qm two; git push -q origin main; git fetch -q origin
out=$(FACTORY_ROOT="$TMP/repo" "$GUARD" --check-only 2>&1 || true)
grep -q "exist only in this working tree" <<<"$out" \
  && fail "guard still complains about a committed-and-pushed tree"
grep -q "working tree clean" <<<"$out" || fail "guard did not go quiet"

echo "OK factory-guard sees the working tree"
