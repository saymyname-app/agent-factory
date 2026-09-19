#!/usr/bin/env bash

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
STATUS_SCRIPT="$REPO_ROOT/bin/saymyname-product-status"
FIXTURE_ROOT="$REPO_ROOT/tests/fixtures/saymyname-product-status"
TESTS_RUN=0
STDERR_FILE=$(mktemp)
trap 'rm -f "$STDERR_FILE"' EXIT

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

# A malformed Bead in one section (last delivered outcome, or current
# outcome) must degrade that section only: the projection still succeeds,
# still carries the canonical contract, and still logs an operator-visible
# WARNING -- it must never die() and take the whole projection down
# (governance invariant a, af-wisp-c3zmg6).
assert_degraded() {
  local scenario=$1 expression=$2 expected_substring=$3 warning_substring=$4
  local output actual stderr_output

  TESTS_RUN=$((TESTS_RUN + 1))
  output=$(run_fixture_json "$scenario" 2>"$STDERR_FILE") \
    || fail_test "$scenario should degrade, not fail closed"
  actual=$(jq -er "$expression" <<<"$output") || fail_test "$scenario JSON path failed: $expression"
  [[ $actual == *"$expected_substring"* ]] \
    || fail_test "$scenario: expected '$actual' to contain '$expected_substring'"
  [[ $(jq -r '.contract' <<<"$output") == agent-factory-human-state/v1 ]] \
    || fail_test "$scenario contract differs while degraded"
  stderr_output=$(cat "$STDERR_FILE")
  [[ $stderr_output == *"WARNING"*"$warning_substring"* ]] \
    || fail_test "$scenario did not log the expected degrade WARNING: $stderr_output"
}

