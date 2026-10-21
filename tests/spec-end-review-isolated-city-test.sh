#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime, an isolated Dolt server and its own supervisor
#
# Adoption trial of the end code review of a Spec on its assembled diff (T25,
# af-ji2ruy; Spec af-wf4w5r §6 « Fin de Spec », §9 point 4) in a disposable
# city that shares nothing with the live Factory: its own GC_HOME, runtime
# directory, supervisor port, controller, evidence store and work trees. The
# product is a copy of the Delivery Fixture City, committed in the city root.
# The city has no Mayor.
#
# What is real: the controller, the order that advances the convoy
# (bin/convoy-advance), the end-of-Spec gate it runs (bin/spec-end: registry,
# takeover of the protected branch, regression command of the profile,
# fidelity), bin/spec-end-review, the formula mol-end-review, bin/convoy-state,
# bin/dispatch-door (which routes the review to the agent of the reviewer
# role, and starts the repair), the publication door that published the
# graph and the patch door that adds the repair (bin/ticket-graph-publish),
# on the real tracker, and bin/outcome-evaluation, which launches the
# assembled product from a clean copy of the commit of the gate. What is
# scripted, and spends nothing: the reviewer, a stub that claims the step Gas
# City routes to it and runs the real tools the step names; the Evaluator of
# the end, the stand-in of its own suite
# (tests/fixtures/outcome-evaluation/evaluator), called in place of the
# dispatch door, which observes each user story on the launched product and
# hands its states to the real `outcome-evaluation record`; and the authors, whose two tickets are written as merged and
# closed the way bin/spec-integration and bin/ticket-end leave them (their
# own trials: tests/ticket-end-isolated-city-test.sh).
#
# Two tickets of one Spec, each correct alone, contradict each other on a
# line of the Spec once assembled:
#   1  the pass that renders the three mechanical verdicts of the end
#      launches the end review and the Outcome Evaluation, both on their
#      commit; the preparation record of the review names the whole diff of
#      the integration branch against the protected branch;
#   2  the reviewer hands in a Blocking Finding that cites the line, with
#      the repair it drafted; the gate refuses and names the finding; the
#      next pass publishes that repair through the patch door and starts it
#      like any ticket;
#   3  the repair delivered, the tip moves: the gate replays its verdicts,
#      and the review is made again in full on the new tip by another
#      session, the product evaluated again; favorable there, the gate
#      passes its six conditions.
#
# The trial prints its record (« relevé d'essai ») on stdout.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
. "$ROOT/tests/lib/isolated-city.sh"
PORT="${SPEC_END_REVIEW_TRIAL_PORT:-18451}"
CEILING=4
PROJECT="delivery-fixture-city"
RIG="fixture_city"
STORY_ONE="As an exploitant, I want une sonde de santé qui répond avec chaque jeu de données, so that je sache que le produit tourne."
STORY_TWO="As an exploitant, I want la sonde de santé nommer le jeu de données servi, so that je sache ce qui est servi."
CONTRADICTION="La sonde ne répond plus quand elle nomme le jeu de données vide."
RESTORED="La sonde répond de nouveau avec chaque jeu de données, nommé ou non."

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc bd jq git dolt tmux curl python3 sha256sum; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

TRIAL=$(mktemp -d /tmp/af-ji2ruy-end-review.XXXXXX)
CITY="$TRIAL/c"
PRODUCT="$CITY"
FIXTURE="tests/fixtures/delivery-fixture-city"
cleanup() {
  status=$?
  trap - EXIT
  isolated_city_stop "$TRIAL" "$CITY" >/dev/null 2>&1 || true
  tmux -L "$(basename "$TRIAL")" kill-server >/dev/null 2>&1 || true
  # The products the Outcome Evaluation launched run from clean copies
  # outside the trial directory: stopped from their launch records.
  while IFS= read -r launched; do
    "$ROOT/bin/project-launch" stop --state-file "$launched" >/dev/null 2>&1 || true
  done < <(find "$TRIAL/products" -name '*.json' 2>/dev/null)
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
    isolated_city_remove "$TRIAL"
  fi
  exit "$status"
}
trap cleanup EXIT

