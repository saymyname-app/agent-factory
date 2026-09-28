#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime and an isolated Dolt server

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc bd jq git; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

TEST_CITY=$(mktemp -d /tmp/af-o13-backup-freshness.XXXXXX)
ARCHIVE=$(mktemp -d /tmp/af-o13-backup-freshness-archive.XXXXXX)
cleanup() {
  status=$?
  trap - EXIT
  if [ "${KEEP_TEST_CITY:-0}" = 1 ]; then
    echo "test city preserved at $TEST_CITY, archive at $ARCHIVE" >&2
  else
    rm -rf -- "$TEST_CITY" "$ARCHIVE"
  fi
  exit "$status"
}
trap cleanup EXIT

# The worker process may carry the live Factory's hosted-Dolt, identity, AND
# city-scoping variables. All three families must not escape into this
# isolated local city: an exec order never runs as an agent session (so
# sender-identity resolution must behave like production), and critically
# GC_CITY/GC_CITY_PATH/GC_BEADS_SCOPE_ROOT override cwd-based city discovery
# -- leaving any of them set points every `gc`/`bd` call in this test at the
# LIVE Factory city instead of $TEST_CITY, no matter what `cd` says
# (live incident during this ticket's own development: af-ize6u).
run_clean() {
  env \
    -u GC_DOLT_HOST -u GC_DOLT_PORT -u GC_DOLT_DATABASE -u GC_DOLT_PROJECT_ID -u GC_DOLT_USER \
    -u GC_SESSION_ID -u GC_SESSION_NAME -u GC_ALIAS -u GC_AGENT \
    -u GC_BEAD_ID -u GC_ROOT_BEAD_ID -u GC_CONTINUATION_GROUP \
    -u GC_CITY -u GC_CITY_PATH -u GC_CITY_RUNTIME_DIR -u GC_BEADS_SCOPE_ROOT -u GC_DIR \
    -u GC_TRIGGER_BEAD_ID -u GC_TRIGGER_WORK_BEAD_ID -u GC_TRIGGER_BEAD_STORE_REF -u GC_TRIGGER_WORK_STORE_REF \
    "$@"
}

# 1. The order itself is discoverable and deterministic (mirrors
#    factory-watchdog-order-test.sh's static check).
order=$(run_clean gc order show backup-freshness --city "$ROOT" --json)
jq -e --arg source "$ROOT/orders/backup-freshness.toml" '
  .ok == true and
  .order.type == "exec" and
  .order.trigger == "condition" and
  .order.exec == "/home/benja/agent-factory/bin/backup-freshness --quiet" and
  .order.check == "/home/benja/agent-factory/bin/backup-freshness --check-only --quiet" and
  .order.enabled == true and
  .order.source == $source
' >/dev/null <<<"$order" || fail "backup-freshness Order is not discoverable and deterministic"

# 2. Functional: a stale archive (>24h) with bead changes since must page.
run_clean gc init \
  --template minimal --default-provider codex --skip-provider-readiness --no-start --yes \
  --name af-o13-backup-freshness "$TEST_CITY" >/dev/null

git -C "$ARCHIVE" init -q
git -C "$ARCHIVE" config user.email "test@example.com"
git -C "$ARCHIVE" config user.name "test"
echo '{}' >"$ARCHIVE/seed.jsonl"
git -C "$ARCHIVE" add seed.jsonl
STALE_EPOCH=$(($(date +%s) - 25 * 3600))
GIT_AUTHOR_DATE="@$STALE_EPOCH +0000" GIT_COMMITTER_DATE="@$STALE_EPOCH +0000" \
  git -C "$ARCHIVE" commit -q -m "seed"

run_backup_freshness() {
  FACTORY_ROOT="$TEST_CITY" GC_JSONL_ARCHIVE_REPO="$ARCHIVE" \
    ESCALATION_DOOR_BIN="$ROOT/bin/escalation-door" \
    ESCALATION_DOOR_LOCK_FILE="$TEST_CITY/.escalation-door.lock" \
    BACKUP_FRESHNESS_CHANGED_OVERRIDE="${1:-3}" \
    run_clean "$ROOT/bin/backup-freshness" "${@:2}"
}

run_backup_freshness 3 --check-only --quiet \
  || fail "check-only should fire (exit 0) when the archive is stale and beads changed"

run_backup_freshness 3 --quiet \
  || fail "backup-freshness should exit 0 after filing and paging"

FILED=$(run_clean gc --city "$TEST_CITY" bd list --status open --json \
  | jq '[.[] | select(.metadata["gc.source"] == "backup-freshness")] | length')
[ "${FILED:-0}" = 1 ] || fail "expected exactly one backup-freshness bead, got ${FILED:-0}"

PAGED=$(run_clean gc --city "$TEST_CITY" mail inbox mayor --json \
  | jq '[.messages[] | select(.subject | startswith("Escalation (Mayor first): "))] | length')
[ "${PAGED:-0}" -ge 1 ] || fail "expected the Mayor to be paged via escalation-door"

# 3. A fresh archive (0h old) must not page, regardless of bead activity.
git -C "$ARCHIVE" commit -q --allow-empty -m "fresh"
run_backup_freshness 3 --check-only --quiet \
  && fail "check-only should not fire when the archive was just pushed"

echo "PASS: backup-freshness pages the Mayor for a stale archive with bead activity, and stays quiet otherwise"
