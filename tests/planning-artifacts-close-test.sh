#!/usr/bin/env bash
#
# bin/planning-artifacts-close (W06, A6b): when a convoy closes, its Spec
# bead and the Ticket Graph Draft bead it was published from close too, with
# a reason naming the convoy. Both stay open and readable while the convoy
# is still open. A convoy published from a file draft (earlier graphs, whose
# gc.artifact_id/gc.spec_id are plain strings, not bead ids) is left
# untouched without error.
#
# All bead ids here are synthetic fixtures (zz-fixture*), never a real af-*
# id from the live store.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
TOOL="$REPO_ROOT/bin/planning-artifacts-close"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

export CONVOYS_FILE="$TMP/closed_convoys.json"; echo '[]' > "$CONVOYS_FILE"
export SHOW_FILE="$TMP/show_beads.json"; echo '{}' > "$SHOW_FILE"
export CLOSE_LOG="$TMP/closes.log"; : > "$CLOSE_LOG"
export SHOW_LOG="$TMP/shows.log"; : > "$SHOW_LOG"
export LIST_LOG="$TMP/lists.log"; : > "$LIST_LOG"
mkdir -p "$TMP/bin"

# --- stub gc: serves `bd list --type convoy --status closed`/`bd show` from
# the fixture files, records `bd show` and `bd close` calls and reflects the
# closes into SHOW_FILE so a second run of the tool sees the target already
# closed. As Beads 1.3 does, it refuses `bd close` on an assigned bead (the
# tool names no actor); `bd update --if-assignee X --assignee ""` releases
# the bead only from X, else writes nothing and exits 13 (af-bm9y90) ------
cat > "$TMP/bin/gc" <<'STUB'
#!/usr/bin/env bash
set -Eeuo pipefail
# A leading `--city DIR` is accepted, as gc does: bin/convoy-state names the
# city on every call (af-2o6oyl).
if [[ ${1:-} == --city ]]; then shift 2; fi
if [[ ${1:-} == bd && ${2:-} == list ]]; then
  sleep "${GC_TEST_LIST_SLEEP:-0}"
  printf '%s\n' "$*" >> "$LIST_LOG"
  # --closed-after keeps the convoys closed after it; a fixture without
  # closed_at was closed just now.
  after=""
  while [ $# -gt 0 ]; do
    case "$1" in --closed-after) after=$2; shift 2 ;; *) shift ;; esac
  done
  jq --arg after "$after" '[.[] | select($after == "" or (.closed_at // "9999") > $after)]' "$CONVOYS_FILE"
  exit 0
fi
if [[ ${1:-} == bd && ${2:-} == show ]]; then
  # As bd does with several ids: the ones that resolve come back as one
  # array, the others are only missing from it; none at all is an error
  # object and exit 1.
  shift 2
  ids=()
  for arg in "$@"; do [[ $arg == --* ]] || ids+=("$arg"); done
  printf '%s\n' "${ids[*]}" >> "$SHOW_LOG"
  found=$(jq -c '[$ARGS.positional[] as $id | .[$id] // empty]' "$SHOW_FILE" --args "${ids[@]}")
  if [ "$found" = "[]" ]; then
    echo '{"error": "no issues found matching the provided IDs", "schema_version": 1}'
    exit 1
  fi
  printf '%s\n' "$found"
  exit 0
fi
if [[ ${1:-} == bd && ${2:-} == update ]]; then
  id=$3
  if_assignee="<none>" assignee="<none>"
  shift 3
  while [ $# -gt 0 ]; do
    case "$1" in
      --if-assignee) if_assignee=$2; shift 2 ;;
      --assignee) assignee=$2; shift 2 ;;
      --append-notes) shift 2 ;;
      *) echo "unexpected bd update flag: $1" >&2; exit 64 ;;
    esac
  done
  [ "$assignee" = "" ] || { echo "unexpected bd update of $id" >&2; exit 64; }
  [ "$if_assignee" = "$(jq -r --arg id "$id" '.[$id].assignee // ""' "$SHOW_FILE")" ] || exit 13
  tmp=$(mktemp)
  jq --arg id "$id" 'del(.[$id].assignee)' "$SHOW_FILE" > "$tmp" && mv "$tmp" "$SHOW_FILE"
  exit 0
