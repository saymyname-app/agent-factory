#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime, an isolated Dolt server and its own supervisor
#
# Adoption trial of fresh sessions (T42, af-rc0ozs; Spec af-wf4w5r §4
# « Session neuve et worktree par ticket. N auteurs en parallèle », §5 « le
# rôle relecteur, session neuve ») in a disposable city that shares nothing
# with the live Factory: its own GC_HOME, runtime directory, supervisor port,
# controller, evidence store and work trees. The product is a copy of the
# Delivery Fixture City, committed in the city root. The city has no Mayor.
#
# The agents of the author and reviewer roles are the delivered ones:
# agents/delivery-author and agents/delivery-reviewer are copied as they
# are, and the trial fails if their agent.toml differs from the delivered
# file by one byte. config/delivery-roles.json is the delivered one, and N is
# the delivered max_sessions of config/delivery-flow.json. Only the providers
# behind the agents are stubs, so nothing is spent: the workspace provider
# (the author has no other) and `claude-readonly` (the reviewer's) are
# scripted sessions.
#
# What is real: the controller and its session pool, the order that starts
# the tickets (bin/convoy-advance), the two formulas (mol-ticket-author,
# mol-test-review), bin/test-review, bin/tdd-step, bin/convoy-state and
# bin/dispatch-door. A scripted session does what the prompt of its role
# says: it asks Gas City for work (`gc hook --claim`), works what it is
# given, asks again, and leaves (`gc runtime drain-ack`) when it is given
# nothing.
#
# Two ready tickets without dependency, A and B:
#   1. Both are started under N=2 and each is taken by an author session.
#      One reading of `gc session list` shows the two sessions alive.
#   2. A proves its red and asks for the review of its tests: a reviewer
#      session renders it. That session stays alive.
#   3. B then asks for its review. The session that served A hands in a
#      verdict on B anyway: bin/test-review refuses it, the launch is counted
#      as one without result and nothing else is written. It then asks Gas
#      City for more work and is offered none.
#   4. A second reviewer session renders the review of B.
#
# The trial prints its record (« relevé d'essai ») on stdout.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
. "$ROOT/tests/lib/isolated-city.sh"
PORT="${FRESH_SESSIONS_TRIAL_PORT:-18461}"
SPEC="fx-spec"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc bd jq git dolt tmux curl python3 cmp; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done
CEILING=$(jq -r '.max_sessions' "$ROOT/config/delivery-flow.json")
[ "$CEILING" = 2 ] || fail "the trial is written for N=2; config/delivery-flow.json gives max_sessions=$CEILING"

TRIAL=$(mktemp -d /tmp/af-rc0ozs-fresh.XXXXXX)
CITY="$TRIAL/c"
PRODUCT="$CITY"
FIXTURE="tests/fixtures/delivery-fixture-city"
cleanup() {
  status=$?
  trap - EXIT
  isolated_city_stop "$TRIAL" "$CITY" >/dev/null 2>&1 || true
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
# tests/ticket-author-isolated-city-test.sh).
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$|FACTORY_ROOT$|CONVOY_|DISPATCH_DOOR_|ESCALATION_DOOR_|EVIDENCE_|TICKET_AUTHOR_|SPEC_INTEGRATION_|TEST_REVIEW_(DISPATCH|POLL|FAKE)|DELIVERY_ROLE_)' || true)
export GC_HOME="$TRIAL/h" XDG_RUNTIME_DIR="$TRIAL/r" GC_DISABLE_USAGE_METRICS=1
unset DBUS_SESSION_BUS_ADDRESS
export PATH="/usr/local/bin:$HOME/.local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
mkdir -p "$GC_HOME"
mkdir -m 700 "$XDG_RUNTIME_DIR"
printf '[supervisor]\nport = %s\n' "$PORT" > "$GC_HOME/supervisor.toml"

