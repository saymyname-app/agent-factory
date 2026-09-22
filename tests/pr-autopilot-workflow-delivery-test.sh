#!/usr/bin/env bash
#
# af-aviw4: a merged build-basic workflow used to receive only the legacy
# merge_result/merged_sha projection. Its original source bead remained open,
# so dependents stayed blocked until the Mayor manually ran deliver-close.
#
# Drive the real pr-autopilot and deliver-close scripts against deterministic
# gc/gh fixtures. Prove direct do-work and workflow/convoy delivery, cross-rig
# routing, six-field proof, a single completion wake, idempotence, dry-run
# inertia, and fail-closed behavior for open/red/closed-unmerged PRs, failed
# workflows, and ambiguous source convoys.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

BACKEND="$TMP/factory/rigs/saymyname-backend"
FRONTEND="$TMP/factory/rigs/saymyname-frontend"
mkdir -p "$BACKEND" "$FRONTEND" "$TMP/bin" "$TMP/factory/.gc"
export GC_LOG="$TMP/gc.log"
export GH_LOG="$TMP/gh.log"
export BACKEND_BEADS="$TMP/backend-beads.json"
export FRONTEND_BEADS="$TMP/frontend-beads.json"
export FACTORY_BEADS="$TMP/factory-beads.json"
export BACKEND_OPEN="$TMP/backend-open.json"
export BACKEND_MERGED="$TMP/backend-merged.json"
export FRONTEND_OPEN="$TMP/frontend-open.json"
export FRONTEND_MERGED="$TMP/frontend-merged.json"
export FACTORY_OPEN="$TMP/factory-open.json"
export FACTORY_MERGED="$TMP/factory-merged.json"
export PR_VIEWS="$TMP/pr-views.json"
: > "$GC_LOG"
: > "$GH_LOG"
printf '[]\n' > "$FACTORY_BEADS"
printf '[]\n' > "$FRONTEND_OPEN"
printf '[]\n' > "$FACTORY_OPEN"
printf '[]\n' > "$FACTORY_MERGED"

cat > "$BACKEND_OPEN" <<'JSON'
[
  {"number":17,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BLOCKED","statusCheckRollup":[{"conclusion":"FAILURE"}],"headRefOid":"1717171717171717171717171717171717171717","labels":[]},
  {"number":18,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"conclusion":"SUCCESS"}],"headRefOid":"1818181818181818181818181818181818181818","labels":[]}
]
JSON

cat > "$BACKEND_MERGED" <<'JSON'
[
  {"number":11,"headRefName":"build-basic/smb-root","mergeCommit":{"oid":"b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1"},"mergedAt":"2026-09-21T15:30:00Z"},
  {"number":12,"headRefName":"do-work/smb-direct","mergeCommit":{"oid":"b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2"},"mergedAt":"2026-09-21T15:31:00Z"},
  {"number":13,"headRefName":"build-basic/smb-failedroot","mergeCommit":{"oid":"b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3"},"mergedAt":"2026-09-21T15:32:00Z"},
  {"number":14,"headRefName":"build-basic/smb-ambiguousroot","mergeCommit":{"oid":"b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4"},"mergedAt":"2026-09-21T15:33:00Z"},
  {"number":15,"headRefName":"build-basic/smb-closedroot","mergeCommit":{"oid":"b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5"},"mergedAt":"2026-09-21T15:34:00Z"}
]
JSON

cat > "$FRONTEND_MERGED" <<'JSON'
[
  {"number":16,"headRefName":"build-basic/smf-root","mergeCommit":{"oid":"b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6"},"mergedAt":"2026-09-21T15:35:00Z"}
]
JSON

