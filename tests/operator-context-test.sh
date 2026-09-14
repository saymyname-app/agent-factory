#!/usr/bin/env bash

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

assert_file() {
  [[ -f "$REPO_ROOT/$1" ]] || fail "missing $1"
}

assert_contains() {
  local file=$1
  local text=$2
  grep -Fq -- "$text" "$REPO_ROOT/$file" || fail "$file is missing: $text"
}

assert_absent() {
  local file=$1
  local text=$2
  if grep -Fq -- "$text" "$REPO_ROOT/$file"; then
    fail "$file still contains stale text: $text"
  fi
}

assert_file AGENTS.md
assert_file docs/OPERATOR_BRIDGE.md
assert_file docs/decisions/ADR-0003-native-codex-operator-bridge.md
assert_file docs/FACTORY_WORKSPACE_AGENTS.md
assert_file docs/decisions/ADR-0006-token-free-human-factory-cockpit.md

agent_bytes=$(wc -c < "$REPO_ROOT/AGENTS.md")
(( agent_bytes <= 8192 )) || fail "AGENTS.md exceeds the 8 KiB bootstrap budget"

assert_contains AGENTS.md 'docs/OPERATOR_BRIDGE.md'
assert_contains AGENTS.md './bin/factory-cockpit snapshot'
assert_contains AGENTS.md 'Full access'
assert_contains README.md 'docs/OPERATOR_BRIDGE.md'
assert_contains README.md 'wsl -d Ubuntu-24.04 -u benja --cd /home/benja/agent-factory'
assert_contains docs/CONTEXT_INDEX.md 'OPERATOR_BRIDGE.md'
assert_contains docs/CONTEXT_INDEX.md 'ADR-0003-native-codex-operator-bridge.md'
assert_contains docs/OPERATOR_BRIDGE.md './bin/saymyname-product-status'
assert_contains docs/OPERATOR_BRIDGE.md 'C:\Dev\Projects\AgentFactory'
assert_contains docs/OPERATOR_BRIDGE.md './bin/factory-cockpit open'
assert_contains docs/OPERATOR_BRIDGE.md 'capability of the connected host, not standing authority'
assert_absent README.md 'No production City is configured or proven yet.'
assert_absent README.md 'legacy SayMyName Automation runner remains available'

printf 'PASS: Codex operator context is linked, bounded, and under budget (%s bytes)\n' "$agent_bytes"
