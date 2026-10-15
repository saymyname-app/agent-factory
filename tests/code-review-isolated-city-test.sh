#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime, an isolated Dolt server and its own supervisor
#
# Adoption trial of the code review of a ticket before its merge (T14,
# af-96cusm; Spec af-wf4w5r §6, §8) in a disposable city that shares nothing
# with the live Factory: its own GC_HOME, runtime directory, supervisor port,
# controller, evidence store and work trees. The product is a copy of the
# Delivery Fixture City, committed in the city root. The city has no Mayor.
#
# What is real: the controller, the order that advances the convoy
# (bin/convoy-advance), the formula mol-code-review, bin/code-review,
# bin/convoy-state, bin/spec-integration (the merge control and the merges),
# bin/dispatch-door (which routes each review to the agent of the reviewer
# role) and bin/escalation-door. What is scripted, and spends nothing: the
# reviewer, a stub that claims the step Gas City routes to it and runs the
# real tools the step names; and the author, whose finished tickets are
# written through bin/convoy-state as bin/tdd-step, bin/test-review and
# bin/ticket-exit would (the author formula has its own trial,
# tests/ticket-author-isolated-city-test.sh), each with the favorable Ticket
# Evaluation the merge also asks for, written as bin/ticket-evaluation would
# (its own trial: tests/ticket-evaluation-isolated-city-test.sh).
#
# Three tickets of the fixture, each finished by its author:
#   A  its diff contradicts a line of the Spec: the review records a Blocking
#      Finding that cites that line, and the merge is refused. The author
#      answers « corrigé » with a new commit; a second reviewer session
#      judges the answer favorably, and the ticket is merged. Its reviewer
#      runs on the author's model: the mention is recorded.
#   B  its reviewer gives a finding of taste as blocking, without citation:
#      it is recorded as non-blocking, and the ticket is merged.
#   C  its reviewer sessions end without a verdict: one relaunch, then the
#      ticket is stopped, appears once on the operator's list, and is never
#      merged.
#
# The trial prints its record (« relevé d'essai ») on stdout.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
. "$ROOT/tests/lib/isolated-city.sh"
PORT="${CODE_REVIEW_TRIAL_PORT:-18401}"
CEILING=6
SPEC_LINE="La page d'accueil affiche le nombre d'éléments du jeu de données."

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc bd jq git dolt tmux curl python3; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

TRIAL=$(mktemp -d /tmp/af-96cusm-review.XXXXXX)
CITY="$TRIAL/c"
PRODUCT="$CITY"
FIXTURE="tests/fixtures/delivery-fixture-city"
cleanup() {
  status=$?
  trap - EXIT
  isolated_city_stop "$TRIAL" "$CITY" >/dev/null 2>&1 || true
  tmux -L "$(basename "$TRIAL")" kill-server >/dev/null 2>&1 || true
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
    rm -rf -- "$TRIAL"
  fi
  exit "$status"
}
trap cleanup EXIT

# Nothing of the live Factory may reach this city (same recipe as
# tests/test-review-isolated-city-test.sh).
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$|FACTORY_ROOT$|CONVOY_|DISPATCH_DOOR_|ESCALATION_DOOR_|EVIDENCE_|TICKET_AUTHOR_|SPEC_INTEGRATION_|TEST_REVIEW_|CODE_REVIEW_(DISPATCH|FAKE)|DELIVERY_ROLE_)' || true)
export GC_HOME="$TRIAL/h" XDG_RUNTIME_DIR="$TRIAL/r" GC_DISABLE_USAGE_METRICS=1
unset DBUS_SESSION_BUS_ADDRESS
export PATH="/usr/local/bin:$HOME/.local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
mkdir -p "$GC_HOME"
mkdir -m 700 "$XDG_RUNTIME_DIR"
printf '[supervisor]\nport = %s\n' "$PORT" > "$GC_HOME/supervisor.toml"

