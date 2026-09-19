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
# A candidate predating af-3uefc's schema carries no criterion_refs/independence
# metadata at all -- it must still list, just untraceable to any release.
assert_contains "$output" '"criterion_refs":[],"independence":"unknown"'
assert_contains "$output" '"contract":"agent-factory-human-state/v1"'

output=$("$QUEUE" next)
[[ $output == 'NEXT: Alpha (af-a) — Éligible · non programmé; lancement non automatique' ]] || fail "wrong next candidate: $output"

# af-3uefc: a candidate authored with criterion_refs/independence metadata
# projects them through list --json so a caller can build project_campaign_
# work's queue_candidates without a second Beads round-trip.
traceable_inventory=$QUEUE_INVENTORY
export QUEUE_INVENTORY='[
  {"id":"af-traceable","title":"Traceable","status":"deferred","metadata":{"gc.queue_product":"saymyname","gc.queue_state":"queued","gc.queue_rank":1000,"gc.queue_urgency":"normal","gc.queue_goal":"af-u8id","gc.queue_criterion_refs":"release-e2e,personal-return","gc.queue_independence":"proven"}}
]'
output=$("$QUEUE" list --json)
assert_contains "$output" '"criterion_refs":["release-e2e","personal-return"],"independence":"proven"'
export QUEUE_INVENTORY=$traceable_inventory

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
  --why 'Useful outcome' --authorized-by 'ADR-0021 review finding' \
  --acceptance 'When a learner answers wrongly, the quiz shall show the correction.')
assert_contains "$output" 'ADDED: af-new — position 4 (normal)'
grep -Fq 'create <Delta>' "$QUEUE_LOG"
grep -Fq '<--defer> <2125-01-01>' "$QUEUE_LOG"
grep -Fq '"gc.authorized_by":"ADR-0021 review finding"' "$QUEUE_LOG"
grep -Fq 'update <af-new> <--status> <deferred>' "$QUEUE_LOG"
# Legacy add path (no --criterion-ref/--independence): still traces to nothing.
grep -Fq '"gc.queue_criterion_refs":""' "$QUEUE_LOG"
grep -Fq '"gc.queue_independence":"unknown"' "$QUEUE_LOG"

# af-3uefc: --criterion-ref/--independence make a candidate traceable to a
# versioned release's criteria (lib/product_release.py::project_campaign_work)
# before it is ever a work_graph node.
: >"$QUEUE_LOG"
"$QUEUE" add --title Epsilon --authorized-by 'ADR-0021 review finding' \
  --acceptance 'The quiz shall show the correction.' \
  --criterion-ref release-e2e --criterion-ref personal-return --independence proven \
  >/dev/null
grep -Fq '"gc.queue_criterion_refs":"release-e2e,personal-return"' "$QUEUE_LOG"
grep -Fq '"gc.queue_independence":"proven"' "$QUEUE_LOG"

if "$QUEUE" add --title Zeta --authorized-by ADR-0021 \
  --acceptance 'The quiz shall show the correction.' --independence not-a-real-value \
  >/dev/null 2>&1; then
  fail '--independence must reject an unknown value'
fi
if "$QUEUE" add --title Zeta --authorized-by ADR-0021 \
  --acceptance 'The quiz shall show the correction.' --criterion-ref 'Not Valid' \
  >/dev/null 2>&1; then
  fail '--criterion-ref must reject a value outside the release id pattern'
fi

# Provenance and EARS acceptance are required going forward (add only).
ears='The quiz shall show the correction.'
: >"$QUEUE_LOG"
if output=$("$QUEUE" add --title Delta --acceptance "$ears" 2>&1); then
  fail 'add without --authorized-by must fail'
fi
assert_contains "$output" '--authorized-by is required'
if "$QUEUE" add --title Delta --authorized-by $'ADR\n0021' --acceptance "$ears" >/dev/null 2>&1; then
  fail 'a multi-line --authorized-by must fail'
fi
if output=$("$QUEUE" add --title Delta --authorized-by ADR-0021 2>&1); then
  fail 'add without --acceptance must fail'
fi
assert_contains "$output" '--acceptance is required'
for bad in 'Visible result' 'The quiz is nice.' 'It shall work.' 'The Marshall plan works.'; do
  if output=$("$QUEUE" add --title Delta --authorized-by ADR-0021 --acceptance "$bad" 2>&1); then
    fail "non-EARS acceptance must fail: $bad"
  fi
  assert_contains "$output" 'no EARS-shaped line'
  assert_contains "$output" 'When <trigger>, the <system> shall <response>.'
  assert_contains "$output" 'If <condition>, then the <system> shall <response>.'
