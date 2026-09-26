#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
product="$root/docs/products/saymyname"
agent="$product/PO_WORKSPACE_AGENTS.md"
config="$product/CODEX_PROJECT.toml"

test -s "$agent"
test -s "$product/PRODUCT_CONTEXT.md"
test -s "$product/DECISIONS.md"
test -s "$config"
test "$(wc -c < "$agent")" -le 8192

grep -Fq 'wsl -d Ubuntu-24.04 -u benja --cd /home/benja/agent-factory' "$agent"
grep -Fq './bin/saymyname-product-queue' "$agent"
grep -Fq 'Mayor alone materializes executable Beads' "$agent"
grep -Fq 'it does not tail events' "$agent"
grep -Fq 'The PO does not create or' "$agent"
grep -Fq 'Linear is' "$agent"
grep -Fq 'danger-full-access' "$agent"
grep -Fq 'agent-db.ps1' "$agent"
grep -Fq 'sandbox_mode = "danger-full-access"' "$config"
grep -Fq 'approval_policy = "on-request"' "$config"
! grep -Fq 'mcp_servers.linear' "$config"

grep -Fq 'products/saymyname/PRODUCT_CONTEXT.md' "$root/docs/CONTEXT_INDEX.md"
# The structural-decisions row must span ADR-0001 through the HIGHEST ADR that
# actually exists. Both context tests used to hardcode ADR-0014, which meant
# every new ADR broke two test files and needed a human edit in each -- and,
# worse, the assertion passed for weeks while the index silently omitted
# ADR-0015 and ADR-0016. Deriving the endpoint from docs/decisions/ makes the
# check self-maintaining AND makes it catch the stale index it was meant to.
latest_adr=$(ls "$root/docs/decisions"/ADR-*.md 2>/dev/null \
  | xargs -n1 basename | sort | tail -1 | sed 's/\.md$//')
adr_range="\`decisions/ADR-0001-foundation.md\` through \`decisions/${latest_adr}.md\`"
grep -Fq "$adr_range" "$root/docs/CONTEXT_INDEX.md"
grep -Fq 'bin/product-queue' "$root/docs/PRODUCT_QUEUE.md"
grep -Fq 'materialize <candidate> <execution-bead> --mayor' "$root/agents/mayor/prompt.template.md"
grep -Fq 'C:\Dev\Projects\SayMyName' "$root/docs/OPERATOR_BRIDGE.md"

echo 'SayMyName PO context contract: PASS'
