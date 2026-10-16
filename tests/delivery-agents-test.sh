#!/usr/bin/env bash
# T42 (af-rc0ozs, Spec af-wf4w5r §4 « N auteurs en parallèle », §5 « le rôle
# relecteur, session neuve »): what the delivered agents of the three delivery
# roles ask of Gas City.
#
#   - agents/delivery-author can run as many sessions as the ceiling N of
#     config/delivery-flow.json: a lower cap leaves a started ticket without
#     a session.
#   - The work query of each of the three agents is run here, as Gas City
#     runs it, on a fake tracker: a session that was never assigned a bead is
#     offered the unassigned work routed to its agent; a session that was
#     assigned one is offered only the unassigned work of the workflows it
#     already works, so the next review or evaluation goes to a new session.
#
# The isolated-city trial of the same ticket
# (tests/fresh-sessions-isolated-city-test.sh, local-only) shows the pool of
# Gas City following these settings.
set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

setting() { # <agent> <key>
  python3 - "$REPO_ROOT/agents/$1/agent.toml" "$2" <<'PY'
import sys
import tomllib

# The effective value: a city.toml patch of the agent (no dir) wins over its
# agent.toml, as Gas City resolves it (gc config show).
path, key = sys.argv[1], sys.argv[2]
agent = path.split("/agents/", 1)[1].split("/", 1)[0]
with open(path, "rb") as handle:
    value = tomllib.load(handle).get(key, "")
with open(path.split("/agents/", 1)[0] + "/city.toml", "rb") as handle:
    for patch in tomllib.load(handle).get("patches", {}).get("agent", []):
        if patch.get("name") == agent and "dir" not in patch and key in patch:
            value = patch[key]
print(value)
PY
}

CEILING=$(jq -r '.max_sessions' "$REPO_ROOT/config/delivery-flow.json")
cap=$(setting delivery-author max_active_sessions)
[ "$cap" = "$CEILING" ] \
  || fail "delivery-author runs at most $cap session(s) while N (config/delivery-flow.json max_sessions) is $CEILING"
# af-4xxlo7: one ceiling per delivery role. N above counts authors only;
# the verifier roles are capped by Gas City from their own agent.toml, which
# must say what config/delivery-flow.json says.
for pair in delivery-reviewer:max_reviewer_sessions delivery-evaluator:max_evaluator_sessions; do
  agent=${pair%%:*} key=${pair#*:}
  want=$(jq -r --arg k "$key" '.[$k]' "$REPO_ROOT/config/delivery-flow.json")
  case "$want" in ''|null|*[!0-9]*|0) fail "config/delivery-flow.json $key must be a positive integer, got '$want'" ;; esac
  cap=$(setting "$agent" max_active_sessions)
  [ "$cap" = "$want" ] || fail "$agent runs at most $cap session(s) while config/delivery-flow.json $key is $want"
done

# --- a fake tracker: what `bd` answers to the four reads of the query ------------
mkdir -p "$TMP/bin"
cat > "$TMP/bin/bd" <<'SH'
#!/bin/sh
echo "$*" >> "$FAKE_BD_CALLS"
case "$*" in
  "list --status in_progress --assignee="*) echo "[]" ;;
  "ready --assignee="*) echo "[]" ;;
  "list --all --assignee=$FAKE_SESSION --json --limit=0") cat "$FAKE_BD_ASSIGNED" ;;
  "list --all --assignee=shared-alias --metadata-field gc.session_id=$FAKE_SESSION --json --limit=0") cat "$FAKE_BD_ALIAS_CURRENT" ;;
  "list --all --assignee=shared-alias --json --limit=0") echo '[{"id":"fx-other","metadata":{"gc.root_bead_id":"fx-other-root"}}]' ;;
  "list --all --assignee="*) echo "[]" ;;
  "ready --metadata-field gc.routed_to="*" --unassigned "*) cat "$FAKE_BD_READY" ;;
  *) echo "unexpected bd call: $*" >&2; exit 2 ;;
esac
SH
chmod +x "$TMP/bin/bd"
export FAKE_BD_CALLS="$TMP/calls" FAKE_BD_ASSIGNED="$TMP/assigned.json" FAKE_BD_READY="$TMP/ready.json" FAKE_SESSION="fx-s1" FAKE_BD_ALIAS_CURRENT="$TMP/alias.json"
echo "[]" > "$FAKE_BD_ALIAS_CURRENT"
cat > "$FAKE_BD_READY" <<'JSON'
[{"id": "fx-next", "metadata": {"gc.root_bead_id": "fx-root-next"}},
 {"id": "fx-mine", "metadata": {"gc.root_bead_id": "fx-root-served"}}]
JSON

offered() { # <agent>: the bead ids the work query offers the session fx-s1
  : > "$FAKE_BD_CALLS"
  out=$(PATH="$TMP/bin:$PATH" GC_SESSION_ID="$FAKE_SESSION" GC_SESSION_NAME="" GC_ALIAS="shared-alias" sh -c "$(setting "$1" work_query)") \
    || fail "the work query of $1 failed: $out"
  grep -qF -- "gc.routed_to=$1 " "$FAKE_BD_CALLS" || fail "the work query of $1 does not ask for the work routed to $1"
  printf '%s' "$out" | jq -c '[.[].id]'
}

for agent in delivery-author delivery-reviewer delivery-evaluator; do
  [ -n "$(setting "$agent" work_query)" ] || fail "$agent has no work query: any of its sessions is offered any work of the role"

  # A fresh session stays eligible despite another session sharing its alias.
  echo "[]" > "$FAKE_BD_ASSIGNED"
  fresh=$(offered "$agent")
  [ "$fresh" = '["fx-next","fx-mine"]' ] || fail "a session of $agent that never served is not offered the routed work: $fresh"

  echo '[{"id": "fx-done", "status": "closed", "metadata": {"gc.root_bead_id": "fx-root-served"}}]' > "$FAKE_BD_ASSIGNED"
  served=$(offered "$agent")
  [ "$served" = '["fx-mine"]' ] \
    || fail "a session of $agent that already served is offered the work of another workflow: $served"

  # Conversely, this session's own alias-assigned work still binds its workflow.
  echo "[]" > "$FAKE_BD_ASSIGNED"
  echo '[{"id":"fx-own-alias","metadata":{"gc.root_bead_id":"fx-root-served"}}]' > "$FAKE_BD_ALIAS_CURRENT"
  served=$(offered "$agent")
  [ "$served" = '["fx-mine"]' ] || fail "own alias history is lost for $agent: $served"
  echo "[]" > "$FAKE_BD_ALIAS_CURRENT"
done

echo "PASS: delivery-author is capped at N=$CEILING, and a session of a delivery role that served is offered no other workflow"
