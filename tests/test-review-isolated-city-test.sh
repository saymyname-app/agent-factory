#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime, an isolated Dolt server and its own supervisor
#
# Adoption trial of the review of criterion tests before the freeze (T13,
# af-nkpjpr; Spec af-wf4w5r §5 « Relecture avant gel », §8) in a disposable
# city that shares nothing with the live Factory: its own GC_HOME, runtime
# directory, supervisor port, controller, evidence store and work trees. The
# product is a copy of the Delivery Fixture City, committed in the city root.
# The city has no Mayor.
#
# What is real: the controller, the order that starts the tickets
# (bin/convoy-advance), the two formulas (mol-ticket-author, mol-test-review),
# the check of the author's steps, bin/test-review, bin/tdd-step,
# bin/convoy-state, bin/dispatch-door (which routes each review to the agent
# of the reviewer role) and bin/escalation-door. What is scripted, and spends
# nothing: the author and the reviewer. Each is a stub that claims the step
# Gas City routes to it and runs the real tools the step names; the reviewer
# stub refuses a test that only compares a status, by reading the brief.
#
# Three tickets of the fixture:
#   A  writes a criterion test that only checks a status 200: the review
#      refuses it with its reason, the freeze does not happen; the author
#      corrects the test, the second review passes, the tests are frozen and
#      the code step starts.
#   B  answers the refusal with another status-only test: the second refusal
#      stops the ticket, which appears once on the operator's list; the code
#      step never starts.
#   C  has honest tests, but its reviewer sessions end without a verdict: one
#      relaunch, then the ticket is stopped and appears once on the list.
#
# The trial prints its record (« relevé d'essai ») on stdout.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
. "$ROOT/tests/lib/isolated-city.sh"
PORT="${TEST_REVIEW_TRIAL_PORT:-18399}"
CEILING=6
SPEC="fx-spec"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc bd jq git dolt tmux curl python3; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

TRIAL=$(mktemp -d /tmp/af-nkpjpr-review.XXXXXX)
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
write_tests() { # <count test file of the trial>
  cp "$TRIAL/tests/test_health.py" "$TRIAL/tests/criteria.json" "\$WT/$FIXTURE/tests/"
  cp "$TRIAL/tests/\$1" "\$WT/$FIXTURE/tests/test_count.py"
  git -C "\$WT" add -A; git -C "\$WT" commit -q -m "tests de critère (\$1)"
  tool "\$BIN/tdd-step" red "\$CONVOY" "\$TICKET" --repo "\$WT" --profile "\$PROFILE" --dataset content --base "\$BASE" --table "$FIXTURE/tests/criteria.json"
}
review() { # the review of the tests at HEAD, waited for; its exit status
  local rc=6
  while [ "\$rc" = 6 ]; do
    "\$BIN/test-review" review "\$CONVOY" "\$TICKET" --repo "\$WT" --wait 120 >> "\$LOG" 2>&1; rc=\$?
  done
  say "ticket \$TICKET : test-review review a rendu \$rc"
  echo "\$TICKET \$rc" >> "$TRIAL/reviews"
  return "\$rc"
}
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
  STOPPED=\$(gc bd show "\$TICKET" --json | jq -r '.[0].metadata["gc.flow.stop"] // empty')
  if [ -z "\$STOPPED" ] || [ "\$STEP" = drain ]; then
    case "\$STEP:\$MODE" in
      red:corrects|red:insists)
        write_tests test_count_status_only.py
        if review; then :; else
          # The one return to the author: A observes the criterion this time, B does not.
          if [ "\$MODE" = corrects ]; then write_tests test_count.py; else write_tests test_count_status_again.py; fi
          review || true
        fi
        tool "\$BIN/tdd-step" freeze "\$CONVOY" "\$TICKET" --repo "\$WT" ;;
      red:honest)
        write_tests test_count.py
        review || true
        tool "\$BIN/tdd-step" freeze "\$CONVOY" "\$TICKET" --repo "\$WT" ;;
      code:*)
        cp "$TRIAL/code/app.py" "\$WT/$FIXTURE/app.py"
        git -C "\$WT" add -A; git -C "\$WT" commit -q -m "le nombre et le jeu"
        tool "\$BIN/tdd-step" green "\$CONVOY" "\$TICKET" --repo "\$WT" --profile "\$PROFILE" --dataset content ;;
      drain:*)
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

