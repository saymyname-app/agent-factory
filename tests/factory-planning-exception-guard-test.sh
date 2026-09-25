#!/usr/bin/env bash
#
# bin/factory-planning-exception-guard: detects (1) a bead blocked-closed as a
# semantic/topology surprise with no Planning Exception ever raised for it,
# and (2) a bead that redecomposes an already-blocked bead's work without an
# open Planning Exception or genuine human authorization (af-zwhh0).
#
# Regression for the B12/af-4a44k shape: a worker's own closing note said
# "this is a topology/semantic gap needing a Planning Exception" but
# `bin/planning-exception raise` was never called, and the Mayor separately
# created an ad-hoc redecomposition bead self-authorized via
# `gc.authorized_by` naming the blocked bead's own id -- not a human
# decision. Proves: a bounded technical repair (`gc.blocked_classification=
# repair`) never trips check 1; a semantic/topology blocked-close with no
# `gc.planning_exception_id` is flagged and the Mayor paged exactly once,
# then reported again (never re-paged) on a later run; a semantic/topology
# blocked-close that DOES carry `gc.planning_exception_id` never trips.
# For check 2: a redecomposition bead naming a target with no Planning
# Exception and no `gc.authorized_by` (or one equal to the target's own id --
# self-authorization) is flagged and paged; one naming a target with an open
# Planning Exception, or carrying a real `gc.authorized_by`, is left alone.
#
# All bead ids here are synthetic fixtures (zz-fixture*), never a real af-*
# id from the live store.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/factory-planning-exception-guard"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

export CLOSED_FILE="$TMP/closed_beads.json"; echo '[]' > "$CLOSED_FILE"
export OPEN_FILE="$TMP/open_beads.json"; echo '[]' > "$OPEN_FILE"
export SHOW_FILE="$TMP/show_beads.json"; echo '{}' > "$SHOW_FILE"
export UPDATE_LOG="$TMP/updates.log"; : > "$UPDATE_LOG"
export MAIL_LOG="$TMP/mail.log"; : > "$MAIL_LOG"
mkdir -p "$TMP/bin"

# --- stub gc: serves `bd list`/`bd show` from the fixture files, records
# `bd update` and `mail send` calls ------------------------------------------
cat > "$TMP/bin/gc" <<'STUB'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ ${1:-} == bd && ${2:-} == list ]]; then
  for a in "$@"; do
    if [[ $a == closed ]]; then cat "$CLOSED_FILE"; exit 0; fi
    if [[ $a == open,in_progress ]]; then cat "$OPEN_FILE"; exit 0; fi
  done
  echo '[]'
  exit 0
fi
if [[ ${1:-} == bd && ${2:-} == show ]]; then
  id=$3
  jq -e --arg id "$id" '.[$id] // empty' "$SHOW_FILE" || echo '{}'
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
cat > "$TMP/bin/bd" <<'STUB'
#!/usr/bin/env bash
exit 0
STUB
chmod +x "$TMP/bin/bd"

export PATH="$TMP/bin:$PATH"
export GC_BIN="$TMP/bin/gc"
export BD_BIN="$TMP/bin/bd"
touch "$TMP/city.toml"

guard() { FACTORY_ROOT="$TMP" "$GUARD" "$@" 2>&1 || true; }
update_count() { grep -c "^$1 " "$UPDATE_LOG" 2>/dev/null || true; }
mail_count() { grep -c "^mail-to=$1$" "$MAIL_LOG" 2>/dev/null || true; }

# =============================================================================
# Check 1: blocked-classification without a raised exception
# =============================================================================

repair_close='{
  "id": "zz-fixture-repair", "status": "closed",
  "metadata": {"gc.work_outcome": "blocked", "gc.blocked_classification": "repair"}
}'
semantic_unraised='{
  "id": "zz-fixture-unraised", "status": "closed",
  "metadata": {"gc.work_outcome": "blocked", "gc.blocked_classification": "semantic"}
}'
topology_raised='{
  "id": "zz-fixture-raised", "status": "closed",
  "metadata": {"gc.work_outcome": "abandoned", "gc.blocked_classification": "topology",
               "gc.planning_exception_id": "pd-1"}
}'

# 1a. a bounded technical repair never trips the check, no matter how many
#     other blocked closes exist ---------------------------------------------
jq -n --argjson a "$repair_close" --argjson b "$topology_raised" '[$a, $b]' > "$CLOSED_FILE"
out=$(guard --check-only)
grep -q "healthy" <<<"$out" || { echo "$out" >&2; fail "repair + already-raised closes were not reported healthy"; }
[ "$(update_count zz-fixture-repair)" = "0" ] || fail "touched a bounded technical repair close"
[ "$(update_count zz-fixture-raised)" = "0" ] || fail "touched a close that already names a Planning Exception"
[ "$(mail_count mayor)" = "0" ] || fail "paged the Mayor with nothing wrong (check 1a)"

# 1b. a semantic/topology surprise with no Planning Exception raised: flagged
#     and reported under --check-only, nothing written ------------------------
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
jq -n --argjson a "$semantic_unraised" '[$a]' > "$CLOSED_FILE"
out=$(guard --check-only)
grep -q "zz-fixture-unraised blocked-closed as semantic with no Planning Exception raised" <<<"$out" \
  || { echo "$out" >&2; fail "unraised semantic close was not reported under --check-only"; }
grep -q "^UNRESOLVED" <<<"$out" || fail "an unraised semantic close under --check-only must not read as healthy"
[ "$(update_count zz-fixture-unraised)" = "0" ] || fail "--check-only wrote to Beads"
[ "$(mail_count mayor)" = "0" ] || fail "--check-only paged the Mayor"

