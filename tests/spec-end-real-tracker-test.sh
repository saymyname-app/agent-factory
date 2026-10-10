#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime and an isolated Dolt server
#
# Adoption trial of the state of the end of a Spec (T23, af-s5uysn) on the
# real tracker, in a disposable city that shares nothing with the live
# Factory: what bin/convoy-state writes for the end-of-Spec gate -- a
# Planning Exception that names tracked elements of a Ticket Handoff
# (`raise-planning-exception --item`), the repair of those elements
# (`set-item-repair`), a red that names its control and counts one round in
# the same write (`record-integration-red --check --end-round`) and the
# record of the gate (`record-spec-end`) -- is JSON in metadata values,
# written by `gc bd update --set-metadata`. The fake tracker of
# tests/convoy-state-test.py only proves the command against what this trial
# observes of the real one. No gate runs here: bin/spec-end is proven on the
# fake tracker (tests/spec-end-test.py).
#
# T24 (af-oy7v3i): the same for the Outcome Evaluation and the findings
# « hors ticket » -- the request, its launch, a classification
# (`classify-finding`), the states handed in (`record-outcome-evaluation`),
# the repair code published (`set-outcome-repair`) and a product released --
# with the user stories read in a Spec bead of the real tracker. No
# Evaluator session runs here: bin/outcome-evaluation is proven on the fake
# tracker (tests/outcome-evaluation-test.py).
#
# T26 (af-vwcflt): the same for the bound of the rounds of the end -- a
# refusal of the end once the rounds are consumed writes the red, the stop
# (`gc.flow.end_stop`) and the withdrawal of a Delivered Outcome in ONE
# `gc bd update` (set and unset together), the « non conforme » request is
# recorded on the stop (`end-stop-raised`), and `record-delivered` is
# refused under a stop. Its passage is proven on the fake tracker
# (tests/evidence-pack-test.py): it needs a whole green end of Spec.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
TOOL="$ROOT/bin/convoy-state"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

# A write that must pass: its refusal, if any, is the failure message.
state() {
  local out
  out=$("$TOOL" "$@") || fail "convoy-state $* did not pass: $out"
}

for required in gc bd jq git dolt; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

TRIAL=$(mktemp -d /tmp/af-s5uysn-spec-end.XXXXXX)
TEST_CITY="$TRIAL/city"
cleanup() {
  status=$?
  trap - EXIT
  # The city's managed Dolt server and its watchdog outlive `gc init`; their
  # command lines carry the trial directory, and nothing else does.
  pkill -f -- "$TRIAL/" >/dev/null 2>&1 || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    pgrep -f -- "$TRIAL/" >/dev/null 2>&1 || break
    sleep 0.3
  done
  pkill -9 -f -- "$TRIAL/" >/dev/null 2>&1 || true
  if [ "${KEEP_TEST_CITY:-0}" = 1 ]; then
    echo "trial preserved at $TRIAL" >&2
  else
    rm -rf -- "$TRIAL"
  fi
  exit "$status"
}
trap cleanup EXIT

# Nothing of the live Factory may reach this city: no GC_* variable (hosted
# Dolt, city path, session identity, GC_BIN), no FACTORY_ROOT and no shared HOME.
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$|FACTORY_ROOT$)' || true)
export HOME="$TRIAL/home" TMUX_TMPDIR="$TRIAL/tmux" CONVOY_STATE_LOCK_DIR="$TRIAL/locks"
# The tools name their city to gc from FACTORY_ROOT (af-2o6oyl); left unset,
# they name the repository they are run from -- the live Factory (af-xcfup7).
export FACTORY_ROOT="$TEST_CITY"
mkdir -p "$HOME" "$TMUX_TMPDIR"
dolt config --global --add user.name "spec-end trial" >/dev/null
dolt config --global --add user.email "trial@example.invalid" >/dev/null

gc init --template minimal --default-provider codex --skip-provider-readiness \
  --no-start --yes --name af-s5uysn-spec-end "$TEST_CITY" >/dev/null 2>&1 \
  || fail "gc init of the isolated city failed"
cd "$TEST_CITY"

GATE_REPORT="$ROOT/tests/fixtures/convoy-state/ticket-end-report.json"

