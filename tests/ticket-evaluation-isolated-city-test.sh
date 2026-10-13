#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime, an isolated Dolt server, its own supervisor and bwrap
#
# Adoption trial of the Ticket Evaluation on the launched product (T15,
# af-higj9z; Spec af-wf4w5r §7, §8) in a disposable city that shares nothing
# with the live Factory: its own GC_HOME, runtime directory, supervisor port,
# controller, evidence store, launch records and work trees. The product is a
# copy of the Delivery Fixture City, committed in the city root. The city has
# no Mayor.
#
# What is real: the controller, the order that advances the convoy
# (bin/convoy-advance), the formula mol-ticket-evaluation,
# bin/ticket-evaluation, bin/project-launch (the products are launched by the
# order and outlive its pass), bin/evidence-capture, bin/convoy-state,
# bin/spec-integration (the merge control and the merges), bin/dispatch-door
# (which routes each evaluation to the agent of the Evaluator role),
# bin/escalation-door, and bin/delivery-role-sandbox: the Evaluator runs
# inside the read-only sandbox of its role. What is scripted, and spends
# nothing: the Evaluator, a stub that claims the step Gas City routes to it
# and runs the real tools the step names -- it fetches the home page of the
# launched product and says what it shows; and the author and the reviewer,
# whose finished and reviewed tickets are written through bin/convoy-state as
# their tools would (their formulas have their own trials).
#
# Two tickets of the fixture, each finished by its author:
#   A  a slice whose criterion is not realized: the evaluation records
#      « non observé » with its piece of evidence, the computed verdict is
#      unfavorable, and nothing is merged. The author commits the correction:
#      every state is « observé » with evidence, the verdict is favorable, and
#      the ticket is merged. Its Evaluator runs on the author's supplier: the
#      mention is recorded.
#   P  a prefactoring: no Evaluator session; the control records that the
#      product starts and that its probe answers, and the ticket is merged.
#
# The trial prints its record (« relevé d'essai ») on stdout.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
. "$ROOT/tests/lib/isolated-city.sh"
PORT="${TICKET_EVALUATION_TRIAL_PORT:-18411}"
CEILING=6
COUNT='data-anchor="fixture-count"'

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
TRIAL=$(mktemp -d "$HOME/.cache/af-higj9z-evaluation.XXXXXX")
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
    rm -rf -- "$TRIAL"
  fi
  exit "$status"
}
trap cleanup EXIT

# Nothing of the live Factory may reach this city (same recipe as
# tests/code-review-isolated-city-test.sh).
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$|FACTORY_ROOT$|CONVOY_|DISPATCH_DOOR_|ESCALATION_DOOR_|EVIDENCE_|TICKET_AUTHOR_|SPEC_INTEGRATION_|TEST_REVIEW_|CODE_REVIEW_(DISPATCH|FAKE)|TICKET_EVALUATION_(DISPATCH|FAKE|STATE)|DELIVERY_ROLE_)' || true)
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
# same answer says which provider, hence which supplier, each role runs on.
cat > "$TRIAL/env" <<ENV
export FACTORY_ROOT="$CITY"
export CONVOY_STATE_LOCK_DIR="$TRIAL/locks" CONVOY_ADVANCE_LOCK_DIR="$TRIAL/locks" SPEC_INTEGRATION_LOCK_DIR="$TRIAL/locks"
export SPEC_INTEGRATION_WORK_DIR="$TRIAL/merge"
export EVIDENCE_STORE_DIR="$TRIAL/store"
export TICKET_EVALUATION_STATE_DIR="$TRIAL/launches"
export ESCALATION_DOOR_LOCK_FILE="$TRIAL/escalation-door.lock" PROPOSAL_DOOR_BIN="$TRIAL/proposal-door"
export DISPATCH_DOOR_PROVIDER_FAILOVER_BIN="$TRIAL/provider-failover" DISPATCH_DOOR_ROLE_TRIAL_BIN="$TRIAL/role-adoption-trial"
export DELIVERY_ROLE_PROVIDER_FAILOVER_BIN="$TRIAL/provider-failover"
export GIT_AUTHOR_NAME=essai GIT_AUTHOR_EMAIL=essai@example.invalid GIT_COMMITTER_NAME=essai GIT_COMMITTER_EMAIL=essai@example.invalid
ENV
printf '#!/bin/sh\necho 0\n' > "$TRIAL/proposal-door"
cat > "$TRIAL/provider-failover" <<'SH'
#!/bin/sh
printf '%s\n' '{"total_exhaustion": {"active": false}, "targets": {"trial-author": {"effective": "stub-author"}, "trial-evaluator": {"effective": "stub-evaluator", "chain": [{"provider": "stub-evaluator", "state": "available", "pool": "fournisseur-essai"}]}}}'
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

