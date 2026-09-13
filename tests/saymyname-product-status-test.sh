#!/usr/bin/env bash

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
STATUS_SCRIPT="$REPO_ROOT/bin/saymyname-product-status"
FIXTURE_ROOT="$REPO_ROOT/tests/fixtures/saymyname-product-status"
TESTS_RUN=0

fail_test() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

run_fixture() {
  local scenario=$1
  STATUS_SCENARIO="$scenario" \
    GC_BIN="$FIXTURE_ROOT/gc" \
    GH_BIN="$FIXTURE_ROOT/gh" \
    "$STATUS_SCRIPT"
}

assert_output() {
  local scenario=$1
  local expected=$2
  local output

  TESTS_RUN=$((TESTS_RUN + 1))
  output=$(run_fixture "$scenario") || fail_test "$scenario should succeed"
  [[ $output == "$expected" ]] || {
    printf 'Expected:\n%s\nActual:\n%s\n' "$expected" "$output" >&2
    fail_test "$scenario output differs"
  }
}

assert_failure() {
  local scenario=$1
  local expected_message=$2
  local output

  TESTS_RUN=$((TESTS_RUN + 1))
  if output=$(run_fixture "$scenario" 2>&1); then
    fail_test "$scenario should fail closed"
  fi
  [[ $output == *"$expected_message"* ]] \
    || fail_test "$scenario did not report the expected recovery message: $output"
}

assert_output active "$(cat <<'EXPECTED'
SAYMYNAME
CURRENT: Expose SayMyName product status summary — implementation
CURRENT AGENT: codex-af-test
LAST DELIVERED: Deterministic local preview — PR 24 — merged as bbbbbbbbbbbb; CI not configured
NEXT: Evaluate supported ChatGPT plugin/MCP bridge
NEEDS BENJAMIN: none
EXPECTED
)"

assert_output idle "$(cat <<'EXPECTED'
SAYMYNAME
CURRENT: none — idle
CURRENT AGENT: none
LAST DELIVERED: Deterministic local preview — PR 24 — merged as bbbbbbbbbbbb; CI not configured
NEXT: Evaluate supported ChatGPT plugin/MCP bridge
NEEDS BENJAMIN: none
EXPECTED
)"

assert_output human "$(cat <<'EXPECTED'
SAYMYNAME
CURRENT: Expose SayMyName product status summary — queued
CURRENT AGENT: none
LAST DELIVERED: Deterministic local preview — PR 24 — merged as bbbbbbbbbbbb; CI not configured
NEXT: Evaluate supported ChatGPT plugin/MCP bridge
NEEDS BENJAMIN: Choose whether to prioritize bounded intent intake
EXPECTED
)"

assert_output green "$(cat <<'EXPECTED'
SAYMYNAME
CURRENT: Expose SayMyName product status summary — implementation
CURRENT AGENT: codex-af-test
LAST DELIVERED: Deterministic local preview — PR 24 — merged as bbbbbbbbbbbb; CI green (2 checks)
NEXT: Evaluate supported ChatGPT plugin/MCP bridge
NEEDS BENJAMIN: none
EXPECTED
)"

assert_output routed "$(cat <<'EXPECTED'
SAYMYNAME
CURRENT: Implement backend product outcome — implementation
CURRENT AGENT: codex-af-test
LAST DELIVERED: Deliver frontend product outcome — PR 24 — merged as bbbbbbbbbbbb; CI not configured
NEXT: Evaluate supported ChatGPT plugin/MCP bridge
NEEDS BENJAMIN: none
EXPECTED
)"

assert_failure mismatch "does not match the delivered Bead head and merge evidence"
assert_failure invalid-repo "must be a valid owner/repository name"
assert_failure source-failure "Beads product coordination source command failed"
assert_failure agent-missing "is not uniquely running in Gas City"

printf 'PASS: %d deterministic product-status checks\n' "$TESTS_RUN"
