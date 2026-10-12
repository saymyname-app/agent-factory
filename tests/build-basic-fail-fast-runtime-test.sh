#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime and an isolated Dolt server

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
FIXTURE="$ROOT/tests/fixtures/build-basic-fail-fast/runtime.formula.toml"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc bd jq; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

TEST_CITY=$(mktemp -d /tmp/af-jz8kc-fail-fast.XXXXXX)
cleanup() {
  status=$?
  trap - EXIT
  bd -C "$TEST_CITY" dolt stop >/dev/null 2>&1 || true
  if [ "${KEEP_TEST_CITY:-0}" = 1 ]; then
    echo "test city preserved at $TEST_CITY" >&2
  else
    rm -rf -- "$TEST_CITY"
  fi
  exit "$status"
}
trap cleanup EXIT

# The worker process may carry the live Factory's hosted-Dolt variables.  They
# must not escape into this isolated local city.
run_clean() {
  env \
    -u GC_DOLT_HOST \
    -u GC_DOLT_PORT \
    -u GC_DOLT_DATABASE \
    -u GC_DOLT_PROJECT_ID \
    -u GC_DOLT_USER \
    "$@"
}

run_clean gc init \
  --template minimal \
  --default-provider codex \
  --skip-provider-readiness \
  --no-start \
  --yes \
  --name af-jz8kc-fail-fast \
  "$TEST_CITY" >/dev/null

mkdir -p "$TEST_CITY/formulas" "$TEST_CITY/.gc/scripts/checks"
cp "$FIXTURE" "$TEST_CITY/formulas/build-basic-fail-fast-runtime.formula.toml"

# The review loop must never execute, but the compiler still validates that
# its check path is resolvable inside the isolated city.
cp "$ROOT/tests/fixtures/build-basic-fail-fast/never-run.sh" \
  "$TEST_CITY/.gc/scripts/checks/never-run.sh"
chmod +x "$TEST_CITY/.gc/scripts/checks/never-run.sh"

run_clean gc --city "$TEST_CITY" formula cook build-basic-fail-fast-runtime >/dev/null

snapshot() {
  run_clean gc --city "$TEST_CITY" bd list \
    --all --include-infra --limit 0 --flat --json
}

BEFORE=$(snapshot)
ROOT_ID=$(jq -r '.[] | select(.metadata["gc.kind"] == "workflow") | .id' <<<"$BEFORE")
GATE_ID=$(jq -r '.[] | select(.metadata["gc.step_ref"] == "build-basic-fail-fast-runtime.hard-gate") | .id' <<<"$BEFORE")
GATE_CONTROL_ID=$(jq -r '.[] | select(.metadata["gc.step_ref"] == "build-basic-fail-fast-runtime.hard-gate-scope-check") | .id' <<<"$BEFORE")
REVIEW_CONTROL_ID=$(jq -r '.[] | select(.metadata["gc.step_ref"] == "build-basic-fail-fast-runtime.review-loop") | .id' <<<"$BEFORE")
REVIEW_STEP_ID=$(jq -r --arg id "$REVIEW_CONTROL_ID" '.[] | select(.id == $id) | .metadata["gc.step_id"]' <<<"$BEFORE")
FINALIZER_ID=$(jq -r '.[] | select(.metadata["gc.kind"] == "workflow-finalize") | .id' <<<"$BEFORE")

for resolved in ROOT_ID GATE_ID GATE_CONTROL_ID REVIEW_CONTROL_ID REVIEW_STEP_ID FINALIZER_ID; do
  [ -n "${!resolved}" ] || fail "could not resolve $resolved from cooked graph"
done

jq -e --arg id "$GATE_ID" '
  .[] | select(.id == $id) | .metadata["gc.kind"] == "ralph"
' >/dev/null <<<"$BEFORE" || fail "hard-gate fixture is not a gated control"

