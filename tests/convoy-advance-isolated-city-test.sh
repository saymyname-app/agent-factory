#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime, an isolated Dolt server and its own supervisor
#
# Adoption trial of bin/convoy-advance (T04, af-gfyj6k; Spec af-wf4w5r §0
# rule 3, user story 82) in a disposable city that shares nothing with the
# live Factory: its own GC_HOME, runtime directory, supervisor port and
# controller. The city has no Mayor. Its one agent runs on a stub provider
# (a shell script that sleeps), so a start is a real `gc sling` and a real
# session, and nothing is spent.
#
# What the trial observes, with only the city's controller acting:
#   1. Gas City alone: with ready tickets in a convoy, the controller and
#      its control dispatcher start none of them.
#   2. The order orders/convoy-advance.toml, on a convoy without the mark:
#      nothing is started, nothing is written.
#   3. Once the convoy is marked: its two unblocked tickets are started
#      through the dispatch door; the third, blocked by both, is not; a
#      ticket of a second marked convoy waits, the ceiling N=2 being shared.
#   4. The trial closes a first blocker: the freed place goes to the second
#      convoy's ticket, the third ticket stays blocked.
#   5. The trial closes the second blocker: the third ticket is started.
# At every observation, no more than N tickets are in flight.
#
# The trial prints its record (« relevé d'essai ») on stdout.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
PORT="${CONVOY_ADVANCE_TRIAL_PORT:-18393}"
CEILING=2

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc bd jq git dolt tmux; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

TRIAL=$(mktemp -d /tmp/af-gfyj6k-advance.XXXXXX)
CITY="$TRIAL/c"
PASSES="$TRIAL/passes.jsonl"
cleanup() {
  status=$?
  trap - EXIT
  gc --city "$CITY" stop >/dev/null 2>&1 || true
  gc supervisor stop >/dev/null 2>&1 || true
  tmux -L "$(basename "$TRIAL")" kill-server >/dev/null 2>&1 || true
  # The supervisor, the city's managed Dolt server and the stub sessions
  # carry the trial directory on their command line; nothing else does.
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
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$|FACTORY_ROOT$|CONVOY_|DISPATCH_DOOR_)' || true)
export GC_HOME="$TRIAL/h" XDG_RUNTIME_DIR="$TRIAL/r" GC_DISABLE_USAGE_METRICS=1
export PATH="/usr/local/bin:$HOME/.local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
mkdir -p "$GC_HOME"
mkdir -m 700 "$XDG_RUNTIME_DIR"
printf '[supervisor]\nport = %s\n' "$PORT" > "$GC_HOME/supervisor.toml"

gc init --template minimal --default-provider claude --skip-provider-readiness \
  --no-start --yes --name "$(basename "$TRIAL")" "$CITY" >/dev/null 2>&1 \
  || fail "gc init of the isolated city failed"
# No Mayor in this city: whatever starts a ticket here is not a Mayor.
sed -i '/^\[\[named_session\]\]$/,+2d' "$CITY/pack.toml"
rm -rf "$CITY/agents/mayor"

cat > "$TRIAL/stub-agent" <<'STUB'
#!/bin/sh
echo "stub agent of the convoy-advance trial: idle"
exec sleep 3600
STUB
chmod +x "$TRIAL/stub-agent"
cat > "$CITY/city.toml" <<TOML
[workspace]
provider = "stub"

[providers.stub]
base = "builtin:claude"
command = "$TRIAL/stub-agent"
ready_delay_ms = 0
TOML
mkdir -p "$CITY/agents/trial-author" "$CITY/formulas" "$CITY/orders" "$CITY/config/projects"
cat > "$CITY/agents/trial-author/agent.toml" <<'TOML'
description = "Author of the convoy-advance trial (stub provider, spends nothing)"
scope = "city"
min_active_sessions = 0
max_active_sessions = 3
TOML
echo "Stub of the convoy-advance trial." > "$CITY/agents/trial-author/prompt.template.md"
cat > "$CITY/formulas/trial-start.formula.toml" <<'TOML'
description = "Formula of the convoy-advance trial: one step."
formula = "trial-start"

[requires]
formula_compiler = ">=2.0.0"

[[steps]]
id = "work"
title = "Work the ticket"
description = "Trial step."
TOML

# The Factory root the advance command reads: the city itself, with one
# project, the ceiling and the start formula.
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
# The role agents of the real Factory do not exist here: the ceiling is
# exercised by tickets started and not yet picked by a session.
cp "$ROOT/config/delivery-roles.json" "$CITY/config/delivery-roles.json"