cat > "$BACKEND_BEADS" <<'JSON'
[
  {"id":"smb-source","status":"open","metadata":{"gc.work_branch":"build-basic/smb-root"}},
  {"id":"smb-root","status":"closed","metadata":{"gc.kind":"workflow","gc.outcome":"pass","gc.var.convoy_id":"smb-input","gc.work_branch":"build-basic/smb-root"}},
  {"id":"smb-input","status":"open","issue_type":"convoy","metadata":{},"dependencies":[{"depends_on_id":"smb-source","type":"tracks"}]},
  {"id":"smb-waiter","status":"open","metadata":{"gc.waiting_on":"smb-source"},"dependencies":[{"depends_on_id":"smb-source","type":"blocks"}]},
  {"id":"smb-unrelated","status":"open","metadata":{"gc.work_branch":"build-basic/smb-root"}},

  {"id":"smb-direct","status":"closed","metadata":{"gc.work_branch":"do-work/smb-direct"}},

  {"id":"smb-failedsource","status":"open","metadata":{"gc.work_branch":"build-basic/smb-failedroot"}},
  {"id":"smb-failedroot","status":"closed","metadata":{"gc.kind":"workflow","gc.outcome":"fail","gc.var.convoy_id":"smb-failedinput","gc.work_branch":"build-basic/smb-failedroot"}},
  {"id":"smb-failedinput","status":"open","issue_type":"convoy","metadata":{},"dependencies":[{"depends_on_id":"smb-failedsource","type":"tracks"}]},

  {"id":"smb-ambiguousa","status":"open","metadata":{"gc.work_branch":"build-basic/smb-ambiguousroot"}},
  {"id":"smb-ambiguousb","status":"open","metadata":{"gc.work_branch":"build-basic/smb-ambiguousroot"}},
  {"id":"smb-ambiguousroot","status":"closed","metadata":{"gc.kind":"workflow","gc.outcome":"pass","gc.var.convoy_id":"smb-ambiguousinput","gc.work_branch":"build-basic/smb-ambiguousroot"}},
  {"id":"smb-ambiguousinput","status":"open","issue_type":"convoy","metadata":{},"dependencies":[{"depends_on_id":"smb-ambiguousa","type":"tracks"},{"depends_on_id":"smb-ambiguousb","type":"tracks"}]},

  {"id":"smb-closedsource","status":"open","metadata":{"gc.work_branch":"build-basic/smb-closedroot"}},
  {"id":"smb-closedroot","status":"closed","metadata":{"gc.kind":"workflow","gc.outcome":"pass","gc.var.convoy_id":"smb-closedinput","gc.work_branch":"build-basic/smb-closedroot"}},
  {"id":"smb-closedinput","status":"open","issue_type":"convoy","metadata":{},"dependencies":[{"depends_on_id":"smb-closedsource","type":"tracks"}]},

  {"id":"smb-red","status":"open","metadata":{"gc.work_branch":"do-work/smb-red"}},
  {"id":"smb-open","status":"closed","metadata":{"gc.work_branch":"do-work/smb-open"}}
]
JSON

cat > "$FRONTEND_BEADS" <<'JSON'
[
  {"id":"smf-source","status":"open","metadata":{"gc.work_branch":"build-basic/smf-root"}},
  {"id":"smf-root","status":"closed","metadata":{"gc.kind":"workflow","gc.outcome":"pass","gc.var.convoy_id":"smf-input","gc.work_branch":"build-basic/smf-root"}},
  {"id":"smf-input","status":"open","issue_type":"convoy","metadata":{},"dependencies":[{"depends_on_id":"smf-source","type":"tracks"}]}
]
JSON

cat > "$PR_VIEWS" <<'JSON'
{
  "11":{"number":11,"state":"MERGED","mergedAt":"2026-09-21T15:30:00Z","headRefOid":"a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1","mergeCommit":{"oid":"b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1"},"url":"https://github.com/saymyname-app/Say-my-name-back/pull/11"},
  "12":{"number":12,"state":"MERGED","mergedAt":"2026-09-21T15:31:00Z","headRefOid":"a2a2a2a2a2a2a2a2a2a2a2a2a2a2a2a2a2a2a2a2","mergeCommit":{"oid":"b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2"},"url":"https://github.com/saymyname-app/Say-my-name-back/pull/12"},
  "13":{"number":13,"state":"MERGED","mergedAt":"2026-09-21T15:32:00Z","headRefOid":"a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3","mergeCommit":{"oid":"b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3b3"},"url":"https://github.com/saymyname-app/Say-my-name-back/pull/13"},
  "14":{"number":14,"state":"MERGED","mergedAt":"2026-09-21T15:33:00Z","headRefOid":"a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4a4","mergeCommit":{"oid":"b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4b4"},"url":"https://github.com/saymyname-app/Say-my-name-back/pull/14"},
  "15":{"number":15,"state":"CLOSED","mergedAt":null,"headRefOid":"a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5","mergeCommit":{"oid":"b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5b5"},"url":"https://github.com/saymyname-app/Say-my-name-back/pull/15"},
  "16":{"number":16,"state":"MERGED","mergedAt":"2026-09-21T15:35:00Z","headRefOid":"a6a6a6a6a6a6a6a6a6a6a6a6a6a6a6a6a6a6a6a6","mergeCommit":{"oid":"b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6b6"},"url":"https://github.com/saymyname-app/Say-my-name-front/pull/16"}
}
JSON

