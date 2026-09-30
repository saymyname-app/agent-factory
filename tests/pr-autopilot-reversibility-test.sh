#!/usr/bin/env bash
#
# pr-autopilot must hold what cannot be undone inside the release (ADR-0019).
#
# docs/DELIVERY.md calls Flyway changes GUARDED, yet the merge actor armed every
# green PR to dev -- two DROP COLUMN migrations reached dev that way. This
# drives the real script against stub gh/gc/checker and asserts: a reversible
# PR is armed as before; an undeclared destructive one is held, labelled and
# explained once; a declared-irreversible one that was already armed is
# DISARMED and escalated to the Mayor; verdicts are cached per head commit; a
# fixed PR is released; a checker that cannot run fails closed; reconciliation
# sees closed work beyond the CLI's default 50-row window, silently backfills
# old history, and wakes the Mayor exactly once for a recent merge or active
# waiter, with no --from (real gc mail send rejects any --from that is not a
# live session alias or "human" -- af-4ruvv); --dry-run changes nothing.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory/rigs/example-backend" "$TMP/factory/rigs/example-frontend" \
         "$TMP/bin" "$TMP/verdicts"
: > "$TMP/gh.log"; : > "$TMP/gc.log"; : > "$TMP/check.log"; : > "$TMP/deliver.log"

# Backend open PRs: 1 reversible, 2 undeclared destructive, 3 declared irreversible (already armed)
cat > "$TMP/backend-open.json" <<'JSON'
[
 {"number":1,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"conclusion":"SUCCESS"}],"headRefOid":"aaa1","labels":[]},
 {"number":2,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"conclusion":"SUCCESS"}],"headRefOid":"bbb1","labels":[]},
 {"number":3,"isDraft":false,"autoMergeRequest":{"mergeMethod":"SQUASH"},"mergeStateStatus":"BLOCKED","statusCheckRollup":[],"headRefOid":"ccc1","labels":[{"name":"backend"}]}
]
JSON
printf '0' > "$TMP/verdicts/aaa1"; printf '3' > "$TMP/verdicts/bbb1"; printf '4' > "$TMP/verdicts/ccc1"

cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ \$1 == pr && \$2 == list ]]; then
  if [[ "\$*" == *"--state open"* && "\$*" == *"example-backend"* ]]; then cat "$TMP/backend-open.json"
  elif [[ "\$*" == *"--state merged"* && "\$*" == *"example-backend"* && -f "$TMP/backend-merged.json" ]]; then cat "$TMP/backend-merged.json"
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
  rows=\$(cat "$TMP/beads.json" 2>/dev/null || printf '[]\n')
  if [[ "\$*" == *"--status open"* ]]; then
    rows=\$(jq '[.[]|select(.status=="open")]' <<<"\$rows")
  elif [[ "\$*" != *"--all"* ]]; then
    # Model the real Beads default: closed rows are absent unless --all is
    # explicit. This is the production behavior the regression must exercise.
    rows=\$(jq '[.[]|select(.status!="closed")]' <<<"\$rows")
  fi
  if [[ "\$*" != *"--limit 0"* ]]; then
    # The real CLI also defaults to at most 50 rows.
    rows=\$(jq '.[0:50]' <<<"\$rows")
  fi
  printf '%s\n' "\$rows"
  exit 0
fi
if [[ \$1 == bd && \$2 == show ]]; then
  # af-cfl9j (B01): the live-reconciliation guard reads the CURRENT status of
  # a bead the once-per-tick snapshot ($TMP/beads.json) already thinks is
  # closed, before trusting that to skip. Answer from the same source of
  # truth this test's beads.json already models, not a separate fixture.
  jq --arg id "\$3" '[.[]|select(.id==\$id)]' "$TMP/beads.json" 2>/dev/null || echo '[]'
  exit 0
fi
exit 0
STUB
cat > "$TMP/bin/check" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/check.log"
num=""; mode=json
while [ \$# -gt 0 ]; do case \$1 in --pr) num=\$2; shift;; --comment) mode=comment;; esac; shift; done
sha=\$(jq -r --argjson n "\$num" '.[]|select(.number==\$n)|.headRefOid' "$TMP/backend-open.json")
rc=\$(cat "$TMP/verdicts/\$sha" 2>/dev/null || echo 2)
[ "\$mode" = comment ] && echo "### Réversibilité : PR \$num"
exit "\$rc"
STUB
cat > "$TMP/bin/deliver-close" <<STUB
#!/usr/bin/env bash
set -Eeuo pipefail
echo "\$*" >> "$TMP/deliver.log"
bead=\$1; shift
repo=""; pr=""; workflow=""
while [ \$# -gt 0 ]; do
  case \$1 in
    --repo) repo=\$2; shift 2 ;;
    --pr) pr=\$2; shift 2 ;;
    --required-workflow) workflow=\$2; shift 2 ;;
    *) shift ;;
  esac
