#!/usr/bin/env bash
#
# af-nih6m6: GitHub's merge queue removed PR #889 (its combined commit failed
# the required check) and its auto-merge with it; its own head stayed green
# and CLEAN, so pr-autopilot armed it again, 7 times in 80 minutes on the same
# head (2026-11-16), each time a full merge_group run. This drives
# pr-autopilot against stub gh/gc binaries and proves:
#  1. a ticket-owned PR whose last timeline item is a merge queue removal is
#     not armed: its ticket goes back to the pool with the queue's reason and
#     the refusal is recorded once with the head it refused;
#  2. a PR without a ticket refused the same way is not armed and is filed
#     once as a bead;
#  3. a commit or push after the removal is armed as before;
#  4. a removal already recorded for another head (a commit dated before the
#     removal but pushed after it) does not hold the new head;
#  5. the next pass, on the same refused head, arms nothing and reopens
#     nothing again;
#  6. --dry-run writes nothing and arms nothing refused.
#  7. a PR that last left the queue "merged" is not a refusal.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory/rigs/saymyname-backend" "$TMP/factory/rigs/saymyname-frontend" "$TMP/bin"
: > "$TMP/gh.log"; : > "$TMP/gc.log"
REPO=saymyname-app/Say-my-name-back

# 50: ticket af-q50, removed by the queue, nothing since.
# 51: removed, then a new commit.             52: no ticket, removed.
# 53: removed (event E53), already recorded for an older head.
# 54: last left the queue "merged" (how a merged PR leaves it): not a refusal.
cat > "$TMP/open.json" <<'JSON'
[
 {"number":50,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"status":"COMPLETED","conclusion":"SUCCESS"}],"headRefOid":"sha50aaaaaaaaaa","labels":[]},
 {"number":51,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"status":"COMPLETED","conclusion":"SUCCESS"}],"headRefOid":"sha51aaaaaaaaaa","labels":[]},
 {"number":52,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"status":"COMPLETED","conclusion":"SUCCESS"}],"headRefOid":"sha52aaaaaaaaaa","labels":[]},
 {"number":53,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"status":"COMPLETED","conclusion":"SUCCESS"}],"headRefOid":"sha53bbbbbbbbbb","labels":[]},
 {"number":54,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"status":"COMPLETED","conclusion":"SUCCESS"}],"headRefOid":"sha54aaaaaaaaaa","labels":[]}
]
JSON
cat > "$TMP/all-beads.json" <<'JSON'
[ {"id":"af-q50","status":"in_progress","metadata":{"gc.work_branch":"do-work/af-q50"}} ]
JSON

# The graphql stub answers what `--jq` would print: typename, id, reason.
# COMMENTS_MODE=second carries the markers the first pass posted.
cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ "\$1" == api && "\$2" == graphql ]]; then
  # GitHub refuses a query whose braces do not balance; so does this stub.
  q="\$*"; opens=\${q//[^\{]/}; closes=\${q//[^\}]/}
  [ \${#opens} = \${#closes} ] || { echo "unbalanced query" >&2; exit 1; }
  case " \$* " in
    *" num=50 "*) printf 'RemovedFromMergeQueueEvent\tE50\tfailed_checks\n' ;;
    *" num=51 "*) printf 'PullRequestCommit\t\t\n' ;;
    *" num=52 "*) printf 'RemovedFromMergeQueueEvent\tE52\tfailed_checks\n' ;;
    *" num=53 "*) printf 'RemovedFromMergeQueueEvent\tE53\tfailed_checks\n' ;;
    *" num=54 "*) printf 'RemovedFromMergeQueueEvent\tE54\tmerged\n' ;;
  esac
  exit 0
fi
if [[ "\$1" == pr && "\$2" == list ]]; then
  if [[ "\$*" == *"Say-my-name-back"* && "\$*" == *"--state open"* ]]; then cat "$TMP/open.json"; else echo '[]'; fi
  exit 0
fi
if [[ "\$1" == pr && "\$2" == view && "\$*" == *"--json comments"* ]]; then
  case " \$* " in
    *" 50 "*) [[ "\${COMMENTS_MODE:-first}" == second ]] \
                && printf '%s\n' "pr-autopilot: merge queue removal E50 refused sha50aaaaaaa (failed_checks): not queued again until a new commit." \
                                 "pr-autopilot: rejected af-q50 for sha50aaaaaaa: merge queue refused head sha50aaaaaaa (failed_checks)." ;;
    *" 53 "*) echo "pr-autopilot: merge queue removal E53 refused sha53aaaaaaa (failed_checks): not queued again until a new commit." ;;
  esac
  exit 0
