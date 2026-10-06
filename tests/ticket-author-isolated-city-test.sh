#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime, an isolated Dolt server and its own supervisor
#
# Adoption trial of the author formula (T12, af-i3q5a5; Spec af-wf4w5r §0
# rule 4, §4, §5) in a disposable city that shares nothing with the live
# Factory: its own GC_HOME, runtime directory, supervisor port, controller,
# evidence store and work trees. The product is a copy of the Delivery
# Fixture City, committed in the city root: the city is the repository of its
# one project, as the Factory is of its own (`rig_dir = "."`). The city has no
# Mayor.
#
# The tickets are started by the city's own order (bin/convoy-advance), on
# the real formula formulas/mol-ticket-author.formula.toml. The author is a
# scripted stub (it spends nothing): it claims each step Gas City routes to
# it, runs the real tools the step names, and closes the step. Whether the
# next step starts is decided by Gas City running bin/ticket-author-check.
#
# Three tickets of the fixture, three behaviours of the author:
#   A  walks the sequence: tests first, code, demonstration, exit « terminé ».
#   B  closes the red step without proving anything, each time it is given
#      back: the check stops it, the code step never starts.
#   C  finds that its demonstration line needs a behaviour the Spec fixes:
#      exit « Planning Exception » at the red step; the ticket is parked and
#      nothing of it is merged.
#
# The trial prints its record (« relevé d'essai ») on stdout.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
PORT="${TICKET_AUTHOR_TRIAL_PORT:-18397}"
CEILING=3
SPEC="fx-spec"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc bd jq git dolt tmux curl python3; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

TRIAL=$(mktemp -d /tmp/af-i3q5a5-author.XXXXXX)
CITY="$TRIAL/c"
PRODUCT="$CITY"
FIXTURE="tests/fixtures/delivery-fixture-city"
cleanup() {
  status=$?
  trap - EXIT
  gc --city "$CITY" stop >/dev/null 2>&1 || true
  gc supervisor stop >/dev/null 2>&1 || true
  tmux -L "$(basename "$TRIAL")" kill-server >/dev/null 2>&1 || true
  # The supervisor, the city's managed Dolt server, the stub sessions and a
  # product left launched carry the trial directory on their command line.
  pkill -f -- "$TRIAL/" >/dev/null 2>&1 || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    pgrep -f -- "$TRIAL/" >/dev/null 2>&1 || break
    sleep 0.3
  done
  pkill -9 -f -- "$TRIAL/" >/dev/null 2>&1 || true
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

# Nothing of the live Factory may reach this city (same recipe as
# tests/convoy-advance-isolated-city-test.sh).
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$|FACTORY_ROOT$|CONVOY_|DISPATCH_DOOR_|ESCALATION_DOOR_|EVIDENCE_|TICKET_AUTHOR_|SPEC_INTEGRATION_)' || true)
export GC_HOME="$TRIAL/h" XDG_RUNTIME_DIR="$TRIAL/r" GC_DISABLE_USAGE_METRICS=1
unset DBUS_SESSION_BUS_ADDRESS
export PATH="/usr/local/bin:$HOME/.local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
mkdir -p "$GC_HOME"
mkdir -m 700 "$XDG_RUNTIME_DIR"
printf '[supervisor]\nport = %s\n' "$PORT" > "$GC_HOME/supervisor.toml"

