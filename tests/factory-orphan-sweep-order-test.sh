#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime and an isolated Dolt server

# W08 (A6b, Spec af-3s8prq, stories 11-13): Gas City's core `orphan-sweep`
# order drops an in_progress claim held by any assignee it doesn't
# recognize -- including a po-agent/* operator session's claim on a
# planning ticket, so a parallel session can take the same ticket minutes
# later (a claim silently dropped after 5-10 minutes, per the Spec problem
# statement). orders/factory-orphan-sweep.toml replaces it with
# bin/factory-orphan-sweep, a copy of the same upstream script plus one
# guard: a po-agent/* claim or a planning-plane bead's claim is treated as
# owned and survives the sweep; every other orphaned delivery claim is
# still released exactly as upstream would release it.
#
# This test proves, against fixture beads in an isolated test city (never
# the live Factory):
#   1. the order is discoverable and deterministic through gc's own order
#      validation, and the core orphan-sweep order is skipped in city.toml;
#   2. a po-agent/* claim and a planning-plane bead's claim survive a sweep;
#   3. a claim by an unknown delivery actor is released;
#   4. bin/factory-orphan-sweep's content still matches the upstream script
#      it was copied from -- a `gc` upgrade that changes that script must
#      fail this test, not silently drift out of sync.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc bd jq git sha256sum; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

TEST_TMPDIR=$(mktemp -d /tmp/af-w08-factory-orphan-sweep.XXXXXX)
TEST_CITY="$TEST_TMPDIR/city"
mkdir -p "$TEST_CITY"

cleanup() {
  status=$?
  trap - EXIT
  if [ "${KEEP_TEST_CITY:-0}" = 1 ]; then
    echo "test city preserved at $TEST_CITY" >&2
  else
    rm -rf -- "$TEST_TMPDIR"
  fi
  exit "$status"
}
trap cleanup EXIT

# The worker process may carry the live Factory's identity, Dolt and
# city-scoping variables. All must not escape into this isolated test city
# -- GC_CITY/GC_CITY_PATH/GC_BEADS_SCOPE_ROOT override cwd-based city
# discovery no matter what `cd` says (same guard as
# tests/backup-freshness-order-test.sh, live incident af-ize6u).
run_clean() {
  env \
    -u GC_DOLT_HOST -u GC_DOLT_PORT -u GC_DOLT_DATABASE -u GC_DOLT_PROJECT_ID -u GC_DOLT_USER \
    -u GC_SESSION_ID -u GC_SESSION_NAME -u GC_ALIAS -u GC_AGENT \
    -u GC_BEAD_ID -u GC_ROOT_BEAD_ID -u GC_CONTINUATION_GROUP \
    -u GC_CITY -u GC_CITY_PATH -u GC_CITY_RUNTIME_DIR -u GC_BEADS_SCOPE_ROOT -u GC_DIR \
    -u GC_TRIGGER_BEAD_ID -u GC_TRIGGER_WORK_BEAD_ID -u GC_TRIGGER_BEAD_STORE_REF -u GC_TRIGGER_WORK_STORE_REF \
    -u GC_BEADS \
    -u BEADS_ACTOR -u BEADS_HOLDER_TOKEN -u BEADS_DOLT_AUTO_START -u BEADS_DOLT_SYNC_CLI_REMOTES \
    -u BEADS_DOLT_SERVER_PORT -u BEADS_ROUTING_MODE -u BD_DOLT_SYNC_CLI_REMOTES -u BEADS_BACKUP_ENABLED \
    "$@"
}

# 1a. bin/factory-orphan-sweep's own order is discoverable and deterministic
#     in the live Factory config, and the core orphan-sweep order it
#     replaces is skipped there.
live_order=$(run_clean gc order show factory-orphan-sweep --city "$ROOT" --json)
jq -e --arg source "$ROOT/orders/factory-orphan-sweep.toml" \
      --arg exec "$ROOT/bin/factory-orphan-sweep" '
  .ok == true and
  .order.type == "exec" and
  .order.trigger == "condition" and
  .order.interval == "5m" and
  .order.exec == $exec and
  .order.enabled == true and
  .order.source == $source
' >/dev/null <<<"$live_order" || fail "factory-orphan-sweep Order is not discoverable and deterministic"

run_clean gc order show orphan-sweep --city "$ROOT" --json >/dev/null 2>&1 \
  && fail "core orphan-sweep order should be skipped in city.toml, but gc order show still finds it"

[ -x "$ROOT/bin/factory-orphan-sweep" ] || fail "$ROOT/bin/factory-orphan-sweep must be executable"

