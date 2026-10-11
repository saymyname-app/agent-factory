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
#
# 2026-10-01 (PR #372): a CI-failure bead a worker has claimed is in_progress,
# and `bd list --status open` does not return it -- so every new red head
# filed one more "[ci] PR #372 failed" bead (three in 46 minutes, each waking
# its own worker on the same PR), and nothing would ever have closed the
# claimed ones. Same night, PR #373: red on a flaky test, rejected for that
# head, then BEHIND once #372 merged -- the red-check branch `continue`d
# before the BEHIND update, the worker had nothing to push, and the PR sat
# there with the Mayor waiting on pr-autopilot. PR 97 (red and BEHIND) must
# be brought up to date, not flagged: a new head gets a fresh required run. The gc stub below filters on --status like the real bd, and
# the beads of PR 47 and PR 99 are in_progress: PR 99 must not be filed a
# second time, PR 47's bead must still close on recovery, and PR 98 (red, no
# bead yet) proves the filing path is still reached.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory/rigs/example-backend" "$TMP/factory/rigs/example-frontend" "$TMP/bin"
: > "$TMP/gh.log"; : > "$TMP/gc.log"

# PR 47: checks recovered to OK, still open (not merged yet).
# PR 99: still FAILURE, open -- its bead must be left alone, and not doubled.
# PR 98: FAILURE, open, no bead yet -- must be filed.
# PR 97: FAILURE and BEHIND, no bead -- must be updated, not filed.
cat > "$TMP/open.json" <<'JSON'
[
 {"number":47,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"conclusion":"SUCCESS"}],"headRefOid":"fff1","labels":[]},
 {"number":99,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BLOCKED","statusCheckRollup":[{"conclusion":"FAILURE"}],"headRefOid":"ggg1","labels":[]},
 {"number":98,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BLOCKED","statusCheckRollup":[{"conclusion":"FAILURE"}],"headRefOid":"hhh1","labels":[]},
 {"number":97,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BEHIND","statusCheckRollup":[{"conclusion":"FAILURE"}],"headRefOid":"iii1","labels":[]}
]
JSON
# PR 45: merged, never seen green while open (this pass's first look is
# already post-merge) -- its CI-failure bead must still close.
cat > "$TMP/merged.json" <<'JSON'
[
 {"number":45,"headRefName":"feat/smb-a6bm-leaderboard-slice2-board-scope","mergeCommit":{"oid":"1111111111111111111111111111111111111a"},"mergedAt":"2026-09-21T15:30:00Z"}
]
JSON
cat > "$TMP/beads.json" <<'JSON'
[
 {"id":"af-ci47","status":"in_progress","title":"[ci] PR #47 failed required checks on dev","metadata":{"pr_number":"47","source":"pr-autopilot"}},
 {"id":"af-ci99","status":"in_progress","title":"[ci] PR #99 failed required checks on dev","metadata":{"pr_number":"99","source":"pr-autopilot"}},
 {"id":"af-ci45","status":"open","title":"[ci] PR #45 failed required checks on dev","metadata":{"pr_number":"45","source":"pr-autopilot"}},
 {"id":"af-work45","status":"in_progress","title":"work delivered by PR 45","metadata":{"gc.work_branch":"feat/smb-a6bm-leaderboard-slice2-board-scope"}}
]
JSON

cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ \$1 == pr && \$2 == list ]]; then
  if [[ "\$*" != *"example-backend"* ]]; then echo '[]'; exit 0; fi
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
  # Like the real bd: --status filters on the stored status (comma-separated
  # for several); with --all or no --status every bead comes back.
  statuses=""
  args=("\$@")
  for i in "\${!args[@]}"; do
    [[ \${args[\$i]} == --status ]] && statuses=\${args[\$((i+1))]}
  done
  jq -c --arg s "\$statuses" \
    '(\$s|split(",")) as \$want | map(select(\$s == "" or (.status as \$st | \$want | index(\$st))))' \
    "$TMP/beads.json"
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
export GC_PR_AUTHORS=example-operator
export REVERSIBILITY_CHECK_BIN="$TMP/bin/gh"
export DELIVER_CLOSE_BIN="$TMP/bin/deliver-close"
export PROTECTED_RIGS_CONFIG_DIR="$REPO_ROOT/tests/fixtures/pr-autopilot-projects"

pilot() { "$AUTOPILOT" "$@" 2>&1 || true; }

out=$(pilot)

# PR 47: checks recovered (OK) while still open -> its CI-failure bead closes,
# even though a worker had claimed it (in_progress).
grep -q "^bd update af-ci47 --status closed" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "PR #47's recovered-checks bead was not closed"; }

# PR 99: still FAILURE -> its bead must be left untouched, and no second bead
# filed for the same PR while the first one is in_progress.
grep -q "^bd update af-ci99 " "$TMP/gc.log" && fail "PR #99 is still failing but its CI bead was closed"
grep -qF "bd create [ci] PR #99 failed required checks" "$TMP/gc.log" \
  && { echo "$out" >&2; fail "PR #99 already has an in_progress CI-failure bead but a second one was filed"; }

# PR 98: FAILURE with no bead yet -> filed (the filing path is reached).
grep -qF "bd create [ci] PR #98 failed required checks" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "PR #98 (red, no bead yet) was not flagged"; }

# PR 97: red and BEHIND -> no bead for the stale head. It waits while PR 47
# (up to date, green) holds the queue (af-31t0y8); the pass at the end of
# this file, with PR 47 gone, proves it is then brought up to date.
grep -q "pulls/97/update-branch" "$TMP/gh.log" \
  && { echo "$out" >&2; fail "PR #97 (BEHIND) was brought up to date while PR #47 held the queue"; }
grep -qF "bd create [ci] PR #97 failed required checks" "$TMP/gc.log" \
  && { echo "$out" >&2; fail "PR #97 (red and BEHIND) was flagged for a head about to be replaced"; }

# PR 45: merged (first seen already merged, never green while open) -> closes too.
grep -q "^bd update af-ci45 --status closed" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "PR #45's CI-failure bead was not closed on merge"; }
grep -q "^bd update af-work45 .*merge_result=merged .*--status=closed" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "PR #45 work did not pass through the delivery finalizer"; }

# PR 47 merged: nothing holds the queue any more (98 and 99 are red), so the
# red and BEHIND PR 97 is brought up to date, still without a bead.
python3 - "$TMP/open.json" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    prs = [pr for pr in json.load(f) if pr["number"] != 47]
with open(sys.argv[1], "w") as f:
    json.dump(prs, f)
PY
: > "$TMP/gh.log"; : > "$TMP/gc.log"
out=$(pilot)
grep -q "pulls/97/update-branch" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #97 (red and BEHIND) was not brought up to date once nothing held the queue"; }
grep -qF "bd create [ci] PR #97 failed required checks" "$TMP/gc.log" \
  && { echo "$out" >&2; fail "PR #97 (red and BEHIND) was flagged for a head about to be replaced"; }

echo "OK pr-autopilot closes CI-failure beads once checks recover or the PR merges, and files one per PR"
