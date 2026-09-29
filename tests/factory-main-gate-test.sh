#!/usr/bin/env bash
#
# factory-main-gate must actually block a push that lands a broken commit on
# `main`, and must not add friction anywhere else.
#
# This is not hypothetical: on 2026-09-16 commit 8d92c13 landed directly on
# `main` and broke referential integrity between
# a product's DECISIONS.md and its product config's decision_refs (both
# retired since) — a check the Cockpit V1 test suite (retired since) already had (13
# failing cases). Nothing forced that suite to run before the commit reached
# `main`. This test builds a throwaway repo with its own tiny, controllable
# "CI" (one fake test file the fixture can make pass or fail) and proves:
#
#   1. a push to main whose guarded test fails is rejected, and the bad
#      commit never reaches the remote's main;
#   2. a push to main whose guarded test passes goes through;
#   3. a push to a non-main branch is never gated, even with a failing test —
#      the gate must not add friction to ordinary branch work or PRs.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GATE="$REPO_ROOT/bin/factory-main-gate"
HOOK="$REPO_ROOT/.githooks/pre-push"
RUNNER="$REPO_ROOT/bin/ci-run-tests"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

[ -x "$GATE" ] || fail "$GATE is not executable"
[ -x "$HOOK" ] || fail "$HOOK is not executable"
[ -x "$RUNNER" ] || fail "$RUNNER is not executable"

# --- a throwaway repo with an origin, the real hook, and a fake CI ----------
git init -q --bare "$TMP/origin.git"
git init -q "$TMP/repo"
cd "$TMP/repo"
git config user.email t@t; git config user.name t; git config commit.gpgsign false
git remote add origin "$TMP/origin.git"

mkdir -p .githooks bin tests .github/workflows
cp "$HOOK" .githooks/pre-push
cp "$GATE" bin/factory-main-gate
cp "$RUNNER" bin/ci-run-tests
chmod +x .githooks/pre-push bin/factory-main-gate bin/ci-run-tests
git config core.hooksPath .githooks

cat > .github/workflows/ci.yml <<'YAML'
name: Fixture CI
on: [push]
jobs:
  tests:
    steps:
      - run: bin/ci-run-tests
YAML

# The fixture test: passes unless FIXTURE_SHOULD_FAIL exists in the repo.
# factory-main-gate discovers this through bin/ci-run-tests, not by name.
cat > tests/fixture-test.py <<'PY'
import pathlib, sys
if pathlib.Path("FIXTURE_SHOULD_FAIL").exists():
    print("referential integrity broken: decision_refs points at nothing")
    sys.exit(1)
print("OK")
PY

echo one > file
git add -A
git commit -qm "initial (test passes)"
git branch -M main
git push -q origin main
[ -x "$GATE" ]  # sanity: still present after checkout

# ---------------------------------------------------------------------------
# 1. a broken commit must never reach origin's main
# ---------------------------------------------------------------------------
touch FIXTURE_SHOULD_FAIL
git add -A
git commit -qm "break referential integrity (like 8d92c13)"
if git push origin main >"$TMP/push1.out" 2>&1; then
  fail "push of a commit that fails the guarded test was NOT rejected"
fi
grep -q "factory-main-gate: BLOCKED" "$TMP/push1.out" \
  || { cat "$TMP/push1.out" >&2; fail "gate did not explain why it blocked the push"; }

remote_head=$(git ls-remote origin refs/heads/main | cut -f1)
local_broken=$(git rev-parse HEAD)
[ "$remote_head" != "$local_broken" ] \
  || fail "the broken commit reached origin/main despite the rejection"

# ---------------------------------------------------------------------------
# 2. once fixed, the same branch pushes cleanly
# ---------------------------------------------------------------------------
rm -f FIXTURE_SHOULD_FAIL
git add -A
git commit -qm "fix referential integrity"
git push -q origin main \
  || fail "a push whose guarded test passes was rejected"
remote_head=$(git ls-remote origin refs/heads/main | cut -f1)
[ "$remote_head" = "$(git rev-parse HEAD)" ] \
  || fail "the fixed commit did not reach origin/main"

# ---------------------------------------------------------------------------
# 3. a non-main branch is never gated, even while broken
# ---------------------------------------------------------------------------
git checkout -qb feat/some-work
touch FIXTURE_SHOULD_FAIL
git add -A
git commit -qm "wip, deliberately broken, not going to main"
git push -q origin feat/some-work \
  || fail "gate blocked a push to a non-main branch -- it must never do that"

echo "OK factory-main-gate blocks broken pushes to main, allows everything else"