# What every tool of the flow reads, in the stub sessions and in the order
# alike: the city as Factory root, and stores of the trial. The dispatch door
# is the real one; it asks these stubs where a role runs and whether its
# adoption trial passed (the stubs of this city are no provider to try). The
# same answer says which provider, hence which model, each role runs on.
cat > "$TRIAL/env" <<ENV
export FACTORY_ROOT="$CITY"
export CONVOY_STATE_LOCK_DIR="$TRIAL/locks" CONVOY_ADVANCE_LOCK_DIR="$TRIAL/locks" SPEC_INTEGRATION_LOCK_DIR="$TRIAL/locks"
export SPEC_INTEGRATION_WORK_DIR="$TRIAL/merge"
export EVIDENCE_STORE_DIR="$TRIAL/store"
export ESCALATION_DOOR_LOCK_FILE="$TRIAL/escalation-door.lock" PROPOSAL_DOOR_BIN="$TRIAL/proposal-door"
export DISPATCH_DOOR_PROVIDER_FAILOVER_BIN="$TRIAL/provider-failover" DISPATCH_DOOR_ROLE_TRIAL_BIN="$TRIAL/role-adoption-trial"
export DELIVERY_ROLE_PROVIDER_FAILOVER_BIN="$TRIAL/provider-failover"
export GIT_AUTHOR_NAME=essai GIT_AUTHOR_EMAIL=essai@example.invalid GIT_COMMITTER_NAME=essai GIT_COMMITTER_EMAIL=essai@example.invalid
ENV
printf '#!/bin/sh\necho 0\n' > "$TRIAL/proposal-door"
cat > "$TRIAL/provider-failover" <<'SH'
#!/bin/sh
printf '%s\n' '{"total_exhaustion": {"active": false}, "targets": {"trial-author": {"effective": "stub-author"}, "trial-reviewer": {"effective": "stub-reviewer"}}}'
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