cat > "$TMP/bin/gh" <<'STUB'
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "$*" >> "$GH_LOG"
if [[ ${1:-} == pr && ${2:-} == list ]]; then
  case "$*" in
    *Say-my-name-back*"--state open"*) cat "$BACKEND_OPEN" ;;
    *Say-my-name-back*"--state merged"*) cat "$BACKEND_MERGED" ;;
    *Say-my-name-front*"--state open"*) cat "$FRONTEND_OPEN" ;;
    *Say-my-name-front*"--state merged"*) cat "$FRONTEND_MERGED" ;;
    *agent-factory*"--state open"*) cat "$FACTORY_OPEN" ;;
    *agent-factory*"--state merged"*) cat "$FACTORY_MERGED" ;;
    *) echo '[]' ;;
  esac
  exit 0
fi
if [[ ${1:-} == pr && ${2:-} == view ]]; then
  jq -c --arg n "${3:-}" '.[$n] // empty' "$PR_VIEWS"
  exit 0
fi
exit 0
STUB

cat > "$TMP/bin/gc" <<'STUB'
#!/usr/bin/env bash
set -Eeuo pipefail
case "$PWD" in
  */rigs/saymyname-backend*) store=$BACKEND_BEADS; scope=backend ;;
  */rigs/saymyname-frontend*) store=$FRONTEND_BEADS; scope=frontend ;;
  *) store=$FACTORY_BEADS; scope=factory ;;
esac
printf '%s %s\n' "$scope" "$*" >> "$GC_LOG"

if [[ ${1:-} == bd && ${2:-} == list ]]; then
  rows=$(cat "$store")
  if [[ "$*" == *"--status open"* ]]; then
    rows=$(jq '[.[] | select(.status == "open")]' <<<"$rows")
  fi
  printf '%s\n' "$rows"
  exit 0
fi

if [[ ${1:-} == bd && ${2:-} == update ]]; then
  id=${3:-}
  shift 3
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --set-metadata)
        assignment=${2:-}; key=${assignment%%=*}; value=${assignment#*=}
        next="$store.next"
        jq --arg id "$id" --arg key "$key" --arg value "$value" \
          'map(if .id == $id then .metadata = ((.metadata // {}) + {($key):$value}) else . end)' \
          "$store" > "$next"
        mv "$next" "$store"
        shift 2
        ;;
      --status=*)
        value=${1#--status=}; next="$store.next"
        jq --arg id "$id" --arg value "$value" \
          'map(if .id == $id then .status = $value else . end)' "$store" > "$next"
        mv "$next" "$store"
        shift
        ;;
      --status)
        value=${2:-}; next="$store.next"
        jq --arg id "$id" --arg value "$value" \
          'map(if .id == $id then .status = $value else . end)' "$store" > "$next"
        mv "$next" "$store"
        shift 2
        ;;
      --notes|--append-notes) shift 2 ;;
      *) shift ;;
    esac
  done
  exit 0
fi

if [[ ${1:-} == bd && ${2:-} == create ]]; then exit 0; fi
if [[ ${1:-} == mail && ${2:-} == send ]]; then exit 0; fi
exit 0
STUB

cat > "$TMP/bin/check" <<'STUB'
#!/usr/bin/env bash
exit 0
STUB

chmod +x "$TMP/bin/gh" "$TMP/bin/gc" "$TMP/bin/check"
export PATH="$TMP/bin:$PATH"
export FACTORY_ROOT="$TMP/factory"
export REVERSIBILITY_CHECK_BIN="$TMP/bin/check"
export REVERSIBILITY_CACHE="$TMP/factory/.gc/reversibility-cache.tsv"
export PR_AUTOPILOT_NOW_EPOCH
PR_AUTOPILOT_NOW_EPOCH=$(date -u -d '2026-09-21T16:00:00Z' +%s)
export PR_AUTOPILOT_RECONCILE_WAKE_WINDOW_SECONDS=3600

pilot() { "$AUTOPILOT" "$@" 2>&1 || true; }
update_for() { grep -F "bd update $1 " "$GC_LOG" || true; }
mail_for() { grep -F "mail send mayor --from pr-autopilot --notify --subject SHIPPED: $1 " "$GC_LOG" || true; }