fi
if [[ ${1:-} == bd && ${2:-} == close ]]; then
  id=$3
  [ -z "$(jq -r --arg id "$id" '.[$id].assignee // ""' "$SHOW_FILE")" ] || {
    echo "cannot close $id: assignee is another actor" >&2
    exit 1
  }
  reason=""
  shift 3
  while [ $# -gt 0 ]; do
    case "$1" in
      --reason) reason=$2; shift 2 ;;
      *) shift ;;
    esac
  done
  printf '%s\t%s\n' "$id" "$reason" >> "$CLOSE_LOG"
  tmp=$(mktemp)
  jq --arg id "$id" '.[$id].status = "closed"' "$SHOW_FILE" > "$tmp" && mv "$tmp" "$SHOW_FILE"
  exit 0
fi
echo "unexpected gc invocation: $*" >&2
exit 64
STUB
chmod +x "$TMP/bin/gc"

export PATH="$TMP/bin:$PATH"
export GC_BIN="$TMP/bin/gc"
export FACTORY_ROOT="$TMP"

run_tool() { "$TOOL" "$@" 2>&1; }
close_count() { grep -c "^$1"$'\t' "$CLOSE_LOG" 2>/dev/null || true; }
bead_status() { jq -r --arg id "$1" '.[$id].status // "missing"' "$SHOW_FILE"; }

# =============================================================================
# 1. Convoy still open: bd list --status closed never returns it, so its
#    Spec/Draft beads are never touched.
# =============================================================================

jq -n '{
  "zz-fixture-spec-open": {"id": "zz-fixture-spec-open", "status": "open"},
  "zz-fixture-draft-open": {"id": "zz-fixture-draft-open", "status": "open"}
}' > "$SHOW_FILE"
echo '[]' > "$CONVOYS_FILE"   # the open convoy is not "closed", so bd list returns nothing for it
: > "$CLOSE_LOG"

out=$(run_tool)
grep -q "closed=0 skipped=0 failed=0" <<<"$out" || { echo "$out" >&2; fail "expected a no-op run while the convoy is open"; }
[ "$(bead_status zz-fixture-spec-open)" = "open" ] || fail "Spec bead was touched while its convoy is still open"
[ "$(bead_status zz-fixture-draft-open)" = "open" ] || fail "Draft bead was touched while its convoy is still open"

# =============================================================================
# 2. Convoy closed, bead mode: gc.artifact_id/gc.spec_id resolve to real
#    beads -- both close with a reason naming the convoy.
# =============================================================================

jq -n '{
  "zz-fixture-spec-1": {"id": "zz-fixture-spec-1", "status": "open"},
  "zz-fixture-draft-1": {"id": "zz-fixture-draft-1", "status": "open"}
}' > "$SHOW_FILE"
jq -n '[{
  "id": "zz-fixture-convoy-1", "title": "Fixture Convoy One", "status": "closed",
  "metadata": {"gc.artifact_id": "zz-fixture-draft-1", "gc.spec_id": "zz-fixture-spec-1"}
}]' > "$CONVOYS_FILE"
: > "$CLOSE_LOG"

out=$(run_tool)
grep -q "closed=2 skipped=0 failed=0" <<<"$out" || { echo "$out" >&2; fail "expected both Spec and Draft beads to close"; }
[ "$(bead_status zz-fixture-spec-1)" = "closed" ] || fail "Spec bead did not close when its convoy closed"
[ "$(bead_status zz-fixture-draft-1)" = "closed" ] || fail "Draft bead did not close when its convoy closed"
[ "$(close_count zz-fixture-spec-1)" = "1" ] || fail "expected exactly one close call for the Spec bead"
[ "$(close_count zz-fixture-draft-1)" = "1" ] || fail "expected exactly one close call for the Draft bead"
grep -q "^zz-fixture-spec-1"$'\t'".*zz-fixture-convoy-1" "$CLOSE_LOG" \
  || fail "close reason for the Spec bead does not name the convoy"
grep -q "^zz-fixture-draft-1"$'\t'".*zz-fixture-convoy-1" "$CLOSE_LOG" \
  || fail "close reason for the Draft bead does not name the convoy"

