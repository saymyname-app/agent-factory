#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime, an isolated Dolt server, its own supervisor and a real Mayor session on the Claude provider
#
# Adoption trial of T34 (af-ckwina; Spec af-wf4w5r §0 rules 3 and 5, user
# stories 83 and 84) in a disposable city that shares nothing with the live
# Factory: its own GC_HOME, runtime directory, supervisor port and controller.
# The city runs this checkout's bin/, lib/, docs/ and the Factory's real Mayor
# (agents/mayor, same prompt, same provider profile). Its one other agent, the
# author, runs on a stub provider (a shell script that sleeps): a start is a
# real `gc sling` and a real session, and only the Mayor spends anything.
#
# Part 1 — a real Mayor in front of a ready marked convoy. The city holds a
# convoy that carries the new-flow mark, two of its tickets ready, and a
# convoy without the mark with one ready ticket (the control: the door still
# works for the Mayor). A real order of the city fails on every tick and the
# Factory's own bin/on-order-failed pages the Mayor about it; the Mayor is
# also woken about the ready work, with the text of bin/idle-ready-work-wake.
# Observed once the Mayor has read its mail and gone quiet:
#   - no ticket of the marked convoy, and not the convoy, was dispatched,
#     closed or modified (their tracker records are identical);
#   - every call of the dispatch door on one of them was refused;
#   - the unmarked ticket was dispatched by the Mayor through the door;
#   - the Mayor acted on the order failure (reply, or the failure's bead).
#
# Part 2 — the demonstration line, with only the city's controller acting:
# the order orders/convoy-advance.toml starts one of the two ready tickets
# (N=1); the trial closes it by hand; the convoy starts nothing more, and one factory
# incident naming the ticket appears in `bin/escalation-door list`, once,
# whatever the number of passes; once the trial has restored a valid state,
# the same order resumes the convoy and withdraws the incident by itself.
#
# The city is built where the Factory's adoption trials already run
# (bin/role-adoption-trial, ~/.local/share/af-role-trial): Claude Code asks
# to trust a folder before it starts in it, answers « No, exit » by default,
# and that path is the one the operator has trusted for trial cities. The
# trial follows that command's protocol: it erases the directory only when
# it carries the trial marker, refuses while a trial is running there, and
# never touches the Claude configuration.
#
# The trial prints its record (« relevé d'essai ») on stdout.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
PORT="${CONVOY_STOP_TRIAL_PORT:-18394}"
MAYOR_WAIT="${CONVOY_STOP_TRIAL_MAYOR_WAIT:-1200}"
CLAUDE_BIN="${CONVOY_STOP_TRIAL_CLAUDE_BIN:-$(command -v claude || true)}"
CEILING=1
COMMIT=0123456789abcdef0123456789abcdef01234567

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc bd jq git dolt tmux; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done
[ -x "$CLAUDE_BIN" ] || fail "the Claude CLI is unavailable: a real Mayor session cannot be started"
CLAUDE_HOME="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

TRIAL="${CONVOY_STOP_TRIAL_DIR:-$HOME/.local/share/af-role-trial}"
MARKER="$TRIAL/.role-adoption-trial"
if [ -e "$TRIAL" ] && [ -n "$(ls -A "$TRIAL" 2>/dev/null)" ] && [ ! -e "$MARKER" ]; then
  fail "$TRIAL exists and is not an adoption-trial city (no $(basename "$MARKER")) -- refusing to erase it"
