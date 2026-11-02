#!/usr/bin/env bash
# Regression for af-41ahv: an HQ implementation workflow must route through
# factory-worker, inherit the workspace provider, and keep resumable slots
# at the configured pool cap (af-puf4p: two concurrent writers on this rig,
# each isolated in its own worktree).
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

cat > "$TMP/convoy-state" <<'STUB'
#!/usr/bin/env bash
printf 'state %s\n' "$*" >> "$CALLS"
[ "$*" != "link-technical-repair af-convoy af-ticket --repair af-refused" ] || exit 1
printf '{"ok":true}\n'
STUB
chmod +x "$TMP/convoy-state"

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
GC_BIN="$TMP/gc" FACTORY_ROOT="$REPO_ROOT" \
  FACTORY_WORK_DISPATCH_CONVOY_STATE_BIN="$TMP/convoy-state" \
  "$DISPATCH" af-repair --technical-request af-convoy af-ticket >/dev/null
mapfile -t calls < "$CALLS"
[ "${#calls[@]}" -eq 4 ] || fail "expected a technical link followed by the ordinary dispatch, got: ${calls[*]-}"
[[ ${calls[0]} == "state link-technical-repair af-convoy af-ticket --repair af-repair" ]] \
  || fail "technical repair was not linked through convoy-state first: ${calls[0]}"
[[ ${calls[2]} == "--city $REPO_ROOT sling factory-worker af-repair --on mol-do-work --reassign" ]] \
  || fail "technical repair did not use the ordinary HQ dispatch: ${calls[2]}"

: > "$CALLS"
GC_BIN="$TMP/gc" FACTORY_ROOT="$REPO_ROOT" \
  FACTORY_WORK_DISPATCH_CONVOY_STATE_BIN="$TMP/convoy-state" \
  "$DISPATCH" af-delivered --technical-request af-convoy af-ticket --link-only >/dev/null
mapfile -t calls < "$CALLS"
[ "${#calls[@]}" -eq 1 ] \
  || fail "link-only must migrate the relation without redispatching delivered work: ${calls[*]-}"
[[ ${calls[0]} == "state link-technical-repair af-convoy af-ticket --repair af-delivered" ]] \
  || fail "link-only did not use the state-owned transition: ${calls[0]}"

: > "$CALLS"
if GC_BIN="$TMP/gc" FACTORY_ROOT="$REPO_ROOT" \
  FACTORY_WORK_DISPATCH_CONVOY_STATE_BIN="$TMP/convoy-state" \
  "$DISPATCH" af-refused --technical-request af-convoy af-ticket >/dev/null 2>&1; then
  fail "dispatched a repair whose technical link was refused"
fi
mapfile -t calls < "$CALLS"
[ "${#calls[@]}" -eq 1 ] \
  || fail "a refused technical link must stop before dispatch: ${calls[*]-}"

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
grep -q '^max_active_sessions = 2$' "$AGENT_TOML" || fail "factory-worker is not scaled to the configured two-writer cap"
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

echo "PASS: HQ work dispatch is role-fixed, workspace-inherited, and capped at the configured pool size"
