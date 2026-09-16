#!/usr/bin/env bash
#
# bin/factory-delivery-guard: the missing check on the way OUT of a delivery
# bead's lifecycle. bin/deliver-close already refuses to close a delivery
# bead without its six ADR-0016 proof fields; nothing checked a bead closed
# some other way (a raw `gc bd close`, exactly what happened to af-7700 on
# 2026-09-16). This drives the guard against stub `gc`/`gh` binaries and
# proves: a fully-documented bead is left alone; a bead missing proof but
# naming a verifiably-merged PR is auto-repaired from that verified evidence;
# a bead with no verifiable PR is flagged exactly once, not on every run; and
# --check-only writes nothing in either case.
#
# All bead ids here are synthetic fixtures (zz-fixture*), never a real af-*
# id from the live store.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/factory-delivery-guard"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

export BEADS_FILE="$TMP/city_beads.json"
export UPDATE_LOG="$TMP/updates.log"; : > "$UPDATE_LOG"
mkdir -p "$TMP/bin"

# --- stub gc: serves `bd list` from BEADS_FILE, records every `bd update` ----
cat > "$TMP/bin/gc" <<'STUB'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ ${1:-} == bd && ${2:-} == --rig ]]; then
  # rig-scoped call: no fixtures configured for it in this test, empty list
  if [[ ${5:-} == list ]]; then echo '[]'; exit 0; fi
  exit 0
fi
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
exit 64
STUB
chmod +x "$TMP/bin/gc"

# --- stub gh: `pr view <n> --repo <repo>` reports per-scenario -------------
cat > "$TMP/bin/gh" <<'STUB'
#!/usr/bin/env bash
set -Eeuo pipefail
[[ ${1:-} == pr && ${2:-} == view ]] || exit 64
pr_arg=$3
repo=""
shift 3
while [[ $# -gt 0 ]]; do
  if [[ $1 == --repo ]]; then repo=${2:-}; break; fi
  shift
done
scenario=${GUARD_TEST_SCENARIO:-merged}
number=$pr_arg
state="MERGED"
merged_at="2026-09-16T07:00:00Z"
head_ref="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
merge_oid="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
case "$scenario" in
  merged) ;;
  not-merged) state="OPEN"; merged_at="" ;;
  gh-failure) echo "gh: could not resolve pull request" >&2; exit 1 ;;
  *) echo "unknown GUARD_TEST_SCENARIO: $scenario" >&2; exit 64 ;;
esac
cat <<JSON
{"number":$number,"state":"$state","mergedAt":"$merged_at","headRefOid":"$head_ref","mergeCommit":{"oid":"$merge_oid"},"url":"https://github.example.invalid/$repo/pull/$pr_arg"}
JSON
STUB
chmod +x "$TMP/bin/gh"

: > "$TMP/bin/jq_marker"  # ensure jq itself comes from the real PATH
export PATH="$TMP/bin:$PATH"
touch "$TMP/city.toml"

guard() { FACTORY_ROOT="$TMP" GUARD_TEST_SCENARIO="${GUARD_TEST_SCENARIO:-merged}" "$GUARD" "$@" 2>&1 || true; }
update_count() { grep -c "^$1 " "$UPDATE_LOG" 2>/dev/null || true; }

complete_bead='{
  "id": "zz-fixture-complete", "status": "closed", "title": "Complete",
  "labels": ["product-goal"],
  "metadata": {
    "gc.delivery_status": "merged", "gc.work_outcome": "shipped",
    "gc.github_repo": "example-org/example-repo", "gc.pr_number": 1,
    "gc.pr_head": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "gc.merge_commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  }
}'
not_a_goal='{"id": "zz-fixture-other", "status": "closed", "title": "Other", "labels": ["task"], "metadata": {}}'
cancelled_bead='{
  "id": "zz-fixture-cancelled", "status": "closed", "title": "Cancelled",
  "labels": ["product-goal"], "metadata": {"gc.work_outcome": "cancelled"}
}'
verifiable_bead='{
  "id": "zz-fixture-verifiable", "status": "closed", "title": "Backend slice merged, close bypassed deliver-close",
  "labels": ["product-goal"],
  "metadata": {"gc.github_repo": "example-org/example-repo", "gc.pr_number": 42}
}'
unverifiable_bead='{
  "id": "zz-fixture-af7700-shape", "status": "closed", "title": "Raw close, no proof at all",
  "labels": ["product-goal"], "metadata": {}
}'

jq -n --argjson a "$complete_bead" --argjson b "$not_a_goal" --argjson c "$cancelled_bead" \
  '[$a, $b, $c]' > "$BEADS_FILE"

