#!/usr/bin/env bash

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
STATUS_SCRIPT="$REPO_ROOT/bin/saymyname-product-status"
FIXTURE_ROOT="$REPO_ROOT/tests/fixtures/saymyname-product-status"
TESTS_RUN=0

fail_test() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

run_fixture() {
  local scenario=$1
  STATUS_SCENARIO="$scenario" \
    GC_BIN="$FIXTURE_ROOT/gc" \
    GH_BIN="$FIXTURE_ROOT/gh" \
    SAYMYNAME_QUEUE_BIN="$FIXTURE_ROOT/queue" \
    "$STATUS_SCRIPT"
}

run_fixture_json() {
  local scenario=$1
  STATUS_SCENARIO="$scenario" \
    GC_BIN="$FIXTURE_ROOT/gc" \
    GH_BIN="$FIXTURE_ROOT/gh" \
    SAYMYNAME_QUEUE_BIN="$FIXTURE_ROOT/queue" \
    "$STATUS_SCRIPT" --json
}

assert_output() {
  local scenario=$1
  local expected=$2
  local output

  TESTS_RUN=$((TESTS_RUN + 1))
  output=$(run_fixture "$scenario") || fail_test "$scenario should succeed"
  [[ $output == "$expected" ]] || {
    printf 'Expected:\n%s\nActual:\n%s\n' "$expected" "$output" >&2
    fail_test "$scenario output differs"
  }
}

assert_failure() {
  local scenario=$1
  local expected_message=$2
  local output

  TESTS_RUN=$((TESTS_RUN + 1))
  if output=$(run_fixture "$scenario" 2>&1); then
    fail_test "$scenario should fail closed"
  fi
  [[ $output == *"$expected_message"* ]] \
    || fail_test "$scenario did not report the expected recovery message: $output"
}

assert_json() {
  local scenario=$1 expression=$2 expected=$3 output actual
  TESTS_RUN=$((TESTS_RUN + 1))
  output=$(run_fixture_json "$scenario") || fail_test "$scenario should succeed"
  actual=$(jq -er "$expression" <<<"$output") || fail_test "$scenario JSON path failed: $expression"
  [[ $actual == "$expected" ]] || fail_test "$scenario: expected '$expected', got '$actual'"
  [[ $(jq -r '.contract' <<<"$output") == agent-factory-human-state/v1 ]] \
    || fail_test "$scenario contract differs"
  [[ $(jq -r '.model_calls' <<<"$output") == 0 ]] || fail_test "$scenario used a model"
}

assert_json active '.activity.state' working
assert_json idle '.resume.mode + ":" + (.resume.automatic | tostring) + ":" + .next_candidate.state' 'manual:false:eligible'
assert_json human '.resume.mode + ":" + .resume.owner' 'blocking_decision:Benjamin'
assert_json finalizing '.resume.mode + ":" + .result.stage' 'mayor_finalization:finalizing'
assert_json dependency '.activity.state + ":" + .resume.condition' 'waiting_automatic:La dépendance af-proof se ferme'
assert_json blocked '.resume.mode + ":" + .result.cause' 'blocked:La preuve externe requise manque'
assert_json agent-missing '.resume.mode + ":" + .resume.owner' 'materialized_without_agent:Mayor'
assert_json health-down '.health.state + ":" + .activity.state' 'unavailable:stopped'
assert_json health-partial '.health.state + ":" + .activity.state' 'degraded:stopped'
assert_json idle-campaign '.resume.mode + ":" + (.resume.automatic | tostring)' 'automatic_campaign:true'
assert_json all-paused '.resume.mode + ":" + (.next_candidate == null | tostring)' 'all_paused:true'
assert_json no-candidate '.activity.state + ":" + .resume.owner' 'stopped:none'
assert_json green '.last_delivery.evidence' 'PR 24 — merged as bbbbbbbbbbbb; CI green (2 checks)'
assert_json routed '.result.title + ":" + .last_delivery.title' 'Implement backend product outcome:Deliver frontend product outcome'

idle_output=$(run_fixture idle)
[[ $idle_output == *'SANTÉ: Infrastructure disponible'* ]] || fail_test 'idle health missing'
[[ $idle_output == *'ACTIVITÉ: Attend une action facultative'* ]] || fail_test 'idle activity missing'
[[ $idle_output == *'NEXT: af-next — Evaluate supported ChatGPT plugin/MCP bridge — Éligible · non programmé'* ]] || fail_test 'idle NEXT is not canonical'
[[ $idle_output == *'REPRISE AUTOMATIQUE: non'* ]] || fail_test 'idle resume mode missing'
[[ $idle_output == *'ACTION UTILE: Demander « Lance le prochain résultat ».'* ]] || fail_test 'idle action missing'
[[ $idle_output == *'NEEDS BENJAMIN: none — aucune décision bloquante'* ]] || fail_test 'idle blocker distinction missing'
[[ $idle_output != *'si cet état persiste'* ]] || fail_test 'misleading wait advice remains'

assert_failure mismatch "does not match the delivered Bead head and merge evidence"
assert_failure invalid-repo "must be a valid owner/repository name"
assert_failure source-failure "Beads product coordination source command failed"
assert_failure queue-failure "SayMyName product queue source command failed"
assert_failure queue-inconsistent "canonical human candidate contract"
assert_failure mismatch-next "Coordination NEXT disagrees"

printf 'PASS: %d deterministic product-status checks\n' "$TESTS_RUN"
