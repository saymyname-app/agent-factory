#!/usr/bin/env bash
# The reviewer reads the ticket and its criteria, not the whole Spec
# (af-s1yzo9): the Spec of a convoy can be ~100 KB. mol-code-review writes
# only the « Testing Decisions » section to code-review-spec.md (the closed
# question internal_test cites it); any other section is read by name, when
# the ticket cites it. bin/code-review record still checks a citation
# against the whole Spec.
set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
FORMULA="$REPO_ROOT/formulas/mol-code-review.formula.toml"
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT

spec_line=$(grep -F '> code-review-spec.md' "$FORMULA") || fail "the formula writes no code-review-spec.md"
ticket_line=$(grep -F '> code-review-ticket.md' "$FORMULA") || fail "the formula writes no code-review-ticket.md"

jq -n '{spec: {text: "# Spec\n\n## Problem Statement\nPROBLEM-TEXT\n\n## Testing Decisions\nTEST-DECISION-TEXT\n### Sub\nSUB-TEXT\n\n## Validated Prototype : Journal\nPROTOTYPE-TEXT\n"},
        ticket_text: {description: "TICKET-TEXT", demonstration_line: "DEMO-TEXT"}}' > "$WORK/code-review-brief.json"
(cd "$WORK" && eval "$spec_line" && eval "$ticket_line")

grep -q 'TEST-DECISION-TEXT' "$WORK/code-review-spec.md" || fail "code-review-spec.md lacks the Testing Decisions section"
grep -q 'SUB-TEXT' "$WORK/code-review-spec.md" || fail "code-review-spec.md cuts the Testing Decisions section short"
! grep -q 'PROBLEM-TEXT\|PROTOTYPE-TEXT' "$WORK/code-review-spec.md" || fail "code-review-spec.md still carries the whole Spec"
grep -q 'TICKET-TEXT' "$WORK/code-review-ticket.md" || fail "code-review-ticket.md lacks the ticket"

grep -Fq 'only when the ticket or one of its criteria cites it' "$FORMULA" \
  || fail "the formula does not say when another Spec section is read"

echo "PASS code-review-spec-scope-test"