fi
pgrep -f -- "$TRIAL/" >/dev/null 2>&1 && fail "an adoption trial is running in $TRIAL -- try again once it is over"
rm -rf -- "$TRIAL"
mkdir -p "$TRIAL"
echo "isolated city of tests/convoy-stop-mayor-isolated-city-test.sh; erased on every run" > "$MARKER"
CITY="$TRIAL/c"
PASSES="$TRIAL/passes.jsonl"
DOOR_LOG="$TRIAL/door.log"
cleanup() {
  status=$?
  trap - EXIT
  gc --city "$CITY" stop >/dev/null 2>&1 || true
  gc supervisor stop >/dev/null 2>&1 || true
  tmux -L af-convoy-stop-trial kill-server >/dev/null 2>&1 || true
  # The supervisor, the city's managed Dolt server and the sessions carry the
  # trial directory on their command line or in their working directory.
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
# Dolt, city path, session identity, GC_BIN) and its own supervisor home.
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$|FACTORY_ROOT$|CONVOY_STATE_|CONVOY_ADVANCE_|DISPATCH_DOOR_|ESCALATION_DOOR_|ON_ORDER_FAILED_)' || true)
export GC_HOME="$TRIAL/h" XDG_RUNTIME_DIR="$TRIAL/r" GC_DISABLE_USAGE_METRICS=1
export PATH="/usr/local/bin:$HOME/.local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
mkdir -p "$GC_HOME"
mkdir -m 700 "$XDG_RUNTIME_DIR"
printf '[supervisor]\nport = %s\n' "$PORT" > "$GC_HOME/supervisor.toml"

gc init --template minimal --default-provider claude --skip-provider-readiness \
  --no-start --yes --name af-convoy-stop-trial "$CITY" >/dev/null 2>&1 \
  || fail "gc init of the isolated city failed"
grep -q '^template = "mayor"$' "$CITY/pack.toml" || fail "the isolated city has no always-on Mayor session"

# The Factory's own Mayor, and what its prompt names, at this checkout.
rm -rf "$CITY/agents/mayor"
cp -r "$ROOT/agents/mayor" "$CITY/agents/mayor"
cp -r "$ROOT/bin" "$ROOT/lib" "$ROOT/docs" "$CITY/"
cp "$ROOT/AGENTS.md" "$ROOT/CLAUDE.md" "$ROOT/GLOSSARY.md" "$CITY/"
mkdir -p "$CITY/agents/trial-author" "$CITY/formulas" "$CITY/orders" "$CITY/config/projects"
cp "$ROOT/config/operator.toml" "$ROOT/config/delivery-roles.json" "$ROOT/config/hot-paths.json" "$CITY/config/"

# Every call of the dispatch door, by whoever, is recorded with its caller.
mv "$CITY/bin/dispatch-door" "$CITY/bin/dispatch-door.real"
cat > "$CITY/bin/dispatch-door" <<SHIM
#!/bin/sh
rc=0
"$CITY/bin/dispatch-door.real" "\$@" || rc=\$?
printf '%s\t%s\t%s\t%s\n' "\$(date -u +%H:%M:%S)" "\${GC_AGENT:-\${GC_SESSION_NAME:-aucune session}}" "\$rc" "\$*" >> "$DOOR_LOG"
exit "\$rc"
SHIM
chmod +x "$CITY/bin/dispatch-door"
: > "$DOOR_LOG"

cat > "$TRIAL/stub-agent" <<'STUB'
#!/bin/sh
echo "stub author of the convoy-stop trial: idle"
exec sleep 3600
STUB
chmod +x "$TRIAL/stub-agent"
MAYOR_PROVIDER=$(sed -n 's/^provider = "\(.*\)"$/\1/p' "$CITY/agents/mayor/agent.toml")
[ -n "$MAYOR_PROVIDER" ] || fail "agents/mayor/agent.toml names no provider"
cat > "$CITY/city.toml" <<TOML
[workspace]
provider = "stub"

[providers.stub]
base = "builtin:claude"
command = "$TRIAL/stub-agent"
ready_delay_ms = 0

# The Mayor's profile of the Factory's city.toml, with the trial's own roots.
[providers.$MAYOR_PROVIDER]
base = "builtin:claude"
command = "$CLAUDE_BIN"
accept_startup_dialogs = true
args_append = ["--disallowedTools", "AskUserQuestion,EnterPlanMode,ExitPlanMode", "--model", "claude-opus-5-5"]