# --- the scripted reviewer --------------------------------------------------------
# One session, one review, as the step of mol-test-review asks: the brief,
# one answer per test, the verdict handed to `test-review record`. Its
# judgement is a rule: a test that compares a status and never reads the
# page is refused. For a ticket whose reviewer is « mute » the session ends
# without a verdict, as a crashed one would.
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
  echo "\$TICKET \$REVIEW_BEAD \${GC_SESSION_NAME:-?}" >> "$TRIAL/review-sessions"
  OUTCOME=pass
  if [ "\$(cat "$TRIAL/reviewer.\$TICKET")" = mute ]; then
    say "ticket \$TICKET : session terminée sans verdict (\$REVIEW_BEAD)"
    OUTCOME=fail
  else
    BRIEF=\$("\$BIN/test-review" brief "\$CONVOY" "\$TICKET" 2>>"\$LOG")
    printf '%s' "\$BRIEF" | jq '
      . as \$b | {commit, files: .fingerprints, tests: (.tests | map(. as \$t | {key: .id, value: (
        if (\$b.files[\$t.file] | test("assertEqual\\\\(200, status\\\\)")) and (\$b.files[\$t.file] | test("fixture-count") | not)
        then {state: "unfavorable", reason: "le test ne compare qu'"'"'un statut 200 : il passerait sur une page qui n'"'"'affiche pas le nombre d'"'"'éléments"}
        else {state: "favorable"} end)}) | from_entries)}' > "$TRIAL/verdict.\$REVIEW_BEAD.json"
    "\$BIN/test-review" record "\$CONVOY" "\$TICKET" --verdict-file "$TRIAL/verdict.\$REVIEW_BEAD.json" >> "\$LOG" 2>&1 || OUTCOME=fail
    say "ticket \$TICKET : verdict remis (\$REVIEW_BEAD, \$OUTCOME)"
  fi
  gc bd update "\$REVIEW_BEAD" --set-metadata gc.outcome=\$OUTCOME --status=closed --notes "relecture \$OUTCOME" >/dev/null 2>&1
  gc bd update "\$BEAD" --set-metadata gc.outcome=\$OUTCOME --status=closed --notes "relecture \$OUTCOME" >/dev/null 2>&1
  gc runtime drain-ack >/dev/null 2>&1
  exit 0
done
STUB
chmod +x "$TRIAL/stub-reviewer"

# What the authors write: the criterion tests, their table, the code.
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
# Red at the start commit (the product answers 404 to a query string), and
# green on a product that never shows the count.
cat > "$TRIAL/tests/test_count_status_only.py" <<'PY'
import os
import unittest
import urllib.error
import urllib.request


class CountTest(unittest.TestCase):
    def test_count_is_shown(self):
        try:
            status = urllib.request.urlopen(os.environ["PRODUCT_ADDRESS"] + "/?count=1").status
        except urllib.error.HTTPError as error:
            status = error.code
        self.assertEqual(200, status)
PY
sed 's/?count=1/?count=2/' "$TRIAL/tests/test_count_status_only.py" > "$TRIAL/tests/test_count_status_again.py"
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

# --- the city: an author agent and a reviewer agent on their stubs, the real
# --- formulas, the real order ------------------------------------------------------
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

[providers.stub-reviewer]
base = "builtin:claude"
command = "$TRIAL/stub-reviewer"
process_names = ["stub-reviewer", "bash"]
ready_delay_ms = 0
TOML
mkdir -p "$CITY/agents/trial-author" "$CITY/agents/trial-reviewer" "$CITY/formulas" "$CITY/orders" \
  "$CITY/config/projects" "$CITY/config/project-descriptors" "$CITY/bin"
cat > "$CITY/agents/trial-author/agent.toml" <<'TOML'
description = "Author of the test-review trial (scripted stub, spends nothing)"
scope = "city"
min_active_sessions = 0
max_active_sessions = 3
TOML
query=$(grep '^work_query = ' "$ROOT/agents/delivery-author/agent.toml") || fail "the author agent declares no work_query"
printf '%s\n' "${query//-- delivery-author/-- trial-author}" >> "$CITY/agents/trial-author/agent.toml"
echo "Scripted author of the test-review trial." > "$CITY/agents/trial-author/prompt.template.md"
cat > "$CITY/agents/trial-reviewer/agent.toml" <<'TOML'
description = "Reviewer of the test-review trial (scripted stub, spends nothing)"
scope = "city"
min_active_sessions = 0
max_active_sessions = 2
provider = "stub-reviewer"
TOML
echo "Scripted reviewer of the test-review trial." > "$CITY/agents/trial-reviewer/prompt.template.md"
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
sling_target = "trial-author"
formulas = "mol-ticket-author,mol-test-review"
TOML
jq '.rigs = ["trial"]' "$ROOT/$FIXTURE/descriptor.json" > "$CITY/config/project-descriptors/trial.json"
jq -n --argjson n "$CEILING" '{contract: "agent-factory-delivery-flow/v1", max_sessions: $n,
  start: {formula: "mol-ticket-author", role: "author"},
  test_review: {formula: "mol-test-review", role: "reviewer", rig: "trial", timeout_seconds: 600}}' \
  > "$CITY/config/delivery-flow.json"
