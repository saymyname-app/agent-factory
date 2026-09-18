#!/usr/bin/env bash
#
# bin/factory-queue-guard: detects a product-queue candidate whose status
# changed by any path other than product-queue's own commands (af-tbkcc).
# Regression for the 2026-09-18 23:53Z-02:12Z incident: af-ogg8z and
# af-gp8fd were set to in_progress/open directly by a PO session, bypassing
# product-queue, which cascaded into 8 sentinel failures and a 2h10 blocked
# campaign. This drives the guard against stub gc/bd binaries and proves: a
# candidate whose status matches its queue_state is left alone; a drifted
# candidate with no execution Bead linked is restored to deferred and the
# Mayor is paged exactly once; a drifted candidate that DOES link an
# execution Bead is never auto-restored, only flagged and paged once; and
# --check-only writes and pages nothing.
#
# All bead ids here are synthetic fixtures (zz-fixture*), never a real af-*
# id from the live store.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/factory-queue-guard"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

export BEADS_FILE="$TMP/city_beads.json"
export UPDATE_LOG="$TMP/updates.log"; : > "$UPDATE_LOG"
export MAIL_LOG="$TMP/mail.log"; : > "$MAIL_LOG"
mkdir -p "$TMP/bin"

# --- stub gc: serves `bd list` from BEADS_FILE, records `bd update` and
# `mail send` calls ------------------------------------------------------
cat > "$TMP/bin/gc" <<'STUB'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ ${1:-} == bd && ${2:-} == list ]]; then
  cat "$BEADS_FILE"
  exit 0
fi
if [[ ${1:-} == bd && ${2:-} == update ]]; then
  id=$3
  shift 3
  printf '%s %s\n' "$id" "$*" >> "$UPDATE_LOG"
  exit 0
fi
if [[ ${1:-} == mail && ${2:-} == send ]]; then
  printf 'mail-to=%s\n' "$3" >> "$MAIL_LOG"
  exit 0
fi
exit 64
STUB
chmod +x "$TMP/bin/gc"
cp "$TMP/bin/gc" "$TMP/bin/bd_unused" 2>/dev/null || true
# `bd` itself is only require_command-checked, never invoked directly by the
# guard (it always calls through `$GC_BIN bd ...`); a no-op stub is enough.
cat > "$TMP/bin/bd" <<'STUB'
#!/usr/bin/env bash
exit 0
STUB
chmod +x "$TMP/bin/bd"

export PATH="$TMP/bin:$PATH"
# Every Gas City agent session (this one included) has GC_BIN pre-exported
# to the real `gc` binary, which silently outranks a PATH-only stub -- a
# real 2026-09-18 incident (af-txnw2) during af-x45xw verification, where
# this exact gap in a sibling test let a write reach the live store instead
# of this fixture. Override it explicitly, the same belt-and-braces pattern
# tests/campaign-pointer-test.sh already uses.
export GC_BIN="$TMP/bin/gc"
export BD_BIN="$TMP/bin/bd"
touch "$TMP/city.toml"

guard() { FACTORY_ROOT="$TMP" "$GUARD" "$@" 2>&1 || true; }
update_count() { grep -c "^$1 " "$UPDATE_LOG" 2>/dev/null || true; }
mail_count() { grep -c "^mail-to=$1$" "$MAIL_LOG" 2>/dev/null || true; }

healthy_bead='{
  "id": "zz-fixture-healthy", "status": "deferred", "title": "Healthy",
  "labels": ["product-queue"],
  "metadata": {"gc.queue_product": "saymyname", "gc.queue_state": "queued", "gc.queue_rank": 1000}
}'
closed_materialized='{
  "id": "zz-fixture-materialized", "status": "closed", "title": "Materialized",
  "labels": ["product-queue"],
  "metadata": {"gc.queue_product": "saymyname", "gc.queue_state": "materialized", "gc.materialized_bead": "zz-exec"}
}'
not_a_candidate='{
  "id": "zz-fixture-mayor-task", "status": "closed", "title": "Ordinary Mayor task",
  "labels": ["product-queue"], "metadata": {"gc.outcome": "pass"}
}'
drifted_no_link='{
  "id": "zz-fixture-drifted", "status": "in_progress", "title": "Drifted directly",
  "labels": ["product-queue"],
  "metadata": {"gc.queue_product": "saymyname", "gc.queue_state": "queued", "gc.queue_rank": 2000}
}'
drifted_with_link='{
  "id": "zz-fixture-drifted-linked", "status": "open", "title": "Drifted, execution linked",
  "labels": ["product-queue"],
  "metadata": {"gc.queue_product": "saymyname", "gc.queue_state": "queued", "gc.queue_rank": 3000, "gc.materialized_bead": "zz-exec-2"}
}'

