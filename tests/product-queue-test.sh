#!/usr/bin/env bash

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
QUEUE="$ROOT/bin/product-queue"
FIXTURES="$ROOT/tests/fixtures/product-queue"
TEST_TMP=$(mktemp -d)
trap 'rm -rf -- "$TEST_TMP"' EXIT
export PRODUCT_QUEUE_PRODUCT=saymyname
export PRODUCT_QUEUE_DEFAULT_GOAL=af-u8id
export BD_BIN="$FIXTURES/bd"
export GC_BIN="$FIXTURES/gc"
export QUEUE_LOG="$TEST_TMP/calls.log"
export QUEUE_INVENTORY='[
  {"id":"af-b","title":"Beta","status":"deferred","priority":1,"acceptance_criteria":"Beta done","metadata":{"gc.queue_product":"saymyname","gc.queue_state":"paused","gc.queue_rank":2000,"gc.queue_urgency":"urgent","gc.queue_goal":"af-u8id"}},
  {"id":"af-c","title":"Gamma","status":"deferred","priority":0,"acceptance_criteria":"Gamma done","metadata":{"gc.queue_product":"saymyname","gc.queue_state":"queued","gc.queue_rank":3000,"gc.queue_urgency":"critical","gc.queue_goal":"af-u8id"}},
  {"id":"af-a","title":"Alpha","status":"deferred","priority":2,"acceptance_criteria":"Alpha done","metadata":{"gc.queue_product":"saymyname","gc.queue_state":"queued","gc.queue_rank":1000,"gc.queue_urgency":"normal","gc.queue_goal":"af-u8id"}}
]'

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
assert_contains() { [[ $1 == *"$2"* ]] || fail "missing '$2' in '$1'"; }

output=$("$QUEUE" list)
assert_contains "$output" '1. [queued][normal] Alpha (af-a)'
assert_contains "$output" '2. [paused][urgent] Beta (af-b)'
assert_contains "$output" '3. [queued][critical] Gamma (af-c)'

output=$("$QUEUE" list --json)
assert_contains "$output" '"position":1,"id":"af-a"'

output=$("$QUEUE" next)
[[ $output == 'NEXT: Alpha (af-a) — normal' ]] || fail "wrong next candidate: $output"

: >"$QUEUE_LOG"
"$QUEUE" move af-c 1 >/dev/null
grep -Fq 'update <af-c> <--set-metadata> <gc.queue_rank=1000>' "$QUEUE_LOG"
grep -Fq 'update <af-a> <--set-metadata> <gc.queue_rank=2000>' "$QUEUE_LOG"
grep -Fq 'update <af-b> <--set-metadata> <gc.queue_rank=3000>' "$QUEUE_LOG"

: >"$QUEUE_LOG"
"$QUEUE" urgency af-a urgent >/dev/null
grep -Fq 'update <af-a> <--priority> <1> <--set-metadata> <gc.queue_urgency=urgent>' "$QUEUE_LOG"
"$QUEUE" pause af-a 'Waiting for product decision' >/dev/null
grep -Fq 'gc.queue_state=paused' "$QUEUE_LOG"
"$QUEUE" resume af-b >/dev/null
grep -Fq 'gc.queue_state=queued' "$QUEUE_LOG"

: >"$QUEUE_LOG"
output=$("$QUEUE" add --title Delta --goal af-u8id --urgency normal \
  --why 'Useful outcome' --acceptance 'Visible result')
assert_contains "$output" 'ADDED: af-new — position 4 (normal)'
grep -Fq 'create <Delta>' "$QUEUE_LOG"
grep -Fq '<--defer> <2125-01-01>' "$QUEUE_LOG"
grep -Fq 'update <af-new> <--status> <deferred>' "$QUEUE_LOG"

if "$QUEUE" materialize af-a smf-exec >/dev/null 2>&1; then
  fail 'materialize without Mayor authority should fail'
fi
if "$QUEUE" materialize af-c smf-exec --mayor >/dev/null 2>&1; then
  fail 'materializing a non-first candidate should fail'
fi
: >"$QUEUE_LOG"
"$QUEUE" materialize af-a smf-exec --mayor >/dev/null
grep -Fq 'gc.queue_state=materialized' "$QUEUE_LOG"
grep -Fq 'gc.materialized_bead=smf-exec' "$QUEUE_LOG"
grep -Fq 'close <af-a>' "$QUEUE_LOG"

: >"$QUEUE_LOG"
"$QUEUE" cancel af-c 'No longer useful' >/dev/null
grep -Fq 'gc.queue_state=cancelled' "$QUEUE_LOG"
grep -Fq 'close <af-c>' "$QUEUE_LOG"

printf 'PASS: product queue ordering and authority contract\n'