# What every tool of the flow reads, in the stub sessions, in the order and
# in the check alike: the city as Factory root, and stores of the trial. The
# dispatch door is the real one; it asks these two stubs where a role runs
# and whether its adoption trial passed (the stubs of this city are no
# provider to try).
cat > "$TRIAL/env" <<ENV
export FACTORY_ROOT="$CITY"
export CONVOY_STATE_LOCK_DIR="$TRIAL/locks" CONVOY_ADVANCE_LOCK_DIR="$TRIAL/locks" SPEC_INTEGRATION_LOCK_DIR="$TRIAL/locks"
export SPEC_INTEGRATION_WORK_DIR="$TRIAL/merge"
export EVIDENCE_STORE_DIR="$TRIAL/store" TICKET_AUTHOR_WORKTREES_DIR="$TRIAL/worktrees"
export ESCALATION_DOOR_LOCK_FILE="$TRIAL/escalation-door.lock" PROPOSAL_DOOR_BIN="$TRIAL/proposal-door"
export DISPATCH_DOOR_PROVIDER_FAILOVER_BIN="$TRIAL/provider-failover" DISPATCH_DOOR_ROLE_TRIAL_BIN="$TRIAL/role-adoption-trial"
export TEST_REVIEW_POLL_SECONDS=3
export GIT_AUTHOR_NAME=essai GIT_AUTHOR_EMAIL=essai@example.invalid GIT_COMMITTER_NAME=essai GIT_COMMITTER_EMAIL=essai@example.invalid
ENV
printf '#!/bin/sh\necho 0\n' > "$TRIAL/proposal-door"
cat > "$TRIAL/provider-failover" <<'SH'
#!/bin/sh
printf '%s\n' '{"total_exhaustion": {"active": false}, "targets": {"delivery-author": {"effective": "stub-author"}, "delivery-reviewer": {"effective": "claude-readonly"}}}'
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

# --- the scripted author ---------------------------------------------------------
# One session, one ticket: the steps of mol-ticket-author up to the freeze.
# It holds before its red step until the trial lets its ticket go, so the
# trial decides when each review is asked.
cat > "$TRIAL/stub-author" <<STUB
#!/bin/bash
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
  CONVOY=\$("\$BIN/ticket-author" locate "\$TICKET" | jq -r '.convoy')
  START=\$("\$BIN/ticket-author" start "\$CONVOY" "\$TICKET" 2>>"\$LOG")
  WT=\$(printf '%s' "\$START" | jq -r '.worktree'); BASE=\$(printf '%s' "\$START" | jq -r '.base')
  PROFILE=\$(printf '%s' "\$START" | jq -r '.profile')
  say "ticket \$TICKET étape \$STEP"
  echo "\$TICKET \$STEP \${GC_SESSION_NAME:-?}" >> "$TRIAL/steps"
  if [ "\$STEP" = red ]; then
    while [ ! -e "$TRIAL/go.\$TICKET" ]; do sleep 2; done
    cp "$TRIAL/tests/test_health.py" "$TRIAL/tests/test_count.py" "$TRIAL/tests/criteria.json" "\$WT/$FIXTURE/tests/"
    git -C "\$WT" add -A; git -C "\$WT" commit -q -m "tests de critère"
    tool "\$BIN/tdd-step" red "\$CONVOY" "\$TICKET" --repo "\$WT" --profile "\$PROFILE" --dataset content --base "\$BASE" --table "$FIXTURE/tests/criteria.json"
    rc=6
    while [ "\$rc" = 6 ]; do
      "\$BIN/test-review" review "\$CONVOY" "\$TICKET" --repo "\$WT" --wait 120 >> "\$LOG" 2>&1; rc=\$?
    done
    say "ticket \$TICKET : test-review review a rendu \$rc"
    tool "\$BIN/tdd-step" freeze "\$CONVOY" "\$TICKET" --repo "\$WT"
    # The trial ends at the freeze: the session keeps its ticket and stays.
    exec sleep 3600
  fi
  gc bd update "\$BEAD" --set-metadata gc.outcome=pass --status=closed --notes "étape \$STEP close par l'auteur" >/dev/null 2>&1
done
STUB
chmod +x "$TRIAL/stub-author"