CONVOY=$(gc bd create --title "convoi d'essai" --type convoy --silent 2>/dev/null)
T1=$(gc bd create --title "ticket d'essai" --type task --silent 2>/dev/null)
R1=$(gc bd create --title "repair d'essai" --type task --silent 2>/dev/null)
R2=$(gc bd create --title "second repair d'essai" --type task --silent 2>/dev/null)
gc bd update "$T1" --set-metadata gc.ticket_kind=prefactoring >/dev/null
for repair in "$R1" "$R2"; do
  gc bd update "$repair" --set-metadata gc.ticket_kind=repair >/dev/null
  gc bd dep add "$CONVOY" "$repair" --type tracks >/dev/null
done
gc bd dep add "$CONVOY" "$T1" --type tracks >/dev/null
state mark "$CONVOY" \
  --demonstration-line "$R1=La sonde est branchée" \
  --demonstration-line "$R2=La sonde est branchée"

BASE=0123456789abcdef0123456789abcdef01234567
TIP=89abcdef0123456789abcdef0123456789abcdef
state set-integration "$CONVOY" --branch integration/essai --protected main --base "$BASE"

item_state() {
  "$TOOL" show "$CONVOY" | jq -r --arg t "$T1" '.tickets[] | select(.id == $t) | .tracked_items[0].state'
}

# --- tracked elements of a Ticket Handoff -------------------------------------
NOT_DONE="La sonde n'est pas branchée : « a=b » reste à faire."
HANDOFF="$TRIAL/handoff.json"
jq -n --arg tip "$TIP" --arg what "$NOT_DONE" '{
  sections: {done: ["Critère 1 observé."], deviations: ["La liste est triée par nom."], not_done: [$what],
             out_of_ticket: ["Le pied de page affiche une année fausse."]},
  partial: false, commit: $tip, records: {commits: [], deferral_markers: []}}' >"$HANDOFF"
state add-evidence "$CONVOY" "$T1" --piece handoff_records \
  --digest "sha256:$(sha256sum <"$HANDOFF" | cut -d' ' -f1)" --commit "$TIP"
state set-handoff "$CONVOY" "$T1" --file "$HANDOFF"
shown=$("$TOOL" show "$CONVOY") || fail "show after the Handoff failed: $shown"
jq -e --arg t "$T1" --arg what "$NOT_DONE" '
  .unruled == false
  and ([.tickets[] | select(.id == $t) | .tracked_items[] | [.id, .text, .state, .request, .repair]]
       == [["deviations.1", "La liste est triée par nom.", "ouvert", null, null],
           ["not_done.1", $what, "ouvert", null, null]])
' <<<"$shown" >/dev/null || fail "tracked elements not read back from the real tracker: $shown"

# An element the Handoff does not carry is refused, and nothing is written.
before=$(gc bd show "$T1" --json)
set +e
out=$("$TOOL" raise-planning-exception "$CONVOY" "$T1" --kind semantic --summary "x" --item not_done.2 --accept-option b); rc=$?
set -e
[ "$rc" = 1 ] || fail "an element the Handoff does not carry exited $rc, want 1"
grep -q "ne porte pas l'élément not_done.2" <<<"$out" || fail "the refusal of an unknown element does not say why: $out"
[ "$before" = "$(gc bd show "$T1" --json)" ] || fail "a refused Planning Exception changed the tracker"

# The Planning Exception that names both elements; raised again, it writes nothing.
SUMMARY="Fin de Spec, ticket $T1, sans état final : écart 1 ; « non fait » 1 (a=b)"
state raise-planning-exception "$CONVOY" "$T1" --kind semantic --summary "$SUMMARY" \
  --item deviations.1 --item not_done.1 --accept-option b
before=$(gc bd show "$T1" --json)
state raise-planning-exception "$CONVOY" "$T1" --kind semantic --summary "$SUMMARY" \
  --item deviations.1 --item not_done.1 --accept-option b
[ "$before" = "$(gc bd show "$T1" --json)" ] || fail "the same Planning Exception raised again changed the tracker"

# Not answered: no repair is named, and the elements stay open.
set +e
out=$("$TOOL" set-item-repair "$CONVOY" "$T1" --repair "$R1"); rc=$?
set -e
[ "$rc" = 1 ] || fail "a repair named before the operator answered exited $rc, want 1"
grep -q "pas de réponse de l'opérateur" <<<"$out" || fail "the refusal of an early repair does not say why: $out"
[ "$(item_state)" = "ouvert" ] || fail "an element is not open while its request has no answer"