assert_json active '.activity.state' working
assert_json idle '.resume.mode + ":" + (.resume.automatic | tostring) + ":" + .next_candidate.state' 'manual:false:eligible'
assert_json human '.resume.mode + ":" + .resume.owner' 'blocking_decision:Benjamin'
assert_json finalizing '.resume.mode + ":" + .result.stage' 'mayor_finalization:finalizing'
# A current result closed without being finalized (af-7700, 2026-09-16) is the
# Mayor's finalization, not a result waiting for an agent -- and it must not
# even need the degrade path.
assert_json closed-current '.resume.mode + ":" + .result.stage' 'mayor_finalization:finalizing'
assert_json closed-current '.result.phase' 'Fermé mais non finalisé · enregistrer les preuves avec bin/deliver-close, puis avancer gc.last_delivered et gc.current'
TESTS_RUN=$((TESTS_RUN + 1))
run_fixture_json closed-current >/dev/null 2>"$STDERR_FILE" || fail_test "closed-current should succeed"
[[ $(cat "$STDERR_FILE") != *WARNING* ]] || fail_test "closed-current went through the degrade path"
assert_json dependency '.activity.state + ":" + .resume.condition' 'waiting_automatic:La dépendance af-proof se ferme'
# C7: a current result closed while explicitly waiting (an automatic
# dependency, or a bare gc.waiting_on hold) must not be nagged to finalize
# like af-7700 was -- it has nothing owed until the wait is lifted (live case:
# af-u8id.4.1).
assert_json closed-dependency '.resume.mode + ":" + .resume.condition' 'automatic_dependency:La dépendance af-proof se ferme'
TESTS_RUN=$((TESTS_RUN + 1))
run_fixture_json closed-dependency >/dev/null 2>"$STDERR_FILE" || fail_test "closed-dependency should succeed"
[[ $(cat "$STDERR_FILE") != *WARNING* ]] || fail_test "closed-dependency went through the degrade path"
assert_json closed-waiting-on '.result.stage' 'materialized'
assert_json closed-waiting-on '.result.phase' 'Fermé, en attente délibérée (po) · rien à finaliser tant que ce n'"'"'est pas levé'
assert_json blocked '.resume.mode + ":" + .result.cause' 'blocked:La preuve externe requise manque'
assert_json agent-missing '.resume.mode + ":" + .resume.owner' 'materialized_without_agent:Mayor'
assert_json health-down '.health.state + ":" + .activity.state' 'unavailable:stopped'
assert_json health-partial '.health.state + ":" + .activity.state' 'degraded:stopped'
assert_json idle-campaign '.resume.mode + ":" + (.resume.automatic | tostring)' 'automatic_campaign:true'
assert_json idle-campaign '.campaign.state + ":" + .campaign.owner' 'active:Mayor'
assert_json campaign-decision '.resume.action' 'Valider le périmètre puis demander au Mayor de reprendre'
assert_json campaign-decision '.campaign.action' 'Valider le périmètre puis demander au Mayor de reprendre'
assert_json campaign-decision '.campaign.cause + ":" + .campaign.owner' 'La campagne attend le choix de périmètre:Benjamin'
assert_json campaign-admin '.campaign.state + ":" + .campaign.blocker_kind + ":" + .campaign.owner + ":" + (.needs_benjamin == null | tostring)' 'blocked:admin:Benjamin:true'
assert_json campaign-durable '.resume.mode + ":" + .campaign.cause' 'campaign_blocked:Trois lectures déterministes ont échoué'
assert_json campaign-retry '.activity.state + ":" + (.resume.automatic | tostring) + ":" + .campaign.blocker_kind' 'waiting_automatic:true:transient_failure'
assert_json campaign-all-paused '.campaign.state + ":" + .campaign.owner + ":" + (.needs_benjamin == null | tostring)' 'blocked:Mayor:true'
assert_json all-paused '.resume.mode + ":" + (.next_candidate == null | tostring)' 'all_paused:true'
assert_json no-candidate '.activity.state + ":" + .resume.owner' 'stopped:none'
assert_json green '.last_delivery.evidence' 'PR 24 — merged as bbbbbbbbbbbb; CI green (2 checks)'
assert_json routed '.result.title + ":" + .last_delivery.title' 'Implement backend product outcome:Deliver frontend product outcome'
assert_json direct '.activity.state + ":" + .result.agent' 'working:codex-af-jqla'
# af-9z472: a v2 workflow root's gc.session_name is stamped once from its
# first step and never updated. The current-outcome bead here carries
# gc.kind=workflow plus that stale session data; the direct-session branch
# must not trust it (it would report materialized/no-agent) -- the fix
# skips straight to convoy/workflow matching, which finds the live current
# step's session instead.
assert_json workflow-root '.activity.state + ":" + .result.agent' 'working:codex-af-test'
# af-illx1: when current_id IS the workflow root itself (not someone else's
# leaf), its own convoy tracks its implementation children, never itself --
# the tracks-matching loop above never finds it that way. Nothing else
# tracks it here (emit_workflows returns an empty inventory), so the fix
# must fall back to treating the in-progress workflow current_issue itself
# as the active result and resolve its own live current step's session.
assert_json self-workflow '.activity.state + ":" + .result.agent' 'working:codex-af-self'
# af-6k6sn: a v2 workflow root's gc.session_name is stamped once and never
# updated as later formula steps hand off to new sessions. Once handed off
# past the first step, a session_name-filtered step lookup always finds
# zero -- the old active_count reused that same lookup and misreported a
# genuinely running workflow (its convoy still has an open tracked child)
# as "finalizing". The fix checks the workflow's own convoy membership
# instead: result.stage must stay "active", not roll over to "finalizing",
# even though no specific current step/agent can be named from the stale
# session.
assert_json self-workflow-handoff '.result.stage + ":" + (.result.agent == null | tostring)' 'active:true'
# af-lwgmt: an "active" result whose specific hand-off session can't be
# resolved must still resolve to resume.mode active_delivery, not
# materialized_without_agent -- the latter is not a PROGRESS_REASON
# (bin/mayor-campaign), so gc.campaign_progress_at would freeze and the
# sentinel would re-send a "reprendre" wake every tick even while the
# workflow's convoy proves sub-agent sessions are genuinely active.
assert_json self-workflow-handoff '.resume.mode' 'active_delivery'
assert_json workflow-pending-finalize '.resume.mode' 'active_delivery'
# af-knbxq: the implementation convoy closing (active_count == 0) is not the
# same as the whole v2 workflow finishing -- starter review, publish, and
# finalize-workflow are the workflow root's own open "blocks" dependency
# (its completion gate), not convoy members, and must hold off finalizing
# until that gate itself closes (live case smb-44tt/smb-3akx 2026-09-18).
assert_json workflow-pending-finalize '.result.stage + ":" + (.result.agent == null | tostring)' 'active:true'
# Once the completion gate itself closes, active_count == 0 must still
# resolve to finalizing as before -- the fix narrows the check, it does not
# remove it.
assert_json workflow-truly-finalizing '.result.stage' 'finalizing'