# --- the scripted Evaluator ---------------------------------------------------------
# One session, one evaluation, as the step of mol-ticket-evaluation asks: the
# brief, a captured page of the launched product per criterion and for the
# demonstration line, one state each, handed to `ticket-evaluation record`.
# Its judgement is a rule on what the product serves: the criterion and the
# line are « observed » when the home page of the product launched on the
# dataset `content` shows the count anchor, « not_observed » otherwise. It
# runs inside bin/delivery-role-sandbox, as a session of the Evaluator role
# does, and writes down what it could see of the launch from there.
cat > "$TRIAL/stub-evaluator-inner" <<STUB
#!/bin/bash
. "$TRIAL/env"
BIN="$ROOT/bin"
LOG="$TRIAL/evaluator.log"
say() { echo "\$(date -u +%H:%M:%S) \${GC_SESSION_NAME:-?} \$*" >> "\$LOG"; }
while true; do
  CLAIM=\$(gc hook --claim --json 2>/dev/null)
  ACTION=\$(printf '%s' "\$CLAIM" | jq -r '.action // empty' 2>/dev/null)
  BEAD=\$(printf '%s' "\$CLAIM" | jq -r '.bead_id // empty' 2>/dev/null)
  if [ "\$ACTION" != work ] || [ -z "\$BEAD" ]; then sleep 3; continue; fi
  ROOT_BEAD=\$(gc bd show "\$BEAD" --json | jq -r '.[0].metadata["gc.root_bead_id"]')
  INPUT=\$(gc bd show "\$ROOT_BEAD" --json | jq -r '.[0].metadata["gc.input_convoy_id"]')
  EVALUATION_BEAD=\$(gc convoy status "\$INPUT" --json | jq -r '.children[0].id')
  TEXT=\$(gc bd show "\$EVALUATION_BEAD" --json | jq -r '.[0].description')
  CONVOY=\$(printf '%s\n' "\$TEXT" | sed -n 's/^convoy: //p'); TICKET=\$(printf '%s\n' "\$TEXT" | sed -n 's/^ticket: //p')
  OUTCOME=pass
  BRIEF="$TRIAL/brief.\$EVALUATION_BEAD.json"
  if ! "\$BIN/ticket-evaluation" brief "\$CONVOY" "\$TICKET" > "\$BRIEF.new" 2>>"\$LOG"; then
    # Seen in this trial (gc 1.4.1): the command of the session is started
    # once more between its drain-ack and its stop, and is handed the step
    # it just closed. Nothing is asked any more, and nothing is written.
    say "ticket \$TICKET : aucune évaluation demandée (\$EVALUATION_BEAD), rien à faire"
    rm -f "\$BRIEF.new"
    gc runtime drain-ack >/dev/null 2>&1
    exit 0
  fi
  mv "\$BRIEF.new" "\$BRIEF"
  ADDRESS=\$(jq -r '.environments[] | select(.dataset == "content") | .address' "\$BRIEF")
  LAUNCH=\$(jq -r '.environments[] | select(.dataset == "content") | .launch_state' "\$BRIEF")
  # What a session of the role can see of the clean copy the product runs from.
  WORKTREE=\$(jq -r '.worktree' "\$LAUNCH")
  if [ -e "\$WORKTREE" ]; then SEEN=visible; else SEEN=invisible; fi
  if touch "$ROOT/.sandbox-probe" 2>/dev/null; then rm -f "$ROOT/.sandbox-probe"; WRITE=writable; else WRITE=read-only; fi
  echo "\$TICKET \$EVALUATION_BEAD \${GC_SESSION_NAME:-?} \$ADDRESS copy=\$SEEN factory=\$WRITE read_only=\${DELIVERY_ROLE_READ_ONLY:-0}" >> "$TRIAL/evaluation-sessions"
  state_of() { # <piece> <text>: capture the home page, print the state as JSON
    local captured page
    captured=\$("\$BIN/evidence-capture" command "\$CONVOY" "\$TICKET" --piece "\$1" --launch-state "\$LAUNCH" -- curl -s "\$ADDRESS/" 2>>"\$LOG") || return 1
    page=\$(jq -r '.output' "\$(printf '%s' "\$captured" | jq -r '.path')")
    if printf '%s' "\$page" | grep -qF '$COUNT'; then
      jq -n --arg text "\$2" --arg piece "\$1" '{text: \$text, state: "observed", evidence: \$piece}'
    else
      jq -n --arg text "\$2" --arg piece "\$1" '{text: \$text, state: "not_observed", evidence: \$piece, reason: "la page du produit lancé ne montre pas l'"'"'ancre fixture-count"}'
    fi
  }
  RESULT="$TRIAL/result.\$EVALUATION_BEAD.json"
  CRITERIA='[]'
  while IFS= read -r criterion; do
    NUMBER=\$(printf '%s' "\$criterion" | jq -r '.number')
    STATE=\$(state_of "evaluation.c\$NUMBER" "\$(printf '%s' "\$criterion" | jq -r '.text')") || OUTCOME=fail
    CRITERIA=\$(jq -c --argjson n "\$NUMBER" --argjson s "\${STATE:-null}" '. + [{number: \$n} + \$s]' <<< "\$CRITERIA")
  done < <(jq -c '.criteria[]' "\$BRIEF")
  LINE=\$(state_of evaluation.demo "\$(jq -r '.demonstration_line' "\$BRIEF")") || OUTCOME=fail
  jq --argjson criteria "\$CRITERIA" --argjson line "\${LINE:-null}" '{commit, criteria: \$criteria, demonstration_line: \$line}' "\$BRIEF" > "\$RESULT"
  "\$BIN/ticket-evaluation" record "\$CONVOY" "\$TICKET" --file "\$RESULT" >> "\$LOG" 2>&1 || OUTCOME=fail
  say "ticket \$TICKET : états remis (\$EVALUATION_BEAD, \$OUTCOME)"
  gc bd update "\$EVALUATION_BEAD" --set-metadata gc.outcome=\$OUTCOME --status=closed --notes "évaluation \$OUTCOME" >> "\$LOG" 2>&1 || say "fermeture du bead d'évaluation refusée"
  gc bd update "\$BEAD" --set-metadata gc.outcome=\$OUTCOME --status=closed --notes "évaluation \$OUTCOME" >> "\$LOG" 2>&1 || say "fermeture de l'étape refusée"
  gc runtime drain-ack >> "\$LOG" 2>&1 || say "drain-ack refusé"
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
chmod +x "$TRIAL/stub-evaluator" "$TRIAL/stub-evaluator-inner"