# --- the scripted reviewer --------------------------------------------------------
# One session, one round, as the step of mol-code-review asks: the brief,
# then a review or a judgement handed to `code-review record`. Its judgement
# is a rule read from the diff the brief names: a diff that says the count is
# not shown contradicts the line of the Spec, which it cites; for a ticket
# whose reviewer is « taste » it gives a smell as blocking, without citation;
# for a ticket whose reviewer is « mute » the session ends without a verdict,
# as a crashed one would. A judgement finds every answer right.
cat > "$TRIAL/stub-reviewer" <<STUB
#!/bin/bash
. "$TRIAL/env"
export DELIVERY_ROLE_READ_ONLY=1
BIN="$ROOT/bin"
LOG="$TRIAL/reviewer.log"
say() { echo "\$(date -u +%H:%M:%S) \${GC_SESSION_NAME:-?} \$*" >> "\$LOG"; }
while true; do
  CLAIM=\$(gc hook --claim --json 2>/dev/null)
  ACTION=\$(printf '%s' "\$CLAIM" | jq -r '.action // empty' 2>/dev/null)
  BEAD=\$(printf '%s' "\$CLAIM" | jq -r '.bead_id // empty' 2>/dev/null)
  if [ "\$ACTION" != work ] || [ -z "\$BEAD" ]; then sleep 3; continue; fi
  ROOT_BEAD=\$(gc bd show "\$BEAD" --json | jq -r '.[0].metadata["gc.root_bead_id"]')
  INPUT=\$(gc bd show "\$ROOT_BEAD" --json | jq -r '.[0].metadata["gc.input_convoy_id"]')
  REVIEW_BEAD=\$(gc convoy status "\$INPUT" --json | jq -r '.children[0].id')
  TEXT=\$(gc bd show "\$REVIEW_BEAD" --json | jq -r '.[0].description')
  CONVOY=\$(printf '%s\n' "\$TEXT" | sed -n 's/^convoy: //p'); TICKET=\$(printf '%s\n' "\$TEXT" | sed -n 's/^ticket: //p')
  OUTCOME=pass
  MODE=\$(cat "$TRIAL/reviewer.\$TICKET")
  if [ "\$MODE" = mute ]; then
    echo "\$TICKET \$REVIEW_BEAD \${GC_SESSION_NAME:-?} mute" >> "$TRIAL/review-sessions"
    say "ticket \$TICKET : session terminée sans verdict (\$REVIEW_BEAD)"
    OUTCOME=fail
  else
    BRIEF="$TRIAL/brief.\$REVIEW_BEAD.json"
    if ! "\$BIN/code-review" brief "\$CONVOY" "\$TICKET" > "\$BRIEF.new" 2>>"\$LOG"; then
      # Seen in this trial (gc 1.4.1): once a stub has drained and exited, a
      # session is started again on the step it just closed. Nothing is
      # asked any more: the brief it was given stays, nothing is written.
      say "ticket \$TICKET : aucune revue demandée (\$REVIEW_BEAD), rien à faire"
      rm -f "\$BRIEF.new"
      gc runtime drain-ack >/dev/null 2>&1
      exit 0
    fi
    mv "\$BRIEF.new" "\$BRIEF"
    KIND=\$(jq -r '.kind' "\$BRIEF")
    echo "\$TICKET \$REVIEW_BEAD \${GC_SESSION_NAME:-?} \$KIND" >> "$TRIAL/review-sessions"
    RESULT="$TRIAL/result.\$REVIEW_BEAD.json"
    if [ "\$KIND" = judgement ]; then
      jq '{commit, judgements: (.findings | map({key: .id, value: {state: "favorable"}}) | from_entries)}' "\$BRIEF" > "\$RESULT"
    else
      DIFF=\$(sh -c "\$(jq -r '.diff.command' "\$BRIEF")")
      FINDINGS='[]'
      if [ "\$MODE" = taste ]; then
        FINDINGS='[{"axis": "standards", "blocking": true, "summary": "Possible Mysterious Name : le fichier de la tranche ne dit pas ce qu'"'"'il contient."}]'
      elif printf '%s' "\$DIFF" | grep -q "n'est pas affiché"; then
        FINDINGS=\$(jq -c --arg line "$SPEC_LINE" '[{axis: "spec", blocking: true, summary: "Le diff dit que le nombre n'"'"'est pas affiché.", citation: {source: "spec", quote: (.spec.text | split("\n") | map(select(contains(\$line))) | .[0] | sub("^[0-9]+\\\\. "; ""))}}]' "\$BRIEF")
      fi
      jq --argjson findings "\$FINDINGS" '{commit, findings: \$findings, answers: (.questions | map({key: .id, value: {answer: "oui"}}) | from_entries)}' "\$BRIEF" > "\$RESULT"
    fi
    # A review the trial holds is handed once the trial releases it.
    while [ -e "$TRIAL/hold.\$TICKET" ]; do sleep 2; done
    "\$BIN/code-review" record "\$CONVOY" "\$TICKET" --file "\$RESULT" >> "\$LOG" 2>&1 || OUTCOME=fail
    say "ticket \$TICKET : \$KIND remis (\$REVIEW_BEAD, \$OUTCOME)"
  fi
  gc bd update "\$REVIEW_BEAD" --set-metadata gc.outcome=\$OUTCOME --status=closed --notes "revue \$OUTCOME" >/dev/null 2>&1
  gc bd update "\$BEAD" --set-metadata gc.outcome=\$OUTCOME --status=closed --notes "revue \$OUTCOME" >/dev/null 2>&1
  gc runtime drain-ack >/dev/null 2>&1
  exit 0
done
STUB
chmod +x "$TRIAL/stub-reviewer"

# --- the city: a reviewer agent on its stub, the real formula, the real order ----
cat > "$CITY/city.toml" <<TOML
[workspace]
provider = "stub-reviewer"

