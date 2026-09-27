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
export MAIL_LOG="$TMP/mail.log"; : > "$MAIL_LOG"
# Scenarios below reuse PR numbers across merged/open states; the merged-PR
# cache is exercised on its own in case 6b.
export FACTORY_DELIVERY_GUARD_MERGED_CACHE=/dev/null
mkdir -p "$TMP/bin"

# --- stub gc: serves `bd list` from BEADS_FILE, records every `bd update`
# and `mail send` -------------------------------------------------------
cat > "$TMP/bin/gc" <<'STUB'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ ${1:-} == bd && ${2:-} == --rig ]]; then
  # rig-scoped call: no fixtures configured for it in this test, empty list
  if [[ ${5:-} == list ]]; then echo '[]'; exit 0; fi
  exit 0
fi
if [[ ${1:-} == bd && ${2:-} == list ]]; then
  if [[ " $* " == *" --status "* || " $* " == *" --label "* || " $* " == *" --has-metadata-key "* ]]; then
    cat "$BEADS_FILE"; exit 0
  fi
  # an unfiltered `list --all` sees every bead: fixtures plus execution beads
  echo "list-all" >> "$TMP_LIST_ALL_LOG"
  jq -s '.[0] + (.[1] | to_entries | map({id: .key, status: .value}))' "$BEADS_FILE" "$EXEC_STATUS_FILE"
  exit 0
fi
if [[ ${1:-} == bd && ${2:-} == update ]]; then
  id=$3
  shift 3
  printf '%s %s\n' "$id" "$*" >> "$UPDATE_LOG"
  exit 0
fi
if [[ ${1:-} == bd && ${2:-} == show ]]; then
  id=$3
  echo "$id" >> "$TMP_SHOW_LOG"
  status=$(jq -r --arg id "$id" '.[$id] // empty' "$EXEC_STATUS_FILE" 2>/dev/null)
  if [ -n "$status" ]; then printf '[{"id":"%s","status":"%s"}]' "$id" "$status"; else echo '[]'; fi
  exit 0
fi
if [[ ${1:-} == convoy && ${2:-} == status ]]; then
  id=$3
  child=$(jq -r --arg id "$id" '.[$id] // empty' "$CONVOY_CHILDREN_FILE" 2>/dev/null)
  if [ -n "$child" ]; then printf '{"children":[{"id":"%s"}]}' "$child"; else echo '{"children":[]}'; fi
  exit 0
fi
if [[ ${1:-} == mail && ${2:-} == send ]]; then
  printf 'mail-to=%s\n' "$3" >> "$MAIL_LOG"
  exit 0
fi
exit 64
STUB
chmod +x "$TMP/bin/gc"
export EXEC_STATUS_FILE="$TMP/exec_status.json"; echo '{}' > "$EXEC_STATUS_FILE"
export TMP_SHOW_LOG="$TMP/show.log" TMP_LIST_ALL_LOG="$TMP/list-all.log"
: > "$TMP_SHOW_LOG"; : > "$TMP_LIST_ALL_LOG"
export CONVOY_CHILDREN_FILE="$TMP/convoy_children.json"; echo '{}' > "$CONVOY_CHILDREN_FILE"

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
# factory-delivery-guard resolves GC_BIN="${GC_BIN:-gc}" and
# GH_BIN="${GH_BIN:-gh}" itself. Every Gas City agent session (this one
# included) has GC_BIN pre-exported to the real `gc` binary, which silently
# outranks a PATH-only stub and defeats the ${VAR:-default} fallback the
# guard relies on -- the same class of gap af-ylndd audited for, and a real
# 2026-09-18 incident (af-txnw2) where it let a test write reach the live
# store instead of its fixture. Override both explicitly, the same
# belt-and-braces pattern tests/factory-queue-guard-test.sh and
# tests/campaign-pointer-test.sh already use.
export GC_BIN="$TMP/bin/gc"
export GH_BIN="$TMP/bin/gh"
touch "$TMP/city.toml"

guard() { FACTORY_ROOT="$TMP" GUARD_TEST_SCENARIO="${GUARD_TEST_SCENARIO:-merged}" "$GUARD" "$@" 2>&1 || true; }
update_count() { grep -c "^$1 " "$UPDATE_LOG" 2>/dev/null || true; }
mail_count() { grep -c "^mail-to=$1$" "$MAIL_LOG" 2>/dev/null || true; }

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

