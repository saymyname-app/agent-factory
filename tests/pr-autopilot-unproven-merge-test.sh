#!/usr/bin/env bash
#
# af-65mbq2: PR #876 was merged into an integration branch with no run of the
# required workflow on its head; deliver-close refused its ticket on every
# pass and pr-autopilot counted that refusal as an order error each time, so
# the order failed every 3 minutes for hours. A merged PR's refused proof is a
# finding filed once (reopened if its bead was closed), not an order error;
# a finding that cannot be filed still fails the order.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory/rigs/example-backend" "$TMP/factory/rigs/example-frontend" "$TMP/bin"

cat > "$TMP/merged.json" <<'JSON'
[
 {"number":61,"headRefName":"b61","mergeCommit":{"oid":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"},"mergedAt":"2026-11-13T08:09:25Z"}
]
JSON
WORK='{"id":"af-wip","status":"in_progress","title":"work of PR 61","metadata":{"gc.work_branch":"b61","gc.delivery_contract":"pr-ci-merged-v1"}}'
TITLE="[autopilot] PR #61 merged without delivery proof for af-wip"

cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
if [[ "\$1" == pr && "\$2" == list ]]; then
  if [[ "\$*" == *"example-backend"* && "\$*" == *"--state merged"* ]]; then cat "$TMP/merged.json"; else echo '[]'; fi
  exit 0
fi
exit 0
STUB
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gc.log"
if [[ "\$1" == bd && "\$2" == list && "\$*" == *"--status open"* ]]; then cat "$TMP/open.json"; exit 0; fi
if [[ "\$1" == bd && "\$2" == list && "\$*" == *"--all"* ]]; then cat "$TMP/all.json"; exit 0; fi
if [[ "\$1" == bd && ( "\$2" == create || "\$2" == update ) ]]; then exit "\$(cat "$TMP/write_rc")"; fi
exit 0
STUB
cat > "$TMP/bin/deliver-close" <<'STUB'
#!/usr/bin/env bash
echo "deliver-close: ERROR: Required workflow 'Factory CI' has no pull_request run on exact PR head bbbb." >&2
exit 1
STUB
chmod +x "$TMP/bin/"*
export PATH="$TMP/bin:$PATH"
export FACTORY_ROOT="$TMP/factory"
export GC_PR_AUTHORS=example-operator
export REVERSIBILITY_CHECK_BIN="$TMP/bin/gh"
export DELIVER_CLOSE_BIN="$TMP/bin/deliver-close"
export PROTECTED_RIGS_CONFIG_DIR="$REPO_ROOT/tests/fixtures/pr-autopilot-projects"
export PR_AUTOPILOT_RECONCILE_CACHE="$TMP/factory/.gc/pr-autopilot-reconciled-cache.tsv"

# pass <open beads json> <all beads json> <rc of a bead write>: one pass, its exit code in $rc.
pass() {
  printf '%s' "$1" > "$TMP/open.json"; printf '%s' "$2" > "$TMP/all.json"; echo "$3" > "$TMP/write_rc"
  : > "$TMP/gc.log"
  rc=0; out=$("$AUTOPILOT" 2>&1) || rc=$?
}

# First refusal: one finding filed with deliver-close's reason, the order passes.
pass "[$WORK]" "[$WORK]" 0
[ "$rc" = 0 ] || { echo "$out" >&2; fail "a refused merged PR failed the order (exit $rc)"; }
grep -qF "bd create $TITLE -p 1 -t bug" "$TMP/gc.log" || { echo "$out" >&2; fail "no finding was filed for the refused merged PR"; }
grep -qF "has no pull_request run on exact PR head bbbb" "$TMP/gc.log" || fail "the finding does not carry deliver-close's reason"

# Next pass, finding still open: nothing filed again, the order passes.
FLAG='{"id":"af-flag","status":"open","title":"'"$TITLE"'","metadata":{"source":"pr-autopilot","pr_number":"61"}}'
pass "[$WORK,$FLAG]" "[$WORK,$FLAG]" 0
[ "$rc" = 0 ] || { echo "$out" >&2; fail "an already filed refusal failed the order (exit $rc)"; }
grep -qE "bd (create|update) " "$TMP/gc.log" && { echo "$out" >&2; fail "an already filed refusal was filed again"; }

# Finding closed while the ticket is still refused: the same bead is reopened.
CLOSED='{"id":"af-flag","status":"closed","title":"'"$TITLE"'","metadata":{"source":"pr-autopilot","pr_number":"61"}}'
pass "[$WORK]" "[$WORK,$CLOSED]" 0
[ "$rc" = 0 ] || { echo "$out" >&2; fail "a reopened finding failed the order (exit $rc)"; }
grep -qF "bd update af-flag --status open" "$TMP/gc.log" || { echo "$out" >&2; fail "the closed finding was not reopened"; }
grep -qF "bd create " "$TMP/gc.log" && fail "a second finding was filed instead of reopening the closed one"

# A finding that cannot be filed still fails the order.
pass "[$WORK]" "[$WORK]" 1
[ "$rc" = 1 ] || { echo "$out" >&2; fail "a refusal that could not be filed did not fail the order (exit $rc)"; }

echo "OK pr-autopilot files a merged PR's refused delivery proof once instead of failing the order every pass"
