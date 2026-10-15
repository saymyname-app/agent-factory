#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime, an isolated Dolt server, its own supervisor, bwrap and Node.js
#
# Adoption trial of the flow on the second project of the Delivery Fixture
# City (T35, af-f62cxt; Spec af-wf4w5r §12, user story 79): a JSON API on
# Node.js, another language than the first project and no web page
# (tests/fixtures/delivery-fixture-city-api). One of its tickets goes from
# « started » to « closed by the ticket-end gate » -- red, freeze, code,
# review, evaluation, merge -- by the same formulas and the same scripts as a
# ticket of the first project, in a disposable city that shares nothing with
# the live Factory: its own GC_HOME, runtime directory, supervisor port,
# controller, evidence store, launch records and work trees. The product is a
# copy of the second project, committed in the city root. The city has no
# Mayor.
#
# Nothing of the flow is told which project it works on: every tool reads the
# profile of the project (config/project-descriptors/trial.json, the
# descriptor of the fixture) -- its launch recipe, its probe, its test
# perimeter, its per-test test command, its seam mode, its regression command.
#
# What is real: the controller, the order that advances the convoy
# (bin/convoy-advance), which starts the ticket through the real
# bin/dispatch-door; the tracker (gc/bd); the formulas mol-ticket-author,
# mol-code-review and mol-ticket-evaluation; the check of each step of the
# author formula (bin/ticket-author check, materialised by
# bin/factory-build-gates); bin/ticket-author, bin/tdd-step (red, freeze,
# green, on tests written in JavaScript), bin/test-review, bin/ticket-exit,
# bin/code-review, bin/ticket-evaluation, bin/project-launch,
# bin/evidence-capture, bin/convoy-state, bin/spec-integration (the merge,
# with the regression command of the profile run on the merged result),
# bin/ticket-end and bin/delivery-role-sandbox (the Evaluator runs inside the
# read-only sandbox of its role). What is scripted, and spends nothing: the
# author, the reviewer and the Evaluator, three stubs that claim the step Gas
# City routes to them and run the real tools the step names (those of
# tests/ticket-author-isolated-city-test.sh and
# tests/ticket-end-isolated-city-test.sh); and the reviewer of the criterion
# tests between red and freeze, for which tests/fixtures/test-review/reviewer
# stands in for the dispatch door and the session (that role on a real
# controller is tried by tests/test-review-isolated-city-test.sh).
#
# The trial prints its record (« relevé d'essai ») on stdout.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
. "$ROOT/tests/lib/isolated-city.sh"
PORT="${SECOND_PROJECT_TRIAL_PORT:-18441}"
CEILING=4
APPROVER="essai-approbateur"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

# Not under /tmp: bin/delivery-role-sandbox gives a read-only role an empty
# /tmp, and the Evaluator of this trial runs inside it.
mkdir -p "$HOME/.cache"
TRIAL=$(mktemp -d "$HOME/.cache/af-f62cxt-second-project.XXXXXX")
CITY="$TRIAL/c"
PRODUCT="$CITY"
FIXTURE="tests/fixtures/delivery-fixture-city-api"
cleanup() {
  status=$?
  trap - EXIT
  isolated_city_stop "$TRIAL" "$CITY" >/dev/null 2>&1 || true
  tmux -L "$(basename "$TRIAL")" kill-server >/dev/null 2>&1 || true
  # A product an evaluation launched and that no pass stopped.
  if [ -d "$TRIAL/launches" ]; then
    while IFS= read -r record; do
      "$ROOT/bin/project-launch" stop --state-file "$record" >/dev/null 2>&1 || true
    done < <(find "$TRIAL/launches" -name '*.json' 2>/dev/null)
  fi
  # The supervisor, the city's managed Dolt server and the stub sessions
  # carry the trial directory on their command line.
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
    git -C "$PRODUCT" worktree prune >/dev/null 2>&1 || true
    rm -rf -- "$TRIAL"
  fi
  exit "$status"
}
trap cleanup EXIT

# Nothing of the live Factory may reach this city (same recipe as
# tests/ticket-end-isolated-city-test.sh).
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$|FACTORY_ROOT$|CONVOY_|DISPATCH_DOOR_|ESCALATION_DOOR_|EVIDENCE_|TICKET_AUTHOR_|SPEC_INTEGRATION_|TEST_REVIEW_|CODE_REVIEW_(DISPATCH|FAKE)|TICKET_EVALUATION_(DISPATCH|FAKE|STATE)|CORRECTION_ROUND_(DISPATCH|FAKE)|PROJECT_PLANNING_PROFILE_BIN$|DELIVERY_ROLE_)' || true)
export GC_HOME="$TRIAL/h" XDG_RUNTIME_DIR="$TRIAL/r" GC_DISABLE_USAGE_METRICS=1
unset DBUS_SESSION_BUS_ADDRESS
export PATH="/usr/local/bin:$HOME/.local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
mkdir -p "$GC_HOME"
mkdir -m 700 "$XDG_RUNTIME_DIR"
printf '[supervisor]\nport = %s\n' "$PORT" > "$GC_HOME/supervisor.toml"

# After the PATH of the trial is set: the interpreter of the second project
# is found on it by the launcher, the test command and the regression command.
for required in gc bd jq git dolt tmux curl python3 bwrap node; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