[providers.stub-author]
base = "builtin:claude"
command = "/bin/true"
ready_delay_ms = 0

[providers.stub-reviewer]
base = "builtin:claude"
command = "$TRIAL/stub-reviewer"
# A stub is a shell script: without its process name Gas City finds no
# \`claude\` process in the session and reaps it as a zombie.
process_names = ["stub-reviewer", "bash"]
ready_delay_ms = 0
TOML
mkdir -p "$CITY/agents/trial-reviewer" "$CITY/formulas" "$CITY/orders" "$CITY/config/projects" "$CITY/config/project-descriptors"
cat > "$CITY/agents/trial-reviewer/agent.toml" <<'TOML'
description = "Reviewer of the code-review trial (scripted stub, spends nothing)"
scope = "city"
min_active_sessions = 0
max_active_sessions = 2
provider = "stub-reviewer"
wake_mode = "fresh"
TOML
echo "Scripted reviewer of the code-review trial." > "$CITY/agents/trial-reviewer/prompt.template.md"
cp "$ROOT/formulas/mol-code-review.formula.toml" "$CITY/formulas/"
cat > "$CITY/config/projects/trial.toml" <<TOML
rig_dir = "."
repo = "example/trial"
protected_branch = "main"
required_ci = "CI"
sling_target = "trial-reviewer"
formulas = "mol-code-review"
TOML
jq '.rigs = ["trial"] | .stacks = {"trial": ["fixture-stack"]}' "$ROOT/$FIXTURE/descriptor.json" > "$CITY/config/project-descriptors/trial.json"
jq -n --argjson n "$CEILING" '{contract: "agent-factory-delivery-flow/v1", max_sessions: $n,
  start: {formula: "mol-ticket-author", role: "author"},
  code_review: {formula: "mol-code-review", role: "reviewer", rig: "trial", timeout_seconds: 600},
  evaluation: {formula: "mol-ticket-evaluation", role: "evaluator", rig: "trial", timeout_seconds: 600, start_timeout_seconds: 30}}' \
  > "$CITY/config/delivery-flow.json"
jq '.roles.author.agent = "trial-author" | .roles.reviewer.agent = "trial-reviewer"' "$ROOT/config/delivery-roles.json" \
  > "$CITY/config/delivery-roles.json"
# The model of each provider of the trial: the reviewer's is « modele-relecteur ».
jq -n '{providers: {"stub-author": {recommended: ["modele-auteur"]}, "stub-reviewer": {recommended: ["modele-relecteur"]}}}' \
  > "$CITY/config/model-catalog.json"

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

Le nombre d'éléments sur la page d'accueil.

## Acceptance criteria

- [ ] Point d'entrée : GET / — Observable : ancre fixture-count — Faux si : le nombre d'éléments n'y est pas

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
A=$(new_ticket "ticket A, diff qui contredit la Spec")
B=$(new_ticket "ticket B, constat de goût")
C=$(new_ticket "ticket C, revue sans sortie")
ALL=("$A" "$B" "$C")
echo cites > "$TRIAL/reviewer.$A"; echo taste > "$TRIAL/reviewer.$B"; echo mute > "$TRIAL/reviewer.$C"
: > "$TRIAL/hold.$B"
for t in "${ALL[@]}"; do
  gc bd dep add "$CONVOY" "$t" --type tracks >/dev/null
  gc bd update "$t" --set-metadata gc.ticket_kind=vertical_slice >/dev/null
done

echo "relevé d'essai — revue de code par ticket avant la fusion, cité isolée ($(gc version 2>/dev/null | head -1), N=$CEILING, aucun Mayor, relecteur scripté, vraie porte de dispatch, vraie commande de fusion)"
echo "convoi $CONVOY (Spec $SPEC) : A=$A (diff contraire à la Spec) B=$B (constat de goût) C=$C (relecteur sans verdict)"