# Nothing of the live Factory may reach this city (same recipe as
# tests/code-review-isolated-city-test.sh).
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$|FACTORY_ROOT$|CONVOY_|DISPATCH_DOOR_|ESCALATION_DOOR_|EVIDENCE_|TICKET_GRAPH_|GRAPH_REVIEW_|SPEC_INTEGRATION_|SPEC_END_|TICKET_END_|OUTCOME_EVALUATION_|DELIVERY_ROLE_)' || true)
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
# doors of the graph reach the tracker of the city, and wake no Mayor.
cat > "$TRIAL/env" <<ENV
export FACTORY_ROOT="$CITY"
export CONVOY_STATE_LOCK_DIR="$TRIAL/locks" CONVOY_ADVANCE_LOCK_DIR="$TRIAL/locks" SPEC_INTEGRATION_LOCK_DIR="$TRIAL/locks"
export SPEC_END_LOCK_DIR="$TRIAL/locks" SPEC_END_WORK_DIR="$TRIAL/gate" SPEC_INTEGRATION_WORK_DIR="$TRIAL/merge"
export EVIDENCE_STORE_DIR="$TRIAL/store"
export EVIDENCE_PACK_DIR="$TRIAL/packs"
export ESCALATION_DOOR_LOCK_FILE="$TRIAL/escalation-door.lock" PROPOSAL_DOOR_BIN="$TRIAL/proposal-door"
export DISPATCH_DOOR_PROVIDER_FAILOVER_BIN="$TRIAL/provider-failover" DISPATCH_DOOR_ROLE_TRIAL_BIN="$TRIAL/role-adoption-trial"
export DELIVERY_ROLE_PROVIDER_FAILOVER_BIN="$TRIAL/provider-failover"
export TICKET_GRAPH_BD_WORKSPACE="$CITY" TICKET_GRAPH_PUBLISH_SKIP_MAYOR_NOTIFY=1
export GC_BIN=gc OUTCOME_EVALUATION_DISPATCH_DOOR_BIN="$ROOT/tests/fixtures/outcome-evaluation/evaluator"
export OUTCOME_EVALUATION_STATE_DIR="$TRIAL/products" OUTCOME_EVALUATION_FAKE_LOG="$TRIAL/evaluator.log"
export OUTCOME_EVALUATION_FAKE_PLAN="$TRIAL/evaluator-plan.json" OUTCOME_EVALUATION_FAKE_BRIEFS="$TRIAL/evaluator-briefs"
export GIT_AUTHOR_NAME=essai GIT_AUTHOR_EMAIL=essai@example.invalid GIT_COMMITTER_NAME=essai GIT_COMMITTER_EMAIL=essai@example.invalid
ENV
printf '#!/bin/sh\necho 0\n' > "$TRIAL/proposal-door"
# The Evaluator of the end observes each user story on the launched product.
echo '[{}]' > "$TRIAL/evaluator-plan.json"
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
# One session, one review, as the step of mol-end-review asks: the brief, then
# an end review handed to `spec-end-review record`. Its judgement is a rule
# read from the diff the brief names: an assembled diff that says the probe
# no longer answers, and nowhere that it answers again, contradicts the first
# user story, which it cites, with the repair it drafts. It says it covered
# the two axes and every file of the diff.
cat > "$TRIAL/stub-reviewer" <<STUB
#!/bin/bash
. "$TRIAL/env"
export DELIVERY_ROLE_READ_ONLY=1
# As Claude Code does: each process start is a conversation of its own, even
# a relaunch in the warm tmux box under the same generation (af-bb69uq).
export CLAUDE_CODE_SESSION_ID=\$(cat /proc/sys/kernel/random/uuid)
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
  CONVOY=\$(gc bd show "\$REVIEW_BEAD" --json | jq -r '.[0].description' | sed -n 's/^convoy: //p')
  OUTCOME=pass
  # The brief is kept under the commit it is given for: with these stubs
  # (gc 1.4.1) the session of a later launch may be started on the step of
  # an earlier one, already closed, and reads the review bead of that one.
  NEW="$TRIAL/brief.\$\$.new"
  if ! "\$BIN/spec-end-review" brief "\$CONVOY" > "\$NEW" 2>>"\$LOG"; then
    # Seen with these stubs (gc 1.4.1; gc 1.5.0 wakes the drained session again
    # under the same name): a session is started again on the step it just closed. Nothing is asked
    # any more: the brief it was given stays, nothing is written.
    say "aucune revue de fin demandée (\$REVIEW_BEAD), rien à faire"
    rm -f "\$NEW"
    gc runtime drain-ack >/dev/null 2>&1
    exit 0
  fi
  BRIEF="$TRIAL/brief.\$(jq -r '.commit' "\$NEW").json"
  mv "\$NEW" "\$BRIEF"
  echo "\$REVIEW_BEAD \${GC_SESSION_NAME:-?} \$(jq -r '.commit' "\$BRIEF")" >> "$TRIAL/review-sessions"
  RESULT="$TRIAL/result.\$(jq -r '.commit' "\$BRIEF").json"
  DIFF=\$(sh -c "\$(jq -r '.diff.command' "\$BRIEF")")
  FINDINGS='[]'
  if printf '%s' "\$DIFF" | grep -q "ne répond plus" && ! printf '%s' "\$DIFF" | grep -q "répond de nouveau"; then
    FINDINGS=\$(jq -c --arg line "$STORY_ONE" '[{
      axis: "spec", blocking: true,
      summary: "Les deux tickets, assemblés, se contredisent : la sonde ne répond plus dès qu'"'"'elle nomme le jeu de données vide.",
      citation: {source: "spec", quote: \$line},
      repair: {
        title: "La sonde de santé répond avec chaque jeu de données, nommé ou non",
        what_it_delivers: "La sonde de santé du produit répond avec chaque jeu de données, qu'"'"'elle le nomme ou non.",
        restores: {kind: "spec_line", ref: \$line},
        demonstration_line: "Sur le produit lancé, GET /health répond 200 avec chaque jeu de données.",
        acceptance_criteria: [{entry_point: "GET /health sur le produit lancé avec le jeu de données « vide »",
                               observable: "la réponse a le statut 200", false_if: "la réponse a un autre statut"}]}}]' "\$BRIEF")
  fi
  jq --argjson findings "\$FINDINGS" '{commit, findings: \$findings, coverage: {axes: .axes, files: [.diff.files[].path]}}' "\$BRIEF" > "\$RESULT"
  "\$BIN/spec-end-review" record "\$CONVOY" --file "\$RESULT" >> "\$LOG" 2>&1 || OUTCOME=fail
  say "revue de fin remise au commit \$(jq -r '.commit' "\$BRIEF") (\$REVIEW_BEAD, \$OUTCOME)"
  gc bd update "\$REVIEW_BEAD" --set-metadata gc.outcome=\$OUTCOME --status=closed --notes "revue de fin \$OUTCOME" >/dev/null 2>&1
  gc bd update "\$BEAD" --set-metadata gc.outcome=\$OUTCOME --status=closed --notes "revue de fin \$OUTCOME" >/dev/null 2>&1
  gc runtime drain-ack >/dev/null 2>&1
  exit 0
