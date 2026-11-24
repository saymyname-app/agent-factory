#!/usr/bin/env bash
#
# on-order-failed pages the Mayor once a chronic order is failing, instead of
# leaving order.failed events unread forever (O1: 371 in 24h, live, none read).
#
# Drives the real script against a stub gc whose `events` subcommand returns
# canned order.failed lines, and asserts: below the streak threshold, nothing
# happens; at or above it, exactly one bead is filed and the Mayor is paged
# once; a second run recognises the still-open bead, or the same bead taken
# for repair, and does not duplicate it; a new series of the same order while
# its bead is unfinished is a comment on it, never a second bead
# (af-56yoam.8); a different order gets its own bead; --check-only files
# nothing.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SCRIPT="$REPO_ROOT/bin/on-order-failed"
# tests/lib/sandbox.sh (P10, af-ygibh): a throwaway HOME/city and, crucially,
# GC_BIN pointed off the real binary. on-order-failed shells out to
# bin/escalation-door, which resolves ${GC_BIN:-gc} directly, so a PATH-only
# stub does not stop it reaching the live city (live incident 2026-09-29,
# af-0h4vnc: this test paged the live Mayor and filed a real bead -- "af-new1"
# resolved to the unrelated live bead af-fnew1).
. "$REPO_ROOT/tests/lib/sandbox.sh"
sandbox_init
TMP="$SANDBOX_DIR"
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/bin" "$TMP/beads"
CALLS="$TMP/calls.log"; : > "$CALLS"
EVENTS_FILE="$TMP/events.jsonl"

events_add() {  # events_add <subject> <count> <first minute> [message]: one failure a minute from 12:<first>
  local subject=$1 count=$2 first=$3 message=${4:-exit status 1} i
  for ((i = first; i < first + count; i++)); do
    jq -nc --arg message "$message" --arg subject "$subject" --arg ts "2026-09-17T12:$(printf '%02d' "$i"):00Z" \
      '{actor:"controller",message:$message,payload:{},subject:$subject,ts:$ts,type:"order.failed",ok:true}' \
      >> "$EVENTS_FILE"
  done
}
events_n() {  # events_n <subject> <count> [message]: only these failures, from 12:00
  : > "$EVENTS_FILE"
  events_add "$1" "$2" 0 "${3:-exit status 1}"
}

# The tracker stub: $TMP/beads/filed holds one bead per line,
# <id> TAB <order> TAB <gc.order_series_at> TAB <created_at>, all of the status
# in $TMP/beads/filed-status (open when absent); $TMP/beads/closed-at is the
# closing time of an older, closed bead of any order.
cat > "$TMP/bin/gc" <<'STUB'
#!/usr/bin/env bash
TMP=@TMP@
printf '%s\n' "$*" >> "$TMP/calls.log"
if [[ ${1:-} == events ]]; then
  cat "$TMP/events.jsonl" 2>/dev/null
  exit 0
fi
if [[ ${1:-} == bd && ${2:-} == list ]]; then
  [[ -f "$TMP/beads/list-fails" ]] && exit 1
  field=""; status=""
  args=("$@")
  for i in "${!args[@]}"; do
    [[ ${args[$i]} == --metadata-field ]] && field="${args[$((i+1))]}"
    [[ ${args[$i]} == --status ]] && status="${args[$((i+1))]}"
  done
  order=${field#gc.order_subject=}
  if [[ $status == closed ]]; then
    if [[ -f "$TMP/beads/closed-at" ]]; then
      echo '[{"id":"af-old","closed_at":"'"$(cat "$TMP/beads/closed-at")"'"}]'
    else
      echo '[]'
    fi
    exit 0
  fi
  filed_status=open; [[ -f "$TMP/beads/filed-status" ]] && filed_status=$(cat "$TMP/beads/filed-status")
  if [[ ",$status," != *",$filed_status,"* || ! -f "$TMP/beads/filed" ]]; then echo '[]'; exit 0; fi
  awk -F'\t' -v o="$order" '$2 == o' "$TMP/beads/filed" \
    | jq -Rsc 'split("\n") | map(select(length > 0) | split("\t")
        | {id: .[0], created_at: .[3], metadata: ({"gc.order_subject": .[1]}
           + (if .[2] == "" then {} else {"gc.order_series_at": .[2]} end))})'
  exit 0
fi
if [[ ${1:-} == bd && ${2:-} == create ]]; then
  meta=""; args=("$@")
  for i in "${!args[@]}"; do [[ ${args[$i]} == --metadata ]] && meta="${args[$((i+1))]}"; done
  id="af-new$(( $(cat "$TMP/beads/filed" 2>/dev/null | wc -l) + 1 ))"
  printf '%s\t%s\t%s\t%s\n' "$id" "$(jq -r '.["gc.order_subject"]' <<<"$meta")" \
    "$(jq -r '.["gc.order_series_at"] // ""' <<<"$meta")" "2026-09-17T11:00:00Z" >> "$TMP/beads/filed"
  echo '{"id":"'"$id"'"}'
  exit 0