# What every tool of the flow reads, in the stub sessions, in the order and
# in the check alike: the city as Factory root, and stores of the trial.
cat > "$TRIAL/env" <<ENV
export FACTORY_ROOT="$CITY"
export CONVOY_STATE_LOCK_DIR="$TRIAL/locks" CONVOY_ADVANCE_LOCK_DIR="$TRIAL/locks" SPEC_INTEGRATION_LOCK_DIR="$TRIAL/locks"
export SPEC_INTEGRATION_WORK_DIR="$TRIAL/merge"
export EVIDENCE_STORE_DIR="$TRIAL/store" TICKET_AUTHOR_WORKTREES_DIR="$TRIAL/worktrees"
export ESCALATION_DOOR_LOCK_FILE="$TRIAL/escalation-door.lock" PROPOSAL_DOOR_BIN="$TRIAL/proposal-door"
export GIT_AUTHOR_NAME=essai GIT_AUTHOR_EMAIL=essai@example.invalid GIT_COMMITTER_NAME=essai GIT_COMMITTER_EMAIL=essai@example.invalid
ENV
printf '#!/bin/sh\necho 0\n' > "$TRIAL/proposal-door"
chmod +x "$TRIAL/proposal-door"
# shellcheck disable=SC1091
. "$TRIAL/env"

gc init --template minimal --default-provider claude --skip-provider-readiness \
  --no-start --yes --name "$(basename "$TRIAL")" "$CITY" >/dev/null 2>&1 \
  || fail "gc init of the isolated city failed"
sed -i '/^\[\[named_session\]\]$/,+2d' "$CITY/pack.toml"
rm -rf "$CITY/agents/mayor"

# --- the product: the Delivery Fixture City, the only thing committed ----------
mkdir -p "$PRODUCT/$(dirname "$FIXTURE")"
cp -R "$ROOT/$FIXTURE" "$PRODUCT/$FIXTURE"
git -C "$PRODUCT" init -q -b main
git -C "$PRODUCT" add -- "$FIXTURE"
git -C "$PRODUCT" commit -q -m "base"

# --- the scripted author ---------------------------------------------------------
cat > "$TRIAL/stub-author" <<STUB
#!/bin/bash
# Scripted author of the trial: one session, one ticket. It runs the real
# tools each step of mol-ticket-author names, then closes the step.
. "$TRIAL/env"
BIN="$ROOT/bin"
LOG="$TRIAL/author.log"
say() { echo "\$(date -u +%H:%M:%S) \${GC_SESSION_NAME:-?} \$*" >> "\$LOG"; }
tool() { "\$@" >> "\$LOG" 2>&1; }
while true; do
  CLAIM=\$(gc hook --claim --json 2>/dev/null)
  ACTION=\$(printf '%s' "\$CLAIM" | jq -r '.action // empty' 2>/dev/null)
  BEAD=\$(printf '%s' "\$CLAIM" | jq -r '.bead_id // empty' 2>/dev/null)
  if [ "\$ACTION" != work ] || [ -z "\$BEAD" ]; then sleep 3; continue; fi
  META=\$(gc bd show "\$BEAD" --json | jq -c '.[0].metadata')
  STEP=\$(printf '%s' "\$META" | jq -r '.["gc.step_id"]')
  ROOT_BEAD=\$(printf '%s' "\$META" | jq -r '.["gc.root_bead_id"]')
  INPUT=\$(gc bd show "\$ROOT_BEAD" --json | jq -r '.[0].metadata["gc.input_convoy_id"]')
  TICKET=\$(gc convoy status "\$INPUT" --json | jq -r '.children[0].id')
  MODE=\$(cat "$TRIAL/mode.\$TICKET")
  CONVOY=\$("\$BIN/ticket-author" locate "\$TICKET" | jq -r '.convoy')
  START=\$("\$BIN/ticket-author" start "\$CONVOY" "\$TICKET" 2>>"\$LOG")
  WT=\$(printf '%s' "\$START" | jq -r '.worktree'); BASE=\$(printf '%s' "\$START" | jq -r '.base')
  PROFILE=\$(printf '%s' "\$START" | jq -r '.profile')
  say "ticket \$TICKET (\$MODE) étape \$STEP"
  echo "\$TICKET \$STEP \${GC_SESSION_NAME:-?}" >> "$TRIAL/steps"
  EXITED=\$(gc bd show "\$TICKET" --json | jq -r '.[0].metadata["gc.flow.exit"] // empty')
  if [ -z "\$EXITED" ] || [ "\$STEP" = drain ]; then
    case "\$STEP:\$MODE" in
      red:honest)
        cp "$TRIAL/tests/"* "\$WT/$FIXTURE/tests/"
        git -C "\$WT" add -A; git -C "\$WT" commit -q -m "tests de critère"
        tool "\$BIN/tdd-step" red "\$CONVOY" "\$TICKET" --repo "\$WT" --profile "\$PROFILE" --dataset content --base "\$BASE" --table "$FIXTURE/tests/criteria.json"
        tool "\$BIN/tdd-step" freeze "\$CONVOY" "\$TICKET" --repo "\$WT" ;;
      red:skip-red)
        say "ferme l'étape rouge sans rien prouver" ;;
      red:exception)
        tool "\$BIN/ticket-exit" exit "\$CONVOY" "\$TICKET" --exit planning_exception --kind semantic \\
          --summary "La Spec fixe le libellé de la page, la ligne de démonstration en demande un autre" ;;
      code:honest)
        cp "$TRIAL/code/app.py" "\$WT/$FIXTURE/app.py"
        echo "Le produit affiche son nombre d'éléments." > "\$WT/README.md"
        git -C "\$WT" add -A; git -C "\$WT" commit -q -m "le nombre et le jeu"
        tool "\$BIN/tdd-step" green "\$CONVOY" "\$TICKET" --repo "\$WT" --profile "\$PROFILE" --dataset content ;;
      demonstration:honest)
        tool "\$BIN/ticket-author" demonstrate "\$CONVOY" "\$TICKET" --repo "\$WT" --profile "\$PROFILE" --dataset content \\
          -- sh -c 'curl -sf "\$PRODUCT_ADDRESS/" | grep -F "data-anchor=\\"fixture-count\\">3<"' ;;
      exit:honest)
        tool "\$BIN/ticket-exit" exit "\$CONVOY" "\$TICKET" --exit finished --repo "\$WT" --handoff "$TRIAL/handoff.json" ;;
      drain:*)
        tool "\$BIN/ticket-author" release "\$CONVOY" "\$TICKET"
        gc bd update "\$BEAD" --set-metadata gc.outcome=pass --status=closed --notes "Drain acknowledged." >/dev/null 2>&1
        say "ticket \$TICKET : session terminée"
        gc runtime drain-ack >/dev/null 2>&1
        exit 0 ;;
    esac
  fi
  gc bd update "\$BEAD" --set-metadata gc.outcome=pass --status=closed --notes "étape \$STEP close par l'auteur" >/dev/null 2>&1