jq '.roles.author.agent = "trial-author" | .roles.reviewer.agent = "trial-reviewer"' "$ROOT/config/delivery-roles.json" \
  > "$CITY/config/delivery-roles.json"

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
A=$(new_ticket "ticket A, test corrigé après un refus")
B=$(new_ticket "ticket B, second refus")
C=$(new_ticket "ticket C, relecture sans résultat")
ALL=("$A" "$B" "$C")
declare -A NAME=([$A]=A [$B]=B [$C]=C)
echo corrects > "$TRIAL/mode.$A"; echo insists > "$TRIAL/mode.$B"; echo honest > "$TRIAL/mode.$C"
echo judges > "$TRIAL/reviewer.$A"; echo judges > "$TRIAL/reviewer.$B"; echo mute > "$TRIAL/reviewer.$C"
for t in "${ALL[@]}"; do
  gc bd dep add "$CONVOY" "$t" --type tracks >/dev/null
  gc bd update "$t" --set-metadata gc.ticket_kind=vertical_slice >/dev/null
done

echo "relevé d'essai — relecture des tests de critère avant le gel, cité isolée ($(gc version 2>/dev/null | head -1), N=$CEILING, aucun Mayor, auteur et relecteur scriptés, vraie porte de dispatch)"
echo "convoi $CONVOY (Spec $SPEC) : A=$A (corrige après un refus) B=$B (second refus) C=$C (relecteur sans verdict)"

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
  --demonstration-line "$C=La page d'accueil affiche le nombre d'éléments" \
  --user-stories "$A=1" --user-stories "$B=2" --user-stories "$C=3" >/dev/null
opened=$("$ROOT/bin/spec-integration" open "$CONVOY" --repo "$PRODUCT" --protected main) \
  || fail "spec-integration open did not pass: $opened"
echo "$(date -u +%H:%M:%S) marque posée, branche integration/$SPEC ouverte"

field() { gc bd show "$1" --json | jq -r --arg k "$2" '.[0].metadata[$k] // empty'; }
wait_for() { # <seconds> <command...>
  local deadline=$(( $(date +%s) + $1 )); shift
  until "$@"; do
    [ "$(date +%s)" -lt "$deadline" ] || return 1
    sleep 5
  done
}
step_seen() { grep -q "^$1 $2 " "$TRIAL/steps" 2>/dev/null; }
review_of() { field "$1" gc.flow.test_review; }
dump() { tail -40 "$TRIAL/author.log" >&2 || true; tail -20 "$TRIAL/reviewer.log" >&2 || true; tail -20 "$TRIAL/checks.log" >&2 || true; tail -3 "$TRIAL/passes.jsonl" >&2 || true; }
operator_list() { "$ROOT/bin/escalation-door" list 2>&1; }
on_list() { operator_list | sed -n '/^NEEDS BENJAMIN:/,/^Pending proposals/p' | grep -c "^  $1 — " || true; }

all_taken() { for t in "${ALL[@]}"; do step_seen "$t" workspace || return 1; done; }
wait_for 420 all_taken || { dump; fail "the three tickets were not all taken by an author session within 420s"; }
echo "$(date -u +%H:%M:%S) les trois tickets sont démarrés par l'ordre (bin/convoy-advance → bin/dispatch-door --role author)"

# --- A: refused once, corrected, reviewed again, frozen ---------------------------
a_first_refusal() { [ "$(review_of "$A" | jq -r '.rounds[0].verdict // empty' 2>/dev/null)" = unfavorable ]; }
wait_for 600 a_first_refusal || { dump; fail "the first review of A did not refuse its status-only test within 600s"; }
first=$(review_of "$A" | jq -c '.rounds[0]')
printf '%s' "$first" | jq -e '[.tests[] | select(.state == "unfavorable")] | length == 1 and (.[0].reason | test("statut 200"))' >/dev/null \
  || fail "the first review of A did not record one refusal with its reason: $first"