# What every tool of the flow reads, in the stub sessions, in the order and
# in the check alike: the city as Factory root, and stores of the trial. The
# dispatch door is the real one; it asks these stubs where a role runs and
# whether its adoption trial passed (the stubs of this city are no provider
# to try).
cat > "$TRIAL/env" <<ENV
export TRIAL="$TRIAL" BIN="$ROOT/bin" PRODUCT="$PRODUCT" FIXTURE="$FIXTURE"
export FACTORY_ROOT="$CITY"
export CONVOY_STATE_LOCK_DIR="$TRIAL/locks" CONVOY_ADVANCE_LOCK_DIR="$TRIAL/locks" SPEC_INTEGRATION_LOCK_DIR="$TRIAL/locks"
export SPEC_INTEGRATION_WORK_DIR="$TRIAL/merge"
export EVIDENCE_STORE_DIR="$TRIAL/store"
export EVIDENCE_PACK_DIR="$TRIAL/packs"
export TICKET_EVALUATION_STATE_DIR="$TRIAL/launches"
export TICKET_AUTHOR_WORKTREES_DIR="$TRIAL/wt"
export ESCALATION_DOOR_LOCK_FILE="$TRIAL/escalation-door.lock" PROPOSAL_DOOR_BIN="$TRIAL/proposal-door"
export DISPATCH_DOOR_PROVIDER_FAILOVER_BIN="$TRIAL/provider-failover" DISPATCH_DOOR_ROLE_TRIAL_BIN="$TRIAL/role-adoption-trial"
export DELIVERY_ROLE_PROVIDER_FAILOVER_BIN="$TRIAL/provider-failover"
export GC_BIN=gc TEST_REVIEW_DISPATCH_DOOR_BIN="$ROOT/tests/fixtures/test-review/reviewer" TEST_REVIEW_POLL_SECONDS=1
export TEST_REVIEW_FAKE_LOG="$TRIAL/review-door.log" TEST_REVIEW_FAKE_PLAN="$TRIAL/review-plan.json" TEST_REVIEW_FAKE_REPO="$CITY"
export GIT_AUTHOR_NAME=essai GIT_AUTHOR_EMAIL=essai@example.invalid GIT_COMMITTER_NAME=essai GIT_COMMITTER_EMAIL=essai@example.invalid
ENV
printf '#!/bin/sh\necho 0\n' > "$TRIAL/proposal-door"
cat > "$TRIAL/provider-failover" <<'SH'
#!/bin/sh
printf '%s\n' '{"total_exhaustion": {"active": false}, "targets": {"trial-author": {"effective": "stub-author"}, "trial-reviewer": {"effective": "stub-reviewer"}, "trial-evaluator": {"effective": "stub-evaluator", "chain": [{"provider": "stub-evaluator", "state": "available", "pool": "fournisseur-essai"}]}}}'
SH
printf '#!/bin/sh\nexit 0\n' > "$TRIAL/role-adoption-trial"
chmod +x "$TRIAL/proposal-door" "$TRIAL/provider-failover" "$TRIAL/role-adoption-trial"
echo '["favorable"]' > "$TRIAL/review-plan.json"
# shellcheck disable=SC1091
. "$TRIAL/env"

gc init --template minimal --default-provider claude --skip-provider-readiness \
  --no-start --yes --name "$(basename "$TRIAL")" "$CITY" >/dev/null 2>&1 \
  || fail "gc init of the isolated city failed"
sed -i '/^\[\[named_session\]\]$/,+2d' "$CITY/pack.toml"
rm -rf "$CITY/agents/mayor"

# --- the product: the second project of the fixture, the only thing committed ---
mkdir -p "$PRODUCT/$(dirname "$FIXTURE")"
cp -R "$ROOT/$FIXTURE" "$PRODUCT/$FIXTURE"
git -C "$PRODUCT" init -q -b main
git -C "$PRODUCT" add -- "$FIXTURE"
git -C "$PRODUCT" commit -q -m "base"

# What the author writes: the criterion tests, in the language of the
# project, their table, then the code.
mkdir -p "$TRIAL/tests" "$TRIAL/code"
cat > "$TRIAL/tests/count.test.js" <<'JS'
'use strict';
const assert = require('node:assert');

module.exports = {
  async count_is_answered() {
    const body = await (await fetch(process.env.PRODUCT_ADDRESS + '/items')).json();
    assert.strictEqual(body.count, 3);
  },
};
JS
cat > "$TRIAL/tests/health.test.js" <<'JS'
'use strict';
const assert = require('node:assert');

module.exports = {
  async dataset_is_named() {
    const body = await (await fetch(process.env.PRODUCT_ADDRESS + '/health')).json();
    assert.strictEqual(body.dataset, 'content');
  },
};
JS
jq -n --arg t "$FIXTURE/tests" '{criteria: {"1": [$t + "/count.test.js::count_is_answered"], "2": [$t + "/health.test.js::dataset_is_named"]}}' \
  > "$TRIAL/tests/criteria.json"
python3 - "$ROOT/$FIXTURE/server.js" "$TRIAL/code/server.js" <<'PY'
import sys
source = open(sys.argv[1], encoding="utf-8").read()
shown = "    state: String(dataset.state ?? ''),"
probe = "{ status: 'ok' }"
assert shown in source and probe in source
green = source.replace(shown, shown + "\n    count: Array.isArray(dataset.items) ? dataset.items.length : 0,") \
    .replace(probe, "{ status: 'ok', dataset: String(dataset.state) }")
open(sys.argv[2], "w", encoding="utf-8").write(green)
PY
jq -n '{done: ["Critères 1 et 2 observés ; la ligne se voit par GET /items sur le jeu content."], deviations: "aucun", not_done: "aucun", out_of_ticket: "aucun"}' \
  > "$TRIAL/handoff.json"

# One stub per role: the header names the trial, the body is the session.
stub() { # <name>: reads the body on stdin
  printf '#!/bin/bash\n. "%s/env"\n' "$TRIAL" > "$TRIAL/$1"
  cat >> "$TRIAL/$1"
  chmod +x "$TRIAL/$1"
}

