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

GC_BIN="$TMP/gc" FACTORY_ROOT="$REPO_ROOT" "$DISPATCH" af-fixture >/dev/null
call=$(cat "$CALLS")
[[ $call == "--city $REPO_ROOT sling factory-worker af-fixture --on mol-do-work --reassign" ]] \
  || fail "unexpected sling call: $call"

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

echo "PASS: HQ work dispatch is role-fixed, workspace-inherited, and single-session"
