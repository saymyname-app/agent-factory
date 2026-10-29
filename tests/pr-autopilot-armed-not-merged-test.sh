#!/usr/bin/env bash
#
# af-n8gft2: an armed PR whose required check is green on its head and whose
# merge state is CLEAN can stay open -- GitHub's auto-merge did not fire on
# PR #479 for 17 minutes (2026-10-09) while `gh pr merge --squash` merged it
# at once. pr-autopilot read "auto-merge already armed" and moved on, every
# 3 minutes. This drives pr-autopilot against armed and newly armed PRs on
# agent-factory and proves:
#  1. armed, CLEAN, required check green for longer than the delay -> one
#     direct squash merge pinned to the head that was read, never `--auto`;
#  2. the same PR green for less than the delay is left to GitHub;
#  3. an armed PR that is not CLEAN, or whose required check is not green, or
#     whose check carries no completion time, is never merged directly;
#  4. a non-zero exit of the direct merge is never retried: the server state
#     is re-read once. MERGED there is a merge (no run error); still OPEN is
#     one run error, with a single merge call;
#  5. --dry-run names the merge and calls nothing;
#  6. a zero exit from an arm request is verified on GitHub: OPEN/null with
#     the same head, CLEAN state and green required check takes the pinned
#     direct path; an unknown read, moved head, non-green check or non-CLEAN
#     state never does.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory" "$TMP/bin"
: > "$TMP/gh.log"; : > "$TMP/gc.log"

NOW=1791558000
at() { date -u -d "@$((NOW - $1))" +%Y-%m-%dT%H:%M:%SZ; }
ARMED_JSON='{"mergeMethod":"SQUASH","enabledAt":"2026-10-09T14:23:49Z"}'
REPO=saymyname-app/agent-factory

# 30: green for 17 min, CLEAN -> merged.          31: green for 1 min -> GitHub's turn.
# 32: required check still running (BLOCKED).     33: green, CLEAN, merge exits 1 but merged.
# 34: green, CLEAN, merge exits 1 and still open. 35: green, CLEAN, no completion time.
# 36: an unrelated check is the old green one; the required one is 1 min old.
# 37: arm exits 0 but is absent server-side -> direct merge. 38: head moved.
# 39: post-arm check is pending. 40: post-arm state is DIRTY. 41: re-read fails.
# 42: arm exits 0 and is confirmed server-side.
cat > "$TMP/af_open.json" <<JSON
[
 {"number":30,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":$ARMED_JSON,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Tests","status":"COMPLETED","conclusion":"SUCCESS","completedAt":"$(at 1020)"}],"headRefOid":"af30","labels":[]},
 {"number":31,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":$ARMED_JSON,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Tests","status":"COMPLETED","conclusion":"SUCCESS","completedAt":"$(at 60)"}],"headRefOid":"af31","labels":[]},
 {"number":32,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":$ARMED_JSON,"mergeStateStatus":"BLOCKED","statusCheckRollup":[{"name":"Tests","status":"IN_PROGRESS","conclusion":"","completedAt":"0001-01-01T00:00:00Z"}],"headRefOid":"af32","labels":[]},
 {"number":33,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":$ARMED_JSON,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Tests","status":"COMPLETED","conclusion":"SUCCESS","completedAt":"$(at 1020)"}],"headRefOid":"af33","labels":[]},
 {"number":34,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":$ARMED_JSON,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Tests","status":"COMPLETED","conclusion":"SUCCESS","completedAt":"$(at 1020)"}],"headRefOid":"af34","labels":[]},
 {"number":35,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":$ARMED_JSON,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Tests","status":"COMPLETED","conclusion":"SUCCESS"}],"headRefOid":"af35","labels":[]},
 {"number":36,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":$ARMED_JSON,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Lint","status":"COMPLETED","conclusion":"SUCCESS","completedAt":"$(at 1020)"},{"name":"Tests","status":"COMPLETED","conclusion":"SUCCESS","completedAt":"$(at 60)"}],"headRefOid":"af36","labels":[]},
 {"number":37,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Tests","status":"COMPLETED","conclusion":"SUCCESS","completedAt":"$(at 60)"}],"headRefOid":"af37","labels":[]},
 {"number":38,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Tests","status":"COMPLETED","conclusion":"SUCCESS","completedAt":"$(at 60)"}],"headRefOid":"af38","labels":[]},
 {"number":39,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Tests","status":"COMPLETED","conclusion":"SUCCESS","completedAt":"$(at 60)"}],"headRefOid":"af39","labels":[]},
 {"number":40,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Tests","status":"COMPLETED","conclusion":"SUCCESS","completedAt":"$(at 60)"}],"headRefOid":"af40","labels":[]},
 {"number":41,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Tests","status":"COMPLETED","conclusion":"SUCCESS","completedAt":"$(at 60)"}],"headRefOid":"af41","labels":[]},
 {"number":42,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Tests","status":"COMPLETED","conclusion":"SUCCESS","completedAt":"$(at 60)"}],"headRefOid":"af42","labels":[]}
]
JSON

# gh stub: `pr merge` exits 1 for PR 33 and 34 (33 is nevertheless merged
# server-side, as when gh cannot delete a branch a worktree still pins);
# `pr view --json state` answers MERGED for 33 and OPEN for the others.
cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ \$1 == api ]] && [[ "\$*" == *"rules/branches"* ]]; then
  case "\$*" in
    *"$REPO"*) echo '["Tests"]' ;;
    *)         echo '[]' ;;
  esac
  exit 0
fi
if [[ \$1 == pr && \$2 == list ]]; then
  if [[ "\$*" == *"--state merged"* ]]; then echo '[]'; exit 0; fi
  case "\$*" in
    *"$REPO"*) cat "$TMP/af_open.json" ;;
    *)         echo '[]' ;;
  esac
  exit 0