printf '%s' "$first" | jq -e '(.files | length) >= 3 and (.commit | length) == 40' >/dev/null \
  || fail "the first verdict of A is not bound to a commit and to fingerprints: $first"
a_frozen() { [ -n "$(field "$A" gc.flow.tdd.freeze)" ]; }
wait_for 600 a_frozen || { dump; fail "the corrected tests of A were not frozen within 600s"; }
rounds_a=$(review_of "$A" | jq -c '[.rounds[].verdict]')
[ "$rounds_a" = '["unfavorable","favorable"]' ] || fail "A does not carry a refusal then a favorable review: $rounds_a"
refused_commit=$(printf '%s' "$first" | jq -r '.commit')
frozen_commit=$(field "$A" gc.flow.tdd.freeze | jq -r '.commit')
[ "$frozen_commit" = "$(review_of "$A" | jq -r '.rounds[1].commit')" ] || fail "A was frozen at another commit than the one reviewed favorably"
[ "$frozen_commit" != "$refused_commit" ] || fail "A was frozen at the commit of the refused test"
wait_for 300 step_seen "$A" code || { dump; fail "the code step of A did not start after the freeze"; }
[ -z "$(field "$A" gc.flow.stop)" ] || fail "A is stopped"
[ "$(on_list "$A")" = 0 ] || fail "A is on the operator's list"
sessions_a=$(grep "^$A " "$TRIAL/review-sessions" | cut -d' ' -f3 | sort -u | wc -l | tr -d ' ')
echo "$(date -u +%H:%M:%S) A : première relecture = refus du test « statut 200 » avec sa raison, lié au commit $refused_commit ; gel refusé jusque-là ; test corrigé, seconde relecture favorable, gel au commit $frozen_commit ; étape de code démarrée ; $sessions_a sessions de relecteur distinctes"

# --- B: second refusal -> stopped, once on the operator's list ---------------------
b_stopped() { [ "$(field "$B" gc.flow.stop | jq -r '.reason // empty' 2>/dev/null)" = test_review_refused ]; }
wait_for 900 b_stopped || { dump; fail "B was not stopped by its second refusal within 900s"; }
b_raised() { [ "$(on_list "$B")" = 1 ]; }
wait_for 120 b_raised || { dump; fail "the stop of B is not exactly once on the operator's list: $(operator_list)"; }
[ "$(review_of "$B" | jq -c '[.rounds[].verdict]')" = '["unfavorable","unfavorable"]' ] || fail "B does not carry two refusals"
[ -z "$(field "$B" gc.flow.tdd.freeze)" ] || fail "the tests of B were frozen"
sleep 60
step_seen "$B" code && fail "the code step of B started although its tests were refused twice"
[ "$(on_list "$B")" = 1 ] || fail "B is not exactly once on the operator's list after later passes"
echo "$(date -u +%H:%M:%S) B : deux refus, ticket arrêté (test_review_refused), aucun gel, étape de code jamais démarrée ; une seule ligne sur la liste de la porte d'escalade : $(operator_list | grep "^  $B — " | head -1)"

# --- C: reviewer without verdict -> one relaunch, then stopped ---------------------
c_stopped() { [ "$(field "$C" gc.flow.stop | jq -r '.reason // empty' 2>/dev/null)" = test_review_no_result ]; }
wait_for 900 c_stopped || { dump; fail "C was not stopped after two reviews without result within 900s"; }
launches_c=$(grep -c "^$C " "$TRIAL/review-sessions" || true)
[ "$launches_c" = 2 ] || fail "the review of C was launched $launches_c times, not twice"
c_raised() { [ "$(on_list "$C")" = 1 ]; }
wait_for 120 c_raised || { dump; fail "the stop of C is not exactly once on the operator's list: $(operator_list)"; }
[ "$(review_of "$C" | jq -c '.rounds')" = '[]' ] || fail "C carries a verdict nobody gave"
[ -z "$(field "$C" gc.flow.tdd.freeze)" ] || fail "the tests of C were frozen"
step_seen "$C" code && fail "the code step of C started although its tests were never reviewed"
echo "$(date -u +%H:%M:%S) C : deux sessions de relecteur terminées sans verdict (une relance), ticket arrêté (test_review_no_result), aucun gel ; une seule ligne sur la liste : $(operator_list | grep "^  $C — " | head -1)"

gc session list --state all --json | jq -e '[.sessions[] | select(.template | test("mayor"))] | length == 0' >/dev/null \
  || fail "a Mayor session exists in the trial city"
echo "PASS: the criterion tests of each ticket were read by a reviewer session before the freeze, and code decided what followed"
