#!/usr/bin/env bash
#
# P06 (af-elhn7): a factory-worker used to leave a red or conflicted PR behind
# when it moved on to the next ticket -- nobody watched the PR come back, and
# a human had to notice and manually re-dispatch it. This drives pr-autopilot
# against stub gh/gc/escalation-door binaries and proves: a DIRTY ticket-owned
# PR (#10) and a ticket-owned PR still red after pr-autopilot's one retry
# (#20) each reopen their ticket bead (status open, unassigned) with a
# structured rejection reason and an incremented rejection count, and keep
# their branch/PR untouched (no worktree/branch metadata is touched); the
# third rejection (#20 starts at count 2) pages the Mayor via escalation-door
# exactly once; a DIRTY PR with no linked ticket (#30) falls through to the
# pre-existing generic stuck-PR flow unchanged; and a second pass on an
# already-rejected head (comment marker already posted) does not reopen or
# recount the ticket again, nor re-page the Mayor.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory/rigs/saymyname-backend" "$TMP/factory/rigs/saymyname-frontend" "$TMP/bin"
: > "$TMP/gh.log"; : > "$TMP/gc.log"; : > "$TMP/escalation.log"

# PR 10: DIRTY, belongs to ticket af-tick1 (branch do-work/af-tick1), never
#   rejected before (no gc.pr_rejection_count on the bead).
# PR 20: required check FAILURE, a retry marker for its head already exists
#   (retry_ci_failure must not retry again), belongs to ticket af-tick2
#   (branch do-work/af-tick2) already rejected twice (gc.pr_rejection_count=2)
#   -- this is its third rejection.
# PR 30: DIRTY, branch feature/manual-fix -- no linked work bead anywhere.
cat > "$TMP/open.json" <<'JSON'
[
 {"number":10,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"DIRTY","statusCheckRollup":[],"headRefOid":"sha10a","labels":[]},
 {"number":20,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BLOCKED","statusCheckRollup":[{"conclusion":"FAILURE"}],"headRefOid":"sha20a","labels":[]},
 {"number":30,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"DIRTY","statusCheckRollup":[],"headRefOid":"sha30a","labels":[]}
]
JSON

cat > "$TMP/all-beads.json" <<'JSON'
[
 {"id":"af-tick1","status":"in_progress","metadata":{"gc.work_branch":"do-work/af-tick1"}},
 {"id":"af-tick2","status":"in_progress","metadata":{"gc.work_branch":"do-work/af-tick2","gc.pr_rejection_count":"2"}}
]
JSON

# COMMENTS_MODE (env, read by the gh stub) toggles what "pr view --json
# comments" returns per PR, so the second pass in this test can simulate the
# rejection/retry markers pr-autopilot itself would have posted on the first.
cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ "\$1" == pr && "\$2" == list ]]; then
  if [[ "\$*" != *"Say-my-name-back"* ]]; then echo '[]'; exit 0; fi
  if [[ "\$*" == *"--state open"* ]]; then cat "$TMP/open.json";
  elif [[ "\$*" == *"--state merged"* ]]; then echo '[]';
  else echo '[]'; fi
  exit 0
fi
if [[ "\$1" == pr && "\$2" == view && "\$*" == *"--json comments"* ]]; then
  case " \$* " in
    *" 10 "*) [[ "\${COMMENTS_MODE:-first}" == second ]] && echo "pr-autopilot: rejected af-tick1 for sha10a" ;;
    *" 20 "*)
      echo "pr-autopilot: retried CI once for sha20a"
      [[ "\${COMMENTS_MODE:-first}" == second ]] && echo "pr-autopilot: rejected af-tick2 for sha20a" ;;
  esac
  exit 0
fi
if [[ "\$1" == pr && "\$2" == view && "\$*" == *"--json headRefName"* ]]; then
  case " \$* " in
    *" 10 "*) echo "do-work/af-tick1" ;;
    *" 20 "*) echo "do-work/af-tick2" ;;
    *" 30 "*) echo "feature/manual-fix" ;;
  esac
  exit 0
fi
if [[ "\$1" == pr && "\$2" == view ]]; then echo '["OPEN","false"]' | jq -r '@tsv'; exit 0; fi
if [[ "\$1" == api ]]; then
  if [[ "\$*" == *"/commits/"* ]]; then echo "deadbeefcafefeed1234567890abcdef12345678"; exit 0; fi
  exit 1
