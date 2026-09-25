#!/usr/bin/env bash
# af-qaogn: build-basic's publish step must file a follow-up bead when it hits
# the overlapping/duplicate-content worktree no-op fallback, instead of only
# leaving a silent log line — an approved, all-REQs-covered result must never
# depend on a human or the ladder noticing it went unmerged.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
PUBLISH_MD="$ROOT/assets/workflows/build-basic/publish.md"

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

[ -f "$PUBLISH_MD" ] || fail "publish.md not found at $PUBLISH_MD"

grep -qi 'overlapping' "$PUBLISH_MD" \
  || fail "publish.md does not mention the overlapping-worktree fallback"

grep -q 'gc bd create' "$PUBLISH_MD" \
  || fail "publish.md's overlapping-worktree fallback does not file a follow-up bead (no 'gc bd create')"

grep -q 'gc.publish_followup_bead_id' "$PUBLISH_MD" \
  || fail "publish.md does not record the follow-up bead id on the workflow root"

grep -q 'af-1c3yy' "$PUBLISH_MD" \
  || fail "publish.md does not cite the design decision (af-1c3yy) against auto-merge/auto-PR"

# The fallback must not silently swap in an auto-merge/auto-PR instead of
# filing a bead — out of scope per af-1c3yy.
if grep -qi 'automated N-way merge' "$PUBLISH_MD" && ! grep -qi 'do not attempt' "$PUBLISH_MD"; then
  fail "publish.md mentions an N-way merge without explicitly forbidding it"
fi

echo "PASS: build-basic publish.md files a follow-up bead on the overlapping-worktree no-op fallback"