# --- the scripted author ---------------------------------------------------------
# One session, one ticket: it runs the real tools each step of
# mol-ticket-author names, then closes the step. Whether the next step starts
# is decided by Gas City running the check of the formula.
stub stub-author <<'STUB'
LOG="$TRIAL/author.log"
say() { echo "$(date -u +%H:%M:%S) ${GC_SESSION_NAME:-?} $*" >> "$LOG"; }
tool() { "$@" >> "$LOG" 2>&1; }
echo "stub> " # the prompt its provider declares: the start of the session waits for it
while true; do
  CLAIM=$(gc hook --claim --json 2>/dev/null)
  ACTION=$(printf '%s' "$CLAIM" | jq -r '.action // empty' 2>/dev/null)
  BEAD=$(printf '%s' "$CLAIM" | jq -r '.bead_id // empty' 2>/dev/null)
  if [ "$ACTION" != work ] || [ -z "$BEAD" ]; then sleep 3; continue; fi
  META=$(gc bd show "$BEAD" --json | jq -c '.[0].metadata')
  STEP=$(printf '%s' "$META" | jq -r '.["gc.step_id"]')
  ROOT_BEAD=$(printf '%s' "$META" | jq -r '.["gc.root_bead_id"]')
  INPUT=$(gc bd show "$ROOT_BEAD" --json | jq -r '.[0].metadata["gc.input_convoy_id"]')
  TICKET=$(gc convoy status "$INPUT" --json | jq -r '.children[0].id')
  CONVOY=$("$BIN/ticket-author" locate "$TICKET" | jq -r '.convoy')
  START=$("$BIN/ticket-author" start "$CONVOY" "$TICKET" 2>>"$LOG")
  WT=$(printf '%s' "$START" | jq -r '.worktree'); BASE=$(printf '%s' "$START" | jq -r '.base')
  PROFILE=$(printf '%s' "$START" | jq -r '.profile')
  say "ticket $TICKET étape $STEP"
  echo "$TICKET $STEP ${GC_SESSION_NAME:-?}" >> "$TRIAL/steps"
  EXITED=$(gc bd show "$TICKET" --json | jq -r '.[0].metadata["gc.flow.exit"] // empty')
  if [ -z "$EXITED" ] || [ "$STEP" = drain ]; then
    case "$STEP" in
      red)
        cp "$TRIAL/tests/"* "$WT/$FIXTURE/tests/"
        git -C "$WT" add -A; git -C "$WT" commit -q -m "tests de critère"
        tool "$BIN/tdd-step" red "$CONVOY" "$TICKET" --repo "$WT" --profile "$PROFILE" --dataset content --base "$BASE" --table "$FIXTURE/tests/criteria.json"
        tool "$BIN/test-review" review "$CONVOY" "$TICKET" --repo "$WT" --wait 60
        tool "$BIN/tdd-step" freeze "$CONVOY" "$TICKET" --repo "$WT" ;;
      code)
        cp "$TRIAL/code/server.js" "$WT/$FIXTURE/server.js"
        git -C "$WT" add -A; git -C "$WT" commit -q -m "le nombre et le jeu"
        tool "$BIN/tdd-step" green "$CONVOY" "$TICKET" --repo "$WT" --profile "$PROFILE" --dataset content ;;
      demonstration)
        tool "$BIN/ticket-author" demonstrate "$CONVOY" "$TICKET" --repo "$WT" --profile "$PROFILE" --dataset content \
          -- sh -c 'curl -sf "$PRODUCT_ADDRESS/items" | grep -F "\"count\":3"' ;;
      exit)
        tool "$BIN/ticket-exit" exit "$CONVOY" "$TICKET" --exit finished --repo "$WT" --handoff "$TRIAL/handoff.json" ;;
      drain)
        tool "$BIN/ticket-author" release "$CONVOY" "$TICKET"
        gc bd update "$BEAD" --set-metadata gc.outcome=pass --status=closed --notes "Drain acknowledged." >/dev/null 2>&1
        say "ticket $TICKET : session terminée"
        gc runtime drain-ack >/dev/null 2>&1
        exit 0 ;;
    esac
  fi
  gc bd update "$BEAD" --set-metadata gc.outcome=pass --status=closed --notes "étape $STEP close par l'auteur" >/dev/null 2>&1
done
STUB

# --- the scripted reviewer --------------------------------------------------------
# One session, one round, as the step of mol-code-review asks: it reads the
# diff the brief names and finds nothing the Spec contradicts.
stub stub-reviewer <<'STUB'
export DELIVERY_ROLE_READ_ONLY=1
LOG="$TRIAL/reviewer.log"
say() { echo "$(date -u +%H:%M:%S) ${GC_SESSION_NAME:-?} $*" >> "$LOG"; }
echo "stub> "
while true; do
  CLAIM=$(gc hook --claim --json 2>/dev/null)
  ACTION=$(printf '%s' "$CLAIM" | jq -r '.action // empty' 2>/dev/null)
  BEAD=$(printf '%s' "$CLAIM" | jq -r '.bead_id // empty' 2>/dev/null)
  if [ "$ACTION" != work ] || [ -z "$BEAD" ]; then sleep 3; continue; fi
  ROOT_BEAD=$(gc bd show "$BEAD" --json | jq -r '.[0].metadata["gc.root_bead_id"]')
  INPUT=$(gc bd show "$ROOT_BEAD" --json | jq -r '.[0].metadata["gc.input_convoy_id"]')
  REVIEW_BEAD=$(gc convoy status "$INPUT" --json | jq -r '.children[0].id')
  TEXT=$(gc bd show "$REVIEW_BEAD" --json | jq -r '.[0].description')
  CONVOY=$(printf '%s\n' "$TEXT" | sed -n 's/^convoy: //p'); TICKET=$(printf '%s\n' "$TEXT" | sed -n 's/^ticket: //p')
  OUTCOME=pass
  BRIEF="$TRIAL/review-brief.$REVIEW_BEAD.json"
  if ! "$BIN/code-review" brief "$CONVOY" "$TICKET" > "$BRIEF.new" 2>>"$LOG"; then
    # Seen on gc 1.4.1: a session is started again on the step it just
    # closed. Nothing is asked any more, and nothing is written.
    say "ticket $TICKET : aucune revue demandée ($REVIEW_BEAD), rien à faire"
    rm -f "$BRIEF.new"
    gc runtime drain-ack >/dev/null 2>&1
    exit 0
  fi
  mv "$BRIEF.new" "$BRIEF"
  KIND=$(jq -r '.kind' "$BRIEF")
  RESULT="$TRIAL/review-result.$REVIEW_BEAD.json"
  sh -c "$(jq -r '.diff.command' "$BRIEF")" > "$TRIAL/review-diff.$REVIEW_BEAD" 2>>"$LOG" || OUTCOME=fail
  echo "$TICKET $REVIEW_BEAD ${GC_SESSION_NAME:-?} $KIND $(jq -r '.commit' "$BRIEF") $(grep -c '^+++ ' "$TRIAL/review-diff.$REVIEW_BEAD")" >> "$TRIAL/review-sessions"
  if [ "$KIND" = judgement ]; then
    jq '{commit, judgements: (.findings | map({key: .id, value: {state: "favorable"}}) | from_entries)}' "$BRIEF" > "$RESULT"
  else
    jq '{commit, findings: [], answers: (.questions | map({key: .id, value: {answer: "oui"}}) | from_entries)}' "$BRIEF" > "$RESULT"
  fi
  "$BIN/code-review" record "$CONVOY" "$TICKET" --file "$RESULT" >> "$LOG" 2>&1 || OUTCOME=fail
  say "ticket $TICKET : $KIND remis ($REVIEW_BEAD, $OUTCOME)"
  gc bd update "$REVIEW_BEAD" --set-metadata gc.outcome=$OUTCOME --status=closed --notes "revue $OUTCOME" >/dev/null 2>&1
  gc bd update "$BEAD" --set-metadata gc.outcome=$OUTCOME --status=closed --notes "revue $OUTCOME" >/dev/null 2>&1
  gc runtime drain-ack >/dev/null 2>&1
  exit 0