fi
if [[ "\$1" == run && "\$2" == list ]]; then echo ""; exit 0; fi
if [[ "\$1" == pr && "\$2" == comment ]]; then exit 0; fi
if [[ "\$1" == pr && "\$2" == edit ]]; then exit 0; fi
if [[ "\$1" == label && "\$2" == create ]]; then exit 0; fi
exit 0
STUB
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gc.log"
if [[ "\$1" == bd && "\$2" == list ]]; then
  if [[ "\$*" == *"--all"* ]]; then cat "$TMP/all-beads.json"; else echo '[]'; fi
  exit 0
fi
exit 0
STUB
cat > "$TMP/bin/escalation-door" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/escalation.log"
exit 0
STUB
chmod +x "$TMP/bin/"*
export PATH="$TMP/bin:$PATH"
export FACTORY_ROOT="$TMP/factory"
export REVERSIBILITY_CHECK_BIN="$TMP/bin/gh"
export ESCALATION_DOOR_BIN="$TMP/bin/escalation-door"
export GC_BIN="$TMP/bin/gc"

pilot() { COMMENTS_MODE="$1" "$AUTOPILOT" 2>&1 || true; }

out=$(pilot first)

# PR 10 (DIRTY, ticket-owned, first rejection): reopened to the pool with a
# structured reason and rejection_count=1; branch/PR untouched (no work_branch
# or pr_url metadata write).
grep -qF "bd update af-tick1 --status open --assignee  --set-metadata" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "PR #10's ticket af-tick1 was not reopened to the pool"; }
grep -qF "gc.pr_rejection_reason=conflict with dev@deadbeefcafe" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "PR #10's rejection reason was not the DIRTY conflict-with-base form"; }
grep -qF "gc.pr_rejection_count=1" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "PR #10's first rejection did not set rejection_count=1"; }
grep -qF "gc.work_branch" "$TMP/gc.log" \
  && fail "PR #10's reopen touched gc.work_branch -- the branch must be left exactly as it is"
grep -q "^pr comment 10 --repo saymyname-app/Say-my-name-back --body pr-autopilot: rejected af-tick1 for sha10a" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #10's rejection marker comment was not posted"; }
grep -qF "af-tick1" "$TMP/escalation.log" \
  && fail "PR #10's first rejection paged the Mayor (should only page on the third)"

# PR 20 (FAILURE after retry already marked, ticket-owned, third rejection):
# reopened with rejection_count=3, and escalation-door mayor paged exactly once.
grep -qF "bd update af-tick2 --status open --assignee  --set-metadata" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "PR #20's ticket af-tick2 was not reopened to the pool"; }
grep -qF "gc.pr_rejection_count=3" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "PR #20's third rejection did not set rejection_count=3"; }
[ "$(grep -c '^run rerun' "$TMP/gh.log")" = "0" ] \
  || fail "PR #20 was retried again even though its retry marker was already posted"
grep -q "^mayor af-tick2 " "$TMP/escalation.log" \
  || { echo "$out" >&2; fail "PR #20's third rejection did not page the Mayor via escalation-door"; }
[ "$(grep -c '^mayor af-tick2 ' "$TMP/escalation.log")" = "1" ] \
  || fail "PR #20's third rejection paged the Mayor more than once"

# PR 30 (DIRTY, no linked ticket): falls through to the pre-existing generic
# stuck-PR flow (first pass: label only, no bead, no ticket touched).
grep -q "^pr edit 30 --repo saymyname-app/Say-my-name-back --add-label autopilot-stuck" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #30 (no ticket) did not fall through to the generic stuck-PR label"; }
grep -qF "PR #30" "$TMP/gc.log" && fail "PR #30 touched a ticket bead despite having no linked work bead"

# --- second pass: both rejections already marked on their heads -> idempotent ---
: > "$TMP/gc.log"; : > "$TMP/gh.log"; : > "$TMP/escalation.log"
out=$(pilot second)
grep -qF "bd update af-tick1" "$TMP/gc.log" \
  && { echo "$out" >&2; fail "PR #10 was rejected a second time for the same head"; }
grep -qF "bd update af-tick2" "$TMP/gc.log" \
  && { echo "$out" >&2; fail "PR #20 was rejected a second time for the same head"; }
[ -s "$TMP/escalation.log" ] \
  && { echo "$out" >&2; fail "escalation-door was called again on an already-escalated, unresolved head"; }

echo "OK pr-autopilot returns a DIRTY or still-red ticket-owned PR to the pool with a rejection reason, escalates on the third, and is idempotent per head"