# 4. named repo+PR that does NOT verify as merged is flagged, never guessed,
#    and the Mayor is paged exactly once ------------------------------------
jq -n --argjson v "$verifiable_bead" '[$v]' > "$BEADS_FILE"
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
out=$(GUARD_TEST_SCENARIO=not-merged guard)
grep -q "not verifiably merged" <<<"$out" || { echo "$out" >&2; fail "unmerged PR was not reported"; }
grep -q "flagged zz-fixture-verifiable" <<<"$out" || fail "unverified bead was not flagged"
[[ $(grep "^zz-fixture-verifiable " "$UPDATE_LOG" || true) == *"gc.delivery_proof_flagged_at="* ]] \
  || fail "flag metadata was not written"
[[ $(grep "^zz-fixture-verifiable " "$UPDATE_LOG" || true) != *"gc.delivery_status=merged"* ]] \
  || fail "an unmerged PR must never be backfilled as if it were verified"
[ "$(mail_count mayor)" = "1" ] || fail "expected exactly one page to the Mayor for the newly-flagged bead"

# 5. no repo/PR at all (the actual af-7700 shape): flagged once, not spammed,
#    and the label is never stripped (it may be a genuine delivery bead
#    closed the wrong way, not a mislabel -- see the guard's header comment) -
jq -n --argjson u "$unverifiable_bead" '[$u]' > "$BEADS_FILE"
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
out=$(guard)
grep -q "no verifiable GitHub repo/PR recorded" <<<"$out" || { echo "$out" >&2; fail "af-7700-shaped bead not reported"; }
grep -q "flagged zz-fixture-af7700-shape" <<<"$out" || fail "af-7700-shaped bead was not flagged"
[ "$(update_count zz-fixture-af7700-shape)" = "1" ] || fail "expected exactly one write (the flag)"
[[ $(grep "^zz-fixture-af7700-shape " "$UPDATE_LOG" || true) != *"--remove-label"* ]] \
  || fail "an unverifiable product-goal bead must never have its label stripped automatically"
[ "$(mail_count mayor)" = "1" ] || fail "expected exactly one page to the Mayor for the af-7700-shaped bead"

# Simulate the flag having landed on the bead (as the real store would show
# on the next guard run) and prove the second run does not re-flag it.
jq '.[0].metadata["gc.delivery_proof_flagged_at"] = "2026-09-16T12:00:00Z"
    | .[0].metadata["gc.delivery_proof_missing"] = "gc.delivery_status,gc.work_outcome,gc.github_repo,gc.pr_number,gc.pr_head,gc.merge_commit"' \
  "$BEADS_FILE" > "$BEADS_FILE.next"
mv "$BEADS_FILE.next" "$BEADS_FILE"
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
out=$(guard)
grep -q "already flagged, awaiting a human" <<<"$out" \
  || { echo "$out" >&2; fail "already-flagged bead did not say so on the second run"; }
[ "$(update_count zz-fixture-af7700-shape)" = "0" ] || fail "re-flagged an already-flagged bead — spammed a duplicate write"
[ "$(mail_count mayor)" = "0" ] || fail "paged the Mayor a second time for the same flagged bead"
grep -q "^UNRESOLVED" <<<"$out" || fail "an unresolved unverifiable bead must not read as healthy"

# --- claimed-shipped sibling check (af-1xz1g): a closed bead of ANY label
# claiming gc.outcome=pass / gc.work_outcome=shipped with its own gc.pr_url
# gets that PR independently verified, even without the product-goal label
# the checks above require. -------------------------------------------------

claimed_shipped_merged='{
  "id": "zz-fixture-claimed-merged", "status": "closed", "title": "No label, claims pass, PR genuinely merged",
  "labels": [],
  "metadata": {"gc.outcome": "pass", "gc.pr_url": "https://github.com/example-org/example-repo/pull/7"}
}'
# The exact af-x45xw shape: closed gc.outcome=pass, own gc.pr_url recorded,
# no product-goal label -- and the PR is still OPEN (GUARD_TEST_SCENARIO
# not-merged below drives gh to report that).
af_x45xw_shape='{
  "id": "zz-fixture-af-x45xw-shape", "status": "closed", "title": "Closed pass while its own PR was still open",
  "labels": [],
  "metadata": {"gc.outcome": "pass", "gc.pr_url": "https://github.com/example-org/example-repo/pull/114"}
}'
claimed_shipped_already_proven='{
  "id": "zz-fixture-claimed-proven", "status": "closed", "title": "No label but already fully proven, nothing new to verify",
  "labels": [],
  "metadata": {
    "gc.outcome": "pass", "gc.pr_url": "https://github.com/example-org/example-repo/pull/9",
    "gc.delivery_status": "merged", "gc.work_outcome": "shipped",
    "gc.github_repo": "example-org/example-repo", "gc.pr_number": 9,
    "gc.pr_head": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "gc.merge_commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  }
}'

