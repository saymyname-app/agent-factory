#!/usr/bin/env bash
#
# af-wnj692: bin/ci-run-tests gives every test a throwaway XDG_RUNTIME_DIR
# and fails one that still reaches bin/escalation-door's default lock file
# there. Proves, against a throwaway tests/ tree: a test that creates the
# default lock is reported FAIL and names ESCALATION_DOOR_LOCK_FILE; a test
# that does not is OK; and the directory a test sees is never the caller's
# own XDG_RUNTIME_DIR.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
RUNNER="$ROOT/bin/ci-run-tests"
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/clean/tests" "$TMP/offender/tests" "$TMP/host-runtime"
cat >"$TMP/clean/tests/quiet-test.sh" <<'TEST'
#!/usr/bin/env bash
printf '%s\n' "$XDG_RUNTIME_DIR" >"$SEEN_RUNTIME_DIR"
TEST
cat >"$TMP/offender/tests/default-lock-test.sh" <<'TEST'
#!/usr/bin/env bash
: >"${ESCALATION_DOOR_LOCK_FILE:-$XDG_RUNTIME_DIR/agent-factory-escalation-door.lock}"
TEST

run() {  # root -> runner output; a caller-set lock override must not hide an offender
  FACTORY_ROOT=$1 XDG_RUNTIME_DIR="$TMP/host-runtime" SEEN_RUNTIME_DIR="$TMP/seen" \
    ESCALATION_DOOR_LOCK_FILE="$TMP/caller.lock" "$RUNNER" 2>&1
}

out=$(run "$TMP/clean") || { echo "$out" >&2; fail "a test that never touches the door lock must pass"; }
[[ $(cat "$TMP/seen") != "$TMP/host-runtime" ]] \
  || fail "the test ran with the caller's own XDG_RUNTIME_DIR"

if out=$(run "$TMP/offender"); then
  echo "$out" >&2
  fail "a test that reaches the default door lock must fail the run"
fi
grep -Fq 'ESCALATION_DOOR_LOCK_FILE' <<<"$out" \
  || { echo "$out" >&2; fail "the failure must name ESCALATION_DOOR_LOCK_FILE"; }
[[ ! -e "$TMP/host-runtime/agent-factory-escalation-door.lock" && ! -e "$TMP/caller.lock" ]] \
  || fail "the offending test wrote a lock outside its throwaway runtime dir"

printf 'PASS: ci-run-tests keeps tests off the host escalation-door lock\n'
