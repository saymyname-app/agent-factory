#!/usr/bin/env bash
#
# bin/ci-run-tests (category P, af-8cfygl): a test file that ends leaving a
# process it started alive fails, names it, and what it left is killed; a
# test that stops what it starts passes. On 10/11/2026 a cockpit test left one
# synthetic door that never answers per run: 16 were alive on the host after
# a day, 23 on 11/11 (af-i9llwm). Proven against a throwaway tests/ tree.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
RUNNER="$ROOT/bin/ci-run-tests"
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/leaks/tests" "$TMP/clean/tests"
# The leak as it was: a child with an environment replaced, in a session of
# its own, its output elsewhere, that the test never stops.
cat >"$TMP/leaks/tests/leaks-test.sh" <<'TEST'
#!/usr/bin/env bash
env -i "$(command -v setsid)" "$(command -v sleep)" 600 >/dev/null 2>&1 </dev/null &
echo $! >"$PIDS/leaked"
exit 0
TEST
cat >"$TMP/clean/tests/clean-test.sh" <<'TEST'
#!/usr/bin/env bash
sleep 600 >/dev/null 2>&1 </dev/null &
kill $!
wait $! 2>/dev/null
exit 0
TEST

run() {  # root -> runner output
  env -u CI_RUN_TESTS_JOBS HOST_SLOTS_DIR="$TMP/slots" HOST_SLOTS=1 FACTORY_ROOT="$1" PIDS="$TMP" "$RUNNER" 2>&1
}

if out=$(run "$TMP/leaks"); then
  echo "$out" >&2
  fail "a test that left a process alive passed"
fi
grep -Fq 'FAILED: tests/leaks-test.sh' <<<"$out" || { echo "$out" >&2; fail "the test that left a process is not named"; }
grep -Fq 'left these processes alive' <<<"$out" || { echo "$out" >&2; fail "the process left alive is not shown"; }
leaked=$(cat "$TMP/leaked")
for _ in $(seq 1 50); do
  kill -0 "$leaked" 2>/dev/null || break
  sleep 0.1
done
if kill -0 "$leaked" 2>/dev/null; then
  kill -KILL "$leaked" 2>/dev/null
  fail "the process the test left is still alive"
fi
echo "ok   a test that leaves a process alive fails, and the process is killed"

out=$(run "$TMP/clean") || { echo "$out" >&2; fail "a test that stops what it starts failed"; }
echo "ok   a test that stops what it starts passes"

printf 'PASS: ci-run-tests fails a test that leaves a process alive and kills it\n'
