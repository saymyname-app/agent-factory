#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime, an isolated Dolt server and its own supervisor
#
# Adoption trial of fresh sessions (T42, af-rc0ozs; Spec af-wf4w5r §4
# « Session neuve et worktree par ticket. N auteurs en parallèle ») in a
# disposable city that shares nothing
# with the live Factory: its own GC_HOME, runtime directory, supervisor port,
# controller, evidence store and work trees. The product is a copy of the
# Delivery Fixture City, committed in the city root. The city has no Mayor.
#
# The agent of the author role is the delivered one: agents/delivery-author
# is copied as it is, and the trial fails if its agent.toml differs from the
# delivered file by one byte. config/delivery-roles.json is the delivered
# one, and N is the delivered max_sessions of config/delivery-flow.json. Only
# the provider behind the agent is a stub, so nothing is spent: the workspace
# provider (the author has no other) is a scripted session.
#
# What is real: the controller and its session pool, the order that starts
# the tickets (bin/convoy-advance), the formula mol-ticket-author,
# bin/tdd-step, bin/convoy-state and bin/dispatch-door. A scripted session
# does what the prompt of its role says: it asks Gas City for work
# (`gc hook --claim`) and works what it is given.
#
# Two ready tickets without dependency, A and B, are started under N=2 and
# each is taken by an author session. One reading of `gc session list` shows
# the two sessions alive.
#
# A fresh reviewer session per review (Spec §5) was tried here on the review
# of the criterion tests until ADR-0030 L7 removed it with bin/test-review;
# the code review and the Ticket Evaluation keep the same refusal
# (bin/convoy-state, tests/code-review-test.py, tests/ticket-evaluation-test.py).
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
    isolated_city_remove "$TRIAL"
  fi
  exit "$status"
}
trap cleanup EXIT

# Nothing of the live Factory may reach this city (same recipe as
# tests/ticket-author-isolated-city-test.sh).
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$|FACTORY_ROOT$|CONVOY_|DISPATCH_DOOR_|ESCALATION_DOOR_|EVIDENCE_|TICKET_AUTHOR_|SPEC_INTEGRATION_|DELIVERY_ROLE_)' || true)
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
# One session, one ticket: the steps of mol-ticket-author up to the freeze,
# where it keeps its ticket and stays.
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
    cp "$TRIAL/tests/test_health.py" "$TRIAL/tests/test_count.py" "$TRIAL/tests/criteria.json" "\$WT/$FIXTURE/tests/"
    git -C "\$WT" add -A; git -C "\$WT" commit -q -m "tests de critère"
    tool "\$BIN/tdd-step" red "\$CONVOY" "\$TICKET" --repo "\$WT" --profile "\$PROFILE" --dataset content --base "\$BASE" --table "$FIXTURE/tests/criteria.json"
    tool "\$BIN/tdd-step" freeze "\$CONVOY" "\$TICKET" --repo "\$WT"
    # The trial ends at the freeze: the session keeps its ticket and stays.
    exec sleep 3600
  fi
  gc bd update "\$BEAD" --set-metadata gc.outcome=pass --status=closed --notes "étape \$STEP close par l'auteur" >/dev/null 2>&1
done
STUB
chmod +x "$TRIAL/stub-author"

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
TOML
mkdir -p "$CITY/agents" "$CITY/formulas" "$CITY/orders" "$CITY/config/projects" "$CITY/config/project-descriptors" "$CITY/bin"
cp -R "$ROOT/agents/delivery-author" "$CITY/agents/delivery-author"
cmp -s "$ROOT/agents/delivery-author/agent.toml" "$CITY/agents/delivery-author/agent.toml" \
  || fail "agents/delivery-author/agent.toml of the trial is not the delivered one"
cp "$ROOT/formulas/mol-ticket-author.formula.toml" "$CITY/formulas/"
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
formulas = "mol-ticket-author"
TOML
jq '.rigs = ["trial"] | .stacks = {"trial": ["fixture-stack"]}' "$ROOT/$FIXTURE/descriptor.json" > "$CITY/config/project-descriptors/trial.json"
jq '{contract, max_sessions, start}' \
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
A=$(new_ticket "ticket A")
B=$(new_ticket "ticket B")
ALL=("$A" "$B")
for t in "${ALL[@]}"; do
  gc bd dep add "$CONVOY" "$t" --type tracks >/dev/null
  gc bd update "$t" --set-metadata gc.ticket_kind=vertical_slice >/dev/null
