#!/usr/bin/env bash
#
# factory-pii-guard (af-6eqc, Layer A) must block a push carrying a real
# identifier from the local dev-DB list, allow everything else through, and
# never echo the list or a matched value in its own output -- the list is
# gitignored on purpose (.gc/ is excluded repo-wide) because the value it
# holds must never leave this machine, including into this guard's stdout.
#
# This builds a throwaway repo with its own origin and the real hook wired
# up via core.hooksPath, exactly like tests/factory-main-gate-test.sh.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/factory-pii-guard"
HOOK="$REPO_ROOT/.githooks/pre-push"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

[ -x "$GUARD" ] || fail "$GUARD is not executable"
[ -x "$HOOK" ] || fail "$HOOK is not executable"

git init -q --bare "$TMP/origin.git"
git init -q "$TMP/repo"
cd "$TMP/repo"
git config user.email t@t; git config user.name t; git config commit.gpgsign false
git remote add origin "$TMP/origin.git"

mkdir -p .githooks bin
cp "$HOOK" .githooks/pre-push
cp "$GUARD" bin/factory-pii-guard
chmod +x .githooks/pre-push bin/factory-pii-guard
git config core.hooksPath .githooks

echo one > file
git add -A
git commit -qm "initial"
git branch -M main
git push -q origin main

# ---------------------------------------------------------------------------
# 1. no identifier list at all -- never blocks, but must say INACTIVE and
#    exit 3, not exit 0 -- a bare "exit 0, nothing to check" reads as "pass"
#    to any caller that only checks for zero, which is exactly how this
#    containment layer went uncaught-inactive for a year (af-ox44d).
# ---------------------------------------------------------------------------
echo two >> file
git add -A
git commit -qm "ordinary change, no list present"
git push -q origin main \
  || fail "push was blocked with no identifier list present"

inactive_status=0
inactive_out=$("$PWD/bin/factory-pii-guard" --repo-root "$PWD" 2>&1) || inactive_status=$?
[ "$inactive_status" -eq 3 ] \
  || fail "guard exited $inactive_status with no identifier list present, want 3 (INACTIVE)"
printf '%s' "$inactive_out" | grep -q "INACTIVE" \
  || fail "guard did not report INACTIVE with no identifier list present: $inactive_out"

# ---------------------------------------------------------------------------
# 2. a listed identifier reaching the outgoing diff is blocked
# ---------------------------------------------------------------------------
mkdir -p .gc/pii-guard
printf 'RealPerson McRealname\nreal.person@example.com\n' > .gc/pii-guard/real-identifiers.local

echo "RealPerson McRealname" >> file
git add file
git commit -qm "accidentally leaked a real identifier"
if git push origin main >"$TMP/push1.out" 2>&1; then
  fail "push carrying a listed real identifier was NOT rejected"
fi
grep -q "factory-pii-guard: BLOCKED" "$TMP/push1.out" \
  || { cat "$TMP/push1.out" >&2; fail "guard did not explain why it blocked the push"; }
grep -qF "RealPerson McRealname" "$TMP/push1.out" \
  && fail "guard printed the matched real identifier -- it must never do that"

remote_head=$(git ls-remote origin refs/heads/main | cut -f1)
local_leaked=$(git rev-parse HEAD)
[ "$remote_head" != "$local_leaked" ] \
  || fail "the commit carrying a real identifier reached origin/main despite the rejection"

# ---------------------------------------------------------------------------
# 3. once scrubbed, the branch pushes cleanly again
# ---------------------------------------------------------------------------
sed -i 's/RealPerson McRealname/Synthetic Testperson/' file
git add file
git commit -qm "scrub the real identifier, use synthetic data instead"
git push -q origin main \
  || fail "a push with the real identifier scrubbed was rejected"
remote_head=$(git ls-remote origin refs/heads/main | cut -f1)
[ "$remote_head" = "$(git rev-parse HEAD)" ] \
  || fail "the scrubbed commit did not reach origin/main"

# ---------------------------------------------------------------------------
# 4. the guard's own stdout never contains the list contents either way
# ---------------------------------------------------------------------------
out=$("$PWD/bin/factory-pii-guard" --repo-root "$PWD" 2>&1 || true)
printf '%s' "$out" | grep -qF "real.person@example.com" \
  && fail "guard's clean-run output leaked the identifier list contents"

echo "OK factory-pii-guard blocks a real identifier leaving the machine, allows everything else, and never echoes the list"