# What bin/escalation-door repondre writes on the ticket: the operator asks for the repair.
gc bd update "$T1" --set-metadata gc.needs_benjamin=none --set-metadata gc.escalation_response_option=a \
  --set-metadata gc.escalation_response_at=2999-01-01T00:00:00Z >/dev/null
set +e
"$TOOL" set-item-repair "$CONVOY" "$T1" --repair "$T1" >/dev/null; rc=$?
set -e
[ "$rc" = 1 ] || fail "naming a ticket that is not a repair exited $rc, want 1"
state set-item-repair "$CONVOY" "$T1" --repair "$R1"
before=$(gc bd show "$T1" --json)
set +e
out=$("$TOOL" set-item-repair "$CONVOY" "$T1" --repair "$R2"); rc=$?
set -e
[ "$rc" = 1 ] || fail "a second repair for the same request exited $rc, want 1"
grep -q "un seul repair par demande" <<<"$out" || fail "the refusal of a second repair does not say why: $out"
[ "$before" = "$(gc bd show "$T1" --json)" ] || fail "a refused second repair changed the tracker"
shown=$("$TOOL" show "$CONVOY") || fail "show after the repair was named failed: $shown"
jq -e --arg t "$T1" --arg r1 "$R1" '
  .unruled == false
  and ([.tickets[] | select(.id == $t) | .tracked_items[] | [.state, .repair, .request.state, .request.accepted]]
       == [["ouvert", $r1, "resolved", false], ["ouvert", $r1, "resolved", false]])
  and ([.tickets[] | select(.id == $t) | .planning_exceptions[-1] | [.items, .repair, .response.option]]
       == [[["deviations.1", "not_done.1"], $r1, "a"]])
' <<<"$shown" >/dev/null || fail "repair of the tracked elements not read back from the real tracker: $shown"

# The repair closed by the ticket-end gate: the elements read « réparé ».
state close-ticket "$CONVOY" "$R1" --commit "$TIP" --file "$GATE_REPORT"
[ "$(item_state)" = "réparé" ] || fail "an element is not « réparé » once the gate closed its repair: $(item_state)"

# --- a red of the end of the Spec: its control named, one round in the same write ---
CONTROL="fidélité mécanique au Validated Prototype : écart(s) ouvert(s) sur integration/essai à ${TIP:0:12}"
DETAIL="1 écart(s) ouvert(s) : empty/fixture-items/presence (missing) ; comparé : 4 ancre(s) de 2 état(s)"
state record-integration-red "$CONVOY" --commit "$TIP" --integration "$TIP" --protected "$BASE" \
  --control "$CONTROL" --detail "$DETAIL" --check fidelity --end-round
shown=$("$TOOL" show "$CONVOY") || fail "show after the red of the end failed: $shown"
jq -e --arg control "$CONTROL" --arg detail "$DETAIL" --arg tip "$TIP" --arg base "$BASE" '
  .unruled == false
  and (.convoy.integration_red | del(.at))
      == {control: $control, commit: $tip, integration: $tip, protected: $base, detail: $detail, check: "fidelity"}
  and .convoy.counters.end_rounds == 1
' <<<"$shown" >/dev/null || fail "red of the end of the Spec not read back from the real tracker: $shown"
# The same red again: nothing written, nothing counted.
before=$(gc bd show "$CONVOY" --json)
state record-integration-red "$CONVOY" --commit "$TIP" --integration "$TIP" --protected "$BASE" \
  --control "$CONTROL" --detail "$DETAIL" --check fidelity --end-round
[ "$before" = "$(gc bd show "$CONVOY" --json)" ] || fail "the same red of the end recorded again changed the tracker"

# --- the record of the gate ---------------------------------------------------
REPORT="$TRIAL/spec-end.json"
COMMAND="sh -c 'test ! -e rouge' --seuil=1"
jq -n --arg tip "$TIP" --arg command "$COMMAND" '{
  version: "spec-end/v4",
  conditions: [
    {number: 1, name: "registry", verdict: "pass", detail: "2 ticket(s) fermé(s) par la porte ; 2 écart(s) et « non fait(s) » dans un état final (0 accepté par Benjamin, 2 réparé)"},
    {number: 2, name: "tests", verdict: "pass", detail: "commande de régression (\($command)) : code 0"},
    {number: 3, name: "fidelity", verdict: "pass", detail: "aucun écart ouvert sur 4 ancre(s) de 2 état(s) prototypé(s) (content, empty) sur accueil"}],
  records: {tests: {command: $command, exit_code: 0, commit: $tip},
            fidelity: {commit: $tip, prototypes: []}}}' >"$REPORT"