# The real order, pointed at this checkout's command and at this city.
cat > "$TRIAL/advance" <<WRAP
#!/bin/sh
export FACTORY_ROOT="$CITY" CONVOY_STATE_LOCK_DIR="$TRIAL/locks" CONVOY_ADVANCE_LOCK_DIR="$TRIAL/locks"
if [ "\$1" = "--check-only" ]; then
  exec "$ROOT/bin/convoy-advance" --check-only
fi
out=\$("$ROOT/bin/convoy-advance" "\$@"); rc=\$?
printf '%s' "\$out" | jq -c --arg at "\$(date -u +%H:%M:%S)" --argjson rc "\$rc" '{at: \$at, rc: \$rc} + .' >> "$PASSES"
exit "\$rc"
WRAP
chmod +x "$TRIAL/advance"
sed "s#/home/benja/agent-factory/bin/convoy-advance#$TRIAL/advance#g" "$ROOT/orders/convoy-advance.toml" \
  > "$CITY/orders/convoy-advance.toml"
grep -q "$TRIAL/advance --all" "$CITY/orders/convoy-advance.toml" || fail "the order does not run bin/convoy-advance --all"

cd "$CITY"
state() {
  local out
  out=$(FACTORY_ROOT="$CITY" CONVOY_STATE_LOCK_DIR="$TRIAL/locks" "$ROOT/bin/convoy-state" "$@") \
    || fail "convoy-state $* did not pass: $out"
}
new_ticket() {
  gc bd create --title "$1" --type task --silent \
    --description $'## What to build\n\nessai\n\n## Target rigs\n\ntrial\n\n## Autonomous execution contract\n\n- none' 2>/dev/null
}

CONVOY=$(gc bd create --title "convoi d'essai" --type convoy --silent 2>/dev/null)
T1=$(new_ticket "ticket 1")
T2=$(new_ticket "ticket 2")
T3=$(new_ticket "ticket 3, bloqué par 1 et 2")
OTHER=$(gc bd create --title "convoi d'une autre Spec" --type convoy --silent 2>/dev/null)
O1=$(new_ticket "ticket de l'autre Spec")
for t in "$T1" "$T2" "$T3"; do gc bd dep add "$CONVOY" "$t" --type tracks >/dev/null; done
gc bd dep add "$OTHER" "$O1" --type tracks >/dev/null
gc bd dep add "$T3" "$T1" >/dev/null
gc bd dep add "$T3" "$T2" >/dev/null
ALL=("$T1" "$T2" "$T3" "$O1")
# A ticket is marked with its kind (T05); a prefactoring needs no demonstration line.
for t in "${ALL[@]}"; do gc bd update "$t" --set-metadata gc.ticket_kind=prefactoring >/dev/null; done
declare -A NAME=([$T1]=T1 [$T2]=T2 [$T3]=T3 [$O1]=O1)

echo "relevé d'essai — bin/convoy-advance en cité isolée ($(gc version 2>/dev/null | head -1), N=$CEILING, aucun Mayor)"
echo "convoi $CONVOY : T1=$T1 T2=$T2 T3=$T3 (T3 bloqué par T1 et T2) ; autre Spec $OTHER : O1=$O1"

(gc supervisor run > "$TRIAL/supervisor.out" 2>&1 &)
sleep 3
gc --city "$CITY" start >/dev/null 2>&1 || true
gc --city "$CITY" status 2>/dev/null | grep -q "Controller: supervisor-managed" || fail "the isolated city's controller did not start"
gc order show convoy-advance --json >/dev/null 2>&1 || fail "the city does not accept orders/convoy-advance.toml"

# A ticket is started when the door stamped it; it is in flight until closed.
started() {
  gc bd show "$1" --json | jq -e '.[0].metadata["gc.dispatched_via"] == "dispatch-door" and (.[0].metadata["gc.flow.gate.dispatch"] != null)' >/dev/null 2>&1
}
closed() { [ "$(gc bd show "$1" --json | jq -r '.[0].status')" = closed ]; }
observe() { # <label>: print one line of the record, fail above the ceiling
  local line="" in_flight=0 t
  for t in "${ALL[@]}"; do
    if closed "$t"; then line+=" ${NAME[$t]}=fermé"
    elif started "$t"; then line+=" ${NAME[$t]}=démarré"; in_flight=$((in_flight + 1))
    else line+=" ${NAME[$t]}=en attente"; fi
  done
  echo "$(date -u +%H:%M:%S) $1 :$line ; en vol $in_flight/$CEILING ; passes $(passes)"
  [ "$in_flight" -le "$CEILING" ] || fail "$in_flight tickets in flight, above the ceiling $CEILING"
}
passes() { if [ -f "$PASSES" ]; then wc -l < "$PASSES" | tr -d ' '; else echo 0; fi; }
wait_for() { # <seconds> <command...>
  local deadline=$(( $(date +%s) + $1 )); shift
  until "$@"; do
    [ "$(date +%s)" -lt "$deadline" ] || return 1
    sleep 5
  done
}
passes_reach() { [ "$(passes)" -ge "$1" ]; }
wait_passes() { # <n more passes>
  local target=$(( $(passes) + $1 ))
  wait_for 300 passes_reach "$target" || fail "the order did not run $1 more pass(es) in 300s"
}
close_by_trial() { # the flow's own ticket end is not in T04: the trial closes
  state record-gate "$CONVOY" "$1" --gate ticket_end --commit 0123456789abcdef0123456789abcdef01234567
  gc bd close "$1" --reason "fermé par l'essai" >/dev/null 2>&1
  echo "$(date -u +%H:%M:%S) l'essai ferme ${NAME[$1]} dans le tracker"
}