INITIAL_ITERATIONS=$(jq \
  --arg control "$REVIEW_CONTROL_ID" \
  --arg step "$REVIEW_STEP_ID" \
  '[.[] | select(
    .metadata["gc.logical_bead_id"] == $control or
    .metadata["gc.ralph_step_id"] == $step
  )] | length' <<<"$BEFORE")
[ "$INITIAL_ITERATIONS" -gt 0 ] || fail "fixture did not pre-seed the first review iteration"

# --force: the gate's first iteration is still open, and Beads 1.3.1 refuses
# to close an issue with a live blocker without it (af-1umdgn).
run_clean gc --city "$TEST_CITY" bd update "$GATE_ID" \
  --set-metadata 'gc.outcome=fail' \
  --set-metadata 'gc.failure_reason=control_dispatch_error' \
  --set-metadata 'gc.failure_class=hard' \
  --status=closed --force \
  --notes 'Injected hard gate failure for deterministic fail-fast regression.' >/dev/null

# One scope-control pass must abort the body and sweep both the downstream
# Ralph control and every already-materialized logical descendant.
run_clean gc --city "$TEST_CITY" convoy control "$GATE_CONTROL_ID" >/dev/null
AFTER_ABORT=$(snapshot)

jq -e --arg id "$GATE_ID" '
  .[] | select(.id == $id) |
  .status == "closed" and
  .metadata["gc.outcome"] == "fail" and
  .metadata["gc.failure_reason"] == "control_dispatch_error" and
  .metadata["gc.failure_class"] == "hard"
' >/dev/null <<<"$AFTER_ABORT" || fail "hard gate lost its original failure evidence"

jq -e --arg id "$REVIEW_CONTROL_ID" '
  .[] | select(.id == $id) |
  .status == "closed" and .metadata["gc.outcome"] == "skipped"
' >/dev/null <<<"$AFTER_ABORT" || fail "review loop control was not closed skipped"

jq -e --arg control "$REVIEW_CONTROL_ID" --arg step "$REVIEW_STEP_ID" '
  [.[] | select(
    .metadata["gc.logical_bead_id"] == $control or
    .metadata["gc.ralph_step_id"] == $step
  )] as $iterations |
  ($iterations | length) > 0 and
  all($iterations[]; .status == "closed" and .metadata["gc.outcome"] == "skipped")
' >/dev/null <<<"$AFTER_ABORT" || fail "materialized review descendants were not swept"

SECOND_ITERATIONS=$(jq --arg step "$REVIEW_STEP_ID" '[.[] | select(
  (.metadata["gc.ralph_step_id"] == $step or .metadata["gc.step_id"] == $step) and
  (.metadata["gc.iteration"] == "2" or (.metadata["gc.step_ref"] // "" | contains("iteration.2")))
)] | length' <<<"$AFTER_ABORT")
[ "$SECOND_ITERATIONS" = 0 ] || fail "a review iteration materialized after the hard failure"

# The body failure and skipped review sink make the finalizer ready immediately;
# a second bounded control pass must settle the workflow root as failed.
run_clean gc --city "$TEST_CITY" convoy control "$FINALIZER_ID" >/dev/null
AFTER_FINALIZE=$(snapshot)

jq -e --arg id "$ROOT_ID" '
  .[] | select(.id == $id) |
  .status == "closed" and .metadata["gc.outcome"] == "fail"
' >/dev/null <<<"$AFTER_FINALIZE" || fail "workflow root did not close fail"

READY_REVIEW=$(run_clean gc --city "$TEST_CITY" bd list --ready --limit 0 --flat --json \
  | jq --arg control "$REVIEW_CONTROL_ID" --arg step "$REVIEW_STEP_ID" '[.[] | select(
      .id == $control or
      .metadata["gc.logical_bead_id"] == $control or
      .metadata["gc.ralph_step_id"] == $step
    )] | length')
[ "$READY_REVIEW" = 0 ] || fail "review work remained claimable after scope abort"

echo "PASS: hard gate failure swept review descendants and closed the root fail"
