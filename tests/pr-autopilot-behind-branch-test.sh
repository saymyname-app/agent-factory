#!/usr/bin/env bash
#
# af-s6lef (P04): pr-autopilot used to arm auto-merge on any open PR
# regardless of mergeStateStatus -- GitHub happily accepts the arm request
# on a BEHIND PR and, on a non-strict ruleset (before P05 flips it), would
# merge it without the base's latest required check ever running against
# that branch. This drives pr-autopilot against two BEHIND PRs on
# agent-factory and proves:
#  1. neither BEHIND PR is armed for auto-merge;
#  2. one tick updates exactly the oldest (lowest numbered) BEHIND PR, not
#     the other, through the REST endpoint (`gh api -X PUT
#     repos/{repo}/pulls/{num}/update-branch`);
#  3. once a PR catches up (no longer BEHIND) and its required check is
#     green, the next tick arms it;
#  4. a failed update-branch is logged with gh's own error line, does not
#     add a run error (order.failed), and the same PR is retried (not
#     silently dropped) on the next tick;
#  5. (af-jaimhb) a BEHIND PR is waiting, not stuck: neither the one being
#     updated nor the ones queued behind it are marked or get a bug bead,
#     even on a second pass; only a branch update GitHub refuses is marked,
#     then filed on the next refusal, with GitHub's answer in the bead.
#
# Regression (2026-09-29): pr-autopilot called `gh pr update-branch`, which
# the installed gh 2.45 does not have. This test's fake gh used to accept that
# nonexistent subcommand, so it passed while every real BEHIND tick failed.
# The fake now behaves like gh 2.45: `pr update-branch` is an unknown command.

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
 {"number":11,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BEHIND","statusCheckRollup":[{"name":"Tests","conclusion":"SUCCESS"}],"headRefOid":"af11","labels":[]},
 {"number":10,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BEHIND","statusCheckRollup":[{"name":"Tests","conclusion":"SUCCESS"}],"headRefOid":"af10","labels":[]}
]
JSON

# gh stub: `api -X PUT repos/<repo>/pulls/<num>/update-branch` flips that
# PR's mergeStateStatus in the fixture from BEHIND to CLEAN (simulating
# GitHub catching the branch up), unless FAIL_UPDATE names that PR number, in
# which case it fails like a real 422 and the fixture is left untouched
# (never silently marked done). `pr update-branch` is rejected exactly like
# gh 2.45 rejects it (unknown command), so the regression cannot come back.
cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ \$1 == pr && \$2 == update-branch ]]; then
  echo 'unknown command "update-branch" for "gh pr"' >&2
  exit 1
fi
if [[ \$1 == api && \$2 == -X && \$3 == PUT && \$4 == repos/*/pulls/*/update-branch ]]; then
  num=\${4%/update-branch}; num=\${num##*/}
  if [[ "\${FAIL_UPDATE:-}" == "\$num" ]]; then
    echo '{"message":"merge conflict between base and head"}'
    echo 'gh: merge conflict between base and head (HTTP 422)' >&2
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
  echo '{"message":"Updating pull request branch.","url":"x"}'
  exit 0
fi
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
export GC_PR_AUTHORS=example-operator
export REVERSIBILITY_CHECK_BIN="$TMP/bin/gh"

pilot() { "$AUTOPILOT" "$@" 2>&1 || true; }

# --- tick 1: both PRs BEHIND -> only the oldest (#10) is updated ---
out=$(pilot)
grep -qF "api -X PUT repos/saymyname-app/agent-factory/pulls/10/update-branch -f expected_head_sha=af10" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "oldest BEHIND PR #10 was not updated on tick 1"; }
grep -qF "/pulls/11/update-branch" "$TMP/gh.log" \
  && { echo "$out" >&2; fail "PR #11 was updated on tick 1 before its turn"; }
grep -q "^pr merge 10 " "$TMP/gh.log" && { echo "$out" >&2; fail "BEHIND PR #10 was armed for auto-merge"; }
grep -q "^pr merge 11 " "$TMP/gh.log" && { echo "$out" >&2; fail "BEHIND PR #11 was armed for auto-merge"; }

# --- tick 2: #10 caught up (CLEAN, green) -> armed; #11 still BEHIND -> updated ---
: > "$TMP/gh.log"
out=$(pilot)
grep -q "^pr merge 10 --repo saymyname-app/agent-factory --auto --squash --delete-branch" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #10 (caught up, checks green) was not armed on tick 2"; }
grep -qF "api -X PUT repos/saymyname-app/agent-factory/pulls/11/update-branch" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #11 was not updated on tick 2 once it was its turn"; }
grep -q "^pr merge 11 " "$TMP/gh.log" && { echo "$out" >&2; fail "PR #11 was armed while still BEHIND"; }

