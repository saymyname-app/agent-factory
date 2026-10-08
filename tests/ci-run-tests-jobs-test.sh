#!/usr/bin/env bash
#
# bin/ci-run-tests --jobs J (af-mzuprx): J test files really run at once, a
# failure among them still fails the run with its output, and every file is
# counted. Proven against a throwaway tests/ tree, without a clock: two
# tests each wait for the other's marker, so they pass only when both are
# running at the same time.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
RUNNER="$ROOT/bin/ci-run-tests"
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/pair/tests" "$TMP/mixed/tests"
for name in a b; do
  other=$([ "$name" = a ] && echo b || echo a)
  cat >"$TMP/pair/tests/$name-test.sh" <<TEST
#!/usr/bin/env bash
: >"\$MEET/$name"
for _ in \$(seq 1 \$((WAIT_TENTHS))); do
  [ -e "\$MEET/$other" ] && exit 0
  sleep 0.1
done
echo "$name never saw $other running"
exit 1
TEST
done

run() {  # root wait-tenths runner-args... -> runner output
  local root=$1 tenths=$2
  shift 2
  rm -rf "$TMP/meet" && mkdir "$TMP/meet"
  env -u CI_RUN_TESTS_JOBS FACTORY_ROOT="$root" MEET="$TMP/meet" WAIT_TENTHS="$tenths" "$RUNNER" "$@" 2>&1
}

out=$(run "$TMP/pair" 300 --jobs 2) || { echo "$out" >&2; fail "--jobs 2 did not run the two files at once"; }
grep -Fq 'ran 2 test(s), 0 failure(s)' <<<"$out" || { echo "$out" >&2; fail "--jobs 2 did not count its two files"; }
echo "ok   --jobs 2 runs two files at the same time"

# One at a time, the first file ends before the second starts.
if out=$(run "$TMP/pair" 5); then
  echo "$out" >&2
  fail "without --jobs the files ran at once: the default is no longer one at a time"
fi
grep -Fq 'never saw' <<<"$out" || { echo "$out" >&2; fail "a failing file's output is not shown"; }
echo "ok   the default runs one file at a time"

out=$(rm -rf "$TMP/meet"; mkdir "$TMP/meet"
  CI_RUN_TESTS_JOBS=2 FACTORY_ROOT="$TMP/pair" MEET="$TMP/meet" WAIT_TENTHS=300 "$RUNNER" 2>&1) \
  || { echo "$out" >&2; fail "CI_RUN_TESTS_JOBS=2 did not run the two files at once"; }
echo "ok   CI_RUN_TESTS_JOBS sets the default"

# A failure among files run at once fails the run, names the file, shows its
# output, and the others are still run and counted.
for i in 1 2 3 4 5; do
  printf '#!/usr/bin/env bash\nexit 0\n' >"$TMP/mixed/tests/pass-$i-test.sh"
done
printf '#!/usr/bin/env bash\necho "the reason it broke"\nexit 3\n' >"$TMP/mixed/tests/broken-test.sh"
if out=$(run "$TMP/mixed" 1 --jobs 3); then
  echo "$out" >&2
  fail "a failing file did not fail a --jobs run"
fi
grep -Fq 'ran 6 test(s), 1 failure(s)' <<<"$out" || { echo "$out" >&2; fail "the files of a --jobs run are not all counted"; }
grep -Fq 'FAILED: tests/broken-test.sh' <<<"$out" || { echo "$out" >&2; fail "the failing file is not named"; }
grep -Fq 'the reason it broke' <<<"$out" || { echo "$out" >&2; fail "the failing file's output is not shown"; }
[ "$(grep -c ' OK ' <<<"$out")" -eq 5 ] || { echo "$out" >&2; fail "the passing files do not each have their line"; }
echo "ok   a failure among files run at once fails the run and is shown"

for bad in "" 0 -1 two; do
  if run "$TMP/mixed" 1 --jobs $bad >/dev/null; then fail "--jobs '$bad' was accepted"; fi
done
echo "ok   a malformed --jobs is refused"

printf 'PASS: ci-run-tests --jobs runs files at once and still reports each one\n'