done
gc bd update "\$bead" \
  --set-metadata gc.work_outcome=shipped \
  --set-metadata gc.delivery_status=merged \
  --set-metadata gc.github_repo="\$repo" \
  --set-metadata gc.pr_number="\$pr" \
  --set-metadata gc.pr_url="https://github.com/\$repo/pull/\$pr" \
  --set-metadata gc.pr_head=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  --set-metadata gc.merge_commit=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb \
  --set-metadata merge_result=merged \
  --set-metadata merged_sha=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb \
  --set-metadata merged_target=dev \
  --set-metadata gc.required_ci_workflow="\$workflow" \
  --set-metadata gc.ci_run_id=123 \
  --set-metadata gc.ci_head_sha=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  --set-metadata gc.ci_conclusion=success \
  --status=closed
STUB
chmod +x "$TMP/bin/"*
export PATH="$TMP/bin:$PATH"
export FACTORY_ROOT="$TMP/factory"
export REVERSIBILITY_CHECK_BIN="$TMP/bin/check"
export DELIVER_CLOSE_BIN="$TMP/bin/deliver-close"
export PROTECTED_RIGS_CONFIG_DIR="$REPO_ROOT/tests/fixtures/pr-autopilot-projects"
export GC_OPERATOR_NAME=operator-1
export REVERSIBILITY_CACHE="$TMP/factory/.gc/rev-cache.tsv"
export PR_AUTOPILOT_NOW_EPOCH
PR_AUTOPILOT_NOW_EPOCH=$(date -u -d '2026-09-21T16:00:00Z' +%s)
export PR_AUTOPILOT_RECONCILE_WAKE_WINDOW_SECONDS=3600

pilot() { "$AUTOPILOT" "$@" 2>&1 || true; }
diffs() { grep -c -- '--json' "$TMP/check.log" || true; }

# --- dry run first: nothing may change -------------------------------------------
out=$(pilot --dry-run)
grep -q "PR #2: HELD -> reversibility-declaration-needed" <<<"$out" || { echo "$out" >&2; fail "dry-run did not report the hold"; }
grep -qE '^(pr (merge|comment|edit)|label create)' "$TMP/gh.log" && fail "--dry-run mutated GitHub"
grep -q "mail send" "$TMP/gc.log" && fail "--dry-run mailed the Mayor"

# --- the real pass -----------------------------------------------------------------
: > "$TMP/gh.log"; : > "$TMP/check.log"; rm -f "$REVERSIBILITY_CACHE"
out=$(pilot)
# 1: reversible -> armed exactly as before
grep -q "^pr merge 1 --repo example-corp/example-backend --auto --squash" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "reversible PR was not armed"; }
# 2: undeclared -> held, labelled, explained, not armed, no escalation
grep -q "^pr merge 2 " "$TMP/gh.log" && fail "undeclared destructive PR was armed"
grep -q "^label create reversibility-declaration-needed" "$TMP/gh.log" || fail "hold label not created"
grep -q "^pr comment 2 " "$TMP/gh.log" || fail "hold not explained on PR 2"
grep -q "^api -X POST repos/[^ ]*/issues/2/labels -f labels\[\]=reversibility-declaration-needed" "$TMP/gh.log" || fail "PR 2 not labelled"
# 3: declared irreversible and already armed -> disarmed, labelled, escalated
grep -q "^pr merge 3 --repo example-corp/example-backend --disable-auto" "$TMP/gh.log" || fail "armed irreversible PR not disarmed"
grep -q "^api -X POST repos/[^ ]*/issues/3/labels -f labels\[\]=irreversible-change" "$TMP/gh.log" || fail "PR 3 not labelled irreversible"
grep -q "mail send mayor" "$TMP/gc.log" || fail "irreversible PR not escalated to the Mayor"
grep -q "ESCALADE test 4" "$TMP/gc.log" || fail "escalation does not name test 4"
grep -q "pas operator-1" "$TMP/gc.log" || fail "escalation does not state its author"
grep -q "held=2" <<<"$out" || { echo "$out" >&2; fail "summary does not count the holds"; }

