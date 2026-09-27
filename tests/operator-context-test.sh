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
assert_file agents/ux-reviewer/agent.toml
assert_file agents/ux-reviewer/prompt.template.md

agent_bytes=$(wc -c < "$REPO_ROOT/AGENTS.md")
(( agent_bytes <= 8192 )) || fail "AGENTS.md exceeds the 8 KiB bootstrap budget"

assert_contains AGENTS.md 'docs/OPERATOR_BRIDGE.md'
assert_contains AGENTS.md 'Cockpit V1 is retired to `legacy/`'
assert_contains AGENTS.md 'Full access'
assert_contains README.md 'docs/OPERATOR_BRIDGE.md'
assert_contains README.md 'wsl -d Ubuntu-24.04 -u benja --cd /home/benja/agent-factory'
assert_contains docs/CONTEXT_INDEX.md 'OPERATOR_BRIDGE.md'
# The structural-decisions row must span ADR-0001 through the HIGHEST ADR that
# actually exists. Both context tests used to hardcode ADR-0014, which meant
# every new ADR broke two test files and needed a human edit in each -- and,
# worse, the assertion passed for weeks while the index silently omitted
# ADR-0015 and ADR-0016. Deriving the endpoint from docs/decisions/ makes the
# check self-maintaining AND makes it catch the stale index it was meant to.
latest_adr=$(ls "$REPO_ROOT/docs/decisions"/ADR-*.md 2>/dev/null \
  | xargs -n1 basename | sort | tail -1 | sed 's/\.md$//')
first_adr=$(ls "$REPO_ROOT/docs/decisions"/ADR-*.md 2>/dev/null \
  | xargs -n1 basename | sort | head -1 | sed 's/\.md$//')
adr_range="\`decisions/${first_adr}.md\` through \`decisions/${latest_adr}.md\`"
# Pre-refactor material is reachable, and flagged untrusted, from the index.
assert_contains docs/CONTEXT_INDEX.md '../legacy/README.md'
assert_contains docs/CONTEXT_INDEX.md "$adr_range"
assert_contains agents/mayor/prompt.template.md 'UI/UX design gate'
# Decisions 7-9 (Benjamin, 2026-09-25): the Mayor executes approved graphs,
# re-slices only through the traced door, and proposes instead of improving.
assert_contains agents/mayor/prompt.template.md 'Where work comes from'
assert_contains agents/mayor/prompt.template.md 'bin/ticket-graph-publish patch'
assert_contains agents/mayor/prompt.template.md '--labels proposal'
! grep -q 'product-queue\|mayor-campaign\|saymyname-product' "$REPO_ROOT/agents/mayor/prompt.template.md" \
  || fail 'the Mayor prompt still points at retired legacy commands'
# The Mayor is project-agnostic: project rules live in each rig's AGENTS.md.
! grep -qi 'saymyname' "$REPO_ROOT/agents/mayor/prompt.template.md" \
  || fail 'the Mayor prompt names a project; project rules belong in its rig AGENTS.md'
assert_absent docs/OPERATOR_BRIDGE.md './bin/saymyname-product-status'
assert_contains docs/OPERATOR_BRIDGE.md 'C:\Dev\Projects\AgentFactory'
assert_absent docs/OPERATOR_BRIDGE.md './bin/factory-cockpit'
assert_contains docs/OPERATOR_BRIDGE.md 'capability of the connected host, not standing authority'
assert_absent README.md 'No production City is configured or proven yet.'
assert_absent README.md 'legacy SayMyName Automation runner remains available'

printf 'PASS: Codex operator context is linked, bounded, and under budget (%s bytes)\n' "$agent_bytes"