# --- the scripted reviewer --------------------------------------------------------
# What the prompt of the role says: ask Gas City for work, do the review of
# mol-test-review (the brief, one answer per test, `test-review record`),
# close, ask again, and leave when nothing is offered. The first session to
# serve a review waits, before it asks again, until the trial says the next
# review is launched; it hands in a verdict on that review anyway, as a
# session that kept working would, then asks again and is offered nothing.
cat > "$TRIAL/stub-reviewer" <<STUB
#!/bin/bash
. "$TRIAL/env"
export DELIVERY_ROLE_READ_ONLY=1
BIN="$ROOT/bin"
LOG="$TRIAL/reviewer.log"
say() { echo "\$(date -u +%H:%M:%S) \${GC_SESSION_NAME:-?} \$*" >> "\$LOG"; }
verdict() { # <convoy> <ticket> <file>: every test favorable
  "\$BIN/test-review" brief "\$1" "\$2" 2>>"\$LOG" \
    | jq '{commit, files: .fingerprints, tests: (.tests | map({key: .id, value: {state: "favorable"}}) | from_entries)}' > "\$3"
}
SERVED=0
FIRST=0
while true; do
  CLAIM=\$(gc hook --claim --json 2>/dev/null)
  ACTION=\$(printf '%s' "\$CLAIM" | jq -r '.action // empty' 2>/dev/null)
  BEAD=\$(printf '%s' "\$CLAIM" | jq -r '.bead_id // empty' 2>/dev/null)
  if [ "\$ACTION" != work ] || [ -z "\$BEAD" ]; then
    if [ "\$SERVED" = 0 ]; then sleep 3; continue; fi
    echo "\${GC_SESSION_NAME:-?} none" >> "$TRIAL/asked-again"
    say "a redemandé du travail : rien n'est offert"
    gc runtime drain-ack >/dev/null 2>&1
    exit 0
  fi
  if [ "\$SERVED" = 1 ]; then echo "\${GC_SESSION_NAME:-?} \$BEAD" >> "$TRIAL/asked-again"; fi
  ROOT_BEAD=\$(gc bd show "\$BEAD" --json | jq -r '.[0].metadata["gc.root_bead_id"]')
  INPUT=\$(gc bd show "\$ROOT_BEAD" --json | jq -r '.[0].metadata["gc.input_convoy_id"]')
  REVIEW_BEAD=\$(gc convoy status "\$INPUT" --json | jq -r '.children[0].id')
  TEXT=\$(gc bd show "\$REVIEW_BEAD" --json | jq -r '.[0].description')
  CONVOY=\$(printf '%s\n' "\$TEXT" | sed -n 's/^convoy: //p'); TICKET=\$(printf '%s\n' "\$TEXT" | sed -n 's/^ticket: //p')
  echo "\$TICKET \$REVIEW_BEAD \${GC_SESSION_NAME:-?}" >> "$TRIAL/review-sessions"
  OUTCOME=pass
  verdict "\$CONVOY" "\$TICKET" "$TRIAL/verdict.\$REVIEW_BEAD.json"
  "\$BIN/test-review" record "\$CONVOY" "\$TICKET" --verdict-file "$TRIAL/verdict.\$REVIEW_BEAD.json" >> "\$LOG" 2>&1 || OUTCOME=fail
  say "ticket \$TICKET : verdict remis (\$REVIEW_BEAD, \$OUTCOME)"
  gc bd update "\$REVIEW_BEAD" --set-metadata gc.outcome=\$OUTCOME --status=closed --notes "relecture \$OUTCOME" >/dev/null 2>&1
  gc bd update "\$BEAD" --set-metadata gc.outcome=\$OUTCOME --status=closed --notes "relecture \$OUTCOME" >/dev/null 2>&1
  if [ "\$SERVED" = 0 ] && mkdir "$TRIAL/first-served" 2>/dev/null; then
    FIRST=1
    for _ in \$(seq 1 300); do [ -e "$TRIAL/second-launched" ] && break; sleep 2; done
    # Handed in before it asks again: Gas City ends a session of the pool
    # once it is offered nothing.
    NEXT=\$(cat "$TRIAL/second-launched")
    verdict "\$CONVOY" "\$NEXT" "$TRIAL/verdict.served.json"
    "\$BIN/test-review" record "\$CONVOY" "\$NEXT" --verdict-file "$TRIAL/verdict.served.json" > "$TRIAL/served.out" 2>>"\$LOG"
    echo "\$?" > "$TRIAL/served.rc"
    say "verdict remis sur \$NEXT par une session qui a déjà servi : statut \$(cat "$TRIAL/served.rc")"
  fi
  SERVED=1