# --- second pass: cached verdicts, no second comment once labelled ---------------------
jq '(.[]|select(.number==2)).labels=[{"name":"reversibility-declaration-needed"}]
  | (.[]|select(.number==3)).labels=[{"name":"irreversible-change"}]
  | (.[]|select(.number==3)).autoMergeRequest=null
  | (.[]|select(.number==1)).autoMergeRequest={"mergeMethod":"SQUASH"}' \
  "$TMP/backend-open.json" > "$TMP/next.json" && mv "$TMP/next.json" "$TMP/backend-open.json"
before=$(diffs); : > "$TMP/gh.log"; : > "$TMP/gc.log"
pilot >/dev/null
[ "$(diffs)" = "$before" ] || fail "verdicts were not cached per head commit"
grep -q "^pr comment" "$TMP/gh.log" && fail "a held PR was commented twice"
grep -q "mail send" "$TMP/gc.log" && fail "the Mayor was escalated twice"

# --- the writer fixes PR 2: new commit, now reversible -> released and armed -------------
jq '(.[]|select(.number==2)).headRefOid="bbb2"' "$TMP/backend-open.json" > "$TMP/next.json" \
  && mv "$TMP/next.json" "$TMP/backend-open.json"
printf '0' > "$TMP/verdicts/bbb2"
: > "$TMP/gh.log"
out=$(pilot)
grep -q "^api -X DELETE repos/[^ ]*/issues/2/labels/reversibility-declaration-needed" "$TMP/gh.log" || { echo "$out" >&2; fail "fixed PR kept its hold label"; }
grep -q "^pr merge 2 .*--auto" "$TMP/gh.log" || fail "fixed PR was not armed"
grep -q "^pr merge 3 .*--auto" "$TMP/gh.log" && fail "irreversible PR was armed"

# --- a checker that cannot run fails closed ------------------------------------------------
jq '(.[]|select(.number==1)).headRefOid="zzz9" | (.[]|select(.number==1)).autoMergeRequest=null' \
  "$TMP/backend-open.json" > "$TMP/next.json" && mv "$TMP/next.json" "$TMP/backend-open.json"
: > "$TMP/gh.log"
out=$(pilot)
grep -q "PR #1: reversibility could not be checked" <<<"$out" || { echo "$out" >&2; fail "checker failure not reported"; }
grep -q "^pr merge 1 " "$TMP/gh.log" && fail "PR armed while its reversibility was unknown"
grep -q "zzz9" "$REVERSIBILITY_CACHE" && fail "a failed check was cached as a verdict"

# --- old bulk reconciliation backfills metadata without waking the Mayor ------------------
# "[ci] failed" / "[autopilot] stuck" beads carry pr_number too; listed first,
# one used to win the [0] pick and get merge_result=merged instead of the work.
cat > "$TMP/backend-merged.json" <<'JSON'
[
 {"number":7,"headRefName":"polecat/af-work7","mergeCommit":{"oid":"feedbeef7"},"mergedAt":"2026-09-18T12:00:00Z"},
 {"number":8,"headRefName":"polecat/af-work8","mergeCommit":{"oid":"feedbeef8"},"mergedAt":"2026-09-19T12:00:00Z"}
]
JSON
jq -n '
  [{"id":"af-flag7","status":"open","title":"[ci] PR #7 failed required checks on dev","metadata":{"pr_number":"7","source":"pr-autopilot"}}]
  + [range(0;49) | {id:("af-noise" + tostring), status:"open", title:"unrelated", metadata:{}}]
  + [
      {"id":"af-work7","status":"closed","title":"old work 7","metadata":{"gc.work_branch":"polecat/af-work7"}},
      {"id":"af-work8","status":"closed","title":"old partial work 8","metadata":{"gc.work_branch":"polecat/af-work8","merge_result":"merged"}}
    ]
' > "$TMP/beads.json"

: > "$TMP/gc.log"
out=$(pilot)
grep -q "^bd list --all --limit 0 --json$" "$TMP/gc.log" || { echo "$out" >&2; fail "reconcile did not request unlimited closed history"; }
grep -q "^bd update af-work7 .*merge_result=merged" "$TMP/gc.log" || { echo "$out" >&2; fail "merged PR was not reconciled onto its work bead"; }
grep -q "^bd update af-work8 .*merge_result=merged" "$TMP/gc.log" || { echo "$out" >&2; fail "second historical PR was not backfilled"; }
grep -q "^bd update af-flag7 .*merge_result=merged" "$TMP/gc.log" && fail "reconcile stamped a pr-autopilot flag bead as merged"
grep -q "^af-work7 --repo example-corp/example-backend --pr 7 --required-workflow Backend CI" "$TMP/deliver.log" \
  || fail "reconciliation did not go through the exact-CI deliver-close door"