fi
if [[ \$1 == pr && \$2 == merge ]]; then
  case "\$3" in 33|34) exit 1 ;; esac
  exit 0
fi
if [[ \$1 == pr && \$2 == view ]]; then
  if [[ "\$*" == *"--json state,autoMergeRequest,mergeStateStatus,statusCheckRollup,headRefOid"* ]]; then
    case "\$3" in
      37) printf '%s\n' '{"state":"OPEN","autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Tests","status":"COMPLETED","conclusion":"SUCCESS"}],"headRefOid":"af37"}' ;;
      38) printf '%s\n' '{"state":"OPEN","autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Tests","status":"COMPLETED","conclusion":"SUCCESS"}],"headRefOid":"af38-moved"}' ;;
      39) printf '%s\n' '{"state":"OPEN","autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Tests","status":"IN_PROGRESS","conclusion":""}],"headRefOid":"af39"}' ;;
      40) printf '%s\n' '{"state":"OPEN","autoMergeRequest":null,"mergeStateStatus":"DIRTY","statusCheckRollup":[{"name":"Tests","status":"COMPLETED","conclusion":"SUCCESS"}],"headRefOid":"af40"}' ;;
      41) exit 1 ;;
      42) printf '%s\n' '{"state":"OPEN","autoMergeRequest":{"mergeMethod":"SQUASH"},"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Tests","status":"COMPLETED","conclusion":"SUCCESS"}],"headRefOid":"af42"}' ;;
    esac
    exit 0
  fi
  case "\$3" in 33) echo MERGED ;; *) echo OPEN ;; esac
  exit 0
fi
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
export PR_AUTOPILOT_NOW_EPOCH=$NOW
export PR_AUTOPILOT_RECONCILE_CACHE="$TMP/reconciled.tsv"

pilot() { "$AUTOPILOT" "$@" 2>&1 || true; }
merges_of() { grep -c "^pr merge $1 " "$TMP/gh.log" || true; }

# --- dry run: named, nothing called ---
out=$(pilot --dry-run)
grep -qF "DRY-RUN: gh pr merge 30 --repo $REPO --squash --match-head-commit af30" <<<"$out" \
  || { echo "$out" >&2; fail "--dry-run did not name the direct merge of PR #30"; }
grep -q "^pr merge " "$TMP/gh.log" && { echo "$out" >&2; fail "--dry-run called gh pr merge"; }

# --- one tick ---
: > "$TMP/gh.log"
out=$(pilot)

