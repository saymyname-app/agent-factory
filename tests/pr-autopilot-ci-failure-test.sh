#!/usr/bin/env bash
#
# af-gpq0y: pr-autopilot files a "[ci] PR #N failed required checks" bead the
# first time a PR's required check goes red, but nothing ever closed it again
# -- smb-au8d stayed open for hours after PR #47's checks turned green and it
# merged. This drives pr-autopilot against stub gh/gc binaries and proves:
# a CI-failure bead is closed the pass checks recover to non-FAILURE while
# the PR is still open, and closed on the pass the PR shows up merged (even
# if it never showed green while open, e.g. this is the first look post-merge).
# An unrelated open, still-failing PR's bead is left alone in both cases.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory/rigs/saymyname-backend" "$TMP/factory/rigs/saymyname-frontend" "$TMP/bin"
: > "$TMP/gh.log"; : > "$TMP/gc.log"

# PR 47: checks recovered to OK, still open (not merged yet).
# PR 99: still FAILURE, open -- its bead must be left alone.
cat > "$TMP/open.json" <<'JSON'
[
 {"number":47,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"conclusion":"SUCCESS"}],"headRefOid":"fff1","labels":[]},
 {"number":99,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BLOCKED","statusCheckRollup":[{"conclusion":"FAILURE"}],"headRefOid":"ggg1","labels":[]}
]
JSON
# PR 45: merged, never seen green while open (this pass's first look is
# already post-merge) -- its CI-failure bead must still close.
cat > "$TMP/merged.json" <<'JSON'
[
 {"number":45,"headRefName":"feat/smb-a6bm-leaderboard-slice2-board-scope","mergeCommit":{"oid":"1111111111111111111111111111111111111a"},"mergedAt":"2026-09-21T15:30:00Z"}
]
JSON

cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ \$1 == pr && \$2 == list ]]; then
  if [[ "\$*" != *"Say-my-name-back"* ]]; then echo '[]'; exit 0; fi
  if [[ "\$*" == *"--state open"* ]]; then cat "$TMP/open.json";
  elif [[ "\$*" == *"--state merged"* ]]; then cat "$TMP/merged.json";
  else echo '[]'; fi
  exit 0
fi
if [[ \$1 == pr && \$2 == view ]]; then echo '["OPEN","false"]' | jq -r '@tsv'; exit 0; fi
exit 0
STUB
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gc.log"
if [[ \$1 == bd && \$2 == list ]]; then
  echo '[{"id":"af-ci47","title":"[ci] PR #47 failed required checks on dev","metadata":{"pr_number":"47","source":"pr-autopilot"}},
        {"id":"af-ci99","title":"[ci] PR #99 failed required checks on dev","metadata":{"pr_number":"99","source":"pr-autopilot"}},
        {"id":"af-ci45","title":"[ci] PR #45 failed required checks on dev","metadata":{"pr_number":"45","source":"pr-autopilot"}},
        {"id":"af-work45","status":"in_progress","title":"work delivered by PR 45","metadata":{"gc.work_branch":"feat/smb-a6bm-leaderboard-slice2-board-scope"}}]'
  exit 0
fi
exit 0
STUB
cat > "$TMP/bin/deliver-close" <<STUB
#!/usr/bin/env bash
set -Eeuo pipefail
bead=\$1
gc bd update "\$bead" --set-metadata merge_result=merged --set-metadata gc.ci_conclusion=success --status=closed
STUB
chmod +x "$TMP/bin/"*
export PATH="$TMP/bin:$PATH"
export FACTORY_ROOT="$TMP/factory"
export REVERSIBILITY_CHECK_BIN="$TMP/bin/gh"
export DELIVER_CLOSE_BIN="$TMP/bin/deliver-close"

pilot() { "$AUTOPILOT" "$@" 2>&1 || true; }

out=$(pilot)

# PR 47: checks recovered (OK) while still open -> its CI-failure bead closes.
grep -q "^bd update af-ci47 --status closed" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "PR #47's recovered-checks bead was not closed"; }

# PR 99: still FAILURE -> its bead must be left untouched.
grep -q "^bd update af-ci99 " "$TMP/gc.log" && fail "PR #99 is still failing but its CI bead was closed"

# PR 45: merged (first seen already merged, never green while open) -> closes too.
grep -q "^bd update af-ci45 --status closed" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "PR #45's CI-failure bead was not closed on merge"; }
grep -q "^bd update af-work45 .*merge_result=merged .*--status=closed" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "PR #45 work did not pass through the delivery finalizer"; }

echo "OK pr-autopilot closes CI-failure beads once checks recover or the PR merges"
