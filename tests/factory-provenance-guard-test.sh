#!/usr/bin/env bash
#
# factory-provenance-guard (af-6eqc, Layer B) is the CI-side structural
# backstop for both rigs: it never sees a real identifier (CI holds no
# secret list -- that would itself hand real PII to a third party), so it
# instead requires every data file under a fixture/seed/test-resource path
# to carry a synthetic-provenance manifest entry pointing at the af-hq2j
# generator, and fails the build on anything unmarked.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/factory-provenance-guard"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

[ -x "$GUARD" ] || fail "$GUARD is not executable"

# ---------------------------------------------------------------------------
# 1. no watched paths at all -- clean
# ---------------------------------------------------------------------------
mkdir -p "$TMP/case1/src"
echo "hello" > "$TMP/case1/src/main.ts"
"$GUARD" --root "$TMP/case1" \
  || fail "clean tree with no watched paths was blocked"

# ---------------------------------------------------------------------------
# 2. an unmarked data file under a watched path fails
# ---------------------------------------------------------------------------
mkdir -p "$TMP/case2/test/fixtures"
printf '{"name": "should not be here unmarked"}\n' > "$TMP/case2/test/fixtures/people.json"
if "$GUARD" --root "$TMP/case2" >"$TMP/case2.out" 2>&1; then
  fail "an unmarked data file under fixtures/ was NOT blocked"
fi
grep -q "unmarked data file" "$TMP/case2.out" \
  || { cat "$TMP/case2.out" >&2; fail "guard did not explain the unmarked-file failure"; }
grep -q "should not be here unmarked" "$TMP/case2.out" \
  && fail "guard printed the data file's contents -- it must only ever report the path"

# ---------------------------------------------------------------------------
# 3. the same file, once recorded in a PROVENANCE.md manifest, passes
# ---------------------------------------------------------------------------
printf 'people.json: synthetic-provenance af-hq2j\n' > "$TMP/case2/test/fixtures/PROVENANCE.md"
"$GUARD" --root "$TMP/case2" \
  || fail "a data file marked in PROVENANCE.md was still blocked"

# ---------------------------------------------------------------------------
# 4. a data-shaped file OUTSIDE a watched directory is not touched
# ---------------------------------------------------------------------------
mkdir -p "$TMP/case4/config"
printf '{"unrelated": true}\n' > "$TMP/case4/config/app.json"
"$GUARD" --root "$TMP/case4" \
  || fail "a data file outside any watched path was blocked"

# ---------------------------------------------------------------------------
# 5. node_modules/target/dist noise under a watched-looking name is excluded
# ---------------------------------------------------------------------------
mkdir -p "$TMP/case5/node_modules/some-pkg/test/fixtures"
printf '{"vendored": true}\n' > "$TMP/case5/node_modules/some-pkg/test/fixtures/data.json"
"$GUARD" --root "$TMP/case5" \
  || fail "a fixture file under node_modules/ was blocked -- vendored code must be excluded"

echo "OK factory-provenance-guard blocks unmarked fixture/seed/test-resource data, passes marked or unrelated files"