# 1c. default run flags it once and pages the Mayor exactly once -------------
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
out=$(guard)
grep -q "flagged zz-fixture-unraised once for the Mayor (semantic blocked-close with no Planning Exception raised) and paged it" <<<"$out" \
  || { echo "$out" >&2; fail "unraised semantic close was not flagged and reported"; }
call=$(grep "^zz-fixture-unraised " "$UPDATE_LOG" || true)
[[ $call == *"gc.planning_exception_guard_flagged_at="* ]] || fail "flag call did not set gc.planning_exception_guard_flagged_at: $call"
[ "$(mail_count mayor)" = "1" ] || fail "expected exactly one page to the Mayor"

# 1d. a later run reports the same bead again but never re-pages -------------
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
jq -n --argjson a "$(jq '.metadata["gc.planning_exception_guard_flagged_at"] = "2026-09-25T00:00:00Z"' <<<"$semantic_unraised")" \
  '[$a]' > "$CLOSED_FILE"
out=$(guard)
grep -q "zz-fixture-unraised still unraised (semantic, no gc.planning_exception_id) — already flagged, awaiting a decision" <<<"$out" \
  || { echo "$out" >&2; fail "already-flagged unraised close was not reported again"; }
grep -q "^UNRESOLVED" <<<"$out" || fail "an already-flagged unraised close must still read as unresolved"
[ "$(update_count zz-fixture-unraised)" = "0" ] || fail "re-flagged an already-flagged bead"
[ "$(mail_count mayor)" = "0" ] || fail "re-paged the Mayor for an already-flagged bead"

# =============================================================================
# Check 2: unauthorized redecomposition dispatch
# =============================================================================

jq -n '{
  "zz-fixture-target-no-pe": {"id": "zz-fixture-target-no-pe", "metadata": {}},
  "zz-fixture-target-pe": {"id": "zz-fixture-target-pe", "metadata": {"gc.planning_exception_id": "pd-2"}}
}' > "$SHOW_FILE"

unauthorized_unset='{
  "id": "zz-fixture-redecomp-unset", "status": "open",
  "metadata": {"gc.redecomposes": "zz-fixture-target-no-pe"}
}'
unauthorized_self='{
  "id": "zz-fixture-redecomp-self", "status": "in_progress",
  "metadata": {"gc.redecomposes": "zz-fixture-target-no-pe", "gc.authorized_by": "zz-fixture-target-no-pe"}
}'
authorized_human='{
  "id": "zz-fixture-redecomp-human", "status": "open",
  "metadata": {"gc.redecomposes": "zz-fixture-target-no-pe", "gc.authorized_by": "benjamin-hurand"}
}'
authorized_pe='{
  "id": "zz-fixture-redecomp-pe", "status": "open",
  "metadata": {"gc.redecomposes": "zz-fixture-target-pe"}
}'

# 2a. no gc.authorized_by at all, target has no Planning Exception: flagged --
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
jq -n --argjson a "$unauthorized_unset" '[$a]' > "$OPEN_FILE"
echo '[]' > "$CLOSED_FILE"
out=$(guard --check-only)
grep -q "zz-fixture-redecomp-unset redecomposes zz-fixture-target-no-pe with no open Planning Exception and gc.authorized_by is unset" <<<"$out" \
  || { echo "$out" >&2; fail "unauthorized (unset) redecomposition was not reported"; }
[ "$(update_count zz-fixture-redecomp-unset)" = "0" ] || fail "--check-only wrote to Beads (2a)"

# 2b. gc.authorized_by equals the target's own id (self-authorization): flagged
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
jq -n --argjson a "$unauthorized_self" '[$a]' > "$OPEN_FILE"
out=$(guard)
grep -q "zz-fixture-redecomp-self redecomposes zz-fixture-target-no-pe with no open Planning Exception and gc.authorized_by is the target's own id -- self-authorized, not a human decision" <<<"$out" \
  || { echo "$out" >&2; fail "self-authorized redecomposition was not flagged"; }
grep -q "flagged zz-fixture-redecomp-self once for the Mayor" <<<"$out" \
  || fail "self-authorized redecomposition was not repaired-and-reported"
[ "$(mail_count mayor)" = "1" ] || fail "expected exactly one page to the Mayor (2b)"

# 2c. a real human name in gc.authorized_by: left alone ----------------------
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
jq -n --argjson a "$authorized_human" '[$a]' > "$OPEN_FILE"
out=$(guard)
grep -q "healthy" <<<"$out" || { echo "$out" >&2; fail "human-authorized redecomposition was not left alone"; }
[ "$(update_count zz-fixture-redecomp-human)" = "0" ] || fail "touched a human-authorized redecomposition"
[ "$(mail_count mayor)" = "0" ] || fail "paged the Mayor over a human-authorized redecomposition"

# 2d. target already has an open Planning Exception: left alone -------------
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
jq -n --argjson a "$authorized_pe" '[$a]' > "$OPEN_FILE"
out=$(guard)
grep -q "healthy" <<<"$out" || { echo "$out" >&2; fail "redecomposition of a bead with an open Planning Exception was not left alone"; }
[ "$(update_count zz-fixture-redecomp-pe)" = "0" ] || fail "touched a redecomposition whose target already has a Planning Exception"
[ "$(mail_count mayor)" = "0" ] || fail "paged the Mayor over an already-authorized redecomposition"

echo "PASS: factory-planning-exception-guard flags unraised semantic/topology blocked-closes and unauthorized redecomposition dispatch, leaves bounded repairs and authorized work alone"