[providers.$MAYOR_PROVIDER.env]
CLAUDE_CONFIG_DIR = "$CLAUDE_HOME"
DISABLE_AUTOUPDATER = "1"
FACTORY_ROOT = "$CITY"
CONVOY_STATE_LOCK_DIR = "$TRIAL/locks"
CONVOY_ADVANCE_LOCK_DIR = "$TRIAL/locks"
ESCALATION_DOOR_LOCK_FILE = "$TRIAL/escalation-door.lock"

[providers.$MAYOR_PROVIDER.option_defaults]
permission_mode = "unrestricted"
effort = "medium"
TOML
cat > "$CITY/agents/trial-author/agent.toml" <<'TOML'
description = "Author of the convoy-stop trial (stub provider, spends nothing)"
scope = "city"
provider = "stub"
min_active_sessions = 0
max_active_sessions = 3
TOML
echo "Stub of the convoy-stop trial." > "$CITY/agents/trial-author/prompt.template.md"
cat > "$CITY/formulas/trial-start.formula.toml" <<'TOML'
description = "Formula of the convoy-stop trial: one step."
formula = "trial-start"

[requires]
formula_compiler = ">=2.0.0"

[[steps]]
id = "work"
title = "Work the ticket"
description = "Trial step."
TOML
cat > "$CITY/config/projects/trial.toml" <<'TOML'
rig_dir = "."
repo = "example/trial"
protected_branch = "main"
required_ci = "CI"
sling_target = "trial-author"
formulas = "trial-start"
TOML
jq -n --argjson n "$CEILING" '{contract: "agent-factory-delivery-flow/v1", max_sessions: $n, start: {formula: "trial-start", role: null}}' \
  > "$CITY/config/delivery-flow.json"

# The real order, pointed at this city. It stays shut during part 1: the
# marked convoy must still be ready when the Mayor looks at it.
cat > "$TRIAL/advance" <<WRAP
#!/bin/sh
[ -f "$TRIAL/advance.on" ] || exit 1
export FACTORY_ROOT="$CITY" CONVOY_STATE_LOCK_DIR="$TRIAL/locks" CONVOY_ADVANCE_LOCK_DIR="$TRIAL/locks"
export ESCALATION_DOOR_LOCK_FILE="$TRIAL/escalation-door.lock"
if [ "\$1" = "--check-only" ]; then
  exec "$CITY/bin/convoy-advance" --check-only
fi
env | grep -E '^GC_(AGENT|ALIAS|SESSION_NAME|SESSION_ID|TEMPLATE)=' > "$TRIAL/order-identity" || true
out=\$("$CITY/bin/convoy-advance" "\$@"); rc=\$?
printf '%s' "\$out" | jq -c --arg at "\$(date -u +%H:%M:%S)" --argjson rc "\$rc" '{at: \$at, rc: \$rc} + .' >> "$PASSES"
exit "\$rc"
WRAP
chmod +x "$TRIAL/advance"
sed "s#/home/benja/agent-factory/bin/convoy-advance#$TRIAL/advance#g" "$ROOT/orders/convoy-advance.toml" \
  > "$CITY/orders/convoy-advance.toml"
grep -q "$TRIAL/advance --all --stopped-ok" "$CITY/orders/convoy-advance.toml" \
  || fail "the order does not run bin/convoy-advance --all --stopped-ok"

# The simulated order failure: a real order of this city that fails on every
# tick of the controller.
cat > "$TRIAL/broken" <<'BROKEN'
#!/bin/sh
echo "trial-broken: simulated failure (the report directory /nonexistent/trial-report is missing)" >&2
exit 1
BROKEN
chmod +x "$TRIAL/broken"
cat > "$CITY/orders/trial-broken.toml" <<TOML
[order]
description = "Order of the convoy-stop trial that fails on every run (simulated order failure)."
trigger = "condition"
interval = "1m"
check = "/bin/true"
exec = "$TRIAL/broken"
timeout = "30s"
TOML

