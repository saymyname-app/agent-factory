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
             out_of_ticket: "aucun"},
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
  version: "spec-end/v2",
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

echo "PASS: tracked elements, their repair, the red of the end with its round and the record of the end-of-Spec gate are written and read back on the real tracker"
