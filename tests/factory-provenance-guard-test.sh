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
# 3. the same file, once recorded in a PROVENANCE.md manifest with a
#    matching sha256, passes
# ---------------------------------------------------------------------------
hash_of() { sha256sum "$1" | awk '{print $1}'; }

HASH=$(hash_of "$TMP/case2/test/fixtures/people.json")
printf 'people.json: synthetic-provenance af-hq2j sha256:%s\n' "$HASH" \
  > "$TMP/case2/test/fixtures/PROVENANCE.md"
"$GUARD" --root "$TMP/case2" \
  || fail "a data file marked in PROVENANCE.md with a matching sha256 was still blocked"

# ---------------------------------------------------------------------------
# 3b. an old-format entry (no sha256) is not proof -- self-attestation alone
#     must not pass
# ---------------------------------------------------------------------------
mkdir -p "$TMP/case3b/test/fixtures"
printf '{"name": "no hash on this claim"}\n' > "$TMP/case3b/test/fixtures/people.json"
printf 'people.json: synthetic-provenance af-hq2j\n' > "$TMP/case3b/test/fixtures/PROVENANCE.md"
if "$GUARD" --root "$TMP/case3b" >"$TMP/case3b.out" 2>&1; then
  fail "a manifest entry with no sha256 binding was accepted as proof"
fi
grep -q "no sha256 binding" "$TMP/case3b.out" \
  || { cat "$TMP/case3b.out" >&2; fail "guard did not explain the missing-hash rejection"; }

# ---------------------------------------------------------------------------
# 3c. a stale entry -- file content changed after the manifest was written
#     -- must be rejected, not trusted on filename+keyword alone
# ---------------------------------------------------------------------------
mkdir -p "$TMP/case3c/test/fixtures"
printf '{"name": "original"}\n' > "$TMP/case3c/test/fixtures/people.json"
HASH=$(hash_of "$TMP/case3c/test/fixtures/people.json")
printf 'people.json: synthetic-provenance af-hq2j sha256:%s\n' "$HASH" \
  > "$TMP/case3c/test/fixtures/PROVENANCE.md"
printf '{"name": "swapped after marking"}\n' > "$TMP/case3c/test/fixtures/people.json"
if "$GUARD" --root "$TMP/case3c" >"$TMP/case3c.out" 2>&1; then
  fail "a stale sha256 attestation (file changed after marking) was accepted"
fi
grep -q "does not match the file's current content" "$TMP/case3c.out" \
  || { cat "$TMP/case3c.out" >&2; fail "guard did not explain the stale-attestation rejection"; }

# ---------------------------------------------------------------------------
# 3d. Maven's real convention, src/test/resources (not hyphenated
#     test-resources), is watched too
# ---------------------------------------------------------------------------
mkdir -p "$TMP/case3d/src/test/resources"
printf '{"name": "maven-style path"}\n' > "$TMP/case3d/src/test/resources/people.json"
if "$GUARD" --root "$TMP/case3d" >"$TMP/case3d.out" 2>&1; then
  fail "an unmarked data file under src/test/resources (Maven convention) was NOT blocked"
fi
grep -q "unmarked data file" "$TMP/case3d.out" \
  || { cat "$TMP/case3d.out" >&2; fail "guard did not flag src/test/resources as watched"; }

# ---------------------------------------------------------------------------
# 3e. --root with no value fails as a usage error, not an unbound-variable
#     crash
# ---------------------------------------------------------------------------
set +e
"$GUARD" --root >"$TMP/case3e.out" 2>&1
case3e_rc=$?
set -e
[ "$case3e_rc" -eq 2 ] \
  || { cat "$TMP/case3e.out" >&2; fail "--root with a missing value should exit 2 (usage error), got $case3e_rc"; }
grep -qi "requires a value" "$TMP/case3e.out" \
  || { cat "$TMP/case3e.out" >&2; fail "--root with a missing value did not report a clean usage error"; }

# ---------------------------------------------------------------------------
# 3f. a filename containing a regex metacharacter (the extension dot) must
#     match only its own exact manifest entry, never a same-length
#     lookalike -- an unescaped basename would treat "." as "any char"
# ---------------------------------------------------------------------------
mkdir -p "$TMP/case3f/test/fixtures"
printf '{"name": "a"}\n' > "$TMP/case3f/test/fixtures/a.json"
HASH=$(hash_of "$TMP/case3f/test/fixtures/a.json")
# A decoy line, listed first, that an unescaped "a.json" pattern (dot =
# "any char") would also match -- with a WRONG hash. If the guard is not
# escaping the basename, it matches this line first and reports a stale
# attestation even though the real, correctly escaped entry for a.json
# (with the right hash) follows right after.
printf 'aXjson: synthetic-provenance af-hq2j sha256:0000000000000000000000000000000000000000000000000000000000000000\na.json: synthetic-provenance af-hq2j sha256:%s\n' \
  "$HASH" > "$TMP/case3f/test/fixtures/PROVENANCE.md"
"$GUARD" --root "$TMP/case3f" \
  || fail "a.json's own correctly matching manifest entry was shadowed by an unescaped-dot decoy line"

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