# --- idempotent: a second run over the same already-closed convoy touches
# nothing further --------------------------------------------------------
: > "$CLOSE_LOG"
out=$(run_tool)
grep -q "closed=0 skipped=2 failed=0" <<<"$out" || { echo "$out" >&2; fail "a re-run over an already-closed convoy should skip, not re-close"; }
[ "$(close_count zz-fixture-spec-1)" = "0" ] || fail "re-closed an already-closed Spec bead"
[ "$(close_count zz-fixture-draft-1)" = "0" ] || fail "re-closed an already-closed Draft bead"

# =============================================================================
# 2b. Spec handoff: the Spec bead was claimed for /to-tickets and is still
#     in_progress and assigned when its convoy closes -- it closes like an
#     open one, although the tool is not the actor that holds it (af-bm9y90).
# =============================================================================

jq -n '{
  "zz-fixture-spec-claimed": {"id": "zz-fixture-spec-claimed", "status": "in_progress",
    "assignee": "po-agent/zz-fixture-session",
    "metadata": {"wayfinder.offered_by": "po-agent/zz-fixture-offerer"}},
  "zz-fixture-draft-3": {"id": "zz-fixture-draft-3", "status": "open"}
}' > "$SHOW_FILE"
jq -n '[{
  "id": "zz-fixture-convoy-3", "title": "Fixture Convoy Three", "status": "closed",
  "metadata": {"gc.artifact_id": "zz-fixture-draft-3", "gc.spec_id": "zz-fixture-spec-claimed"}
}]' > "$CONVOYS_FILE"
: > "$CLOSE_LOG"

out=$(run_tool)
grep -q "closed=2 skipped=0 failed=0" <<<"$out" || { echo "$out" >&2; fail "expected the claimed Spec and its Draft to close"; }
[ "$(bead_status zz-fixture-spec-claimed)" = "closed" ] || fail "a claimed (in_progress, assigned) Spec bead did not close with its convoy"

# =============================================================================
# 3. Convoy closed, file-draft mode: gc.artifact_id/gc.spec_id are plain
#    identifier strings from a draft YAML, not bead ids -- `bd show` never
#    resolves them, so the convoy is left untouched, without error.
# =============================================================================

echo '{}' > "$SHOW_FILE"   # no bead in the store for the file-mode artifact/spec ids
jq -n '[{
  "id": "zz-fixture-convoy-2", "title": "Fixture Convoy Two (file draft)", "status": "closed",
  "metadata": {
    "gc.artifact_id": "ticket-graph-draft-zz-fixture",
    "gc.spec_id": "spec-zz-fixture-2026-09-30"
  }
}]' > "$CONVOYS_FILE"
: > "$CLOSE_LOG"

rc=0
out=$(run_tool) || rc=$?
[ "$rc" -eq 0 ] || { echo "$out" >&2; fail "a file-draft convoy must not error"; }
grep -q "closed=0 skipped=0 failed=0" <<<"$out" || { echo "$out" >&2; fail "a file-draft convoy's artifact/spec ids must be left untouched"; }
[ -s "$CLOSE_LOG" ] && fail "attempted to close a file-draft artifact/spec id"

# =============================================================================
# 4. Marked convoy (new flow, T22): it closes only by the acceptance or the
#    abandon command. Closed any other way, its Spec and its Draft stay open;
#    an unmarked convoy closed in the same run still closes its own.
# =============================================================================

jq -n '{
  "zz-fixture-spec-marked": {"id": "zz-fixture-spec-marked", "status": "open"},
  "zz-fixture-draft-marked": {"id": "zz-fixture-draft-marked", "status": "open"},
  "zz-fixture-spec-plain": {"id": "zz-fixture-spec-plain", "status": "open"},
  "zz-fixture-draft-plain": {"id": "zz-fixture-draft-plain", "status": "open"}
}' > "$SHOW_FILE"
jq -n '[{
  "id": "zz-fixture-convoy-marked", "title": "Fixture Convoy Marked", "status": "closed", "issue_type": "convoy",
  "close_reason": "convoy autoclose: all children closed",
  "metadata": {"gc.flow.mark": "new-flow/v1",
               "gc.artifact_id": "zz-fixture-draft-marked", "gc.spec_id": "zz-fixture-spec-marked"}
}, {
  "id": "zz-fixture-convoy-plain", "title": "Fixture Convoy Plain", "status": "closed", "issue_type": "convoy",
  "metadata": {"gc.artifact_id": "zz-fixture-draft-plain", "gc.spec_id": "zz-fixture-spec-plain"}
}]' > "$CONVOYS_FILE"
: > "$CLOSE_LOG"