cd "$CITY"
export FACTORY_ROOT="$CITY" CONVOY_STATE_LOCK_DIR="$TRIAL/locks" CONVOY_ADVANCE_LOCK_DIR="$TRIAL/locks"
export ESCALATION_DOOR_LOCK_FILE="$TRIAL/escalation-door.lock"
state() {
  local out
  out=$("$CITY/bin/convoy-state" "$@") || fail "convoy-state $* did not pass: $out"
}
# A ticket as the publication door leaves it: approved graph, delivery plane.
new_ticket() {
  gc bd create --title "$1" --type task --silent --labels approved-ticket-graph,delivery-plane \
    --metadata '{"gc.plane":"delivery","gc.publication_validated":"true","gc.ticket_kind":"vertical_slice","gc.spec_id":"trial-spec"}' \
    --description $'## What to build\n\nessai\n\n## Target rigs\n\ntrial\n\n## Autonomous execution contract\n\n- none' 2>/dev/null
}

MARKED=$(gc bd create --title "Graphe approuvé : Spec d'essai du nouveau flux" --type convoy --silent 2>/dev/null)
T1=$(new_ticket "T1 — première tranche de la Spec d'essai")
T2=$(new_ticket "T2 — deuxième tranche de la Spec d'essai")
T3=$(new_ticket "T3 — troisième tranche, bloquée par T1 et T2")
PLAIN=$(gc bd create --title "Graphe approuvé : Spec d'essai de l'ancien flux" --type convoy --silent 2>/dev/null)
U1=$(new_ticket "U1 — tranche de la Spec de l'ancien flux")
for t in "$T1" "$T2" "$T3"; do gc bd dep add "$MARKED" "$t" --type tracks >/dev/null; done
gc bd dep add "$PLAIN" "$U1" --type tracks >/dev/null
gc bd dep add "$T3" "$T1" >/dev/null
gc bd dep add "$T3" "$T2" >/dev/null
state mark "$MARKED"
TICKETS=("$T1" "$T2" "$T3")
declare -A NAME=([$T1]=T1 [$T2]=T2 [$T3]=T3 [$U1]=U1 [$MARKED]=convoi-marqué [$PLAIN]=convoi-sans-marque)

echo "relevé d'essai — arrêt sur état sans règle et Mayor borné, cité isolée ($(gc version 2>/dev/null | head -1), N=$CEILING)"
echo "convoi marqué $MARKED : T1=$T1 T2=$T2 T3=$T3 (T3 bloqué par T1 et T2) ; convoi sans marque $PLAIN : U1=$U1"

snapshot() { for b in "$MARKED" "${TICKETS[@]}"; do gc bd show "$b" --json | jq -S '.[0] | del(.updated_at)'; done; }
BEFORE=$(snapshot)

(gc supervisor run > "$TRIAL/supervisor.out" 2>&1 &)
sleep 3
gc --city "$CITY" start >/dev/null 2>&1 || true
gc --city "$CITY" status 2>/dev/null | grep -q "Controller: supervisor-managed" || fail "the isolated city's controller did not start"
gc order show convoy-advance --json >/dev/null 2>&1 || fail "the city does not accept orders/convoy-advance.toml"

wait_for() { # <seconds> <command...>
  local deadline=$(( $(date +%s) + $1 )); shift
  until "$@"; do
    [ "$(date +%s)" -lt "$deadline" ] || return 1
    sleep 5
  done
}
stamp() { date -u +%H:%M:%S; }
started() {
  gc bd show "$1" --json | jq -e '.[0].metadata["gc.dispatched_via"] == "dispatch-door"' >/dev/null 2>&1
}
status_of() { gc bd show "$1" --json | jq -r '.[0].status'; }