# --- retry: an update-branch failure is logged and retried next tick ---
cat > "$TMP/af_open.json" <<'JSON'
[
 {"number":20,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BEHIND","statusCheckRollup":[{"name":"Tests","conclusion":"SUCCESS"}],"headRefOid":"af20","labels":[]}
]
JSON
: > "$TMP/gh.log"
export FAIL_UPDATE=20
out=$(pilot)
printf '%s\n' "$out" | grep -qF "PR #20: BEHIND base -> updating branch" \
  || { echo "$out" >&2; fail "PR #20's update attempt was not logged"; }
printf '%s\n' "$out" | grep -qF "branch update failed: gh: merge conflict between base and head (HTTP 422)" \
  || { echo "$out" >&2; fail "PR #20's update-branch failure was not logged with gh's error"; }
# The fixture has no backend/frontend rig dirs, so each "SKIP: ... missing"
# is one legitimate error; the failed branch update must add none on top.
missing=$(printf '%s\n' "$out" | grep -c "SKIP: .* missing" || true)
printf '%s\n' "$out" | grep -qE "(^| )errors=$missing( |$)" \
  || { echo "$out" >&2; fail "one PR's failed branch update was counted as a run error (order.failed every tick)"; }
grep -qF "api -X PUT repos/saymyname-app/agent-factory/pulls/20/update-branch" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #20's update-branch was not attempted"; }

: > "$TMP/gh.log"
unset FAIL_UPDATE
out=$(pilot)
grep -qF "api -X PUT repos/saymyname-app/agent-factory/pulls/20/update-branch" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #20 was not retried on the next tick after the failed update"; }

grep -q "^pr update-branch" "$TMP/gh.log" && fail "pr-autopilot called 'gh pr update-branch' (absent from gh 2.45)"

# --- af-jaimhb: a queue of BEHIND PRs is a wait, never a bug bead ---
# 2026-10-09: with one CI job at a time, every merge left the queued PRs
# BEHIND again; the first pass labelled them all and updated the oldest, the
# second pass filed a bead for each of the others (27 beads for 17 PRs).
# PR 31 carries the label an earlier pass left: under that rule it is filed.
cat > "$TMP/af_open.json" <<'JSON'
[
 {"number":30,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BEHIND","statusCheckRollup":[{"name":"Tests","conclusion":"SUCCESS"}],"headRefOid":"af30","labels":[]},
 {"number":31,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BEHIND","statusCheckRollup":[{"name":"Tests","conclusion":"SUCCESS"}],"headRefOid":"af31","labels":[{"name":"autopilot-stuck"}]},
 {"number":32,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BEHIND","statusCheckRollup":[{"name":"Tests","conclusion":"SUCCESS"}],"headRefOid":"af32","labels":[]}
]
JSON
: > "$TMP/gh.log"; : > "$TMP/gc.log"
out=$(pilot)
grep -qF "/pulls/30/update-branch" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #30 (oldest of the queue) was not updated"; }
grep -q "^bd create" "$TMP/gc.log" \
  && { echo "$out" >&2; cat "$TMP/gc.log" >&2; fail "a bug bead was filed for a BEHIND PR waiting its turn"; }
grep -q "^pr comment 3[012] " "$TMP/gh.log" \
  && { echo "$out" >&2; fail "a waiting BEHIND PR was commented as needing attention"; }
grep -qE "^api -X POST repos/[^ ]*/issues/3[02]/labels -f labels\[\]=autopilot-stuck" "$TMP/gh.log" \
  && { echo "$out" >&2; fail "a BEHIND PR being updated or waiting its turn was marked stuck"; }

# --- af-jaimhb: a refused update is marked first, filed on the next refusal ---
cat > "$TMP/af_open.json" <<'JSON'
[
 {"number":40,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BEHIND","statusCheckRollup":[{"name":"Tests","conclusion":"SUCCESS"}],"headRefOid":"af40","labels":[]}
]
JSON
: > "$TMP/gh.log"; : > "$TMP/gc.log"
export FAIL_UPDATE=40
out=$(pilot)
grep -q "^api -X POST repos/saymyname-app/agent-factory/issues/40/labels -f labels\[\]=autopilot-stuck" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #40 (branch update refused) was not marked on the first refusal"; }
grep -q "^bd create" "$TMP/gc.log" && { echo "$out" >&2; fail "PR #40 was filed on its first refused update"; }

cat > "$TMP/af_open.json" <<'JSON'
[
 {"number":40,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BEHIND","statusCheckRollup":[{"name":"Tests","conclusion":"SUCCESS"}],"headRefOid":"af40","labels":[{"name":"autopilot-stuck"}]}
]
JSON
: > "$TMP/gh.log"; : > "$TMP/gc.log"
out=$(pilot)
grep -qF "bd create [autopilot] PR #40 stuck: behind base, branch update refused" "$TMP/gc.log" \
  || { echo "$out" >&2; cat "$TMP/gc.log" >&2; fail "PR #40 (update refused on a second pass) did not file a bead"; }
grep -qF "merge conflict between base and head (HTTP 422)" "$TMP/gc.log" \
  || { cat "$TMP/gc.log" >&2; fail "the bead does not carry GitHub's answer to the refused update"; }
[ "$(grep -c "^bd create" "$TMP/gc.log")" = 1 ] || fail "more than one bead for PR #40"

# The same marked PR, once GitHub accepts the update: nothing is filed.
: > "$TMP/gh.log"; : > "$TMP/gc.log"
unset FAIL_UPDATE
out=$(pilot)
grep -q "^bd create" "$TMP/gc.log" \
  && { echo "$out" >&2; fail "PR #40 was filed although its branch update went through"; }

echo "OK pr-autopilot updates BEHIND PRs one at a time, oldest first, never arms one, and files a bead only for a refused update"