state mark "$CONVOY" \
  --demonstration-line "$A=La page d'accueil affiche le nombre d'éléments" \
  --demonstration-line "$B=La page d'accueil affiche le nombre d'éléments" \
  --demonstration-line "$C=La page d'accueil affiche le nombre d'éléments" \
  --user-stories "$A=1" --user-stories "$B=1" --user-stories "$C=1" >/dev/null
opened=$("$ROOT/bin/spec-integration" open "$CONVOY" --repo "$PRODUCT" --protected main) \
  || fail "spec-integration open did not pass: $opened"
INTEGRATION="integration/$SPEC"

# --- the author's side, written as its tools would: a ticket finished at its tip ---
field() { gc bd show "$1" --json | jq -r --arg k "$2" '.[0].metadata[$k] // empty'; }
commit_on() { # <ticket> <path> <content> <message>: one commit on the branch of the ticket; prints its SHA
  local wt="$TRIAL/wt/$1"
  if [ ! -d "$wt" ]; then
    git -C "$PRODUCT" worktree add -q -b "ticket/$1" "$wt" "$INTEGRATION" >/dev/null 2>&1 || fail "no work tree for $1"
  fi
  mkdir -p "$wt/$(dirname "$2")"
  printf '%s\n' "$3" > "$wt/$2"
  git -C "$wt" add -A
  git -C "$wt" commit -q -m "$4"
  git -C "$wt" rev-parse HEAD
}
evaluated() {  # TICKET COMMIT REPO: a favorable Ticket Evaluation, as an Evaluator session records it (bin/ticket-evaluation, T15)
  local shown
  shown=$("$ROOT/bin/convoy-state" show "$CONVOY" --repo "$3" | jq -c --arg t "$1" '.tickets[] | select(.id == $t)')
  jq -n '{roles: {author: null, evaluator: null, same_provider: null, other_declared: []},
    environment: [{dataset: null, address: "http://127.0.0.1:1", state_file: "/launch.json"}]}' > "$TRIAL/evaluation-request-$1.json"
  state open-evaluation "$CONVOY" "$1" --commit "$2" --file "$TRIAL/evaluation-request-$1.json" >/dev/null
  python3 "$ROOT/tests/lib/ticket_proofs.py" capture "$CONVOY" "$1" evaluation.seen "$2" --repo "$3" >/dev/null
  jq -n --arg commit "$2" --arg session "delivery-evaluator-trial-$1-${2:0:12}" --argjson t "$shown" '{commit: $commit, recorded_by: $session,
    criteria: [$t.criteria | to_entries[] | {number: (.key + 1), text: .value, state: "observed", evidence: "evaluation.seen"}],
    demonstration_line: {text: $t.demonstration_line, state: "observed", evidence: "evaluation.seen"}}' > "$TRIAL/evaluation-$1.json"
  state record-evaluation "$CONVOY" "$1" --file "$TRIAL/evaluation-$1.json" >/dev/null
}
finish() { # <ticket> <tip>: every step of the TDD with its sealed report, the demonstration, the sealed records, the Handoff, the exit, a favorable evaluation
  python3 "$ROOT/tests/lib/ticket_proofs.py" finish "$CONVOY" "$1" "$2" --repo "$PRODUCT" --base "$BASE" --branch "ticket/$1" \
    --done "PROSE-DU-HANDOFF : fait à ma façon." --subject "PROSE-DU-COMMIT" >/dev/null
  evaluated "$1" "$2" "$PRODUCT"
}
author_finishes() { # <ticket> <author model> <what the slice says>
  local t=$1 red tip files
  state record-gate "$CONVOY" "$t" --gate dispatch >/dev/null
  state set-branch "$CONVOY" "$t" --branch "ticket/$t" >/dev/null
  state set-session "$CONVOY" "$t" --session "trial-author-$t" >/dev/null
  state set-model "$CONVOY" "$t" --role author --agent trial-author --provider stub-author --model "$2" >/dev/null
  red=$(commit_on "$t" "$FIXTURE/tests/test_count_$t.py" "# test de critère du ticket $t" "PROSE-DU-COMMIT : tests de critère")
  tip=$(commit_on "$t" "docs/$t.md" "$3" "PROSE-DU-COMMIT : la tranche")
  files=$(jq -n --arg p "$FIXTURE/tests/test_count_$t.py" --arg d "sha256:$(git -C "$PRODUCT" show "$red:$FIXTURE/tests/test_count_$t.py" | sha256sum | cut -d' ' -f1)" '{($p): $d}')
  state set-tdd "$CONVOY" "$t" --step red --commit "$red" --base "$BASE" >/dev/null
  jq -n --argjson files "$files" --arg id "$FIXTURE/tests/test_count_$t.py::CountTest.test_count" '{files: $files, criteria: {"1": [$id]}}' > "$TRIAL/request.$t.json"
  state open-test-review "$CONVOY" "$t" --commit "$red" --file "$TRIAL/request.$t.json" >/dev/null
  jq -n --argjson files "$files" --arg commit "$red" --arg session "trial-test-reviewer-$t" --arg id "$FIXTURE/tests/test_count_$t.py::CountTest.test_count" \
    '{commit: $commit, files: $files, tests: {($id): {state: "favorable"}}, recorded_by: $session}' > "$TRIAL/verdict.$t.json"
  state record-test-review "$CONVOY" "$t" --file "$TRIAL/verdict.$t.json" >/dev/null
  state set-tdd "$CONVOY" "$t" --step freeze --commit "$red" >/dev/null
  finish "$t" "$tip"
  printf '%s' "$tip"
}

