#!/usr/bin/env bash
#
# af-i3k3f (B02): a live measurement on 2026-09-24 showed one pr-autopilot
# tick (three repos) taking 100-107s against the order's 100s soft / 120s
# hard (SIGKILL, no trace) budget -- almost entirely spent re-verifying
# already-terminal merged PRs with a fresh `gc bd show` on EVERY tick,
# forever (PR #209's fix, correct but unbounded). This drives pr-autopilot
# against stub gh/gc binaries across TWO ticks and proves: a merged PR's
# bead, once actually observed status=closed live, is never re-checked via
# `gc bd show` on a later tick -- only new, not-yet-cached merges still pay
# that cost.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory/rigs/example-backend" "$TMP/factory/rigs/example-frontend" "$TMP/bin"
: > "$TMP/gh.log"; : > "$TMP/gc.log"

cat > "$TMP/open.json" <<'JSON'
[]
JSON
# PR 61 (branch b61, bead af-done): snapshot and live store agree it is
# closed and proven, both ticks.
cat > "$TMP/merged.json" <<'JSON'
[
 {"number":61,"headRefName":"b61","mergeCommit":{"oid":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},"mergedAt":"2026-09-24T00:41:00Z"}
]
JSON
cat > "$TMP/all_beads.json" <<'JSON'
[
 {"id":"af-done","status":"closed","title":"work delivered by PR 61","metadata":{"gc.work_branch":"b61","gc.delivery_contract":"pr-ci-merged-v1","gc.plane":"delivery","gc.graph_digest":"sha256:deadbeef","merge_result":"merged","merged_sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","gc.merge_commit":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","merged_target":"main","gc.pr_url":"https://github.com/example-corp/example-app/pull/61","gc.github_repo":"example-corp/example-app","gc.pr_number":"61","gc.pr_head":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","gc.delivery_status":"merged","gc.work_outcome":"shipped","gc.required_ci_workflow":"Factory CI","gc.ci_run_id":"2","gc.ci_head_sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","gc.ci_conclusion":"success"}}
]
JSON
cat > "$TMP/show_done.json" <<'JSON'
[{"id":"af-done","status":"closed"}]
JSON

cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ "\$1" == pr && "\$2" == list ]]; then
  if [[ "\$*" != *"example-backend"* ]]; then echo '[]'; exit 0; fi
  if [[ "\$*" == *"--state open"* ]]; then cat "$TMP/open.json";
  elif [[ "\$*" == *"--state merged"* ]]; then cat "$TMP/merged.json";
  else echo '[]'; fi
  exit 0
fi
if [[ "\$1" == pr && "\$2" == view ]]; then echo '["OPEN","false"]' | jq -r '@tsv'; exit 0; fi
exit 0
STUB
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gc.log"
if [[ "\$1" == bd && "\$2" == list && "\$*" == *"--status open"* ]]; then echo '[]'; exit 0; fi
if [[ "\$1" == bd && "\$2" == list && "\$*" == *"--all"* ]]; then cat "$TMP/all_beads.json"; exit 0; fi
if [[ "\$1" == bd && "\$2" == show ]]; then
  case " \$* " in
    *" af-done "*)  cat "$TMP/show_done.json" ;;
    *) echo '[]' ;;
  esac
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
export PROTECTED_RIGS_CONFIG_DIR="$REPO_ROOT/tests/fixtures/pr-autopilot-projects"
export PR_AUTOPILOT_RECONCILE_CACHE="$TMP/factory/.gc/pr-autopilot-reconciled-cache.tsv"

pilot() { "$AUTOPILOT" "$@" 2>&1 || true; }

# Tick 1: no cache yet -> af-done's live status IS checked once, and the
# confirmation is cached.
out1=$(pilot)
grep -q "^bd show af-done --json$" "$TMP/gc.log" \
  || { echo "$out1" >&2; fail "tick 1 never verified af-done's live status before trusting the snapshot"; }
[ -f "$PR_AUTOPILOT_RECONCILE_CACHE" ] && grep -qF "example-corp/example-backend#61	af-done" "$PR_AUTOPILOT_RECONCILE_CACHE" \
  || fail "tick 1 did not record af-done's verified-closed status in the reconcile cache"

# Tick 2: same merged PR, same snapshot -> af-done must be skipped WITHOUT a
# second `gc bd show` call. Reset gc.log so tick 2's calls are isolated.
: > "$TMP/gc.log"
out2=$(pilot)
grep -q "af-done" "$TMP/gc.log" \
  && { echo "$out2" >&2; fail "tick 2 re-checked af-done's live status despite it already being cached as verified-closed"; }

echo "OK pr-autopilot caches a live-verified terminal PR and skips the repeat gc bd show on later ticks"
