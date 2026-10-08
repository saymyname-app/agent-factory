#!/usr/bin/env bash
#
# O06 / C01 T06: escalation-door is the one door for every escalation
# (replaces bin/campaign-pointer escalate). Proves: `benjamin` refuses an
# incomprehensible request without writing anything (missing field, a line
# over 140 characters, an option with no consequence, two "Recommandé",
# a recommendation with no reason, a language other than the Operator
# Language); a complete request is written with its fields, timestamp and
# blocking flag and still shows up on `list`; `repondre` writes the chosen
# option, clears NEEDS BENJAMIN and wakes the Mayor, and refuses an unknown
# option; Mayor-first only escalates after 2h unresolved (fake clock) and a
# sweep promotion never fails even on an incomplete source; every escalation
# fails loudly (no `>/dev/null || true`).

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

# A complete request Benjamin can understand without opening an agent
# session: quoi / pourquoi / que faire (each option with its consequence, at
# most one Recommandé with its reason) / langue.
COMPLETE_REQUEST='{
  "quoi": "Le graphe du chantier T09 est en attente d'\''approbation",
  "pourquoi": "Aucun agent ne peut approuver un graphe : c'\''est ta décision",
  "que_faire": [
    {"option": "Approuver le graphe", "consequence": "La livraison démarre.", "recommande": true, "raison": "Le graphe respecte la Spec approuvée."},
    {"option": "Rejeter le graphe", "consequence": "Retour à la carte de planification."}
  ],
  "langue": "fr"
}'

# --- benjamin refuses an incomplete or malformed request --------------------
reset_beads
seed af-blocker '{"id":"af-blocker","status":"open","metadata":{},"notes":"","labels":[]}'

TESTS_RUN=$((TESTS_RUN + 1))
missing_field=$(jq 'del(.pourquoi)' <<<"$COMPLETE_REQUEST")
if door benjamin af-blocker "$missing_field" >/dev/null 2>&1; then
  fail "benjamin with a missing field must refuse"
fi
[[ $(jq -c '.' "$TEST_TMP/beads/af-blocker.json") == '{"id":"af-blocker","status":"open","metadata":{},"notes":"","labels":[]}' ]] \
  || fail "benjamin must leave the bead untouched when it refuses a missing field"

TESTS_RUN=$((TESTS_RUN + 1))
long_line=$(jq --arg q "$(printf 'x%.0s' {1..141})" '.quoi = $q' <<<"$COMPLETE_REQUEST")
if door benjamin af-blocker "$long_line" >/dev/null 2>&1; then
  fail "benjamin with a line over 140 characters must refuse"
fi

TESTS_RUN=$((TESTS_RUN + 1))
no_consequence=$(jq '.que_faire[0] |= del(.consequence)' <<<"$COMPLETE_REQUEST")
if door benjamin af-blocker "$no_consequence" >/dev/null 2>&1; then
  fail "benjamin with an option lacking a consequence must refuse"
fi

TESTS_RUN=$((TESTS_RUN + 1))
two_recommended=$(jq '.que_faire[1].recommande = true | .que_faire[1].raison = "aussi valable"' <<<"$COMPLETE_REQUEST")
if door benjamin af-blocker "$two_recommended" >/dev/null 2>&1; then
  fail "benjamin with two Recommandé options must refuse"
fi

TESTS_RUN=$((TESTS_RUN + 1))
unreasoned_recommendation=$(jq '.que_faire[0] |= del(.raison)' <<<"$COMPLETE_REQUEST")
if door benjamin af-blocker "$unreasoned_recommendation" >/dev/null 2>&1; then
  fail "benjamin with a Recommandé option lacking its raison must refuse"
fi

TESTS_RUN=$((TESTS_RUN + 1))
other_language=$(jq '.langue = "en"' <<<"$COMPLETE_REQUEST")
if door benjamin af-blocker "$other_language" >/dev/null 2>&1; then
  fail "benjamin with a request not in the Operator Language must refuse"
fi

[[ $(jq -c '.' "$TEST_TMP/beads/af-blocker.json") == '{"id":"af-blocker","status":"open","metadata":{},"notes":"","labels":[]}' ]] \
  || fail "every refused benjamin call must leave the bead intact"

