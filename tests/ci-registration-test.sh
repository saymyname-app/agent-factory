#!/usr/bin/env bash
#
# Every test must be registered in CI, or say out loud why it is not.
#
# CI enumerated its test files by hand. On 2026-09-16 that list had drifted to
# 7 of 14: operator-context, product-queue, saymyname-po-context,
# saymyname-product-status and saymyname-preview all pass on a bare runner and
# had simply been forgotten. Nothing reported it, because a test that is never
# invoked cannot fail. A new test file was silently unprotected the moment it
# was written, and only a human remembering to edit ci.yml closed the gap.
#
# So the rule is now enforced rather than remembered: a file in tests/ is
# either named in .github/workflows/ci.yml, or it carries a
#   # ci: local-only — <reason>
# line stating why a GitHub runner cannot run it. Both are visible; silence
# is not an option.

set -Eeuo pipefail
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
CI="$REPO_ROOT/.github/workflows/ci.yml"
SELF=$(basename -- "${BASH_SOURCE[0]}")

[ -f "$CI" ] || { echo "FAIL: $CI not found" >&2; exit 1; }

missing=0
for f in "$REPO_ROOT"/tests/*.sh "$REPO_ROOT"/tests/*.py; do
  [ -e "$f" ] || continue
  base=$(basename -- "$f")
  [ "$base" = "$SELF" ] && continue
  grep -qF "tests/$base" "$CI" && continue
  if grep -qE '^#[[:space:]]*ci:[[:space:]]*local-only' "$f"; then
    reason=$(grep -m1 -E '^#[[:space:]]*ci:[[:space:]]*local-only' "$f" \
             | sed -E 's/^#[[:space:]]*ci:[[:space:]]*local-only[[:space:]]*(—|--)?[[:space:]]*//')
    [ -n "$reason" ] || {
      echo "FAIL: $base is marked local-only without a reason" >&2; missing=1; continue; }
    printf '  local-only  %-42s %s\n' "$base" "$reason"
    continue
  fi
  echo "FAIL: tests/$base runs nowhere — add it to ci.yml, or mark it" >&2
  echo "      '# ci: local-only — <reason>' if a GitHub runner cannot run it." >&2
  missing=1
done

[ "$missing" = "0" ] || exit 1
echo "OK every test is either registered in CI or declared local-only"
