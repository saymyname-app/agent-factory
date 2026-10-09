#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime, an isolated Dolt server and its own supervisor
#
# Adoption trial of the manual lifecycle of a marked convoy (T22, af-kn83no;
# Spec af-wf4w5r §9, user story 55) in a disposable city that shares nothing
# with the live Factory: its own GC_HOME, runtime directory, supervisor port
# and controller. The city has no Mayor and no agent: nothing is spent.
#
# What is real: the controller; the three orders of the Factory that react
# to a closing, run by that controller (orders/convoy-parent-sweep.toml and
# its `gc convoy check`, orders/planning-artifacts-close.toml,
# orders/convoy-advance.toml); the tracker (gc/bd); bin/convoy-state,
# bin/convoy-advance, bin/planning-artifacts-close and bin/escalation-door.
# What the trial does by hand: it publishes nothing (the convoys, their
# tickets, their Spec and Draft beads are created here) and it closes the
# tickets itself, the marked ones with the record of the ticket-end gate.
#
# What the trial observes:
#   1. A marked convoy and an unmarked one, all their tickets closed: the
#      convoy sweep closes the unmarked one, as before, and its Spec and
#      Draft close with it. The marked convoy is still open, without any
#      closing reason, and so are its Spec and its Draft -- after that sweep,
#      and after the same two commands run once more by the trial itself.
#   2. The trial then closes the marked convoy by hand: its Spec and its
#      Draft stay open, and one factory incident naming the convoy appears
#      in `bin/escalation-door list`.
#   3. The trial reopens it: the incident leaves the list.
#   4. Closing by command (T30, af-vlzc6v; Spec §9, §11). Benjamin's answer
#      is put on the convoy by hand (below); `bin/convoy-state close-convoy`
#      then closes it on « abandonné »: the real tracker takes the closed
#      status and the record of the closing in one `gc bd update`, the
#      state command lists the convoy as closed by command and rules it,
#      every later write of the flow is refused, the city's own order closes
#      its Spec and its Draft, no pass of the advance names it any more and
#      neither the controller nor `gc convoy check` / `gc convoy status`
#      changes a byte of its bead.
#   5. The same on « accepté », for a second marked convoy whose merge is
#      recorded by `bin/convoy-state record-promotion`.
#
# What 4 and 5 do by hand: `gc.flow.judgement` is written straight on the
# convoy bead, as tests/convoy-close-test.py does on its fake tracker. Its
# public writer, `convoy-state record-owner-answer`, wants a Delivered
# Outcome or a « non conforme » request, that is an integration branch, the
# gate of the end of the Spec, an Outcome Evaluation, an end review and an
# Evidence Pack: none exists in a city without a project. No merge is made
# either: the commits of the promotion are placeholders.
#
# The trial prints its record (« relevé d'essai ») on stdout.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
. "$ROOT/tests/lib/isolated-city.sh"
PORT="${CONVOY_MANUAL_LIFECYCLE_TRIAL_PORT:-18397}"
AUTOCLOSE="convoy autoclose"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc bd jq git dolt; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

