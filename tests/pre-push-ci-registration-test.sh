#!/usr/bin/env bash
#
# 2026-09-24: a new tests/pr-autopilot-reconcile-cache-test.sh landed on a PR
# branch without being wired into .github/workflows/ci.yml. factory-main-gate
# never caught it -- it only runs for pushes that land a ref on `main` (by
# design, per its own header) -- so CI only discovered the gap after the
# round trip to GitHub, on a feature-branch PR. This proves the pre-push hook
# now runs tests/ci-registration-test.sh on EVERY push, to any branch, and
# blocks one that is missing a registration, before it ever leaves the
# machine.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
HOOK="$REPO_ROOT/.githooks/pre-push"
REG_TEST="$REPO_ROOT/tests/ci-registration-test.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

[ -x "$HOOK" ] || fail "$HOOK is not executable"
[ -x "$REG_TEST" ] || fail "$REG_TEST is not executable"

# --- a throwaway repo with an origin and the real hook + registration test --
git init -q --bare "$TMP/origin.git"
git init -q "$TMP/repo"
cd "$TMP/repo"
git config user.email t@t; git config user.name t; git config commit.gpgsign false
git remote add origin "$TMP/origin.git"

mkdir -p .githooks tests .github/workflows
cp "$HOOK" .githooks/pre-push
cp "$REG_TEST" tests/ci-registration-test.sh
chmod +x .githooks/pre-push tests/ci-registration-test.sh
git config core.hooksPath .githooks

cat > .github/workflows/ci.yml <<'YAML'
name: Fixture CI
on: [push]
jobs:
  tests:
    steps:
      - run: bash tests/registered-test.sh
YAML
cat > tests/registered-test.sh <<'SH'
#!/usr/bin/env bash
echo OK
SH
chmod +x tests/registered-test.sh

echo one > file
git add -A
git commit -qm "initial (registration clean)"
git branch -M feat/some-branch
git push -q origin feat/some-branch \
  || fail "a clean push to a non-main branch was rejected"

# ---------------------------------------------------------------------------
# 1. a new tests/*.sh file, NOT wired into ci.yml and NOT declared
#    local-only, must be rejected on a non-main branch -- the exact gap
#    that let tests/pr-autopilot-reconcile-cache-test.sh through twice.
# ---------------------------------------------------------------------------
cat > tests/new-unregistered-test.sh <<'SH'
#!/usr/bin/env bash
echo OK
SH
chmod +x tests/new-unregistered-test.sh
git add -A
git commit -qm "add a test file, forget to register it (the actual 2026-09-24 mistake)"
if git push origin feat/some-branch >"$TMP/push1.out" 2>&1; then
  fail "push of an unregistered test file was NOT rejected on a non-main branch"
fi
grep -q "pre-push: BLOCKED -- tests/ci-registration-test.sh failed" "$TMP/push1.out" \
  || { cat "$TMP/push1.out" >&2; fail "hook did not explain why it blocked the push"; }

remote_head=$(git ls-remote origin refs/heads/feat/some-branch | cut -f1)
local_unregistered=$(git rev-parse HEAD)
[ "$remote_head" != "$local_unregistered" ] \
  || fail "the unregistered-test commit reached origin despite the rejection"

# ---------------------------------------------------------------------------
# 2. registering it (or declaring it local-only) lets the same branch push
# ---------------------------------------------------------------------------
sed -i 's#- run: bash tests/registered-test.sh#- run: bash tests/registered-test.sh\n      - run: bash tests/new-unregistered-test.sh#' .github/workflows/ci.yml
git add -A
git commit -qm "register the new test in ci.yml"
git push -q origin feat/some-branch \
  || fail "a push with the registration fixed was rejected"
remote_head=$(git ls-remote origin refs/heads/feat/some-branch | cut -f1)
[ "$remote_head" = "$(git rev-parse HEAD)" ] \
  || fail "the fixed commit did not reach origin"

echo "OK pre-push blocks any branch's push when a new test file is not registered in CI"