record_spec_end() {
  "$TOOL" record-spec-end "$CONVOY" --commit "$TIP" --protected "$BASE" --file "${1:-$REPORT}"
}
# Refused under a red, with a ticket left open, and for a list that is not the known one.
set +e
out=$(record_spec_end); rc=$?
set -e
[ "$rc" = 1 ] || fail "a record of the gate under a red exited $rc, want 1"
grep -q "est rouge" <<<"$out" || fail "the refusal under a red does not say why: $out"
state clear-integration-red "$CONVOY"
set +e
out=$(record_spec_end); rc=$?
set -e
[ "$rc" = 1 ] || fail "a record of the gate with a ticket left open exited $rc, want 1"
grep -q "$T1" <<<"$out" || fail "the refusal does not name the ticket left open: $out"
state close-ticket "$CONVOY" "$T1" --commit "$TIP" --file "$GATE_REPORT"
state close-ticket "$CONVOY" "$R2" --commit "$TIP" --file "$GATE_REPORT"
before=$(gc bd show "$CONVOY" --json)
jq '.version = "spec-end/v0"' "$REPORT" >"$TRIAL/spec-end-v0.json"
set +e
record_spec_end "$TRIAL/spec-end-v0.json" >/dev/null; rc=$?
set -e
[ "$rc" = 1 ] || fail "a record of an unknown version exited $rc, want 1"
[ "$before" = "$(gc bd show "$CONVOY" --json)" ] || fail "a refused record of the gate changed the tracker"

out=$(record_spec_end) || fail "record-spec-end did not pass: $out"
shown=$("$TOOL" show "$CONVOY") || fail "show after the record of the gate failed: $shown"
jq -e --arg tip "$TIP" --arg base "$BASE" --slurpfile report "$REPORT" '
  .unruled == false
  and (.convoy.spec_end | del(.at))
      == ($report[0] + {commit: $tip, protected: $base})
  and .convoy.counters.end_rounds == 1
' <<<"$shown" >/dev/null || fail "record of the end-of-Spec gate not read back from the real tracker: $shown"

# --- the Outcome Evaluation and the findings « hors ticket » (T24, af-oy7v3i) ---
# The Spec of the convoy is a bead of the real tracker: its numbered user
# stories are read there, by the reader bin/spec-approve holds a Spec to.
SPEC=$(gc bd create --title "Spec d'essai" --type task --body-file "$ROOT/tests/fixtures/delivery-fixture-city/spec.md" --silent 2>/dev/null)
gc bd update "$CONVOY" --set-metadata "gc.spec_id=$SPEC" >/dev/null
finding_state() {
  "$TOOL" show "$CONVOY" | jq -r --arg t "$T1" '.tickets[] | select(.id == $t) | .findings[0].state'
}
classify() {
  "$TOOL" classify-finding "$CONVOY" "$T1" --item out_of_ticket.1 --recorded-by essai-evaluator "$@"
}
draft() {  # draft STORY -> a drafted repair that cites that user story
  jq -n --arg story "$1" '{
    title: "Rétablir la user story \($story)", what_it_delivers: "Le produit assemblé sert la user story \($story).",
    restores: {kind: "user_story", ref: "user story \($story)"},
    demonstration_line: "Sur le produit lancé, la user story \($story) est servie.",
    acceptance_criteria: [{entry_point: "GET / sur le produit lancé", observable: "la story y est servie",
                           false_if: "la story n'\''y est pas servie"}]}'
}
[ "$(finding_state)" = "non classé" ] || fail "a finding nobody classified does not read « non classé »: $(finding_state)"

# No evaluation open: nothing is classified, nothing is written.
before=$(gc bd show "$T1" --json)
set +e
out=$(classify --as proposal); rc=$?
set -e
[ "$rc" = 1 ] || fail "a finding classified outside an Outcome Evaluation exited $rc, want 1"
grep -q "aucune Outcome Evaluation n'est ouverte" <<<"$out" || fail "the refusal outside an evaluation does not say why: $out"
[ "$before" = "$(gc bd show "$T1" --json)" ] || fail "a refused classification changed the tracker"