TRIAL=$(mktemp -d /tmp/af-kn83no-lifecycle.XXXXXX)
CITY="$TRIAL/c"
SWEEPS="$TRIAL/sweeps.jsonl"
ARTIFACT_RUNS="$TRIAL/artifact-runs.log"
PASSES="$TRIAL/passes.jsonl"
# Before the trap: whatever the cleanup stops is this trial's own supervisor,
# never the host's, even if the script dies on its next line.
export GC_HOME="$TRIAL/h" XDG_RUNTIME_DIR="$TRIAL/r" GC_DISABLE_USAGE_METRICS=1
cleanup() {
  status=$?
  trap - EXIT
  isolated_city_stop "$TRIAL" "$CITY" >/dev/null 2>&1 || true
  # The supervisor and the city's managed Dolt server carry the trial
  # directory on their command line; nothing else does.
  pkill -f -- "$TRIAL/" >/dev/null 2>&1 || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    pgrep -f -- "$TRIAL/" >/dev/null 2>&1 || break
    sleep 0.3
  done
  pkill -9 -f -- "$TRIAL/" >/dev/null 2>&1 || true
  # Should a systemd user unit of this trial exist anyway, it is removed and
  # the trial fails: it would restart at every login.
  for unit in "$HOME/.local/share/systemd/user"/gascity-supervisor-*.service; do
    [ -f "$unit" ] && grep -qF -- "$TRIAL/" "$unit" || continue
    echo "FAIL: the trial left the systemd user unit $(basename "$unit"); removing it" >&2
    systemctl --user disable --now "$(basename "$unit")" >/dev/null 2>&1 || true
    rm -f -- "$unit"
    systemctl --user daemon-reload >/dev/null 2>&1 || true
    [ "$status" != 0 ] || status=1
  done
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
export GC_HOME="$TRIAL/h" XDG_RUNTIME_DIR="$TRIAL/r" GC_DISABLE_USAGE_METRICS=1   # unset just above with the other GC_*
# No user bus: `gc start` must not install or start a systemd unit for this
# trial's supervisor on the host (same recipe as
# tests/convoy-advance-isolated-city-test.sh).
unset DBUS_SESSION_BUS_ADDRESS
export PATH="/usr/local/bin:$HOME/.local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
mkdir -p "$GC_HOME"
mkdir -m 700 "$XDG_RUNTIME_DIR"
printf '[supervisor]\nport = %s\n' "$PORT" > "$GC_HOME/supervisor.toml"

gc init --template minimal --default-provider claude --skip-provider-readiness \
  --no-start --yes --name "$(basename "$TRIAL")" "$CITY" >/dev/null 2>&1 \
  || fail "gc init of the isolated city failed"
# No Mayor and no agent in this city: only the controller and its orders act.
sed -i '/^\[\[named_session\]\]$/,+2d' "$CITY/pack.toml"
rm -rf "$CITY/agents/mayor"

# The Factory's commands at this checkout, with the city as their root.
cp -r "$ROOT/bin" "$ROOT/lib" "$CITY/"
mkdir -p "$CITY/orders" "$CITY/config/projects"
cp "$ROOT/config/operator.toml" "$ROOT/config/delivery-roles.json" "$CITY/config/"
# The bounds of the flow are the Factory's own: the commands copied above
# read them next to themselves, that is in this file, and refuse without.
jq '{contract: "agent-factory-delivery-flow/v1", max_sessions: 2, start: {formula: "trial-start", role: null}, bounds}' \
  "$ROOT/config/delivery-flow.json" > "$CITY/config/delivery-flow.json"
jq -e '.bounds | type == "object"' "$CITY/config/delivery-flow.json" >/dev/null \
  || fail "config/delivery-flow.json sets no bounds"

# The three real orders. Each command is the one the order names, wrapped
# only to record that it ran.
grep -qxF 'exec = "gc convoy check --json"' "$ROOT/orders/convoy-parent-sweep.toml" \
  || fail "orders/convoy-parent-sweep.toml no longer runs gc convoy check --json"
cat > "$TRIAL/sweep" <<WRAP
#!/bin/sh
out=\$(gc convoy check --json); rc=\$?
printf '%s\n' "\$out" >> "$SWEEPS"
exit "\$rc"
WRAP
sed "s#^exec = \"gc convoy check --json\"\$#exec = \"$TRIAL/sweep\"#" "$ROOT/orders/convoy-parent-sweep.toml" \
  > "$CITY/orders/convoy-parent-sweep.toml"

cat > "$TRIAL/artifacts" <<WRAP
#!/bin/sh
export FACTORY_ROOT="$CITY"
out=\$("$CITY/bin/planning-artifacts-close" "\$@" 2>&1); rc=\$?
printf '%s rc=%s %s\n' "\$(date -u +%H:%M:%S)" "\$rc" "\$(printf '%s' "\$out" | tr '\n' ' ')" >> "$ARTIFACT_RUNS"
exit "\$rc"
WRAP
sed "s#/home/benja/agent-factory/bin/planning-artifacts-close#$TRIAL/artifacts#g" "$ROOT/orders/planning-artifacts-close.toml" \
  > "$CITY/orders/planning-artifacts-close.toml"
grep -qF "exec = \"$TRIAL/artifacts\"" "$CITY/orders/planning-artifacts-close.toml" \
  || fail "the order does not run bin/planning-artifacts-close"

cat > "$TRIAL/advance" <<WRAP
#!/bin/sh
export FACTORY_ROOT="$CITY" CONVOY_STATE_LOCK_DIR="$TRIAL/locks" CONVOY_ADVANCE_LOCK_DIR="$TRIAL/locks"
export ESCALATION_DOOR_LOCK_FILE="$TRIAL/escalation-door.lock"
if [ "\$1" = "--check-only" ]; then
  exec "$CITY/bin/convoy-advance" --check-only
fi
out=\$("$CITY/bin/convoy-advance" "\$@"); rc=\$?
printf '%s' "\$out" | jq -c --arg at "\$(date -u +%H:%M:%S)" --argjson rc "\$rc" '{at: \$at, rc: \$rc} + .' >> "$PASSES"
exit "\$rc"
WRAP
sed "s#/home/benja/agent-factory/bin/convoy-advance#$TRIAL/advance#g" "$ROOT/orders/convoy-advance.toml" \
  > "$CITY/orders/convoy-advance.toml"
grep -q "$TRIAL/advance --all --stopped-ok" "$CITY/orders/convoy-advance.toml" \
  || fail "the order does not run bin/convoy-advance --all --stopped-ok"
chmod +x "$TRIAL/sweep" "$TRIAL/artifacts" "$TRIAL/advance"

cd "$CITY"
export FACTORY_ROOT="$CITY" CONVOY_STATE_LOCK_DIR="$TRIAL/locks" CONVOY_ADVANCE_LOCK_DIR="$TRIAL/locks"
export ESCALATION_DOOR_LOCK_FILE="$TRIAL/escalation-door.lock"
state() {
  local out
  out=$("$CITY/bin/convoy-state" "$@") || fail "convoy-state $* did not pass: $out"
}
new_bead() { gc bd create --title "$1" --type "$2" --silent 2>/dev/null; }
field() { gc bd show "$1" --json | jq -r --arg f "$2" '.[0][$f] // ""'; }

# Two convoys as the publication door leaves them: each names its Spec and
# its Draft, beads of this tracker.
SPEC=$(new_bead "Spec de la fixture" task);        DRAFT=$(new_bead "Brouillon de graphe de la fixture" task)
PLAIN_SPEC=$(new_bead "Spec sans marque" task);    PLAIN_DRAFT=$(new_bead "Brouillon sans marque" task)
CONVOY=$(new_bead "convoi de la fixture" convoy);  PLAIN=$(new_bead "convoi sans marque" convoy)
T1=$(new_bead "ticket 1" task); T2=$(new_bead "ticket 2" task); P1=$(new_bead "ticket sans marque" task)
gc bd update "$CONVOY" --set-metadata "gc.spec_id=$SPEC" --set-metadata "gc.artifact_id=$DRAFT" >/dev/null
gc bd update "$PLAIN" --set-metadata "gc.spec_id=$PLAIN_SPEC" --set-metadata "gc.artifact_id=$PLAIN_DRAFT" >/dev/null
for t in "$T1" "$T2" "$P1"; do gc bd update "$t" --set-metadata gc.ticket_kind=prefactoring >/dev/null; done
gc bd dep add "$CONVOY" "$T1" --type tracks >/dev/null
gc bd dep add "$CONVOY" "$T2" --type tracks >/dev/null
gc bd dep add "$PLAIN" "$P1" --type tracks >/dev/null
state mark "$CONVOY"

echo "relevé d'essai — convoi marqué sans fermeture automatique, en cité isolée ($(gc version 2>/dev/null | head -1), aucun Mayor, aucun agent)"
echo "convoi marqué $CONVOY (tickets $T1 $T2, Spec $SPEC, brouillon $DRAFT) ; convoi sans marque $PLAIN (ticket $P1, Spec $PLAIN_SPEC, brouillon $PLAIN_DRAFT)"

(gc supervisor run > "$TRIAL/supervisor.out" 2>&1 &)
sleep 3
gc --city "$CITY" start >/dev/null 2>&1 || true
grep -q "Controller: supervisor-managed" <<<"$(gc --city "$CITY" status 2>/dev/null)" || fail "the isolated city's controller did not start"
for order in convoy-parent-sweep planning-artifacts-close convoy-advance; do
  gc order show "$order" --json >/dev/null 2>&1 || fail "the city does not accept orders/$order.toml"
done

count() { if [ -f "$1" ]; then wc -l < "$1" | tr -d ' '; else echo 0; fi; }
wait_for() { # <seconds> <command...>
  local deadline=$(( $(date +%s) + $1 )); shift
  until "$@"; do
    [ "$(date +%s)" -lt "$deadline" ] || return 1
    sleep 5
  done
}
is_closed() { [ "$(field "$1" status)" = closed ]; }
reaches() { [ "$(count "$1")" -ge "$2" ]; }
incident_lines() { "$CITY/bin/escalation-door" list 2>/dev/null | grep "Incident d'usine" || true; }
observe() {
  echo "$(date -u +%H:%M:%S) $1 : convoi marqué=$(field "$CONVOY" status) Spec=$(field "$SPEC" status) brouillon=$(field "$DRAFT" status)" \
    "; convoi sans marque=$(field "$PLAIN" status) Spec=$(field "$PLAIN_SPEC" status) brouillon=$(field "$PLAIN_DRAFT" status)" \
    "; balayages $(count "$SWEEPS"), fermetures d'artefacts $(count "$ARTIFACT_RUNS"), passes $(count "$PASSES")"
}
marked_convoy_untouched() { # <when>
  [ "$(field "$CONVOY" status)" = open ] || fail "the marked convoy is $(field "$CONVOY" status) $1"
  [ -z "$(field "$CONVOY" close_reason)" ] || fail "the marked convoy carries a closing reason $1: $(field "$CONVOY" close_reason)"
  [ "$(field "$SPEC" status)" = open ] || fail "the Spec of the marked convoy is $(field "$SPEC" status) $1"
  [ "$(field "$DRAFT" status)" = open ] || fail "the Draft of the marked convoy is $(field "$DRAFT" status) $1"
}

# --- 1: every ticket closed -> only the unmarked convoy closes ----------------
observe "départ"
for t in "$T1" "$T2"; do
  # The record of the ticket-end gate and the closed status, in one write (T19).
  state close-ticket "$CONVOY" "$t" --commit 0123456789abcdef0123456789abcdef01234567 \
    --file "$ROOT/tests/fixtures/convoy-state/ticket-end-report.json"
done
gc bd close "$P1" --reason "fait" >/dev/null 2>&1
echo "$(date -u +%H:%M:%S) l'essai ferme les tickets des deux convois"

wait_for 300 is_closed "$PLAIN" || fail "the convoy sweep did not close the unmarked convoy within 300s"
grep -qF "$AUTOCLOSE" <<<"$(field "$PLAIN" close_reason)" \
  || fail "the unmarked convoy was not closed by the sweep: $(field "$PLAIN" close_reason)"
wait_for 300 is_closed "$PLAIN_SPEC" || fail "the Spec of the unmarked convoy did not close with it within 300s"
wait_for 300 is_closed "$PLAIN_DRAFT" || fail "the Draft of the unmarked convoy did not close with it within 300s"
observe "le balayage a fermé le convoi sans marque"
marked_convoy_untouched "after the sweep that closed the unmarked convoy"

# Once more on the same state, by the trial itself: the same two commands.
gc convoy check --json >/dev/null || fail "gc convoy check failed"
"$CITY/bin/planning-artifacts-close" >/dev/null || fail "bin/planning-artifacts-close failed"
observe "balayage et fermeture d'artefacts repassés par l'essai"
marked_convoy_untouched "after the sweep ran again"
[ -z "$(incident_lines)" ] || fail "an open marked convoy whose tickets are closed raised an incident: $(incident_lines)"

# --- 2: closed by hand -> anomaly on the escalation door's list ---------------
artifact_runs=$(count "$ARTIFACT_RUNS")
gc bd close "$CONVOY" --reason "fermé à la main par l'essai" >/dev/null
echo "$(date -u +%H:%M:%S) l'essai ferme le convoi marqué à la main"
incident_listed() { grep -qF "$CONVOY" <<<"$(incident_lines)"; }
wait_for 300 incident_listed || fail "no factory incident naming the convoy appeared in the escalation door's list within 300s"
[ "$(incident_lines | wc -l | tr -d ' ')" = 1 ] || fail "expected one incident line, got: $(incident_lines)"
grep -qF "fermé hors commande" <<<"$(incident_lines)" || fail "the incident does not say how the convoy was closed: $(incident_lines)"
wait_for 300 reaches "$ARTIFACT_RUNS" "$(( artifact_runs + 1 ))" || fail "the artifact closing did not run after the convoy was closed by hand"
"$CITY/bin/planning-artifacts-close" >/dev/null || fail "bin/planning-artifacts-close failed"
[ "$(field "$SPEC" status)" = open ] || fail "the Spec of a marked convoy closed by hand was closed"
[ "$(field "$DRAFT" status)" = open ] || fail "the Draft of a marked convoy closed by hand was closed"
observe "convoi marqué fermé à la main"
echo "$(date -u +%H:%M:%S) liste de la porte d'escalade : $(incident_lines | tr -s ' ')"

# --- 3: reopened -> the incident leaves the list -------------------------------
gc bd reopen "$CONVOY" >/dev/null
echo "$(date -u +%H:%M:%S) l'essai rouvre le convoi marqué"
incident_gone() { [ -z "$(incident_lines)" ]; }
wait_for 300 incident_gone || fail "the incident is still in the escalation door's list 300s after the convoy was reopened"
marked_convoy_untouched "after it was reopened"
observe "convoi marqué rouvert"

# --- 4, 5: closed by command, on Benjamin's words (T30) -------------------------
JUDGED=1111111111111111111111111111111111111111
MERGED=2222222222222222222222222222222222222222
PROTECTED=3333333333333333333333333333333333333333
PACK="sha256:$(printf '%064d' 0)"
WRITES="$TRIAL/tracker-writes.log"
# The state command's tracker, for the closing only: the real gc, which
# notes each `bd update` it is asked for.
cat > "$TRIAL/gc-noting-updates" <<WRAP
#!/bin/sh
[ "\$1 \$2" = "bd update" ] && printf '%s\n' "\$*" >> "$WRITES"
exec gc "\$@"
WRAP
chmod +x "$TRIAL/gc-noting-updates"

bead_bytes() { gc bd show "$1" --json | jq -S '.[0]'; }
listed_in() { "$CITY/bin/convoy-state" list | jq -e --arg id "$2" --arg where "$1" '.[$where] | index($id) != null' >/dev/null; }
after_a_pass() {
  # The advance follows a final answer by itself (bin/outcome-promote), and
  # this city has no project to promote: the answer is written just after a
  # pass of the order, and the convoy is closed long before the next one.
  local passes
  passes=$(count "$PASSES")
  wait_for 300 reaches "$PASSES" "$(( passes + 1 ))" || fail "the advance order made no pass within 300s"
}
answered() { # <convoy> <response> <words|reason> <what he said>: Benjamin's answer, by hand
  local judgement
  judgement=$(jq -cn --arg response "$2" --arg field "$3" --arg said "$4" --arg commit "$JUDGED" --arg pack "$PACK" \
    --arg at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{verdicts: [], answers: [{response: $response, approver: "benjamin", commit: $commit, pack: $pack, at: $at, ($field): $said}]}')
  gc bd update "$1" --set-metadata "gc.flow.judgement=$judgement" >/dev/null || fail "the judgement could not be written on $1"
  "$CITY/bin/convoy-state" show "$1" --repo "$CITY" >/dev/null || fail "the convoy $1 is not ruled once it carries Benjamin's answer"
}
refused_as_closed() { # <convoy> <convoy-state command...>
  local convoy=$1 before out; shift
  before=$(bead_bytes "$convoy")
  if out=$("$CITY/bin/convoy-state" "$@"); then fail "convoy-state $* passed on a convoy closed by command: $out"; fi
  grep -qF "rien ne le rouvre" <<<"$(jq -r '.error // ""' <<<"$out")" || fail "convoy-state $* was not refused as reopening a closed Outcome: $out"
  [ "$(bead_bytes "$convoy")" = "$before" ] || fail "the refused convoy-state $* changed the convoy bead"
}
closed_by_command() { # <convoy> <ticket> <spec> <draft> <how> <said>
  local convoy=$1 ticket=$2 spec=$3 draft=$4 how=$5 said=$6 out shown closed ticket_before passes sweeps
  passes=$(count "$PASSES"); sweeps=$(count "$SWEEPS")
  ticket_before=$(bead_bytes "$ticket")
  : > "$WRITES"
  out=$(GC_BIN="$TRIAL/gc-noting-updates" "$CITY/bin/convoy-state" close-convoy "$convoy") \
    || fail "convoy-state close-convoy $convoy did not pass: $out"
  echo "$(date -u +%H:%M:%S) l'essai ferme le convoi $convoy par la commande, sur « $said »"

  # The mechanism under trial: one update of the real tracker carries the
  # closed status and the record of the closing.
  [ "$(count "$WRITES")" = 1 ] || fail "close-convoy made $(count "$WRITES") tracker writes, expected one: $(cat "$WRITES")"
  grep -qF -- "bd update $convoy --status closed --set-metadata gc.flow.closed=" "$WRITES" \
    || fail "the one write of close-convoy is not the status and the record together: $(cat "$WRITES")"
  [ "$(field "$convoy" status)" = closed ] || fail "the tracker says the convoy $convoy is $(field "$convoy" status) after close-convoy"
  closed=$(bead_bytes "$convoy")
  [ "$(jq -r '.metadata["gc.flow.closed"] | fromjson | "\(.how) \(.approver) \(.said)"' <<<"$closed")" = "$how benjamin $said" ] \
    || fail "the tracker does not hold the record of the closing: $(jq -c '.metadata["gc.flow.closed"]' <<<"$closed")"
  echo "$(date -u +%H:%M:%S) écriture unique : gc $(cut -c1-150 "$WRITES")…"
  echo "$(date -u +%H:%M:%S) tracker : status=$(field "$convoy" status) gc.flow.closed=$(jq -r '.metadata["gc.flow.closed"]' <<<"$closed")"

  # The state command: closed by command, ruled, and not reopened.
  listed_in closed "$convoy" || fail "convoy-state list does not name $convoy under closed: $("$CITY/bin/convoy-state" list | jq -c .)"
  ! listed_in closed_outside "$convoy" || fail "convoy-state list names $convoy as closed outside its commands"
  ! listed_in convoys "$convoy" || fail "convoy-state list still names $convoy among the open convoys"
  shown=$("$CITY/bin/convoy-state" show "$convoy" --repo "$CITY") || fail "convoy-state show $convoy does not rule a convoy closed by command: $shown"
  [ "$(jq -c '[.convoy.status, .convoy.unruled, .convoy.closed.how]' <<<"$shown")" = "[\"closed\",[],\"$how\"]" ] \
    || fail "convoy-state show $convoy: $(jq -c '[.convoy.status, .convoy.unruled, .convoy.closed]' <<<"$shown")"
  refused_as_closed "$convoy" mark "$convoy"
  refused_as_closed "$convoy" open-resume "$convoy" "$ticket" --cause compaction
  refused_as_closed "$convoy" close-convoy "$convoy"
  [ "$(bead_bytes "$ticket")" = "$ticket_before" ] || fail "a refused write changed the ticket $ticket"
  echo "$(date -u +%H:%M:%S) convoy-state : list le range sous closed, show sans « état sans règle » ; mark, open-resume et close-convoy refusés (« rien ne le rouvre »)"

  # The city: its order closes the Spec and the Draft on that closing.
  wait_for 300 is_closed "$spec" || fail "the Spec of the convoy $convoy closed by command did not close within 300s"
  wait_for 300 is_closed "$draft" || fail "the Draft of the convoy $convoy closed by command did not close within 300s"
  for artifact in "$spec" "$draft"; do
    grep -qF "Convoy $convoy " <<<"$(field "$artifact" close_reason)" \
      || fail "$artifact was not closed by bin/planning-artifacts-close for $convoy: $(field "$artifact" close_reason)"
  done
  # Those two closings are events of the city too: its sweep runs on them.
  wait_for 300 reaches "$SWEEPS" "$(( sweeps + 1 ))" || fail "the convoy sweep did not run after the closing of $convoy"
  gc convoy check --json >/dev/null || fail "gc convoy check failed"
  gc convoy status "$convoy" >/dev/null || fail "gc convoy status $convoy failed"
  "$CITY/bin/planning-artifacts-close" >/dev/null || fail "bin/planning-artifacts-close failed"
  [ -z "$(incident_lines)" ] || fail "a convoy closed by command raised an incident: $(incident_lines)"
  ! grep -qF "$convoy" <<<"$(tail -n "+$(( passes + 1 ))" "$PASSES")" \
    || fail "a pass of the advance still names the convoy $convoy closed by command"
  [ "$(bead_bytes "$convoy")" = "$closed" ] \
    || fail "the bead of $convoy changed after its closing: $(diff <(printf '%s\n' "$closed") <(bead_bytes "$convoy") | tr '\n' ' ')"
  echo "$(date -u +%H:%M:%S) cité : Spec $spec=$(field "$spec" status) brouillon $draft=$(field "$draft" status) (« $(field "$spec" close_reason) ») ;" \
    "aucun incident ; bead du convoi inchangé après balayage, gc convoy check et gc convoy status"
}

# The second marked convoy, as the publication door leaves it, its ticket closed by its gate.
A_SPEC=$(new_bead "Spec acceptée" task); A_DRAFT=$(new_bead "Brouillon accepté" task)
ACCEPTED=$(new_bead "convoi accepté" convoy); A1=$(new_bead "ticket accepté" task)
gc bd update "$ACCEPTED" --set-metadata "gc.spec_id=$A_SPEC" --set-metadata "gc.artifact_id=$A_DRAFT" >/dev/null
gc bd update "$A1" --set-metadata gc.ticket_kind=prefactoring >/dev/null
gc bd dep add "$ACCEPTED" "$A1" --type tracks >/dev/null
state mark "$ACCEPTED"
state close-ticket "$ACCEPTED" "$A1" --commit 0123456789abcdef0123456789abcdef01234567 \
  --file "$ROOT/tests/fixtures/convoy-state/ticket-end-report.json"
echo "$(date -u +%H:%M:%S) second convoi marqué $ACCEPTED (ticket $A1 fermé par sa porte, Spec $A_SPEC, brouillon $A_DRAFT)"

# 4: « abandonné » -- the convoy that was closed by hand, then reopened.
after_a_pass
answered "$CONVOY" abandoned reason "Le besoin a disparu."
closed_by_command "$CONVOY" "$T1" "$SPEC" "$DRAFT" abandoned "Le besoin a disparu."
[ "$(field "$ACCEPTED" status)" = open ] || fail "the second marked convoy is $(field "$ACCEPTED" status) before its own closing"
[ "$(field "$A_SPEC" status)" = open ] || fail "the Spec of the second marked convoy closed before its convoy"

# 5: « accepté » -- the closing follows the merge.
after_a_pass
answered "$ACCEPTED" accepted words "Tout est bon, j'accepte."
if out=$("$CITY/bin/convoy-state" close-convoy "$ACCEPTED"); then fail "an accepted convoy closed before its merge: $out"; fi
grep -qF "la fermeture suit la fusion" <<<"$out" || fail "close-convoy before the merge was not refused for the merge: $out"
[ "$(field "$ACCEPTED" status)" = open ] || fail "the refused close-convoy closed the convoy"
state record-promotion "$ACCEPTED" --judged "$JUDGED" --merged "$MERGED" --protected "$PROTECTED" --tip "$JUDGED"
closed_by_command "$ACCEPTED" "$A1" "$A_SPEC" "$A_DRAFT" accepted "Tout est bon, j'accepte."

# No marked convoy is open or closed outside its commands: the advance has nothing left to walk.
out=$("$CITY/bin/convoy-advance" --all --stopped-ok) || fail "bin/convoy-advance --all --stopped-ok failed: $out"
[ "$(jq -c '[.ok, .convoys]' <<<"$out")" = '[true,[]]' ] || fail "the advance still walks a convoy: $(jq -c . <<<"$out")"
if "$CITY/bin/convoy-advance" --check-only >/dev/null 2>&1; then fail "the advance order still has a convoy to walk"; fi
observe "les deux convois marqués fermés par la commande"
echo "$(date -u +%H:%M:%S) convoy-state list : $("$CITY/bin/convoy-state" list | jq -c '{convoys, closed, closed_outside}') ; convoy-advance --all --stopped-ok : $(jq -c '{ok, convoys}' <<<"$out")"

echo "PASS: a marked convoy whose tickets are all closed stays open through the city's own convoy sweep, with its Spec and Draft; the unmarked one closes as before; a marked convoy closed by hand is raised on the escalation door's list; closed by command on « abandonné » or « accepté », it is closed in one tracker write, ruled, never reopened, and its Spec and Draft close with it"