done
STUB
chmod +x "$TRIAL/stub-author"

# What the honest author writes: the criterion tests, their table, the code.
mkdir -p "$TRIAL/tests" "$TRIAL/code"
cat > "$TRIAL/tests/test_count.py" <<'PY'
import os
import unittest
import urllib.request


class CountTest(unittest.TestCase):
    def test_count_is_shown(self):
        page = urllib.request.urlopen(os.environ["PRODUCT_ADDRESS"] + "/").read().decode()
        self.assertIn('<p data-anchor="fixture-count">3</p>', page)
PY
cat > "$TRIAL/tests/test_health.py" <<'PY'
import json
import os
import unittest
import urllib.request


class HealthTest(unittest.TestCase):
    def test_dataset_is_named(self):
        body = json.loads(urllib.request.urlopen(os.environ["PRODUCT_ADDRESS"] + "/health").read())
        self.assertEqual("content", body.get("dataset"))
PY
jq -n --arg t "$FIXTURE/tests" '{criteria: {"1": [$t + "/test_count.py::CountTest.test_count_is_shown"], "2": [$t + "/test_health.py::HealthTest.test_dataset_is_named"]}}' \
  > "$TRIAL/tests/criteria.json"
python3 - "$ROOT/$FIXTURE/app.py" "$TRIAL/code/app.py" <<'PY'
import sys
source = open(sys.argv[1], encoding="utf-8").read()
green = source.replace(
    '"</body></html>"', 'f\'<p data-anchor="fixture-count">{len(items)}</p>\'\n            "</body></html>"',
).replace('{"status": "ok"}', '{"status": "ok", "dataset": self.dataset.get("state")}')
assert green != source
open(sys.argv[2], "w", encoding="utf-8").write(green)
PY
jq -n '{done: ["Critères 1 et 2 observés ; la ligne se voit par GET / sur le jeu content."], deviations: "aucun", not_done: "aucun", out_of_ticket: "aucun"}' \
  > "$TRIAL/handoff.json"

