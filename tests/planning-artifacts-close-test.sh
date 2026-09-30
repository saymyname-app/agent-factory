#!/usr/bin/env bash
#
# bin/planning-artifacts-close (W06, A6b): when a convoy closes, its Spec
# bead and the Ticket Graph Draft bead it was published from close too, with
# a reason naming the convoy. Both stay open and readable while the convoy
# is still open. A convoy published from a file draft (earlier graphs, whose
# gc.artifact_id/gc.spec_id are plain strings, not bead ids) is left
# untouched without error.
#
# All bead ids here are synthetic fixtures (zz-fixture*), never a real af-*
# id from the live store.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
TOOL="$REPO_ROOT/bin/planning-artifacts-close"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

export CONVOYS_FILE="$TMP/closed_convoys.json"; echo '[]' > "$CONVOYS_FILE"
export SHOW_FILE="$TMP/show_beads.json"; echo '{}' > "$SHOW_FILE"
export CLOSE_LOG="$TMP/closes.log"; : > "$CLOSE_LOG"
mkdir -p "$TMP/bin"

# --- stub gc: serves `bd list --type convoy --status closed`/`bd show` from
# the fixture files, records `bd close` calls and reflects them into
# SHOW_FILE so a second run of the tool sees the target already closed -----
cat > "$TMP/bin/gc" <<'STUB'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ ${1:-} == bd && ${2:-} == list ]]; then
  cat "$CONVOYS_FILE"
  exit 0
fi
if [[ ${1:-} == bd && ${2:-} == show ]]; then
  id=$3
  jq -e --arg id "$id" '.[$id] // empty' "$SHOW_FILE" || echo '{}'
  exit 0
fi
if [[ ${1:-} == bd && ${2:-} == close ]]; then
  id=$3
  reason=""
  shift 3
  while [ $# -gt 0 ]; do
    case "$1" in
      --reason) reason=$2; shift 2 ;;
      *) shift ;;
    esac
  done
  printf '%s\t%s\n' "$id" "$reason" >> "$CLOSE_LOG"
  tmp=$(mktemp)
  jq --arg id "$id" '.[$id].status = "closed"' "$SHOW_FILE" > "$tmp" && mv "$tmp" "$SHOW_FILE"
  exit 0
fi
echo "unexpected gc invocation: $*" >&2
exit 64
STUB
chmod +x "$TMP/bin/gc"

export PATH="$TMP/bin:$PATH"
export GC_BIN="$TMP/bin/gc"
export FACTORY_ROOT="$TMP"

run_tool() { "$TOOL" "$@" 2>&1; }
close_count() { grep -c "^$1"$'\t' "$CLOSE_LOG" 2>/dev/null || true; }
bead_status() { jq -r --arg id "$1" '.[$id].status // "missing"' "$SHOW_FILE"; }

# =============================================================================
# 1. Convoy still open: bd list --status closed never returns it, so its
#    Spec/Draft beads are never touched.
# =============================================================================

jq -n '{
  "zz-fixture-spec-open": {"id": "zz-fixture-spec-open", "status": "open"},
  "zz-fixture-draft-open": {"id": "zz-fixture-draft-open", "status": "open"}
}' > "$SHOW_FILE"
echo '[]' > "$CONVOYS_FILE"   # the open convoy is not "closed", so bd list returns nothing for it
: > "$CLOSE_LOG"

out=$(run_tool)
grep -q "closed=0 skipped=0 failed=0" <<<"$out" || { echo "$out" >&2; fail "expected a no-op run while the convoy is open"; }
[ "$(bead_status zz-fixture-spec-open)" = "open" ] || fail "Spec bead was touched while its convoy is still open"
[ "$(bead_status zz-fixture-draft-open)" = "open" ] || fail "Draft bead was touched while its convoy is still open"

# =============================================================================
# 2. Convoy closed, bead mode: gc.artifact_id/gc.spec_id resolve to real
#    beads -- both close with a reason naming the convoy.
# =============================================================================

jq -n '{
  "zz-fixture-spec-1": {"id": "zz-fixture-spec-1", "status": "open"},
  "zz-fixture-draft-1": {"id": "zz-fixture-draft-1", "status": "open"}
}' > "$SHOW_FILE"
jq -n '[{
  "id": "zz-fixture-convoy-1", "title": "Fixture Convoy One", "status": "closed",
  "metadata": {"gc.artifact_id": "zz-fixture-draft-1", "gc.spec_id": "zz-fixture-spec-1"}
}]' > "$CONVOYS_FILE"
: > "$CLOSE_LOG"