rc=0
out=$(run_tool) || rc=$?
[ "$rc" -eq 0 ] || { echo "$out" >&2; fail "a marked convoy closed outside its commands must not fail the run"; }
grep -q "closed=2 skipped=0 failed=0" <<<"$out" || { echo "$out" >&2; fail "expected only the unmarked convoy's Spec and Draft to close"; }
[ "$(bead_status zz-fixture-spec-marked)" = "open" ] || fail "the Spec of a marked convoy closed outside acceptance or abandon was closed"
[ "$(bead_status zz-fixture-draft-marked)" = "open" ] || fail "the Draft of a marked convoy closed outside acceptance or abandon was closed"
[ "$(close_count zz-fixture-spec-marked)" = "0" ] || fail "a close was attempted on the Spec of a marked convoy"
[ "$(close_count zz-fixture-draft-marked)" = "0" ] || fail "a close was attempted on the Draft of a marked convoy"
grep -q "zz-fixture-convoy-marked" <<<"$out" || { echo "$out" >&2; fail "the run does not name the marked convoy it left alone"; }
[ "$(bead_status zz-fixture-spec-plain)" = "closed" ] || fail "an unmarked convoy no longer closes its Spec"
[ "$(bead_status zz-fixture-draft-plain)" = "closed" ] || fail "an unmarked convoy no longer closes its Draft"

# =============================================================================
# 5. The state command cannot say which closed convoys are marked: nothing is
#    closed, and the run fails.
# =============================================================================

jq -n '{
  "zz-fixture-spec-5": {"id": "zz-fixture-spec-5", "status": "open"},
  "zz-fixture-draft-5": {"id": "zz-fixture-draft-5", "status": "open"}
}' > "$SHOW_FILE"
jq -n '[{
  "id": "zz-fixture-convoy-5", "title": "Fixture Convoy Five", "status": "closed", "issue_type": "convoy",
  "metadata": {"gc.artifact_id": "zz-fixture-draft-5", "gc.spec_id": "zz-fixture-spec-5"}
}]' > "$CONVOYS_FILE"
: > "$CLOSE_LOG"
printf '#!/bin/sh\necho "{\"ok\": false}"\nexit 1\n' > "$TMP/bin/broken-convoy-state"
chmod +x "$TMP/bin/broken-convoy-state"

rc=0
out=$(CONVOY_STATE_BIN="$TMP/bin/broken-convoy-state" run_tool) || rc=$?
[ "$rc" -ne 0 ] || { echo "$out" >&2; fail "the run passed although the state command could not answer"; }
[ -s "$CLOSE_LOG" ] && fail "something was closed although the marked convoys could not be told apart"
[ "$(bead_status zz-fixture-spec-5)" = "open" ] || fail "a Spec was closed although the marked convoys could not be told apart"

# =============================================================================
# 6. The order runs on every bead close under a 60 s timeout (af-nybppo):
#    however many convoys have closed, their artifact/spec ids are resolved
#    in one tracker call -- bead-mode and file-draft convoys together, the
#    ids of a marked convoy closed outside its commands left out. A Spec two
#    convoys share is closed once.
# =============================================================================