# --- the city: one author agent on the stub, the real formula, the real order ---
cat > "$CITY/city.toml" <<TOML
[workspace]
provider = "stub"

[providers.stub]
base = "builtin:claude"
command = "$TRIAL/stub-author"
ready_delay_ms = 0
TOML
mkdir -p "$CITY/agents/trial-author" "$CITY/formulas" "$CITY/orders" "$CITY/config/projects" "$CITY/config/project-descriptors" "$CITY/bin"
cat > "$CITY/agents/trial-author/agent.toml" <<'TOML'
description = "Author of the ticket-author trial (scripted stub, spends nothing)"
scope = "city"
min_active_sessions = 0
max_active_sessions = 3
TOML
echo "Scripted author of the ticket-author trial." > "$CITY/agents/trial-author/prompt.template.md"
cp "$ROOT/formulas/mol-ticket-author.formula.toml" "$CITY/formulas/"
# The check path of the formula is read from the city root: the real check,
# with the stores of the trial.
cat > "$CITY/bin/ticket-author-check" <<WRAP
#!/bin/sh
. "$TRIAL/env"
echo "\$(date -u +%H:%M:%S) contrôle sur \$GC_BEAD_ID" >> "$TRIAL/checks.log"
"$ROOT/bin/ticket-author-check" 2>"$TRIAL/check.err" >> "$TRIAL/checks.log"; rc=\$?
cat "$TRIAL/check.err" >> "$TRIAL/checks.log"; cat "$TRIAL/check.err" >&2
exit \$rc
WRAP
chmod +x "$CITY/bin/ticket-author-check"
cat > "$CITY/config/projects/trial.toml" <<TOML
rig_dir = "."
repo = "example/trial"
protected_branch = "main"
required_ci = "CI"
sling_target = "trial-author"
formulas = "mol-ticket-author"
TOML
jq '.rigs = ["trial"]' "$ROOT/$FIXTURE/descriptor.json" > "$CITY/config/project-descriptors/trial.json"
jq -n --argjson n "$CEILING" '{contract: "agent-factory-delivery-flow/v1", max_sessions: $n, start: {formula: "mol-ticket-author", role: null}}' \
  > "$CITY/config/delivery-flow.json"
cp "$ROOT/config/delivery-roles.json" "$CITY/config/delivery-roles.json"

cat > "$TRIAL/advance" <<WRAP
#!/bin/sh
. "$TRIAL/env"
if [ "\$1" = "--check-only" ]; then
  exec "$ROOT/bin/convoy-advance" --check-only
fi
out=\$("$ROOT/bin/convoy-advance" "\$@"); rc=\$?
printf '%s' "\$out" | jq -c --arg at "\$(date -u +%H:%M:%S)" --argjson rc "\$rc" '{at: \$at, rc: \$rc} + .' >> "$TRIAL/passes.jsonl"
exit 0
WRAP
chmod +x "$TRIAL/advance"
sed "s#/home/benja/agent-factory/bin/convoy-advance#$TRIAL/advance#g" "$ROOT/orders/convoy-advance.toml" \
  > "$CITY/orders/convoy-advance.toml"

cd "$CITY"
state() {
  local out
  out=$("$ROOT/bin/convoy-state" "$@") || fail "convoy-state $* did not pass: $out"
  printf '%s' "$out"
}
new_ticket() {
  gc bd create --title "$1" --type task --silent --description "## What to build

Le nombre d'éléments et le nom du jeu de données.

## Acceptance criteria

- [ ] Point d'entrée : GET / — Observable : ancre fixture-count — Faux si : le nombre d'éléments n'y est pas
- [ ] Point d'entrée : GET /health — Observable : champ dataset — Faux si : le champ est absent

## Target rigs

trial" 2>/dev/null
}