fi
if [[ ${1:-} == bd && ${2:-} == update && ${4:-} == --set-metadata && ${5:-} == gc.order_series_at=* ]]; then
  awk -F'\t' -v OFS='\t' -v id="$3" -v at="${5#gc.order_series_at=}" '$1 == id { $3 = at } 1' \
    "$TMP/beads/filed" > "$TMP/beads/filed.new" && mv "$TMP/beads/filed.new" "$TMP/beads/filed"
  exit 0
fi
if [[ ${1:-} == bd && ${2:-} == show ]]; then
  # escalation-door's own show_bead call -- every id on the mayor path here
  # is a bead this test just filed, so a minimal open bead is always valid.
  echo '[{"id":"'"${3:-}"'","status":"open","metadata":{}}]'
  exit 0
fi
exit 0
STUB
sed -i "s|@TMP@|$TMP|" "$TMP/bin/gc"
chmod +x "$TMP/bin/gc"
export PATH="$TMP/bin:$PATH"
export GC_BIN="$TMP/bin/gc"
export FACTORY_ROOT="$TMP"
export ON_ORDER_FAILED_STREAK=5
touch "$TMP/city.toml" 2>/dev/null || true

run() { FACTORY_ROOT="$TMP" "$SCRIPT" "$@" 2>&1; }

# --- an explicit capacity deferral is replayable, not a chronic failure ----
events_n convoy-advance 5 \
  "exit status 75: convoy-advance: échec de la passe -- af-strhoy integration.error: refus : tests NOT RUN, exit 75; retry next pass"
out=$(run)
grep -q "^bd create" "$CALLS" && fail "filed a bead for explicit NOT RUN/75 capacity deferrals"
grep -q "^mail send" "$CALLS" && fail "paged the Mayor for explicit NOT RUN/75 capacity deferrals"

# --- below the streak threshold: nothing happens -----------------------------
: > "$CALLS"
events_n dolt-remotes-patrol 4
out=$(run)
grep -q "mail send mayor" "$CALLS" && fail "paged below the failure streak threshold"
[ ! -s "$TMP/beads/filed" ] || fail "filed a bead below the failure streak threshold"

# --- at the threshold: files exactly one bead, pages the mayor once ---------
: > "$CALLS"
events_n dolt-remotes-patrol 5
out=$(run)
grep -q "^bd create" "$CALLS" || { echo "$out" >&2; fail "did not file a bead at the streak threshold"; }
grep -q "^mail send mayor" "$CALLS" || fail "did not page the mayor at the streak threshold"
# Routed through escalation-door's Mayor-first class (O06/O07), not a raw mail.
grep -q "^mail send mayor --notify -s Escalation (Mayor first): af-new1" "$CALLS" \
  || fail "did not route through escalation-door's mayor-first class"
[ "$(grep -c '^bd create' "$CALLS")" = "1" ] || fail "filed more than one bead in a single run"
# The count is a total inside the lookback window, so the page must not claim a run.
grep -q "consecutive failures" "$CALLS" && fail "the page words a total count as consecutive failures"

# --- a second run recognises the still-open bead: no duplicate --------------
: > "$CALLS"
out=$(run)
grep -q "^bd create" "$CALLS" && fail "duplicated an already-open finding"
grep -q "^mail send mayor" "$CALLS" && fail "re-paged an already-open finding"
grep -q "^bd comments add" "$CALLS" && fail "told again a series its bead already holds"

# --- two more series of the same order: one bead, two comments (af-56yoam.8) -
# Live: one bead per series, about a hundred [on-order-failed] beads since October.
: > "$CALLS"
events_add dolt-remotes-patrol 5 10 "exit status 1: second series"
out=$(run)
events_add dolt-remotes-patrol 5 20 "exit status 1: third series"
out+=$(run)
out+=$(run)
grep -q "^bd create" "$CALLS" && { echo "$out" >&2; fail "filed a second bead for a new series of an unfinished one"; }
grep -q "^mail send" "$CALLS" && fail "paged again for a new series of an unfinished bead"
[ "$(grep -c '^bd comments add af-new1 ' "$CALLS")" = "2" ] || { cat "$CALLS" >&2; fail "two new series are not two comments on the one bead"; }
grep -q "^bd comments add af-new1 New failure series of order 'dolt-remotes-patrol': 5 failures since 2026-09-17T12:04:00Z, latest at 2026-09-17T12:14:00Z (latest: exit status 1: second series)" "$CALLS" \
  || { cat "$CALLS" >&2; fail "the comment does not give the series' count, dates and latest error"; }