# 1b. The order loads through gc's own order validation (a fresh city, since
#     the live Factory's city.toml intentionally skips the core order this
#     script is a copy of -- its own order.list/order.show must still
#     resolve cleanly from a bare init).
run_clean gc init \
  --template minimal --default-provider codex --skip-provider-readiness --no-start --yes \
  --name af-w08-factory-orphan-sweep "$TEST_CITY" >/dev/null

# 2. Pin the hash of the upstream script this file was copied from, so a
#    `gc` upgrade that changes it fails this test instead of silently
#    drifting out of sync with the guard added below. Located dynamically
#    (never a hardcoded cache path, which embeds a content-addressed repo
#    hash that changes on any pack update) via the still-present core order
#    in this fresh test city.
UPSTREAM_ORDER_SOURCE=$(run_clean gc order show orphan-sweep --city "$TEST_CITY" --json \
  | jq -r '.order.source')
[ -n "$UPSTREAM_ORDER_SOURCE" ] && [ -f "$UPSTREAM_ORDER_SOURCE" ] \
  || fail "could not locate the upstream orphan-sweep order definition"
UPSTREAM_PACK_DIR=$(dirname -- "$(dirname -- "$UPSTREAM_ORDER_SOURCE")")
UPSTREAM_SCRIPT="$UPSTREAM_PACK_DIR/assets/scripts/orphan-sweep.sh"
[ -f "$UPSTREAM_SCRIPT" ] || fail "upstream orphan-sweep.sh not found at $UPSTREAM_SCRIPT"

PINNED_UPSTREAM_SHA256="006ad97d2a0a0ee4967b2f7599c4bd48e9b5a6dc7ef119f62bf2e23a150417ff"
ACTUAL_UPSTREAM_SHA256=$(sha256sum "$UPSTREAM_SCRIPT" | awk '{print $1}')
[ "$ACTUAL_UPSTREAM_SHA256" = "$PINNED_UPSTREAM_SHA256" ] || fail \
  "gc's core orphan-sweep.sh changed upstream (was $PINNED_UPSTREAM_SHA256, now $ACTUAL_UPSTREAM_SHA256) -- re-diff it against bin/factory-orphan-sweep, update the guard if needed, and re-pin this hash"

# 3. Functional: fixture beads over the guard.
run_clean bd create "po-agent claim" --directory "$TEST_CITY" --id awfos-po1 \
  --metadata '{"gc.plane":"delivery"}' >/dev/null
run_clean bd create "planning bead claim" --directory "$TEST_CITY" --id awfos-plan1 \
  --metadata '{"gc.plane":"planning"}' >/dev/null
run_clean bd create "orphaned delivery claim" --directory "$TEST_CITY" --id awfos-orphan1 \
  --metadata '{"gc.plane":"delivery"}' >/dev/null
run_clean bd update awfos-po1 --directory "$TEST_CITY" --status in_progress --assignee "po-agent/abc123" >/dev/null
run_clean bd update awfos-plan1 --directory "$TEST_CITY" --status in_progress --assignee "unknown-actor" >/dev/null
run_clean bd update awfos-orphan1 --directory "$TEST_CITY" --status in_progress --assignee "unknown-delivery-actor" >/dev/null

(cd "$TEST_CITY" && run_clean "$ROOT/bin/factory-orphan-sweep") \
  || fail "bin/factory-orphan-sweep exited non-zero"

po_status=$(run_clean bd show awfos-po1 --directory "$TEST_CITY" --json | jq -r 'if type=="array" then .[0] else . end | .status')
plan_status=$(run_clean bd show awfos-plan1 --directory "$TEST_CITY" --json | jq -r 'if type=="array" then .[0] else . end | .status')
orphan_status=$(run_clean bd show awfos-orphan1 --directory "$TEST_CITY" --json | jq -r 'if type=="array" then .[0] else . end | .status')
orphan_assignee=$(run_clean bd show awfos-orphan1 --directory "$TEST_CITY" --json | jq -r 'if type=="array" then .[0] else . end | .assignee // ""')

[ "$po_status" = "in_progress" ] || fail "a po-agent/* claim must survive the sweep, got status=$po_status"
[ "$plan_status" = "in_progress" ] || fail "a planning-plane bead's claim must survive the sweep, got status=$plan_status"
[ "$orphan_status" != "in_progress" ] || fail "a claim by an unknown delivery actor must be released, still in_progress"
[ -z "$orphan_assignee" ] || fail "a released claim must have no assignee, got assignee=$orphan_assignee"

echo "PASS: factory-orphan-sweep keeps po-agent/* and planning-plane claims, releases genuinely orphaned delivery claims, and its upstream copy is pinned"