done
STUB

# --- the scripted Evaluator ---------------------------------------------------------
# One session, one evaluation, as the step of mol-ticket-evaluation asks: for
# each criterion and for the demonstration line, the answer of the entry
# point the criterion names, captured on the launched product; « observed »
# when the answer holds the field asked, « not_observed » otherwise. It runs
# inside bin/delivery-role-sandbox. The product has no page: what is captured
# is the JSON body of its API.
stub stub-evaluator-inner <<'STUB'
LOG="$TRIAL/evaluator.log"
say() { echo "$(date -u +%H:%M:%S) ${GC_SESSION_NAME:-?} $*" >> "$LOG"; }
echo "stub> "
while true; do
  CLAIM=$(gc hook --claim --json 2>/dev/null)
  ACTION=$(printf '%s' "$CLAIM" | jq -r '.action // empty' 2>/dev/null)
  BEAD=$(printf '%s' "$CLAIM" | jq -r '.bead_id // empty' 2>/dev/null)
  if [ "$ACTION" != work ] || [ -z "$BEAD" ]; then sleep 3; continue; fi
  ROOT_BEAD=$(gc bd show "$BEAD" --json | jq -r '.[0].metadata["gc.root_bead_id"]')
  INPUT=$(gc bd show "$ROOT_BEAD" --json | jq -r '.[0].metadata["gc.input_convoy_id"]')
  EVALUATION_BEAD=$(gc convoy status "$INPUT" --json | jq -r '.children[0].id')
  TEXT=$(gc bd show "$EVALUATION_BEAD" --json | jq -r '.[0].description')
  CONVOY=$(printf '%s\n' "$TEXT" | sed -n 's/^convoy: //p'); TICKET=$(printf '%s\n' "$TEXT" | sed -n 's/^ticket: //p')
  OUTCOME=pass
  BRIEF="$TRIAL/evaluation-brief.$EVALUATION_BEAD.json"
  if ! "$BIN/ticket-evaluation" brief "$CONVOY" "$TICKET" > "$BRIEF.new" 2>>"$LOG"; then
    say "ticket $TICKET : aucune évaluation demandée ($EVALUATION_BEAD), rien à faire"
    rm -f "$BRIEF.new"
    gc runtime drain-ack >/dev/null 2>&1
    exit 0
  fi
  mv "$BRIEF.new" "$BRIEF"
  product_on() {
    local answer deadline=$(( $(date +%s) + 300 ))
    while true; do
      answer=$("$BIN/ticket-evaluation" product "$CONVOY" "$TICKET" --dataset "$1" 2>>"$LOG") || return 1
      if [ "$(printf '%s' "$answer" | jq -r '.ready')" = true ]; then
        ADDRESS=$(printf '%s' "$answer" | jq -r '.address')
        LAUNCH=$(printf '%s' "$answer" | jq -r '.launch_state')
        return 0
      fi
      [ "$(date +%s)" -lt "$deadline" ] || return 1
      sleep 2
    done
  }
  covered() {
    "$BIN/evidence-capture" command "$CONVOY" "$TICKET" --piece "evaluation.coverage.$1" --launch-state "$LAUNCH" -- curl -s "$ADDRESS/health" >/dev/null 2>>"$LOG" || return 1
    jq -n --arg dataset "$1" '{dataset: $dataset, evidence: ("evaluation.coverage." + $dataset)}'
  }
  product_on content || OUTCOME=fail
  echo "$TICKET $EVALUATION_BEAD ${GC_SESSION_NAME:-?} $(jq -r '.commit' "$BRIEF")" >> "$TRIAL/evaluation-sessions"
  state_of() { # <piece> <text>: capture the answer of the entry point the text names, print the state as JSON
    local captured body path=/items field='"count":3'
    case "$2" in *"GET /health"*) path=/health; field='"dataset":"content"' ;; esac
    captured=$("$BIN/evidence-capture" command "$CONVOY" "$TICKET" --piece "$1" --launch-state "$LAUNCH" -- curl -s "$ADDRESS$path" 2>>"$LOG") || return 1
    body=$(jq -r '.output' "$(printf '%s' "$captured" | jq -r '.path')")
    if printf '%s' "$body" | grep -qF "$field"; then
      jq -n --arg text "$2" --arg piece "$1" '{text: $text, state: "observed", evidence: $piece}'
    else
      jq -n --arg text "$2" --arg piece "$1" --arg reason "la réponse de GET $path ne porte pas $field" \
        '{text: $text, state: "not_observed", evidence: $piece, reason: $reason}'
    fi
  }
  RESULT="$TRIAL/evaluation-result.$EVALUATION_BEAD.json"
  CRITERIA='[]'
  while IFS= read -r criterion; do
    NUMBER=$(printf '%s' "$criterion" | jq -r '.number')
    STATE=$(state_of "evaluation.c$NUMBER" "$(printf '%s' "$criterion" | jq -r '.text')") || OUTCOME=fail
    CRITERIA=$(jq -c --argjson n "$NUMBER" --argjson s "${STATE:-null}" '. + [{number: $n} + $s]' <<< "$CRITERIA")
  done < <(jq -c '.criteria[]' "$BRIEF")
  LINE=$(state_of evaluation.demo "$(jq -r '.demonstration_line' "$BRIEF")") || OUTCOME=fail
  COVERAGE=$(covered content) || OUTCOME=fail
  COVERAGE="[${COVERAGE:-null}]"
  while IFS= read -r dataset; do
    [ "$dataset" = content ] && continue
    ENTRY=$(product_on "$dataset" && covered "$dataset") || OUTCOME=fail
    COVERAGE=$(jq -c --argjson e "${ENTRY:-null}" '. + [$e]' <<< "$COVERAGE")
  done < <(jq -r '.datasets[]' "$BRIEF")
  jq --argjson criteria "$CRITERIA" --argjson line "${LINE:-null}" --argjson coverage "$COVERAGE" '{commit, criteria: $criteria, demonstration_line: $line, coverage: $coverage}' "$BRIEF" > "$RESULT"
  "$BIN/ticket-evaluation" record "$CONVOY" "$TICKET" --file "$RESULT" >> "$LOG" 2>&1 || OUTCOME=fail
  say "ticket $TICKET : états remis ($EVALUATION_BEAD, $OUTCOME)"
  gc bd update "$EVALUATION_BEAD" --set-metadata gc.outcome=$OUTCOME --status=closed --notes "évaluation $OUTCOME" >> "$LOG" 2>&1 || say "fermeture du bead d'évaluation refusée"
  gc bd update "$BEAD" --set-metadata gc.outcome=$OUTCOME --status=closed --notes "évaluation $OUTCOME" >> "$LOG" 2>&1 || say "fermeture de l'étape refusée"
  gc runtime drain-ack >> "$LOG" 2>&1 || say "drain-ack refusé"
  exit 0