done
STUB
cat > "$TRIAL/stub-author" <<'STUB'
#!/bin/sh
echo "stub author of the end-review trial: idle"
exec sleep 3600
STUB
chmod +x "$TRIAL/stub-reviewer" "$TRIAL/stub-author"

# --- the city: a reviewer agent on its stub, the real formula, the real order ----
cat > "$CITY/city.toml" <<TOML
[workspace]
provider = "stub-author"

[providers.stub-author]
base = "builtin:claude"
command = "$TRIAL/stub-author"
ready_delay_ms = 0

[providers.stub-reviewer]
base = "builtin:claude"
command = "$TRIAL/stub-reviewer"
# A stub is a shell script: without its process name Gas City finds no
# \`claude\` process in the session and reaps it as a zombie.
process_names = ["stub-reviewer", "bash"]
ready_delay_ms = 0
TOML
mkdir -p "$CITY/agents/trial-reviewer" "$CITY/agents/trial-author" "$CITY/formulas" "$CITY/orders" \
  "$CITY/config/projects" "$CITY/config/project-descriptors"
cat > "$CITY/agents/trial-reviewer/agent.toml" <<'TOML'
description = "Reviewer of the end-review trial (scripted stub, spends nothing)"
scope = "city"
min_active_sessions = 0
max_active_sessions = 1
provider = "stub-reviewer"
wake_mode = "fresh"
TOML
echo "Scripted reviewer of the end-review trial." > "$CITY/agents/trial-reviewer/prompt.template.md"
cat > "$CITY/agents/trial-author/agent.toml" <<'TOML'
description = "Author of the end-review trial (idle stub, spends nothing)"
scope = "city"
min_active_sessions = 0
max_active_sessions = 2
provider = "stub-author"
TOML
echo "Idle author of the end-review trial." > "$CITY/agents/trial-author/prompt.template.md"
cp "$ROOT/formulas/mol-end-review.formula.toml" "$CITY/formulas/"
cat > "$CITY/formulas/trial-start.formula.toml" <<'TOML'
description = "Start formula of the end-review trial: one step."
formula = "trial-start"

[requires]
formula_compiler = ">=2.0.0"

[[steps]]
id = "work"
title = "Work the ticket"
description = "Trial step."
TOML
# The project of the Spec declares its human approver (the patch door reads
# it); the rig its tickets target is what the dispatch door reads.
for name in "$PROJECT" "$RIG"; do
  cat > "$CITY/config/projects/$name.toml" <<TOML
