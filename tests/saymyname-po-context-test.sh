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
grep -Fq 'ADR-0004-saymyname-po-cockpit.md' "$root/docs/CONTEXT_INDEX.md"
grep -Fq 'ADR-0005-mayor-owned-product-queue.md' "$root/docs/CONTEXT_INDEX.md"
grep -Fq 'bin/product-queue' "$root/docs/PRODUCT_QUEUE.md"
grep -Fq 'materialize <candidate> <execution-bead> --mayor' "$root/agents/mayor/prompt.template.md"
grep -Fq 'C:\Dev\Projects\SayMyName' "$root/docs/OPERATOR_BRIDGE.md"

echo 'SayMyName PO context contract: PASS'
