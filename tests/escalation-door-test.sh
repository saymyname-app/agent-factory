#!/usr/bin/env bash
#
# O06: escalation-door is the one door for every escalation (replaces
# bin/campaign-pointer escalate). Proves the routing rules -- straight to
# Benjamin lands on the list at once, Mayor-first only escalates after 2h
# unresolved (fake clock) -- every escalation fails loudly (no
# `>/dev/null || true`), and the read-only CLI reports the list and the
# pending-proposal count.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SCRIPT="$ROOT/bin/escalation-door"
FIXTURE="$ROOT/tests/fixtures/escalation-door/gc"
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

bead() { jq -c '.' "$TEST_TMP/beads/$1.json"; }

door() {
  GC_BIN="$FIXTURE" ED_BEAD_DIR="$TEST_TMP/beads" ED_CALL_LOG="$TEST_TMP/calls.log" \
    ESCALATION_DOOR_LOCK_FILE="$TEST_TMP/lock" "$SCRIPT" "$@"
}

# --- benjamin (straight to Benjamin) ----------------------------------------
reset_beads
seed af-blocker '{"id":"af-blocker","status":"open","metadata":{},"notes":"","labels":[]}'
TESTS_RUN=$((TESTS_RUN + 1))
door benjamin af-blocker "Irreversible production change" >/dev/null \
  || fail "benjamin should succeed"
[[ $(jq -r '.metadata["gc.needs_benjamin"]' "$TEST_TMP/beads/af-blocker.json") == "Irreversible production change" ]] \
  || fail "benjamin did not set gc.needs_benjamin on the target bead"
[[ $(jq -r '.notes' "$TEST_TMP/beads/af-blocker.json") == *"Irreversible production change"* ]] \
  || fail "benjamin did not append the cause to the bead's notes"
grep -Fq 'mail send human' "$TEST_TMP/calls.log" || fail "benjamin did not mail the escalation recipient"

TESTS_RUN=$((TESTS_RUN + 1))
if door benjamin af-blocker $'two\nlines' >/dev/null 2>&1; then
  fail "benjamin with a multi-line reason must refuse"
fi

TESTS_RUN=$((TESTS_RUN + 1))
: >"$TEST_TMP/calls.log"
if ED_MAIL_FAIL=human GC_BIN="$FIXTURE" ED_BEAD_DIR="$TEST_TMP/beads" ED_CALL_LOG="$TEST_TMP/calls.log" \
    ESCALATION_DOOR_LOCK_FILE="$TEST_TMP/lock" "$SCRIPT" benjamin af-blocker "Cause" >/dev/null 2>&1; then
  fail "benjamin must refuse (non-zero, visible) when the mail cannot be sent"
fi

# --- list (read-only CLI) ---------------------------------------------------
TESTS_RUN=$((TESTS_RUN + 1))
seed af-blocker '{"id":"af-blocker","status":"open","metadata":{"gc.needs_benjamin":"Irreversible production change"},"notes":"","labels":[]}'
seed af-proposal-1 '{"id":"af-proposal-1","status":"open","metadata":{},"notes":"","labels":["proposal"]}'
seed af-proposal-2 '{"id":"af-proposal-2","status":"open","metadata":{},"notes":"","labels":["proposal"]}'
out=$(door list) || fail "list should succeed"
grep -Fq "af-blocker — Irreversible production change" <<<"$out" \
  || { echo "$out" >&2; fail "list did not print the escalated bead and its reason"; }
grep -Fq "Pending proposals: 2" <<<"$out" \
  || { echo "$out" >&2; fail "list did not print the pending-proposal count"; }

TESTS_RUN=$((TESTS_RUN + 1))
reset_beads
out=$(door list) || fail "list on an empty city should succeed"
grep -Fq "(none)" <<<"$out" || { echo "$out" >&2; fail "list did not report an empty NEEDS BENJAMIN list"; }
grep -Fq "Pending proposals: 0" <<<"$out" || { echo "$out" >&2; fail "list did not report zero pending proposals"; }

# --- mayor-first, then sweep after 2h (fake clock) --------------------------
reset_beads
seed af-order '{"id":"af-order","status":"open","metadata":{},"notes":"","labels":[]}'
T0=1790000000
TESTS_RUN=$((TESTS_RUN + 1))
ESCALATION_DOOR_NOW=$T0 door mayor af-order "on-order-failed: dolt-remotes-patrol failing repeatedly" >/dev/null \
  || fail "mayor-first escalation should succeed"
[[ $(jq -r '.metadata["gc.escalation_mayor_paged_at"]' "$TEST_TMP/beads/af-order.json") != "" ]] \
  || fail "mayor-first did not stamp gc.escalation_mayor_paged_at"
grep -Fq 'mail send mayor' "$TEST_TMP/calls.log" || fail "mayor-first did not mail mayor"
[[ $(jq -r '.metadata["gc.needs_benjamin"] // "none"' "$TEST_TMP/beads/af-order.json") == none ]] \
  || fail "mayor-first must not touch gc.needs_benjamin"

