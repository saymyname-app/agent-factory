#!/usr/bin/env bash
#
# ADR-0016 invariant 2: closing a delivery bead without its six proof fields
# must be refused, never silent. Proves bin/deliver-close closes only after a
# verified merged PR, writes all six fields in that same call, and makes no
# Beads write at all when the PR cannot be verified as merged.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SCRIPT="$REPO_ROOT/bin/deliver-close"
FIXTURE_ROOT="$REPO_ROOT/tests/fixtures/deliver-close"
CALL_LOG=$(mktemp)
TESTS_RUN=0

trap 'rm -f "$CALL_LOG"' EXIT

fail_test() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

run() {
  local scenario=$1
  shift
  : > "$CALL_LOG"
  DELIVER_SCENARIO="$scenario" \
    GC_BIN="$FIXTURE_ROOT/gc" \
    GH_BIN="$FIXTURE_ROOT/gh" \
    DELIVER_CLOSE_CALL_LOG="$CALL_LOG" \
    "$SCRIPT" "$@" --required-workflow "Factory CI"
}

assert_closed_with_all_six() {
  local scenario=$1
  shift
  local call

  TESTS_RUN=$((TESTS_RUN + 1))
  run "$scenario" "$@" >/dev/null || fail_test "$scenario should close successfully"
  call=$(<"$CALL_LOG")
  [[ $(wc -l <<<"$call") -eq 1 ]] || fail_test "$scenario should write Beads exactly once"
  for field in \
    "gc.delivery_status=merged" \
    "gc.work_outcome=shipped" \
    "gc.github_repo=owner/repo" \
    "gc.pr_number=42" \
    "gc.pr_head=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" \
    "gc.merge_commit=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" \
    "merge_result=merged" \
    "merged_sha=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" \
    "merged_target=main" \
    "gc.required_ci_workflow=Factory CI" \
    "gc.ci_run_id=35882143816" \
    "gc.ci_head_sha=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" \
    "gc.ci_conclusion=success"
  do
    [[ $call == *"$field"* ]] || fail_test "$scenario missing proof field in Beads write: $field"
  done
  [[ $call == *"--status=closed"* ]] || fail_test "$scenario did not close the bead"
}

assert_refused() {
  local scenario=$1
  shift
  local expected_message=$1
  shift
  local output call

  TESTS_RUN=$((TESTS_RUN + 1))
  if output=$(run "$scenario" "$@" 2>&1); then
    fail_test "$scenario should refuse to close"
  fi
  [[ $output == *"$expected_message"* ]] \
    || fail_test "$scenario did not report the expected refusal: $output"
  call=$(<"$CALL_LOG")
  [[ -z $call ]] || fail_test "$scenario made a Beads write despite refusing: $call"
}

assert_closed_with_all_six merged af-outcome --repo owner/repo --pr 42
assert_refused not-merged "not verifiably merged" af-outcome --repo owner/repo --pr 42
assert_refused number-mismatch "not verifiably merged" af-outcome --repo owner/repo --pr 42
assert_refused short-sha "not verifiably merged" af-outcome --repo owner/repo --pr 42
assert_refused gh-failure "source command failed" af-outcome --repo owner/repo --pr 42
assert_refused ci-failure "not successful on exact PR head" af-outcome --repo owner/repo --pr 42
assert_refused ci-missing "has no pull_request run on exact PR head" af-outcome --repo owner/repo --pr 42
assert_refused ci-head-mismatch "has no pull_request run on exact PR head" af-outcome --repo owner/repo --pr 42
assert_refused merged "--repo must be a valid owner/repository name" af-outcome --repo not-a-repo --pr 42
assert_refused merged "--pr must be a positive pull request number" af-outcome --repo owner/repo --pr abc
assert_refused merged "--pr must be a positive pull request number" af-outcome --repo owner/repo --pr 0

TESTS_RUN=$((TESTS_RUN + 1))
if run merged af-outcome --repo owner/repo >/dev/null 2>&1; then
  fail_test "missing --pr should be rejected"
fi

# ADR-0023: the --outcome form is the door mol-do-work uses instead of a raw
# `gc bd update --set-metadata gc.work_outcome=...`. No GitHub verification.
TESTS_RUN=$((TESTS_RUN + 1))
run merged af-work --outcome shipped --commit cafef00d --branch do-work/af-work >/dev/null \
  || fail_test "--outcome shipped should close successfully"
call=$(<"$CALL_LOG")
for field in "gc.outcome=pass" "gc.work_outcome=shipped" "gc.work_commit=cafef00d" \
  "gc.work_branch=do-work/af-work" "--status=closed"; do
  [[ $call == *"$field"* ]] || fail_test "--outcome shipped missing field in Beads write: $field"
