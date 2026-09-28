#!/usr/bin/env bash
#
# bin/dispatch-door-guard (O03, af-ui0ua): reports any dispatch that
# bypassed bin/dispatch-door -- a bead carrying gc.routed_to (something was
# `gc sling`d to it) with no gc.dispatched_via=dispatch-door stamp. Proves:
# a door-routed bead (carries the stamp) is left alone; a formula-internal
# step bead (gc.step_ref set) is never flagged even with no stamp; a
# graph.v2 workflow root (gc.kind=workflow) is never flagged either; a
# genuine raw-sling bypass is reported, and under --check-only nothing is
# written or paged; a default run marks it reported and pages the Mayor
# exactly once, then a repeat run does not page again; and both the HQ root
# and every product rig from config/projects/ are scanned.
#
# All bead ids here are synthetic fixtures (zz-fixture*), never a real af-*
# id from the live store.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/dispatch-door-guard"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

export HQ_BEADS_FILE="$TMP/hq_beads.json"; echo '[]' > "$HQ_BEADS_FILE"
export RIG_BEADS_FILE="$TMP/rig_beads.json"; echo '[]' > "$RIG_BEADS_FILE"
export UPDATE_LOG="$TMP/updates.log"; : > "$UPDATE_LOG"
export MAIL_LOG="$TMP/mail.log"; : > "$MAIL_LOG"
mkdir -p "$TMP/bin"

cat > "$TMP/bin/gc" <<'STUB'
#!/usr/bin/env bash
set -Eeuo pipefail
rig=""
args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --city) shift 2 ;;
    --rig) rig=$2; shift 2 ;;
    *) args+=("$1"); shift ;;
  esac
done
set -- "${args[@]}"
if [[ ${1:-} == bd && ${2:-} == list ]]; then
  if [[ -n $rig ]]; then cat "$RIG_BEADS_FILE"; else cat "$HQ_BEADS_FILE"; fi
  exit 0
fi
if [[ ${1:-} == bd && ${2:-} == update ]]; then
  id=$3
  shift 3
  printf 'rig=%s %s %s\n' "${rig:-hq}" "$id" "$*" >> "$UPDATE_LOG"
  exit 0
fi
if [[ ${1:-} == mail && ${2:-} == send ]]; then
  printf 'mail-to=%s\n' "$3" >> "$MAIL_LOG"
  exit 0
fi
exit 64
STUB
chmod +x "$TMP/bin/gc"

CONFIG_DIR="$TMP/config/projects"
mkdir -p "$CONFIG_DIR"
cat > "$CONFIG_DIR/zz-fixture-hq.toml" <<'EOF'
rig_dir = "."
repo = "zz-fixture/hq-repo"
protected_branch = "main"
required_ci = "HQ CI"
sling_target = "worker"
formulas = "do-work"
EOF
cat > "$CONFIG_DIR/zz-fixture-rig.toml" <<'EOF'
rig_dir = "rigs/zz-fixture-rig"
repo = "zz-fixture/rig-repo"
protected_branch = "dev"
required_ci = "Rig CI"
sling_target = "claude"
formulas = "do-work,build-basic"
EOF

export GC_BIN="$TMP/bin/gc"
export DISPATCH_DOOR_GUARD_CONFIG_DIR="$CONFIG_DIR"
touch "$TMP/city.toml"

guard() { FACTORY_ROOT="$TMP" "$GUARD" "$@" 2>&1 || true; }
update_count() { grep -c " $1 " "$UPDATE_LOG" 2>/dev/null || true; }
mail_count() { grep -c "^mail-to=$1$" "$MAIL_LOG" 2>/dev/null || true; }

door_routed='{
  "id": "zz-fixture-door-routed", "status": "in_progress",
  "metadata": {"gc.routed_to": "worker", "gc.dispatched_via": "dispatch-door"}
}'
formula_step='{
  "id": "zz-fixture-step", "status": "in_progress",
  "metadata": {"gc.routed_to": "worker", "gc.step_ref": "mol-do-work.workspace-setup"}
}'
workflow_root='{
  "id": "zz-fixture-workflow-root", "status": "in_progress",
  "metadata": {"gc.routed_to": "worker", "gc.kind": "workflow"}
}'
bypass='{
  "id": "zz-fixture-bypass", "status": "in_progress",
  "metadata": {"gc.routed_to": "worker"}
}'

