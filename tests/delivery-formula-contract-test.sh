#!/usr/bin/env bash
# ADR-0026 wiring: PR creation records waiting state; only deliver-close owns
# the merge+CI close transition.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

for formula in \
  "$ROOT/formulas/mol-do-work.formula.toml" \
  "$ROOT/formulas/mol-polecat-commit.formula.toml" \
  "$ROOT/formulas/mol-scoped-work.formula.toml"
do
  grep -q 'gc.delivery_contract=pr-ci-merged-v1' "$formula" \
    || fail "$(basename "$formula") does not mark PR-backed work"
  grep -q 'gc.delivery_status=waiting' "$formula" \
    || fail "$(basename "$formula") does not leave PR-backed work waiting"
  if grep -Fq 'gc bd close "$WORK_BEAD_ID"' "$formula"; then
    fail "$(basename "$formula") still closes the work bead at PR creation"
  fi
done

grep -q 'finalize_delivery .*required-workflow' "$ROOT/bin/pr-autopilot" \
  || grep -q -- '--required-workflow "$workflow"' "$ROOT/bin/pr-autopilot" \
  || fail "pr-autopilot does not route merged PRs through the required-CI door"

if grep -q -- '--set-metadata merge_result=merged' "$ROOT/bin/pr-autopilot"; then
  fail "pr-autopilot still writes merge completion around deliver-close"
fi

for field in merge_result=merged merged_sha= merged_target= gc.ci_run_id= gc.ci_head_sha= gc.ci_conclusion=success; do
  grep -q "$field" "$ROOT/bin/deliver-close" \
    || fail "deliver-close does not own structural field $field"
done

echo "PASS: PR formulas wait and deliver-close owns merge+exact-head-CI completion"
