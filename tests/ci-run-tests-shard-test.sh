#!/usr/bin/env bash
#
# bin/ci-run-tests --shard I/N: the lots Factory CI runs side by side
# (.github/workflows/ci.yml) hold every discovered test exactly once. A file
# in no lot would run nowhere and could not fail; a file in two would only
# cost time. The workflow must also ask for every lot of the number it names.

set -Eeuo pipefail
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
RUNNER="$REPO_ROOT/bin/ci-run-tests"
CI="$REPO_ROOT/.github/workflows/ci.yml"
fail() { echo "FAIL: $*" >&2; exit 1; }

all=$("$RUNNER" --list)
[ -n "$all" ] || fail "no test discovered"

for n in 1 3 4 7; do
  union=""
  for i in $(seq 1 "$n"); do
    lot=$("$RUNNER" --shard "$i/$n" --list)
    union+="$lot"$'\n'
  done
  sorted=$(printf '%s' "$union" | sed '/^$/d' | sort)
  [ "$sorted" = "$all" ] || fail "the $n lots together are not the discovered list"
  [ -z "$(printf '%s\n' "$sorted" | uniq -d)" ] || fail "a file is in two of the $n lots"
done
echo "ok   every file is in exactly one lot, for 1, 3, 4 and 7 lots"

# No lot is left with nearly everything: the largest is at most twice the smallest.
counts=$(for i in 1 2 3 4; do "$RUNNER" --shard "$i/4" --list | wc -l; done | sort -n)
[ "$(echo "$counts" | tail -1)" -le "$(( $(echo "$counts" | head -1) * 2 ))" ] || fail "lots of very unequal size: $(echo $counts)"
echo "ok   four lots of comparable size ($(echo $counts))"

# The order of the arguments does not matter, and a lot is a subset.
[ "$("$RUNNER" --list --shard 2/4)" = "$("$RUNNER" --shard 2/4 --list)" ] || fail "--list --shard differs from --shard --list"

for bad in "" "0/4" "5/4" "2" "a/b" "1/0"; do
  if "$RUNNER" --shard $bad --list >/dev/null 2>&1; then fail "--shard '$bad' was accepted"; fi
done
echo "ok   a malformed or out-of-range lot is refused"

# The workflow runs every lot of the number it names, and lot 1 keeps the
# name the ruleset and bin/pr-autopilot require.
lots=$(sed -n 's/^  LOTS: *\([0-9][0-9]*\) *$/\1/p' "$CI")
[ -n "$lots" ] || fail "$CI does not name its number of lots (env LOTS)"
matrix=$(sed -n 's/^ *lot: *\[\(.*\)\] *$/\1/p' "$CI" | tr -d ' ')
[ "$matrix" = "$(seq -s, 1 "$lots")" ] || fail "$CI runs lots [$matrix] but names $lots lots: a lot would run nowhere"
grep -qF 'bin/ci-run-tests --shard "${{ matrix.lot }}/$LOTS"' "$CI" || fail "$CI does not run its matrix lot out of LOTS"
grep -qF "matrix.lot == 1 && 'Tests'" "$CI" || fail "$CI no longer names lot 1 \"Tests\", the required status check"
grep -qF 'startswith("Lot ")' "$CI" || fail "the job named Tests no longer waits for the other lots"
echo "ok   the workflow runs lots 1..$lots and lot 1 is the required check"