# The evaluation opens at the commit of the gate only; opened again, it writes nothing.
REQUEST="$TRIAL/outcome-request.json"
LAUNCH="$TRIAL/launch.json"
jq -n --arg launch "$LAUNCH" '{
  roles: {authors: [], evaluator: null, same_provider: null, other_declared: []},
  environment: [{dataset: null, address: "http://127.0.0.1:18080", state_file: $launch}]}' >"$REQUEST"
before=$(gc bd show "$CONVOY" --json)
set +e
out=$("$TOOL" open-outcome-evaluation "$CONVOY" --commit "$BASE" --file "$REQUEST"); rc=$?
set -e
[ "$rc" = 1 ] || fail "an Outcome Evaluation opened off the commit of the gate exited $rc, want 1"
grep -q "porte sur le commit de la porte" <<<"$out" || fail "the refusal off the commit of the gate does not say why: $out"
[ "$before" = "$(gc bd show "$CONVOY" --json)" ] || fail "a refused opening changed the tracker"
state open-outcome-evaluation "$CONVOY" --commit "$TIP" --file "$REQUEST"
before=$(gc bd show "$CONVOY" --json)
state open-outcome-evaluation "$CONVOY" --commit "$TIP" --file "$REQUEST"
[ "$before" = "$(gc bd show "$CONVOY" --json)" ] || fail "the same Outcome Evaluation opened again changed the tracker"
state launch-outcome-evaluation "$CONVOY" --bead "$SPEC"
# The stories of the request are those the Spec bead numbers, read on the real tracker.
STORIES=$(gc bd show "$CONVOY" --json | jq -c '.[0].metadata["gc.flow.outcome_evaluation"] | fromjson | .request.stories')
[ "$(jq -c 'map(.number)' <<<"$STORIES")" = "[1,2,3]" ] || fail "the stories of the Spec bead are not those of the request: $STORIES"

# « dismissed » without a reason, « repaired » without what it restores, and
# a citation of a story the Spec does not number: refused, nothing written.
before=$(gc bd show "$T1" --json)
set +e
out=$(classify --as dismissed); rc=$?
set -e
[ "$rc" = 1 ] || fail "« dismissed » without a reason exited $rc, want 1"
grep -q "écarté sans raison" <<<"$out" || fail "the refusal of « dismissed » without a reason does not say why: $out"
set +e
out=$(classify --as repaired); rc=$?
set -e
[ "$rc" = 1 ] || fail "« repaired » without a citation exited $rc, want 1"
grep -q "sans citation de ce qu'il rétablit" <<<"$out" || fail "the refusal of « repaired » without a citation does not say why: $out"
draft 9 >"$TRIAL/draft-9.json"
set +e
out=$(classify --as repaired --file "$TRIAL/draft-9.json"); rc=$?
set -e
[ "$rc" = 1 ] || fail "« repaired » citing a story the Spec does not number exited $rc, want 1"
grep -q "cite une user story absente de la Spec $SPEC" <<<"$out" || fail "the refusal of an unknown story does not say why: $out"
[ "$before" = "$(gc bd show "$T1" --json)" ] || fail "a refused classification changed the tracker"
draft 2 >"$TRIAL/draft-2.json"
state classify-finding "$CONVOY" "$T1" --item out_of_ticket.1 --recorded-by essai-evaluator --as repaired --file "$TRIAL/draft-2.json"
[ "$(finding_state)" = "à réparer" ] || fail "a finding classified « repaired » does not read « à réparer »: $(finding_state)"

# One state per story, each with a piece captured under the convoy at the commit of the gate.
for number in 1 2 3; do
  state add-evidence "$CONVOY" "$CONVOY" --piece "outcome.s$number" \
    --digest "sha256:$(printf 'story %s' "$number" | sha256sum | cut -d' ' -f1)" --commit "$TIP"