# Dry-run observes every case but never writes delivery, projection, or mail.
: > "$GC_LOG"
pilot --dry-run >/dev/null
grep -q ' bd update ' "$GC_LOG" && fail "--dry-run wrote Beads state"
grep -q ' mail send ' "$GC_LOG" && fail "--dry-run sent mail"

# Real reconciliation: both direct and workflow sources go through
# deliver-close and receive all six proof fields atomically.
: > "$GC_LOG"
out=$(pilot)
for id in smb-source smb-direct smf-source; do
  call=$(update_for "$id")
  [[ $call == *"gc.delivery_status=merged"* ]] || fail "$id missing gc.delivery_status"
  [[ $call == *"gc.work_outcome=shipped"* ]] || fail "$id missing gc.work_outcome"
  [[ $call == *"gc.github_repo="* ]] || fail "$id missing gc.github_repo"
  [[ $call == *"gc.pr_number="* ]] || fail "$id missing gc.pr_number"
  [[ $call == *"gc.pr_head="* ]] || fail "$id missing gc.pr_head"
  [[ $call == *"gc.merge_commit="* ]] || fail "$id missing gc.merge_commit"
  [[ $call == *"--status=closed"* ]] || fail "$id was not deliver-closed"
  [ "$(mail_for "$id" | wc -l)" = "1" ] || fail "$id did not get exactly one completion wake"
done

# The build root wins over other rows sharing its branch, but only the one
# child explicitly tracked by gc.var.convoy_id is delivered.
[ -z "$(update_for smb-unrelated)" ] || fail "branch collision closed an unrelated bead"
grep -q 'bd update smb-root .*merge_result=merged' "$GC_LOG" \
  || fail "build workflow root did not receive the legacy merge projection"
grep -q 'bd update smf-root .*merge_result=merged' "$GC_LOG" \
  || fail "cross-rig frontend workflow root was not reconciled"
grep -q '^frontend bd update smf-source ' "$GC_LOG" \
  || fail "frontend source was not deliver-closed inside its own rig"

# Closing the true blocker is the Beads transition that makes its waiting
# dependent eligible; the waiter and its explicit blocks edge remain intact.
jq -e '
  (map(select(.id == "smb-source"))[0].status == "closed") and
  (map(select(.id == "smb-waiter"))[0] as $w
    | $w.status == "open"
    and any($w.dependencies[]; .depends_on_id == "smb-source" and .type == "blocks"))
' "$BACKEND_BEADS" >/dev/null || fail "waiting dependent was not released by closing its real source blocker"

# Non-delivery cases stay untouched. A failed workflow may record that its PR
# merged, but it never turns that into source delivery.
[ -z "$(update_for smb-failedsource)" ] || fail "failed workflow closed its source"
grep -q 'bd update smb-failedroot .*merge_result=merged' "$GC_LOG" \
  || fail "failed workflow did not retain the factual legacy merge projection"
[ -z "$(update_for smb-ambiguousa)$(update_for smb-ambiguousb)" ] \
  || fail "ambiguous convoy closed one of several possible sources"
grep -q 'source_convoy_not_exactly_one' <<<"$out" \
  || fail "ambiguous convoy was not reported"
[ -z "$(update_for smb-closedsource)" ] || fail "closed-unmerged PR closed its source"
grep -q 'not verifiably merged' <<<"$out" \
  || fail "closed-unmerged PR was not rejected by deliver-close"
[ -z "$(update_for smb-red)$(update_for smb-open)" ] \
  || fail "open/red PR produced delivery proof"

# Keep only successful merged PRs. State written above now contains both the
# source proof and anchor projection; a retry must be entirely silent.
jq '[.[] | select(.number == 11 or .number == 12)]' "$BACKEND_MERGED" > "$BACKEND_MERGED.next"
mv "$BACKEND_MERGED.next" "$BACKEND_MERGED"
printf '[]\n' > "$BACKEND_OPEN"
: > "$GC_LOG"
pilot >/dev/null
grep -q ' bd update ' "$GC_LOG" && fail "idempotent retry rewrote delivery state"
grep -q ' mail send ' "$GC_LOG" && fail "idempotent retry sent a second completion wake"

echo "OK pr-autopilot deliver-closes explicit workflow sources after verified merges"