# 1. door-routed, formula-step, and workflow-root beads: never flagged -------
jq -n --argjson a "$door_routed" --argjson b "$formula_step" --argjson c "$workflow_root" \
  '[$a, $b, $c]' > "$HQ_BEADS_FILE"
out=$(guard --check-only)
grep -q "healthy — 3 routed bead(s) checked, no dispatch-door bypass" <<<"$out" \
  || { echo "$out" >&2; fail "door-routed/formula-step/workflow-root beads were not left alone"; }
[ -s "$UPDATE_LOG" ] && fail "touched a bead that never needed touching"
[ "$(mail_count mayor)" = "0" ] || fail "paged the Mayor with nothing wrong"

# 2. a genuine raw-sling bypass: --check-only reports it, writes/pages nothing
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
jq -n --argjson d "$bypass" '[$d]' > "$HQ_BEADS_FILE"
out=$(guard --check-only)
grep -q "zz-fixture-bypass routed to 'worker' with no gc.dispatched_via=dispatch-door stamp" <<<"$out" \
  || { echo "$out" >&2; fail "bypass was not reported under --check-only"; }
grep -q "^UNRESOLVED" <<<"$out" || fail "a real bypass under --check-only must not read as healthy"
[ ! -s "$UPDATE_LOG" ] || fail "--check-only wrote to Beads"
[ "$(mail_count mayor)" = "0" ] || fail "--check-only paged the Mayor"

# 3. default run marks it reported and pages the Mayor exactly once; a
#    repeat run does not page again (the bypass persists -- it is a process
#    violation to fix at the source, not metadata to silently patch) --------
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
out=$(guard)
grep -q "zz-fixture-bypass: routed to 'worker' bypassed the door; paged the Mayor" <<<"$out" \
  || { echo "$out" >&2; fail "bypass was not reported and paged by a default run"; }
[ "$(update_count zz-fixture-bypass)" = "1" ] || fail "expected exactly one stamp write"
[ "$(mail_count mayor)" = "1" ] || fail "expected exactly one page to the Mayor"
grep -q "gc.dispatch_bypass_reported_at=" "$UPDATE_LOG" || fail "did not record when the bypass was reported"

: > "$UPDATE_LOG"; : > "$MAIL_LOG"
# simulate the gc.dispatch_bypass_reported_at stamp landing on the fixture,
# as the prior default run's write would have done for real.
already_reported='{
  "id": "zz-fixture-bypass", "status": "in_progress",
  "metadata": {"gc.routed_to": "worker", "gc.dispatch_bypass_reported_at": "2026-09-28T00:00:00Z"}
}'
jq -n --argjson d "$already_reported" '[$d]' > "$HQ_BEADS_FILE"
out=$(guard)
grep -q "^UNRESOLVED" <<<"$out" || fail "an already-reported bypass must still surface as unresolved"
[ "$(mail_count mayor)" = "0" ] || fail "re-paged the Mayor for an already-reported bypass"

# 4. product rigs from config/projects/ are scanned too ----------------------
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
echo '[]' > "$HQ_BEADS_FILE"
jq -n --argjson d "$bypass" '[($d + {"id": "zz-fixture-rig-bypass"})]' > "$RIG_BEADS_FILE"
out=$(guard)
grep -q "zz-fixture-rig-bypass routed to 'worker' with no gc.dispatched_via=dispatch-door stamp" <<<"$out" \
  || { echo "$out" >&2; fail "a product-rig bypass was not scanned"; }
grep -q "^rig=zz-fixture-rig zz-fixture-rig-bypass " "$UPDATE_LOG" \
  || fail "the stamp write did not go through --rig zz-fixture-rig: $(cat "$UPDATE_LOG")"

echo "PASS: dispatch-door-guard reports raw-sling bypasses, leaves door-routed/formula-step/workflow-root beads alone, and scans every rig"
