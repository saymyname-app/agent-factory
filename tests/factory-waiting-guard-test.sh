#!/usr/bin/env bash
#
# bin/factory-waiting-guard: gc.waiting_on keeps a bead out of the idle
# ladder (lib/factory_campaign.py is_ladder_bead) unconditionally -- nothing
# used to clear it once the bead it named closed. Regression for the live
# 2026-09-19 incident (af-atyry): af-p4v9v carried gc.waiting_on=af-r3j5r,
# which closed via PR #141, and sat excluded from the ladder for 14+ hours
# with no mechanism to notice or clear it.
#
# Drives the guard against a stub gc binary and proves: a bead waiting on a
# bead ID that is still open is left alone; a bead waiting on free text (not
# a bead-ID shape, e.g. "stalled") is left alone, never reported; a bead
# waiting on a closed bead ID is reported under --check-only (untouched) and
# repaired (gc.waiting_on cleared, Mayor paged once) by a default run; a bead
# waiting on a bead ID that resolves nowhere is reported and, on a default
# run, marked with gc.waiting_on_missing_reported and paged once -- then a
# second run with that marker already in place stays silent (no repeat page)
# for the same value.
#
# All bead ids here are synthetic fixtures (zzwait-*/zztgt-*), never a real
# af-* id from the live store.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/factory-waiting-guard"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

export BEADS_FILE="$TMP/waiting_beads.json"
export TARGETS_FILE="$TMP/targets.json"; echo '[]' > "$TARGETS_FILE"
export UPDATE_LOG="$TMP/updates.log"; : > "$UPDATE_LOG"
export MAIL_LOG="$TMP/mail.log"; : > "$MAIL_LOG"
mkdir -p "$TMP/bin"

# --- stub gc: `bd list` serves BEADS_FILE (the open beads carrying
# gc.waiting_on), `bd show <id>` resolves against TARGETS_FILE (what
# gc.waiting_on names), `bd update`/`mail send` are recorded ---------------
cat > "$TMP/bin/gc" <<'STUB'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ ${1:-} == --city ]]; then shift 2; fi
if [[ ${1:-} == bd && ${2:-} == list ]]; then
  cat "$BEADS_FILE"
  exit 0
fi
if [[ ${1:-} == bd && ${2:-} == show ]]; then
  id=$3
  match=$(jq -c --arg id "$id" '[.[] | select(.id == $id)]' "$TARGETS_FILE")
  if [[ "$match" == "[]" ]]; then
    echo '{"error":"no issues found matching the provided IDs","schema_version":1}'
    exit 1
  fi
  echo "$match"
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

export PATH="$TMP/bin:$PATH"
# GC_BIN is pre-exported to the real `gc` in every Gas City agent session,
# which silently outranks a PATH-only stub -- override it explicitly, same
# as tests/factory-dispatch-guard-test.sh and friends.
export GC_BIN="$TMP/bin/gc"
touch "$TMP/city.toml"

guard() { FACTORY_ROOT="$TMP" "$GUARD" "$@" 2>&1 || true; }
update_count() { grep -c "^$1 " "$UPDATE_LOG" 2>/dev/null || true; }
mail_count() { grep -c "^mail-to=$1$" "$MAIL_LOG" 2>/dev/null || true; }

echo '[
  {"id": "zztgt-open",   "status": "open"},
  {"id": "zztgt-closed", "status": "closed", "closed_at": "2026-09-18T18:31:07Z"}
]' > "$TARGETS_FILE"

waiting_open='{
  "id": "zzwait-open", "status": "open", "title": "Legitimately waiting",
  "metadata": {"gc.waiting_on": "zztgt-open"}
}'
waiting_freetext='{
  "id": "zzwait-freetext", "status": "open", "title": "Waiting on a person",
  "metadata": {"gc.waiting_on": "stalled"}
}'
waiting_closed='{
  "id": "zzwait-closed", "status": "open", "title": "Waiting on something already done",
  "metadata": {"gc.waiting_on": "zztgt-closed"}
}'
waiting_missing='{
  "id": "zzwait-missing", "status": "open", "title": "Waiting on a typo'"'"'d or vanished bead",
  "metadata": {"gc.waiting_on": "zztgt-missing"}
}'