out=$(run_tool)
grep -q "closed=2 skipped=0 failed=0" <<<"$out" || { echo "$out" >&2; fail "expected both Spec and Draft beads to close"; }
[ "$(bead_status zz-fixture-spec-1)" = "closed" ] || fail "Spec bead did not close when its convoy closed"
[ "$(bead_status zz-fixture-draft-1)" = "closed" ] || fail "Draft bead did not close when its convoy closed"
[ "$(close_count zz-fixture-spec-1)" = "1" ] || fail "expected exactly one close call for the Spec bead"
[ "$(close_count zz-fixture-draft-1)" = "1" ] || fail "expected exactly one close call for the Draft bead"
grep -q "^zz-fixture-spec-1"$'\t'".*zz-fixture-convoy-1" "$CLOSE_LOG" \
  || fail "close reason for the Spec bead does not name the convoy"
grep -q "^zz-fixture-draft-1"$'\t'".*zz-fixture-convoy-1" "$CLOSE_LOG" \
  || fail "close reason for the Draft bead does not name the convoy"

# --- idempotent: a second run over the same already-closed convoy touches
# nothing further --------------------------------------------------------
: > "$CLOSE_LOG"
out=$(run_tool)
grep -q "closed=0 skipped=2 failed=0" <<<"$out" || { echo "$out" >&2; fail "a re-run over an already-closed convoy should skip, not re-close"; }
[ "$(close_count zz-fixture-spec-1)" = "0" ] || fail "re-closed an already-closed Spec bead"
[ "$(close_count zz-fixture-draft-1)" = "0" ] || fail "re-closed an already-closed Draft bead"

# =============================================================================
# 2b. Spec handoff: the Spec bead was claimed for /to-tickets and is still
#     in_progress and assigned when its convoy closes -- it closes like an
#     open one.
# =============================================================================

jq -n '{
  "zz-fixture-spec-claimed": {"id": "zz-fixture-spec-claimed", "status": "in_progress",
    "assignee": "po-agent/zz-fixture-session",
    "metadata": {"wayfinder.offered_by": "po-agent/zz-fixture-offerer"}},
  "zz-fixture-draft-3": {"id": "zz-fixture-draft-3", "status": "open"}
}' > "$SHOW_FILE"
jq -n '[{
  "id": "zz-fixture-convoy-3", "title": "Fixture Convoy Three", "status": "closed",
  "metadata": {"gc.artifact_id": "zz-fixture-draft-3", "gc.spec_id": "zz-fixture-spec-claimed"}
}]' > "$CONVOYS_FILE"
: > "$CLOSE_LOG"

out=$(run_tool)
grep -q "closed=2 skipped=0 failed=0" <<<"$out" || { echo "$out" >&2; fail "expected the claimed Spec and its Draft to close"; }
[ "$(bead_status zz-fixture-spec-claimed)" = "closed" ] || fail "a claimed (in_progress, assigned) Spec bead did not close with its convoy"

# =============================================================================
# 3. Convoy closed, file-draft mode: gc.artifact_id/gc.spec_id are plain
#    identifier strings from a draft YAML, not bead ids -- `bd show` never
#    resolves them, so the convoy is left untouched, without error.
# =============================================================================

echo '{}' > "$SHOW_FILE"   # no bead in the store for the file-mode artifact/spec ids
jq -n '[{
  "id": "zz-fixture-convoy-2", "title": "Fixture Convoy Two (file draft)", "status": "closed",
  "metadata": {
    "gc.artifact_id": "ticket-graph-draft-zz-fixture",
    "gc.spec_id": "spec-zz-fixture-2026-09-30"
  }
}]' > "$CONVOYS_FILE"
: > "$CLOSE_LOG"

rc=0
out=$(run_tool) || rc=$?
[ "$rc" -eq 0 ] || { echo "$out" >&2; fail "a file-draft convoy must not error"; }
grep -q "closed=0 skipped=0 failed=0" <<<"$out" || { echo "$out" >&2; fail "a file-draft convoy's artifact/spec ids must be left untouched"; }
[ -s "$CLOSE_LOG" ] && fail "attempted to close a file-draft artifact/spec id"

echo "PASS: planning-artifacts-close (open convoy untouched, bead-mode closes idempotently, claimed Spec closes, file-draft mode untouched without error)"
