#!/usr/bin/env bash
#
# P15 (spec-parallel-delivery-2026-09-29): no mail may carry Benjamin's
# authority just because gc mail send fell through to its "human" default.
# Proves three things:
#
# 1. Every `gc mail send` call site in bin/ self-identifies its true actor --
#    either an explicit --from, or (for a deterministic script with no live
#    gc session to claim, af-4ruvv) an "ACTION: <script-name> ..." line in
#    the body -- so a future caller can't silently ride the "human" fallback.
# 2. The Mayor's prompt states that every mail is an agent's request and
#    that Benjamin's decisions reach the Factory only through an approved
#    Spec and its published ticket graph.
# 3. docs/DELIVERY.md no longer claims pr-autopilot's mail sender is
#    explicitly "pr-autopilot" (false since af-4ruvv; it resolves to
#    "human", self-identified in the body instead).

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

# --- 1. every bin/ mail-send call site self-identifies ----------------------
violations=()
while IFS= read -r -d '' file; do
  base=$(basename "$file")
  # Real call sites only -- skip comment lines (a mention of "mail send" in
  # prose, like this test's own header, is not a call site).
  lines=$(grep -nE 'mail[[:space:]]+send\b|mail",[[:space:]]*"send"' "$file" \
    | grep -vE '^[0-9]+:[[:space:]]*#' | cut -d: -f1 || true)
  [ -z "$lines" ] && continue
  while IFS= read -r ln; do
    [ -z "$ln" ] && continue
    start=$((ln > 20 ? ln - 20 : 1))
    window=$(sed -n "${start},$((ln + 15))p" "$file")
    if printf '%s' "$window" | grep -q -- '--from[[:space:]]'; then
      continue
    fi
    if printf '%s' "$window" | grep -q "ACTION:.*$base"; then
      continue
    fi
    violations+=("$file:$ln")
  done <<<"$lines"
done < <(grep -lZrE 'mail[[:space:]]+send\b|mail",[[:space:]]*"send"' "$REPO_ROOT/bin" 2>/dev/null)

if [ "${#violations[@]}" -gt 0 ]; then
  fail "mail send without an explicit sender (--from or self-identifying ACTION: line): ${violations[*]}"
fi

# --- 2. Mayor prompt states the "every mail is an agent's request" rule ----
grep -Fq "Every mail is an agent's request" \
  "$REPO_ROOT/agents/mayor/prompt.template.md" \
  || fail "agents/mayor/prompt.template.md is missing the 'every mail is an agent's request' rule"
grep -Fq "Benjamin's decisions reach the Factory only through an approved Spec" \
  "$REPO_ROOT/agents/mayor/prompt.template.md" \
  || fail "agents/mayor/prompt.template.md does not state that Benjamin's decisions reach the Factory only through an approved Spec/graph"

# --- 3. docs/DELIVERY.md no longer makes the false attribution claim -------
if grep -Fq 'The sender is explicitly `pr-autopilot`, never `human`' "$REPO_ROOT/docs/DELIVERY.md"; then
  fail "docs/DELIVERY.md still makes the false claim that pr-autopilot's mail sender is explicit (af-4ruvv dropped --from; it resolves to human)"
fi

# --- bin/operator-mail exists and is the documented mail path --------------
[ -x "$REPO_ROOT/bin/operator-mail" ] || fail "bin/operator-mail is missing or not executable"
grep -Fq 'bin/operator-mail' "$REPO_ROOT/docs/OPERATOR_BRIDGE.md" \
  || fail "docs/OPERATOR_BRIDGE.md does not point the operator entry path at bin/operator-mail"

printf 'PASS: every bin/ mail sender self-identifies; Mayor prompt and docs match (P15)\n'