# 1. open target, free-text wait: both left alone, reported healthy ---------
jq -n --argjson a "$waiting_open" --argjson b "$waiting_freetext" '[$a, $b]' > "$BEADS_FILE"
out=$(guard --check-only)
grep -q "healthy — 2 open bead(s) with gc.waiting_on checked, 0 closed-target wait(s), 0 unproven-delivery wait(s) and 0 missing-target wait(s)" <<<"$out" \
  || { echo "$out" >&2; fail "open-target/free-text waits were not reported healthy"; }
[ "$(update_count zzwait-open)" = "0" ] || fail "touched a bead legitimately waiting on an open bead"
[ "$(update_count zzwait-freetext)" = "0" ] || fail "touched a bead waiting on free text"
[ "$(mail_count mayor)" = "0" ] || fail "paged the Mayor with nothing wrong"

# 2. closed target: --check-only reports it, writes and pages nothing ------
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
jq -n --argjson c "$waiting_closed" '[$c]' > "$BEADS_FILE"
out=$(guard --check-only)
grep -q "zzwait-closed: gc.waiting_on='zztgt-closed' but that bead is already closed" <<<"$out" \
  || { echo "$out" >&2; fail "closed-target wait was not reported under --check-only"; }
grep -q "^UNRESOLVED" <<<"$out" || fail "a real closed-target wait under --check-only must not read as healthy"
[ "$(update_count zzwait-closed)" = "0" ] || fail "--check-only wrote to Beads"
[ "$(mail_count mayor)" = "0" ] || fail "--check-only paged the Mayor"

# 3. closed target: default run clears gc.waiting_on, pages the Mayor once -
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
out=$(guard)
grep -q "cleared gc.waiting_on='zztgt-closed' (closed) — eligible for the idle ladder again" <<<"$out" \
  || { echo "$out" >&2; fail "closed-target wait was not repaired and reported"; }
call=$(grep "^zzwait-closed " "$UPDATE_LOG" || true)
[[ $call == *'--unset-metadata gc.waiting_on'* ]] || fail "repair call did not clear gc.waiting_on: $call"
[[ $call == *"--append-notes"* ]] || fail "repair call left no note: $call"
[ "$(mail_count mayor)" = "1" ] || fail "expected exactly one page to the Mayor"

# 4. A closed PR-backed target is not enough: P01/P02-shaped open-review,
# red-CI, and head-mismatch proof must keep the wait. Exact merge+CI proof and
# explicit no-op retain the historical closed-target clearing semantics.
jq '. + [
  {"id":"zztgt-p01","status":"closed","metadata":{
    "gc.plane":"delivery","gc.graph_digest":"sha256:5555555555555555555555555555555555555555555555555555555555555555",
    "gc.pr_url":"https://github.com/example-org/example-repo/pull/197"}},
  {"id":"zztgt-red","status":"closed","metadata":{
    "gc.delivery_status":"merged","gc.work_outcome":"shipped","gc.github_repo":"example-org/example-repo",
    "gc.pr_number":200,"gc.pr_head":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "gc.merge_commit":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "gc.pr_url":"https://github.com/example-org/example-repo/pull/200","pr_number":200,
    "merge_result":"merged","merged_sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","merged_target":"main",
    "gc.required_ci_workflow":"Factory CI","gc.ci_run_id":35882143816,
    "gc.ci_head_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","gc.ci_conclusion":"failure"}},
  {"id":"zztgt-head","status":"closed","metadata":{
    "gc.delivery_status":"merged","gc.work_outcome":"shipped","gc.github_repo":"example-org/example-repo",
    "gc.pr_number":201,"gc.pr_head":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "gc.merge_commit":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "gc.pr_url":"https://github.com/example-org/example-repo/pull/201","pr_number":201,
    "merge_result":"merged","merged_sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","merged_target":"main",
    "gc.required_ci_workflow":"Factory CI","gc.ci_run_id":35882143817,
    "gc.ci_head_sha":"cccccccccccccccccccccccccccccccccccccccc","gc.ci_conclusion":"success"}},
  {"id":"zztgt-proven","status":"closed","metadata":{
    "gc.delivery_status":"merged","gc.work_outcome":"shipped","gc.github_repo":"example-org/example-repo",
    "gc.pr_number":202,"gc.pr_head":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "gc.merge_commit":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "gc.pr_url":"https://github.com/example-org/example-repo/pull/202","pr_number":202,
    "merge_result":"merged","merged_sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","merged_target":"main",
    "gc.required_ci_workflow":"Factory CI","gc.ci_run_id":35882143818,
    "gc.ci_head_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","gc.ci_conclusion":"success"}},
  {"id":"zztgt-noop","status":"closed","metadata":{
    "gc.plane":"delivery","gc.graph_digest":"sha256:5555555555555555555555555555555555555555555555555555555555555555",
    "gc.work_outcome":"no-op"}}
]' "$TARGETS_FILE" > "$TARGETS_FILE.next" && mv "$TARGETS_FILE.next" "$TARGETS_FILE"