# A's author runs on the reviewer's model; B's and C's on another one.
TIP_A=$(author_finishes "$A" modele-relecteur "Le nombre d'éléments n'est pas affiché sur la page d'accueil.")
TIP_B=$(author_finishes "$B" modele-auteur "Le nombre d'éléments est affiché sur la page d'accueil.")
TIP_C=$(author_finishes "$C" modele-auteur "Le nombre d'éléments est affiché, vu par C.")
echo "$(date -u +%H:%M:%S) marque posée, branche $INTEGRATION ouverte, trois tickets terminés par leur auteur (A $TIP_A, B $TIP_B, C $TIP_C)"

(env -u CLAUDE_CODE_SESSION_ID gc supervisor run > "$TRIAL/supervisor.out" 2>&1 &)
sleep 3
gc --city "$CITY" start >/dev/null 2>&1 || true
grep -q "Controller: supervisor-managed" <<<"$(gc --city "$CITY" status 2>/dev/null)" || fail "the isolated city's controller did not start"
gc order show convoy-advance --json >/dev/null 2>&1 || fail "the city does not accept orders/convoy-advance.toml"
grep -q "^mol-code-review\$" <<<"$(gc formula list 2>/dev/null)" || fail "the city does not resolve formulas/mol-code-review.formula.toml"

wait_for() { # <seconds> <command...>
  local deadline=$(( $(date +%s) + $1 )); shift
  until "$@"; do
    [ "$(date +%s)" -lt "$deadline" ] || return 1
    sleep 5
  done
}
review_of() { field "$1" gc.flow.code_review; }
merged() { [ "$(field "$1" gc.flow.merge | jq -r '.outcome // empty' 2>/dev/null)" = merged ]; }
on_integration() { git -C "$PRODUCT" merge-base --is-ancestor "$1" "$INTEGRATION"; }
dump() { tail -30 "$TRIAL/reviewer.log" >&2 || true; tail -3 "$TRIAL/passes.jsonl" >&2 || true; }
operator_list() { "$ROOT/bin/escalation-door" list 2>&1; }
on_list() { operator_list | sed -n '/^NEEDS BENJAMIN:/,/^Pending proposals/p' | grep -c "^  $1 — " || true; }
sessions_of() { grep "^$1 " "$TRIAL/review-sessions" | cut -d' ' -f3; }

