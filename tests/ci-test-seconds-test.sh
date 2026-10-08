#!/usr/bin/env bash
#
# af-mzuprx: the lots of bin/ci-run-tests --shard follow measured seconds,
# and bin/ci-test-seconds writes those seconds from the logs of a run.
# Proven against a throwaway tests/ tree and a fake `gh`: no network.

set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

# --- the list is written from the "tests/x OK 12s" lines of every job -------
cat >"$TMP/gh" <<'FAKE'
#!/usr/bin/env bash
case "$2" in
  *"/workflows/ci.yml/runs?"*) echo 77 ;;
  *"/runs/77/jobs"*) printf '901\n902\n' ;;
  *"/jobs/901/logs") printf '%s\n' \
    '2026-10-08T02:30:00.0000000Z   tests/a-test.py                          OK    100s' \
    '2026-10-08T02:30:01.0000000Z   tests/d-test.sh                          OK      1s' \
    '2026-10-08T02:30:02.0000000Z ci-run-tests: ran 2 test(s), 0 failure(s)' ;;
  *"/jobs/902/logs") printf '%s\n' \
    '2026-10-08T02:30:00.0000000Z   tests/b-test.py                          OK     50s' \
    '2026-10-08T02:30:01.0000000Z   tests/c-test.py                          OK     50s' ;;
  *) echo "unexpected: $*" >&2; exit 1 ;;
esac
FAKE
chmod +x "$TMP/gh"
mkdir -p "$TMP/tree/tests" "$TMP/tree/config"
GH_BIN="$TMP/gh" "$ROOT/bin/ci-test-seconds" --out "$TMP/tree/config/ci-test-seconds.tsv" >/dev/null \
  || fail "ci-test-seconds failed"
got=$(grep -v '^#' "$TMP/tree/config/ci-test-seconds.tsv")
want=$(printf 'tests/a-test.py\t100\ntests/b-test.py\t50\ntests/c-test.py\t50\ntests/d-test.sh\t1')
[ "$got" = "$want" ] || { echo "$got" >&2; fail "the list is not the seconds of the four files of the two jobs"; }
grep -q '^# .*run 77' "$TMP/tree/config/ci-test-seconds.tsv" || fail "the list does not name the run it was read from"
echo "ok   the list is written from the logs of every job of the run"

# --- a test the run left out keeps its seconds (af-5mw6z0) -------------------
# A run of a docs-only pull request does not execute the long tests: read
# alone, it would make them unmeasured, so no longer long, so run every time.
: >"$TMP/tree/tests/long-test.py"
printf '# old\ntests/long-test.py\t300\ntests/gone-test.py\t200\ntests/a-test.py\t7\n' >"$TMP/tree/config/ci-test-seconds.tsv"
GH_BIN="$TMP/gh" "$ROOT/bin/ci-test-seconds" --out "$TMP/tree/config/ci-test-seconds.tsv" >/dev/null \
  || fail "ci-test-seconds failed over an existing list"
got=$(grep -v '^#' "$TMP/tree/config/ci-test-seconds.tsv")
want=$(printf 'tests/a-test.py\t100\ntests/b-test.py\t50\ntests/c-test.py\t50\ntests/d-test.sh\t1\ntests/long-test.py\t300')
[ "$got" = "$want" ] || { echo "$got" >&2; fail "a test the run did not execute lost its seconds, or a deleted one kept them"; }
rm "$TMP/tree/tests/long-test.py"
GH_BIN="$TMP/gh" "$ROOT/bin/ci-test-seconds" --out "$TMP/tree/config/ci-test-seconds.tsv" >/dev/null
echo "ok   a test the run left out keeps its seconds, a deleted test does not"

# --- the lots follow it: longest first, each to the lot that has the least --
for f in a-test.py b-test.py c-test.py d-test.sh e-test.sh; do : >"$TMP/tree/tests/$f"; done   # e is not measured
lot() { FACTORY_ROOT="$TMP/tree" "$ROOT/bin/ci-run-tests" --shard "$1/2" --list | tr '\n' ' '; }
[ "$(lot 1)" = "tests/a-test.py tests/d-test.sh " ] || fail "lot 1/2 is '$(lot 1)': a (100 s) should be alone with one short file"
[ "$(lot 2)" = "tests/b-test.py tests/c-test.py tests/e-test.sh " ] || fail "lot 2/2 is '$(lot 2)': b and c (50 s each) should balance a"
echo "ok   two lots of 101 s each instead of 150 s and 51 s"

# --- without a list, or with a broken one, every file still has its lot ------
printf 'tests/a-test.py\tsoon\nnot a line\n' >"$TMP/tree/config/ci-test-seconds.tsv"
[ "$( { lot 1; lot 2; } | tr ' ' '\n' | sed '/^$/d' | sort | tr '\n' ' ')" = "tests/a-test.py tests/b-test.py tests/c-test.py tests/d-test.sh tests/e-test.sh " ] \
  || fail "a broken list lost or doubled a file"
rm "$TMP/tree/config/ci-test-seconds.tsv"
[ "$( { lot 1; lot 2; } | wc -w)" -eq 5 ] || fail "without a list a file is lost or doubled"
echo "ok   a missing or broken list changes the balance, never the set of files"

# --- the versioned list names real files ------------------------------------
LIST="$ROOT/config/ci-test-seconds.tsv"
[ -r "$LIST" ] || fail "config/ci-test-seconds.tsv is missing: the lots fall back to file size"
known=$(grep -vc '^#' "$LIST")
present=$(grep -v '^#' "$LIST" | cut -f1 | while read -r f; do [ -e "$ROOT/$f" ] && echo "$f"; done | wc -l)
[ "$present" -ge $((known / 2)) ] || fail "more than half of config/ci-test-seconds.tsv names files that are gone: run bin/ci-test-seconds"
echo "ok   the versioned list still names the test files ($present of $known)"

printf 'PASS: lots follow measured seconds\n'
