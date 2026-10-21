#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime, an isolated Dolt server, its own supervisor and bwrap
#
# Adoption trial of the ticket-end gate (T19, af-iefuud; Spec af-wf4w5r §9,
# user story 51) in a disposable city that shares nothing with the live
# Factory: its own GC_HOME, runtime directory, supervisor port, controller,
# evidence store, launch records and work trees. The product is a copy of the
# Delivery Fixture City, committed in the city root. The city has no Mayor.
#
# What is real: the controller, the order that advances the convoy
# (bin/convoy-advance), the tracker (gc/bd), the formulas mol-code-review and
# mol-ticket-evaluation, bin/code-review, bin/ticket-evaluation,
# bin/project-launch, bin/evidence-capture, bin/convoy-state,
# bin/spec-integration (the merge control, which asks the gate, and the
# merge), bin/ticket-end (settle, called by the order's pass; check),
# bin/dispatch-door (which routes each review and evaluation to the agent of
# its role), bin/escalation-door, bin/deliver-close and
# bin/delivery-role-sandbox (the Evaluator runs inside the read-only sandbox
# of its role). What is scripted, and spends nothing: the reviewer and the
# Evaluator, two stubs that claim the step Gas City routes to them and run
# the real tools the step names (those of
# tests/correction-round-isolated-city-test.sh); and the author of each
# ticket, whose steps are recorded through bin/convoy-state, each with its
# piece filed and sealed by the real bin/evidence-capture
# (tests/lib/ticket_proofs.py), instead of walking bin/tdd-step,
# bin/demonstrate and bin/ticket-exit (walked for real by
# tests/ticket-author-isolated-city-test.sh). The tickets are started by a
# dispatch record written by this script, not by the pass (the start by code
# is the trial of T04, tests/convoy-advance-isolated-city-test.sh). No ticket
# is an interface ticket: the fidelity check before the merge is not run here.
#
# Two tickets of the fixture, each finished by its author on a product that
# shows what its criterion asks.
#   A  walks the whole flow: reviewed, evaluated, merged into the integration
#      branch by a pass of the order, and closed by the same pass through the
#      ticket-end gate -- the record of the gate (its version, its nine
#      verdicts, the commit that was merged) and the closed status are read
#      back on the real tracker.
#   B  the same walk with one condition missing (a criterion edited on the
#      ticket after its publication): reviewed and evaluated, never merged,
#      left open by every later pass, and the gate names condition 1. Neither
#      an agent session asking the gate, nor bin/deliver-close, closes it.
#      Closed by hand at the end, it stops the convoy: one factory incident.
#
# The trial prints its record (« relevé d'essai ») on stdout.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
. "$ROOT/tests/lib/isolated-city.sh"
PORT="${TICKET_END_TRIAL_PORT:-18431}"
CEILING=6
APPROVER="essai-approbateur"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc bd jq git dolt tmux curl python3 bwrap; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

# Not under /tmp: bin/delivery-role-sandbox gives a read-only role an empty
# /tmp, and the Evaluator of this trial runs inside it.
mkdir -p "$HOME/.cache"
TRIAL=$(mktemp -d "$HOME/.cache/af-iefuud-ticket-end.XXXXXX")
CITY="$TRIAL/c"
PRODUCT="$CITY"
FIXTURE="tests/fixtures/delivery-fixture-city"
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
    isolated_city_remove "$TRIAL"
  fi
  exit "$status"
}
trap cleanup EXIT

# Nothing of the live Factory may reach this city (same recipe as
# tests/correction-round-isolated-city-test.sh, whose city this one is).
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$|FACTORY_ROOT$|CONVOY_|DISPATCH_DOOR_|ESCALATION_DOOR_|EVIDENCE_|TICKET_AUTHOR_|SPEC_INTEGRATION_|CODE_REVIEW_(DISPATCH|FAKE)|TICKET_EVALUATION_(DISPATCH|FAKE|STATE)|CORRECTION_ROUND_(DISPATCH|FAKE)|PROJECT_PLANNING_PROFILE_BIN$|DELIVERY_ROLE_)' || true)
export GC_HOME="$TRIAL/h" XDG_RUNTIME_DIR="$TRIAL/r" GC_DISABLE_USAGE_METRICS=1
unset DBUS_SESSION_BUS_ADDRESS
export PATH="/usr/local/bin:$HOME/.local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
mkdir -p "$GC_HOME"
mkdir -m 700 "$XDG_RUNTIME_DIR"
printf '[supervisor]\nport = %s\n' "$PORT" > "$GC_HOME/supervisor.toml"

