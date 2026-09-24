#!/usr/bin/env bash
#
# af-6xs2n: af-cfl9j (PR#206) and af-i3k3f (PR#210) each sat merged,
# exact-head CI green, and stuck status=in_progress -- a direct `gc bd show`
# on the real work bead always reported the correct in_progress status, yet
# pr-autopilot's own candidate query kept resolving to a DIFFERENT bead that
# looked "already terminal", so the real bead was never reconciled. PR #216
# fixed the one reproduced instance of this (a step-tracking wisp sharing
# gc.work_branch); this test proves the same failure mode is closed for the
# broader class -- ANY other bead that happens to share the merged PR's
# gc.work_branch, with no gc.step_ref at all, and is already closed. Without
# a tiebreak, `[0]` could still land on that already-closed decoy first and
# skip the real, still in_progress work bead forever. Drives pr-autopilot
# against stub gh/gc binaries and proves the still-open real bead is always
# preferred and reconciled, never the closed decoy.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory/rigs/saymyname-backend" "$TMP/factory/rigs/saymyname-frontend" "$TMP/bin"
: > "$TMP/gh.log"; : > "$TMP/gc.log"

cat > "$TMP/open.json" <<'JSON'
[]
JSON
cat > "$TMP/merged.json" <<'JSON'
[
 {"number":80,"headRefName":"do-work/af-real2","mergeCommit":{"oid":"dddddddddddddddddddddddddddddddddddddddd"},"mergedAt":"2026-09-24T00:40:00Z"}
]
JSON
# af-decoy is an ordinary (non-wisp, no gc.step_ref) closed bead that
# happens to carry the same gc.work_branch as the real, still in_progress
# ticket af-real2 -- e.g. a stale/duplicate record. It sorts before af-real2
# in the snapshot on purpose, so a naive `[0]` pick would land on it.
cat > "$TMP/all_beads.json" <<'JSON'
[
 {"id":"af-decoy","status":"closed","title":"an unrelated already-closed bead","metadata":{"gc.work_branch":"do-work/af-real2"}},
 {"id":"af-real2","status":"in_progress","title":"the real ticket","metadata":{"gc.work_branch":"do-work/af-real2","gc.delivery_contract":"pr-ci-merged-v1","gc.plane":"delivery","gc.graph_digest":"sha256:deadbeef"}}
]
JSON
cat > "$TMP/show_real.json" <<'JSON'
[{"id":"af-real2","status":"in_progress"}]
JSON

cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ "\$1" == pr && "\$2" == list ]]; then
  if [[ "\$*" != *"Say-my-name-back"* ]]; then echo '[]'; exit 0; fi
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
    *" af-real2 "*) cat "$TMP/show_real.json" ;;
    *" af-decoy "*) echo '[{"id":"af-decoy","status":"closed"}]' ;;
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

pilot() { "$AUTOPILOT" "$@" 2>&1 || true; }
out=$(pilot)

grep -q "^bd update af-real2 .*--status=closed$" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "the real work bead af-real2 was never reconciled -- the closed decoy shadowed it"; }
grep -q "^bd update af-decoy " "$TMP/gc.log" \
  && { echo "$out" >&2; fail "the already-closed decoy af-decoy was reconciled instead of the real, still open work bead"; }

echo "OK pr-autopilot prefers the still-open real work bead over an already-closed duplicate match, never the reverse"