done
STUB
chmod +x "$TRIAL/stub-reviewer"

# What the authors write: the criterion tests and their table.
mkdir -p "$TRIAL/tests"
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

# --- the city: the delivered role agents, on stub providers ------------------------
cat > "$CITY/city.toml" <<TOML
[workspace]
provider = "stub-author"

[providers.stub-author]
base = "builtin:claude"
command = "$TRIAL/stub-author"
# A stub is a shell script: without its process name Gas City finds no
# \`claude\` process in the session and reaps it as a zombie.
process_names = ["stub-author", "bash"]
ready_delay_ms = 0

# The provider agents/delivery-reviewer/agent.toml names.
[providers.claude-readonly]
base = "builtin:claude"
command = "$TRIAL/stub-reviewer"
process_names = ["stub-reviewer", "bash"]
ready_delay_ms = 0
TOML
mkdir -p "$CITY/agents" "$CITY/formulas" "$CITY/orders" "$CITY/config/projects" "$CITY/config/project-descriptors" "$CITY/bin"
for agent in delivery-author delivery-reviewer; do
  cp -R "$ROOT/agents/$agent" "$CITY/agents/$agent"
  cmp -s "$ROOT/agents/$agent/agent.toml" "$CITY/agents/$agent/agent.toml" \
    || fail "agents/$agent/agent.toml of the trial is not the delivered one"
done
cp "$ROOT/formulas/mol-ticket-author.formula.toml" "$ROOT/formulas/mol-test-review.formula.toml" "$CITY/formulas/"
mkdir -p "$CITY/assets/scripts/checks"
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
sling_target = "delivery-author"
formulas = "mol-ticket-author,mol-test-review"
TOML
jq '.rigs = ["trial"]' "$ROOT/$FIXTURE/descriptor.json" > "$CITY/config/project-descriptors/trial.json"
jq '{contract, max_sessions, start, test_review: (.test_review | .rig = "trial" | .timeout_seconds = 600)}' \
  "$ROOT/config/delivery-flow.json" > "$CITY/config/delivery-flow.json"
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
A=$(new_ticket "ticket A, relu en premier")
B=$(new_ticket "ticket B, relu ensuite")
ALL=("$A" "$B")
for t in "${ALL[@]}"; do
  gc bd dep add "$CONVOY" "$t" --type tracks >/dev/null
  gc bd update "$t" --set-metadata gc.ticket_kind=vertical_slice >/dev/null
done

caps=$(for agent in delivery-author delivery-reviewer; do
  printf '%s max_active_sessions=%s ; ' "$agent" "$(sed -n 's/^max_active_sessions = //p' "$CITY/agents/$agent/agent.toml")"; done)
echo "relevé d'essai — sessions neuves, cité isolée ($(gc version 2>/dev/null | head -1), N=$CEILING, aucun Mayor, agents de livraison tels que livrés sur des fournisseurs scriptés, vraie porte de dispatch)"
echo "agents (agent.toml identiques à ceux livrés) : ${caps% ; }"
echo "convoi $CONVOY (Spec $SPEC) : A=$A B=$B, sans dépendance"

(gc supervisor run > "$TRIAL/supervisor.out" 2>&1 &)
sleep 3
gc --city "$CITY" start >/dev/null 2>&1 || true
grep -q "Controller: supervisor-managed" <<<"$(gc --city "$CITY" status 2>/dev/null)" || fail "the isolated city's controller did not start"
gc order show convoy-advance --json >/dev/null 2>&1 || fail "the city does not accept orders/convoy-advance.toml"
for formula in mol-ticket-author mol-test-review; do
  grep -q "^$formula\$" <<<"$(gc formula list 2>/dev/null)" || fail "the city does not resolve formulas/$formula.formula.toml"