jq -n '[
  {"id":"zzwait-p01","status":"open","metadata":{"gc.waiting_on":"zztgt-p01"}},
  {"id":"zzwait-red","status":"open","metadata":{"gc.waiting_on":"zztgt-red"}},
  {"id":"zzwait-head","status":"open","metadata":{"gc.waiting_on":"zztgt-head"}},
  {"id":"zzwait-proven","status":"open","metadata":{"gc.waiting_on":"zztgt-proven"}},
  {"id":"zzwait-noop","status":"open","metadata":{"gc.waiting_on":"zztgt-noop"}}
]' > "$BEADS_FILE"
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
out=$(guard)
for id in zzwait-p01 zzwait-red zzwait-head; do
  [ "$(update_count "$id")" = "0" ] || fail "$id was released without structural delivery proof"
done
grep -q "zzwait-p01: gc.waiting_on='zztgt-p01' is closed but cannot release the wait" <<<"$out" \
  || { echo "$out" >&2; fail "P01 closed-under-review wait was not rejected"; }
grep -q "gc.ci_conclusion" <<<"$out" || { echo "$out" >&2; fail "red CI was not named in the rejection"; }
grep -q "gc.ci_head_sha!=gc.pr_head" <<<"$out" \
  || { echo "$out" >&2; fail "head-mismatched CI was not named in the rejection"; }
for id in zzwait-proven zzwait-noop; do
  call=$(grep "^$id " "$UPDATE_LOG" || true)
  [[ $call == *'--unset-metadata gc.waiting_on'* ]] || fail "$id did not clear after a valid terminal outcome"
done

# 5. missing target: --check-only reports it, writes and pages nothing -----
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
jq -n --argjson d "$waiting_missing" '[$d]' > "$BEADS_FILE"
out=$(guard --check-only)
grep -q "zzwait-missing: gc.waiting_on='zztgt-missing' names a bead ID that does not exist" <<<"$out" \
  || { echo "$out" >&2; fail "missing-target wait was not reported under --check-only"; }
[ "$(update_count zzwait-missing)" = "0" ] || fail "--check-only wrote to Beads"
[ "$(mail_count mayor)" = "0" ] || fail "--check-only paged the Mayor"

# 6. missing target: default run records the report marker and pages once -
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
out=$(guard)
grep -q "reported missing gc.waiting_on target 'zztgt-missing' (left in place; kept out of the ladder)" <<<"$out" \
  || { echo "$out" >&2; fail "missing-target wait was not marked reported"; }
call=$(grep "^zzwait-missing " "$UPDATE_LOG" || true)
[[ $call == *'--set-metadata gc.waiting_on_missing_reported=zztgt-missing'* ]] \
  || fail "report call did not set the missing-report marker: $call"
[ "$(mail_count mayor)" = "1" ] || fail "expected exactly one page to the Mayor"

# 7. same missing value, marker already recorded: silent, no repeat page ---
# (the guard itself never rewrites BEADS_FILE -- reflect what step 5's write
# would have produced, same as factory-dispatch-guard-test.sh does for its
# own repair-then-rerun case.)
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
waiting_missing_reported='{
  "id": "zzwait-missing", "status": "open", "title": "Waiting on a typo'"'"'d or vanished bead",
  "metadata": {"gc.waiting_on": "zztgt-missing", "gc.waiting_on_missing_reported": "zztgt-missing"}
}'
jq -n --argjson e "$waiting_missing_reported" '[$e]' > "$BEADS_FILE"
out=$(guard)
grep -q "healthy — 1 open bead(s) with gc.waiting_on checked, 0 closed-target wait(s), 0 unproven-delivery wait(s) and 1 missing-target wait(s)" <<<"$out" \
  || { echo "$out" >&2; fail "an already-reported missing target was not treated as quiet/healthy"; }
[ "$(update_count zzwait-missing)" = "0" ] || fail "re-wrote a missing-target report already recorded for the same value"
[ "$(mail_count mayor)" = "0" ] || fail "re-paged the Mayor for a missing-target value already reported"

echo "PASS: factory-waiting-guard clears gc.waiting_on once its target closes, reports an unresolvable target once, and leaves open/free-text waits alone"