done
handed() {  # handed FILTER -> what the Evaluator hands in, the stories filtered
  jq -n --arg tip "$TIP" --argjson stories "$STORIES" --slurpfile repair <(draft 3) '{
    commit: $tip, recorded_by: "essai-evaluator", exploration: "aucun", fidelity_deviations: "aucun",
    stories: [$stories[] | . + {evidence: "outcome.s\(.number)"}
              + (if .number == 3 then {state: "not_observed", reason: "La sonde ne répond pas."} else {state: "observed"} end)],
    repairs: [$repair[0] + {story: 3}]}' | jq "$1"
}
before=$(gc bd show "$CONVOY" --json)
handed '.stories |= map(select(.number != 2))' >"$TRIAL/outcome-short.json"
set +e
out=$("$TOOL" record-outcome-evaluation "$CONVOY" --file "$TRIAL/outcome-short.json"); rc=$?
set -e
[ "$rc" = 1 ] || fail "an Outcome Evaluation with a story left without state exited $rc, want 1"
grep -q "user story 2 sans état" <<<"$out" || fail "the refusal does not name the story left without state: $out"
handed '. + {verdict: "favorable"}' >"$TRIAL/outcome-verdict.json"
set +e
out=$("$TOOL" record-outcome-evaluation "$CONVOY" --file "$TRIAL/outcome-verdict.json"); rc=$?
set -e
[ "$rc" = 1 ] || fail "an Outcome Evaluation that hands in its verdict exited $rc, want 1"
grep -q "le verdict est calculé par du code" <<<"$out" || fail "the refusal of a handed-in verdict does not say why: $out"
[ "$before" = "$(gc bd show "$CONVOY" --json)" ] || fail "a refused Outcome Evaluation changed the tracker"
handed . >"$TRIAL/outcome.json"
out=$("$TOOL" record-outcome-evaluation "$CONVOY" --file "$TRIAL/outcome.json") || fail "record-outcome-evaluation did not pass: $out"
jq -e '.outcome == "repair" and .verdict == "unfavorable"' <<<"$out" >/dev/null || fail "the computed verdict is not « repair »: $out"

# What code published is named once: on the story, and on the finding, which
# reads « réparé » since the ticket-end gate closed that repair.
state set-outcome-repair "$CONVOY" --repair "$R2" --story 3
state set-outcome-repair "$CONVOY" --repair "$R1" --ticket "$T1" --item out_of_ticket.1
before=$(gc bd show "$CONVOY" --json)$(gc bd show "$T1" --json)
state set-outcome-repair "$CONVOY" --repair "$R2" --story 3
state set-outcome-repair "$CONVOY" --repair "$R1" --ticket "$T1" --item out_of_ticket.1
[ "$before" = "$(gc bd show "$CONVOY" --json)$(gc bd show "$T1" --json)" ] || fail "a repair named again changed the tracker"
set +e
out=$("$TOOL" set-outcome-repair "$CONVOY" --repair "$R1" --story 3); rc=$?
set -e
[ "$rc" = 1 ] || fail "a second repair for the same story exited $rc, want 1"
grep -q "un seul repair par élément" <<<"$out" || fail "the refusal of a second repair of a story does not say why: $out"
state release-outcome-evaluation "$CONVOY" --state-file "$LAUNCH"
shown=$("$TOOL" show "$CONVOY") || fail "show after the Outcome Evaluation failed: $shown"
jq -e --arg t "$T1" --arg tip "$TIP" --arg r1 "$R1" --arg r2 "$R2" '
  .unruled == false
  and (.convoy.outcome_evaluation.state
       == {verdict: "unfavorable", outcome: "repair", commit: $tip, not_observed: [3], unobservable: [],
           repairs: [{story: 3, repair: $r2}], contradictions: []})
  and ([.tickets[] | select(.id == $t) | .findings[] | [.id, .state, .classification, .repair]]
       == [["\($t):out_of_ticket.1", "réparé", "repaired", $r1]])
' <<<"$shown" >/dev/null || fail "Outcome Evaluation and findings not read back from the real tracker: $shown"

# --- the bound of the rounds of the end, its stop, Delivered withdrawn (T26, af-vwcflt) ---
# A Delivered Outcome on the convoy (a false state, of the shape its command
# writes): what the next refusal of the end must withdraw.
TIP2=fedcba9876543210fedcba9876543210fedcba98
PACK_DIGEST="sha256:$(printf 'dossier' | sha256sum | cut -d' ' -f1)"
gc bd update "$CONVOY" --set-metadata "gc.flow.delivered=$(jq -nc --arg tip "$TIP" --arg base "$BASE" --arg pack "$PACK_DIGEST" \
  '{commit: $tip, protected: $base, pack: $pack, version: "spec-end/v4", at: "2026-10-08T10:00:00Z"}')" >/dev/null
shown=$("$TOOL" show "$CONVOY") || fail "show with a Delivered Outcome failed: $shown"
jq -e --arg tip "$TIP" '.unruled == false and .convoy.delivered.commit == $tip and .convoy.end_stop == null' <<<"$shown" >/dev/null \
  || fail "Delivered Outcome not read back from the real tracker: $shown"

