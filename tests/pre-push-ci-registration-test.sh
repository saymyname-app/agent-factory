#!/usr/bin/env bash
#
# 2026-09-24: a new tests/pr-autopilot-reconcile-cache-test.sh landed on a PR
# branch without being wired into .github/workflows/ci.yml. factory-main-gate
# never caught it -- it only runs for pushes that land a ref on `main` (by
# design, per its own header) -- so CI only discovered the gap after the
# round trip to GitHub, on a feature-branch PR. bin/ci-run-tests (P01,
# af-tltj3) later removed the hand-written ci.yml list in favor of
# discovering every tests/*.sh and tests/*.py file, so an ordinary new test
# no longer needs a ci.yml edit at all -- but a file the discovery glob
# cannot see (wrong extension, wrong directory) is exactly as silently
# unprotected as the old hand-written list once was. This proves the
# pre-push hook still runs tests/ci-registration-test.sh on EVERY push, to
# any branch, and blocks a push carrying such a file, before it ever leaves
# the machine.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
HOOK="$REPO_ROOT/.githooks/pre-push"
REG_TEST="$REPO_ROOT/tests/ci-registration-test.sh"
RUNNER="$REPO_ROOT/bin/ci-run-tests"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

[ -x "$HOOK" ] || fail "$HOOK is not executable"
[ -x "$REG_TEST" ] || fail "$REG_TEST is not executable"
[ -x "$RUNNER" ] || fail "$RUNNER is not executable"

# --- a throwaway repo with an origin and the real hook + registration test --
git init -q --bare "$TMP/origin.git"
git init -q "$TMP/repo"
cd "$TMP/repo"
git config user.email t@t; git config user.name t; git config commit.gpgsign false
git remote add origin "$TMP/origin.git"

mkdir -p .githooks bin tests .github/workflows
cp "$HOOK" .githooks/pre-push
cp "$REG_TEST" tests/ci-registration-test.sh
cp "$RUNNER" bin/ci-run-tests
chmod +x .githooks/pre-push tests/ci-registration-test.sh bin/ci-run-tests
git config core.hooksPath .githooks

cat > .github/workflows/ci.yml <<'YAML'
name: Fixture CI
on: [push]
jobs:
  tests:
    steps:
      - run: bin/ci-run-tests
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
# 1. a new test file discovery cannot see -- wrong extension, not declared
#    local-only -- must be rejected on a non-main branch. Nothing needs to be
#    "wired into ci.yml" anymore, so the gap this now guards is a file that
#    bin/ci-run-tests' tests/*.sh|*.py glob would silently skip.
# ---------------------------------------------------------------------------
cat > tests/new-unregistered-test <<'SH'
#!/usr/bin/env bash
echo OK
SH
chmod +x tests/new-unregistered-test
git add -A
git commit -qm "add a test file with an extension discovery cannot see"
if git push origin feat/some-branch >"$TMP/push1.out" 2>&1; then
  fail "push of an undiscoverable test file was NOT rejected on a non-main branch"
fi
grep -q "pre-push: BLOCKED -- tests/ci-registration-test.sh failed" "$TMP/push1.out" \
  || { cat "$TMP/push1.out" >&2; fail "hook did not explain why it blocked the push"; }

remote_head=$(git ls-remote origin refs/heads/feat/some-branch | cut -f1)
local_unregistered=$(git rev-parse HEAD)
[ "$remote_head" != "$local_unregistered" ] \
  || fail "the undiscoverable-test commit reached origin despite the rejection"

# ---------------------------------------------------------------------------
# 2. renaming it to a discoverable extension (or marking it local-only) lets
#    the same branch push, with no ci.yml edit
# ---------------------------------------------------------------------------
git mv tests/new-unregistered-test tests/new-unregistered-test.sh
git add -A
git commit -qm "rename so bin/ci-run-tests discovers it -- no ci.yml edit needed"
git push -q origin feat/some-branch \
  || fail "a push with the discoverable extension was rejected"
remote_head=$(git ls-remote origin refs/heads/feat/some-branch | cut -f1)
[ "$remote_head" = "$(git rev-parse HEAD)" ] \
  || fail "the fixed commit did not reach origin"

echo "OK pre-push blocks any branch's push when a new test file is not discoverable by CI"