grep -q "^bd comments add af-new1 .*: 5 failures since 2026-09-17T12:14:00Z, latest at 2026-09-17T12:24:00Z" "$CALLS" \
  || { cat "$CALLS" >&2; fail "the second comment does not start after the first series told"; }

# --- an open bead filed before the series mark counts from its creation -------
# The one live open bead (pr-autopilot, 2026-11-24) carries no gc.order_series_at.
printf 'af-legacy\tlegacy-order\t\t2026-09-17T12:02:30Z\n' > "$TMP/beads/filed"; : > "$CALLS"
events_n legacy-order 8
out=$(run)
grep -q "^bd create" "$CALLS" && fail "filed a bead beside an open one filed before the series mark"
grep -q "^bd comments add af-legacy .*: 5 failures since 2026-09-17T12:02:30Z" "$CALLS" \
  || { echo "$out" >&2; cat "$CALLS" >&2; fail "an unmarked open bead does not count the series from its creation"; }
rm -f "$TMP/beads/filed"

# --- two different orders: two beads -----------------------------------------
: > "$CALLS"
events_n dolt-remotes-patrol 5
events_add factory-guard 5 10
out=$(run)
[ "$(grep -c '^bd create' "$CALLS")" = "2" ] || { echo "$out" >&2; fail "two failing orders did not get a bead each"; }
grep -q "^bd create \[on-order-failed\] factory-guard failing repeatedly" "$CALLS" || fail "the second order has no bead of its own"
grep -q "^bd comments add" "$CALLS" && fail "an order's series was told on another order's bead"
printf 'af-new1\tdolt-remotes-patrol\t2026-09-17T12:04:00Z\t2026-09-17T11:00:00Z\n' > "$TMP/beads/filed"
events_n dolt-remotes-patrol 5

# --- a bead taken for repair still answers its cause (af-yzojic) -------------
# Live: af-65mbq2 in_progress under its repair, three duplicates filed beside it.
for taken in in_progress blocked; do
  echo "$taken" > "$TMP/beads/filed-status"; : > "$CALLS"
  out=$(run)
  grep -q "^bd create" "$CALLS" && { echo "$out" >&2; fail "duplicated a finding whose bead is $taken"; }
  grep -q "^mail send mayor" "$CALLS" && fail "re-paged a finding whose bead is $taken"
done
rm -f "$TMP/beads/filed-status"

# --- --check-only never files or pages ---------------------------------------
rm -f "$TMP/beads/filed"; : > "$CALLS"
out=$(run --check-only)
grep -q "^bd create" "$CALLS" && fail "--check-only filed a bead"
grep -q "^mail send" "$CALLS" && fail "--check-only paged anyone"
grep -q "would flag dolt-remotes-patrol" <<<"$out" || { echo "$out" >&2; fail "--check-only did not report what it would do"; }

# --- a closed bead answers the failures before its closing (af-yzo8fo.2) -----
# events_n dates the failures 12:00, 12:01, ... one a minute.
rm -f "$TMP/beads/filed"; : > "$CALLS"
events_n dolt-remotes-patrol 5
echo "2026-09-17T12:02:30Z" > "$TMP/beads/closed-at"
out=$(run)
grep -q "^bd create" "$CALLS" && { echo "$out" >&2; fail "refiled a bead for failures its closed bead already answered"; }
grep -q "2 failure(s) since its last bead closed" <<<"$out" || { echo "$out" >&2; fail "did not say how many failures follow the closing"; }

# ...and the streak counts again from that closing: a new bead.
: > "$CALLS"
events_n dolt-remotes-patrol 8
out=$(run)
grep -q "^bd create" "$CALLS" || { echo "$out" >&2; fail "did not file a bead for a new streak after the closing"; }
grep -q "failed 5 times" "$CALLS" || fail "the page does not count the failures after the closing"
rm -f "$TMP/beads/closed-at"

# --- a tracker read that fails files nothing ----------------------------------
rm -f "$TMP/beads/filed"; : > "$CALLS"
touch "$TMP/beads/list-fails"
events_n dolt-remotes-patrol 6
out=$(run)
grep -q "^bd create" "$CALLS" && fail "filed a bead although the open beads could not be read"
grep -q "could not read the open beads" <<<"$out" || { echo "$out" >&2; fail "did not say the read failed"; }
rm -f "$TMP/beads/list-fails"

# --- no events at all: quiet, no error ---------------------------------------
: > "$EVENTS_FILE"; : > "$CALLS"
run >/dev/null || fail "an empty event stream must not be an error"
grep -qE '^(bd |mail )' "$CALLS" && fail "an empty event stream should not call gc bd/mail at all"

echo "OK on-order-failed pages a chronic failure, not a transient one"