# 6. no label at all, but the PR genuinely verifies merged: reported healthy,
#    nothing written (no six-field backfill for a non-product-goal bead) ----
jq -n --argjson v "$claimed_shipped_merged" '[$v]' > "$BEADS_FILE"
: > "$UPDATE_LOG"
out=$(GUARD_TEST_SCENARIO=merged guard)
grep -q "zz-fixture-claimed-merged (city) claims shipped" <<<"$out" \
  || { echo "$out" >&2; fail "claimed-shipped bead was not checked"; }
grep -q "example-org/example-repo#7 verifies merged" <<<"$out" \
  || { echo "$out" >&2; fail "claimed-shipped bead with a merged PR was not reported healthy"; }
[ "$(update_count zz-fixture-claimed-merged)" = "0" ] || fail "a verified claimed-shipped bead should not be written to"

# 6b. a merged PR is asked of gh once, then served from the host-local cache
#     (a merge is terminal) -- every tick used to re-ask for every bead ---
cache="$TMP/merged-cache.tsv"; : > "$cache"; : > "$TMP/gh-calls.log"
cat > "$TMP/gh-counting" <<STUB
#!/usr/bin/env bash
echo call >> "$TMP/gh-calls.log"
exec "$TMP/bin/gh" "\$@"
STUB
chmod +x "$TMP/gh-counting"
FACTORY_DELIVERY_GUARD_MERGED_CACHE="$cache" GH_BIN="$TMP/gh-counting" guard --check-only >/dev/null
[ -s "$cache" ] && fail "--check-only must not write the merged-PR cache"
for _ in 1 2; do
  out=$(FACTORY_DELIVERY_GUARD_MERGED_CACHE="$cache" GH_BIN="$TMP/gh-counting" GUARD_TEST_SCENARIO=merged guard)
done
grep -q "example-org/example-repo#7 verifies merged" <<<"$out" \
  || { echo "$out" >&2; fail "a cached merged PR was not reported healthy"; }
[ "$(wc -l < "$TMP/gh-calls.log")" = "2" ] \
  || fail "gh should be asked once in --check-only and once for the first real run, never again ($(wc -l < "$TMP/gh-calls.log") calls)"
[ "$(update_count zz-fixture-claimed-merged)" = "0" ] || fail "the merged-PR cache must never become a Beads write"

# 7. the af-x45xw shape itself: closed gc.outcome=pass, own gc.pr_url set,
#    no product-goal label, PR still OPEN -- must be flagged, never trusted,
#    and the Mayor paged exactly once ---------------------------------------
jq -n --argjson v "$af_x45xw_shape" '[$v]' > "$BEADS_FILE"
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
out=$(GUARD_TEST_SCENARIO=not-merged guard)
grep -q "not verifiably merged" <<<"$out" \
  || { echo "$out" >&2; fail "af-x45xw-shaped bead was not reported as unverified"; }
grep -q "flagged zz-fixture-af-x45xw-shape" <<<"$out" \
  || { echo "$out" >&2; fail "af-x45xw-shaped bead was not flagged"; }
[[ $(grep "^zz-fixture-af-x45xw-shape " "$UPDATE_LOG" || true) == *"gc.delivery_proof_flagged_at="* ]] \
  || fail "af-x45xw-shaped bead flag metadata was not written"
grep -q "^UNRESOLVED" <<<"$out" || fail "the af-x45xw shape must not read as healthy"
[ "$(mail_count mayor)" = "1" ] || fail "expected exactly one page to the Mayor for the af-x45xw-shaped bead"

# 8. no label, but already carries all six verified proof fields: the
#    claimed-shipped check has nothing new to verify and leaves it alone ----
jq -n --argjson v "$claimed_shipped_already_proven" '[$v]' > "$BEADS_FILE"
: > "$UPDATE_LOG"
out=$(guard --check-only)
[[ $out != *"zz-fixture-claimed-proven"* ]] \
  || { echo "$out" >&2; fail "an already-fully-proven bead should not be re-processed by the claimed-shipped check"; }