# --- the city: an Evaluator agent on its stub, the real formula, the real order ----
cat > "$CITY/city.toml" <<TOML
[workspace]
provider = "stub-evaluator"

[providers.stub-author]
base = "builtin:claude"
command = "/bin/true"
ready_delay_ms = 0

[providers.stub-evaluator]
base = "builtin:claude"
command = "$TRIAL/stub-evaluator"
# A stub is a shell script: without its process name Gas City finds no
# \`claude\` process in the session and reaps it as a zombie.
process_names = ["stub-evaluator", "stub-evaluator-inner", "bwrap", "bash"]
ready_delay_ms = 0
TOML
mkdir -p "$CITY/agents/trial-evaluator" "$CITY/formulas" "$CITY/orders" "$CITY/config/projects" "$CITY/config/project-descriptors"
cat > "$CITY/agents/trial-evaluator/agent.toml" <<'TOML'
description = "Evaluator of the ticket-evaluation trial (scripted stub, spends nothing)"
scope = "city"
min_active_sessions = 0
max_active_sessions = 1
provider = "stub-evaluator"
TOML
echo "Scripted Evaluator of the ticket-evaluation trial." > "$CITY/agents/trial-evaluator/prompt.template.md"
cp "$ROOT/formulas/mol-ticket-evaluation.formula.toml" "$CITY/formulas/"
cat > "$CITY/config/projects/trial.toml" <<TOML
rig_dir = "."
repo = "example/trial"
protected_branch = "main"
required_ci = "CI"
sling_target = "trial-evaluator"
formulas = "mol-ticket-evaluation"
TOML
jq '.rigs = ["trial"] | .stacks = {"trial": ["fixture-stack"]}' "$ROOT/$FIXTURE/descriptor.json" > "$CITY/config/project-descriptors/trial.json"
jq -n --argjson n "$CEILING" '{contract: "agent-factory-delivery-flow/v1", max_sessions: $n,
  start: {formula: "mol-ticket-author", role: "author"},
  code_review: {formula: "mol-code-review", role: "reviewer", rig: "trial", timeout_seconds: 600},
  evaluation: {formula: "mol-ticket-evaluation", role: "evaluator", rig: "trial", timeout_seconds: 600, start_timeout_seconds: 30}}' \
  > "$CITY/config/delivery-flow.json"