grep -q "^bd update af-work7 .*gc.ci_conclusion=success .*--status=closed" "$TMP/gc.log" \
  || fail "delivery door did not atomically close with CI proof"
# af-gpq0y: the flag bead itself IS closed now (a different, deliberate path
# -- close_ci_failure_beads -- not the reconcile stamp above), since its own
# PR merged and the failure it reported no longer applies.
grep -q "^bd update af-flag7 --status closed" "$TMP/gc.log" || { echo "$out" >&2; fail "PR #7's CI-failure bead was not closed on merge"; }
grep -q "^mail send mayor" "$TMP/gc.log" && fail "old bulk backfill with no active waiter sent mail"

# Model the full proof left by the historical backfill before later cases.
jq 'map(if .id=="af-work7" then
      .status="closed"
      | .metadata += {"gc.work_outcome":"shipped","gc.delivery_status":"merged",
          "gc.github_repo":"example-corp/example-backend","gc.pr_number":"7",
          "gc.pr_url":"https://github.com/example-corp/example-backend/pull/7",
          "gc.pr_head":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","gc.merge_commit":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","merge_result":"merged",
          "merged_sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","merged_target":"dev","gc.required_ci_workflow":"Backend CI",
          "gc.ci_run_id":"123","gc.ci_head_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","gc.ci_conclusion":"success"}
     elif .id=="af-work8" then
      .status="closed"
      | .metadata += {"gc.work_outcome":"shipped","gc.delivery_status":"merged",
          "gc.github_repo":"example-corp/example-backend","gc.pr_number":"8",
          "gc.pr_url":"https://github.com/example-corp/example-backend/pull/8",
          "gc.pr_head":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","gc.merge_commit":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","merge_result":"merged",
          "merged_sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","merged_target":"dev","gc.required_ci_workflow":"Backend CI",
          "gc.ci_run_id":"123","gc.ci_head_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","gc.ci_conclusion":"success"}
     else . end)' \
  "$TMP/beads.json" > "$TMP/next.json" && mv "$TMP/next.json" "$TMP/beads.json"

# --- a recent first reconciliation wakes exactly once and never as human -----------------
cat > "$TMP/backend-merged.json" <<'JSON'
[{"number":9,"headRefName":"polecat/af-work9","mergeCommit":{"oid":"feedbeef9"},"mergedAt":"2026-09-21T15:30:00Z"}]
JSON
jq '. + [{"id":"af-work9","status":"closed","title":"recent work","metadata":{"gc.work_branch":"polecat/af-work9"}}]' \
  "$TMP/beads.json" > "$TMP/next.json" && mv "$TMP/next.json" "$TMP/beads.json"

# A dry run may read both snapshots but must neither stamp the work bead nor
# send a meaningful completion wake.
: > "$TMP/gc.log"
out=$(pilot --dry-run)
grep -q "^bd list --all --limit 0 --json$" "$TMP/gc.log" || { echo "$out" >&2; fail "dry-run reconcile did not request unlimited closed history"; }
grep -q "^bd update af-work9 " "$TMP/gc.log" && fail "--dry-run wrote reconciliation metadata"
grep -q "^mail send mayor" "$TMP/gc.log" && fail "--dry-run sent the completion wake"

: > "$TMP/gc.log"
out=$(pilot)
grep -q "^bd update af-work9 .*merge_result=merged" "$TMP/gc.log" || { echo "$out" >&2; fail "recent merge was not reconciled"; }
test "$(grep -c '^mail send mayor --notify' "$TMP/gc.log" || true)" = "1" || fail "recent reconciliation did not send exactly one completion wake"
grep -q -- "--from pr-autopilot" "$TMP/gc.log" && fail "completion wake passed --from pr-autopilot, which real gc mail send rejects (session not found: only a live session alias or human is a valid sender; af-4ruvv)"
grep -q -- "--from human" "$TMP/gc.log" && fail "completion wake impersonated human"
grep -q "SHIPPED: af-work9 via PR #9" "$TMP/gc.log" || fail "completion wake did not name the bead and PR"
grep -q "ACTION: pr-autopilot reconciled af-work9 from merged PR #9" "$TMP/gc.log" || fail "completion wake lacks its ACTION"
grep -q "^STATE: SHIPPED$" "$TMP/gc.log" || fail "completion wake lacks its STATE"
grep -q "^EVIDENCE: af-work9; PR #9; merge SHA feedbeef9$" "$TMP/gc.log" || fail "completion wake lacks exact evidence"
grep -q "^NEXT: Mayor advances or finalizes work waiting on af-work9\.$" "$TMP/gc.log" || fail "completion wake lacks its next action"

