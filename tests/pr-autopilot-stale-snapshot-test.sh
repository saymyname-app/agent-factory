#!/usr/bin/env bash
#
# af-cfl9j (B01) sat merged, CI-proven, and stuck status=in_progress for 1h40
# on 2026-09-24: pr-autopilot's RECONCILE loop reads its whole bead snapshot
# once per tick (af-k1f97, a real perf need), and that snapshot said the
# delivery was "already terminal and proven" -- so it was skipped, forever,
# without anyone ever calling the one door that actually closes the bead.
# This drives pr-autopilot against stub gh/gc binaries and proves: when the
# once-per-tick snapshot claims a merged PR's bead is already terminal, a
# fresh `gc bd show` is consulted before trusting that and skipping -- if the
# live bead is NOT actually closed, reconciliation proceeds for real instead
# of silently skipping again. A genuinely closed live bead is still skipped
# with no wasted work.

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
# PR 60 (branch b60, bead af-stale): the once-per-tick snapshot says
# status=closed with full proof (looks terminal) -- but the live store says
# in_progress (stale snapshot, the actual bug shape). Must reconcile for real.
# PR 61 (branch b61, bead af-done): snapshot AND live store agree it is
# closed and proven -- must be skipped with no reconcile call.
cat > "$TMP/merged.json" <<'JSON'
[
 {"number":60,"headRefName":"b60","mergeCommit":{"oid":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},"mergedAt":"2026-09-24T00:40:00Z"},
 {"number":61,"headRefName":"b61","mergeCommit":{"oid":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},"mergedAt":"2026-09-24T00:41:00Z"}
]
JSON
cat > "$TMP/all_beads.json" <<'JSON'
[
 {"id":"af-stale","status":"closed","title":"work delivered by PR 60","metadata":{"gc.work_branch":"b60","gc.delivery_contract":"pr-ci-merged-v1","gc.plane":"delivery","gc.graph_digest":"sha256:deadbeef","merge_result":"merged","merged_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","gc.merge_commit":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","merged_target":"main","gc.pr_url":"https://github.com/example-corp/example-app/pull/60","gc.github_repo":"example-corp/example-app","gc.pr_number":"60","gc.pr_head":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","gc.delivery_status":"merged","gc.work_outcome":"shipped","gc.required_ci_workflow":"Factory CI","gc.ci_run_id":"1","gc.ci_head_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","gc.ci_conclusion":"success"}},
 {"id":"af-done","status":"closed","title":"work delivered by PR 61","metadata":{"gc.work_branch":"b61","gc.delivery_contract":"pr-ci-merged-v1","gc.plane":"delivery","gc.graph_digest":"sha256:deadbeef","merge_result":"merged","merged_sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","gc.merge_commit":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","merged_target":"main","gc.pr_url":"https://github.com/example-corp/example-app/pull/61","gc.github_repo":"example-corp/example-app","gc.pr_number":"61","gc.pr_head":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","gc.delivery_status":"merged","gc.work_outcome":"shipped","gc.required_ci_workflow":"Factory CI","gc.ci_run_id":"2","gc.ci_head_sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","gc.ci_conclusion":"success"}}
]
JSON
# Live `gc bd show` disagrees with the snapshot for af-stale (in_progress),
# and agrees for af-done (closed).
cat > "$TMP/show_stale.json" <<'JSON'
[{"id":"af-stale","status":"in_progress"}]
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
    *" af-stale "*) cat "$TMP/show_stale.json" ;;
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
export GC_PR_AUTHORS=example-operator
export REVERSIBILITY_CHECK_BIN="$TMP/bin/gh"
export DELIVER_CLOSE_BIN="$TMP/bin/deliver-close"
export PROTECTED_RIGS_CONFIG_DIR="$REPO_ROOT/tests/fixtures/pr-autopilot-projects"

pilot() { "$AUTOPILOT" "$@" 2>&1 || true; }
out=$(pilot)

# af-stale: snapshot said terminal, live gc bd show says in_progress ->
# pr-autopilot must re-verify (call `gc bd show af-stale`) and reconcile for
# real (call deliver-close), not silently skip a second time.
grep -q "^bd show af-stale --json$" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "af-stale's live status was never re-checked before trusting the stale snapshot"; }
grep -q "^bd update af-stale .*--status=closed$" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "af-stale was not reconciled through deliver-close despite the live status disagreeing"; }

# af-done: snapshot AND live agree closed -> skipped, no reconcile call, but
# the live re-check still happens (cheap, only paid on the terminal path).
grep -q "^bd show af-done --json$" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "af-done's live status was never checked"; }
grep -q "^bd update af-done " "$TMP/gc.log" \
  && { echo "$out" >&2; fail "af-done was reconciled again despite being genuinely closed"; }

echo "OK pr-autopilot re-verifies a stale already-terminal snapshot before trusting it to skip reconciliation"