TESTS_RUN=$((TESTS_RUN + 1))
: >"$TEST_TMP/calls.log"
if ED_MAIL_FAIL=human GC_BIN="$FIXTURE" ED_BEAD_DIR="$TEST_TMP/beads" ED_CALL_LOG="$TEST_TMP/calls.log" \
    ESCALATION_DOOR_LOCK_FILE="$TEST_TMP/lock" "$SCRIPT" benjamin af-blocker "$COMPLETE_REQUEST" >/dev/null 2>&1; then
  fail "benjamin must refuse (non-zero, visible) when the mail cannot be sent"
fi

# --- benjamin writes a complete request with its timestamp and flag --------
reset_beads
seed af-blocker '{"id":"af-blocker","status":"open","metadata":{},"notes":"","labels":[]}'
TESTS_RUN=$((TESTS_RUN + 1))
blocking_request=$(jq '.bloquant = true' <<<"$COMPLETE_REQUEST")
door benjamin af-blocker "$blocking_request" >/dev/null || fail "a complete request should be accepted"
written=$(bead af-blocker)
[[ $(jq -r '.metadata["gc.needs_benjamin"]' <<<"$written") == *"graphe du chantier T09"* ]] \
  || fail "benjamin did not write the quoi field onto gc.needs_benjamin"
[[ $(jq -r '.metadata["gc.escalation_pourquoi"]' <<<"$written") == *"c'est ta décision"* ]] \
  || fail "benjamin did not write the pourquoi field"
[[ $(jq -r '.metadata["gc.escalation_bloquant"]' <<<"$written") == "true" ]] \
  || fail "benjamin did not write the blocking flag"
[[ -n $(jq -r '.metadata["gc.escalation_horodatage"]' <<<"$written") ]] \
  || fail "benjamin did not stamp a timestamp"
que_faire=$(jq -r '.metadata["gc.escalation_que_faire"]' <<<"$written")
[[ $(jq -r '.[0].lettre' <<<"$que_faire") == a ]] || fail "benjamin did not letter the first option 'a'"
[[ $(jq -r '.[1].lettre' <<<"$que_faire") == b ]] || fail "benjamin did not letter the second option 'b'"
[[ $(jq -r '.notes' <<<"$written") == *"NEEDS BENJAMIN"* ]] \
  || fail "benjamin did not append the cause to the bead's notes"
grep -Fq 'mail send human' "$TEST_TMP/calls.log" || fail "benjamin did not mail the escalation recipient"

TESTS_RUN=$((TESTS_RUN + 1))
out=$(door list) || fail "list should succeed"
grep -Fq "graphe du chantier T09" <<<"$out" \
  || { echo "$out" >&2; fail "list did not display the complete request as before"; }

