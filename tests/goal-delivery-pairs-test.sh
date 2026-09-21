#!/usr/bin/env bash
#
# bin/goal-delivery-pairs: the deterministic query for every (repo, PR)
# delivery pair a cross-rig goal shipped, given that ADR-0016's six proof
# fields fit only one pair per bead (af-kidv). Modeled on the real af-7700
# shape: the goal bead mirrors the backend pair (PR #39), the frontend pair
# (PR #50) lives only on a `gc.goal`-linked child bead in another rig.
#
# All bead ids here are synthetic fixtures (zz-fixture*), never a real af-*
# id from the live store.
set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SCRIPT="$REPO_ROOT/bin/goal-delivery-pairs"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

export GOAL_FILE="$TMP/goal.json"
export CITY_FILE="$TMP/city.json"
export BACKEND_FILE="$TMP/backend.json"
export FRONTEND_FILE="$TMP/frontend.json"
mkdir -p "$TMP/bin"

# --- stub gc: serves `bd show`, `rig list`, and `bd [--rig X] list
# --metadata-field gc.goal=...` from fixture files -----------------------
cat > "$TMP/bin/gc" <<'STUB'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ ${1:-} == bd && ${2:-} == show ]]; then
  cat "$GOAL_FILE"
  exit 0
fi
if [[ ${1:-} == rig && ${2:-} == list ]]; then
  cat <<'RIGS'
{"rigs":[{"name":"agent-factory","hq":true},{"name":"zz-backend","hq":false},{"name":"zz-frontend","hq":false}]}
RIGS
  exit 0
fi
if [[ ${1:-} == bd && ${2:-} == --rig ]]; then
  rig=$3
  case "$rig" in
    zz-backend) cat "$BACKEND_FILE" ;;
    zz-frontend) cat "$FRONTEND_FILE" ;;
    *) echo '[]' ;;
  esac
  exit 0
fi
if [[ ${1:-} == bd && ${2:-} == list ]]; then
  cat "$CITY_FILE"
  exit 0
fi
echo "unexpected gc invocation: $*" >&2
exit 2
STUB
chmod +x "$TMP/bin/gc"
export PATH="$TMP/bin:$PATH"
export GC_BIN=gc
export FACTORY_ROOT="$REPO_ROOT"

# --- fixture: goal bead mirrors the backend pair, closed+delivered -------
cat > "$GOAL_FILE" <<'JSON'
[{"id":"zz-fixturegoal","status":"closed",
  "metadata":{"gc.delivery_status":"merged","gc.work_outcome":"shipped",
    "gc.github_repo":"acme/backend","gc.pr_number":39,
    "gc.pr_head":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "gc.merge_commit":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}}]
JSON

# --- fixture: no gc.goal-linked children in the city itself --------------
echo '[]' > "$CITY_FILE"

# --- fixture: the backend rig's own child mirrors the same pair ----------
cat > "$BACKEND_FILE" <<'JSON'
[{"id":"zz-fixturebackend",
  "metadata":{"gc.goal":"zz-fixturegoal","gc.delivery_status":"merged",
    "gc.github_repo":"acme/backend","gc.pr_number":39,
    "gc.pr_head":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "gc.merge_commit":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}}]
JSON

# --- fixture: the frontend rig's child carries the second, distinct pair -
cat > "$FRONTEND_FILE" <<'JSON'
[{"id":"zz-fixturefrontend",
  "metadata":{"gc.goal":"zz-fixturegoal","gc.delivery_status":"merged",
    "gc.github_repo":"acme/frontend","gc.pr_number":50,
    "gc.pr_head":"cccccccccccccccccccccccccccccccccccccccc",
    "gc.merge_commit":"dddddddddddddddddddddddddddddddddddddddd"}}]
JSON

out=$("$SCRIPT" zz-fixturegoal --json)
pairs=$(jq 'length' <<<"$out")
[ "$pairs" = "2" ] || fail "expected 2 deduped pairs, got $pairs: $out"

backend_seen=$(jq '[.[] | select(.github_repo == "acme/backend" and .pr_number == 39)] | length' <<<"$out")
[ "$backend_seen" = "1" ] || fail "expected the backend pair exactly once (goal + child dedup): $out"

frontend_seen=$(jq '[.[] | select(.github_repo == "acme/frontend" and .pr_number == 50)] | length' <<<"$out")
[ "$frontend_seen" = "1" ] || fail "expected the frontend pair from the sibling rig's child: $out"

text_out=$("$SCRIPT" zz-fixturegoal)
grep -q 'acme/backend#39' <<<"$text_out" || fail "text output missing backend pair: $text_out"
grep -q 'acme/frontend#50' <<<"$text_out" || fail "text output missing frontend pair: $text_out"

# --- a goal with no delivered pairs yet: empty result, exit 0 ------------
cat > "$GOAL_FILE" <<'JSON'
[{"id":"zz-fixturegoal","status":"open","metadata":{}}]
JSON
echo '[]' > "$BACKEND_FILE"
echo '[]' > "$FRONTEND_FILE"
empty_out=$("$SCRIPT" zz-fixturegoal --json)
[ "$empty_out" = "[]" ] || fail "expected an empty array for an undelivered goal, got: $empty_out"

echo "PASS: goal-delivery-pairs"