# 1. nothing to do: healthy, correctly-closed, and non-candidate (no
#    gc.queue_state) beads are all left alone -------------------------------
jq -n --argjson a "$healthy_bead" --argjson b "$closed_materialized" --argjson c "$not_a_candidate" \
  '[$a, $b, $c]' > "$BEADS_FILE"
out=$(guard --check-only)
grep -q "healthy — 2 product-queue candidate(s) checked, no status drift" <<<"$out" \
  || { echo "$out" >&2; fail "a clean queue was not reported healthy"; }
[ "$(update_count zz-fixture-healthy)" = "0" ] || fail "touched a healthy candidate"
[ "$(update_count zz-fixture-materialized)" = "0" ] || fail "touched a correctly-closed candidate"
[ "$(update_count zz-fixture-mayor-task)" = "0" ] || fail "touched a Bead with no gc.queue_state at all"
[ "$(mail_count mayor)" = "0" ] || fail "paged the Mayor with nothing wrong"

# 2. drifted with no execution Bead linked: --check-only reports, writes and
#    pages nothing -----------------------------------------------------------
jq -n --argjson d "$drifted_no_link" '[$d]' > "$BEADS_FILE"
out=$(guard --check-only)
grep -q "zz-fixture-drifted product-queue status (in_progress) drifted" <<<"$out" \
  || { echo "$out" >&2; fail "drift was not reported under --check-only"; }
[ "$(update_count zz-fixture-drifted)" = "0" ] || fail "--check-only wrote to Beads"
[ "$(mail_count mayor)" = "0" ] || fail "--check-only paged the Mayor"
grep -q "^UNRESOLVED" <<<"$out" || fail "a real drift under --check-only must not read as healthy"

# 3. drifted with no execution Bead linked: default run restores status and
#    pages the Mayor exactly once --------------------------------------------
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
out=$(guard)
grep -q "restored to deferred (was in_progress; queue_state=queued) and paged the Mayor" <<<"$out" \
  || { echo "$out" >&2; fail "drifted candidate was not restored and reported"; }
call=$(grep "^zz-fixture-drifted " "$UPDATE_LOG" || true)
[[ $call == *"--status deferred"* ]] || fail "restore call did not set status=deferred: $call"
[ "$(mail_count mayor)" = "1" ] || fail "expected exactly one page to the Mayor"

# 4. drifted WITH an execution Bead linked: never auto-restored, only
#    flagged and paged once --------------------------------------------------
jq -n --argjson d "$drifted_with_link" '[$d]' > "$BEADS_FILE"
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
out=$(guard)
grep -q "needs the Mayor, not an automatic restore" <<<"$out" \
  || { echo "$out" >&2; fail "linked drift was not reported"; }
call=$(grep "^zz-fixture-drifted-linked " "$UPDATE_LOG" || true)
[[ $call == *"gc.queue_guard_flagged_at="* ]] || fail "linked drift was not flagged: $call"
[[ $call != *"--status"* ]] || fail "a candidate linking an execution Bead must never be auto-restored: $call"
[ "$(mail_count mayor)" = "1" ] || fail "expected exactly one page to the Mayor for the linked drift"

# Simulate the flag having landed on the Bead (as the real store would show
# on the next guard run) and prove the second run does not re-flag or re-page.
jq '.[0].metadata["gc.queue_guard_flagged_at"] = "2026-09-18T02:12:00Z"
    | .[0].metadata["gc.queue_guard_flagged_status"] = "open"' \
  "$BEADS_FILE" > "$BEADS_FILE.next"
mv "$BEADS_FILE.next" "$BEADS_FILE"
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
out=$(guard)
grep -q "already flagged, awaiting the Mayor" <<<"$out" \
  || { echo "$out" >&2; fail "already-flagged drift did not say so on the second run"; }
[ "$(update_count zz-fixture-drifted-linked)" = "0" ] || fail "re-flagged an already-flagged candidate"
[ "$(mail_count mayor)" = "0" ] || fail "paged the Mayor a second time for the same drift"
grep -q "^UNRESOLVED" <<<"$out" || fail "an unresolved linked drift must not read as healthy"

echo "PASS: factory-queue-guard restores unlinked drift and flags linked drift exactly once"