# --- 1 and 2: no mark -> Gas City starts nothing, the order starts nothing ----
snapshot() { for t in "${ALL[@]}" "$CONVOY" "$OTHER"; do gc bd show "$t" --json | jq -S '.[0] | del(.updated_at)'; done; }
before=$(snapshot)
sleep 150   # more than two controller ticks and two firings of the order's check
gc session list --json | jq -e '[.sessions[] | select(.template | test("trial-author"))] | length == 0' >/dev/null \
  || fail "a session was started for a ticket of a convoy without the mark"
[ "$before" = "$(snapshot)" ] || fail "a convoy without the mark was written"
[ "$(passes)" = 0 ] || fail "the order ran a pass although no convoy carries the mark"
observe "150 s sans marque, contrôleur actif, ordre installé (rien démarré, rien écrit)"

# --- 3: marked -> the two unblocked tickets start, under the shared ceiling ---
state mark "$CONVOY"
state mark "$OTHER"
echo "$(date -u +%H:%M:%S) l'essai pose la marque sur les deux convois"
both_started() { started "$T1" && started "$T2"; }
wait_for 300 both_started || fail "T1 and T2 were not started within 300s of the mark"
wait_passes 2
started "$T3" && fail "T3 was started while its blockers are open"
started "$O1" && fail "O1 was started above the shared ceiling"
observe "après la marque (T3 bloqué, O1 retenu par le plafond partagé)"
gc session list --json | jq -e '[.sessions[] | select(.template | test("trial-author"))] | length >= 1' >/dev/null \
  || fail "no author session was created by the starts"
gc session list --state all --json | jq -e '[.sessions[] | select(.template | test("mayor"))] | length == 0' >/dev/null \
  || fail "a Mayor session exists in the trial city"
echo "$(date -u +%H:%M:%S) sessions de la cité : $(gc session list --json | jq -r '[.sessions[] | "\(.template)=\(.state)"] | join(", ")')"

# --- 4: first blocker closed -> the freed place goes to the other Spec ---------
close_by_trial "$T1"
o1_started() { started "$O1"; }
wait_for 300 o1_started || fail "O1 was not started after a place was freed"
wait_passes 1
started "$T3" && fail "T3 was started with one blocker still open"
observe "après la fermeture de T1 (O1 prend la place, T3 encore bloqué par T2)"

# --- 5: second blocker closed -> the third ticket starts ----------------------
close_by_trial "$T2"
t3_started() { started "$T3"; }
wait_for 300 t3_started || fail "T3 was not started after both its blockers were closed"
wait_passes 1
observe "après la fermeture de T2 (T3 démarré)"

# --- no ticket was started twice ----------------------------------------------
for t in "${ALL[@]}"; do
  n=$(jq -s --arg t "$t" '[.[].convoys[]?.started[]? | select(. == $t)] | length' "$PASSES")
  [ "$n" = 1 ] || fail "${NAME[$t]} was started $n times"
done
gc session list --state all --json | jq -e '[.sessions[] | select(.template | test("mayor"))] | length == 0' >/dev/null \
  || fail "a Mayor session exists in the trial city"

names=$(jq -n --arg t1 "$T1" --arg t2 "$T2" --arg t3 "$T3" --arg o1 "$O1" '{($t1): "T1", ($t2): "T2", ($t3): "T3", ($o1): "O1"}')
echo "ordre de démarrage relevé dans les passes : $(jq -s -r --argjson names "$names" \
  '[.[] | select([.convoys[]?.started[]?] | length > 0) | "\(.at) " + ([.convoys[].started[]] | map($names[.]) | join("+"))] | join(" ; ")' "$PASSES")"
echo "passes de l'ordre : $(passes), toutes sorties 0 : $(jq -s 'all(.[]; .rc == 0)' "$PASSES")"
echo "PASS: convoy-advance, run by the city's own order, started the three tickets in dependency order under N=$CEILING, with no Mayor"
