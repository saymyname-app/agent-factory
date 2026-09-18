#!/usr/bin/env bash
#
# ADR-0023: campaign-pointer is the one door for the coordination-root
# pointers (gc.current, gc.current_jit, gc.last_delivered, gc.needs_benjamin).
# Proves start/finish/escalate/clear-decision validate before writing, write
# every field of the transition together, and refuse anything else with a
# one-line reason -- and replays the four 2026-09-18 incidents that motivated
# ADR-0023 to prove each leaves the campaign in a coherent state.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SCRIPT="$ROOT/bin/campaign-pointer"
FIXTURE="$ROOT/tests/fixtures/campaign-pointer/gc"
TEST_TMP=$(mktemp -d)
trap 'rm -rf -- "$TEST_TMP"' EXIT
TESTS_RUN=0

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

reset_beads() {
  rm -rf "$TEST_TMP/beads" "$TEST_TMP/calls.log"
  mkdir -p "$TEST_TMP/beads"
  : >"$TEST_TMP/calls.log"
}

seed() {  # id json
  printf '%s' "$2" >"$TEST_TMP/beads/$1.json"
}

coordination() {
  jq -c '.' "$TEST_TMP/beads/af-1vr4.json"
}

run() {
  GC_BIN="$FIXTURE" CP_BEAD_DIR="$TEST_TMP/beads" CP_CALL_LOG="$TEST_TMP/calls.log" \
    CAMPAIGN_LOCK_FILE="$TEST_TMP/lock" "$SCRIPT" "$@"
}

# --- start ---------------------------------------------------------------
reset_beads
seed af-1vr4 '{"id":"af-1vr4","status":"in_progress","metadata":{"gc.current":"none","gc.current_jit":"none"}}'
seed af-candidate '{"id":"af-candidate","status":"open","metadata":{}}'
TESTS_RUN=$((TESTS_RUN + 1))
run start af-candidate >/dev/null || fail "start on an open bead should succeed"
[[ $(jq -r '.metadata["gc.current"]' <<<"$(coordination)")  == af-candidate ]] || fail "start did not set gc.current"
[[ $(jq -r '.metadata["gc.current_jit"]' <<<"$(coordination)") == af-candidate ]] || fail "start did not set gc.current_jit"

TESTS_RUN=$((TESTS_RUN + 1))
seed af-closed '{"id":"af-closed","status":"closed","metadata":{}}'
if run start af-closed >/dev/null 2>&1; then fail "start on a closed bead must refuse"; fi

TESTS_RUN=$((TESTS_RUN + 1))
if run start 'not an id' >/dev/null 2>&1; then fail "start with a malformed id must refuse"; fi

TESTS_RUN=$((TESTS_RUN + 1))
if run start af-does-not-exist >/dev/null 2>&1; then fail "start on an unknown bead must refuse"; fi

# --- finish ----------------------------------------------------------------
reset_beads
seed af-1vr4 '{"id":"af-1vr4","status":"in_progress","metadata":{"gc.current":"af-delivered","gc.current_jit":"af-delivered"}}'
seed af-delivered '{"id":"af-delivered","status":"closed","metadata":{
  "gc.delivery_status":"merged","gc.work_outcome":"shipped","gc.github_repo":"owner/repo",
  "gc.pr_number":"42","gc.pr_head":"aaaa","gc.merge_commit":"bbbb"}}'
TESTS_RUN=$((TESTS_RUN + 1))
run finish af-delivered >/dev/null || fail "finish with full delivery proof should succeed"
[[ $(jq -r '.metadata["gc.last_delivered"]' <<<"$(coordination)") == af-delivered ]] \
  || fail "finish did not set gc.last_delivered"
[[ $(jq -r '.metadata["gc.current"]' <<<"$(coordination)") == none ]] \
  || fail "finish did not clear gc.current"
[[ $(jq -r '.metadata["gc.current_jit"]' <<<"$(coordination)") == none ]] \
  || fail "finish did not clear gc.current_jit"

# af-16-style incident: a delivery bead closed without its six proof fields.
TESTS_RUN=$((TESTS_RUN + 1))
seed af-incomplete '{"id":"af-incomplete","status":"closed","metadata":{}}'
if output=$(run finish af-incomplete 2>&1); then fail "finish without delivery proof must refuse"; fi
[[ $output == *"missing delivery proof"* ]] || fail "finish did not name the missing proof: $output"