jq -n '{
  "zz-fixture-spec-6a": {"id": "zz-fixture-spec-6a", "status": "open"},
  "zz-fixture-draft-6a": {"id": "zz-fixture-draft-6a", "status": "open"},
  "zz-fixture-draft-6b": {"id": "zz-fixture-draft-6b", "status": "closed"},
  "zz-fixture-spec-6m": {"id": "zz-fixture-spec-6m", "status": "open"},
  "zz-fixture-draft-6m": {"id": "zz-fixture-draft-6m", "status": "open"}
}' > "$SHOW_FILE"
jq -n '[{
  "id": "zz-fixture-convoy-6a", "title": "Fixture Convoy Six A", "status": "closed", "issue_type": "convoy",
  "metadata": {"gc.artifact_id": "zz-fixture-draft-6a", "gc.spec_id": "zz-fixture-spec-6a"}
}, {
  "id": "zz-fixture-convoy-6b", "title": "Fixture Convoy Six B", "status": "closed", "issue_type": "convoy",
  "metadata": {"gc.artifact_id": "zz-fixture-draft-6b", "gc.spec_id": "zz-fixture-spec-6a"}
}, {
  "id": "zz-fixture-convoy-6f", "title": "Fixture Convoy Six (file draft)", "status": "closed", "issue_type": "convoy",
  "metadata": {"gc.artifact_id": "ticket-graph-draft-zz-fixture-6", "gc.spec_id": "spec-zz-fixture-6"}
}, {
  "id": "zz-fixture-convoy-6m", "title": "Fixture Convoy Six Marked", "status": "closed", "issue_type": "convoy",
  "close_reason": "convoy autoclose: all children closed",
  "metadata": {"gc.flow.mark": "new-flow/v1",
               "gc.artifact_id": "zz-fixture-draft-6m", "gc.spec_id": "zz-fixture-spec-6m"}
}]' > "$CONVOYS_FILE"
: > "$CLOSE_LOG"
: > "$SHOW_LOG"

rc=0
out=$(run_tool) || rc=$?
[ "$rc" -eq 0 ] || { echo "$out" >&2; fail "a run over several closed convoys failed"; }
[ "$(wc -l < "$SHOW_LOG")" -eq 1 ] || { cat "$SHOW_LOG" >&2; fail "expected one bd show for the whole run, not one per artifact/spec id"; }
grep -q "zz-fixture-draft-6a" "$SHOW_LOG" && grep -q "ticket-graph-draft-zz-fixture-6" "$SHOW_LOG" \
  || { cat "$SHOW_LOG" >&2; fail "the one bd show does not carry the ids of every closed convoy"; }
grep -q "6m" "$SHOW_LOG" && { cat "$SHOW_LOG" >&2; fail "the ids of a marked convoy closed outside its commands were looked up"; }
grep -q "closed=2 skipped=2 failed=0" <<<"$out" || { echo "$out" >&2; fail "expected the open Draft and the shared Spec to close once, the closed Draft and the second sight of the Spec to be skipped"; }
[ "$(close_count zz-fixture-spec-6a)" = "1" ] || fail "a Spec two closed convoys share was not closed exactly once"
[ "$(close_count zz-fixture-draft-6a)" = "1" ] || fail "expected exactly one close call for the open Draft"
[ "$(close_count zz-fixture-draft-6b)" = "0" ] || fail "re-closed an already-closed Draft"
[ "$(grep -c "does not resolve to a bead" <<<"$out")" = "2" ] || { echo "$out" >&2; fail "the file-draft ids were not left untouched beside the resolved ones"; }
[ "$(bead_status zz-fixture-spec-6m)" = "open" ] || fail "the Spec of a marked convoy closed outside acceptance or abandon was closed"

# =============================================================================
# 7. A loaded host slows every tracker call (af-p1d8ka): a run cut by the
#    tool's own budget, below the order's timeout, is deferred (exit 0)
#    and closes nothing half-way; only runs cut three times in a row fail,
#    and a run that finishes clears the count.
# =============================================================================

DEFERRED_FILE="$TMP/.gc/runtime/planning-artifacts-close-deferred-passes"
cut_run() {
  PLANNING_ARTIFACTS_CLOSE_BUDGET_SECONDS=0.3 GC_TEST_LIST_SLEEP=5 "$TOOL" 2>&1
}
jq -n '{
  "zz-fixture-spec-7": {"id": "zz-fixture-spec-7", "status": "open"},
  "zz-fixture-draft-7": {"id": "zz-fixture-draft-7", "status": "open"}
}' > "$SHOW_FILE"
jq -n '[{
  "id": "zz-fixture-convoy-7", "title": "Fixture Convoy Seven", "status": "closed", "issue_type": "convoy",
  "metadata": {"gc.artifact_id": "zz-fixture-draft-7", "gc.spec_id": "zz-fixture-spec-7"}
}]' > "$CONVOYS_FILE"
: > "$CLOSE_LOG"