fi
if [[ "\$1" == pr && "\$2" == view && "\$*" == *"--json headRefName"* ]]; then
  case " \$* " in
    *" 50 "*) echo "do-work/af-q50" ;;
    *) echo "feature/manual-\$3" ;;
  esac
  exit 0
fi
if [[ "\$1" == pr && "\$2" == view ]]; then
  printf '%s\n' '{"state":"OPEN","autoMergeRequest":{"mergeMethod":"SQUASH"},"mergeStateStatus":"CLEAN","statusCheckRollup":[],"headRefOid":"x"}'
  exit 0
fi
if [[ "\$1" == api && "\$*" == *"/files"* ]]; then exit 0; fi
if [[ "\$1" == api ]]; then exit 1; fi
exit 0
STUB
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gc.log"
if [[ "\$1" == bd && "\$2" == list ]]; then
  if [[ "\$*" == *"--all"* ]]; then cat "$TMP/all-beads.json"; else cat "\${OPEN_BEADS:-/dev/null}" 2>/dev/null || echo '[]'; fi
  exit 0
fi
exit 0
STUB
chmod +x "$TMP/bin/"*
export PATH="$TMP/bin:$PATH"
export FACTORY_ROOT="$TMP/factory"
export GC_PR_AUTHORS=example-operator
export REVERSIBILITY_CHECK_BIN="$TMP/bin/gh"
export ESCALATION_DOOR_BIN="$TMP/bin/gh"
export GC_BIN="$TMP/bin/gc"

pilot() { COMMENTS_MODE="$1" "$AUTOPILOT" "${@:2}" 2>&1 || true; }
armed() { grep -q "^pr merge $1 --repo $REPO --auto" "$TMP/gh.log"; }

# --- dry run: nothing written, nothing refused armed ---
out=$(pilot first --dry-run)
armed 50 && { echo "$out" >&2; fail "--dry-run armed refused PR #50"; }
grep -q "^pr comment" "$TMP/gh.log" && { echo "$out" >&2; fail "--dry-run posted a comment"; }
grep -q "^bd update\|^bd create" "$TMP/gc.log" && { echo "$out" >&2; fail "--dry-run wrote a bead"; }

# --- first pass ---
: > "$TMP/gh.log"; : > "$TMP/gc.log"
out=$(pilot first)

# 1. refused, ticket-owned: not armed, ticket back with the queue's reason.
armed 50 && { echo "$out" >&2; fail "PR #50 was armed again on the head the merge queue refused"; }
grep -qF "pr comment 50 --repo $REPO --body pr-autopilot: merge queue removal E50 refused sha50aaaaaaa (failed_checks)" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #50's refusal was not recorded with the head it refused"; }
grep -qF "bd update af-q50 --status open" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "PR #50's ticket af-q50 was not sent back to the pool"; }
grep -qF "gc.pr_rejection_reason=merge queue refused head sha50aaaaaaa (failed_checks)" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "PR #50's rejection reason does not name the merge queue refusal"; }

# 2. refused, no ticket: not armed, filed once.
armed 52 && { echo "$out" >&2; fail "PR #52 was armed again on the head the merge queue refused"; }
grep -qF "bd create [autopilot] PR #52 refused by the merge queue at sha52aaaaaaa" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "PR #52 (no ticket) refused by the queue was not filed"; }

# 3 and 4. a new head after the removal is armed.
armed 51 || { echo "$out" >&2; fail "PR #51, with a commit after the removal, was not armed"; }
armed 53 || { echo "$out" >&2; fail "PR #53's new head was held by a refusal recorded for an older head"; }
armed 54 || { echo "$out" >&2; fail "PR #54, which left the queue merged, was taken for a refusal"; }

# 5. next pass, same refused heads: nothing armed, reopened or filed again.
: > "$TMP/gh.log"; : > "$TMP/gc.log"
printf '[{"id":"af-x52","status":"open","title":"[autopilot] PR #52 refused by the merge queue at sha52aaaaaaa"}]' > "$TMP/open-beads.json"
out=$(OPEN_BEADS="$TMP/open-beads.json" pilot second)
armed 50 && { echo "$out" >&2; fail "PR #50 was armed on the second pass"; }
armed 52 && { echo "$out" >&2; fail "PR #52 was armed on the second pass"; }
grep -qF "bd update af-q50" "$TMP/gc.log" && { echo "$out" >&2; fail "PR #50's ticket was sent back a second time for the same head"; }
grep -qF "bd create" "$TMP/gc.log" && { echo "$out" >&2; fail "PR #52 was filed a second time"; }
grep -q "^pr comment 50 " "$TMP/gh.log" && { echo "$out" >&2; fail "PR #50's refusal was recorded a second time"; }

echo "OK pr-autopilot never queues again a head the merge queue refused, and sends it back to its ticket"
