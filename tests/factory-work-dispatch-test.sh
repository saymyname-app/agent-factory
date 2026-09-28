#!/usr/bin/env bash
# Regression for af-41ahv: an HQ implementation workflow must route through
# factory-worker, inherit the workspace provider, and keep one resumable slot.
set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
DISPATCH="$REPO_ROOT/bin/factory-work-dispatch"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

CALLS="$TMP/calls"
: > "$CALLS"
cat > "$TMP/gc" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$CALLS"
printf '{"ok":true}\n'
STUB
chmod +x "$TMP/gc"
export CALLS

# O08: dispatch-door checks provider-failover before dispatching; stub it
# available so this test does not depend on this host's live provider state.
cat > "$TMP/provider-failover" <<'STUB'
#!/usr/bin/env bash
printf '{"total_exhaustion":{"active":false}}\n'
STUB
chmod +x "$TMP/provider-failover"
export DISPATCH_DOOR_PROVIDER_FAILOVER_BIN="$TMP/provider-failover"

GC_BIN="$TMP/gc" FACTORY_ROOT="$REPO_ROOT" "$DISPATCH" af-fixture >/dev/null
mapfile -t calls < "$CALLS"
[ "${#calls[@]}" -eq 3 ] || fail "expected a label-check call, a sling call, and a dispatch-door stamp call, got: ${calls[*]-}"
[[ ${calls[0]} == "--city $REPO_ROOT bd show af-fixture --json" ]] \
  || fail "unexpected label-check call: ${calls[0]}"
[[ ${calls[1]} == "--city $REPO_ROOT sling factory-worker af-fixture --on mol-do-work --reassign" ]] \
  || fail "unexpected sling call: ${calls[1]}"
[[ ${calls[2]} == "--city $REPO_ROOT bd update af-fixture --set-metadata gc.dispatched_via=dispatch-door --set-metadata gc.dispatch_formula=mol-do-work --set-metadata gc.dispatch_target=factory-worker --set-metadata gc.dispatch_rig=agent-factory" ]] \
  || fail "unexpected dispatch-door stamp call: ${calls[2]}"

: > "$CALLS"
if GC_BIN="$TMP/gc" FACTORY_ROOT="$REPO_ROOT" "$DISPATCH" bd.dog af-fixture >/dev/null 2>&1; then
  fail "accepted an infrastructure role as an HQ work target"
fi
[ ! -s "$CALLS" ] || fail "called gc after rejecting the infrastructure target"

if GC_BIN="$TMP/gc" FACTORY_ROOT="$REPO_ROOT" "$DISPATCH" af-fixture --on mol-dog-stale-db >/dev/null 2>&1; then
  fail "accepted a Dolt-maintenance formula through the implementation door"
fi
[ ! -s "$CALLS" ] || fail "called gc after rejecting the non-implementation formula"

AGENT_TOML="$REPO_ROOT/agents/factory-worker/agent.toml"
PROMPT="$REPO_ROOT/agents/factory-worker/prompt.template.md"
FORMULA="$REPO_ROOT/formulas/mol-do-work.formula.toml"
grep -q '^scope = "city"$' "$AGENT_TOML" || fail "factory-worker is not city-scoped"
grep -q '^max_active_sessions = 1$' "$AGENT_TOML" || fail "factory-worker is not a singleton"
if grep -q '^wake_mode[[:space:]]*=[[:space:]]*"fresh"' "$AGENT_TOML"; then
  fail "factory-worker discards continuity by forcing a fresh wake"
fi
if grep -q '^provider[[:space:]]*=' "$AGENT_TOML"; then
  fail "factory-worker pins a provider instead of inheriting workspace"
fi
grep -q 'gc hook --claim --json' "$PROMPT" || fail "startup claim protocol missing"
grep -q '^## Continuation Group Protocol$' "$PROMPT" || fail "continuation protocol missing"
grep -qF './bin/factory-work-dispatch' "$REPO_ROOT/agents/mayor/prompt.template.md" \
  || fail "Mayor does not use the guarded HQ dispatch door"

claim_line=$(grep -nF 'gc bd update "$WORK_BEAD_ID" --claim' "$FORMULA" | head -1 | cut -d: -f1)
release_line=$(grep -nF 'gc bd update "$WORK_BEAD_ID" --assignee ""' "$FORMULA" | head -1 | cut -d: -f1)
[ -n "$claim_line" ] && [ -n "$release_line" ] && [ "$release_line" -gt "$claim_line" ] \
  || fail "mol-do-work does not release the target assignee after marking it in progress"
grep -qF 'gc.session_name=${GC_SESSION_NAME:-${GC_AGENT:-}}' "$FORMULA" \
  || fail "mol-do-work loses target session evidence during continuation handoff"

echo "PASS: HQ work dispatch is role-fixed, workspace-inherited, and single-session"