done
STUB
cat > "$TRIAL/stub-evaluator" <<STUB
#!/bin/bash
# The provider of a read-only role: its command is the sandbox, which
# launches the real binary named in DELIVERY_ROLE_SANDBOX_EXEC.
export DELIVERY_ROLE_SANDBOX_EXEC="$TRIAL/stub-evaluator-inner"
exec "$ROOT/bin/delivery-role-sandbox"
STUB
chmod +x "$TRIAL/stub-evaluator"

# --- the city: one agent per role on its stub, the real formulas, the real order ----
cat > "$CITY/city.toml" <<TOML
[workspace]
provider = "stub-reviewer"

[providers.stub-author]
base = "builtin:claude"
command = "$TRIAL/stub-author"
# A stub is a shell script: without its process name Gas City finds no
# \`claude\` process in the session and reaps it as a zombie.
process_names = ["stub-author", "bash"]
ready_delay_ms = 0
# A stub shows no startup dialog and no prompt. Left to the claude base, the
# start of a session waits for both, about 40 s on a quiet host against the
# 60 s Gas City gives a start: under load the start times out
# (session.cold_start_timeout) and the session that holds the ticket is
# replaced by a new one, step after step.
accept_startup_dialogs = false
ready_prompt_prefix = "stub>"

[providers.stub-reviewer]
base = "builtin:claude"
command = "$TRIAL/stub-reviewer"
process_names = ["stub-reviewer", "bash"]
ready_delay_ms = 0
accept_startup_dialogs = false
ready_prompt_prefix = "stub>"

[providers.stub-evaluator]
base = "builtin:claude"
command = "$TRIAL/stub-evaluator"
process_names = ["stub-evaluator", "stub-evaluator-inner", "bwrap", "bash"]
ready_delay_ms = 0
accept_startup_dialogs = false
ready_prompt_prefix = "stub>"
TOML
mkdir -p "$CITY/formulas" "$CITY/orders" "$CITY/config/projects" "$CITY/config/project-descriptors" "$CITY/bin" "$CITY/assets/scripts/checks"
for role in author reviewer evaluator; do
  mkdir -p "$CITY/agents/trial-$role"
  cat > "$CITY/agents/trial-$role/agent.toml" <<TOML
description = "Role $role of the second-project trial (scripted stub, spends nothing)"
scope = "city"
min_active_sessions = 0
max_active_sessions = 2
provider = "stub-$role"
TOML
  echo "Scripted $role of the second-project trial." > "$CITY/agents/trial-$role/prompt.template.md"
done
# The work query of the author is the one of the real author agent: it is
# what keeps a session that holds a ticket from taking a step of another one.
query=$(grep '^work_query = ' "$ROOT/agents/delivery-author/agent.toml") || fail "the author agent declares no work_query"
printf '%s\n' "${query//-- delivery-author/-- trial-author}" >> "$CITY/agents/trial-author/agent.toml"
for formula in mol-ticket-author mol-code-review mol-ticket-evaluation mol-ticket-correction; do
  cp "$ROOT/formulas/$formula.formula.toml" "$CITY/formulas/"
