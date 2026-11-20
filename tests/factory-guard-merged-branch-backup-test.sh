#!/usr/bin/env bash
#
# factory-guard's work-backup pushed to origin every local branch absent from
# it and not in origin/main. A squash-merged branch is both, once GitHub
# deletes it on merge: the guard re-created merged branches on origin minutes
# after their merge (do-work/af-abozjt, PR #917, 2026-11-20, af-tdpbg1).
# A branch whose head a merged PR of it holds is not backed up; one with no
# such PR still is, and so is one whose PR state cannot be read.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/factory-guard"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

git init -q --bare "$TMP/origin.git"
git init -q "$TMP/repo"
cd "$TMP/repo"
git config user.email t@t; git config user.name t; git config commit.gpgsign false
git remote add origin "$TMP/origin.git"
mkdir -p .gc
printf '.gc/\n' > .gitignore
echo one > file; git add -A; git commit -qm one
git branch -M main; git push -q origin main; git fetch -q origin

branch_with_commit() {
  git checkout -qb "$1" main
  echo "$1" > "$1"; git add -A; git commit -qm "$1"
  git checkout -q main
}
branch_with_commit squash-merged
branch_with_commit behind-pr-head
git checkout -q behind-pr-head
echo more > more; git add -A; git commit -qm more
PR_HEAD=$(git rev-parse HEAD)
git reset -q --hard HEAD~1
git checkout -q main
branch_with_commit unmerged
branch_with_commit unreadable

mkdir -p "$TMP/bin"
cat > "$TMP/bin/gh" <<EOF
#!/usr/bin/env bash
case " \$* " in
  *" pr list --head squash-merged --state merged "*) echo $(git rev-parse squash-merged) ;;
  *" pr list --head behind-pr-head --state merged "*) echo $PR_HEAD ;;
  *" pr list --head unmerged --state merged "*) ;;
  *) exit 1 ;;
esac
EOF
chmod +x "$TMP/bin/gh"

out=$(PATH="$TMP/bin:$PATH" HOME="$TMP/home" FACTORY_ROOT="$TMP/repo" "$GUARD" 2>&1 || true)
on_origin() { git ls-remote --exit-code --heads origin "$1" >/dev/null 2>&1; }

on_origin squash-merged && { printf '%s\n' "$out" >&2; fail "a branch whose head is a merged PR's head was pushed back to origin"; }
on_origin behind-pr-head && fail "a branch whose head is before a merged PR's head was pushed back to origin"
on_origin unmerged || { printf '%s\n' "$out" >&2; fail "a branch with no merged PR was not backed up"; }
on_origin unreadable || fail "a branch whose PR state could not be read was not backed up"
echo "PASS: factory-guard backs up only branches no merged PR holds"