# --- convoy-delivery reconciliation (af-gpq0y): a workflow bead can close
# with full verified delivery proof while the execution bead a convoy tracks
# never receives it and stays open. -----------------------------------------

buildbasic_root='{
  "id": "zz-fixture-buildbasic-root", "status": "closed", "title": "build-basic",
  "labels": [],
  "metadata": {
    "gc.delivery_status": "merged", "gc.work_outcome": "shipped",
    "gc.github_repo": "example-org/example-repo", "gc.pr_number": 45,
    "gc.pr_head": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "gc.merge_commit": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "gc.var.convoy_id": "zz-fixture-convoy"
  }
}'
authorized_by_root='{
  "id": "zz-fixture-consolidate-root", "status": "closed", "title": "Consolidate worktrees into one branch + PR",
  "labels": [],
  "metadata": {
    "gc.delivery_status": "merged", "gc.work_outcome": "shipped",
    "gc.github_repo": "example-org/example-repo", "gc.pr_number": 47,
    "gc.pr_head": "cccccccccccccccccccccccccccccccccccccccc",
    "gc.merge_commit": "dddddddddddddddddddddddddddddddddddddddd",
    "gc.authorized_by": "zzfixture-direct"
  }
}'
adr_authorized_root='{
  "id": "zz-fixture-adr-authorized-root", "status": "closed", "title": "Unrelated delivered workflow",
  "labels": [],
  "metadata": {
    "gc.delivery_status": "merged", "gc.work_outcome": "shipped",
    "gc.github_repo": "example-org/example-repo", "gc.pr_number": 50,
    "gc.pr_head": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
    "gc.merge_commit": "ffffffffffffffffffffffffffffffffffffffff",
    "gc.authorized_by": "ADR-0017 (Factory improvements need root cause); observed live 2026-09-19"
  }
}'
already_closed_exec_root='{
  "id": "zz-fixture-noop-root", "status": "closed", "title": "Already reconciled",
  "labels": [],
  "metadata": {
    "gc.delivery_status": "merged", "gc.work_outcome": "shipped",
    "gc.github_repo": "example-org/example-repo", "gc.pr_number": 60,
    "gc.pr_head": "1111111111111111111111111111111111111a",
    "gc.merge_commit": "2222222222222222222222222222222222222b",
    "gc.var.convoy_id": "zz-fixture-noop-convoy"
  }
}'

# 9. build-basic shape: gc.var.convoy_id -> convoy -> open execution bead.
#    Reconciled: exec bead gets all six proof fields + gc.delivered_via and
#    closes; its convoy closes alongside it.
jq -n --argjson r "$buildbasic_root" '[$r]' > "$BEADS_FILE"
jq -n '{"zz-fixture-exec-buildbasic":"open","zz-fixture-convoy":"open"}' > "$EXEC_STATUS_FILE"
jq -n '{"zz-fixture-convoy":"zz-fixture-exec-buildbasic"}' > "$CONVOY_CHILDREN_FILE"
: > "$UPDATE_LOG"
out=$(guard)
grep -q "zz-fixture-buildbasic-root (city) delivered (merged example-org/example-repo#45) but its execution bead zz-fixture-exec-buildbasic is still open" <<<"$out" \
  || { echo "$out" >&2; fail "build-basic-shaped delivery gap was not detected"; }
call=$(grep "^zz-fixture-exec-buildbasic " "$UPDATE_LOG" || true)
for field in \
  "gc.delivery_status=merged" "gc.work_outcome=shipped" \
  "gc.github_repo=example-org/example-repo" "gc.pr_number=45" \
  "gc.pr_head=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" \
  "gc.merge_commit=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" \
  "gc.delivered_via=zz-fixture-buildbasic-root" "--status=closed"
do
  [[ $call == *"$field"* ]] || fail "reconcile call missing $field: $call"
done
grep -q "^zz-fixture-convoy --status=closed" "$UPDATE_LOG" \
  || { echo "$UPDATE_LOG contents:"; cat "$UPDATE_LOG" >&2; fail "the input convoy was not closed alongside its execution bead"; }