done
[[ ! -s $QUEUE_LOG ]] || fail 'a rejected add must not touch Beads'
for good in \
  'The quiz shall show the correction.' \
  'when a learner answers, the quiz SHALL show the correction.' \
  'While offline, the app shall queue answers.' \
  'Where photos are enabled, the quiz shall show them.' \
  'If the upload fails, then the app shall keep the draft.' \
  $'Context line first.\n- [Event] When a learner answers, the quiz shall respond.' \
  'Le système doit afficher la correction.' \
  'Quand un apprenant répond, le quiz doit afficher la correction.' \
  'Lorsqu’un apprenant répond, le quiz doit afficher la correction.' \
  'Tant que le réseau est coupé, les réponses doivent rester en file.' \
  'Là où les photos sont activées, le quiz doit les afficher.' \
  'Si l'"'"'envoi échoue, alors l'"'"'application doit garder le brouillon.'
do
  "$QUEUE" add --title Delta --authorized-by ADR-0021 --acceptance "$good" >/dev/null \
    || fail "EARS acceptance must be accepted: $good"
done

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
# Legacy candidate (no gc.authorized_by): only the source back-link is written.
grep -Fxq 'update <smf-exec> <--set-metadata> <gc.source_candidate=af-a>' "$QUEUE_LOG"

# materialize copies provenance onto the execution Bead; a failed back-link
# write only warns and never undoes the materialization.
legacy_inventory=$QUEUE_INVENTORY
export QUEUE_INVENTORY='[
  {"id":"af-p","title":"Provenance","status":"deferred","metadata":{"gc.queue_product":"saymyname","gc.queue_state":"queued","gc.queue_rank":1000,"gc.queue_urgency":"normal","gc.queue_goal":"af-u8id","gc.authorized_by":"ADR-0021"}}
]'
: >"$QUEUE_LOG"
"$QUEUE" materialize af-p smf-exec --mayor >/dev/null
grep -Fxq 'update <smf-exec> <--set-metadata> <gc.source_candidate=af-p> <--set-metadata> <gc.authorized_by=ADR-0021>' "$QUEUE_LOG"
: >"$QUEUE_LOG"
output=$(QUEUE_FAIL_UPDATE_ID=smf-exec "$QUEUE" materialize af-p smf-exec --mayor 2>&1) \
  || fail 'a back-link write failure must not abort materialize'
assert_contains "$output" 'WARNING: Could not write the provenance back-link on smf-exec'
assert_contains "$output" 'MATERIALIZED: af-p -> smf-exec'
grep -Fq 'gc.materialized_bead=smf-exec' "$QUEUE_LOG"
grep -Fq 'close <af-p>' "$QUEUE_LOG"
# Legacy candidates without the new metadata still list.
export QUEUE_INVENTORY=$legacy_inventory
"$QUEUE" list >/dev/null || fail 'legacy candidates without provenance must still list'

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

# A node the campaign sentinel quarantined after a durable failure (ADR-0016 §7)
# must not poison the whole queue read; it is excluded like paused/materialized.
export QUEUE_INVENTORY='[
  {"id":"af-live","title":"Live","status":"deferred","metadata":{"gc.queue_product":"saymyname","gc.queue_state":"queued","gc.queue_rank":1000,"gc.queue_urgency":"normal","gc.queue_goal":"af-u8id"}},
  {"id":"af-quarantined","title":"Quarantined","status":"deferred","metadata":{"gc.queue_product":"saymyname","gc.queue_state":"blocked_durable_failure","gc.queue_rank":2000,"gc.queue_urgency":"normal","gc.queue_goal":"af-u8id","gc.queue_pause_reason":"Panne durable"}}
]'
output=$("$QUEUE" list --json)
assert_contains "$output" '"id":"af-live"'
assert_not_contains "$output" 'af-quarantined'

# resume must still be able to reach a quarantined node directly by id even
# though it is invisible to list/next -- that is how the Mayor lifts a
# campaign-sentinel quarantine (ADR-0016 §7) once the underlying cause is fixed.
: >"$QUEUE_LOG"
"$QUEUE" resume af-quarantined >/dev/null
grep -Fq 'update <af-quarantined> <--set-metadata> <gc.queue_state=queued>' "$QUEUE_LOG"
if "$QUEUE" resume af-does-not-exist >/dev/null 2>&1; then
  fail 'resuming an unknown candidate must fail closed'