human_approver = "benjamin"
rig_dir = "."
repo = "example/trial"
protected_branch = "main"
required_ci = "CI"
sling_target = "trial-author"
formulas = "trial-start,mol-end-review"
TOML
done
jq --arg rig "$RIG" '.rigs = [$rig] | .stacks = {($rig): ["fixture-stack"]}' "$ROOT/$FIXTURE/descriptor.json" > "$CITY/config/project-descriptors/$PROJECT.json"
jq -n --argjson n "$CEILING" --arg rig "$RIG" '{contract: "agent-factory-delivery-flow/v1", max_sessions: $n,
  start: {formula: "trial-start", role: null},
  outcome_evaluation: {formula: "mol-outcome-evaluation", role: "evaluator", rig: $rig, timeout_seconds: 600, start_timeout_seconds: 30},
  end_review: {formula: "mol-end-review", role: "reviewer", rig: $rig, timeout_seconds: 600}}' \
  > "$CITY/config/delivery-flow.json"
jq '.roles.author.agent = "trial-author" | .roles.reviewer.agent = "trial-reviewer"' "$ROOT/config/delivery-roles.json" \
  > "$CITY/config/delivery-roles.json"
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
digest_of() {
  printf 'sha256:%s' "$(printf '%s' "$1" | sha256sum | cut -d' ' -f1)"
}
field() { gc bd show "$1" --json | jq -r --arg k "$2" '.[0].metadata[$k] // empty'; }

