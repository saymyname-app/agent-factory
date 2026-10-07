#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime, an isolated Dolt server, its own supervisor and bwrap
#
# Adoption trial of the single correction round of a ticket, of the stop of a
# ticket still refused and of the override of the operator (T17, af-rx0ocp;
# Spec af-wf4w5r §8, user stories 43 to 45) in a disposable city that shares
# nothing with the live Factory: its own GC_HOME, runtime directory,
# supervisor port, controller, evidence store, launch records and work
# trees. The product is a copy of the Delivery Fixture City, committed in the
# city root. The city has no Mayor.
#
# What is real: the controller, the order that advances the convoy
# (bin/convoy-advance), the formulas mol-code-review, mol-ticket-evaluation
# and mol-ticket-correction, bin/code-review, bin/ticket-evaluation,
# bin/correction-round, bin/project-launch, bin/evidence-capture,
# bin/convoy-state, bin/spec-integration (the merge control and the merge),
# bin/dispatch-door (which routes each review, evaluation and correction
# round to the agent of its role), bin/ticket-author start (the correction
# session takes the ticket), bin/escalation-door, bin/project-planning-profile
# (the declared human approver) and bin/delivery-role-sandbox (the Evaluator
# runs inside the read-only sandbox of its role). What is scripted, and
# spends nothing: the reviewer, the Evaluator and the author of the
# correction round, three stubs that claim the step Gas City routes to them
# and run the real tools the step names; and the first author of each ticket,
# whose finished ticket is written through bin/convoy-state as bin/tdd-step,
# bin/test-review and bin/ticket-exit would (tests/ticket-author-isolated-city-test.sh).
#
# Two tickets of the fixture, each finished by its author with the same two
# defects: its diff contradicts a line of the Spec, and its product does not
# show what its criterion asks.
#   A  review and evaluation start on the same commit, by the same pass; both
#      refuse; one author session starts, and its brief holds the Blocking
#      Finding of the one and the states not observed of the other. That
#      session ends without correcting: the ticket is stopped, never merged,
#      no second session starts, and it is one item on the operator's list.
#      The override of its Blocking Finding by the declared human approver is
#      recorded; the same from anybody else, and the override of the
#      criterion that was not observed, are refused.
#   B  its correction session corrects both: the answer is judged favorably
#      by a second reviewer session, the product is evaluated again at the
#      new tip, the ticket is merged, and its round counted one resume.
#
# The trial prints its record (« relevé d'essai ») on stdout.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
PORT="${CORRECTION_ROUND_TRIAL_PORT:-18421}"
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
TRIAL=$(mktemp -d "$HOME/.cache/af-rx0ocp-correction.XXXXXX")
CITY="$TRIAL/c"
PRODUCT="$CITY"
FIXTURE="tests/fixtures/delivery-fixture-city"
cleanup() {
  status=$?
  trap - EXIT
  gc --city "$CITY" stop >/dev/null 2>&1 || true
  gc supervisor stop >/dev/null 2>&1 || true
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
# tests/ticket-evaluation-isolated-city-test.sh).
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$|FACTORY_ROOT$|CONVOY_|DISPATCH_DOOR_|ESCALATION_DOOR_|EVIDENCE_|TICKET_AUTHOR_|SPEC_INTEGRATION_|TEST_REVIEW_|CODE_REVIEW_(DISPATCH|FAKE)|TICKET_EVALUATION_(DISPATCH|FAKE|STATE)|CORRECTION_ROUND_(DISPATCH|FAKE)|PROJECT_PLANNING_PROFILE_BIN$|DELIVERY_ROLE_)' || true)
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
finish() { # <convoy> <ticket> <tip>: every step of the TDD with its sealed report, the demonstration, the sealed records, the Handoff, the exit « terminé » (T19: the merge asks the ticket-end gate)
  python3 "$BIN/../tests/lib/ticket_proofs.py" finish "$1" "$2" "$3" --repo "$PRODUCT" --base "$(cat "$TRIAL/base")" --branch "ticket/$2" \
    --done "Le nombre est affiché." --subject "travail du ticket" >/dev/null
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
  ADDRESS=$(jq -r '.environments[] | select(.dataset == "content") | .address' "$BRIEF")
  LAUNCH=$(jq -r '.environments[] | select(.dataset == "content") | .launch_state' "$BRIEF")
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
  jq --argjson criteria "$CRITERIA" --argjson line "${LINE:-null}" '{commit, criteria: $criteria, demonstration_line: $line}' "$BRIEF" > "$RESULT"
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
description = "Role $role of the correction-round trial (scripted stub, spends nothing)"
scope = "city"
min_active_sessions = 0
max_active_sessions = 2
provider = "stub-$role"
TOML
  echo "Scripted $role of the correction-round trial." > "$CITY/agents/trial-$role/prompt.template.md"
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
jq '.rigs = ["trial"]' "$ROOT/$FIXTURE/descriptor.json" > "$CITY/config/project-descriptors/trial.json"
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
new_ticket() {
  gc bd create --title "$1" --type task --silent --description "## What to build

Le nombre d'éléments sur la page d'accueil.

## Acceptance criteria

- [ ] $CRITERION

## Target rigs

trial" 2>/dev/null
}
SPEC=$(gc bd create --title "Spec d'essai" --type task --silent --description "## User Stories

1. $SPEC_LINE

## Testing Decisions

Seams : GET / et GET /health." 2>/dev/null)
gc bd update "$SPEC" --status closed >/dev/null 2>&1 || true
CONVOY=$(gc bd create --title "convoi d'essai" --type convoy --silent 2>/dev/null)
gc bd update "$CONVOY" --set-metadata "gc.spec_id=$SPEC" >/dev/null
A=$(new_ticket "ticket A, refusé par les deux, tour de correction sans correction")
B=$(new_ticket "ticket B, refusé par les deux, corrigé à son tour de correction")
echo leaves > "$TRIAL/author.$A"; echo corrects > "$TRIAL/author.$B"
for t in "$A" "$B"; do
  gc bd dep add "$CONVOY" "$t" --type tracks >/dev/null
  gc bd update "$t" --set-metadata gc.ticket_kind=vertical_slice >/dev/null
done

echo "relevé d'essai — tour de correction unique, arrêt du ticket, dérogation ; cité isolée ($(gc version 2>/dev/null | head -1), N=$CEILING, aucun Mayor ; relecteur, Evaluator et auteur de correction scriptés ; vraie porte de dispatch, vrai lancement du produit, vraie commande de fusion)"
echo "convoi $CONVOY (Spec $SPEC) : A=$A (tour de correction sans correction) B=$B (corrigé à son tour de correction)"

state mark "$CONVOY" --demonstration-line "$A=$LINE" --demonstration-line "$B=$LINE" \
  --user-stories "$A=1" --user-stories "$B=1" >/dev/null
opened=$("$ROOT/bin/spec-integration" open "$CONVOY" --repo "$PRODUCT" --protected main) \
  || fail "spec-integration open did not pass: $opened"
INTEGRATION="integration/$SPEC"
printf '%s' "$INTEGRATION" > "$TRIAL/integration"

# --- the first author of each ticket, written as its tools would ---------------------
field() { gc bd show "$1" --json | jq -r --arg k "$2" '.[0].metadata[$k] // empty'; }
author_finishes() { # <ticket>: a slice finished at its tip with both defects; prints the tip
  local t=$1 red tip files
  state record-gate "$CONVOY" "$t" --gate dispatch >/dev/null
  state set-branch "$CONVOY" "$t" --branch "ticket/$t" >/dev/null
  state set-session "$CONVOY" "$t" --session "trial-author-$t" >/dev/null
  state set-model "$CONVOY" "$t" --role author --agent trial-author --provider stub-author --model modele-auteur >/dev/null
  red=$(commit_on "$t" "$FIXTURE/tests/test_count_$t.py" "# test de critère du ticket $t" "tests de critère")
  tip=$(commit_on "$t" "docs/$t.md" "Le nombre d'éléments n'est pas affiché sur la page d'accueil." "la tranche")
  files=$(jq -n --arg p "$FIXTURE/tests/test_count_$t.py" --arg d "sha256:$(git -C "$PRODUCT" show "$red:$FIXTURE/tests/test_count_$t.py" | sha256sum | cut -d' ' -f1)" '{($p): $d}')
  state set-tdd "$CONVOY" "$t" --step red --commit "$red" --base "$BASE" >/dev/null
  jq -n --argjson files "$files" --arg id "$FIXTURE/tests/test_count_$t.py::CountTest.test_count" '{files: $files, criteria: {"1": [$id]}}' > "$TRIAL/request.$t.json"
  state open-test-review "$CONVOY" "$t" --commit "$red" --file "$TRIAL/request.$t.json" >/dev/null
  jq -n --argjson files "$files" --arg commit "$red" --arg id "$FIXTURE/tests/test_count_$t.py::CountTest.test_count" \
    '{commit: $commit, files: $files, tests: {($id): {state: "favorable"}}, recorded_by: "trial-test-reviewer"}' > "$TRIAL/verdict.$t.json"
  state record-test-review "$CONVOY" "$t" --file "$TRIAL/verdict.$t.json" >/dev/null
  state set-tdd "$CONVOY" "$t" --step freeze --commit "$red" >/dev/null
  finish "$CONVOY" "$t" "$tip" || fail "the first author could not finish $t"
  printf '%s' "$tip"
}
TIP_A=$(author_finishes "$A")
TIP_B=$(author_finishes "$B")
echo "$(date -u +%H:%M:%S) marque posée, branche $INTEGRATION ouverte, deux tickets terminés par leur auteur (A $TIP_A, B $TIP_B) : diff contraire à la Spec, critère non réalisé"

(gc supervisor run > "$TRIAL/supervisor.out" 2>&1 &)
sleep 3
gc --city "$CITY" start >/dev/null 2>&1 || true
grep -q "Controller: supervisor-managed" <<<"$(gc --city "$CITY" status 2>/dev/null)" || fail "the isolated city's controller did not start"
gc order show convoy-advance --json >/dev/null 2>&1 || fail "the city does not accept orders/convoy-advance.toml"
grep -q "^mol-ticket-correction\$" <<<"$(gc formula list 2>/dev/null)" || fail "the city does not resolve formulas/mol-ticket-correction.formula.toml"

wait_for() { # <seconds> <command...>
  local deadline=$(( $(date +%s) + $1 )); shift
  until "$@"; do
    [ "$(date +%s)" -lt "$deadline" ] || return 1
    sleep 5
  done
}
merged() { [ "$(field "$1" gc.flow.merge | jq -r '.outcome // empty' 2>/dev/null)" = merged ]; }
on_integration() { git -C "$PRODUCT" merge-base --is-ancestor "$1" "$INTEGRATION"; }
dump() {
  for log in reviewer evaluator author; do tail -15 "$TRIAL/$log.log" >&2 2>/dev/null || true; done
  tail -3 "$TRIAL/passes.jsonl" >&2 || true
}
operator_list() { "$ROOT/bin/escalation-door" list 2>&1; }
on_list() { operator_list | sed -n '/^NEEDS BENJAMIN:/,/^Pending proposals/p' | grep -c "^  $1 — " || true; }
shown() { "$ROOT/bin/convoy-state" show "$CONVOY" --repo "$PRODUCT" | jq -c --arg t "$1" '.tickets[] | select(.id == $t)'; }
correction_sessions() { # <ticket>: how many author sessions took its correction round
  [ -f "$TRIAL/correction-sessions" ] || { echo 0; return 0; }
  grep -c "^$1 " "$TRIAL/correction-sessions" || true
}

# --- A: review and evaluation on the same commit, by the same pass ------------------
a_refused_by_both() {
  [ "$(field "$A" gc.flow.code_review | jq -r '.rounds[0].verdict // empty' 2>/dev/null)" = unfavorable ] \
    && [ "$(field "$A" gc.flow.evaluation | jq -r '.rounds[0].verdict // empty' 2>/dev/null)" = unfavorable ]
}
wait_for 600 a_refused_by_both || { dump; fail "the review and the evaluation of A did not both refuse it within 600s"; }
review_a=$(field "$A" gc.flow.code_review | jq -c '.rounds[0]')
evaluation_a=$(field "$A" gc.flow.evaluation | jq -c '.rounds[0]')
[ "$(printf '%s' "$review_a" | jq -r '.commit')" = "$TIP_A" ] && [ "$(printf '%s' "$evaluation_a" | jq -r '.commit')" = "$TIP_A" ] \
  || fail "the review and the evaluation of A were not made on the same commit $TIP_A: $review_a / $evaluation_a"
same_pass=$(jq -c --arg a "$A" 'select(any(.convoys[]; ([.code_review.launched[]?.ticket] | index($a)) != null and ([.evaluation.launched[]?.ticket] | index($a)) != null)) | .at' "$TRIAL/passes.jsonl" | head -1)
[ -n "$same_pass" ] || fail "no single pass sent both the review and the evaluation of A: $(jq -c '.convoys[] | {code_review, evaluation}' "$TRIAL/passes.jsonl" | head -5)"
review_started=$(grep "^$A .* review " "$TRIAL/review-sessions" | head -1 | awk '{print $NF}')
evaluation_started=$(grep "^$A " "$TRIAL/evaluation-sessions" | head -1 | awk '{print $NF}')
printf '%s' "$review_a" | jq -e --arg line "$SPEC_LINE" '.kind == "review" and (.findings | length) == 1 and .findings[0].blocking and .findings[0].citation.quote == $line' >/dev/null \
  || fail "the review of A did not record its Blocking Finding: $review_a"
printf '%s' "$evaluation_a" | jq -e '.outcome == "return_to_author" and .criteria[0].state == "not_observed" and .demonstration_line.state == "not_observed"' >/dev/null \
  || fail "the evaluation of A did not record « not_observed »: $evaluation_a"
echo "$(date -u +%H:%M:%S) A : revue et évaluation envoyées par la même passe (${same_pass//\"/}), sur le même commit $TIP_A ; session relecteur démarrée à $review_started, session Evaluator à $evaluation_started, sans attendre l'autre ; revue défavorable (F1.1, cite « $SPEC_LINE »), évaluation défavorable (critère 1 et ligne de démonstration non observés)"

# --- A: one author session, whose inputs hold the findings of both -------------------
a_round_sent() { [ "$(correction_sessions "$A")" -ge 1 ]; }
wait_for 600 a_round_sent || { dump; fail "no correction session started for A within 600s"; }
brief_a=$(ls "$TRIAL"/correction-brief."$A".*.json | head -1)
jq -e --arg tip "$TIP_A" --arg line "$SPEC_LINE" --arg criterion "$CRITERION" '
  .commit == $tip
  and ([.code_review.blocking_findings[].id] == ["F1.1"]) and .code_review.blocking_findings[0].citation.quote == $line
  and ([.evaluation.not_observed[].what] == ["critère 1", "ligne de démonstration"])
  and .evaluation.not_observed[0].text == $criterion and (.evaluation.not_observed[0].reason | length) > 0' "$brief_a" >/dev/null \
  || fail "the brief of the correction session of A does not hold the findings of both: $(jq -c '{commit, code_review, evaluation}' "$brief_a")"
author_a=$(grep "^$A " "$TRIAL/correction-sessions" | head -1 | cut -d' ' -f3)
[ "$author_a" != "trial-author-$A" ] || fail "the correction session of A is the session that wrote it"
a_taken() { [ "$(field "$A" gc.flow.session | jq -r '.name // empty')" = "$author_a" ]; }
wait_for 60 a_taken || fail "the correction session of A did not take the ticket (bin/ticket-author start): $(field "$A" gc.flow.session)"
[ "$(shown "$A" | jq -c '.counters')" = '{"correction_rounds":1,"resumes":1}' ] \
  || fail "the correction round of A is not counted among its resumes: $(shown "$A" | jq -c '.counters')"
echo "$(date -u +%H:%M:%S) A : une session neuve d'auteur ($author_a, ≠ trial-author-$A) a pris le ticket par la vraie porte de dispatch ; son brief contient F1.1 (revue) et critère 1 + ligne de démonstration (évaluation) ; compteurs relus : $(shown "$A" | jq -c '.counters')"

# --- A: still refused after its round -> stopped, one item, nothing merged ------------
a_stopped() { [ "$(field "$A" gc.flow.stop | jq -r '.reason // empty' 2>/dev/null)" = still_refused ]; }
wait_for 600 a_stopped || { dump; fail "A was not stopped after its correction round within 600s"; }
a_raised() { [ "$(on_list "$A")" = 1 ]; }
wait_for 120 a_raised || { dump; fail "the stop of A is not exactly once on the operator's list: $(operator_list)"; }
sleep 75   # at least two more passes of the order
[ "$(correction_sessions "$A")" = 1 ] || fail "A got $(correction_sessions "$A") correction sessions, not one"
[ "$(field "$A" gc.flow.correction | jq -r '.launches | length')" = 1 ] || fail "A does not carry exactly one launch of its correction round"
merged "$A" && fail "A was merged although it is still refused"
on_integration "$TIP_A" && fail "the tip of A reached the integration branch"
[ "$(on_list "$A")" = 1 ] || fail "A is not exactly once on the operator's list after later passes: $(operator_list)"
[ "$(shown "$A" | jq -c '.counters')" = '{"correction_rounds":1,"resumes":1}' ] || fail "the counters of A moved after its stop: $(shown "$A" | jq -c '.counters')"
echo "$(date -u +%H:%M:%S) A : session de correction terminée sans corriger ; ticket arrêté (still_refused : $(field "$A" gc.flow.stop | jq -r '.detail')) ; aucun second tour (1 session, 1 lancement), rien de fusionné ; une seule ligne sur la liste : $(operator_list | grep "^  $A — " | head -1)"

# --- A: the override of the Blocking Finding, and what is refused ---------------------
override() { "$ROOT/bin/correction-round" override "$CONVOY" "$A" --repo "$PRODUCT" "$@"; }
WORDS="Je passe outre F1.1 : la phrase du fichier de notes n'est pas le produit."
before=$(gc bd show "$A" --json | jq -c '.[0].metadata')
other=$(override --finding F1.1 --approved-by trial-author --words "$WORDS") && fail "an override by another than the declared human approver was accepted: $other"
printf '%s' "$other" | grep -q "approbateur humain déclaré" || fail "the refusal of the wrong approver does not say why: $other"
empty=$(override --finding F1.1 --approved-by "$APPROVER" --words "  ") && fail "an override without words was accepted: $empty"
criterion=$(override --criterion 1 --approved-by "$APPROVER" --words "$WORDS") && fail "the override of a criterion that was not observed was accepted: $criterion"
printf '%s' "$criterion" | grep -q "Planning Exception" || fail "the refusal for a criterion does not name the Planning Exception: $criterion"
[ "$(gc bd show "$A" --json | jq -c '.[0].metadata')" = "$before" ] || fail "a refused override wrote something on A"
accepted=$(override --finding F1.1 --approved-by "$APPROVER" --words "$WORDS") || fail "the override of F1.1 by the declared human approver was refused: $accepted"
read_back=$("$ROOT/bin/correction-round" show "$CONVOY" "$A" --repo "$PRODUCT" | jq -c '.overrides')
printf '%s' "$read_back" | jq -e --arg who "$APPROVER" --arg words "$WORDS" \
  'length == 1 and .[0].finding == "F1.1" and .[0].state == "dérogation enregistrée" and .[0].approver == $who and .[0].words == $words' >/dev/null \
  || fail "the override of A is not read back as recorded: $read_back"
echo "$(date -u +%H:%M:%S) A : dérogation de $APPROVER sur F1.1 acceptée et relue « $(printf '%s' "$read_back" | jq -r '.[0].state') » avec ses mots ; refusées sans rien écrire : par trial-author (« $(printf '%s' "$other" | jq -r '.error' | cut -c1-90)… »), sans mots, et sur le critère 1 (« $(printf '%s' "$criterion" | jq -r '.error' | cut -c1-110)… »)"

# --- B: corrected at its round -> judged, evaluated again, merged, one resume ---------
wait_for 900 merged "$B" || { dump; fail "B was not merged within 900s once its correction round corrected it"; }
FIX_B=$(git -C "$PRODUCT" rev-parse "ticket/$B")
on_integration "$FIX_B" || fail "the corrected tip of B is not on the integration branch"
[ "$(correction_sessions "$B")" = 1 ] || fail "B got $(correction_sessions "$B") correction sessions, not one"
judgement=$(field "$B" gc.flow.code_review | jq -c '.rounds[-1]')
printf '%s' "$judgement" | jq -e --arg tip "$FIX_B" --arg base "$TIP_B" \
  '.kind == "judgement" and .verdict == "favorable" and .commit == $tip and .base == $base' >/dev/null \
  || fail "the answers of B were not judged favorably at its corrected tip: $judgement"
[ "$(printf '%s' "$judgement" | jq -r '.recorded_by')" != "$(field "$B" gc.flow.code_review | jq -r '.rounds[0].recorded_by')" ] \
  || fail "the judgement of B was given by the session that reviewed it"
field "$B" gc.flow.evaluation | jq -e --arg tip "$FIX_B" '.rounds[-1] | .commit == $tip and .outcome == "favorable"' >/dev/null \
  || fail "B was not evaluated favorably at its corrected tip: $(field "$B" gc.flow.evaluation | jq -c '.rounds[-1]')"
[ "$(shown "$B" | jq -c '.counters')" = '{"correction_rounds":1,"resumes":1}' ] \
  || fail "the correction round of B did not count exactly one resume: $(shown "$B" | jq -c '.counters')"
[ -z "$(field "$B" gc.flow.stop)" ] || fail "B was stopped although its round corrected it"
[ "$(on_list "$B")" = 0 ] || fail "B is on the operator's list"
echo "$(date -u +%H:%M:%S) B : une session de correction ($(grep "^$B " "$TRIAL/correction-sessions" | cut -d' ' -f3)) a corrigé au commit $FIX_B et répondu « corrigé » à F1.1 ; jugement favorable par une seconde session relecteur, évaluation rejouée et favorable à la nouvelle pointe ; ticket fusionné dans $INTEGRATION ; compteurs relus : $(shown "$B" | jq -c '.counters')"

gc session list --state all --json | jq -e '[.sessions[] | select(.template | test("mayor"))] | length == 0' >/dev/null \
  || fail "a Mayor session exists in the trial city"
echo "PASS: one correction round per ticket received the findings of the review and of the evaluation; a ticket still refused stopped as one item; only a Blocking Finding took an override"
