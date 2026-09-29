#!/usr/bin/env bash
#
# af-s6lef (P04): pr-autopilot used to arm auto-merge on any open PR
# regardless of mergeStateStatus -- GitHub happily accepts the arm request
# on a BEHIND PR and, on a non-strict ruleset (before P05 flips it), would
# merge it without the base's latest required check ever running against
# that branch. This drives pr-autopilot against two BEHIND PRs on
# agent-factory and proves:
#  1. neither BEHIND PR is armed for auto-merge;
#  2. one tick calls `gh pr update-branch` on exactly the oldest (lowest
#     numbered) BEHIND PR, not the other;
#  3. once a PR catches up (no longer BEHIND) and its required check is
#     green, the next tick arms it;
#  4. a failed update-branch is logged and the same PR is retried (not
#     silently dropped) on the next tick.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory" "$TMP/bin"
: > "$TMP/gh.log"; : > "$TMP/gc.log"

# PR 10 and 11: both agent-factory, both BEHIND base, both green on "Tests".
# 10 is the older (lower-numbered) PR.
cat > "$TMP/af_open.json" <<'JSON'
[
 {"number":11,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BEHIND","statusCheckRollup":[{"name":"Tests","conclusion":"SUCCESS"}],"headRefOid":"af11","labels":[]},
 {"number":10,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BEHIND","statusCheckRollup":[{"name":"Tests","conclusion":"SUCCESS"}],"headRefOid":"af10","labels":[]}
]
JSON

# gh stub: `pr update-branch <num>` flips that PR's mergeStateStatus in the
# fixture from BEHIND to CLEAN (simulating GitHub catching the branch up),
# unless FAIL_UPDATE names that PR number, in which case it fails instead
# and the fixture is left untouched (never silently marked done).
cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ \$1 == api ]] && [[ "\$*" == *"rules/branches"* ]]; then
  case "\$*" in
    *"saymyname-app/agent-factory"*) echo '["Tests"]' ;;
    *)                                echo '[]' ;;
  esac
  exit 0
fi
if [[ \$1 == pr && \$2 == list ]]; then
  if [[ "\$*" == *"--state merged"* ]]; then echo '[]'; exit 0; fi
  case "\$*" in
    *"saymyname-app/agent-factory"*) cat "$TMP/af_open.json" ;;
    *)                                echo '[]' ;;
  esac
  exit 0
fi
if [[ \$1 == pr && \$2 == update-branch ]]; then
  num=\$3
  if [[ "\${FAIL_UPDATE:-}" == "\$num" ]]; then
    exit 1
  fi
  python3 - "$TMP/af_open.json" "\$num" <<'PY'
import json, sys
path, num = sys.argv[1], int(sys.argv[2])
with open(path) as f:
    prs = json.load(f)
for pr in prs:
    if pr["number"] == num:
        pr["mergeStateStatus"] = "CLEAN"
with open(path, "w") as f:
    json.dump(prs, f)
PY
  exit 0
fi
if [[ \$1 == pr && \$2 == view ]]; then echo '["OPEN","false"]' | jq -r '@tsv'; exit 0; fi
if [[ \$1 == run && \$2 == list ]]; then echo ''; exit 0; fi
exit 0
STUB
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gc.log"
if [[ \$1 == bd && \$2 == list ]]; then echo '[]'; exit 0; fi
exit 0
STUB
chmod +x "$TMP/bin/"*
export PATH="$TMP/bin:$PATH"
export FACTORY_ROOT="$TMP/factory"
export REVERSIBILITY_CHECK_BIN="$TMP/bin/gh"

pilot() { "$AUTOPILOT" "$@" 2>&1 || true; }

# --- tick 1: both PRs BEHIND -> only the oldest (#10) is updated ---
out=$(pilot)
grep -qF "pr update-branch 10 --repo saymyname-app/agent-factory" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "oldest BEHIND PR #10 was not updated on tick 1"; }
grep -qF "pr update-branch 11 " "$TMP/gh.log" \
  && { echo "$out" >&2; fail "PR #11 was updated on tick 1 before its turn"; }
grep -q "^pr merge 10 " "$TMP/gh.log" && { echo "$out" >&2; fail "BEHIND PR #10 was armed for auto-merge"; }
grep -q "^pr merge 11 " "$TMP/gh.log" && { echo "$out" >&2; fail "BEHIND PR #11 was armed for auto-merge"; }

# --- tick 2: #10 caught up (CLEAN, green) -> armed; #11 still BEHIND -> updated ---
: > "$TMP/gh.log"
out=$(pilot)
grep -q "^pr merge 10 --repo saymyname-app/agent-factory --auto --squash --delete-branch" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #10 (caught up, checks green) was not armed on tick 2"; }
grep -qF "pr update-branch 11 --repo saymyname-app/agent-factory" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #11 was not updated on tick 2 once it was its turn"; }
grep -q "^pr merge 11 " "$TMP/gh.log" && { echo "$out" >&2; fail "PR #11 was armed while still BEHIND"; }

# --- retry: an update-branch failure is logged and retried next tick ---
cat > "$TMP/af_open.json" <<'JSON'
[
 {"number":20,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BEHIND","statusCheckRollup":[{"name":"Tests","conclusion":"SUCCESS"}],"headRefOid":"af20","labels":[]}
]
JSON
: > "$TMP/gh.log"
export FAIL_UPDATE=20
out=$(pilot)
printf '%s\n' "$out" | grep -qF "PR #20: BEHIND base -> updating branch" \
  || { echo "$out" >&2; fail "PR #20's update attempt was not logged"; }
printf '%s\n' "$out" | grep -qF "branch update failed -- will retry next tick" \
  || { echo "$out" >&2; fail "PR #20's update-branch failure was not logged"; }
grep -qF "pr update-branch 20 --repo saymyname-app/agent-factory" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #20's update-branch was not attempted"; }

: > "$TMP/gh.log"
unset FAIL_UPDATE
out=$(pilot)
grep -qF "pr update-branch 20 --repo saymyname-app/agent-factory" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #20 was not retried on the next tick after the failed update"; }

echo "OK pr-autopilot updates BEHIND PRs one at a time, oldest first, and never arms auto-merge on one"