done
gates=$("$ROOT/bin/factory-build-gates" --root "$CITY") || fail "factory-build-gates did not materialise the check of the formula: $gates"

state mark "$CONVOY" \
  --demonstration-line "$A=La page d'accueil affiche le nombre d'éléments" \
  --demonstration-line "$B=La page d'accueil affiche le nombre d'éléments" \
  --user-stories "$A=1" --user-stories "$B=2" >/dev/null
opened=$("$ROOT/bin/spec-integration" open "$CONVOY" --repo "$PRODUCT" --protected main) \
  || fail "spec-integration open did not pass: $opened"
echo "$(date -u +%H:%M:%S) marque posée, branche integration/$SPEC ouverte"

field() { gc bd show "$1" --json | jq -r --arg k "$2" '.[0].metadata[$k] // empty'; }
wait_for() { # <seconds> <command...>
  local deadline=$(( $(date +%s) + $1 )); shift
  until "$@"; do
    [ "$(date +%s)" -lt "$deadline" ] || return 1
    sleep 3
  done
}
step_session() { sed -n "s/^$1 $2 //p" "$TRIAL/steps" 2>/dev/null | head -1; }
review_of() { field "$1" gc.flow.test_review; }
round_session() { review_of "$1" | jq -r '.rounds[0].recorded_by // empty' 2>/dev/null; }
live() { # <agent>: the sessions of the agent that are not over, one reading
  gc session list --json | jq -c --arg agent "$1" '[.sessions[] | select((.template | split("/") | last) == $agent)
    | select((.closed // false) | not) | select(.state != "closed") | {session: .session_name, state}]'
}
dump() {
  tail -30 "$TRIAL/author.log" >&2 || true; tail -20 "$TRIAL/reviewer.log" >&2 || true; tail -20 "$TRIAL/checks.log" >&2 || true
  tail -3 "$TRIAL/passes.jsonl" >&2 || true; gc session list --state all 2>&1 | tail -12 >&2 || true
}

# --- 1. two author sessions alive at the same moment, under N=2 --------------------
both_hold() { [ -n "$(step_session "$A" red)" ] && [ -n "$(step_session "$B" red)" ]; }
wait_for 420 both_hold || { dump; fail "the two ready tickets were not both held by an author session within 420s (N=$CEILING; live author sessions: $(live delivery-author))"; }
author_a=$(step_session "$A" red); author_b=$(step_session "$B" red)
[ "$author_a" != "$author_b" ] || fail "one author session holds both tickets: $author_a"
authors=$(live delivery-author)
for session in "$author_a" "$author_b"; do
  printf '%s' "$authors" | jq -e --arg s "$session" 'any(.[]; .session == $s)' >/dev/null \
    || fail "the author session $session is not alive in the reading that shows the other: $authors"
done
for t in "${ALL[@]}"; do
  taken=$(state show "$CONVOY" | jq -r --arg t "$t" '.tickets[] | select(.id == $t) | .session.name')
  [ "$taken" = "$(step_session "$t" red)" ] || fail "the ticket $t is recorded under the session $taken, not the one that works it"
done
echo "$(date -u +%H:%M:%S) 1. deux tickets prêts démarrés par l'ordre sous N=$CEILING ; une lecture de gc session list : $authors ; A est tenu par $author_a, B par $author_b"

# --- 2. the review of A, by a first reviewer session -------------------------------
touch "$TRIAL/go.$A"
a_reviewed() { [ -n "$(round_session "$A")" ]; }
wait_for 600 a_reviewed || { dump; fail "the review of the tests of A was not rendered within 600s"; }
first=$(round_session "$A")
printf '%s' "$(live delivery-reviewer)" | jq -e --arg s "$first" 'any(.[]; .session == $s)' >/dev/null \
  || fail "the reviewer session $first is no longer alive after the review of A: the trial needs it alive when B asks"
echo "$(date -u +%H:%M:%S) 2. relecture de A rendue par $first ($(review_of "$A" | jq -r '.rounds[0].verdict')) ; cette session reste vivante"

# --- 3. the review of B is launched: the session that served A is offered nothing ---
touch "$TRIAL/go.$B"
b_launched() { [ "$(review_of "$B" | jq -r '(.request.launches // []) | length' 2>/dev/null)" -ge 1 ] 2>/dev/null || [ -n "$(round_session "$B")" ]; }
wait_for 600 b_launched || { dump; fail "the review of the tests of B was not launched within 600s"; }
launched=$(review_of "$B" | jq -r '.request.launches[0].bead // empty')
echo "$B" > "$TRIAL/second-launched.tmp" && mv "$TRIAL/second-launched.tmp" "$TRIAL/second-launched"
asked() { grep -q "^$first " "$TRIAL/asked-again" 2>/dev/null; }
wait_for 300 asked || { dump; fail "the reviewer session $first did not ask for more work within 300s"; }
offered=$(sed -n "s/^$first //p" "$TRIAL/asked-again" | head -1)
[ "$offered" = none ] || { dump; fail "Gas City offered the review bead $offered to $first, the session that already served the review of A: no fresh session for the review of B"; }
echo "$(date -u +%H:%M:%S) 3. relecture de B lancée (${launched:-déjà rendue}) pendant que $first vit ; $first redemande du travail (gc hook --claim) : rien ne lui est offert"

served_tried() { [ -s "$TRIAL/served.rc" ]; }
wait_for 120 served_tried || { dump; fail "the session $first did not hand in its verdict on B within 120s"; }
[ "$(cat "$TRIAL/served.rc")" = 1 ] || { cat "$TRIAL/served.out" >&2; fail "the verdict on B handed in by $first, which served the review of A, was not refused (status $(cat "$TRIAL/served.rc"))"; }
refusal=$(jq -r '.error' "$TRIAL/served.out")
[ "$(round_session "$B")" != "$first" ] || fail "B carries a review rendered by $first"
counted=$(review_of "$B" | jq -c '.request.launches // empty')
echo "$(date -u +%H:%M:%S)    verdict sur B remis par $first : refusé (« $refusal ») ; lancements de la relecture de B après le refus : ${counted:-relecture déjà rendue par une autre session}"

# --- 4. the review of B, by another session -----------------------------------------
b_reviewed() { [ -n "$(round_session "$B")" ]; }
wait_for 900 b_reviewed || { dump; fail "the review of the tests of B was not rendered within 900s"; }
second=$(round_session "$B")
[ "$second" != "$first" ] || fail "the two reviews were rendered by one session: $first"
known=$(gc session list --state all --json | jq -c '[.sessions[] | select((.template | split("/") | last) == "delivery-reviewer") | .session_name]')
# $first was read alive among the sessions of that agent at step 2; it has
# left since, and Gas City no longer lists it.
printf '%s' "$known" | jq -e --arg s "$second" 'index($s) != null' >/dev/null \
  || fail "$second is not a session of the delivered reviewer agent: $known"
[ "$(review_of "$A" | jq -c '[.rounds[].recorded_by]')" = "[\"$first\"]" ] || fail "A does not carry exactly the review of $first"
[ "$(review_of "$B" | jq -c '[.rounds[].recorded_by]')" = "[\"$second\"]" ] || fail "B does not carry exactly the review of $second"
b_frozen() { [ -n "$(field "$B" gc.flow.tdd.freeze)" ]; }
wait_for 300 b_frozen || { dump; fail "the tests of B were not frozen after their review"; }
[ -z "$(field "$B" gc.flow.stop)" ] || fail "B is stopped: $(field "$B" gc.flow.stop)"
echo "$(date -u +%H:%M:%S) 4. relecture de B rendue par $second ($(review_of "$B" | jq -r '.rounds[0].verdict')), tests gelés ; sessions du relecteur dans la cité : $known"

gc session list --state all --json | jq -e '[.sessions[] | select(.template | test("mayor"))] | length == 0' >/dev/null \
  || fail "a Mayor session exists in the trial city"
echo "PASS: two author sessions worked two tickets at the same time under N=$CEILING, two successive reviews were rendered by two reviewer sessions, and a verdict from a session that had already served was refused"
