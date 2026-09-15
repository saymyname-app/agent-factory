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
assert_not_contains() { [[ $1 != *"$2"* ]] || fail "unexpected '$2' in '$1'"; }

output=$("$QUEUE" list)
assert_contains "$output" '1. [Éligible · non programmé][urgence Normale] Alpha (af-a)'
assert_contains "$output" '2. [En pause][urgence Urgente] Beta (af-b) — Raison de pause non renseignée'
assert_contains "$output" '3. [Éligible · non programmé][urgence Critique] Gamma (af-c)'
assert_contains "$output" 'techniquement différés dans Beads'

output=$("$QUEUE" list --json)
assert_contains "$output" '"position":1,"id":"af-a"'
assert_contains "$output" '"state":"eligible","state_label":"Éligible · non programmé"'
assert_contains "$output" '"technical_status":"deferred"'
assert_contains "$output" '"contract":"agent-factory-human-state/v1"'

output=$("$QUEUE" next)
[[ $output == 'NEXT: Alpha (af-a) — Éligible · non programmé; lancement non automatique' ]] || fail "wrong next candidate: $output"

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
grep -Fq 'gc.queue_pause_reason=Waiting for product decision' "$QUEUE_LOG"
if "$QUEUE" pause af-a >/dev/null 2>&1; then
  fail 'pause without a reason must fail closed'
fi
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

# Factory campaigns have a separate lane: their first eligible candidate may be
# materialized without bypassing or reordering the first eligible product.
export QUEUE_INVENTORY='[
  {"id":"af-product-first","title":"First product","status":"deferred","metadata":{"gc.queue_product":"saymyname","gc.queue_state":"queued","gc.queue_rank":1000,"gc.queue_urgency":"normal","gc.queue_goal":"af-u8id"}},
  {"id":"af-campaign-first","title":"Campaign","status":"deferred","metadata":{"gc.queue_product":"saymyname","gc.queue_state":"queued","gc.queue_rank":2000,"gc.queue_urgency":"normal","gc.queue_goal":"none"}},
  {"id":"af-product-second","title":"Second product","status":"deferred","metadata":{"gc.queue_product":"saymyname","gc.queue_state":"queued","gc.queue_rank":3000,"gc.queue_urgency":"normal","gc.queue_goal":"af-u8id"}},
  {"id":"af-campaign-second","title":"Later campaign","status":"deferred","metadata":{"gc.queue_product":"saymyname","gc.queue_state":"queued","gc.queue_rank":4000,"gc.queue_urgency":"normal","gc.queue_goal":"none"}}
]'
[[ $("$QUEUE" next) == 'NEXT: First product (af-product-first) — Éligible · non programmé; lancement non automatique' ]] \
  || fail 'a Factory campaign must never replace product NEXT'
if "$QUEUE" materialize af-product-second smf-exec --mayor >/dev/null 2>&1; then
  fail 'the product lane must remain strictly first-eligible'
fi
if "$QUEUE" materialize af-campaign-second smf-exec --mayor >/dev/null 2>&1; then
  fail 'the Factory campaign lane must remain strictly first-eligible'
fi
: >"$QUEUE_LOG"
"$QUEUE" materialize af-campaign-first smf-exec --mayor >/dev/null
grep -Fq 'gc.queue_state=materialized' "$QUEUE_LOG"
grep -Fq 'close <af-campaign-first>' "$QUEUE_LOG"

: >"$QUEUE_LOG"
"$QUEUE" cancel af-product-second 'No longer useful' >/dev/null
grep -Fq 'gc.queue_state=cancelled' "$QUEUE_LOG"
grep -Fq 'close <af-product-second>' "$QUEUE_LOG"

export QUEUE_INVENTORY='[
  {"id":"af-live","title":"Live","status":"deferred","metadata":{"gc.queue_product":"saymyname","gc.queue_state":"queued","gc.queue_rank":1000,"gc.queue_urgency":"normal","gc.queue_goal":"af-u8id"}},
  {"id":"af-old","title":"Already delivered candidate","status":"closed","metadata":{"gc.queue_product":"saymyname","gc.queue_state":"materialized","gc.queue_rank":2000,"gc.queue_urgency":"normal","gc.queue_goal":"af-u8id","gc.materialized_bead":"af-exec.1"}},
  {"id":"af-cancel","title":"Cancelled","status":"closed","metadata":{"gc.queue_product":"saymyname","gc.queue_state":"cancelled","gc.queue_rank":3000,"gc.queue_urgency":"normal","gc.queue_goal":"af-u8id"}}
]'
output=$("$QUEUE" list --json)
assert_contains "$output" '"id":"af-live"'
assert_not_contains "$output" 'af-old'
assert_not_contains "$output" 'af-cancel'

export QUEUE_INVENTORY='[
  {"id":"af-bad","title":"Bad tuple","status":"closed","metadata":{"gc.queue_product":"saymyname","gc.queue_state":"queued","gc.queue_rank":1000,"gc.queue_urgency":"normal","gc.queue_goal":"af-u8id"}}
]'
if "$QUEUE" list --json >/dev/null 2>&1; then
  fail 'an inconsistent status/state tuple must fail closed'
fi
for invalid_metadata in \
  '"gc.queue_state":"materialized","gc.materialized_bead":"af-exec"' \
  '"gc.queue_state":"cancelled"' \
  '"gc.queue_state":"unknown"' \
  '"gc.some_other_field":"missing-state"'
do
  export QUEUE_INVENTORY="[{
    \"id\":\"af-bad\",\"title\":\"Bad tuple\",\"status\":\"deferred\",
    \"metadata\":{\"gc.queue_product\":\"saymyname\",$invalid_metadata,
      \"gc.queue_rank\":1000,\"gc.queue_urgency\":\"normal\",\"gc.queue_goal\":\"af-u8id\"}
  }]"
  if "$QUEUE" list --json >/dev/null 2>&1; then
    fail "invalid deferred tuple must fail closed: $invalid_metadata"
  fi
done

printf 'PASS: product queue ordering, lifecycle, and authority contract\n'