# --- escalate --------------------------------------------------------------
# escalate targets whatever bead needs the decision (an ordinary work Bead,
# or the coordination Bead itself for a campaign-wide block) -- the same bead
# carries both gc.needs_benjamin and the notes (agents/mayor/prompt.template.md
# "the one escalation contract").
reset_beads
seed af-1vr4 '{"id":"af-1vr4","status":"in_progress","metadata":{"gc.needs_benjamin":"none"}}'
seed af-blocker '{"id":"af-blocker","status":"open","metadata":{"gc.needs_benjamin":"none"},"notes":""}'
TESTS_RUN=$((TESTS_RUN + 1))
run escalate af-blocker "Irreversible production change" >/dev/null \
  || fail "escalate should succeed"
[[ $(jq -r '.metadata["gc.needs_benjamin"]' "$TEST_TMP/beads/af-blocker.json") == "Irreversible production change" ]] \
  || fail "escalate did not set gc.needs_benjamin on the target bead"
[[ $(jq -r '.notes' "$TEST_TMP/beads/af-blocker.json") == *"Irreversible production change"* ]] \
  || fail "escalate did not append the cause to the bead's notes"
[[ $(jq -r '.metadata["gc.needs_benjamin"]' <<<"$(coordination)") == none ]] \
  || fail "escalate on an ordinary bead must not touch the coordination bead"
grep -Fq 'mail send human' "$TEST_TMP/calls.log" || fail "escalate did not mail human"

# Escalating the coordination bead itself (factory-guard's durable-failure
# path) sets gc.needs_benjamin where mayor-campaign's activate/block/resume
# gates read it.
TESTS_RUN=$((TESTS_RUN + 1))
run escalate af-1vr4 "Défaillance durable de la campagne" >/dev/null \
  || fail "escalate on the coordination bead should succeed"
[[ $(jq -r '.metadata["gc.needs_benjamin"]' <<<"$(coordination)") == "Défaillance durable de la campagne" ]] \
  || fail "escalate on the coordination bead did not set its gc.needs_benjamin"

TESTS_RUN=$((TESTS_RUN + 1))
if run escalate af-blocker $'two\nlines' >/dev/null 2>&1; then
  fail "escalate with a multi-line reason must refuse"
fi

TESTS_RUN=$((TESTS_RUN + 1))
: >"$TEST_TMP/calls.log"
if CP_MAIL_FAIL=1 run escalate af-blocker "Cause" >/dev/null 2>&1; then
  fail "escalate must refuse when the mail cannot be sent"
fi

# --- clear-decision ----------------------------------------------------------
reset_beads
seed af-1vr4 '{"id":"af-1vr4","status":"in_progress","metadata":{"gc.needs_benjamin":"Cause","gc.blocked_reason":"Cause"}}'
TESTS_RUN=$((TESTS_RUN + 1))
run clear-decision >/dev/null || fail "clear-decision should succeed"
[[ $(jq -r '.metadata["gc.needs_benjamin"]' <<<"$(coordination)") == none ]] \
  || fail "clear-decision did not clear gc.needs_benjamin"
[[ $(jq -r '.metadata["gc.blocked_reason"]' <<<"$(coordination)") == none ]] \
  || fail "clear-decision did not clear gc.blocked_reason"

# --- ADR-0023 incident replay: the campaign stays coherent afterward -------
# 2026-09-18 02:40Z: the Mayor wrote free prose into gc.current by hand. The
# door only ever accepts a validated bead id or "none" -- prose is refused
# outright, so this incident shape cannot recur through the door.
reset_beads
seed af-1vr4 '{"id":"af-1vr4","status":"in_progress","metadata":{"gc.current":"none"}}'
TESTS_RUN=$((TESTS_RUN + 1))
if run start "af-smmwz / smb-99wi — Stop cross-org…" >/dev/null 2>&1; then
  fail "start must refuse prose in place of a bead id"
fi
[[ $(jq -r '.metadata["gc.current"]' <<<"$(coordination)") == none ]] \
  || fail "a refused start must not have touched gc.current"

# 2026-09-16: a delivery bead closed with none of the six proof fields, which
# blocked mayor-campaign/product-status for half a day. finish refuses it
# outright instead of letting gc.last_delivered point at unproven work.
reset_beads
seed af-1vr4 '{"id":"af-1vr4","status":"in_progress","metadata":{"gc.last_delivered":"none"}}'
seed af-7700 '{"id":"af-7700","status":"closed","metadata":{}}'
TESTS_RUN=$((TESTS_RUN + 1))
if run finish af-7700 >/dev/null 2>&1; then fail "finish must refuse a delivery bead missing proof"; fi
[[ $(jq -r '.metadata["gc.last_delivered"]' <<<"$(coordination)") == none ]] \
  || fail "a refused finish must not have touched gc.last_delivered"

printf 'PASS: %d deterministic campaign-pointer checks\n' "$TESTS_RUN"