CONVOY=$(gc bd create --title "convoi d'essai" --type convoy --silent 2>/dev/null)
gc bd update "$CONVOY" --set-metadata "gc.spec_id=$SPEC" >/dev/null
A=$(new_ticket "ticket A, auteur qui suit la séquence")
B=$(new_ticket "ticket B, auteur qui saute le rouge")
C=$(new_ticket "ticket C, Planning Exception")
ALL=("$A" "$B" "$C")
declare -A NAME=([$A]=A [$B]=B [$C]=C)
echo honest > "$TRIAL/mode.$A"; echo skip-red > "$TRIAL/mode.$B"; echo exception > "$TRIAL/mode.$C"
for t in "${ALL[@]}"; do
  gc bd dep add "$CONVOY" "$t" --type tracks >/dev/null
  # A declares a scope that leaves the README out; the others declare none.
  gc bd update "$t" --set-metadata gc.ticket_kind=vertical_slice >/dev/null
done
gc bd update "$A" --set-metadata "gc.scope_paths=$FIXTURE/tests/*,$FIXTURE/app.py" >/dev/null

echo "relevé d'essai — formule de l'auteur en cité isolée ($(gc version 2>/dev/null | head -1), N=$CEILING, aucun Mayor, auteur scripté)"
echo "convoi $CONVOY (Spec $SPEC) : A=$A (suit la séquence) B=$B (saute le rouge) C=$C (Planning Exception)"

(gc supervisor run > "$TRIAL/supervisor.out" 2>&1 &)
sleep 3
gc --city "$CITY" start >/dev/null 2>&1 || true
gc --city "$CITY" status 2>/dev/null | grep -q "Controller: supervisor-managed" || fail "the isolated city's controller did not start"
gc order show convoy-advance --json >/dev/null 2>&1 || fail "the city does not accept orders/convoy-advance.toml"
gc formula list 2>/dev/null | grep -q '^mol-ticket-author$' || fail "the city does not resolve formulas/mol-ticket-author.formula.toml"

state mark "$CONVOY" \
  --demonstration-line "$A=La page d'accueil affiche le nombre d'éléments" \
  --demonstration-line "$B=La page d'accueil affiche le nombre d'éléments" \
  --demonstration-line "$C=La page d'accueil affiche un autre libellé" \
  --user-stories "$A=1" --user-stories "$B=2" --user-stories "$C=3" >/dev/null
opened=$("$ROOT/bin/spec-integration" open "$CONVOY" --repo "$PRODUCT" --protected main) \
  || fail "spec-integration open did not pass: $opened"
INTEGRATION=$(git -C "$PRODUCT" rev-parse "integration/$SPEC")
echo "$(date -u +%H:%M:%S) marque posée, branche integration/$SPEC ouverte à $INTEGRATION"

flow() { gc bd show "$1" --json | jq -c '.[0].metadata'; }
field() { flow "$1" | jq -r --arg k "$2" '.[$k] // empty'; }
wait_for() { # <seconds> <command...>
  local deadline=$(( $(date +%s) + $1 )); shift
  until "$@"; do
    [ "$(date +%s)" -lt "$deadline" ] || return 1
    sleep 5
  done
}
step_seen() { grep -q "^$1 $2 " "$TRIAL/steps" 2>/dev/null; }
workflow_of() { # the mol-ticket-author root started on a ticket
  gc bd list --all --limit 0 --json 2>/dev/null | jq -r --arg t "$1" \
    '[.[] | select(.metadata["gc.kind"] == "workflow" and .metadata["gc.formula_name"] == "mol-ticket-author")] as $roots
     | $roots[] | select(.title | test("x") or true) | .id' | while IFS= read -r root; do
      input=$(gc bd show "$root" --json | jq -r '.[0].metadata["gc.input_convoy_id"] // empty')
      [ -n "$input" ] && [ "$(gc convoy status "$input" --json | jq -r '.children[0].id')" = "$1" ] && echo "$root"
    done | head -1
}
workflow_done() { [ "$(gc bd show "$1" --json | jq -r '.[0].status')" = closed ]; }