# --- A: a Blocking Finding that cites the Spec; the merge is refused ----------------
a_refused() { [ "$(review_of "$A" | jq -r '.rounds[0].verdict // empty' 2>/dev/null)" = unfavorable ]; }
wait_for 600 a_refused || { dump; fail "the review of A did not give its Blocking Finding within 600s"; }
first=$(review_of "$A" | jq -c '.rounds[0]')
printf '%s' "$first" | jq -e --arg line "$SPEC_LINE" --arg tip "$TIP_A" \
  '.kind == "review" and .commit == $tip and (.findings | length) == 1 and .findings[0].blocking == true
   and .findings[0].citation.source == "spec" and .findings[0].citation.quote == $line' >/dev/null \
  || fail "the review of A did not record one Blocking Finding that cites the line of the Spec: $first"
reviewer_a=$(printf '%s' "$first" | jq -r '.recorded_by')
[ "$reviewer_a" != "trial-author-$A" ] && [ "$reviewer_a" = "$(sessions_of "$A" | head -1)" ] \
  || fail "the review of A was not recorded by a reviewer session distinct from its author: $reviewer_a"
printf '%s' "$first" | jq -e '.models == {author: "modele-relecteur", reviewer: "modele-relecteur", same_model: true}' >/dev/null \
  || fail "the review of A does not carry the mention of identical models: $(printf '%s' "$first" | jq -c .models)"
[ "$(field "$A" gc.flow.models | jq -r '.reviewer.model + " " + .reviewer.agent')" = "modele-relecteur trial-reviewer" ] \
  || fail "the model of the reviewer role is not recorded on A: $(field "$A" gc.flow.models)"
brief_a=$(ls "$TRIAL"/brief.*.json | head -1)
grep -q "PROSE-DU-" "$TRIAL"/brief.*.json && fail "a brief handed to the reviewer holds prose of the author"
jq -e 'has("spec") and has("ticket_text") and has("records") and has("diff")' "$brief_a" >/dev/null || fail "the brief of A lacks its inputs"
sleep 75   # at least two more passes of the order
merged "$A" && fail "A was merged with a Blocking Finding that has no favorable verdict"
on_integration "$TIP_A" && fail "the tip of A reached the integration branch"
waiting=$(tail -1 "$TRIAL/passes.jsonl" | jq -r --arg a "$A" '[.convoys[].integration.waiting[]? | select(.id == $a) | .reason] | .[0] // empty')
echo "$(date -u +%H:%M:%S) A : revue par la session $reviewer_a (auteur trial-author-$A) ; Blocking Finding F1.1 qui cite « $SPEC_LINE » ; mention « même modèle » inscrite (modele-relecteur) ; fusion refusée par la passe : ${waiting:-ticket absent de la fusion}"

# --- C: reviewer without verdict -> one relaunch, then stopped, never merged -------
# Before anything is merged: no reviewer is sent on a branch behind the
# integration tip (T44), so a relaunch of C after the merge of B would be
# refused and C handed back to its author instead of stopped. The review of B
# is held until C is stopped.
c_stopped() { [ "$(field "$C" gc.flow.stop | jq -r '.reason // empty' 2>/dev/null)" = code_review_no_result ]; }
wait_for 900 c_stopped || { dump; fail "C was not stopped after two reviews without result within 900s"; }
# One review bead per launch: a session started again on a bead it already
# closed (seen with these stubs on gc 1.4.1) is not a launch.
launches_c=$(grep "^$C " "$TRIAL/review-sessions" | cut -d' ' -f2 | sort -u | wc -l | tr -d ' ')
[ "$launches_c" = 2 ] || fail "the review of C was launched $launches_c times, not twice"
c_raised() { [ "$(on_list "$C")" = 1 ]; }
wait_for 120 c_raised || { dump; fail "the stop of C is not exactly once on the operator's list: $(operator_list)"; }
[ "$(review_of "$C" | jq -c '.rounds')" = '[]' ] || fail "C carries a verdict nobody gave"
sleep 60
merged "$C" && fail "C was merged although its review gave no verdict"
on_integration "$TIP_C" && fail "the tip of C reached the integration branch"
[ "$(on_list "$C")" = 1 ] || fail "C is not exactly once on the operator's list after later passes"
echo "$(date -u +%H:%M:%S) C : deux sessions de relecteur terminées sans verdict (une relance), ticket arrêté (code_review_no_result), jamais fusionné ; une seule ligne sur la liste : $(operator_list | grep "^  $C — " | head -1)"
rm -f "$TRIAL/hold.$B"