jq '.roles.author.agent = "trial-author" | .roles.evaluator.agent = "trial-evaluator"' "$ROOT/config/delivery-roles.json" \
  > "$CITY/config/delivery-roles.json"
jq -n '{providers: {"stub-author": {recommended: ["modele-auteur"]}, "stub-evaluator": {recommended: ["modele-evaluateur"]}}}' \
  > "$CITY/config/model-catalog.json"
# Who supplies each provider of the trial: one supplier for both roles.
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
CRITERION="Point d'entrée : GET / — Observable : ancre fixture-count — Faux si : le nombre d'éléments n'y est pas"
LINE="Sur le jeu content, la page d'accueil affiche le nombre d'éléments"
A=$(gc bd create --title "ticket A, critère non réalisé puis corrigé" --type task --silent --description "## What to build

Le nombre d'éléments sur la page d'accueil.

## Acceptance criteria

- [ ] $CRITERION

## Target rigs

trial" 2>/dev/null)
P=$(gc bd create --title "ticket P, prefactoring" --type task --silent --description "## What to build

Ranger le rendu de la page.

## Target rigs

trial" 2>/dev/null)
SPEC=$(gc bd create --title "Spec d'essai" --type task --silent --description "## User Stories

1. As Benjamin, I want la page d'accueil afficher le nombre d'éléments." 2>/dev/null)
gc bd update "$SPEC" --status closed >/dev/null 2>&1 || true
CONVOY=$(gc bd create --title "convoi d'essai" --type convoy --silent 2>/dev/null)
gc bd update "$CONVOY" --set-metadata "gc.spec_id=$SPEC" >/dev/null
gc bd dep add "$CONVOY" "$A" --type tracks >/dev/null
gc bd dep add "$CONVOY" "$P" --type tracks >/dev/null
gc bd update "$A" --set-metadata gc.ticket_kind=vertical_slice >/dev/null
gc bd update "$P" --set-metadata gc.ticket_kind=prefactoring >/dev/null

echo "relevé d'essai — Ticket Evaluation sur le produit lancé, cité isolée ($(gc version 2>/dev/null | head -1), N=$CEILING, aucun Mayor, Evaluator scripté dans le bac à sable lecture seule, vraie porte de dispatch, vrai lancement du produit par l'ordre, vraie commande de fusion)"
echo "convoi $CONVOY (Spec $SPEC) : A=$A (tranche, critère non réalisé puis corrigé) P=$P (prefactoring)"

state mark "$CONVOY" --demonstration-line "$A=$LINE" --user-stories "$A=1" >/dev/null
opened=$("$ROOT/bin/spec-integration" open "$CONVOY" --repo "$PRODUCT" --protected main) \
  || fail "spec-integration open did not pass: $opened"
INTEGRATION="integration/$SPEC"

# --- the author's and the reviewer's side, written as their tools would -------------
field() { gc bd show "$1" --json | jq -r --arg k "$2" '.[0].metadata[$k] // empty'; }
worktree_of() {
  local wt="$TRIAL/wt/$1"
  if [ ! -d "$wt" ]; then
    git -C "$PRODUCT" worktree add -q -b "ticket/$1" "$wt" "$INTEGRATION" >/dev/null 2>&1 || fail "no work tree for $1"
  fi
  printf '%s' "$wt"
}
commit_on() { # <ticket> <path> <content> <message>: one commit on the branch of the ticket; prints its SHA
  local wt
  wt=$(worktree_of "$1")
  mkdir -p "$wt/$(dirname "$2")"
  printf '%s\n' "$3" > "$wt/$2"
  git -C "$wt" add -A
  git -C "$wt" commit -q -m "$4"
  git -C "$wt" rev-parse HEAD
}
realize() { # <ticket>: the product shows the number of items; prints the SHA
  local wt
  wt=$(worktree_of "$1")
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
  git -C "$wt" commit -q -m "PROSE-DU-COMMIT : le nombre est affiché"
  git -C "$wt" rev-parse HEAD
}
finish() { # <ticket> <tip> <green step>: every step of the TDD with its sealed report, the demonstration, the sealed records, the Handoff, the exit, a favorable code review
  python3 "$ROOT/tests/lib/ticket_proofs.py" finish "$CONVOY" "$1" "$2" --repo "$PRODUCT" --base "$BASE" --branch "ticket/$1" \
    --done "PROSE-DU-HANDOFF : tout est observable, à ma façon." --subject "PROSE-DU-COMMIT" >/dev/null
  state open-code-review "$CONVOY" "$1" --kind review --commit "$2" --base "$BASE" >/dev/null
  jq -n --arg commit "$2" --arg session "trial-reviewer-$1-${2:0:12}" '{commit: $commit, findings: [], answers: {}, recorded_by: $session}' > "$TRIAL/review.$1.json"
  state record-code-review "$CONVOY" "$1" --file "$TRIAL/review.$1.json" >/dev/null
}
started() { # <ticket>
  state record-gate "$CONVOY" "$1" --gate dispatch >/dev/null
  state set-branch "$CONVOY" "$1" --branch "ticket/$1" >/dev/null
  state set-session "$CONVOY" "$1" --session "trial-author-$1" >/dev/null
  state set-model "$CONVOY" "$1" --role author --agent trial-author --provider stub-author --model modele-auteur >/dev/null
}

started "$A"
red=$(commit_on "$A" "$FIXTURE/tests/test_count_$A.py" "# test de critère du ticket $A" "PROSE-DU-COMMIT : tests de critère")
TIP_A=$(commit_on "$A" "docs/$A.md" "Le nombre d'éléments sera affiché plus tard." "PROSE-DU-COMMIT : la tranche")
files=$(jq -n --arg p "$FIXTURE/tests/test_count_$A.py" --arg d "sha256:$(git -C "$PRODUCT" show "$red:$FIXTURE/tests/test_count_$A.py" | sha256sum | cut -d' ' -f1)" '{($p): $d}')
state set-tdd "$CONVOY" "$A" --step red --commit "$red" --base "$BASE" >/dev/null
jq -n --argjson files "$files" --arg id "$FIXTURE/tests/test_count_$A.py::CountTest.test_count" '{files: $files, criteria: {"1": [$id]}}' > "$TRIAL/request.$A.json"
state open-test-review "$CONVOY" "$A" --commit "$red" --file "$TRIAL/request.$A.json" >/dev/null
jq -n --argjson files "$files" --arg commit "$red" --arg session "trial-test-reviewer-$A" --arg id "$FIXTURE/tests/test_count_$A.py::CountTest.test_count" \
  '{commit: $commit, files: $files, tests: {($id): {state: "favorable"}}, recorded_by: $session}' > "$TRIAL/verdict.$A.json"
state record-test-review "$CONVOY" "$A" --file "$TRIAL/verdict.$A.json" >/dev/null
state set-tdd "$CONVOY" "$A" --step freeze --commit "$red" >/dev/null
finish "$A" "$TIP_A" green

started "$P"
TIP_P=$(commit_on "$P" "docs/$P.md" "Le rendu de la page est rangé." "PROSE-DU-COMMIT : rangement")
finish "$P" "$TIP_P" prefactoring
echo "$(date -u +%H:%M:%S) marque posée, branche $INTEGRATION ouverte, deux tickets terminés par leur auteur et relus (A $TIP_A, P $TIP_P)"

(gc supervisor run > "$TRIAL/supervisor.out" 2>&1 &)
sleep 3
gc --city "$CITY" start >/dev/null 2>&1 || true
grep -q "Controller: supervisor-managed" <<<"$(gc --city "$CITY" status 2>/dev/null)" || fail "the isolated city's controller did not start"
gc order show convoy-advance --json >/dev/null 2>&1 || fail "the city does not accept orders/convoy-advance.toml"
grep -q "^mol-ticket-evaluation\$" <<<"$(gc formula list 2>/dev/null)" || fail "the city does not resolve formulas/mol-ticket-evaluation.formula.toml"

wait_for() { # <seconds> <command...>
  local deadline=$(( $(date +%s) + $1 )); shift
  until "$@"; do
    [ "$(date +%s)" -lt "$deadline" ] || return 1
    sleep 5
  done
}
evaluation_of() { field "$1" gc.flow.evaluation; }
merged() { [ "$(field "$1" gc.flow.merge | jq -r '.outcome // empty' 2>/dev/null)" = merged ]; }
on_integration() { git -C "$PRODUCT" merge-base --is-ancestor "$1" "$INTEGRATION"; }
dump() { tail -30 "$TRIAL/evaluator.log" >&2 || true; tail -3 "$TRIAL/passes.jsonl" >&2 || true; }
piece() { cat "$TRIAL/store/$SPEC/$1/$2.json"; }
verdict() { "$ROOT/bin/ticket-evaluation" verdict "$CONVOY" "$1" --repo "$PRODUCT"; }

# --- A: the criterion is not realized -> « non observé » with evidence, unfavorable ----
a_refused() { [ "$(evaluation_of "$A" | jq -r '.rounds[0].verdict // empty' 2>/dev/null)" = unfavorable ]; }
wait_for 600 a_refused || { dump; fail "the evaluation of A did not record its states within 600s"; }
first=$(evaluation_of "$A" | jq -c '.rounds[0]')
printf '%s' "$first" | jq -e --arg tip "$TIP_A" --arg text "$CRITERION" \
  '.kind == "evaluation" and .commit == $tip and .outcome == "return_to_author" and (.criteria | length) == 1
   and .criteria[0].state == "not_observed" and .criteria[0].text == $text and .criteria[0].evidence == "evaluation.c1"
   and .demonstration_line.state == "not_observed"' >/dev/null \
  || fail "the evaluation of A did not record « not_observed » on its unrealized criterion: $first"
evidence_a=$(piece "$A" evaluation.c1)
address_a=$(printf '%s' "$evidence_a" | jq -r '.address')
printf '%s' "$evidence_a" | jq -e --arg tip "$TIP_A" '.commit == $tip and .exit_code == 0 and (.output | contains("fixture-count") | not) and (.seal | length) > 0' >/dev/null \
  || fail "the piece of evidence of A is not a capture of the product at its tip: $evidence_a"
printf '%s' "$first" | jq -e --arg address "$address_a" '[.environment[].address] | index($address) != null' >/dev/null \
  || fail "the evidence of A was not captured at an address of the products launched for its evaluation: $address_a"
evaluator_a=$(printf '%s' "$first" | jq -r '.recorded_by')
session_a=$(grep "^$A " "$TRIAL/evaluation-sessions" | head -1)
[ "$evaluator_a" != "trial-author-$A" ] && [ "$evaluator_a" = "$(printf '%s' "$session_a" | cut -d' ' -f3)" ] \
  || fail "the evaluation of A was not recorded by an Evaluator session distinct from its author: $evaluator_a"
case "$session_a" in *"copy=invisible factory=read-only read_only=1") ;; *) fail "the Evaluator of A did not run in the read-only sandbox, or saw the clean copy: $session_a";; esac
printf '%s' "$first" | jq -e '.roles.same_provider == true and .roles.author.supplier == "fournisseur-essai" and .roles.evaluator.provider == "stub-evaluator"' >/dev/null \
  || fail "the evaluation of A does not carry the providers of its roles: $(printf '%s' "$first" | jq -c .roles)"
mention=$("$ROOT/bin/ticket-evaluation" show "$CONVOY" "$A" --repo "$PRODUCT" | jq -r '.independence')
[ "$mention" = "même fournisseur que l'auteur (fournisseur-essai)" ] || fail "the mention of the same supplier is not recorded on A: $mention"
[ "$(field "$A" gc.flow.models | jq -r '.evaluator.agent + " " + .evaluator.provider')" = "trial-evaluator stub-evaluator" ] \
  || fail "the provider of the Evaluator role is not recorded on A: $(field "$A" gc.flow.models)"
grep -q "PROSE-DU-" "$TRIAL"/brief.*.json && fail "a brief handed to the Evaluator holds prose of the author"
brief_a=$(ls "$TRIAL"/brief.*.json | head -1)
jq -e '(has("diff") or has("handoff") or has("repo") or has("records")) | not' "$brief_a" >/dev/null || fail "the brief of A holds the diff, the Handoff or the repository"
grep -qF "$TRIAL/wt/" "$brief_a" && fail "the brief of A names the work tree of the author"
verdict "$A" | jq -e '.favorable == false and .verdict == "unfavorable" and (.consequence | contains("retour à l'"'"'auteur"))' >/dev/null \
  || fail "the computed verdict of A is not unfavorable: $(verdict "$A")"
sleep 75   # at least two more passes of the order
merged "$A" && fail "A was merged although a criterion was not observed"
on_integration "$TIP_A" && fail "the tip of A reached the integration branch"
[ -z "$(find "$TRIAL/launches" -name '*.json' 2>/dev/null)" ] || fail "a pass left a launched product of A running: $(find "$TRIAL/launches" -name '*.json')"
curl -s -m 2 "$address_a/health" >/dev/null 2>&1 && fail "the product launched for A still answers at $address_a"
waiting=$(tail -1 "$TRIAL/passes.jsonl" | jq -r --arg a "$A" '[.convoys[].integration.waiting[]? | select(.id == $a) | .reason] | .[0] // empty')
echo "$(date -u +%H:%M:%S) A : évaluée par la session $evaluator_a (auteur trial-author-$A), dans le bac à sable (${session_a#* * * * }) ; produit lancé par l'ordre depuis une copie propre du commit $TIP_A à $address_a ; critère 1 « non observé », preuve evaluation.c1 (commit et adresse scellés) ; verdict calculé défavorable, retour à l'auteur ; mention « $mention » ; produits arrêtés par la passe suivante ; fusion refusée : ${waiting:-ticket absent de la fusion}"

# --- P: a prefactoring -> no Evaluator session, the product starts, merged ------------
wait_for 600 merged "$P" || { dump; fail "P was not merged within 600s"; }
startup=$(evaluation_of "$P" | jq -c '.rounds[0]')
printf '%s' "$startup" | jq -e --arg tip "$TIP_P" '.kind == "startup" and .started == true and .commit == $tip and .verdict == "favorable" and .evidence == "evaluation.startup"' >/dev/null \
  || fail "the control of P did not record that its product starts: $startup"
piece "$P" evaluation.startup | jq -e --arg tip "$TIP_P" '.commit == $tip and .exit_code == 0 and (.output | contains("\"status\": \"ok\"")) and (.command | last | tostring) == "200"' >/dev/null \
  || fail "the piece of P is not the answer of the probe of its product: $(piece "$P" evaluation.startup)"
grep -q "^$P " "$TRIAL/evaluation-sessions" && fail "an Evaluator session was started for the prefactoring P"
on_integration "$TIP_P" || fail "the tip of P is not on the integration branch"
echo "$(date -u +%H:%M:%S) P : prefactoring, aucune session d'Evaluator ; le contrôle a lancé le produit au commit $TIP_P, la sonde a répondu (preuve evaluation.startup à $(piece "$P" evaluation.startup | jq -r '.address')) ; verdict favorable ; ticket fusionné dans $INTEGRATION"

# --- A again: corrected -> every state « observé », favorable, merged -------------------
FIX_A=$(realize "$A")
finish "$A" "$FIX_A" green
wait_for 600 merged "$A" || { dump; fail "A was not merged within 600s once its criterion was realized"; }
second=$(evaluation_of "$A" | jq -c '.rounds[1]')
printf '%s' "$second" | jq -e --arg tip "$FIX_A" \
  '.kind == "evaluation" and .commit == $tip and .outcome == "favorable" and .verdict == "favorable"
   and ([.criteria[].state] | all(. == "observed")) and .demonstration_line.state == "observed"' >/dev/null \
  || fail "the corrected A was not evaluated favorably at its new tip: $second"
for name in evaluation.c1 evaluation.demo; do
  piece "$A" "$name" | jq -e --arg tip "$FIX_A" '.commit == $tip and (.output | contains("fixture-count"))' >/dev/null \
    || fail "the piece $name of the corrected A does not show the count at its tip"
done
[ "$(printf '%s' "$second" | jq -r '.recorded_by')" != "$evaluator_a" ] || fail "the second evaluation of A was made by the session of the first"
[ "$(grep -c "^$A " "$TRIAL/evaluation-sessions")" = 2 ] || fail "A was not evaluated by exactly two Evaluator sessions"
on_integration "$FIX_A" || fail "the corrected tip of A is not on the integration branch"
no_product_left() { [ -z "$(find "$TRIAL/launches" -name '*.json' 2>/dev/null)" ]; }
wait_for 120 no_product_left || fail "a launched product of A was never stopped: $(find "$TRIAL/launches" -name '*.json')"
[ "$(evaluation_of "$A" | jq -r 'has("live")')" = false ] || fail "A still names a launched product to stop"
echo "$(date -u +%H:%M:%S) A : corrigée au commit $FIX_A ; nouvelle session ($(printf '%s' "$second" | jq -r '.recorded_by')) sur un nouveau produit lancé à $(piece "$A" evaluation.c1 | jq -r '.address') ; tous les états « observé » avec preuve ; verdict calculé favorable ; ticket fusionné ; produits arrêtés"

gc session list --state all --json | jq -e '[.sessions[] | select(.template | test("mayor"))] | length == 0' >/dev/null \
  || fail "a Mayor session exists in the trial city"
echo "PASS: each finished ticket was evaluated on a product launched by code from a clean copy of its branch, and code computed the verdict"