# --- every ticket is started by the order, each in a session of its own ---------
all_taken() { for t in "${ALL[@]}"; do step_seen "$t" workspace || return 1; done; }
wait_for 420 all_taken || fail "the three tickets were not all taken by an author session within 420s"
for t in "${ALL[@]}"; do
  [ "$(field "$t" gc.dispatched_via)" = dispatch-door ] || fail "${NAME[$t]} was not started through the dispatch door"
done
echo "$(date -u +%H:%M:%S) les trois tickets sont démarrés par l'ordre (bin/convoy-advance → bin/dispatch-door)"

# --- A: the whole sequence, to the exit « terminé » ------------------------------
a_finished() { [ "$(field "$A" gc.flow.exit | jq -r '.exit // empty' 2>/dev/null)" = finished ]; }
wait_for 900 a_finished || { tail -40 "$TRIAL/author.log" >&2; tail -20 "$TRIAL/checks.log" >&2; fail "A did not reach the exit « terminé » within 900s"; }
shown=$(state show "$CONVOY" --repo "$PRODUCT")
ticket() { printf '%s' "$shown" | jq -c --arg t "$1" '.tickets[] | select(.id == $t)'; }
a=$(ticket "$A")
tip=$(printf '%s' "$a" | jq -r '.tip')
[ "$(printf '%s' "$a" | jq -r '.branch')" = "ticket/$A" ] || fail "A does not carry its ticket branch"
git -C "$PRODUCT" merge-base --is-ancestor "$INTEGRATION" "$tip" || fail "the branch of A does not leave from the integration branch"
[ "$(git -C "$PRODUCT" rev-parse "$tip~2")" = "$INTEGRATION" ] || fail "the branch of A does not start at the tip of the integration branch"
for piece in tdd_red tdd_freeze tdd_green demonstration handoff_records; do
  printf '%s' "$a" | jq -e --arg p "$piece" '.evidence[$p].digest' >/dev/null || fail "A carries no fingerprint for the piece $piece"
  [ -f "$TRIAL/store/$SPEC/$A/$piece.json" ] || fail "the evidence store holds no piece $piece for A"
done
"$ROOT/bin/evidence-capture" verify "$CONVOY" "$A" >/dev/null || fail "the pieces of A do not verify"
[ "$(printf '%s' "$a" | jq -r '.evidence.demonstration.commit')" = "$tip" ] || fail "the demonstration of A is not at the head commit"
jq -e '.address != null and .exit_code == 0 and (.output | contains("fixture-count"))' "$TRIAL/store/$SPEC/$A/demonstration.json" >/dev/null \
  || fail "the demonstration piece of A was not captured on the launched product"
[ "$(printf '%s' "$a" | jq -c '.handoff.records.files_outside_declared_scope')" = '["README.md"]' ] \
  || fail "the Handoff of A does not record the file outside its Declared Scope"
session_a=$(printf '%s' "$a" | jq -r '.session.name')
echo "$(date -u +%H:%M:%S) A : sortie « terminé » ; session $session_a ; branche ticket/$A partie de integration/$SPEC ; preuves au magasin : rouge, gel, vert, démonstration (au commit de tête $tip), relevés ; hors scope relevé : README.md"