# --- lien: the optional link of the dossier a request carries (T26) ---------
# A request may carry the link of the dossier Benjamin reads to decide (the
# « non conforme » request of a convoy carries its Evidence Pack). One line,
# longer than 140 characters if the path is; stored, mailed, and printed by
# `list` on the request's own line.
reset_beads
seed af-blocker '{"id":"af-blocker","status":"open","metadata":{},"notes":"","labels":[]}'
TESTS_RUN=$((TESTS_RUN + 1))
long_link="/tmp/$(printf 'dossier-%.0s' {1..30})/evidence-pack/index.html"
(( ${#long_link} > 140 )) || fail "the test link should be longer than a field's 140 characters"
linked_request=$(jq --arg lien "$long_link" '.lien = $lien' <<<"$COMPLETE_REQUEST")
door benjamin af-blocker "$linked_request" >/dev/null || fail "a request with a link should be accepted"
[[ $(jq -r '.metadata["gc.escalation_lien"]' <<<"$(bead af-blocker)") == "$long_link" ]] \
  || fail "benjamin did not write the link of the dossier"
grep -Fq "DOSSIER: $long_link" "$TEST_TMP/calls.log" || fail "the escalation mail does not carry the link of the dossier"
out=$(door list) || fail "list should succeed"
[[ $(grep -c "af-blocker" <<<"$out") == 1 ]] || { echo "$out" >&2; fail "list must print one line per request"; }
grep -F "af-blocker" <<<"$out" | grep -Fq "en attente d'approbation — dossier : $long_link" \
  || { echo "$out" >&2; fail "list did not print the link on the request's line"; }

TESTS_RUN=$((TESTS_RUN + 1))
before=$(bead af-blocker)
for bad in '"deux\nlignes"' '""' '12' '["/x"]'; do
  refused=$(jq --argjson lien "$bad" '.lien = $lien' <<<"$COMPLETE_REQUEST")
  if door benjamin af-blocker "$refused" >/dev/null 2>&1; then
    fail "benjamin must refuse a link that is not one non-empty line ($bad)"
  fi
  [[ $(bead af-blocker) == "$before" ]] || fail "a refused link ($bad) wrote onto the bead"
done

# A later request with no link, on the same bead, does not keep the old one.
TESTS_RUN=$((TESTS_RUN + 1))
door benjamin af-blocker "$COMPLETE_REQUEST" >/dev/null || fail "a request without a link should be accepted"
[[ $(jq -r '.metadata["gc.escalation_lien"]' <<<"$(bead af-blocker)") == none ]] \
  || fail "a request without a link kept the link of the request before"
out=$(door list) || fail "list should succeed"
grep -Fq "dossier :" <<<"$out" && { echo "$out" >&2; fail "list printed the link of a request that has none"; }

# A bead that never had a link gets no link field at all.
reset_beads
seed af-blocker '{"id":"af-blocker","status":"open","metadata":{},"notes":"","labels":[]}'
TESTS_RUN=$((TESTS_RUN + 1))
door benjamin af-blocker "$COMPLETE_REQUEST" >/dev/null || fail "a complete request should be accepted"
[[ $(jq -r '.metadata | has("gc.escalation_lien")' <<<"$(bead af-blocker)") == false ]] \
  || fail "a request without a link wrote a link field on a bead that had none"
grep -Fq "DOSSIER:" "$TEST_TMP/calls.log" && fail "the mail of a request without a link names a dossier"

# --- repondre writes the chosen option, clears, and wakes the Mayor --------
TESTS_RUN=$((TESTS_RUN + 1))
: >"$TEST_TMP/calls.log"
door repondre af-blocker a >/dev/null || fail "repondre should succeed for a known option"
written=$(bead af-blocker)
[[ $(jq -r '.metadata["gc.escalation_response_option"]' <<<"$written") == a ]] \
  || fail "repondre did not write the chosen option"
[[ -n $(jq -r '.metadata["gc.escalation_response_at"]' <<<"$written") ]] \
  || fail "repondre did not write when it happened"
[[ $(jq -r '.metadata["gc.escalation_response_actor"]' <<<"$written") == benjamin ]] \
  || fail "repondre did not write the acting actor"
[[ $(jq -r '.metadata["gc.needs_benjamin"]' <<<"$written") == none ]] \
  || fail "repondre did not clear NEEDS BENJAMIN"
[[ $(jq -r '.notes' <<<"$written") == *"RÉPONSE"* ]] \
  || fail "repondre did not trace the response in the bead's notes"
grep -Fq 'mail send mayor' "$TEST_TMP/calls.log" || fail "repondre did not wake the Mayor"
grep -Fq "répondu a sur af-blocker" "$TEST_TMP/calls.log" \
  || fail "repondre's wake-up mail did not name the fixed phrase 'répondu <lettre> sur <bead>'"

TESTS_RUN=$((TESTS_RUN + 1))
if door repondre af-blocker z >/dev/null 2>&1; then
  fail "repondre with an option that was never offered must refuse"
fi

TESTS_RUN=$((TESTS_RUN + 1))
reset_beads
seed af-no-options '{"id":"af-no-options","status":"open","metadata":{},"notes":"","labels":[]}'
if door repondre af-no-options a >/dev/null 2>&1; then
  fail "repondre on a bead with no recorded options must refuse"
fi

# --- list (read-only CLI) ---------------------------------------------------
TESTS_RUN=$((TESTS_RUN + 1))
reset_beads
seed af-blocker '{"id":"af-blocker","status":"open","metadata":{"gc.needs_benjamin":"Irreversible production change"},"notes":"","labels":[]}'
seed af-proposal-1 '{"id":"af-proposal-1","status":"open","metadata":{},"notes":"","labels":["proposal"]}'
seed af-proposal-2 '{"id":"af-proposal-2","status":"open","metadata":{},"notes":"","labels":["proposal"]}'
out=$(door list) || fail "list should succeed"
grep -Fq "af-blocker — Irreversible production change" <<<"$out" \
  || { echo "$out" >&2; fail "list did not print the escalated bead and its reason"; }
grep -Fq "Pending proposals: 2" <<<"$out" \
  || { echo "$out" >&2; fail "list did not print the pending-proposal count"; }

# af-1al0t1: a NEEDS BENJAMIN stays visible whatever the bead's status -- a
# parked (blocked) or deferred bead in the main list, a closed bead in its
# own section (the close did not answer the question). A cleared one never.
TESTS_RUN=$((TESTS_RUN + 1))
reset_beads
seed af-parked '{"id":"af-parked","status":"blocked","metadata":{"gc.needs_benjamin":"Choisir une variante"},"notes":"","labels":[]}'
seed af-later '{"id":"af-later","status":"deferred","metadata":{"gc.needs_benjamin":"Question reportée"},"notes":"","labels":[]}'
seed af-shut '{"id":"af-shut","status":"closed","metadata":{"gc.needs_benjamin":"Question jamais montrée","gc.work_outcome":"blocked"},"notes":"","labels":[]}'
seed af-done '{"id":"af-done","status":"closed","metadata":{"gc.needs_benjamin":"none"},"notes":"","labels":[]}'
out=$(door list) || fail "list should succeed"
grep -Fq "af-parked — Choisir une variante" <<<"$out" \
  || { echo "$out" >&2; fail "list did not show a NEEDS BENJAMIN on a parked (blocked) bead"; }
grep -Fq "af-later — Question reportée" <<<"$out" \
  || { echo "$out" >&2; fail "list did not show a NEEDS BENJAMIN on a deferred bead"; }
grep -Fq "af-shut — Question jamais montrée" <<<"$out" \
  || { echo "$out" >&2; fail "list did not show an active NEEDS BENJAMIN on a closed bead"; }
closed_section=$(sed -n '/sur un bead fermé/,$p' <<<"$out")
grep -Fq "af-shut" <<<"$closed_section" \
  || { echo "$out" >&2; fail "list did not put the closed bead in its own section"; }
grep -Fq "af-parked" <<<"$closed_section" \
  && { echo "$out" >&2; fail "list put an unclosed bead in the closed section"; }
grep -Fq "af-done" <<<"$out" && { echo "$out" >&2; fail "list showed a cleared (none) NEEDS BENJAMIN"; }

# --- repondre reopens work parked (or closed) as blocked --------------------
# af-1al0t1: an answered NEEDS BENJAMIN on a ticket deliver-close parked
# (status blocked, gc.work_outcome=blocked) -- or closed as blocked before
# that fix -- puts it back in the ready pool, so a worker resumes it and its
# dependents stay gated until it is delivered.
ANSWERABLE_QUE_FAIRE='[{"option":"Variante B","consequence":"T22 suit B.","lettre":"b"}]'
for status in blocked closed; do
  TESTS_RUN=$((TESTS_RUN + 1))
  reset_beads
  seed af-t21 "$(jq -nc --arg s "$status" --arg q "$ANSWERABLE_QUE_FAIRE" '
    {id: "af-t21", status: $s,
     metadata: {"gc.needs_benjamin": "Choisir une variante", "gc.escalation_que_faire": $q,
                "gc.outcome": (if $s == "closed" then "pass" else "blocked" end),
                "gc.work_outcome": "blocked", "gc.blocked_classification": "repair"},
     notes: "", labels: []}')"
  door repondre af-t21 b >/dev/null || fail "repondre on a $status-blocked ticket should succeed"
  written=$(bead af-t21)
  [[ $(jq -r '.status' <<<"$written") == open ]] \
    || fail "repondre did not reopen a $status ticket with gc.work_outcome=blocked: $written"
  [[ $(jq -r '.metadata | has("gc.work_outcome") or has("gc.outcome") or has("gc.blocked_classification")' <<<"$written") == false ]] \
    || fail "repondre left a stale blocked outcome on the reopened $status ticket: $written"
  [[ $(jq -r '.metadata["gc.needs_benjamin"]' <<<"$written") == none ]] \
    || fail "repondre did not clear NEEDS BENJAMIN on the $status ticket"
  grep -Fq "rouvert" "$TEST_TMP/calls.log" \
    || fail "repondre's Mayor mail did not say the $status ticket was reopened"
done

# A bead that was not blocked keeps its status: repondre is not a reopen door.
TESTS_RUN=$((TESTS_RUN + 1))
reset_beads
seed af-shipped "$(jq -nc --arg q "$ANSWERABLE_QUE_FAIRE" '
  {id: "af-shipped", status: "closed",
   metadata: {"gc.needs_benjamin": "Vieille question", "gc.escalation_que_faire": $q,
              "gc.work_outcome": "shipped"}, notes: "", labels: []}')"
door repondre af-shipped b >/dev/null || fail "repondre on a shipped bead should succeed"
[[ $(jq -r '.status' "$TEST_TMP/beads/af-shipped.json") == closed ]] \
  || fail "repondre reopened a bead that was delivered, not blocked"
[[ $(jq -r '.metadata["gc.work_outcome"]' "$TEST_TMP/beads/af-shipped.json") == shipped ]] \
  || fail "repondre touched the outcome of a delivered bead"

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

# At/after 2h: sweep must escalate to Benjamin -- and never fail even though
# af-order carries no quoi/pourquoi/que_faire of its own (T06: an incomplete
# source stays a written, incomplete request, not a sweep failure).
TESTS_RUN=$((TESTS_RUN + 1))
: >"$TEST_TMP/calls.log"
ESCALATION_DOOR_NOW=$((T0 + 7200)) door sweep >/dev/null || fail "sweep should succeed at the 2h boundary"
written=$(bead af-order)
[[ $(jq -r '.metadata["gc.needs_benjamin"]' <<<"$written") == *"non résolue après 2h"* ]] \
  || fail "sweep did not promote the unresolved Mayor-first escalation to Benjamin"
[[ $(jq -r '.metadata["gc.escalation_pourquoi"]' <<<"$written") == *"il n'a pas dit pourquoi"* ]] \
  || fail "sweep did not fill the fixed repli pourquoi for an incomplete source"
[[ $(jq -r '.metadata["gc.escalation_que_faire"]' <<<"$written") == *"continuer avec un agent"* ]] \
  || fail "sweep did not fill the fixed repli option for an incomplete source"
grep -Fq 'mail send human' "$TEST_TMP/calls.log" || fail "sweep did not mail Benjamin once promoted"

# A second sweep must not re-page: the bead now carries gc.needs_benjamin.
TESTS_RUN=$((TESTS_RUN + 1))
: >"$TEST_TMP/calls.log"
ESCALATION_DOOR_NOW=$((T0 + 10800)) door sweep >/dev/null || fail "a later sweep should still succeed"
grep -Fq 'mail send human' "$TEST_TMP/calls.log" && fail "sweep re-escalated an already-escalated bead"

# A sweep promotion keeps quoi/pourquoi/que_faire escalation-door already
# wrote on the bead, instead of overwriting them with the repli text.
reset_beads
EXISTING_QUE_FAIRE='[{"option":"Continuer","consequence":"Rien ne change.","lettre":"a"}]'
seed af-has-fields "$(jq -nc --arg que_faire "$EXISTING_QUE_FAIRE" '
  {id: "af-has-fields", status: "open",
   metadata: {"gc.escalation_mayor_paged_at": "2026-09-30T00:00:00Z",
              "gc.escalation_mayor_reason": "stuck PR",
              "gc.escalation_pourquoi": "Déjà posée avec sa raison",
              "gc.escalation_que_faire": $que_faire},
   notes: "", labels: []}')"
TESTS_RUN=$((TESTS_RUN + 1))
ESCALATION_DOOR_NOW=$((T0 + 7200)) door sweep >/dev/null || fail "sweep should succeed on a bead with existing fields"
written=$(bead af-has-fields)
[[ $(jq -r '.metadata["gc.escalation_pourquoi"]' <<<"$written") == "Déjà posée avec sa raison" ]] \
  || fail "sweep must keep an existing pourquoi instead of overwriting it with the repli text"
[[ $(jq -r '.metadata["gc.escalation_que_faire"]' <<<"$written") == *"Continuer"* ]] \
  || fail "sweep must keep the existing que_faire instead of overwriting it with the repli option"

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

# A page about the bead's own PR is resolved by that PR's verified merge: the
# sweep clears it instead of promoting it (af-53v22s, 2026-10-01: PR #360
# merged at 00:16 Paris, its "rejected 3 times" page reached Benjamin at
# 01:22 on a ticket already delivered).
reset_beads
MERGED_REASON="PR #360 rejected 3 times: required check 'Tests' failed after one retry"
seed af-shipped "$(jq -nc --arg reason "$MERGED_REASON" '
  {id: "af-shipped", status: "closed",
   metadata: {"gc.escalation_mayor_paged_at": "2026-09-01T00:00:00Z",
              "gc.escalation_mayor_reason": $reason,
              "gc.delivery_status": "merged", "gc.pr_number": 360},
   notes: "", labels: []}')"
# Same page on a merged ticket, but about another PR: not resolved by this merge.
seed af-otherpr "$(jq -nc '
  {id: "af-otherpr", status: "closed",
   metadata: {"gc.escalation_mayor_paged_at": "2026-09-01T00:00:00Z",
              "gc.escalation_mayor_reason": "PR #361 rejected 3 times: conflict",
              "gc.delivery_status": "merged", "gc.pr_number": 360},
   notes: "", labels: []}')"
# Same page, PR still open: not resolved.
seed af-stillred "$(jq -nc --arg reason "$MERGED_REASON" '
  {id: "af-stillred", status: "open",
   metadata: {"gc.escalation_mayor_paged_at": "2026-09-01T00:00:00Z",
              "gc.escalation_mayor_reason": $reason, "gc.pr_number": 360},
   notes: "", labels: []}')"
TESTS_RUN=$((TESTS_RUN + 1))
: >"$TEST_TMP/calls.log"
ESCALATION_DOOR_NOW=$((T0 + 7200)) door sweep >/dev/null || fail "sweep should succeed on a page resolved by a merge"
written=$(bead af-shipped)
[[ $(jq -r '.metadata["gc.needs_benjamin"] // "none"' <<<"$written") == none ]] \
  || fail "a page about a PR that merged must not be promoted to Benjamin"
[[ $(jq -r '.metadata["gc.escalation_mayor_paged_at"]' <<<"$written") == none ]] \
  || fail "a page resolved by its merged PR must be cleared, not left to be swept again"
[[ $(jq -r '.notes' <<<"$written") == *"MAYOR FIRST RESOLVED"* ]] \
  || fail "clearing a page resolved by a merge must be traced in the bead's notes"
[[ $(jq -r '.metadata["gc.needs_benjamin"] // "none"' "$TEST_TMP/beads/af-otherpr.json") == *"non résolue après 2h"* ]] \
  || fail "a page about another PR than the merged one must still be promoted"
[[ $(jq -r '.metadata["gc.needs_benjamin"] // "none"' "$TEST_TMP/beads/af-stillred.json") == *"non résolue après 2h"* ]] \
  || fail "a page about a PR that is not merged must still be promoted"

# --- clear -------------------------------------------------------------------
reset_beads
seed af-blocker '{"id":"af-blocker","status":"open","metadata":{"gc.needs_benjamin":"Cause"},"notes":"","labels":[]}'
TESTS_RUN=$((TESTS_RUN + 1))
door clear af-blocker >/dev/null || fail "clear should succeed"
[[ $(jq -r '.metadata["gc.needs_benjamin"]' "$TEST_TMP/beads/af-blocker.json") == none ]] \
  || fail "clear did not clear gc.needs_benjamin"
[[ $(jq -r '.notes' "$TEST_TMP/beads/af-blocker.json") == *"DECISION CLEARED"* ]] \
  || fail "clear did not trace the clearance in the bead's notes"
# af-mjfvwx: the note carries no date of its own; the Cockpit journal dates
# a clearance from this stamp ("date inconnue" without it).
[[ $(jq -r '.metadata["gc.escalation_cleared_at"] // ""' "$TEST_TMP/beads/af-blocker.json") =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]{8}Z$ ]] \
  || fail "clear did not date the clearance (gc.escalation_cleared_at)"

# af-1al0t1: clearing the question of parked-blocked work reopens it too --
# otherwise it would stay parked with nobody left to answer.
TESTS_RUN=$((TESTS_RUN + 1))
reset_beads
seed af-parked '{"id":"af-parked","status":"blocked","metadata":{"gc.needs_benjamin":"Cause","gc.outcome":"blocked","gc.work_outcome":"blocked","gc.blocked_classification":"repair"},"notes":"","labels":[]}'
door clear af-parked >/dev/null || fail "clear on a parked bead should succeed"
[[ $(jq -r '.status' "$TEST_TMP/beads/af-parked.json") == open ]] \
  || fail "clear did not reopen a parked-blocked bead"
[[ $(jq -r '.metadata | has("gc.work_outcome")' "$TEST_TMP/beads/af-parked.json") == false ]] \
  || fail "clear left gc.work_outcome=blocked on the reopened bead"

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
door benjamin af-blocker "$COMPLETE_REQUEST" >/dev/null || fail "benjamin should succeed"
grep -Fq 'clear af-blocker' "$TEST_TMP/calls.log" \
  || fail "the escalation mail must name escalation-door clear <bead>"

# --- malformed / unknown bead ids are refused for every write command ------
TESTS_RUN=$((TESTS_RUN + 1))
if door benjamin 'prose, not an id' "$COMPLETE_REQUEST" >/dev/null 2>&1; then
  fail "benjamin must refuse prose in place of a bead id"
fi
TESTS_RUN=$((TESTS_RUN + 1))
if door benjamin af-does-not-exist "$COMPLETE_REQUEST" >/dev/null 2>&1; then
  fail "benjamin on an unknown bead must refuse"
fi

# --- a long-lived child of one call never blocks the next call (af-wnj692) --
# `gc mail send --notify` leaves a detached nudge poller behind. If it
# inherits the door's lock fd it holds the flock for as long as it lives and
# every later escalation fails with "Could not acquire the escalation-door
# lock." -- an escalation to the operator can be lost that way.
reset_beads
seed af-blocker '{"id":"af-blocker","status":"open","metadata":{},"notes":"","labels":[]}'
seed af-next '{"id":"af-next","status":"open","metadata":{},"notes":"","labels":[]}'
TESTS_RUN=$((TESTS_RUN + 1))
POLLER_PIDS="$TEST_TMP/poller.pids"
: >"$POLLER_PIDS"
kill_pollers() {
  local pid
  while read -r pid; do kill "$pid" 2>/dev/null || true; done <"$POLLER_PIDS"
}
trap 'kill_pollers; rm -rf -- "$TEST_TMP"' EXIT
ED_MAIL_POLLER_PID_FILE="$POLLER_PIDS" door benjamin af-blocker "$COMPLETE_REQUEST" >/dev/null \
  || fail "benjamin should succeed while its mail leaves a poller behind"
poller=$(head -n1 "$POLLER_PIDS")
[[ -n $poller ]] && kill -0 "$poller" 2>/dev/null \
  || fail "the fixture did not leave a long-lived child behind: this check would prove nothing"
for fd in /proc/"$poller"/fd/*; do
  [[ $(readlink "$fd" 2>/dev/null || true) != "$TEST_TMP/lock" ]] \
    || fail "the child left behind by benjamin inherited the door's lock fd (${fd##*/})"
done
second_err=$(door mayor af-next "second escalation" 2>&1 >/dev/null) \
  || fail "a second door call failed while the first call's child was still alive: $second_err"
kill -0 "$poller" 2>/dev/null \
  || fail "the long-lived child died before the second call: this check would prove nothing"
[[ -n $(jq -r '.metadata["gc.escalation_mayor_paged_at"] // empty' "$TEST_TMP/beads/af-next.json") ]] \
  || fail "the second door call did not record its Mayor-first page"
kill_pollers

printf 'PASS: %d deterministic escalation-door checks\n' "$TESTS_RUN"