started_ns=$(date +%s%N)
rc=0
out=$(cut_run) || rc=$?
elapsed_ns=$(( $(date +%s%N) - started_ns ))
[ "$rc" -eq 0 ] || { echo "$out" >&2; fail "one run cut by the budget must be deferred, not failed (was $rc)"; }
grep -q 'internal budget exceeded after 0.3s — run deferred (1 of 3 in a row' <<<"$out" \
  || { echo "$out" >&2; fail "a deferred run must name its own deadline and its count"; }
[ "$elapsed_ns" -lt 4000000000 ] || fail "a slow tracker call must be cut at the tool's budget"
[ -s "$CLOSE_LOG" ] && fail "a run cut by the budget closed something"
rc=0
cut_run >/dev/null || rc=$?
[ "$rc" -eq 0 ] || fail "a second run cut in a row must still be deferred (was $rc)"
rc=0
out=$(cut_run) || rc=$?
[ "$rc" -eq 2 ] || { echo "$out" >&2; fail "a third run cut in a row must exit 2 (was $rc)"; }
grep -q 'internal budget exceeded after 0.3s — 3 runs in a row cut short' <<<"$out" \
  || { echo "$out" >&2; fail "a repeated budget expiry must say it is repeated"; }

out=$(run_tool)
grep -q "closed=2 skipped=0 failed=0" <<<"$out" || { echo "$out" >&2; fail "the run after the deferred ones did not close what they left"; }
[ ! -e "$DEFERRED_FILE" ] || fail "a run that finishes must clear the count of runs cut in a row"

# =============================================================================
# 8. Most runs follow no convoy close (af-ktxsfi, when the order ran on
#    every bead close): after a pass that finished, a run that finds no convoy
#    closed since it asks the tracker once and stops -- no list of every
#    closed convoy, no state command, no bd show. A convoy closed since, or
#    a record older than the full-pass period, makes the whole pass again;
#    a pass that fails keeps the record it found.
# =============================================================================

LAST_PASS_FILE="$TMP/.gc/runtime/planning-artifacts-close-last-pass"
rm -f "$LAST_PASS_FILE"
jq -n '{
  "zz-fixture-spec-8": {"id": "zz-fixture-spec-8", "status": "open"},
  "zz-fixture-draft-8": {"id": "zz-fixture-draft-8", "status": "open"}
}' > "$SHOW_FILE"
jq -n '[{
  "id": "zz-fixture-convoy-8old", "title": "Fixture Convoy Eight Old", "status": "closed", "issue_type": "convoy",
  "closed_at": "2000-01-01T00:00:00Z",
  "metadata": {"gc.artifact_id": "zz-fixture-draft-8old", "gc.spec_id": "zz-fixture-spec-8old"}
}]' > "$CONVOYS_FILE"
out=$(run_tool)
grep -q "closed=0 skipped=0 failed=0" <<<"$out" || { echo "$out" >&2; fail "the first run, with no record, must make the whole pass"; }
[ -s "$LAST_PASS_FILE" ] || fail "a pass that finished did not record when it began"

# Nothing closed since: one tracker call, and the state command is never
# asked (a broken one would fail the run).
jq -n '[{
  "id": "zz-fixture-convoy-8", "title": "Fixture Convoy Eight", "status": "closed", "issue_type": "convoy",
  "closed_at": "2000-01-01T00:00:01Z",
  "metadata": {"gc.artifact_id": "zz-fixture-draft-8", "gc.spec_id": "zz-fixture-spec-8"}
}]' > "$CONVOYS_FILE"
: > "$LIST_LOG"; : > "$SHOW_LOG"; : > "$CLOSE_LOG"
rc=0
out=$(CONVOY_STATE_BIN="$TMP/bin/broken-convoy-state" run_tool) || rc=$?
[ "$rc" -eq 0 ] || { echo "$out" >&2; fail "a run with no convoy closed since the last pass must pass (was $rc)"; }
grep -q "no convoy closed since .* -- nothing to do" <<<"$out" || { echo "$out" >&2; fail "a run with no convoy closed since must say so"; }
[ "$(wc -l < "$LIST_LOG")" -eq 1 ] || { cat "$LIST_LOG" >&2; fail "expected one tracker call when no convoy closed since the last pass"; }
grep -q -- "--closed-after $(cat "$LAST_PASS_FILE") --limit 1" "$LIST_LOG" || { cat "$LIST_LOG" >&2; fail "the one call must ask for one convoy closed since the recorded pass"; }
[ -s "$SHOW_LOG" ] && fail "a bd show ran although no convoy closed since the last pass"
[ "$(bead_status zz-fixture-spec-8)" = "open" ] || fail "a Spec was closed although no convoy closed since the last pass"

