#!/usr/bin/env bash
#
# factory-guard must bring the live root up to what was merged.
#
# On 2026-09-17 pr-autopilot merged a sentinel fix (#87) and the campaign kept
# failing with the old code: the live root IS the runtime, and nothing pulled
# it. It sat 4, then 5 commits behind until a human looked.
#
# The guard may only ever fast-forward: never over tracked edits in progress,
# never on a diverged or drifted branch, and never in --check-only.

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

# Someone else merges to origin/main.
git clone -q "$TMP/origin.git" "$TMP/other"
merge_upstream() {
  ( cd "$TMP/other" && git config user.email o@o && git config user.name o \
    && git config commit.gpgsign false && git pull -q origin main \
    && echo "$1" >> merged && git add -A && git commit -qm "$1" && git push -q origin HEAD:main )
}
run_guard() { FACTORY_ROOT="$TMP/repo" "$GUARD" "$@" 2>&1 || true; }

# --- check-only reports and touches nothing --------------------------------
merge_upstream first
before=$(git rev-parse HEAD)
out=$(run_guard --check-only)
grep -q "1 merged commit(s) not running yet" <<<"$out" \
  || { printf '%s\n' "$out" >&2; fail "--check-only did not report the root as behind"; }
[ "$(git rev-parse HEAD)" = "$before" ] || fail "--check-only moved HEAD"

# --- tracked edits in progress are never pulled over ------------------------
echo wip >> file
out=$(run_guard)
grep -q "not pulling over them" <<<"$out" \
  || { printf '%s\n' "$out" >&2; fail "guard did not refuse to pull over tracked edits"; }
[ "$(git rev-parse HEAD)" = "$before" ] || fail "guard pulled over tracked edits"
git checkout -q -- file

# --- a clean, behind root is fast-forwarded ---------------------------------
out=$(run_guard)
grep -q "fast-forwarded the live root by 1 merged commit(s)" <<<"$out" \
  || { printf '%s\n' "$out" >&2; fail "guard did not fast-forward a clean root"; }
[ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || fail "root is not at origin/main"
[ -f merged ] || fail "the merged file is not in the working tree"

out=$(run_guard)
grep -q "live-root-sync — running the merged 'main'" <<<"$out" \
  || { printf '%s\n' "$out" >&2; fail "guard did not report an up-to-date root"; }

# --- a diverged root is reported, never forced ------------------------------
echo local > local-only; git add -A; git commit -qm local
merge_upstream second
diverged=$(git rev-parse HEAD)
out=$(run_guard)
grep -q "has diverged from origin/main" <<<"$out" \
  || { printf '%s\n' "$out" >&2; fail "guard did not report a diverged root"; }
[ "$(git rev-parse HEAD)" = "$diverged" ] || fail "guard moved a diverged root"

# --- rig checkouts: same contract (section 3b) -----------------------------
git init -q --bare "$TMP/rig-origin.git"
git clone -q "$TMP/rig-origin.git" "$TMP/rig-seed" 2>/dev/null
( cd "$TMP/rig-seed" && git config user.email s@s && git config user.name s \
  && git config commit.gpgsign false && echo a > a && git add -A && git commit -qm a \
  && git branch -M dev && git push -q origin dev )
echo "rigs/" >> .git/info/exclude
mkdir -p rigs && git clone -q -b dev "$TMP/rig-origin.git" rigs/r1
( cd "$TMP/rig-seed" && echo b >> a && git commit -qam b && git push -q origin dev )
rig_before=$(git -C rigs/r1 rev-parse HEAD)

out=$(run_guard --check-only)
grep -q "rig-sync — r1: 1 merged commit(s) not checked out yet (check-only)" <<<"$out" \
  || { printf '%s\n' "$out" >&2; fail "--check-only did not report the rig as behind"; }
[ "$(git -C rigs/r1 rev-parse HEAD)" = "$rig_before" ] || fail "--check-only moved the rig"

echo wip >> rigs/r1/a
out=$(run_guard)
grep -q "rig-sync — r1: 1 merged commit(s) not checked out yet: tracked files are being edited" <<<"$out" \
  || { printf '%s\n' "$out" >&2; fail "guard did not refuse to pull a rig over tracked edits"; }
[ "$(git -C rigs/r1 rev-parse HEAD)" = "$rig_before" ] || fail "guard pulled a rig over tracked edits"
git -C rigs/r1 checkout -q -- a

out=$(run_guard)
grep -q "fast-forwarded rig r1 by 1 merged commit(s)" <<<"$out" \
  || { printf '%s\n' "$out" >&2; fail "guard did not fast-forward a clean rig"; }
[ "$(git -C rigs/r1 rev-parse HEAD)" = "$(git -C rigs/r1 rev-parse origin/dev)" ] || fail "rig is not at origin/dev"

printf 'PASS: factory-guard live-root and rig sync\n'