fi

# af-tbkcc regression (2026-09-18 23:53Z-02:12Z incident): a candidate's
# status/state was edited outside product-queue's own commands, and the
# read-only `list`/`next` paths died on that one bad tuple -- cascading into
# saymyname-product-status and 8 consecutive campaign-sentinel failures over
# an issue a warning would have surfaced without taking the whole queue
# down. list/next must now exclude the invalid candidate with one WARNING
# naming it and still return the valid ones -- never fail the whole read.
export QUEUE_INVENTORY='[
  {"id":"af-bad","title":"Bad tuple","status":"closed","metadata":{"gc.queue_product":"saymyname","gc.queue_state":"queued","gc.queue_rank":1000,"gc.queue_urgency":"normal","gc.queue_goal":"af-u8id"}}
]'
output=$("$QUEUE" list --json 2>"$TEST_TMP/stderr") \
  || fail "list --json must not fail closed on one bad candidate: $(cat "$TEST_TMP/stderr")"
[[ $output == '[]' ]] || fail "invalid-only queue must project empty, not: $output"
assert_contains "$(cat "$TEST_TMP/stderr")" 'WARNING'
assert_contains "$(cat "$TEST_TMP/stderr")" 'af-bad'

export QUEUE_INVENTORY='[
  {"id":"af-good","title":"Good","status":"deferred","metadata":{"gc.queue_product":"saymyname","gc.queue_state":"queued","gc.queue_rank":1000,"gc.queue_urgency":"normal","gc.queue_goal":"af-u8id"}},
  {"id":"af-bad","title":"Bad tuple","status":"closed","metadata":{"gc.queue_product":"saymyname","gc.queue_state":"queued","gc.queue_rank":2000,"gc.queue_urgency":"normal","gc.queue_goal":"af-u8id"}}
]'
output=$("$QUEUE" list --json 2>"$TEST_TMP/stderr") \
  || fail "list --json must still return the valid candidates: $(cat "$TEST_TMP/stderr")"
assert_contains "$output" '"id":"af-good"'
assert_not_contains "$output" 'af-bad'
assert_contains "$(cat "$TEST_TMP/stderr")" 'af-bad'
output=$("$QUEUE" next --json 2>/dev/null)
assert_contains "$output" '"id":"af-good"'

# Unwanted-behavior EARS: mutation commands must still refuse, as today, when
# the line holds any invalid candidate -- read-side leniency never weakens
# write-side safety.
if "$QUEUE" move af-good 1 >/dev/null 2>&1; then
  fail 'a mutation command must still refuse when the line holds an invalid candidate'
fi
if "$QUEUE" pause af-good 'Some reason' >/dev/null 2>&1; then
  fail 'a mutation command must still refuse when the line holds an invalid candidate'
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
  output=$("$QUEUE" list --json 2>"$TEST_TMP/stderr") \
    || fail "invalid deferred tuple must be excluded, not failed closed: $invalid_metadata"
  [[ $output == '[]' ]] || fail "invalid deferred tuple must project empty: $invalid_metadata -> $output"
  assert_contains "$(cat "$TEST_TMP/stderr")" 'af-bad'
  if "$QUEUE" move af-bad 1 >/dev/null 2>&1; then
    fail "mutation must still fail closed on an invalid tuple: $invalid_metadata"
  fi
done

# ADR-0023: quarantine is the door mayor-campaign's sentinel uses instead of
# writing gc.queue_state=blocked_durable_failure directly.
export QUEUE_INVENTORY='[
  {"id":"af-a","title":"Alpha","status":"deferred","metadata":{"gc.queue_product":"saymyname","gc.queue_state":"queued","gc.queue_rank":1000,"gc.queue_urgency":"normal","gc.queue_goal":"af-u8id"}}
]'
: >"$QUEUE_LOG"
"$QUEUE" quarantine af-a 'Panne durable' >/dev/null
grep -Fq 'gc.queue_state=blocked_durable_failure' "$QUEUE_LOG"
grep -Fq 'gc.queue_pause_reason=Panne durable' "$QUEUE_LOG"
if "$QUEUE" quarantine af-does-not-exist 'Panne' >/dev/null 2>&1; then
  fail 'quarantining an unknown candidate must fail closed'
fi
if "$QUEUE" quarantine af-a >/dev/null 2>&1; then
  fail 'quarantine without a reason must fail closed'
fi

printf 'PASS: product queue ordering, lifecycle, and authority contract\n'
