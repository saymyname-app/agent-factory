#!/usr/bin/env bash
# ci: local-only — drives the live `gc` binary on a fresh city
#
# af-9gxs9a: tests/orders-validate-test.sh failed the 2026-10-20 nightly on
# convoy-advance, an order paused through city.toml `[orders] skip`
# (af-tys6ff): gc hides a skipped order, so `gc order show` answers "not
# found". The check now reports a skipped order instead of validating it.
# Both cases run it against a fresh city with one order of each kind; the
# skipped one is malformed on purpose (a condition trigger with no exec=, the
# af-1isbx shape), so the second case proves the skip list is what spares it.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
CHECK="$ROOT/tests/orders-validate-test.sh"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc jq python3; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

TEST_TMPDIR=$(mktemp -d /tmp/af-9gxs9a-orders-skip.XXXXXX)
trap 'rm -rf -- "$TEST_TMPDIR"' EXIT

# GC_CITY/GC_DOLT_*/... would redirect gc at the live Factory city;
# GC_HOME keeps the fresh city out of the live supervisor's registry.
run_clean() {
  env \
    -u GC_DOLT_HOST -u GC_DOLT_PORT -u GC_DOLT_DATABASE -u GC_DOLT_PROJECT_ID -u GC_DOLT_USER \
    -u GC_SESSION_ID -u GC_SESSION_NAME -u GC_ALIAS -u GC_AGENT \
    -u GC_BEAD_ID -u GC_ROOT_BEAD_ID -u GC_CONTINUATION_GROUP \
    -u GC_CITY -u GC_CITY_PATH -u GC_CITY_RUNTIME_DIR -u GC_BEADS_SCOPE_ROOT -u GC_DIR \
    GC_HOME="$TEST_TMPDIR/gc-home" \
    "$@"
}

# Decor, built once: a fresh city with a valid order and a malformed one,
# the malformed one listed in [orders] skip.
DECOR="$TEST_TMPDIR/decor"
run_clean gc init \
  --template minimal --default-provider codex --skip-provider-readiness --no-start --yes \
  --name af-9gxs9a-orders-skip "$DECOR" >/dev/null
cat >"$DECOR/orders/kept.toml" <<'EOF'
[order]
description = "valid order the check must validate"
trigger = "cooldown"
interval = "1h"
exec = "true"
EOF
cat >"$DECOR/orders/paused.toml" <<'EOF'
[order]
description = "malformed order: condition trigger with no exec"
trigger = "condition"
interval = "1h"
check = "true"
EOF
cp "$DECOR/city.toml" "$DECOR/city.toml.no-skip"
printf '\n[orders]\nskip = ["paused"]\n' >>"$DECOR/city.toml"

# 1. A skipped order is reported, not validated; the rest still is.
CASE="$TEST_TMPDIR/case-skipped"
cp -a "$DECOR" "$CASE"
out=$(run_clean env ORDERS_VALIDATE_CITY="$CASE" bash "$CHECK" 2>&1) \
  || fail "a skipped order must not fail the check: $out"
grep -qxF "SKIPPED (city.toml [orders] skip): paused" <<<"$out" \
  || fail "the check must name the skipped order, got: $out"
grep -qF "PASS: every orders/*.toml not skipped in city.toml (1) validates" <<<"$out" \
  || fail "the check must validate the one order not skipped, got: $out"

# 2. The same malformed order, not in the skip list, still fails the check.
CASE="$TEST_TMPDIR/case-not-skipped"
cp -a "$DECOR" "$CASE"
cp "$CASE/city.toml.no-skip" "$CASE/city.toml"
out=$(run_clean env ORDERS_VALIDATE_CITY="$CASE" bash "$CHECK" 2>&1) \
  && fail "a malformed order outside the skip list must fail the check, got: $out"
grep -qF "FAIL: gc order show paused" <<<"$out" \
  || fail "the check must fail on the malformed order, got: $out"

echo "PASS: orders-validate-test.sh reports an order in [orders] skip and still fails a malformed order outside it"