# Model the full proof left by the successful write. The structural proof gate
# must make the next tick silent for this delivery: no repeat write or mail.
jq 'map(if .id=="af-work9" then
      .status="closed"
      | .metadata += {"gc.work_outcome":"shipped","gc.delivery_status":"merged",
          "gc.github_repo":"example-corp/example-backend","gc.pr_number":"9",
          "gc.pr_url":"https://github.com/example-corp/example-backend/pull/9",
          "gc.pr_head":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","gc.merge_commit":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","merge_result":"merged",
          "merged_sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","merged_target":"dev","gc.required_ci_workflow":"Backend CI",
          "gc.ci_run_id":"123","gc.ci_head_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","gc.ci_conclusion":"success"}
     else . end)' \
  "$TMP/beads.json" > "$TMP/next.json" && mv "$TMP/next.json" "$TMP/beads.json"
: > "$TMP/gc.log"
pilot >/dev/null
grep -q "^bd update af-work9 " "$TMP/gc.log" && fail "reconciled the same work bead twice"
grep -q "^mail send mayor" "$TMP/gc.log" && fail "sent the completion wake twice"

# --- an old merge still wakes when active work has a real blocking dependency -----------
cat > "$TMP/backend-merged.json" <<'JSON'
[{"number":10,"headRefName":"polecat/af-work10","mergeCommit":{"oid":"feedbeef10"},"mergedAt":"2026-09-18T12:00:00Z"}]
JSON
jq '. + [
    {"id":"af-work10","status":"closed","title":"old required work","metadata":{"gc.work_branch":"polecat/af-work10"}},
    {"id":"af-wait10","status":"in_progress","title":"active dependent","metadata":{},
     "dependencies":[{"issue_id":"af-wait10","depends_on_id":"af-work10","type":"blocks"}]}
  ]' "$TMP/beads.json" > "$TMP/next.json" && mv "$TMP/next.json" "$TMP/beads.json"
: > "$TMP/gc.log"
out=$(pilot)
grep -q "^bd update af-work10 .*merge_result=merged" "$TMP/gc.log" || { echo "$out" >&2; fail "old merge with active waiter was not reconciled"; }
test "$(grep -c '^mail send mayor --notify' "$TMP/gc.log" || true)" = "1" || fail "old merge with active waiter did not send exactly one wake"
grep -q "ACTION: pr-autopilot reconciled af-work10 from merged PR #10" "$TMP/gc.log" || fail "active-waiter wake lacks its ACTION"
rm -f "$TMP/backend-merged.json" "$TMP/beads.json"

# --- O3: an exhausted run budget stops cleanly, reported, not SIGKILLed ------------------
# The order (orders/pr-autopilot.toml) hard-kills the whole run at 120s with no
# trace at all (context deadline exceeded). A zero budget must make the very
# first repo report "not checked" and stop instead of proceeding -- and exit 0:
# skipped work is retried next tick, it is not an order failure
# (tests/pr-autopilot-time-budget-test.sh covers hung calls).
: > "$TMP/gh.log"
out=$(PR_AUTOPILOT_BUDGET_SECONDS=0 "$AUTOPILOT" 2>&1) && rc=0 || rc=$?
grep -q "and any repo after it — not checked (time budget exhausted" <<<"$out" \
  || { echo "$out" >&2; fail "exhausted run budget was not reported"; }
[ "$rc" -eq 0 ] || { echo "$out" >&2; fail "exhausted run budget failed the order instead of reporting and exiting 0"; }
[ -z "$(cat "$TMP/gh.log")" ] || fail "an exhausted run budget must stop before touching any repo"
# The former variable name is still honoured.
out=$(PR_AUTOPILOT_TICK_DEADLINE_SECONDS=0 "$AUTOPILOT" 2>&1) || true
grep -q "not checked (time budget exhausted" <<<"$out" || fail "PR_AUTOPILOT_TICK_DEADLINE_SECONDS is no longer honoured"

echo "OK pr-autopilot holds what cannot be undone"