# Before 2h: sweep must not escalate to Benjamin.
TESTS_RUN=$((TESTS_RUN + 1))
: >"$TEST_TMP/calls.log"
ESCALATION_DOOR_NOW=$((T0 + 3600)) door sweep >/dev/null || fail "sweep should succeed"
[[ $(jq -r '.metadata["gc.needs_benjamin"] // "none"' "$TEST_TMP/beads/af-order.json") == none ]] \
  || fail "sweep escalated to Benjamin before the 2h grace period elapsed"
grep -Fq 'mail send human' "$TEST_TMP/calls.log" && fail "sweep mailed Benjamin before 2h"

# At/after 2h: sweep must escalate to Benjamin.
TESTS_RUN=$((TESTS_RUN + 1))
: >"$TEST_TMP/calls.log"
ESCALATION_DOOR_NOW=$((T0 + 7200)) door sweep >/dev/null || fail "sweep should succeed at the 2h boundary"
[[ $(jq -r '.metadata["gc.needs_benjamin"]' "$TEST_TMP/beads/af-order.json") == *"unresolved after 2h"* ]] \
  || fail "sweep did not promote the unresolved Mayor-first escalation to Benjamin"
grep -Fq 'mail send human' "$TEST_TMP/calls.log" || fail "sweep did not mail Benjamin once promoted"

# A second sweep must not re-page: the bead now carries gc.needs_benjamin.
TESTS_RUN=$((TESTS_RUN + 1))
: >"$TEST_TMP/calls.log"
ESCALATION_DOOR_NOW=$((T0 + 10800)) door sweep >/dev/null || fail "a later sweep should still succeed"
grep -Fq 'mail send human' "$TEST_TMP/calls.log" && fail "sweep re-escalated an already-escalated bead"

# A Mayor-first escalation resolved before 2h (cleared) must never reach Benjamin.
reset_beads
seed af-pr '{"id":"af-pr","status":"open","metadata":{},"notes":"","labels":[]}'
TESTS_RUN=$((TESTS_RUN + 1))
ESCALATION_DOOR_NOW=$T0 door mayor af-pr "stuck PR" >/dev/null || fail "mayor-first should succeed"
door clear af-pr >/dev/null || fail "clear should succeed"
: >"$TEST_TMP/calls.log"
ESCALATION_DOOR_NOW=$((T0 + 7200)) door sweep >/dev/null || fail "sweep should succeed"
[[ $(jq -r '.metadata["gc.needs_benjamin"] // "none"' "$TEST_TMP/beads/af-pr.json") == none ]] \
  || fail "a resolved Mayor-first escalation must not be swept to Benjamin"
grep -Fq 'mail send human' "$TEST_TMP/calls.log" && fail "sweep mailed Benjamin for a resolved escalation"

# --- clear -------------------------------------------------------------------
reset_beads
seed af-blocker '{"id":"af-blocker","status":"open","metadata":{"gc.needs_benjamin":"Cause"},"notes":"","labels":[]}'
TESTS_RUN=$((TESTS_RUN + 1))
door clear af-blocker >/dev/null || fail "clear should succeed"
[[ $(jq -r '.metadata["gc.needs_benjamin"]' "$TEST_TMP/beads/af-blocker.json") == none ]] \
  || fail "clear did not clear gc.needs_benjamin"
[[ $(jq -r '.notes' "$TEST_TMP/beads/af-blocker.json") == *"DECISION CLEARED"* ]] \
  || fail "clear did not trace the clearance in the bead's notes"

TESTS_RUN=$((TESTS_RUN + 1))
if door clear af-does-not-exist >/dev/null 2>&1; then
  fail "clear on an unknown bead must refuse"
fi
TESTS_RUN=$((TESTS_RUN + 1))
if door clear 'not an id' >/dev/null 2>&1; then
  fail "clear with a malformed id must refuse"
fi

# --- the escalation mail names the exact command that clears it ------------
reset_beads
seed af-blocker '{"id":"af-blocker","status":"open","metadata":{},"notes":"","labels":[]}'
TESTS_RUN=$((TESTS_RUN + 1))
: >"$TEST_TMP/calls.log"
door benjamin af-blocker "Cause" >/dev/null || fail "benjamin should succeed"
grep -Fq 'clear af-blocker' "$TEST_TMP/calls.log" \
  || fail "the escalation mail must name escalation-door clear <bead>"

# --- malformed / unknown bead ids are refused for every write command ------
TESTS_RUN=$((TESTS_RUN + 1))
if door benjamin 'prose, not an id' "Cause" >/dev/null 2>&1; then
  fail "benjamin must refuse prose in place of a bead id"
fi
TESTS_RUN=$((TESTS_RUN + 1))
if door benjamin af-does-not-exist "Cause" >/dev/null 2>&1; then
  fail "benjamin on an unknown bead must refuse"
fi

printf 'PASS: %d deterministic escalation-door checks\n' "$TESTS_RUN"
