#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime and an isolated Dolt server

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc bd jq; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

# FACTORY_ROOT doubles as both "where the marked tests are looked for" and
# "which city to write beads/mail into" (bin/local-only-tests cd's there and
# never passes --city), so the test city itself has to carry the fake tests/.
TEST_TMPDIR=$(mktemp -d /tmp/af-o13-local-only-tests.XXXXXX)
TEST_CITY="$TEST_TMPDIR/city"
mkdir -p "$TEST_CITY"
# Isolated tmux socket dir and a stub `codex` ahead of PATH: gc mail send
# --notify (via escalation-door) starts the configured named session on
# demand even with the reconciler off, and without a stub that session
# execs the REAL codex CLI under a tmux server on the shared socket dir --
# a live, untorn-down process (live incident: this test's own
# af-o13-local-only-tests orphan held the live escalation-door flock for
# 40+ min, root-caused 2026-09-28; see tests/backup-freshness-order-test.sh
# for the fuller writeup).
TMUX_TMPDIR="$TEST_TMPDIR/tmux"
STUB_BIN="$TEST_TMPDIR/stubbin"
mkdir -p "$TMUX_TMPDIR" "$STUB_BIN"
cat >"$STUB_BIN/codex" <<'STUB'
#!/usr/bin/env bash
exit 0
STUB
chmod +x "$STUB_BIN/codex"

cleanup() {
  status=$?
  trap - EXIT
  for sock in "$TMUX_TMPDIR"/tmux-*/*; do
    [ -S "$sock" ] || continue
    tmux -S "$sock" kill-server >/dev/null 2>&1 || true
  done
  # Wait for anything matched to actually die before rm -rf: a signalled-
  # but-still-exiting Dolt process can hold its data dir open long enough
  # to leave files behind (silent, but a slow leak across CI runs).
  pkill -f -- "$TEST_TMPDIR" >/dev/null 2>&1 || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    pgrep -f -- "$TEST_TMPDIR" >/dev/null 2>&1 || break
    sleep 0.3
  done
  pkill -9 -f -- "$TEST_TMPDIR" >/dev/null 2>&1 || true
  if [ "${KEEP_TEST_CITY:-0}" = 1 ]; then
    echo "test city preserved at $TEST_CITY" >&2
  else
    rm -rf -- "$TEST_TMPDIR"
  fi
  exit "$status"
}
trap cleanup EXIT

# GC_CITY/GC_CITY_PATH/GC_BEADS_SCOPE_ROOT override cwd-based city discovery
# and will silently redirect every `gc`/`bd` call in this test at the LIVE
# Factory city instead of the isolated one (live incident during this
# ticket's own development: af-ize6u).
run_clean() {
  env \
    -u GC_DOLT_HOST -u GC_DOLT_PORT -u GC_DOLT_DATABASE -u GC_DOLT_PROJECT_ID -u GC_DOLT_USER \
    -u GC_SESSION_ID -u GC_SESSION_NAME -u GC_ALIAS -u GC_AGENT \
    -u GC_BEAD_ID -u GC_ROOT_BEAD_ID -u GC_CONTINUATION_GROUP \
    -u GC_CITY -u GC_CITY_PATH -u GC_CITY_RUNTIME_DIR -u GC_BEADS_SCOPE_ROOT -u GC_DIR \
    -u GC_TRIGGER_BEAD_ID -u GC_TRIGGER_WORK_BEAD_ID -u GC_TRIGGER_BEAD_STORE_REF -u GC_TRIGGER_WORK_STORE_REF \
    PATH="$STUB_BIN:$PATH" \
    TMUX_TMPDIR="$TMUX_TMPDIR" \
    "$@"
}

# 1. The order itself is discoverable and deterministic.
order=$(run_clean gc order show local-only-tests --city "$ROOT" --json)
jq -e --arg source "$ROOT/orders/local-only-tests.toml" --arg exec "$ROOT/bin/local-only-tests --quiet" '
  .ok == true and
  .order.type == "exec" and
  .order.trigger == "cron" and
  .order.schedule == "0 4 * * *" and
  .order.exec == $exec and
  .order.timeout == "300s" and
  .order.enabled == true and
  .order.source == $source
' >/dev/null <<<"$order" || fail "local-only-tests Order is not discoverable and deterministic"

# 2. Functional: an injected failing test must file a bead and page the Mayor.
run_clean gc init \
  --template minimal --default-provider codex --skip-provider-readiness --no-start --yes \
  --name af-o13-local-only-tests "$TEST_CITY" >/dev/null

mkdir -p "$TEST_CITY/tests"
cat >"$TEST_CITY/tests/build-basic-fail-fast-runtime-test.sh" <<'EOF'
#!/usr/bin/env bash
# ci: local-only — fake passing test
exit 0
EOF
cat >"$TEST_CITY/tests/factory-watchdog-order-test.sh" <<'EOF'
#!/usr/bin/env bash
# ci: local-only — fake failing test
echo "FAIL: injected failure for local-only-tests-order-test.sh" >&2
exit 1
EOF
chmod +x "$TEST_CITY/tests/"*.sh

# ESCALATION_DOOR_BIN points at the real repo since the fresh minimal city
# has no bin/ of its own; ESCALATION_DOOR_LOCK_FILE keeps this test from
# waiting on (or colliding with) the live Factory's own escalation-door lock.
run_clean env FACTORY_ROOT="$TEST_CITY" ESCALATION_DOOR_BIN="$ROOT/bin/escalation-door" \
  ESCALATION_DOOR_LOCK_FILE="$TEST_CITY/.escalation-door.lock" \
  "$ROOT/bin/local-only-tests" --quiet \
  && fail "local-only-tests should exit non-zero when a test fails"

FILED=$(run_clean gc --city "$TEST_CITY" bd list --status open --json \
  | jq '[.[] | select(.metadata["gc.source"] == "local-only-tests")] | length')
[ "${FILED:-0}" = 1 ] || fail "expected exactly one local-only-tests bead, got ${FILED:-0}"

PAGED=$(run_clean gc --city "$TEST_CITY" mail inbox mayor --json \
  | jq '[.messages[] | select(.subject | startswith("Escalation (Mayor first): "))] | length')
[ "${PAGED:-0}" -ge 1 ] || fail "expected the Mayor to be paged via escalation-door"

echo "PASS: local-only-tests files a bead and pages the Mayor on a failing local-only test"