# A convoy closed since the recorded pass: a failing pass keeps the record,
# the next one closes the Spec and the Draft.
recorded=$(cat "$LAST_PASS_FILE")
jq -n --arg now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '[{
  "id": "zz-fixture-convoy-8", "title": "Fixture Convoy Eight", "status": "closed", "issue_type": "convoy",
  "closed_at": $now,
  "metadata": {"gc.artifact_id": "zz-fixture-draft-8", "gc.spec_id": "zz-fixture-spec-8"}
}]' > "$CONVOYS_FILE"
rc=0
out=$(CONVOY_STATE_BIN="$TMP/bin/broken-convoy-state" run_tool) || rc=$?
[ "$rc" -ne 0 ] || { echo "$out" >&2; fail "a convoy closed since the last pass did not make the whole pass"; }
[ "$(cat "$LAST_PASS_FILE")" = "$recorded" ] || fail "a pass that failed moved the record"
out=$(run_tool)
grep -q "closed=2 skipped=0 failed=0" <<<"$out" || { echo "$out" >&2; fail "a convoy closed since the last pass did not close its Spec and Draft"; }

# A record older than the full-pass period: the whole pass again, though
# nothing closed since.
jq -n '{"zz-fixture-spec-8": {"id": "zz-fixture-spec-8", "status": "open"}}' > "$SHOW_FILE"
jq -n '[{
  "id": "zz-fixture-convoy-8", "title": "Fixture Convoy Eight", "status": "closed", "issue_type": "convoy",
  "closed_at": "2000-01-01T00:00:01Z",
  "metadata": {"gc.spec_id": "zz-fixture-spec-8"}
}]' > "$CONVOYS_FILE"
out=$(PLANNING_ARTIFACTS_CLOSE_FULL_PASS_SECONDS=0 run_tool)
grep -q "closed=1 skipped=0 failed=0" <<<"$out" || { echo "$out" >&2; fail "a record older than the full-pass period did not make the whole pass"; }

# =============================================================================
# 9. The whole pass lasts 25 to 50 s at loadavg 5 to 13 (af-c8m2gh): under
#    a 30 s budget it never finished, so its record never moved and every
#    run made it again, cut each time. The budget leaves the measured pass
#    twice its room, the order's timeout holds order-pause's 20 s read, the
#    budget and its 3 s kill, and the order no longer fires on every bead
#    close.
# =============================================================================

ORDER="$REPO_ROOT/orders/planning-artifacts-close.toml"
budget=$(sed -n 's/^BUDGET_SECONDS="${PLANNING_ARTIFACTS_CLOSE_BUDGET_SECONDS:-\([0-9][0-9]*\)}"$/\1/p' "$TOOL")
order_timeout=$(sed -n 's/^timeout = "\([0-9][0-9]*\)s"$/\1/p' "$ORDER")
[ -n "$budget" ] && [ -n "$order_timeout" ] || fail "could not read the tool's budget ($budget) or the order's timeout in seconds ($order_timeout)"
[ "$budget" -ge 100 ] || fail "a budget of ${budget}s leaves the whole pass (50 s measured at loadavg 5) less than twice its room"
[ $(( 20 + budget + 3 )) -le "$order_timeout" ] \
  || fail "the order's ${order_timeout}s timeout does not hold order-pause's 20 s, the ${budget}s budget and its 3 s kill"
grep -qx 'trigger = "cooldown"' "$ORDER" || fail "the order must be a cooldown, not fired on every bead close"
grep -q '^on = ' "$ORDER" && fail "the order still names an event"

echo "PASS: planning-artifacts-close (open convoy untouched, bead-mode closes idempotently, claimed Spec closes, file-draft mode untouched without error, marked convoy closed outside its commands keeps its Spec and Draft, unreadable state closes nothing, one bd show per run, a run slowed past its budget deferred until cut three times in a row, a run with no convoy closed since the last pass stops after one tracker call, budget and order timeout hold the whole pass)"