# --- B: the red step closed without proof is stopped by the check ---------------
root_b=""
find_b() { root_b=$(workflow_of "$B"); [ -n "$root_b" ] && workflow_done "$root_b"; }
wait_for 600 find_b || fail "the workflow of B did not end within 600s"
step_seen "$B" code && fail "the code step of B started although its red was never proven"
[ -z "$(field "$B" gc.flow.tdd.red)" ] || fail "B carries a red step nobody proved"
[ "$(gc bd show "$root_b" --json | jq -r '.[0].metadata["gc.outcome"]')" = fail ] || fail "the workflow of B did not end failed"
attempts_b=$(grep -c "^$B red " "$TRIAL/steps")
refusal_b=$(gc bd list --all --limit 0 --json | jq -r --arg r "$root_b" \
  '[.[] | select(.metadata["gc.root_bead_id"] == $r and .metadata["gc.step_id"] == "red" and (.metadata["gc.attempt_log"] != null))][0].metadata["gc.attempt_log"]')
printf '%s' "$refusal_b" | grep -q "étape rouge" || fail "the attempt log of B's red step does not carry the refusal of the gate: $refusal_b"
skipped_b=$(gc bd list --all --limit 0 --json | jq -r --arg r "$root_b" \
  '[.[] | select(.metadata["gc.root_bead_id"] == $r and .metadata["gc.outcome"] == "skipped" and (.metadata["gc.step_id"] // "" | IN("code","demonstration","exit"))) | .metadata["gc.step_id"]] | unique | join(",")')
echo "$(date -u +%H:%M:%S) B : étape rouge fermée $attempts_b fois sans preuve, refusée chaque fois par le contrôle (« étape rouge … n'est pas prouvée ») ; étapes sautées : $skipped_b ; le code n'a jamais commencé ; workflow en échec"

# --- C: Planning Exception -> parked, nothing merged ------------------------------
c_exited() { [ "$(field "$C" gc.flow.exit | jq -r '.exit // empty' 2>/dev/null)" = planning_exception ]; }
wait_for 300 c_exited || fail "C did not take the exit « Planning Exception » within 300s"
root_c=""
find_c() { root_c=$(workflow_of "$C"); [ -n "$root_c" ] && workflow_done "$root_c"; }
wait_for 600 find_c || fail "the workflow of C did not end within 600s"
shown=$(state show "$CONVOY" --repo "$PRODUCT")
c=$(ticket "$C")
[ "$(printf '%s' "$c" | jq -r '.park.cause')" = planning_exception ] || fail "C is not parked"
[ "$(printf '%s' "$c" | jq -r '.tip')" = "$INTEGRATION" ] || fail "the branch of C holds a commit"
[ "$(printf '%s' "$c" | jq -r '.merge')" = null ] || fail "C was merged"
"$ROOT/bin/escalation-door" list 2>/dev/null | grep -q "Planning Exception (semantic) sur $C" \
  || fail "the Planning Exception of C is not on the operator's list"
echo "$(date -u +%H:%M:%S) C : sortie « Planning Exception » à l'étape rouge ; ticket parqué ; demande sur la liste de l'opérateur ; sa branche ne porte aucun commit, rien n'est fusionné"

# --- one fresh session per ticket -------------------------------------------------
sessions=$(for t in "${ALL[@]}"; do grep "^$t workspace " "$TRIAL/steps" | head -1 | cut -d' ' -f3; done | sort -u | wc -l | tr -d ' ')
[ "$sessions" = 3 ] || fail "the three tickets were not worked by three distinct sessions ($sessions)"
gc session list --state all --json | jq -e '[.sessions[] | select(.template | test("mayor"))] | length == 0' >/dev/null \
  || fail "a Mayor session exists in the trial city"
echo "$(date -u +%H:%M:%S) trois tickets, trois sessions d'auteur distinctes, aucun Mayor"

# --- what the order then did with the finished ticket (observed, T18) -----------
sleep 45
merge=$(state show "$CONVOY" --repo "$PRODUCT" | jq -c --arg t "$A" '.tickets[] | select(.id == $t) | .merge')
echo "$(date -u +%H:%M:%S) relevé : fusion de A par l'ordre (bin/spec-integration) = $merge"
echo "PASS: mol-ticket-author, started by the city's own order, held the sequence of each ticket by script"
