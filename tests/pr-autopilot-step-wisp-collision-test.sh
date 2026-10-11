#!/usr/bin/env bash
#
# af-q7r0d (B04) sat merged, CI-proven, and stuck status=in_progress for 1h+
# on 2026-09-24 because pr-autopilot's RECONCILE candidate query matches any
# bead carrying gc.work_branch == the merged PR's branch -- and a graph.v2
# formula step-tracking wisp (gc.step_ref set) copies that same
# gc.work_branch onto itself for its own bookkeeping. With two beads
# matching, `[0]` picked the wisp (af-unzig) instead of the real work bead
# (af-q7r0d): it stamped merge_result=merged onto the wisp, which then
# looked terminal to nobody, and the real ticket was never reconciled --
# silently stranding every dependent ticket behind it in a convoy chain.
# This drives pr-autopilot against stub gh/gc binaries and proves: when a
# step wisp and the real work bead both carry a matching gc.work_branch, the
# real work bead (no gc.step_ref) is the one reconciled -- never the wisp.

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
cat > "$TMP/merged.json" <<'JSON'
[
 {"number":70,"headRefName":"do-work/af-real","mergeCommit":{"oid":"cccccccccccccccccccccccccccccccccccccccc"},"mergedAt":"2026-09-24T00:40:00Z"}
]
JSON
# af-wisp is a step-tracking wisp (gc.step_ref set) that shares the exact
# same gc.work_branch as the real ticket af-real for its own bookkeeping --
# the live collision shape seen on af-unzig/af-q7r0d. It sorts before
# af-real in the snapshot on purpose, so a naive `[0]` pick would land on it.
cat > "$TMP/all_beads.json" <<'JSON'
[
 {"id":"af-wisp","status":"closed","title":"Read assignment; on the HQ rig, isolate work in a worktree","metadata":{"gc.work_branch":"do-work/af-real","gc.step_ref":"mol-do-work.workspace-setup","gc.root_bead_id":"af-workflow","gc.work_bead_id":"af-real"}},
 {"id":"af-real","status":"in_progress","title":"the real ticket","metadata":{"gc.work_branch":"do-work/af-real","gc.delivery_contract":"pr-ci-merged-v1","gc.plane":"delivery","gc.graph_digest":"sha256:deadbeef"}}
]
JSON
cat > "$TMP/show_real.json" <<'JSON'
[{"id":"af-real","status":"in_progress"}]
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
    *" af-real "*) cat "$TMP/show_real.json" ;;
    *" af-wisp "*) echo '[{"id":"af-wisp","status":"closed"}]' ;;
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

grep -q "^bd update af-real .*--status=closed$" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "the real work bead af-real was never reconciled -- the step wisp shadowed it"; }
grep -q "^bd update af-wisp " "$TMP/gc.log" \
  && { echo "$out" >&2; fail "the step-tracking wisp af-wisp was reconciled instead of the real work bead"; }

echo "OK pr-autopilot reconciles the real work bead, never a step-tracking wisp sharing its gc.work_branch"
