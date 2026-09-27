#!/usr/bin/env bash
#
# ADR-0023 rule 6: the Mayor prompt, formulas/*.toml and docs/OPERATIONS.md
# shall contain no instruction to set a coordination or proof gc.* field with
# --set-metadata; a test shall grep for it. (The product-queue doc and the
# campaign mail texts it also named were retired on 2026-09-26.)
#
# The doors themselves (bin/campaign-pointer, bin/deliver-close; the retired
# bin/product-queue was a third) are exempt -- they are the one place `--set-metadata` on
# these fields is allowed to live. Everything else must call the door.
#
# Docs legitimately WARN against the pattern in prose ("Never edit a
# candidate's status... (no raw `gc bd update --status ...` / `--set-metadata
# gc.queue_state=...`)") -- that is the desired, documented prohibition, not
# a violation. What must not exist is a *runnable instruction*: a line that
# starts a `gc bd update` command inside a fenced ```bash (or unlabeled ```)
# code block, the shape every formula step actually executes. This scanner
# only looks inside fenced code blocks for that reason.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
TESTS_RUN=0
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

# Coordination-root pointers (campaign-pointer's door) + the six ADR-0016
# delivery-proof fields (deliver-close's door) + gc.queue_state
# (the retired product-queue's door, kept so no raw write to it comes back).
FIELDS='gc\.(current|current_jit|last_delivered|next_outcome|needs_benjamin|blocked_reason|resume_[a-z_]+|delivery_status|work_outcome|github_repo|pr_number|pr_head|merge_commit|queue_state)'

scan_fenced_code() {  # $1 = file -> prints offending lines, if any
  awk '
    /^[[:space:]]*```/ { in_fence = !in_fence; next }
    in_fence && $0 ~ /--set-metadata.*'"$FIELDS"'/ && $0 ~ /gc bd update/ {
      print NR": "$0
    }
  ' "$1"
}

TARGETS_MD=(
  "$ROOT/agents/mayor/prompt.template.md"
  "$ROOT/docs/OPERATIONS.md"
)

for f in "${TARGETS_MD[@]}"; do
  TESTS_RUN=$((TESTS_RUN + 1))
  [ -f "$f" ] || fail "expected target file missing: $f"
  hit=$(scan_fenced_code "$f")
  [ -z "$hit" ] || fail "$f has a fenced-code instruction to hand-write a coordination/proof gc.* field: $hit"
done

for f in "$ROOT"/formulas/*.toml; do
  TESTS_RUN=$((TESTS_RUN + 1))
  hit=$(scan_fenced_code "$f")
  [ -z "$hit" ] || fail "$f has a fenced-code instruction to hand-write a coordination/proof gc.* field: $hit"
done

# Sanity: prove the scanner actually matches the shape it exists to catch,
# so a change to FIELDS/the awk pattern that stops matching anything (a
# silently broken test) is caught too.
TESTS_RUN=$((TESTS_RUN + 1))
sanity_hit=$(printf '```bash\ngc bd update af-1vr4 --set-metadata gc.needs_benjamin=x\n```\n' \
  | awk '
      /^[[:space:]]*```/ { in_fence = !in_fence; next }
      in_fence && $0 ~ /--set-metadata.*'"$FIELDS"'/ && $0 ~ /gc bd update/ { print }
    ')
[ -n "$sanity_hit" ] || fail "sanity: the scanner should have flagged a synthetic hand-write instruction"

# And prove it does NOT flag the legitimate prohibition prose that must stay
# in agents/mayor/prompt.template.md.
TESTS_RUN=$((TESTS_RUN + 1))
grep -q -- '--set-metadata gc.needs_benjamin=' "$ROOT/agents/mayor/prompt.template.md" \
  || fail "sanity: the prohibition prose this scanner must NOT flag seems to have been removed from the prompt template"

printf 'PASS: %d coordination-pointer-doors checks\n' "$TESTS_RUN"