done

caps="delivery-author max_active_sessions=$(sed -n 's/^max_active_sessions = //p' "$CITY/agents/delivery-author/agent.toml")"
echo "relevé d'essai — sessions neuves, cité isolée ($(gc version 2>/dev/null | head -1), N=$CEILING, aucun Mayor, agents de livraison tels que livrés sur des fournisseurs scriptés, vraie porte de dispatch)"
echo "agent (agent.toml identique à celui livré) : $caps"
echo "convoi $CONVOY (Spec $SPEC) : A=$A B=$B, sans dépendance"

isolated_city_disable_dog "$TRIAL" "$CITY"
(env -u CLAUDE_CODE_SESSION_ID gc supervisor run > "$TRIAL/supervisor.out" 2>&1 &)
sleep 3
gc --city "$CITY" start >/dev/null 2>&1 || true
grep -q "Controller: supervisor-managed" <<<"$(gc --city "$CITY" status 2>/dev/null)" || fail "the isolated city's controller did not start"
gc order show convoy-advance --json >/dev/null 2>&1 || fail "the city does not accept orders/convoy-advance.toml"
grep -q "^mol-ticket-author\$" <<<"$(gc formula list 2>/dev/null)" || fail "the city does not resolve formulas/mol-ticket-author.formula.toml"
gates=$("$ROOT/bin/factory-build-gates" --root "$CITY") || fail "factory-build-gates did not materialise the check of the formula: $gates"

state mark "$CONVOY" \
  --demonstration-line "$A=La page d'accueil affiche le nombre d'éléments" \
  --demonstration-line "$B=La page d'accueil affiche le nombre d'éléments" \
  --user-stories "$A=1" --user-stories "$B=2" >/dev/null
opened=$("$ROOT/bin/spec-integration" open "$CONVOY" --repo "$PRODUCT" --protected main) \
  || fail "spec-integration open did not pass: $opened"
echo "$(date -u +%H:%M:%S) marque posée, branche integration/$SPEC ouverte"

wait_for() { # <seconds> <command...>
  local deadline=$(( $(date +%s) + $1 )); shift
  until "$@"; do
    [ "$(date +%s)" -lt "$deadline" ] || return 1
    sleep 3
  done
}
step_session() { sed -n "s/^$1 $2 //p" "$TRIAL/steps" 2>/dev/null | head -1; }
live() { # <agent>: the sessions of the agent that are not over, one reading
  gc session list --json | jq -c --arg agent "$1" '[.sessions[] | select((.template | split("/") | last) == $agent)
    | select((.closed // false) | not) | select(.state != "closed") | {session: .session_name, state}]'
}
dump() {
  tail -30 "$TRIAL/author.log" >&2 || true; tail -20 "$TRIAL/checks.log" >&2 || true
  tail -3 "$TRIAL/passes.jsonl" >&2 || true; gc session list --state all 2>&1 | tail -12 >&2 || true
}

# --- two author sessions alive at the same moment, under N=2 -----------------------
both_hold() { [ -n "$(step_session "$A" red)" ] && [ -n "$(step_session "$B" red)" ]; }
# A controller tick and two formula claims can take just over seven minutes
# under gc 1.5 even while both sessions keep advancing (af-x3re4a).
wait_for 600 both_hold || { dump; fail "the two ready tickets were not both held by an author session within 600s (N=$CEILING; live author sessions: $(live delivery-author))"; }
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
echo "$(date -u +%H:%M:%S) deux tickets prêts démarrés par l'ordre sous N=$CEILING ; une lecture de gc session list : $authors ; A est tenu par $author_a, B par $author_b"

gc session list --state all --json | jq -e '[.sessions[] | select(.template | test("mayor"))] | length == 0' >/dev/null \
  || fail "a Mayor session exists in the trial city"
echo "PASS: two author sessions worked two tickets at the same time under N=$CEILING"
