#!/usr/bin/env bash
# Agents wait in one blocking call, not by sleep-and-check calls (af-oowsc2):
# each poll re-reads the whole context. Role prompts and formulas carry no
# `sleep N` outside the claim block (whose retry runs inside one call), every
# role prompt states the one-blocking-wait rule, and every formula wait that
# can reach the controller's five-minute stalled threshold establishes the
# hold before it starts.
set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

for f in "$REPO_ROOT"/agents/*/prompt.template.md "$REPO_ROOT"/formulas/*.toml; do
  hits=$(awk '/<<.GC_CLAIM.$/ {skip=1} /^GC_CLAIM$/ {skip=0; next} !skip && /sleep [0-9]/ {print FILENAME ":" FNR ": " $0}' "$f")
  [ -z "$hits" ] || fail "polling sleep in an agent instruction: $hits"
done

for role in factory-worker delivery-author delivery-evaluator delivery-reviewer; do
  grep -Fq 'Wait for a slow result in one blocking call' "$REPO_ROOT/agents/$role/prompt.template.md" \
    || fail "agents/$role/prompt.template.md lacks the one-blocking-wait rule"
done

for f in mol-ticket-evaluation mol-outcome-evaluation; do
  grep -Eq 'product .*--dataset NAME --wait [0-9]+' "$REPO_ROOT/formulas/$f.formula.toml" \
    || fail "formulas/$f.formula.toml asks for a product without --wait"
done

for f in "$REPO_ROOT"/formulas/*.toml; do
  if grep -Eq -- '--wait ([3-9][0-9]{2}|[0-9]{4,})' "$f"; then
    grep -Fq 'gc runtime heartbeat --duration' "$f" \
      || fail "$f can wait at least five minutes without holding its runtime session"
  fi
done

echo "PASS agent-wait-polling-test"