# What every tool of the flow reads, in the stub sessions and in the order
# alike: the city as Factory root, and stores of the trial. The dispatch door
# is the real one; it asks these stubs where a role runs and whether its
# adoption trial passed (the stubs of this city are no provider to try).
cat > "$TRIAL/env" <<ENV
export TRIAL="$TRIAL" BIN="$ROOT/bin" PRODUCT="$PRODUCT" FIXTURE="$FIXTURE"
export FACTORY_ROOT="$CITY"
export CONVOY_STATE_LOCK_DIR="$TRIAL/locks" CONVOY_ADVANCE_LOCK_DIR="$TRIAL/locks" SPEC_INTEGRATION_LOCK_DIR="$TRIAL/locks"
export SPEC_INTEGRATION_WORK_DIR="$TRIAL/merge"
export EVIDENCE_STORE_DIR="$TRIAL/store"
export TICKET_EVALUATION_STATE_DIR="$TRIAL/launches"
export TICKET_AUTHOR_WORKTREES_DIR="$TRIAL/wt"
export ESCALATION_DOOR_LOCK_FILE="$TRIAL/escalation-door.lock" PROPOSAL_DOOR_BIN="$TRIAL/proposal-door"
export DISPATCH_DOOR_PROVIDER_FAILOVER_BIN="$TRIAL/provider-failover" DISPATCH_DOOR_ROLE_TRIAL_BIN="$TRIAL/role-adoption-trial"
export DELIVERY_ROLE_PROVIDER_FAILOVER_BIN="$TRIAL/provider-failover"
export GIT_AUTHOR_NAME=essai GIT_AUTHOR_EMAIL=essai@example.invalid GIT_COMMITTER_NAME=essai GIT_COMMITTER_EMAIL=essai@example.invalid
ENV
printf '#!/bin/sh\necho 0\n' > "$TRIAL/proposal-door"
cat > "$TRIAL/provider-failover" <<'SH'
#!/bin/sh
printf '%s\n' '{"total_exhaustion": {"active": false}, "targets": {"trial-author": {"effective": "stub-author"}, "trial-reviewer": {"effective": "stub-reviewer"}, "trial-evaluator": {"effective": "stub-evaluator", "chain": [{"provider": "stub-evaluator", "state": "available", "pool": "fournisseur-essai"}]}}}'
SH
printf '#!/bin/sh\nexit 0\n' > "$TRIAL/role-adoption-trial"
chmod +x "$TRIAL/proposal-door" "$TRIAL/provider-failover" "$TRIAL/role-adoption-trial"
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
BASE=$(git -C "$PRODUCT" rev-parse HEAD)
printf '%s' "$BASE" > "$TRIAL/base"

# --- what an author does to a ticket, written as its tools would ---------------
# Shared by this script (the first author of each ticket) and by the stub of
# the correction session.
cat > "$TRIAL/author-lib.sh" <<'LIB'
state() {
  local out
  out=$("$BIN/convoy-state" "$@") || { echo "convoy-state $* did not pass: $out" >&2; return 1; }
  printf '%s' "$out"
}
worktree_of() {
  local wt="$TRIAL/wt/$1"
  if [ ! -d "$wt" ]; then
    git -C "$PRODUCT" worktree add -q -b "ticket/$1" "$wt" "$(cat "$TRIAL/integration")" >/dev/null 2>&1 || return 1
  fi
  printf '%s' "$wt"
}
commit_on() { # <ticket> <path> <content> <message>: one commit on the branch of the ticket; prints its SHA
  local wt
  wt=$(worktree_of "$1") || return 1
  mkdir -p "$wt/$(dirname "$2")"
  printf '%s\n' "$3" > "$wt/$2"
  git -C "$wt" add -A
  git -C "$wt" commit -q -m "$4"
  git -C "$wt" rev-parse HEAD
}
realize() { # <ticket>: the product shows the number of items; prints the SHA
  local wt
  wt=$(worktree_of "$1") || return 1
  python3 - "$wt/$FIXTURE/app.py" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
shown = "f'<ul data-anchor=\"fixture-items\">{items_html}</ul>'"
text = path.read_text()
assert shown in text
path.write_text(text.replace(shown, shown + "\n            f'<p data-anchor=\"fixture-count\">{len(items)}</p>'"))
PY
  git -C "$wt" add -A
  git -C "$wt" commit -q -m "le nombre est affiché"
  git -C "$wt" rev-parse HEAD
}
finish() { # <convoy> <ticket> <tip>: every step of the TDD with its sealed report, the demonstration, the sealed records, the Handoff, the exit « terminé »
  python3 "$BIN/../tests/lib/ticket_proofs.py" finish "$1" "$2" "$3" --repo "$PRODUCT" --base "$(cat "$TRIAL/base")" --branch "ticket/$2"
}
LIB