# The two rounds consumed, then the tip refused once more: no third round.
state set-counter "$CONVOY" --counter end_rounds --value 2
CONTROL2="fidélité mécanique au Validated Prototype : écart(s) ouvert(s) sur integration/essai à ${TIP2:0:12}"
state record-integration-red "$CONVOY" --commit "$TIP2" --integration "$TIP2" --protected "$BASE" \
  --control "$CONTROL2" --detail "$DETAIL" --check fidelity --end-round
shown=$("$TOOL" show "$CONVOY") || fail "show after the stop of the rounds failed: $shown"
jq -e --arg tip "$TIP2" '
  .unruled == false
  and .convoy.integration_red.commit == $tip
  and ([.convoy.end_stop | .reason, .commit, .source, .rounds] == ["end_rounds_exhausted", $tip, "fidelity", 2])
  and (.convoy.end_stop | has("request") | not)
  and .convoy.counters.end_rounds == 2
  and .convoy.delivered == null
' <<<"$shown" >/dev/null || fail "red, stop of the rounds and Delivered withdrawn not read back from the real tracker: $shown"
gc bd show "$CONVOY" --json | jq -e '(if type == "array" then .[0] else . end).metadata | has("gc.flow.delivered") | not' >/dev/null \
  || fail "the refusal of the end left gc.flow.delivered on the real tracker"
# The same red again, and one more refusal: nothing written on a stopped convoy.
before=$(gc bd show "$CONVOY" --json)
state record-integration-red "$CONVOY" --commit "$TIP2" --integration "$TIP2" --protected "$BASE" \
  --control "$CONTROL2" --detail "$DETAIL" --check fidelity --end-round
[ "$before" = "$(gc bd show "$CONVOY" --json)" ] || fail "the same red on a stopped convoy changed the tracker"

# The « non conforme » request: refused before its dossier, recorded once.
set +e
out=$("$TOOL" end-stop-raised "$CONVOY" --bead "$CONVOY"); rc=$?
set -e
[ "$rc" = 1 ] || fail "a « non conforme » request without its Evidence Pack exited $rc, want 1"
grep -q "aucun Evidence Pack" <<<"$out" || fail "the refusal of a request without its dossier does not say why: $out"
[ "$before" = "$(gc bd show "$CONVOY" --json)" ] || fail "a refused « non conforme » request changed the tracker"
PACK_DIR="$TRIAL/packs/essai/$CONVOY/$TIP2"
state record-evidence-pack "$CONVOY" --commit "$TIP2" --digest "$PACK_DIGEST" --path "$PACK_DIR" --non-conforming --inadmissible 0
state end-stop-raised "$CONVOY" --bead "$CONVOY"
shown=$("$TOOL" show "$CONVOY") || fail "show after the « non conforme » request failed: $shown"
jq -e --arg convoy "$CONVOY" --arg tip "$TIP2" --arg pack "$PACK_DIGEST" --arg page "$PACK_DIR/index.html" '
  .unruled == false
  and (.convoy.end_stop.request | del(.at)) == {bead: $convoy, commit: $tip, digest: $pack, page: $page}
' <<<"$shown" >/dev/null || fail "« non conforme » request not read back from the real tracker: $shown"
before=$(gc bd show "$CONVOY" --json)
state end-stop-raised "$CONVOY" --bead "$CONVOY"
[ "$before" = "$(gc bd show "$CONVOY" --json)" ] || fail "the same « non conforme » request recorded again changed the tracker"

# Never Delivered under a stop.
set +e
out=$("$TOOL" record-delivered "$CONVOY" --commit "$TIP2" --pack-digest "$PACK_DIGEST"); rc=$?
set -e
[ "$rc" = 1 ] || fail "a Delivered Outcome under a stop of the rounds exited $rc, want 1"
grep -q "tours de réparation de fin arrêtés" <<<"$out" || fail "the refusal of Delivered under a stop does not say why: $out"
[ "$before" = "$(gc bd show "$CONVOY" --json)" ] || fail "a refused Delivered Outcome changed the tracker"

echo "PASS: tracked elements, their repair, the red of the end with its round, the record of the end-of-Spec gate, the Outcome Evaluation and the classified findings, the stop of the rounds of the end with its « non conforme » request and the withdrawal of Delivered are written and read back on the real tracker"