done
# The check of the author formula is the real one, materialised below by the
# real bin/factory-build-gates. It runs `bin/ticket-author check` of the city
# root: here the real tool, with the stores of the trial.
cp "$ROOT/assets/scripts/checks/ticket-author-check.sh" "$CITY/assets/scripts/checks/"
cat > "$CITY/bin/ticket-author" <<WRAP
#!/bin/sh
. "$TRIAL/env"
echo "\$(date -u +%H:%M:%S) contrôle sur \$GC_BEAD_ID" >> "$TRIAL/checks.log"
"$ROOT/bin/ticket-author" "\$@" 2>"$TRIAL/check.err" >> "$TRIAL/checks.log"; rc=\$?
cat "$TRIAL/check.err" >> "$TRIAL/checks.log"; cat "$TRIAL/check.err" >&2
exit \$rc
WRAP
chmod +x "$CITY/bin/ticket-author"
cat > "$CITY/config/projects/trial.toml" <<TOML
rig_dir = "."
repo = "example/trial"
protected_branch = "main"
required_ci = "CI"
sling_target = "trial-author"
formulas = "mol-ticket-author,mol-code-review,mol-ticket-evaluation,mol-ticket-correction"
human_approver = "$APPROVER"
TOML
# The profile of the project is the descriptor of the fixture, whole: only
# the rig it names is the one of this city.
jq '.rigs = ["trial"] | .stacks = {"trial": ["fixture-stack"]}' "$ROOT/$FIXTURE/descriptor.json" > "$CITY/config/project-descriptors/trial.json"
jq -n --argjson n "$CEILING" '{contract: "agent-factory-delivery-flow/v1", max_sessions: $n,
  start: {formula: "mol-ticket-author", role: "author"},
  test_review: {formula: "mol-test-review", role: "reviewer", rig: "trial", timeout_seconds: 600},
  code_review: {formula: "mol-code-review", role: "reviewer", rig: "trial", timeout_seconds: 600},
  evaluation: {formula: "mol-ticket-evaluation", role: "evaluator", rig: "trial", timeout_seconds: 600, start_timeout_seconds: 30},
  correction: {formula: "mol-ticket-correction", role: "author", rig: "trial"}}' \
  > "$CITY/config/delivery-flow.json"
jq '.roles.author.agent = "trial-author" | .roles.reviewer.agent = "trial-reviewer" | .roles.evaluator.agent = "trial-evaluator"' \
  "$ROOT/config/delivery-roles.json" > "$CITY/config/delivery-roles.json"
jq -n '{providers: {"stub-author": {recommended: ["modele-auteur"]}, "stub-reviewer": {recommended: ["modele-relecteur"]},
                    "stub-evaluator": {recommended: ["modele-evaluateur"]}}}' > "$CITY/config/model-catalog.json"