# 1. armed, CLEAN, green for 17 min -> one direct squash merge on that head.
grep -qxF "pr merge 30 --repo $REPO --squash --match-head-commit af30" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "armed, green, CLEAN PR #30 still open after the delay was not merged directly"; }
[ "$(merges_of 30)" = 1 ] || { echo "$out" >&2; fail "PR #30 got $(merges_of 30) merge calls, expected 1"; }
grep -qF "PR #30: armed, required check green for 1020s, CLEAN, still open -> direct squash merge" <<<"$out" \
  || { echo "$out" >&2; fail "PR #30's direct merge was not logged with its reason"; }
if grep -qE '^pr merge (30|31|32|33|34|35|36) .*--auto' "$TMP/gh.log"; then
  echo "$out" >&2
  fail "an already armed PR was armed again"
fi

# 2. green for less than the delay -> GitHub's turn.
[ "$(merges_of 31)" = 0 ] || { echo "$out" >&2; fail "PR #31 (green for 60s) was merged before the delay"; }
# 3. not CLEAN / check running / no completion time / only another check is old.
[ "$(merges_of 32)" = 0 ] || { echo "$out" >&2; fail "PR #32 (BLOCKED, check running) was merged"; }
[ "$(merges_of 35)" = 0 ] || { echo "$out" >&2; fail "PR #35 (no completion time) was merged on a guess"; }
[ "$(merges_of 36)" = 0 ] || { echo "$out" >&2; fail "PR #36 was merged on the age of a check that is not the required one"; }

# 4. non-zero exit: never retried, server state re-read once.
[ "$(merges_of 33)" = 1 ] || { echo "$out" >&2; fail "PR #33 got $(merges_of 33) merge calls after a non-zero exit, expected 1"; }
grep -q "^pr view 33 --repo $REPO --json state" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #33's server state was not re-read after the non-zero exit"; }
[ "$(merges_of 34)" = 1 ] || { echo "$out" >&2; fail "PR #34 got $(merges_of 34) merge calls after a non-zero exit, expected 1"; }
grep -qF "direct merge failed" <<<"$out" \
  || { echo "$out" >&2; fail "PR #34's refused direct merge was not logged"; }
# The fixture has no backend/frontend rig dirs: each "SKIP: ... missing" is
# one legitimate error. PR 34 adds exactly one; PR 33 (merged) adds none.
missing=$(grep -c "SKIP: .* missing" <<<"$out" || true)
grep -qE "(^| )errors=$((missing + 1))( |$)" <<<"$out" \
  || { echo "$out" >&2; fail "expected errors=$((missing + 1)): one for PR #34 still open, none for PR #33 merged server-side"; }

# 6. A successful local arm is only a request: verify the resulting state.
grep -qxF "pr merge 37 --repo $REPO --auto --squash" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #37's auto-merge request is missing"; }
grep -qxF "pr merge 37 --repo $REPO --squash --match-head-commit af37" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #37 stayed OPEN/null after a successful arm but did not take the pinned direct path"; }
[ "$(merges_of 37)" = 2 ] || { echo "$out" >&2; fail "PR #37 got $(merges_of 37) merge calls, expected one arm and one direct merge"; }

for num in 38 39 40 41 42; do
  [ "$(merges_of "$num")" = 1 ] \
    || { echo "$out" >&2; fail "PR #$num got $(merges_of "$num") merge calls, expected only its arm request"; }
done
grep -qF "pr view 37 --repo $REPO --json state,autoMergeRequest,mergeStateStatus,statusCheckRollup,headRefOid" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "a zero-exit arm was not re-read from GitHub"; }
grep -qF "auto-merge is armed server-side" <<<"$out" \
  || { echo "$out" >&2; fail "PR #42's server-confirmed arm was not recognized"; }

# --- the delay is configurable ---
: > "$TMP/gh.log"
out=$(PR_AUTOPILOT_ARMED_MERGE_DELAY_SECONDS=30 pilot)
[ "$(merges_of 31)" = 1 ] || { echo "$out" >&2; fail "PR #31 (green for 60s) was not merged with a 30s delay"; }

if grep -q -- "--delete-branch" "$TMP/gh.log"; then
  fail "merge request must not delete a branch before GitHub confirms merge"
fi

echo "OK pr-autopilot verifies arming server-side and directly merges only the same green, CLEAN head"