done

TESTS_RUN=$((TESTS_RUN + 1))
run merged af-work --outcome no-op >/dev/null || fail_test "--outcome no-op should close successfully"
call=$(<"$CALL_LOG")
[[ $call == *"gc.work_outcome=no-op"* ]] || fail_test "--outcome no-op missing gc.work_outcome"
[[ $call != *"gc.work_commit"* ]] || fail_test "--outcome no-op must not write gc.work_commit"

TESTS_RUN=$((TESTS_RUN + 1))
run merged af-work --outcome blocked --reason "Blocked: waiting on X" >/dev/null \
  || fail_test "--outcome blocked should close successfully"
call=$(<"$CALL_LOG")
[[ $call == *"gc.work_outcome=blocked"* ]] || fail_test "--outcome blocked missing gc.work_outcome"
[[ $call == *"Blocked: waiting on X"* ]] || fail_test "--outcome blocked did not carry --reason through"

assert_refused merged "--outcome shipped requires --commit" af-work --outcome shipped
assert_refused merged "--outcome must be one of" af-work --outcome bogus
assert_refused merged "--outcome cannot be combined with --repo/--pr" \
  af-work --outcome shipped --commit c --branch b --repo owner/repo --pr 1

# Approved delivery-graph work cannot take the lighter non-PR shipped exit.
TESTS_RUN=$((TESTS_RUN + 1))
if output=$(DELIVER_CLOSE_BEAD_METADATA='{"gc.plane":"delivery","gc.graph_digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}' \
  run merged af-work --outcome shipped --commit cafef00d --branch do-work/af-work 2>&1); then
  fail_test "delivery-graph shipped outcome without a linked PR should refuse to close"
fi
[[ $output == *"requires PR+CI delivery proof"* ]] \
  || fail_test "delivery-graph refusal did not name the structural contract: $output"
call=$(<"$CALL_LOG")
[[ -z $call ]] || fail_test "delivery-graph refusal made a Beads write: $call"

# af-fzlp2: the --outcome door must not accept a close (shipped or otherwise
# -- close_by_outcome always sets gc.outcome=pass) when the target bead
# already names its own gc.pr_url and that PR does not verify as merged.
TESTS_RUN=$((TESTS_RUN + 1))
if output=$(DELIVER_CLOSE_PR_URL="https://github.com/owner/repo/pull/42" \
  run not-merged af-work --outcome shipped --commit cafef00d --branch do-work/af-work 2>&1); then
  fail_test "--outcome shipped with an unmerged linked PR should refuse to close"
fi
[[ $output == *"not verifiably merged"* ]] \
  || fail_test "linked-PR refusal did not report the expected reason: $output"
call=$(<"$CALL_LOG")
[[ -z $call ]] \
  || fail_test "--outcome shipped with an unmerged linked PR made a Beads write despite refusing: $call"

TESTS_RUN=$((TESTS_RUN + 1))
if output=$(DELIVER_CLOSE_PR_URL="https://github.com/owner/repo/pull/42" run not-merged af-work --outcome no-op 2>&1); then
  fail_test "--outcome no-op with an unmerged linked PR should refuse to close"
fi
[[ $output == *"not verifiably merged"* ]] \
  || fail_test "no-op linked-PR refusal did not report the expected reason: $output"

TESTS_RUN=$((TESTS_RUN + 1))
if output=$(DELIVER_CLOSE_PR_URL="not-a-github-url" run merged af-work --outcome no-op 2>&1); then
  fail_test "--outcome no-op with an unparseable linked gc.pr_url should refuse to close"
fi
[[ $output == *"not a recognizable GitHub PR URL"* ]] \
  || fail_test "unparseable linked-PR refusal did not report the expected reason: $output"

# A bead whose own linked PR verifies merged closes exactly as before.
TESTS_RUN=$((TESTS_RUN + 1))
DELIVER_CLOSE_PR_URL="https://github.com/owner/repo/pull/42" \
  run merged af-work --outcome shipped --commit cafef00d --branch do-work/af-work >/dev/null \
  || fail_test "--outcome shipped with a verified merged linked PR should close successfully"
call=$(<"$CALL_LOG")
[[ $call == *"gc.work_outcome=shipped"* ]] \
  || fail_test "--outcome shipped with a verified linked PR missing gc.work_outcome in Beads write"
[[ $call == *"gc.ci_head_sha=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"* ]] \
  || fail_test "verified linked PR close missing exact-head CI proof"

printf 'PASS: %d deterministic deliver-close checks\n' "$TESTS_RUN"
