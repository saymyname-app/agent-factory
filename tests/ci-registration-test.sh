#!/usr/bin/env bash
#
# Every test must be discoverable by CI, or say out loud why it is not.
#
# CI used to enumerate its test files by hand. On 2026-09-16 that list had
# drifted to 7 of 14: operator-context, product-queue, saymyname-po-context,
# saymyname-product-status and saymyname-preview all pass on a bare runner and
# had simply been forgotten. Nothing reported it, because a test that is
# never invoked cannot fail. A new test file was silently unprotected the
# moment it was written, and only a human remembering to edit ci.yml closed
# the gap.
#
# bin/ci-run-tests (P01, af-tltj3) replaced the hand-written list with
# discovery: ci.yml runs every tests/*.sh and tests/*.py file, so adding a
# test is adding a file, not editing ci.yml. That removes the old failure
# mode (a file present but never wired in) but opens a narrower one: a file
# that discovery's glob will not see (wrong extension, wrong directory) is
# just as silently unprotected as the old hand-written list once was. So the
# rule stays enforced rather than remembered: every file directly under
# tests/ is either a tests/*.sh or tests/*.py file (which bin/ci-run-tests
# picks up on its own), or it carries a
#   # ci: local-only — <reason>
# line stating why a GitHub runner cannot run it. Both are visible; silence
# is not an option.

set -Eeuo pipefail
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
CI="$REPO_ROOT/.github/workflows/ci.yml"
RUNNER="$REPO_ROOT/bin/ci-run-tests"
SELF=$(basename -- "${BASH_SOURCE[0]}")

[ -f "$CI" ] || { echo "FAIL: $CI not found" >&2; exit 1; }
[ -x "$RUNNER" ] || { echo "FAIL: $RUNNER missing or not executable -- CI has no discovery step" >&2; exit 1; }
grep -qF "bin/ci-run-tests" "$CI" || {
  echo "FAIL: $CI does not invoke bin/ci-run-tests -- tests would run nowhere" >&2
  exit 1
}

missing=0
for f in "$REPO_ROOT"/tests/*; do
  [ -f "$f" ] || continue
  base=$(basename -- "$f")
  [ "$base" = "$SELF" ] && continue
  if grep -qE '^#[[:space:]]*ci:[[:space:]]*local-only' "$f"; then
    reason=$(grep -m1 -E '^#[[:space:]]*ci:[[:space:]]*local-only' "$f" \
             | sed -E 's/^#[[:space:]]*ci:[[:space:]]*local-only[[:space:]]*(—|--)?[[:space:]]*//')
    [ -n "$reason" ] || {
      echo "FAIL: $base is marked local-only without a reason" >&2; missing=1; continue; }
    printf '  local-only  %-42s %s\n' "$base" "$reason"
    continue
  fi
  case "$base" in
    *.sh|*.py) ;; # bin/ci-run-tests discovers this on its own
    *)
      echo "FAIL: tests/$base runs nowhere -- bin/ci-run-tests only discovers" >&2
      echo "      tests/*.sh and tests/*.py; rename it to match, or mark it" >&2
      echo "      '# ci: local-only — <reason>' if a GitHub runner cannot run it." >&2
      missing=1
      ;;
  esac
done

[ "$missing" = "0" ] || exit 1
echo "OK every test is discoverable by bin/ci-run-tests or declared local-only"