# 1. nothing to do: fully documented, unrelated, and deliberately-cancelled
#    beads are all left alone ---------------------------------------------
out=$(guard --check-only)
grep -q "delivery-proof:city — every closed delivery bead is fully documented" <<<"$out" \
  || { echo "$out" >&2; fail "a clean city was not reported healthy"; }
[ "$(update_count zz-fixture-complete)" = "0" ] || fail "touched a fully-documented bead"
[ "$(update_count zz-fixture-cancelled)" = "0" ] || fail "touched a deliberately-cancelled goal"

# 2. verifiable-but-incomplete: --check-only reports, writes nothing --------
jq -n --argjson v "$verifiable_bead" '[$v]' > "$BEADS_FILE"
out=$(GUARD_TEST_SCENARIO=merged guard --check-only)
grep -q "verifies merged — run factory-delivery-guard to backfill" <<<"$out" \
  || { echo "$out" >&2; fail "verifiable-but-incomplete bead not reported under --check-only"; }
[ "$(update_count zz-fixture-verifiable)" = "0" ] || fail "--check-only wrote to Beads"

# 3. verifiable-but-incomplete: default run backfills all six fields --------
: > "$UPDATE_LOG"
out=$(GUARD_TEST_SCENARIO=merged guard)
grep -q "backfilled all six proof fields" <<<"$out" \
  || { echo "$out" >&2; fail "verified bead was not backfilled"; }
call=$(grep "^zz-fixture-verifiable " "$UPDATE_LOG" || true)
for field in \
  "gc.delivery_status=merged" "gc.work_outcome=shipped" \
  "gc.github_repo=example-org/example-repo" "gc.pr_number=42" \
  "gc.pr_head=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" \
  "gc.merge_commit=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
do
  [[ $call == *"$field"* ]] || fail "backfill call missing $field: $call"
done

# 4. named repo+PR that does NOT verify as merged is flagged, never guessed --
jq -n --argjson v "$verifiable_bead" '[$v]' > "$BEADS_FILE"
: > "$UPDATE_LOG"
out=$(GUARD_TEST_SCENARIO=not-merged guard)
grep -q "not verifiably merged" <<<"$out" || { echo "$out" >&2; fail "unmerged PR was not reported"; }
grep -q "flagged zz-fixture-verifiable" <<<"$out" || fail "unverified bead was not flagged"
[[ $(grep "^zz-fixture-verifiable " "$UPDATE_LOG" || true) == *"gc.delivery_proof_flagged_at="* ]] \
  || fail "flag metadata was not written"
[[ $(grep "^zz-fixture-verifiable " "$UPDATE_LOG" || true) != *"gc.delivery_status=merged"* ]] \
  || fail "an unmerged PR must never be backfilled as if it were verified"

# 5. no repo/PR at all (the actual af-7700 shape): flagged once, not spammed -
jq -n --argjson u "$unverifiable_bead" '[$u]' > "$BEADS_FILE"
: > "$UPDATE_LOG"
out=$(guard)
grep -q "no verifiable GitHub repo/PR recorded" <<<"$out" || { echo "$out" >&2; fail "af-7700-shaped bead not reported"; }
grep -q "flagged zz-fixture-af7700-shape" <<<"$out" || fail "af-7700-shaped bead was not flagged"
[ "$(update_count zz-fixture-af7700-shape)" = "1" ] || fail "expected exactly one write (the flag)"

# Simulate the flag having landed on the bead (as the real store would show
# on the next guard run) and prove the second run does not re-flag it.
jq '.[0].metadata["gc.delivery_proof_flagged_at"] = "2026-09-16T12:00:00Z"
    | .[0].metadata["gc.delivery_proof_missing"] = "gc.delivery_status,gc.work_outcome,gc.github_repo,gc.pr_number,gc.pr_head,gc.merge_commit"' \
  "$BEADS_FILE" > "$BEADS_FILE.next"
mv "$BEADS_FILE.next" "$BEADS_FILE"
: > "$UPDATE_LOG"
out=$(guard)
grep -q "already flagged, awaiting a human" <<<"$out" \
  || { echo "$out" >&2; fail "already-flagged bead did not say so on the second run"; }
[ "$(update_count zz-fixture-af7700-shape)" = "0" ] || fail "re-flagged an already-flagged bead — spammed a duplicate write"
grep -q "^UNRESOLVED" <<<"$out" || fail "an unresolved unverifiable bead must not read as healthy"

echo "PASS: factory-delivery-guard backfills verified proof and flags the rest exactly once"