# One stub per role: the header names the trial, the body is the session.
stub() { # <name>: reads the body on stdin
  printf '#!/bin/bash\n. "%s/env"\n. "%s/author-lib.sh"\n' "$TRIAL" "$TRIAL" > "$TRIAL/$1"
  cat >> "$TRIAL/$1"
  chmod +x "$TRIAL/$1"
}

# --- the scripted reviewer --------------------------------------------------------
# One session, one round, as the step of mol-code-review asks. A diff that
# says the count is not shown contradicts the line of the Spec, which the
# review cites; a judgement finds a « corrigé » right when the diff of the
# correction no longer says so.
stub stub-reviewer <<'STUB'
export DELIVERY_ROLE_READ_ONLY=1
LOG="$TRIAL/reviewer.log"
say() { echo "$(date -u +%H:%M:%S) ${GC_SESSION_NAME:-?} $*" >> "$LOG"; }
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
  echo "$TICKET $REVIEW_BEAD ${GC_SESSION_NAME:-?} $KIND $(jq -r '.commit' "$BRIEF") $(date -u +%H:%M:%S)" >> "$TRIAL/review-sessions"
  RESULT="$TRIAL/review-result.$REVIEW_BEAD.json"
  DIFF=$(sh -c "$(jq -r '.diff.command' "$BRIEF")")
  if [ "$KIND" = judgement ]; then
    if printf '%s' "$DIFF" | grep -q "^+.*n'est pas affiché"; then
      jq '{commit, judgements: (.findings | map({key: .id, value: {state: "unfavorable", reason: "le diff dit encore que le nombre n'"'"'est pas affiché"}}) | from_entries)}' "$BRIEF" > "$RESULT"
    else
      jq '{commit, judgements: (.findings | map({key: .id, value: {state: "favorable"}}) | from_entries)}' "$BRIEF" > "$RESULT"
    fi
  else
    FINDINGS='[]'
    if printf '%s' "$DIFF" | grep -q "n'est pas affiché"; then
      FINDINGS=$(jq -c --arg line "$(cat "$TRIAL/spec-line")" '[{axis: "spec", blocking: true, summary: "Le diff dit que le nombre n'"'"'est pas affiché.", citation: {source: "spec", quote: $line}}]' "$BRIEF")
    fi
    jq --argjson findings "$FINDINGS" '{commit, findings: $findings, answers: (.questions | map({key: .id, value: {answer: "oui"}}) | from_entries)}' "$BRIEF" > "$RESULT"
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
# One session, one evaluation, as the step of mol-ticket-evaluation asks: a
# captured page of the launched product per criterion and for the
# demonstration line, « observed » when it shows the count anchor,
# « not_observed » otherwise. It runs inside bin/delivery-role-sandbox.
stub stub-evaluator-inner <<'STUB'
LOG="$TRIAL/evaluator.log"
say() { echo "$(date -u +%H:%M:%S) ${GC_SESSION_NAME:-?} $*" >> "$LOG"; }
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
  echo "$TICKET $EVALUATION_BEAD ${GC_SESSION_NAME:-?} $(jq -r '.commit' "$BRIEF") $(date -u +%H:%M:%S)" >> "$TRIAL/evaluation-sessions"
  state_of() { # <piece> <text>: capture the home page, print the state as JSON
    local captured page
    captured=$("$BIN/evidence-capture" command "$CONVOY" "$TICKET" --piece "$1" --launch-state "$LAUNCH" -- curl -s "$ADDRESS/" 2>>"$LOG") || return 1
    page=$(jq -r '.output' "$(printf '%s' "$captured" | jq -r '.path')")
    if printf '%s' "$page" | grep -qF 'data-anchor="fixture-count"'; then
      jq -n --arg text "$2" --arg piece "$1" '{text: $text, state: "observed", evidence: $piece}'
    else
      jq -n --arg text "$2" --arg piece "$1" '{text: $text, state: "not_observed", evidence: $piece, reason: "la page du produit lancé ne montre pas l'"'"'ancre fixture-count"}'
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

# --- the scripted author of the correction round -----------------------------------
# One session, one round, as the step of mol-ticket-correction asks: it takes
# the ticket (the real bin/ticket-author start), reads its brief, and then
# either corrects both defects and answers the Blocking Finding (« corrects »),
# or ends without correcting anything (« leaves »), as a session that gave up
# would.
stub stub-author <<'STUB'
LOG="$TRIAL/author.log"
say() { echo "$(date -u +%H:%M:%S) ${GC_SESSION_NAME:-?} $*" >> "$LOG"; }
while true; do
  CLAIM=$(gc hook --claim --json 2>/dev/null)
  ACTION=$(printf '%s' "$CLAIM" | jq -r '.action // empty' 2>/dev/null)
  BEAD=$(printf '%s' "$CLAIM" | jq -r '.bead_id // empty' 2>/dev/null)
  if [ "$ACTION" != work ] || [ -z "$BEAD" ]; then sleep 3; continue; fi
  ROOT_BEAD=$(gc bd show "$BEAD" --json | jq -r '.[0].metadata["gc.root_bead_id"]')
  INPUT=$(gc bd show "$ROOT_BEAD" --json | jq -r '.[0].metadata["gc.input_convoy_id"]')
  CORRECTION_BEAD=$(gc convoy status "$INPUT" --json | jq -r '.children[0].id')
  if [ "$(gc bd show "$CORRECTION_BEAD" --json | jq -r '.[0].status')" = closed ]; then
    # Seen on gc 1.4.1: a session is started again on the step it just closed.
    say "bead $CORRECTION_BEAD déjà fermé, rien à faire"
    gc runtime drain-ack >/dev/null 2>&1
    exit 0
  fi
  TEXT=$(gc bd show "$CORRECTION_BEAD" --json | jq -r '.[0].description')
  CONVOY=$(printf '%s\n' "$TEXT" | sed -n 's/^convoy: //p'); TICKET=$(printf '%s\n' "$TEXT" | sed -n 's/^ticket: //p')
  OUTCOME=pass
  START=$("$BIN/ticket-author" start "$CONVOY" "$TICKET" 2>>"$LOG") || { say "ticket $TICKET : start refusé : $START"; OUTCOME=fail; }
  BRIEF="$TRIAL/correction-brief.$TICKET.$CORRECTION_BEAD.json"
  "$BIN/correction-round" brief "$CONVOY" "$TICKET" > "$BRIEF" 2>>"$LOG" || OUTCOME=fail
  MODE=$(cat "$TRIAL/author.$TICKET")
  echo "$TICKET $CORRECTION_BEAD ${GC_SESSION_NAME:-?} $MODE $(date -u +%H:%M:%S)" >> "$TRIAL/correction-sessions"
  if [ "$MODE" = corrects ] && [ "$OUTCOME" = pass ]; then
    realize "$TICKET" >> "$LOG" 2>&1 || OUTCOME=fail
    FIX=$(commit_on "$TICKET" "docs/$TICKET.md" "Le nombre d'éléments est affiché sur la page d'accueil." "correction") || OUTCOME=fail
    jq -n --arg commit "$FIX" --argjson brief "$(cat "$BRIEF")" \
      '{responses: ($brief.code_review.blocking_findings | map({key: .id, value: {response: "fixed", commit: $commit}}) | from_entries)}' \
      > "$TRIAL/responses.$TICKET.json"
    "$BIN/code-review" respond "$CONVOY" "$TICKET" --file "$TRIAL/responses.$TICKET.json" >> "$LOG" 2>&1 || OUTCOME=fail
    finish "$CONVOY" "$TICKET" "$FIX" >> "$LOG" 2>&1 || OUTCOME=fail
    say "ticket $TICKET : corrigé au commit $FIX ($OUTCOME)"
  else
    OUTCOME=fail
    say "ticket $TICKET : session terminée sans corriger"
  fi
  gc bd update "$CORRECTION_BEAD" --set-metadata gc.outcome=$OUTCOME --status=closed --notes "tour de correction $OUTCOME" >> "$LOG" 2>&1 || say "fermeture du bead de correction refusée"
  gc bd update "$BEAD" --set-metadata gc.outcome=$OUTCOME --status=closed --notes "tour de correction $OUTCOME" >> "$LOG" 2>&1 || say "fermeture de l'étape refusée"
  gc runtime drain-ack >> "$LOG" 2>&1 || say "drain-ack refusé"
  exit 0
done
STUB

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

[providers.stub-reviewer]
base = "builtin:claude"
command = "$TRIAL/stub-reviewer"
process_names = ["stub-reviewer", "bash"]
ready_delay_ms = 0

[providers.stub-evaluator]
base = "builtin:claude"
command = "$TRIAL/stub-evaluator"
process_names = ["stub-evaluator", "stub-evaluator-inner", "bwrap", "bash"]
ready_delay_ms = 0
TOML
mkdir -p "$CITY/formulas" "$CITY/orders" "$CITY/config/projects" "$CITY/config/project-descriptors"
for role in author reviewer evaluator; do
  mkdir -p "$CITY/agents/trial-$role"
  cat > "$CITY/agents/trial-$role/agent.toml" <<TOML
description = "Role $role of the ticket-end trial (scripted stub, spends nothing)"
scope = "city"
min_active_sessions = 0
max_active_sessions = 2
provider = "stub-$role"
$([ "$role" = author ] || echo 'wake_mode = "fresh"')
TOML
  echo "Scripted $role of the ticket-end trial." > "$CITY/agents/trial-$role/prompt.template.md"
done
for formula in mol-code-review mol-ticket-evaluation mol-ticket-correction; do
  cp "$ROOT/formulas/$formula.formula.toml" "$CITY/formulas/"
done
cat > "$CITY/config/projects/trial.toml" <<TOML
rig_dir = "."
repo = "example/trial"
protected_branch = "main"
required_ci = "CI"
sling_target = "trial-reviewer"
formulas = "mol-code-review,mol-ticket-evaluation,mol-ticket-correction"
human_approver = "$APPROVER"
TOML
jq '.rigs = ["trial"] | .stacks = {"trial": ["fixture-stack"]}' "$ROOT/$FIXTURE/descriptor.json" > "$CITY/config/project-descriptors/trial.json"
jq -n --argjson n "$CEILING" '{contract: "agent-factory-delivery-flow/v1", max_sessions: $n,
  start: {formula: "mol-ticket-author", role: "author"},
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
# shellcheck disable=SC1091
. "$TRIAL/author-lib.sh"
SPEC_LINE="La page d'accueil affiche le nombre d'éléments du jeu de données."
printf '%s' "$SPEC_LINE" > "$TRIAL/spec-line"
CRITERION="Point d'entrée : GET / — Observable : ancre fixture-count — Faux si : le nombre d'éléments n'y est pas"
LINE="Sur le jeu content, la page d'accueil affiche le nombre d'éléments"
description_of() { # <criterion>
  printf '%s\n' "## What to build" "" "Le nombre d'éléments sur la page d'accueil." "" "## Acceptance criteria" "" "- [ ] $1" "" "## Target rigs" "" "trial"
}
new_ticket() { gc bd create --title "$1" --type task --silent --description "$(description_of "$CRITERION")" 2>/dev/null; }
SPEC=$(gc bd create --title "Spec d'essai" --type task --silent --description "## User Stories

1. $SPEC_LINE

## Testing Decisions

Seams : GET / et GET /health." 2>/dev/null)
gc bd update "$SPEC" --status closed >/dev/null 2>&1 || true
CONVOY=$(gc bd create --title "convoi d'essai" --type convoy --silent 2>/dev/null)
gc bd update "$CONVOY" --set-metadata "gc.spec_id=$SPEC" >/dev/null
A=$(new_ticket "ticket A, parcourt tout le flux")
B=$(new_ticket "ticket B, même parcours, une condition manquante")
for t in "$A" "$B"; do
  echo leaves > "$TRIAL/author.$t"
  gc bd dep add "$CONVOY" "$t" --type tracks >/dev/null
  gc bd update "$t" --set-metadata gc.ticket_kind=vertical_slice >/dev/null
done

echo "relevé d'essai — porte de fin de ticket ; cité isolée ($(gc version 2>/dev/null | head -1), N=$CEILING, aucun Mayor ; relecteur et Evaluator scriptés, auteur scripté dont chaque preuve est scellée par le vrai outil de capture ; vrai contrôleur, vrai ordre, vraie porte de dispatch, vrai lancement du produit, vraie commande de fusion, vraie porte de fin de ticket)"
echo "convoi $CONVOY (Spec $SPEC) : A=$A (parcourt tout le flux) B=$B (même parcours, un critère édité sur le ticket après la publication)"

state mark "$CONVOY" --demonstration-line "$A=$LINE" --demonstration-line "$B=$LINE" \
  --user-stories "$A=1" --user-stories "$B=1" >/dev/null
opened=$("$ROOT/bin/spec-integration" open "$CONVOY" --repo "$PRODUCT" --protected main) \
  || fail "spec-integration open did not pass: $opened"
INTEGRATION="integration/$SPEC"
printf '%s' "$INTEGRATION" > "$TRIAL/integration"

field() { gc bd show "$1" --json | jq -r --arg k "$2" '.[0].metadata[$k] // empty'; }
status_of() { gc bd show "$1" --json | jq -r '.[0].status'; }
shown() { "$ROOT/bin/convoy-state" show "$CONVOY" --repo "$PRODUCT" | jq -c --arg t "$1" '.tickets[] | select(.id == $t)'; }
gate_check() { local t=$1; shift; "$ROOT/bin/ticket-end" check "$CONVOY" "$t" --repo "$PRODUCT" "$@"; }
[ "$(shown "$A" | jq -r '.criteria_frozen.identical')" = true ] || fail "the criteria of A were not frozen with the mark: $(shown "$A" | jq -c '.criteria_frozen')"

# B: a criterion edited on the ticket once the graph is published and marked.
gc bd update "$B" --description "$(description_of "$CRITERION, ou presque")" >/dev/null || fail "could not edit the criterion of B"
[ "$(shown "$B" | jq -r '.criteria_frozen.identical')" = false ] || fail "the edited criterion of B still reads as the frozen one"

# --- the author of each ticket: a product that shows the count, every proof sealed ----
author_finishes() { # <ticket>: prints the tip
  local t=$1 tip
  state record-gate "$CONVOY" "$t" --gate dispatch >/dev/null
  state set-branch "$CONVOY" "$t" --branch "ticket/$t" >/dev/null
  state set-session "$CONVOY" "$t" --session "trial-author-$t" >/dev/null
  state set-model "$CONVOY" "$t" --role author --agent trial-author --provider stub-author --model modele-auteur >/dev/null
  gc bd update "$t" --status in_progress >/dev/null
  commit_on "$t" "$FIXTURE/tests/test_count_$t.py" "# test de critère du ticket $t" "tests de critère" >/dev/null
  realize "$t" >/dev/null || fail "the author could not realize $t"
  tip=$(commit_on "$t" "docs/$t.md" "Le nombre d'éléments est affiché sur la page d'accueil." "la tranche")
  finish "$CONVOY" "$t" "$tip" >/dev/null || fail "the author could not finish $t"
  printf '%s' "$tip"
}
TIP_A=$(author_finishes "$A")
TIP_B=$(author_finishes "$B")
before_merge=$(gate_check "$A" --before-merge) || true
echo "$(date -u +%H:%M:%S) marque posée, critères gelés, branche $INTEGRATION ouverte, deux tickets terminés par leur auteur (A $TIP_A, B $TIP_B) ; porte avant fusion sur A, avant toute revue : conditions manquantes $(printf '%s' "$before_merge" | jq -c '.missing')"

isolated_city_disable_dog "$TRIAL" "$CITY"
(env -u CLAUDE_CODE_SESSION_ID gc supervisor run > "$TRIAL/supervisor.out" 2>&1 &)
sleep 3
gc --city "$CITY" start >/dev/null 2>&1 || true
grep -q "Controller: supervisor-managed" <<<"$(gc --city "$CITY" status 2>/dev/null)" || fail "the isolated city's controller did not start"
gc order show convoy-advance --json >/dev/null 2>&1 || fail "the city does not accept orders/convoy-advance.toml"

wait_for() { # <seconds> <command...>
  local deadline=$(( $(date +%s) + $1 )); shift
  until "$@"; do
    [ "$(date +%s)" -lt "$deadline" ] || return 1
    sleep 5
  done
}
merged() { [ "$(field "$1" gc.flow.merge | jq -r '.outcome // empty' 2>/dev/null)" = merged ]; }
closed() { [ "$(status_of "$1")" = closed ]; }
on_integration() { git -C "$PRODUCT" merge-base --is-ancestor "$1" "$INTEGRATION"; }
dump() {
  for log in reviewer evaluator; do tail -15 "$TRIAL/$log.log" >&2 2>/dev/null || true; done
  tail -3 "$TRIAL/passes.jsonl" >&2 || true
}
operator_list() { "$ROOT/bin/escalation-door" list 2>&1; }

# --- A: walks the whole flow and is closed by the gate, by a pass of the order ---------
wait_for 900 closed "$A" || { dump; fail "A was not closed within 900s"; }
merged "$A" || fail "A is closed without being merged"
on_integration "$TIP_A" || fail "the tip of A is not on the integration branch"
record=$(field "$A" gc.flow.gate.ticket_end)
printf '%s' "$record" | jq -e --arg tip "$TIP_A" '
  .version == "ticket-end/v1" and .commit == $tip
  and ([.conditions[] | [.number, .name, .verdict]] == [[1,"criteria","pass"],[2,"handoff","pass"],[3,"evaluation","pass"],
      [4,"fidelity","pass"],[5,"deferral","pass"],[6,"merge","pass"],[7,"evidence","pass"],[8,"tdd","pass"],[9,"review","pass"]])
  and ([.conditions[] | select((.detail | length) == 0)] | length == 0)' >/dev/null \
  || fail "the record of the gate on A is not its version, its nine passing verdicts and the merged commit: $record"
# The gate closes A in the middle of its pass; the wrapper of the order
# appends that pass's line only once the pass has run its later steps (the
# end of the Spec, the Evidence Pack, the acceptance), seconds after A reads
# closed under load (af-pnjrln). So the line is waited for, within the
# timeout of one pass.
closed_seen=$(date +%s)
closing_pass_of_A() {
  jq -c --arg c "$CONVOY" --arg a "$A" 'select(any(.convoys[]?; .id == $c and any(.ticket_end.closed[]?; .id == $a)))' \
    "$TRIAL/passes.jsonl" 2>/dev/null | head -1 || true
}
closing_pass_recorded() { [ -n "$(closing_pass_of_A)" ]; }
wait_for 300 closing_pass_recorded || fail "no pass of the order reports having closed A through the gate"
closing_pass=$(closing_pass_of_A)
recorded_after=$(( $(date +%s) - closed_seen ))
printf '%s' "$closing_pass" | jq -e --arg c "$CONVOY" --arg a "$A" 'any(.convoys[]; .id == $c and any(.integration.merged[]?; .id == $a))' >/dev/null \
  || fail "A was not closed by the pass that merged it: $closing_pass"
"$ROOT/bin/evidence-capture" verify "$CONVOY" "$A" >/dev/null || fail "the evidence of A does not verify"
[ "$(shown "$A" | jq -c '.unruled')" = '[]' ] || fail "A, closed by its gate, reads as an anomaly: $(shown "$A" | jq -c '.unruled')"
echo "$(date -u +%H:%M:%S) A : relu ($(field "$A" gc.flow.code_review | jq -r '.rounds[-1].verdict')), évalué ($(field "$A" gc.flow.evaluation | jq -r '.rounds[-1].outcome')), fusionné dans $INTEGRATION puis fermé par la même passe de l'ordre (passe de $(printf '%s' "$closing_pass" | jq -r '.at'), sa ligne relevée ${recorded_after}s après la fermeture vue) ; statut relu sur le tracker : $(status_of "$A") ; relevé de la porte relu : version $(printf '%s' "$record" | jq -r '.version'), commit $(printf '%s' "$record" | jq -r '.commit'), verdicts $(printf '%s' "$record" | jq -c '[.conditions[] | "\(.number) \(.name) \(.verdict)"]')"
printf '%s' "$record" | jq -r '.conditions[] | "    condition \(.number) (\(.name)) : \(.detail)"'

# --- B: one condition missing -> reviewed, evaluated, never merged, left open, named -----
b_evaluated() { [ "$(field "$B" gc.flow.evaluation | jq -r '.rounds[-1].outcome // empty' 2>/dev/null)" = favorable ]; }
wait_for 600 b_evaluated || { dump; fail "B was not evaluated within 600s"; }
[ "$(field "$B" gc.flow.code_review | jq -r '.rounds[-1].verdict')" = favorable ] || fail "B was not reviewed favorably"
sleep 75   # at least two more passes of the order
merged "$B" && fail "B was merged although its criteria are no longer the approved ones"
on_integration "$TIP_B" && fail "the tip of B reached the integration branch"
[ "$(status_of "$B")" = in_progress ] || fail "B is $(status_of "$B"), not left open"
[ -z "$(field "$B" gc.flow.gate.ticket_end)" ] || fail "B carries a record of the gate"
set +e
named=$(gate_check "$B"); rc=$?
set -e
[ "$rc" = 1 ] || fail "the gate on B exited $rc, want 1: $named"
[ "$(printf '%s' "$named" | jq -c '.missing')" = '[1,6]' ] || fail "the gate on B names $(printf '%s' "$named" | jq -c '.missing'), want conditions 1 (criteria) and 6 (not merged)"
grep -q "condition 1" <<<"$(printf '%s' "$named" | jq -r '.error')" || fail "the refusal of the gate on B does not name condition 1: $named"
waiting=$(tail -1 "$TRIAL/passes.jsonl" | jq -r --arg c "$CONVOY" --arg b "$B" '.convoys[] | select(.id == $c) | .integration.waiting[]? | select(.id == $b) | .reason')
printf '%s' "$waiting" | grep -q "condition 1" || fail "the last pass does not say B waits for condition 1: $(tail -1 "$TRIAL/passes.jsonl")"
echo "$(date -u +%H:%M:%S) B : relu et évalué favorablement, jamais fusionné, laissé ouvert par les passes suivantes (statut $(status_of "$B"), aucun relevé de porte) ; la porte nomme : $(printf '%s' "$named" | jq -r '[.conditions[] | select(.verdict == "fail") | "condition \(.number) (\(.name)) : \(.detail)"] | join(" | ")')"

# --- B: neither an agent session nor the closing door of the flow before closes it ------
before=$(gc bd show "$B" --json | jq -c '.[0] | {status, metadata}')
by_agent=$(GC_SESSION_NAME="trial-author-$B" "$ROOT/bin/ticket-end" close "$CONVOY" "$B" --repo "$PRODUCT") && fail "the gate closed B for an agent session: $by_agent"
printf '%s' "$by_agent" | grep -q "session d'agent" || fail "the refusal to an agent session does not say why: $by_agent"
by_door=$(FACTORY_ROOT="$CITY" "$ROOT/bin/deliver-close" "$B" --outcome no-op 2>&1) && fail "bin/deliver-close closed a ticket of a marked convoy: $by_door"
printf '%s' "$by_door" | grep -q "ticket-end" || fail "the refusal of bin/deliver-close does not name the gate: $by_door"
[ "$(gc bd show "$B" --json | jq -c '.[0] | {status, metadata}')" = "$before" ] || fail "a refused closing wrote something on B"
echo "$(date -u +%H:%M:%S) B : fermeture refusée, sans rien écrire, à une session d'agent (« $(printf '%s' "$by_agent" | jq -r '.error' | cut -c1-110)… ») et par bin/deliver-close (« $(printf '%s' "$by_door" | tail -1 | cut -c1-110)… »)"

# --- B closed by hand: the convoy is stopped, one factory incident -----------------------
gc bd close "$B" --reason "fermé à la main, hors porte" >/dev/null 2>&1 || gc bd update "$B" --status closed >/dev/null
stopped() { tail -1 "$TRIAL/passes.jsonl" | jq -e --arg c "$CONVOY" 'any(.convoys[]?; .id == $c and .signal == "état sans règle")' >/dev/null 2>&1; }
wait_for 180 stopped || { dump; fail "the convoy was not stopped within 180s of a ticket closed outside the gate"; }
incident() { [ "$(operator_list | grep -c "Incident d'usine")" = 1 ]; }
wait_for 120 incident || fail "the stop of the convoy is not exactly one factory incident on the operator's list: $(operator_list)"
echo "$(date -u +%H:%M:%S) B fermé à la main (gc bd close) : la passe suivante voit l'anomalie et arrête le convoi ($(tail -1 "$TRIAL/passes.jsonl" | jq -r --arg c "$CONVOY" '.convoys[] | select(.id == $c) | .unruled[0].reason')) ; un seul incident d'usine sur la liste : $(operator_list | grep "Incident d'usine" | head -1 | cut -c1-150)"

gc session list --state all --json | jq -e '[.sessions[] | select(.template | test("mayor"))] | length == 0' >/dev/null \
  || fail "a Mayor session exists in the trial city"
echo "PASS: a ticket whose nine conditions hold was closed by the ticket-end gate, by the order; the same walk with a condition missing stayed open and the gate named the condition"