idle_output=$(run_fixture idle)
[[ $idle_output == *'SANTÉ: Infrastructure disponible'* ]] || fail_test 'idle health missing'
[[ $idle_output == *'ACTIVITÉ: Attend une action facultative'* ]] || fail_test 'idle activity missing'
[[ $idle_output == *'NEXT: af-next — Evaluate supported ChatGPT plugin/MCP bridge — Éligible · non programmé'* ]] || fail_test 'idle NEXT is not canonical'
[[ $idle_output == *'REPRISE AUTOMATIQUE: non'* ]] || fail_test 'idle resume mode missing'
[[ $idle_output == *'CAMPAGNE: Campagne inactive'* ]] || fail_test 'idle campaign state missing'
[[ $idle_output == *'ACTION UTILE: Demander « Lance le prochain résultat ».'* ]] || fail_test 'idle action missing'
[[ $idle_output == *'NEEDS BENJAMIN: none — aucune décision bloquante'* ]] || fail_test 'idle blocker distinction missing'
[[ $idle_output != *'si cet état persiste'* ]] || fail_test 'misleading wait advice remains'

TESTS_RUN=$((TESTS_RUN + 1))
campaign_decision_output=$(run_fixture campaign-decision)
[[ $campaign_decision_output == *'ACTION UTILE: Valider le périmètre puis demander au Mayor de reprendre'* ]] \
  || fail_test 'campaign decision exact action is missing from the human CLI'
[[ $campaign_decision_output != *'ACTION UTILE: Répondre à la décision bloquante.'* ]] \
  || fail_test 'campaign decision uses the misleading fallback action'

assert_degraded proof-missing '.last_delivery.evidence' 'Preuve de livraison manquante ou invalide pour af-delivered' 'af-delivered'
assert_json proof-missing '.activity.state' working
assert_degraded mismatch '.last_delivery.evidence' 'Preuve de livraison manquante ou invalide pour af-delivered' 'af-delivered'
assert_degraded invalid-repo '.last_delivery.evidence' 'Preuve de livraison manquante ou invalide pour af-delivered' 'af-delivered'
assert_degraded direct-ambiguous '.result.stage' 'materialized' 'smb-direct'
assert_failure source-failure "Beads product coordination source command failed"
assert_failure queue-failure "SayMyName product queue source command failed"
assert_failure queue-inconsistent "canonical human candidate contract"
# ADR-0023: gc.next_outcome is retired. A bead that still carries a stale
# value in that field (leftover from before the retirement) must have no
# effect at all -- the queue alone decides NEXT, and nothing warns about the
# stale field, because nothing reads it any more.
TESTS_RUN=$((TESTS_RUN + 1))
output=$(run_fixture_json mismatch-next 2>"$STDERR_FILE") \
  || fail_test "mismatch-next should succeed"
[[ $(jq -er '.next_candidate.state' <<<"$output") == eligible ]] \
  || fail_test "mismatch-next: queue-derived NEXT was not eligible"
[[ $(cat "$STDERR_FILE") != *"next_outcome"* ]] \
  || fail_test "mismatch-next logged a warning about a field that is no longer read: $(cat "$STDERR_FILE")"

# af-tbkcc regression (2026-09-18 23:53Z-02:12Z incident): product-queue now
# excludes one invalid candidate with a WARNING instead of dying on the whole
# read (bin/product-queue's own list --json fix). saymyname-product-status
# must see this as an ordinary working queue source -- not a hard source
# failure that takes down the whole projection -- while the exclusion
# WARNING it logged remains visible to the operator.
TESTS_RUN=$((TESTS_RUN + 1))
output=$(run_fixture_json queue-candidate-excluded 2>"$STDERR_FILE") \
  || fail_test "queue-candidate-excluded should degrade, not fail closed"
[[ $(jq -r '.next_candidate.id' <<<"$output") == af-next ]] \
  || fail_test "queue-candidate-excluded lost the valid candidate"
[[ $(jq -r '.contract' <<<"$output") == agent-factory-human-state/v1 ]] \
  || fail_test "queue-candidate-excluded contract differs"
[[ $(cat "$STDERR_FILE") == *"WARNING"*"af-bad"* ]] \
  || fail_test "queue-candidate-excluded did not surface the excluded candidate's warning"

printf 'PASS: %d deterministic product-status checks\n' "$TESTS_RUN"