# 10. direct gc.authorized_by shape (smb-jz34 -> smb-fpbj): no convoy_id, so
#     no convoy is touched -- only the execution bead closes.
jq -n --argjson r "$authorized_by_root" '[$r]' > "$BEADS_FILE"
jq -n '{"zzfixture-direct":"open"}' > "$EXEC_STATUS_FILE"
jq -n '{}' > "$CONVOY_CHILDREN_FILE"
: > "$UPDATE_LOG"
out=$(guard)
grep -q "^zzfixture-direct .*--status=closed" "$UPDATE_LOG" \
  || { echo "$out" >&2; fail "gc.authorized_by-linked execution bead was not closed"; }
[ "$(grep -c '^zzfixture-direct ' "$UPDATE_LOG")" = "1" ] || fail "expected exactly one write to the directly-linked execution bead"

# 11. gc.authorized_by names a non-bead reference (an ADR citation, the real
#     af-gpq0y shape on af-hc2mx-authored beads) -- never guessed at as a
#     bead id, nothing written.
jq -n --argjson r "$adr_authorized_root" '[$r]' > "$BEADS_FILE"
jq -n '{}' > "$EXEC_STATUS_FILE"
jq -n '{}' > "$CONVOY_CHILDREN_FILE"
: > "$UPDATE_LOG"
out=$(guard)
[ -z "$(cat "$UPDATE_LOG")" ] || { echo "$out" >&2; fail "an ADR-citation gc.authorized_by value must never be treated as a bead id"; }
grep -q "convoy-delivery:city — no delivered workflow bead has an open execution bead behind it" <<<"$out" \
  || { echo "$out" >&2; fail "the ADR-citation case should read as healthy, not reconciled"; }

# 12. execution bead already closed: nothing to do, reported healthy.
jq -n --argjson r "$already_closed_exec_root" '[$r]' > "$BEADS_FILE"
jq -n '{"zz-fixture-exec-noop":"closed"}' > "$EXEC_STATUS_FILE"
jq -n '{"zz-fixture-noop-convoy":"zz-fixture-exec-noop"}' > "$CONVOY_CHILDREN_FILE"
: > "$UPDATE_LOG"
out=$(guard)
[ -z "$(cat "$UPDATE_LOG")" ] || { echo "$out" >&2; fail "an already-closed execution bead should not be touched"; }

# 13. --check-only reports the gap but writes nothing.
jq -n --argjson r "$buildbasic_root" '[$r]' > "$BEADS_FILE"
jq -n '{"zz-fixture-exec-buildbasic":"open","zz-fixture-convoy":"open"}' > "$EXEC_STATUS_FILE"
jq -n '{"zz-fixture-convoy":"zz-fixture-exec-buildbasic"}' > "$CONVOY_CHILDREN_FILE"
: > "$UPDATE_LOG"
out=$(guard --check-only)
grep -q "execution bead zz-fixture-exec-buildbasic was never closed" <<<"$out" \
  || { echo "$out" >&2; fail "--check-only did not report the convoy-delivery gap"; }
[ -z "$(cat "$UPDATE_LOG")" ] || fail "--check-only wrote to Beads for the convoy-delivery check"
grep -q "^UNRESOLVED" <<<"$out" || fail "an unreconciled convoy-delivery gap must not read as healthy under --check-only"

# 13. the convoy-delivery check reads each store ONCE, never one `bd show`
#     per bead (64 shows a tick cost ~61 s of factory-guard's 180 s budget) --
jq -n --argjson r "$buildbasic_root" '[$r]' > "$BEADS_FILE"
jq -n '{"zz-fixture-exec-buildbasic":"open","zz-fixture-convoy":"open"}' > "$EXEC_STATUS_FILE"
jq -n '{"zz-fixture-convoy":"zz-fixture-exec-buildbasic"}' > "$CONVOY_CHILDREN_FILE"
: > "$TMP_SHOW_LOG"; : > "$TMP_LIST_ALL_LOG"
out=$(guard --check-only)
grep -q "execution bead zz-fixture-exec-buildbasic is still open" <<<"$out" \
  || { echo "$out" >&2; fail "the one-read status map lost the open execution bead"; }
[ ! -s "$TMP_SHOW_LOG" ] || fail "convoy-delivery still looks beads up one by one: $(tr '\n' ' ' < "$TMP_SHOW_LOG")"
[ "$(wc -l < "$TMP_LIST_ALL_LOG")" = "1" ] || fail "the city store should be read exactly once"

# reset the fixture files so they don't leak into any test appended after this one
jq -n '{}' > "$EXEC_STATUS_FILE"; jq -n '{}' > "$CONVOY_CHILDREN_FILE"

echo "PASS: factory-delivery-guard backfills verified proof and flags the rest exactly once"