jq -n '{providers: {"stub-author": {pool: "fournisseur-essai"}, "stub-evaluator": {pool: "fournisseur-essai"}}}' \
  > "$CITY/config/provider-policy.json"

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
LINE="Sur le jeu content, GET /items répond count = 3"
SPEC=$(gc bd create --title "Spec d'essai" --type task --silent --description "## User Stories

1. As a client de l'API, I want le nombre d'éléments dans la réponse de GET /items, so that je n'aie pas à les compter.

## Testing Decisions

Seams : GET /items et GET /health." 2>/dev/null)
gc bd update "$SPEC" --status closed >/dev/null 2>&1 || true
CONVOY=$(gc bd create --title "convoi d'essai" --type convoy --silent 2>/dev/null)
gc bd update "$CONVOY" --set-metadata "gc.spec_id=$SPEC" >/dev/null
T=$(gc bd create --title "ticket du second projet" --type task --silent --description "## What to build

Le nombre d'éléments et le nom du jeu de données.

## Acceptance criteria

- [ ] Point d'entrée : GET /items — Observable : champ count — Faux si : le nombre d'éléments n'y est pas
- [ ] Point d'entrée : GET /health — Observable : champ dataset — Faux si : le champ est absent

## Target rigs

trial" 2>/dev/null)
gc bd dep add "$CONVOY" "$T" --type tracks >/dev/null
gc bd update "$T" --set-metadata gc.ticket_kind=vertical_slice >/dev/null

profile=$("$ROOT/bin/project-planning-profile" describe "$CITY/config/project-descriptors/trial.json")
echo "relevé d'essai — le flux sur le second projet de la fixture ; cité isolée ($(gc version 2>/dev/null | head -1), N=$CEILING, aucun Mayor ; auteur, relecteur et Evaluator scriptés, qui lancent les vrais outils ; vrai contrôleur, vrai ordre, vraie porte de dispatch, vraies formules, vrais scripts rouge, gel et vert, vrai lancement du produit, vraie fusion, vraie porte de fin de ticket)"
echo "projet : $(printf '%s' "$profile" | jq -r '.project_id') ; recette de lancement : $(printf '%s' "$profile" | jq -r '.launch.recipe | join(" ")') ; commande de test : $(printf '%s' "$profile" | jq -r '.launch.test_command') ; seam : $(printf '%s' "$profile" | jq -r '.launch.seam_mode') ; écrans : $(printf '%s' "$profile" | jq -c '.launch.screens // "aucun"') ; équivalent des ancres : $(printf '%s' "$profile" | jq -c '[.launch.anchors.equivalent[].name]') ; $(node --version | sed 's/^/Node.js /')"
echo "convoi $CONVOY (Spec $SPEC) : ticket $T"

(gc supervisor run > "$TRIAL/supervisor.out" 2>&1 &)
sleep 3
gc --city "$CITY" start >/dev/null 2>&1 || true
grep -q "Controller: supervisor-managed" <<<"$(gc --city "$CITY" status 2>/dev/null)" || fail "the isolated city's controller did not start"
gc order show convoy-advance --json >/dev/null 2>&1 || fail "the city does not accept orders/convoy-advance.toml"
grep -q '^mol-ticket-author$' <<<"$(gc formula list 2>/dev/null)" || fail "the city does not resolve formulas/mol-ticket-author.formula.toml"
gates=$("$ROOT/bin/factory-build-gates" --root "$CITY") || fail "factory-build-gates did not materialise the check of the formula: $gates"
[ -x "$CITY/.gc/scripts/checks/ticket-author-check.sh" ] || fail "the check of the formula is not in the city root: $gates"

state mark "$CONVOY" --demonstration-line "$T=$LINE" --user-stories "$T=1" >/dev/null
opened=$("$ROOT/bin/spec-integration" open "$CONVOY" --repo "$PRODUCT" --protected main) \
  || fail "spec-integration open did not pass: $opened"
INTEGRATION="integration/$SPEC"
INTEGRATION_BASE=$(git -C "$PRODUCT" rev-parse "$INTEGRATION")
echo "$(date -u +%H:%M:%S) marque posée, critères gelés, branche $INTEGRATION ouverte à $INTEGRATION_BASE"

field() { gc bd show "$1" --json | jq -r --arg k "$2" '.[0].metadata[$k] // empty'; }
status_of() { gc bd show "$1" --json | jq -r '.[0].status'; }
shown() { "$ROOT/bin/convoy-state" show "$CONVOY" --repo "$PRODUCT" | jq -c --arg t "$T" '.tickets[] | select(.id == $t)'; }
piece() { jq -r '.output' "$TRIAL/store/$SPEC/$T/$1.json"; }
wait_for() { # <seconds> <command...>
  local deadline=$(( $(date +%s) + $1 )); shift
  until "$@"; do
    [ "$(date +%s)" -lt "$deadline" ] || return 1
    sleep 5
  done
}
dump() {
  for log in author checks reviewer evaluator; do
    echo "--- $log.log" >&2
    tail -25 "$TRIAL/$log.log" >&2 2>/dev/null || true
  done
  tail -3 "$TRIAL/passes.jsonl" >&2 || true
}
step_seen() { grep -q "^$T $1 " "$TRIAL/steps" 2>/dev/null; }

# --- started: by the order, through the dispatch door ---------------------------------
wait_for 420 step_seen workspace || { dump; fail "the ticket was not taken by an author session within 420s"; }
[ "$(field "$T" gc.dispatched_via)" = dispatch-door ] || fail "the ticket was not started through the dispatch door"
[ "$(shown | jq -r '.gates.dispatch.at // empty')" != "" ] || fail "the ticket carries no record of its start"
echo "$(date -u +%H:%M:%S) démarré : par l'ordre (bin/convoy-advance → bin/dispatch-door), formule mol-ticket-author, session $(grep "^$T workspace " "$TRIAL/steps" | head -1 | cut -d' ' -f3)"

# --- red, freeze, code: the author, held by the check of each step ---------------------
finished() { [ "$(field "$T" gc.flow.exit | jq -r '.exit // empty' 2>/dev/null)" = finished ]; }
wait_for 2400 finished || { dump; fail "the ticket did not reach the exit « terminé » within 2400s"; }
t=$(shown)
TIP=$(printf '%s' "$t" | jq -r '.tip')
[ "$(printf '%s' "$t" | jq -r '.branch')" = "ticket/$T" ] || fail "the ticket does not carry its ticket branch"
[ "$(git -C "$PRODUCT" rev-parse "$TIP~2")" = "$INTEGRATION_BASE" ] || fail "the branch of the ticket does not start at the tip of the integration branch"
for step in workspace red code demonstration exit; do
  step_seen "$step" || fail "the step $step of the author formula was not walked"
done
for name in tdd_red tdd_freeze tdd_green demonstration handoff_records; do
  printf '%s' "$t" | jq -e --arg p "$name" '.evidence[$p].digest' >/dev/null || fail "the ticket carries no fingerprint for the piece $name"
done
red=$(piece tdd_red); green=$(piece tdd_green)
printf '%s' "$red" | jq -e --arg base "$INTEGRATION_BASE" --arg t "$FIXTURE/tests" '
  .verdict == "red" and .seam_mode == "black_box" and .base == $base and .launch.healthy
  and ([.tests[] | [.id, .outcome, .entry_points]] == [
    [$t + "/count.test.js::count_is_answered", "failure", ["GET /items"]],
    [$t + "/health.test.js::dataset_is_named", "failure", ["GET /health"]]])' >/dev/null \
  || fail "the red proof is not one assertion failure per criterion test, each through its entry point: $red"
[ "$(printf '%s' "$t" | jq -c '[.test_review.rounds[].verdict]')" = '["favorable"]' ] || fail "the criterion tests were frozen without a favorable review"
piece tdd_freeze | jq -e --arg t "$FIXTURE/tests" '.verdict == "frozen" and (.files | keys | sort) == ([$t + "/count.test.js", $t + "/criteria.json", $t + "/harness.js", $t + "/health.test.js"])' >/dev/null \
  || fail "the freeze does not hold the criterion tests, their table and the harness of the profile: $(piece tdd_freeze)"
printf '%s' "$green" | jq -e --arg tip "$TIP" '.verdict == "green" and .commit == $tip and .k == 3 and .seam_mode == "black_box"
  and ([.tests[].runs] == [["passed","passed","passed"],["passed","passed","passed"]])' >/dev/null \
  || fail "the green proof is not the frozen tests passing k times at the tip: $green"
jq -e '.address != null and .exit_code == 0 and (.output | contains("\"count\":3"))' "$TRIAL/store/$SPEC/$T/demonstration.json" >/dev/null \
  || fail "the demonstration piece was not captured on the launched product"
echo "$(date -u +%H:%M:%S) rouge : $(printf '%s' "$red" | jq -c '[.tests[] | "\(.id | split("/") | last) → \(.outcome) par \(.entry_points | join(","))"]') au commit de départ $INTEGRATION_BASE (seam $(printf '%s' "$red" | jq -r '.seam_mode'), produit lancé en bonne santé)"
echo "$(date -u +%H:%M:%S) gel : relecture des tests $(printf '%s' "$t" | jq -r '.test_review.rounds[-1].verdict') ; empreintes de $(piece tdd_freeze | jq -c '.files | keys | map(split("/") | last)')"
echo "$(date -u +%H:%M:%S) code : vert au commit de tête $TIP, k=$(printf '%s' "$green" | jq -r '.k'), exécutions $(printf '%s' "$green" | jq -c '[.tests[] | .runs]') ; démonstration capturée sur le produit lancé ; sortie « terminé »"

# --- review, evaluation, merge, closed by the ticket-end gate, by the order ------------
closed() { [ "$(status_of "$T")" = closed ]; }
wait_for 2400 closed || { dump; fail "the ticket was not closed within 2400s"; }
t=$(shown)
[ "$(printf '%s' "$t" | jq -r '.code_review.rounds[-1].verdict')" = favorable ] || fail "the ticket was not reviewed favorably"
[ "$(printf '%s' "$t" | jq -r '.code_review.state.commit')" = "$TIP" ] || fail "the review is not on the tip of the ticket"
grep -q "^$T .* review $TIP [1-9]" "$TRIAL/review-sessions" || fail "the reviewer session did not read the diff of the ticket: $(cat "$TRIAL/review-sessions")"
[ "$(printf '%s' "$t" | jq -r '.evaluation.rounds[-1].outcome')" = favorable ] || fail "the ticket was not evaluated favorably"
[ "$(printf '%s' "$t" | jq -r '.evaluation.state.commit')" = "$TIP" ] || fail "the evaluation is not on the tip of the ticket"
for name in evaluation.c1 evaluation.c2 evaluation.demo evaluation.coverage.content evaluation.coverage.empty; do
  jq -e '.address != null' "$TRIAL/store/$SPEC/$T/$name.json" >/dev/null || fail "the piece $name was not captured on the launched product"
done
[ "$(jq -r '.address' "$TRIAL/store/$SPEC/$T/evaluation.coverage.content.json")" != "$(jq -r '.address' "$TRIAL/store/$SPEC/$T/evaluation.coverage.empty.json")" ] \
  || fail "coverage of empty came from the content product"
[ "$(printf '%s' "$t" | jq -r '.merge.outcome')" = merged ] || fail "the ticket is closed without being merged"
git -C "$PRODUCT" merge-base --is-ancestor "$TIP" "$INTEGRATION" || fail "the tip of the ticket is not on the integration branch"
jq -e '.exit_code == 0' "$TRIAL/store/$SPEC/$T/merged_tests.json" >/dev/null || fail "the regression command of the profile did not pass on the merged result"
grep -q "regression.js" <<<"$(jq -r '.command | tostring' "$TRIAL/store/$SPEC/$T/merged_tests.json")" \
  || fail "the tests on the merged result are not the regression command of the profile: $(jq -c '.command' "$TRIAL/store/$SPEC/$T/merged_tests.json")"
record=$(field "$T" gc.flow.gate.ticket_end)
printf '%s' "$record" | jq -e --arg tip "$TIP" '
  .version == "ticket-end/v1" and .commit == $tip
  and ([.conditions[] | [.number, .name, .verdict]] == [[1,"criteria","pass"],[2,"handoff","pass"],[3,"evaluation","pass"],
      [4,"fidelity","pass"],[5,"deferral","pass"],[6,"merge","pass"],[7,"evidence","pass"],[8,"tdd","pass"],[9,"review","pass"]])
  and ([.conditions[] | select((.detail | length) == 0)] | length == 0)' >/dev/null \
  || fail "the record of the gate is not its version, its nine passing verdicts and the merged commit: $record"
# The pass that closes the ticket writes its line once it has returned, and
# it carries on past the close: the line is waited for, not read once.
closing_line() { jq -c --arg c "$CONVOY" --arg t "$T" 'select(any(.convoys[]?; .id == $c and any(.ticket_end.closed[]?; .id == $t)))' "$TRIAL/passes.jsonl" 2>/dev/null | head -1; }
closing_reported() { [ -n "$(closing_line)" ]; }
wait_for 600 closing_reported || dump
closing_pass=$(closing_line)
[ -n "$closing_pass" ] || fail "no pass of the order reports having closed the ticket through the gate"
"$ROOT/bin/evidence-capture" verify "$CONVOY" "$T" >/dev/null || fail "the evidence of the ticket does not verify"
[ "$(printf '%s' "$t" | jq -c '.unruled')" = '[]' ] || fail "the ticket, closed by its gate, reads as an anomaly: $(printf '%s' "$t" | jq -c '.unruled')"
[ "$(printf '%s' "$t" | jq -r '.fidelity')" = null ] || fail "a fidelity check was recorded on a ticket of a project without a screen"
echo "$(date -u +%H:%M:%S) revue : $(printf '%s' "$t" | jq -r '.code_review.rounds[-1].verdict') à $TIP ; évaluation : $(printf '%s' "$t" | jq -r '.evaluation.rounds[-1].outcome') à $TIP, états $(jq -c '[.criteria[] | "critère \(.number) \(.state)"] + ["ligne de démonstration \(.demonstration_line.state)"]' "$TRIAL"/evaluation-result.*.json | tail -1)"
echo "$(date -u +%H:%M:%S) fusion : dans $INTEGRATION ($(printf '%s' "$t" | jq -r '.merge.commit')), commande de régression du profil verte sur le résultat fusionné"
echo "$(date -u +%H:%M:%S) fermé par la porte de fin de ticket, par l'ordre (passe de $(printf '%s' "$closing_pass" | jq -r '.at')) ; statut relu sur le tracker : $(status_of "$T") ; relevé de la porte relu : version $(printf '%s' "$record" | jq -r '.version'), commit $(printf '%s' "$record" | jq -r '.commit'), verdicts $(printf '%s' "$record" | jq -c '[.conditions[] | "\(.number) \(.name) \(.verdict)"]')"
printf '%s' "$record" | jq -r '.conditions[] | "    condition \(.number) (\(.name)) : \(.detail)"'

sessions=$(cut -d' ' -f3 "$TRIAL/steps" | sort -u | wc -l | tr -d ' ')
[ "$sessions" = 1 ] || fail "the ticket was not written by one author session ($sessions)"
gc session list --state all --json | jq -e '[.sessions[] | select(.template | test("mayor"))] | length == 0' >/dev/null \
  || fail "a Mayor session exists in the trial city"
echo "PASS: a ticket of the second project of the fixture (another language, no web page) went from started to closed by the ticket-end gate, by the same formulas and the same scripts as the first project"