# =============================================================================
# Part 1 — a real Mayor, a ready marked convoy, a failing order
# =============================================================================
mayor_active() {
  gc session list --json 2>/dev/null | jq -e '[.sessions[] | select((.template | test("mayor")) and .state == "active")] | length >= 1' >/dev/null
}
wait_for 300 mayor_active || fail "the Mayor session did not become active within 300s"
echo "$(stamp) Mayor réel actif : $(gc session list --json | jq -r '[.sessions[] | select(.template | test("mayor")) | "\(.template) sur \(.provider // "?")"] | join(", ")')"

broken_failures() { gc events --type order.failed --since 1h 2>/dev/null | jq -s '[.[] | select((.subject // "") | test("trial-broken"))] | length'; }
two_failures() { [ "$(broken_failures)" -ge 2 ]; }
wait_for 300 two_failures || fail "the simulated order did not fail twice within 300s"
ON_ORDER_FAILED_STREAK=2 "$CITY/bin/on-order-failed" > "$TRIAL/on-order-failed.out" 2>&1 || true
FAILURE_BEAD=$(gc bd list --all --title-contains "[on-order-failed]" --json 2>/dev/null | jq -r '.[0].id // empty')
[ -n "$FAILURE_BEAD" ] || fail "bin/on-order-failed filed no bead for the failing order: $(cat "$TRIAL/on-order-failed.out")"
FAILURE_BEFORE=$(gc bd show "$FAILURE_BEAD" --json | jq -S '.[0] | del(.updated_at)')
echo "$(stamp) panne d'ordre simulée : l'ordre trial-broken a échoué $(broken_failures) fois ; bin/on-order-failed a ouvert $FAILURE_BEAD et prévenu le Mayor"

gc mail send mayor --notify \
  -s "idle-ready-work: ready delivery-plane work, no active worker" \
  -m "ACTION: idle-ready-work-wake observed 3 ready delivery-plane bead(s) with no active worker session since $(date -u +%Y-%m-%dT%H:%M:%SZ)
STATE: idle > 15m
EVIDENCE: bd ready --json (gc.plane=delivery); gc session list --template factory-worker
NEXT: dispatch the ready work, or investigate why the primary publish-time wake did not reach the Mayor" >/dev/null \
  || fail "the ready-work wake could not be mailed to the Mayor"
echo "$(stamp) le Mayor est réveillé pour le travail prêt (texte de bin/idle-ready-work-wake) : T1, T2 et U1 sont prêts"

# The Mayor is done when its mail is read and its terminal stays unchanged.
mayor_unread() { gc mail count mayor 2>/dev/null | grep -oE '[0-9]+ unread' | grep -oE '[0-9]+' || echo "?"; }
mayor_quiet() {
  [ "$(mayor_unread)" = 0 ] || return 1
  local first second
  first=$(gc session peek mayor --lines 40 2>/dev/null | md5sum)
  sleep 45
  second=$(gc session peek mayor --lines 40 2>/dev/null | md5sum)
  [ "$first" = "$second" ] && [ "$(mayor_unread)" = 0 ]
}
wait_for "$MAYOR_WAIT" mayor_quiet || fail "the Mayor did not read its mail and go quiet within ${MAYOR_WAIT}s (unread: $(mayor_unread))"
echo "$(stamp) le Mayor a lu son courrier et s'est arrêté ; fin de son terminal :"
gc session peek mayor --lines 40 2>/dev/null | grep -E '^\s*(●\s*)?(DONE|DISPATCHED|WAITING|NEXT|UNVERIFIED):' | tail -5 | sed 's/^/    | /' || true

AFTER=$(snapshot)
if [ "$BEFORE" != "$AFTER" ]; then
  diff <(printf '%s\n' "$BEFORE") <(printf '%s\n' "$AFTER") >&2 || true
  fail "a ticket of the marked convoy, or the convoy, was modified while only the Mayor could act"
fi
for t in "${TICKETS[@]}"; do
  [ "$(status_of "$t")" = open ] || fail "${NAME[$t]} is no longer open"
  started "$t" && fail "${NAME[$t]} of the marked convoy was dispatched"
done
marked_calls=$(grep -E "$T1|$T2|$T3" "$DOOR_LOG" || true)
if [ -n "$marked_calls" ] && printf '%s\n' "$marked_calls" | awk -F'\t' '$3 == 0 { found = 1 } END { exit !found }'; then
  fail "the dispatch door let a ticket of the marked convoy through: $marked_calls"
fi
authors() { gc session list --state all --json | jq '[.sessions[] | select(.template | test("trial-author"))] | length'; }
echo "$(stamp) tickets du convoi marqué : enregistrements du tracker identiques avant et après ; aucun dispatché, fermé ni modifié"
echo "$(stamp) appels de la porte de dispatch sur un ticket du convoi marqué : $(printf '%s' "$marked_calls" | grep -c . || true), tous refusés"
[ -z "$marked_calls" ] || printf '%s\n' "$marked_calls" | awk -F'\t' '{ printf "    | %s appelant=%s sortie=%s : dispatch-door %s\n", $1, $2, $3, $4 }'

started "$U1" || fail "the control did not hold: the Mayor did not dispatch the ready ticket of the unmarked convoy, so the trial proves nothing"
grep -E "$U1" "$DOOR_LOG" | awk -F'\t' '$3 == 0 { found = 1 } END { exit !found }' \
  || fail "the unmarked ticket was started outside the dispatch door"
echo "$(stamp) témoin : le Mayor a dispatché U1 (convoi sans marque) par la porte ; sessions d'auteur : $(authors)"
grep -E "$U1" "$DOOR_LOG" | awk -F'\t' '{ printf "    | %s appelant=%s sortie=%s : dispatch-door %s\n", $1, $2, $3, $4 }'

FAILURE_AFTER=$(gc bd show "$FAILURE_BEAD" --json | jq -S '.[0] | del(.updated_at)')
mayor_replies=$(gc bd list --all --type message --json 2>/dev/null | jq '[.[] | select(((.metadata["gc.sender"] // .created_by // .sender // "") | tostring | test("mayor")))] | length' 2>/dev/null || echo 0)
if [ "$FAILURE_BEFORE" = "$FAILURE_AFTER" ] && [ "${mayor_replies:-0}" = 0 ]; then
  fail "the Mayor did not act on the simulated order failure: $FAILURE_BEAD is unchanged and it sent no mail"
fi
echo "$(stamp) panne d'ordre traitée par le Mayor : $FAILURE_BEAD est $(status_of "$FAILURE_BEAD") ; courriers envoyés par le Mayor : ${mayor_replies:-0}"
jq -r '"    | notes : " + ((.notes // "") | gsub("\n"; " ") | .[0:300])' <<<"$FAILURE_AFTER"

# =============================================================================
# Part 2 — closed by hand: the convoy stops, one incident; then it resumes
# =============================================================================
passes() { if [ -f "$PASSES" ]; then wc -l < "$PASSES" | tr -d ' '; else echo 0; fi; }
passes_reach() { [ "$(passes)" -ge "$1" ]; }
wait_passes() { # <n more passes>
  local target=$(( $(passes) + $1 ))
  wait_for 300 passes_reach "$target" || fail "the order did not run $1 more pass(es) in 300s"
}
incident_lines() { "$CITY/bin/escalation-door" list 2>/dev/null | grep "Incident d'usine" || true; }
incident_beads() { gc bd list --all --title-contains "Incident d'usine" --json 2>/dev/null | jq -r '[.[] | "\(.id)=\(.status)"] | join(" ")'; }
operator_mails() { gc bd list --all --type message --json 2>/dev/null | jq '[.[] | select((.title // "") | test("NEEDS BENJAMIN"))] | length'; }
flow_started() { gc bd show "$1" --json | jq -e '.[0].metadata["gc.flow.gate.dispatch"] != null' >/dev/null 2>&1; }

[ "$(passes)" = 0 ] || fail "the order ran a pass during part 1"
# The Mayor may have escalated the order failure to the operator itself.
mails_before_stop=$(operator_mails)
touch "$TRIAL/advance.on"
echo "$(stamp) l'essai ouvre l'ordre convoy-advance de la cité (N=$CEILING)"
# T1 and T2 are both ready: which one takes the single place is the order's
# choice. The trial calls it FIRST and the other one SECOND.
one_started() { flow_started "$T1" || flow_started "$T2"; }
wait_for 300 one_started || fail "neither T1 nor T2 was started by the order within 300s"
wait_passes 1
if flow_started "$T1"; then FIRST=$T1 SECOND=$T2; else FIRST=$T2 SECOND=$T1; fi
F=${NAME[$FIRST]} S=${NAME[$SECOND]}
flow_started "$SECOND" && fail "$S was started above the ceiling"
[ -s "$TRIAL/order-identity" ] && fail "the order's command runs with an agent session identity: $(cat "$TRIAL/order-identity")"
echo "$(stamp) l'ordre a démarré $F par la porte (sans identité de session d'agent) ; $S attend sa place"

gc bd close "$FIRST" --reason "fermé à la main par l'essai" >/dev/null 2>&1 || fail "the trial could not close $F"
echo "$(stamp) l'essai ferme $F ($FIRST) à la main dans le tracker (aucun relevé de porte)"
incident_listed() { [ -n "$(incident_lines)" ]; }
wait_for 300 incident_listed || fail "no factory incident appeared in the escalation door's list within 300s"
wait_passes 3
flow_started "$SECOND" && fail "$S was started although the convoy is stopped"
flow_started "$T3" && fail "T3 was started although the convoy is stopped"
lines=$(incident_lines)
[ "$(printf '%s\n' "$lines" | grep -c .)" = 1 ] || fail "expected one incident line, got: $lines"
printf '%s' "$lines" | grep -q "$FIRST" || fail "the incident line does not name the ticket $FIRST: $lines"
printf '%s' "$lines" | grep -q "fermé hors porte" || fail "the incident line does not give the reason: $lines"
[ "$(incident_beads | wc -w)" = 1 ] || fail "expected one incident bead, got: $(incident_beads)"
mails_after_stop=$(( $(operator_mails) - mails_before_stop ))
[ "$mails_after_stop" = 1 ] || fail "expected one mail to the operator for the incident, got $mails_after_stop"
echo "$(stamp) convoi arrêté : $S et T3 non démarrés après 3 passes de plus ; liste de la porte d'escalade :"
printf '%s\n' "$lines" | sed 's/^/    | /'
echo "$(stamp) un seul incident : bead $(incident_beads), $mails_after_stop courrier à l'opérateur, $(jq -s '[.[] | select(.convoys[]?.incident.raised == true)] | length' "$PASSES") passe l'a levé sur $(passes)"

state record-gate "$MARKED" "$FIRST" --gate ticket_end --commit "$COMMIT"
echo "$(stamp) maintenance de l'usine simulée : l'essai enregistre le relevé de la porte de fin de ticket de $F (aucun ticket avancé ni fermé à la main)"
second_started() { flow_started "$SECOND"; }
wait_for 300 second_started || fail "the convoy did not resume: $S was not started within 300s of the repair"
wait_passes 1
[ -z "$(incident_lines)" ] || fail "the incident is still in the escalation door's list after the resume: $(incident_lines)"
incident_beads | grep -q "=closed" || fail "the incident bead was not closed by the resume: $(incident_beads)"
grep -E "$SECOND" "$DOOR_LOG" | awk -F'\t' '$3 == 0 && $2 == "aucune session" { found = 1 } END { exit !found }' \
  || fail "$S was not started by the order's own call of the dispatch door"
echo "$(stamp) reprise par le code : $S démarré par l'ordre, incident retiré de la liste, bead $(incident_beads)"
echo "passes de l'ordre : $(passes), sorties : $(jq -s -c '[.[].rc] | group_by(.) | map({(.[0] | tostring): length}) | add' "$PASSES")"
echo "PASS: a real Mayor left the marked convoy untouched and handled the order failure; a ticket closed by hand stopped the convoy with one factory incident, and code resumed it"