# --- B: a finding of taste is recorded without blocking; the ticket is merged ------
wait_for 600 merged "$B" || { dump; fail "B was not merged within 600s"; }
second=$(review_of "$B" | jq -c '.rounds[0]')
printf '%s' "$second" | jq -e '.verdict == "favorable" and (.findings | length) == 1 and .findings[0].blocking == false
   and (.findings[0].demoted | test("refusé comme bloquant")) and .models.same_model == false' >/dev/null \
  || fail "the finding of taste of B was not recorded as non-blocking: $second"
on_integration "$TIP_B" || fail "the tip of B is not on the integration branch"
echo "$(date -u +%H:%M:%S) B : constat de goût donné comme bloquant sans citation, enregistré non bloquant ($(printf '%s' "$second" | jq -r '.findings[0].demoted')) ; verdict favorable ; modèles distincts (modele-auteur / modele-relecteur) ; ticket fusionné dans $INTEGRATION"

# --- A again: « corrigé », judged by a second reviewer session, merged --------------
# B was merged meanwhile: the author takes the tip of the integration branch
# before the correction. No reviewer is sent on a branch behind it (T44).
git -C "$TRIAL/wt/$A" merge -q --no-edit "$INTEGRATION" || fail "the branch of A did not take the tip of the integration branch"
FIX_A=$(commit_on "$A" "docs/$A.md" "Le nombre d'éléments est affiché sur la page d'accueil." "PROSE-DU-COMMIT : correction")
finish "$A" "$FIX_A"
jq -n --arg commit "$FIX_A" '{responses: {"F1.1": {response: "fixed", commit: $commit}}}' > "$TRIAL/responses.json"
"$ROOT/bin/code-review" respond "$CONVOY" "$A" --file "$TRIAL/responses.json" >/dev/null || fail "code-review respond did not pass on A"
wait_for 600 merged "$A" || { dump; fail "A was not merged within 600s once its Blocking Finding was fixed and judged"; }
judgement=$(review_of "$A" | jq -c '.rounds[1]')
printf '%s' "$judgement" | jq -e --arg tip "$FIX_A" --arg base "$TIP_A" \
  '.kind == "judgement" and .verdict == "favorable" and .commit == $tip and .base == $base and .judgements["F1.1"].state == "favorable"' >/dev/null \
  || fail "the answers of A were not judged favorably at the corrected tip: $judgement"
judge_a=$(printf '%s' "$judgement" | jq -r '.recorded_by')
[ "$judge_a" != "$reviewer_a" ] || fail "the judgement of A was given by the session that reviewed it: $judge_a"
on_integration "$FIX_A" || fail "the corrected tip of A is not on the integration branch"
echo "$(date -u +%H:%M:%S) A : F1.1 « corrigé » au commit $FIX_A, jugé favorablement par une seconde session ($judge_a ≠ $reviewer_a) ; ticket fusionné"

gc session list --state all --json | jq -e '[.sessions[] | select(.template | test("mayor"))] | length == 0' >/dev/null \
  || fail "a Mayor session exists in the trial city"
echo "PASS: each finished ticket was reviewed by a reviewer session before its merge, and code decided what was merged"
