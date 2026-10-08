#!/usr/bin/env bash
#
# bin/ci-run-tests runs one battery at a time on a host (af-7m7ymg): a second
# battery started while one runs waits its turn, says whose battery it waits
# for, and both pass; past its bounded wait it gives up with exit 75 and runs
# nothing. Proven against throwaway tests/ trees and a lock file of its own,
# without a clock: the first battery's test holds until this script has seen
# the second one wait.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
RUNNER="$ROOT/bin/ci-run-tests"
TMP=$(mktemp -d)
LOCK="$TMP/host.lock"
cleanup() {
  [ -s "$TMP/leak.pid" ] && kill "$(cat "$TMP/leak.pid")" 2>/dev/null
  [ -n "${holder_pid:-}" ] && kill "$holder_pid" 2>/dev/null
  rm -rf -- "$TMP"
}
trap cleanup EXIT

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

until_true() {  # description command... -> waits up to 120 s for the command to succeed
  local what=$1 _
  shift
  for _ in $(seq 1 1200); do
    "$@" 2>/dev/null && return 0
    sleep 0.1
  done
  fail "timed out waiting for: $what"
}

battery() {  # root runner-args... ; extra environment comes from the caller
  local root=$1
  shift
  env -u CI_RUN_TESTS_JOBS CI_RUN_TESTS_HOST_LOCK_FILE="$LOCK" FACTORY_ROOT="$root" \
    BUSY="$TMP/busy" RELEASE="$TMP/release" RAN="$TMP/ran" "$RUNNER" "$@"
}

# A test that fails when another battery's test runs beside it, and holds its
# battery open until the file $RELEASE exists.
mkdir -p "$TMP/ran"
for name in first second third; do
  mkdir -p "$TMP/$name/tests"
  cat >"$TMP/$name/tests/alone-test.sh" <<TEST
#!/usr/bin/env bash
: >"\$RAN/$name"
mkdir "\$BUSY" 2>/dev/null || { echo "$name ran beside another battery's test"; exit 1; }
for _ in \$(seq 1 1200); do [ -e "\$RELEASE" ] && break; sleep 0.1; done
rmdir "\$BUSY"
[ -e "\$RELEASE" ] || { echo "$name was never released"; exit 1; }
TEST
done

GITHUB_ACTIONS='' battery "$TMP/first" >"$TMP/first.out" 2>&1 &
first_pid=$!
until_true "the first battery to start its test" test -d "$TMP/busy"

GITHUB_ACTIONS='' battery "$TMP/second" >"$TMP/second.out" 2>&1 &
second_pid=$!
until_true "the second battery to say it waits" grep -Fq 'waiting for the battery of' "$TMP/second.out"
grep -Fq "waiting for the battery of $TMP/first " "$TMP/second.out" \
  || { cat "$TMP/second.out" >&2; fail "the waiting line does not name the battery it waits for"; }
[ ! -e "$TMP/ran/second" ] || fail "the second battery started its tests while the first was running"
echo "ok   a second battery waits and names the one it waits for"

# The wait is bounded: past it, nothing runs and the exit code is not a test failure's.
status=0
out=$(GITHUB_ACTIONS='' CI_RUN_TESTS_HOST_WAIT=0 battery "$TMP/third" 2>&1) || status=$?
[ "$status" -eq 75 ] || { echo "$out" >&2; fail "a battery past its wait exited $status, expected 75"; }
grep -Fq 'NOT RUN' <<<"$out" || { echo "$out" >&2; fail "a battery past its wait does not say it did not run"; }
[ ! -e "$TMP/ran/third" ] || fail "a battery past its wait ran its tests anyway"
echo "ok   past its bounded wait a battery runs nothing and exits 75"

# --list and a GitHub runner never wait.
[ "$(GITHUB_ACTIONS='' CI_RUN_TESTS_HOST_WAIT=0 battery "$TMP/third" --list)" = "tests/alone-test.sh" ] \
  || fail "--list waited for the host or lost its list"
echo "ok   --list does not wait"

: >"$TMP/release"
wait "$first_pid" || { cat "$TMP/first.out" >&2; fail "the first battery failed"; }
wait "$second_pid" || { cat "$TMP/second.out" >&2; fail "the second battery failed after its wait"; }
for name in first second; do
  grep -Fq 'ran 1 test(s), 0 failure(s)' "$TMP/$name.out" || { cat "$TMP/$name.out" >&2; fail "the $name battery did not run its test"; }
done
echo "ok   two batteries started at once run one after the other and both pass"

# A process a test leaves behind does not keep the line; a ci-run-tests started
# from inside a battery (a test of the runner) does not wait for its own battery.
mkdir -p "$TMP/outer/tests" "$TMP/inner/tests"
printf '#!/usr/bin/env bash\nexit 0\n' >"$TMP/inner/tests/quick-test.sh"
cat >"$TMP/outer/tests/leaves-a-process-test.sh" <<'TEST'
#!/usr/bin/env bash
setsid sleep 300 >/dev/null 2>&1 </dev/null &
echo $! >"$LEAK"
TEST
cat >"$TMP/outer/tests/runs-the-runner-test.sh" <<'TEST'
#!/usr/bin/env bash
out=$(FACTORY_ROOT="$INNER" CI_RUN_TESTS_HOST_WAIT=0 "$RUNNER" 2>&1) || { echo "$out"; exit 1; }
grep -Fq 'ran 1 test(s), 0 failure(s)' <<<"$out" || { echo "$out"; exit 1; }
TEST
out=$(GITHUB_ACTIONS='' LEAK="$TMP/leak.pid" INNER="$TMP/inner" RUNNER="$RUNNER" battery "$TMP/outer" 2>&1) \
  || { echo "$out" >&2; fail "a runner started from inside a battery waited for that battery"; }
grep -Fq 'ran 2 test(s), 0 failure(s)' <<<"$out" || { echo "$out" >&2; fail "the outer battery did not run its two files"; }
echo "ok   a ci-run-tests started from inside a battery does not wait for it"
kill -0 "$(cat "$TMP/leak.pid")" 2>/dev/null || fail "the left-behind process is gone: the next check would prove nothing"
flock --nonblock "$LOCK" true || fail "a process left behind by a test still holds the host"
echo "ok   a process a test leaves behind does not keep the line"

# On a GitHub runner the lock is not taken: one run per machine.
( exec 9>"$LOCK"; flock 9; : >"$TMP/held"; exec sleep 300 ) >/dev/null 2>&1 &
holder_pid=$!
until_true "the stand-in battery to hold the host" test -e "$TMP/held"
out=$(GITHUB_ACTIONS=true CI_RUN_TESTS_HOST_WAIT=0 battery "$TMP/inner" 2>&1) \
  || { echo "$out" >&2; fail "a GitHub runner waited for the host lock"; }
grep -Fq 'ran 1 test(s), 0 failure(s)' <<<"$out" || { echo "$out" >&2; fail "the GitHub runner battery did not run"; }
echo "ok   a GitHub runner does not take the host lock"

if GITHUB_ACTIONS='' CI_RUN_TESTS_HOST_WAIT=soon battery "$TMP/inner" >/dev/null 2>&1; then
  fail "a malformed CI_RUN_TESTS_HOST_WAIT was accepted"
fi
echo "ok   a malformed CI_RUN_TESTS_HOST_WAIT is refused"

printf 'PASS: ci-run-tests runs one battery at a time on a host\n'