# --- the Spec and its graph, published by the real publication door ----------------
SPEC=$(gc bd create --title "Spec d'essai de la revue de fin" --type task --silent --description "Spec d'essai de la revue de fin (T25). Données de test seulement.

## User Stories

1. $STORY_ONE
2. $STORY_TWO

## Testing Decisions

Seams : GET / et GET /health." 2>/dev/null)
gc bd update "$SPEC" --set-metadata "spec_state=APPROVED_SPEC" \
  --set-metadata "approved_digest=$(digest_of "$(gc bd show "$SPEC" --json | jq -r '.[0].description')")" \
  --set-metadata "gc.project_id=$PROJECT" >/dev/null
DRAFT=$(gc bd create --title "Brouillon d'essai" --type task --silent --description "flow_contract: new-flow/v1
operator_needs: []
tickets:
- id: T1
  kind: vertical_slice
  title: La sonde de santé répond
  blocked_by: []
  target_rigs: [$RIG]
  what_it_delivers: Le produit répond à une sonde de santé, avec chaque jeu de données.
  demonstration_line: Sur le produit lancé, GET /health répond 200 avec le statut « ok ».
  user_stories: [1]
  acceptance_criteria:
  - entry_point: \"GET /health sur le produit lancé avec le jeu de données « contenu »\"
    observable: \"la réponse a le statut 200\"
    false_if: \"la réponse a un autre statut\"
- id: T2
  kind: vertical_slice
  title: La sonde de santé nomme le jeu de données
  blocked_by: []
  target_rigs: [$RIG]
  what_it_delivers: La sonde de santé du produit nomme le jeu de données servi.
  demonstration_line: Sur le produit lancé, GET /health nomme le jeu de données servi.
  user_stories: [2]
  acceptance_criteria:
  - entry_point: \"GET /health sur le produit lancé avec le jeu de données « contenu »\"
    observable: \"la réponse nomme le jeu de données « contenu »\"
    false_if: \"la réponse ne nomme aucun jeu de données\"" 2>/dev/null)
gc bd update "$DRAFT" --set-metadata "spec_id=$SPEC" --set-metadata "approved_by=benjamin" \
  --set-metadata "approved_evidence=« j'approuve le graphe » (essai)" \
  --set-metadata "approved_digest=$(digest_of "$(gc bd show "$DRAFT" --json | jq -r '.[0].description')")" \
  --set-metadata "display_title=Fixture City : essai de la revue de fin" --set-metadata "language=fr" >/dev/null
# A draft of the new flow is published only with a graph review that holds
# for its digest (T08): this one answers every question of the brief
# favorably, as a reviewer session would
# (tests/ticket-graph-publish-new-flow-real-tracker-test.sh).
mkdir -p "$TRIAL/factory/config"
echo '{"roles": {"reviewer": {"agent": "delivery-reviewer"}}}' > "$TRIAL/factory/config/delivery-roles.json"
printf '[providers.reviewer-profile]\nargs_append = ["--model", "modele-relecteur"]\n' > "$TRIAL/factory/city.toml"
review() {
  FACTORY_ROOT="$TRIAL/factory" GRAPH_REVIEW_BD_WORKSPACE="$CITY" DELIVERY_ROLE_READ_ONLY=1 \
    GRAPH_REVIEW_PROVIDER_FAILOVER_BIN="$ROOT/tests/fixtures/graph-review/provider-failover" "$ROOT/bin/graph-review" "$@"
}
review request "$DRAFT" --author-model modele-auteur >/dev/null || fail "graph review request refused for $DRAFT"
review brief "$DRAFT" | jq '
  def answers($checks): {checks: ($checks | with_entries(.value = (
    if .key == "prototype_fold_present_and_first" then {state: "not_applicable", reason: "aucun ticket d'"'"'interface"}
    else {state: "favorable"} end)))};
  {digest, tickets: (.tickets | map({key: .id, value: answers(.checks)}) | from_entries), graph: answers(.graph_checks)}
' > "$TRIAL/graph-verdict.json"
review record "$DRAFT" --verdict-file "$TRIAL/graph-verdict.json" >/dev/null || fail "graph review verdict refused for $DRAFT"
published=$("$ROOT/bin/ticket-graph-publish" bd-publish "$DRAFT" --project "$PROJECT" --repo-root "$CITY") \
  || fail "the publication door refused the graph of the trial: $published"
CONVOY=$(jq -r '.ids._convoy' <<<"$published")
A=$(jq -r '.ids.T1' <<<"$published"); B=$(jq -r '.ids.T2' <<<"$published")
INTEGRATION=$(jq -r '.integration.branch' <<<"$published")
[ -n "$CONVOY" ] && [ -n "$A" ] && [ -n "$B" ] && [ "$INTEGRATION" != null ] || fail "unexpected publication result: $published"

echo "relevé d'essai — revue de code de fin sur le diff assemblé, cité isolée ($(gc version 2>/dev/null | head -1), N=$CEILING, aucun Mayor, relecteur scripté, vraie porte de fin de Spec, vraies portes de dispatch, de publication et de patch)"
echo "convoi $CONVOY (Spec $SPEC), publié par la porte de publication : T1=$A T2=$B ; branche $INTEGRATION"

# --- the authors' side, written as their tools leave it: merged, closed by the gate ---
commit_on_integration() { # <path> <content> <message>: one commit at the tip of the integration branch; prints its SHA
  local wt="$TRIAL/wt/integration" sha
  git -C "$PRODUCT" worktree add -q --detach "$wt" "$INTEGRATION" >/dev/null 2>&1 || fail "no work tree for $INTEGRATION"
  mkdir -p "$wt/$(dirname "$1")"
  printf '%s\n' "$2" > "$wt/$1"
  git -C "$wt" add -A
  git -C "$wt" commit -q -m "$3"
  sha=$(git -C "$wt" rev-parse HEAD)
  git -C "$PRODUCT" update-ref "refs/heads/$INTEGRATION" "$sha"
  git -C "$PRODUCT" worktree remove --force "$wt"
  printf '%s' "$sha"
}
delivered() { # <ticket> <path> <content>: its work on the integration branch, the ticket closed by the ticket-end gate
  local sha
  [ -n "$(field "$1" gc.flow.gate.dispatch)" ] || state record-gate "$CONVOY" "$1" --gate dispatch >/dev/null
  state set-model "$CONVOY" "$1" --role author --agent trial-author --provider stub-author --model modele-auteur >/dev/null
  sha=$(commit_on_integration "$2" "$3" "PROSE-DU-COMMIT : travail du ticket $1")
  state close-ticket "$CONVOY" "$1" --commit "$sha" --file "$ROOT/tests/fixtures/convoy-state/ticket-end-report.json" >/dev/null
  printf '%s' "$sha"
}
delivered "$A" "docs/sonde-repond.md" "La sonde de santé répond 200." >/dev/null
TIP1=$(delivered "$B" "docs/sonde-nomme.md" "La sonde de santé nomme le jeu de données. $CONTRADICTION")
echo "$(date -u +%H:%M:%S) deux tickets livrés et fermés par leur porte ; pointe de $INTEGRATION : $TIP1 ; branche protégée main : $BASE"

# The conversation of a session (af-bb69uq) is Claude Code's
# CLAUDE_CODE_SESSION_ID: the runner's own must not reach the trial sessions.
isolated_city_disable_dog "$TRIAL" "$CITY"
(env -u CLAUDE_CODE_SESSION_ID gc supervisor run > "$TRIAL/supervisor.out" 2>&1 &)
sleep 3
gc --city "$CITY" start >/dev/null 2>&1 || true
grep -q "Controller: supervisor-managed" <<<"$(gc --city "$CITY" status 2>/dev/null)" || fail "the isolated city's controller did not start"
gc order show convoy-advance --json >/dev/null 2>&1 || fail "the city does not accept orders/convoy-advance.toml"
grep -q "^mol-end-review\$" <<<"$(gc formula list 2>/dev/null)" || fail "the city does not resolve formulas/mol-end-review.formula.toml"

wait_for() { # <seconds> <command...>
  local deadline=$(( $(date +%s) + $1 )); shift
  until "$@"; do
    [ "$(date +%s)" -lt "$deadline" ] || return 1
    sleep 5
  done
}
end_review() { field "$CONVOY" gc.flow.end_review; }
gate_record() { field "$CONVOY" gc.flow.spec_end; }
dump() { tail -30 "$TRIAL/reviewer.log" >&2 || true; tail -3 "$TRIAL/passes.jsonl" >&2 || true; }
check_gate() { "$ROOT/bin/spec-end" check "$CONVOY" --repo "$PRODUCT"; }
launch_pass() { # <commit>: the pass that launched the end review of that commit
  jq -c --arg c "$CONVOY" --arg commit "$1" 'select(any(.convoys[]; .id == $c and .end_review.action == "launched" and .end_review.commit == $commit))
    | .at as $at | .convoys[] | select(.id == $c) | {at: $at, spec_end, outcome_evaluation, end_review}' "$TRIAL/passes.jsonl" | head -1
}

# --- 1: launched by the pass that renders the verdicts, with the Outcome Evaluation, on their commit, on the whole diff ---
outcome() { field "$CONVOY" gc.flow.outcome_evaluation; }
first_round() { [ "$(end_review | jq -r '.rounds | length' 2>/dev/null)" = 1 ]; }
wait_for 600 first_round || { dump; fail "no end review was recorded within 600s"; }
GATE1=$(gate_record | jq -r '.commit')
[ "$(gate_record | jq -r '.version + " " + ([.conditions[].verdict] | join(","))')" = "spec-end/v4 pass,pass,pass" ] \
  || fail "the three mechanical verdicts were not rendered by the gate: $(gate_record)"
git -C "$PRODUCT" merge-base --is-ancestor "$TIP1" "$GATE1" && git -C "$PRODUCT" merge-base --is-ancestor "$BASE" "$GATE1" \
  || fail "the commit of the gate ($GATE1) does not hold the work of the tickets and the protected branch"
pass1=$(launch_pass "$GATE1")
[ -n "$pass1" ] || { dump; fail "no pass launched the end review of the commit of the gate ($GATE1)"; }
jq -e --arg commit "$GATE1" '.spec_end.commit == $commit and .spec_end.replayed == true
  and .spec_end.verdicts == {registry: "pass", tests: "pass", fidelity: "pass", outcome_evaluation: "fail", findings: "not_run", end_review: "fail", evidence_pack: "not_run"}
  and .end_review.commit == $commit and .end_review.launches == 1' <<<"$pass1" >/dev/null \
  || fail "the end review was not launched by the pass that rendered the three verdicts, on their commit: $pass1"
jq -e --arg commit "$GATE1" '.outcome_evaluation.action == "launched" and .outcome_evaluation.commit == $commit' <<<"$pass1" >/dev/null \
  || fail "the Outcome Evaluation was not launched by the pass that launched the end review, on the same commit: $pass1"
outcome_round1() { [ "$(outcome | jq -r --arg commit "$GATE1" '[.rounds[] | select(.commit == $commit)] | length' 2>/dev/null)" = 1 ]; }
wait_for 600 outcome_round1 || { dump; fail "the Outcome Evaluation did not record a round on $GATE1 within 600s"; }
evaluated1=$(outcome | jq -c --arg commit "$GATE1" '[.rounds[] | select(.commit == $commit)][0]')
jq -e '.outcome == "favorable" and ([.stories[].state] == ["observed", "observed"])' <<<"$evaluated1" >/dev/null \
  || fail "the Outcome Evaluation of the commit of the gate did not observe the two user stories: $(outcome)"
round1=$(end_review | jq -c '.rounds[0]')
bead1=$(jq -r '.end_review.bead' <<<"$pass1")
brief1="$TRIAL/brief.$GATE1.json"
[ -f "$brief1" ] || fail "the reviewer was given no brief for the commit of the gate $GATE1"
grep -q "^$bead1 " "$TRIAL/review-sessions" || fail "no reviewer session read the review bead $bead1 the pass launched"
expected_files=$(git -C "$PRODUCT" diff --name-only "$BASE" "$GATE1" | sort | tr '\n' ' ')
[ "$(jq -r '[.diff.files[].path] | sort | join(" ")' "$brief1") " = "$expected_files" ] \
  || fail "the preparation record does not name the whole diff $BASE..$GATE1: $(jq -c '.diff.files' "$brief1")"
jq -e --arg base "$BASE" --arg commit "$GATE1" --arg branch "$INTEGRATION" \
  '.base == $base and .commit == $commit and .branch == $branch and .protected == "main" and .diff.fixed_point == $base
   and .diff.extent.files == (.diff.files | length) and (.diff.extent.files >= 2) and (.tickets | length) == 2' "$brief1" >/dev/null \
  || fail "the preparation record is not the one of the whole diff against the protected branch: $(jq -c '{base, commit, branch, protected, extent: .diff.extent}' "$brief1")"
grep -q "PROSE-DU-" "$brief1" && fail "the brief handed to the end reviewer holds prose of an author"
echo "$(date -u +%H:%M:%S) 1 : la passe de $(jq -r '.at' <<<"$pass1") rend les trois verdicts mécaniques sur $GATE1 et lance sur ce même commit la revue de fin (bead $bead1) et l'Outcome Evaluation (bead $(jq -r '.outcome_evaluation.bead' <<<"$pass1"), $(jq -r '.stories | length' <<<"$evaluated1") user stories observées avec preuve) ; relevé de préparation : $(jq -r '.diff.scope' "$brief1") — $(jq -c '.diff.extent | del(.digest)' "$brief1")"

# --- 2: a cited Blocking Finding, its drafted repair through the patch door, started like any ticket ---
jq -e --arg line "$STORY_ONE" --arg commit "$GATE1" --arg base "$BASE" \
  '.commit == $commit and .base == $base and .outcome == "unfavorable" and (.findings | length) == 1
   and .findings[0].blocking == true and .findings[0].citation == {source: "spec", quote: $line}
   and .findings[0].repair_draft.restores == {kind: "spec_line", ref: $line}
   and .coverage.missing == [] and (.duration_seconds | type) == "number"
   and .models == {authors: ["modele-auteur"], reviewer: "modele-relecteur", same_model: false}' <<<"$round1" >/dev/null \
  || fail "the end review did not record one cited Blocking Finding with its drafted repair: $round1"
reviewer1=$(jq -r '.recorded_by' <<<"$round1")
[ "$reviewer1" = "$(sed -n "s/^[^ ]* \\([^ ]*\\) $GATE1\$/\\1/p" "$TRIAL/review-sessions" | head -1)" ] \
  || fail "the end review was not recorded by the reviewer session Gas City routed it to: $reviewer1"
[ "$(field "$CONVOY" gc.flow.counter.end_rounds)" = 1 ] || fail "the unfavorable end review did not count one round of the end"
set +e
refusal=$(check_gate); rc=$?
set -e
[ "$rc" = 1 ] || fail "the gate did not refuse with a Blocking Finding of the end review: $refusal"
# Condition 7 (the Evidence Pack, spec-end/v4) is not launched while one before it is missing.
jq -e '.missing == [6, 7] and .conditions[6].verdict == "not_run" and (.error | test("F1.1")) and (.error | test("sans verdict favorable"))' <<<"$refusal" >/dev/null \
  || fail "the refusal of the gate does not name the Blocking Finding, on condition 6 alone: missing $(jq -c '.missing' <<<"$refusal"), $(jq -r '.error' <<<"$refusal")"
repair_named() { [ -n "$(end_review | jq -r '.rounds[0].findings[0].repair // empty' 2>/dev/null)" ]; }
wait_for 300 repair_named || { dump; fail "the drafted repair was not published within 300s: $(end_review | jq -c '.rounds[0].findings[0]')"; }
REPAIR=$(end_review | jq -r '.rounds[0].findings[0].repair')
repair_text=$(gc bd show "$REPAIR" --json | jq -r '.[0].description')
[ "$(field "$REPAIR" gc.ticket_kind)" = repair ] && [ "$(field "$REPAIR" gc.flow.mark)" = "new-flow/v1" ] \
  || fail "the published repair is not a marked repair ticket: $(gc bd show "$REPAIR" --json | jq -c '.[0].metadata')"
for expected in "F1.1" "${GATE1:0:12}" "spec_line : $STORY_ONE" "GET /health répond 200 avec chaque jeu de données"; do
  grep -qF -- "$expected" <<<"$repair_text" || fail "the published repair does not carry '$expected': $repair_text"
done
"$ROOT/bin/convoy-state" show "$CONVOY" --repo "$PRODUCT" | jq -e --arg r "$REPAIR" '.unruled == false and any(.tickets[]; .id == $r)' >/dev/null \
  || fail "the published repair is not a ticket of the convoy, or the convoy is in a state without rule"
repair_started() { [ -n "$(field "$REPAIR" gc.flow.gate.dispatch)" ]; }
wait_for 300 repair_started || { dump; fail "the repair $REPAIR was not started through the dispatch door within 300s"; }
[ "$(field "$REPAIR" gc.dispatched_via)" = dispatch-door ] || fail "the repair was not started through the dispatch door"
echo "$(date -u +%H:%M:%S) 2 : revue par la session $reviewer1 ($(jq -r '.duration_seconds' <<<"$round1") s, sortie complète) ; Blocking Finding F1.1 qui cite « $STORY_ONE » ; porte de fin refusée (condition 6 ; la 7, Evidence Pack, non lancée) : $(jq -r '.conditions[5].detail' <<<"$refusal" | cut -c1-150)… ; repair rédigé publié par la porte de patch ($REPAIR), démarré par la passe par la porte de dispatch ; tours de fin : 1"

# --- 3: the repair delivered, the review is replayed in full on the new tip --------
TIP2=$(delivered "$REPAIR" "docs/sonde-avec-chaque-jeu.md" "$RESTORED")
second_round() { [ "$(end_review | jq -r '.rounds | length' 2>/dev/null)" = 2 ]; }
wait_for 600 second_round || { dump; fail "the end review was not replayed on the new tip within 600s"; }
round2=$(end_review | jq -c '.rounds[1]')
GATE2=$(gate_record | jq -r '.commit')
[ "$GATE2" != "$GATE1" ] && git -C "$PRODUCT" merge-base --is-ancestor "$TIP2" "$GATE2" \
  || fail "the gate did not replay its verdicts on the tip that holds the repair: $GATE2"
jq -e --arg commit "$GATE2" --arg base "$BASE" '.commit == $commit and .base == $base and .outcome == "favorable"
  and .findings == [] and .coverage.missing == []' <<<"$round2" >/dev/null \
  || fail "the end review of the new tip is not a favorable review of the whole diff: $round2"
# A session is its name and its conversation (T42): gc 1.5.0 wakes the drained
# reviewer again under the same name, in a new generation (GC_RUNTIME_EPOCH,
# recorded as "g<n>") and a fresh conversation (wake_mode = "fresh").
reviewer2=$(jq -r '.recorded_by' <<<"$round2")
[ "$reviewer2 $(jq -r '.conversation // ""' <<<"$round2")" != "$reviewer1 $(jq -r '.conversation // ""' <<<"$round1")" ] \
  || fail "the second end review was made by the conversation of the first: $reviewer2 $(jq -c '.conversation' <<<"$round2")"
pass2=$(launch_pass "$GATE2")
jq -e --arg commit "$GATE2" '.spec_end.commit == $commit and .spec_end.verdicts.end_review == "fail"
  and (.spec_end.reason | test("jamais réutilisé"))' <<<"$pass2" >/dev/null \
  || fail "the pass that replayed the gate did not refuse the earlier round and launch the review again: $pass2"
jq -e --arg commit "$GATE2" '.outcome_evaluation.action == "launched" and .outcome_evaluation.commit == $commit' <<<"$pass2" >/dev/null \
  || fail "the Outcome Evaluation was not launched again with the review, on the new commit of the gate: $pass2"
brief2="$TRIAL/brief.$GATE2.json"
[ -f "$brief2" ] || fail "the second reviewer was given no brief for the new commit of the gate $GATE2"
[ "$reviewer2" = "$(sed -n "s/^[^ ]* \\([^ ]*\\) $GATE2\$/\\1/p" "$TRIAL/review-sessions" | head -1)" ] \
  || fail "the second end review was not recorded by the session that was given the brief of $GATE2: $reviewer2"
expected_files=$(git -C "$PRODUCT" diff --name-only "$BASE" "$GATE2" | sort | tr '\n' ' ')
[ "$(jq -r '[.diff.files[].path] | sort | join(" ")' "$brief2") " = "$expected_files" ] \
  || fail "the second review was not given the whole diff $BASE..$GATE2: $(jq -c '.diff.files' "$brief2")"
jq -e '.diff.extent.files >= 3' "$brief2" >/dev/null || fail "the second review read less than the whole diff"
gate_passes() { check_gate >/dev/null 2>&1; }
wait_for 600 gate_passes || fail "the gate does not pass its six conditions on the new tip: $(check_gate | jq -r '.error')"
[ "$(field "$CONVOY" gc.flow.counter.end_rounds)" = 1 ] || fail "a favorable end review counted a round of the end"
echo "$(date -u +%H:%M:%S) 3 : repair livré, pointe $TIP2 ; la porte rejoue ses verdicts sur $GATE2 et refuse le tour précédent ; revue refaite en entier par une autre session ($reviewer2 ≠ $reviewer1) sur $(jq -r '.diff.extent.files' "$brief2") fichiers, favorable, produit évalué de nouveau par la même passe ; la porte de fin passe ses six conditions : $(check_gate | jq -c '[.conditions[] | {(.name): .verdict}] | add')"

gc session list --state all --json | jq -e '[.sessions[] | select(.template | test("mayor"))] | length == 0' >/dev/null \
  || fail "a Mayor session exists in the trial city"
echo "PASS: the assembled diff was reviewed on the commit of the gate, its Blocking Finding became a published repair, and the review was replayed in full on the new tip"
