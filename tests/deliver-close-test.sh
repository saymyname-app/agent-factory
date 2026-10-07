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

# P07 (mol-do-work step 3c): a bead fixed inside another ticket's PR names it
# with gc.delivered_via_pr. It still carries the gc.work_branch its own
# dispatch stamped, which is by definition not that PR's head -- the close
# must go through (2026-10-01: af-3hmxgn/af-6c0xm9 named merged PR #372 and
# were refused on every pr-autopilot tick, failing the order each time).
TESTS_RUN=$((TESTS_RUN + 1))
DELIVER_CLOSE_BEAD_METADATA='{"gc.work_branch":"do-work/af-fixed","gc.work_base_branch":"main","gc.delivered_via_pr":42}' \
  run merged af-fixed --repo owner/repo --pr 42 >/dev/null \
  || fail_test "a bead naming PR 42 in gc.delivered_via_pr should close on PR 42 despite its own gc.work_branch"
call=$(<"$CALL_LOG")
[[ $call == *"--status=closed"* && $call == *"gc.pr_number=42"* ]] \
  || fail_test "delivered_via_pr close did not write the delivery proof: $call"

# The branch guard still holds for a bead that does not name this PR: with no
# gc.delivered_via_pr at all, or with one naming another PR.
TESTS_RUN=$((TESTS_RUN + 1))
for metadata in '{"gc.work_branch":"do-work/af-other"}' \
  '{"gc.work_branch":"do-work/af-other","gc.delivered_via_pr":41}'; do
  if output=$(DELIVER_CLOSE_BEAD_METADATA="$metadata" run merged af-other --repo owner/repo --pr 42 2>&1); then
    fail_test "a bead on another branch that does not name PR 42 must be refused ($metadata)"
  fi
  [[ $output == *"records gc.work_branch=do-work/af-other but PR 42 head is do-work/af-work"* ]] \
    || fail_test "branch-mismatch refusal did not report the expected reason: $output"
  [[ -z $(<"$CALL_LOG") ]] || fail_test "branch-mismatch refusal made a Beads write"
done

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

# af-cphvt: a blocked/abandoned close is refused outright with no
# classification at all -- leaving it optional let a worker skip the
# ADR-0028 triage question entirely by just never passing the flag.
assert_refused merged "requires --classification" \
  af-work --outcome blocked --reason "Blocked: waiting on X"
assert_refused merged "requires --classification" \
  af-work --outcome abandoned --reason "Nobody will unblock this"

# af-zwhh0: --classification repair on a bounded technical repair needs no
# Planning Exception.
# af-1al0t1: --outcome blocked parks the bead (status blocked,
# gc.outcome=blocked) instead of closing it as a success -- closing released
# T21's dependents without the operator's answer.
TESTS_RUN=$((TESTS_RUN + 1))
run merged af-work --outcome blocked --classification repair \
  --reason "Blocked: waiting on X" >/dev/null \
  || fail_test "--outcome blocked --classification repair should park successfully"
call=$(<"$CALL_LOG")
[[ $(wc -l <<<"$call") -eq 1 ]] || fail_test "--outcome blocked should write Beads exactly once"
[[ $call == *"gc.work_outcome=blocked"* ]] || fail_test "--outcome blocked missing gc.work_outcome"
[[ $call == *"gc.outcome=blocked"* ]] || fail_test "--outcome blocked must record gc.outcome=blocked"
[[ $call != *"gc.outcome=pass"* ]] || fail_test "--outcome blocked must never record gc.outcome=pass: $call"
[[ $call == *"--status=blocked"* ]] || fail_test "--outcome blocked must park the bead in status blocked: $call"
[[ $call != *"--status=closed"* ]] || fail_test "--outcome blocked must not close the bead: $call"
[[ $call == *"Blocked: waiting on X"* ]] || fail_test "--outcome blocked did not carry --reason through"
[[ $call == *"gc.blocked_classification=repair"* ]] \
  || fail_test "--classification repair missing gc.blocked_classification"
[[ $call != *"gc.planning_exception_id"* ]] \
  || fail_test "--classification repair must not write gc.planning_exception_id"

# af-1al0t1 exact shape: a delivery-graph ticket carrying an active NEEDS
# BENJAMIN (and an as-yet unmerged linked PR) is parked, not closed and not
# refused for its PR -- parking claims nothing delivered.
TESTS_RUN=$((TESTS_RUN + 1))
DELIVER_CLOSE_BEAD_METADATA='{"gc.plane":"delivery","gc.delivery_contract":"pr-ci-merged-v1","gc.graph_digest":"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","gc.needs_benjamin":"Choisir une variante"}' \
  DELIVER_CLOSE_PR_URL="https://github.com/owner/repo/pull/42" \
  run not-merged af-work --outcome blocked --classification repair \
  --reason "Blocked: NEEDS BENJAMIN" >/dev/null \
  || fail_test "a delivery ticket awaiting the operator should park with --outcome blocked"
call=$(<"$CALL_LOG")
[[ $call == *"--status=blocked"* && $call != *"--status=closed"* && $call != *"gc.outcome=pass"* ]] \
  || fail_test "a delivery ticket awaiting the operator was not parked: $call"

# af-1al0t1: no form of the door closes a bead whose NEEDS BENJAMIN is still
# active -- the close would silently drop the operator's question.
NEEDS_ACTIVE='{"gc.needs_benjamin":"Choisir une variante"}'
for form in "--outcome no-op" "--outcome abandoned --classification repair" \
  "--outcome shipped --commit cafef00d --branch do-work/af-work"; do
  TESTS_RUN=$((TESTS_RUN + 1))
  # shellcheck disable=SC2086
  if output=$(DELIVER_CLOSE_BEAD_METADATA="$NEEDS_ACTIVE" run merged af-work $form 2>&1); then
    fail_test "$form must refuse to close a bead with an active NEEDS BENJAMIN"
  fi
  [[ $output == *"active NEEDS BENJAMIN"* ]] \
    || fail_test "$form refusal did not name the active NEEDS BENJAMIN: $output"
  [[ -z $(<"$CALL_LOG") ]] || fail_test "$form made a Beads write despite an active NEEDS BENJAMIN"
done
TESTS_RUN=$((TESTS_RUN + 1))
if output=$(DELIVER_CLOSE_BEAD_METADATA="$NEEDS_ACTIVE" run merged af-work --repo owner/repo --pr 42 2>&1); then
  fail_test "--repo/--pr must refuse to close a bead with an active NEEDS BENJAMIN"
fi
[[ $output == *"active NEEDS BENJAMIN"* && -z $(<"$CALL_LOG") ]] \
  || fail_test "--repo/--pr refusal on an active NEEDS BENJAMIN wrong: $output"

# An answered or cleared question ("none") no longer holds the close.
TESTS_RUN=$((TESTS_RUN + 1))
DELIVER_CLOSE_BEAD_METADATA='{"gc.needs_benjamin":"none"}' run merged af-work --outcome no-op >/dev/null \
  || fail_test "a cleared NEEDS BENJAMIN (none) must not hold the close"
[[ $(<"$CALL_LOG") == *"--status=closed"* ]] || fail_test "cleared NEEDS BENJAMIN close did not close"

# af-zwhh0: a semantic/topology surprise must name the Planning Exception
# decision that was actually raised for it -- refused outright otherwise,
# before any Beads write (ADR-0028; the af-4a44k shape this closes).
assert_refused merged "requires --planning-exception-id" \
  af-work --outcome blocked --classification semantic --reason "Blocked: topology surprise"
assert_refused merged "requires --planning-exception-id" \
  af-work --outcome abandoned --classification topology --reason "Blocked: semantic surprise"
assert_refused merged "--classification must be one of" \
  af-work --outcome blocked --classification bogus
assert_refused merged "--classification/--planning-exception-id only apply to --outcome blocked|abandoned" \
  af-work --outcome shipped --commit cafef00d --branch do-work/af-work --classification repair
assert_refused merged "--classification/--planning-exception-id only apply to --outcome blocked|abandoned" \
  af-work --outcome no-op --planning-exception-id pd-1
assert_refused merged "--planning-exception-id requires --classification" \
  af-work --outcome blocked --planning-exception-id pd-1

TESTS_RUN=$((TESTS_RUN + 1))
run merged af-work --outcome blocked --classification semantic --planning-exception-id pd-1 \
  --reason "Blocked: topology surprise" >/dev/null \
  || fail_test "--classification semantic with --planning-exception-id should park successfully"
call=$(<"$CALL_LOG")
[[ $call == *"gc.blocked_classification=semantic"* ]] \
  || fail_test "--classification semantic missing gc.blocked_classification"
[[ $call == *"gc.planning_exception_id=pd-1"* ]] \
  || fail_test "--classification semantic with a decision id missing gc.planning_exception_id"

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

# O01/P24: a repo named only in a config/projects/*.toml file (never
# hardcoded in deliver-close) has its required CI workflow resolved
# automatically via project_registry -- proves the --repo/--pr form's
# lookup is genuinely config-driven, not a stale hardcoded SayMyName case.
SYNTHETIC_ROOT=$(mktemp -d)
trap 'rm -f "$CALL_LOG"; rm -rf "$SYNTHETIC_ROOT"' EXIT
mkdir -p "$SYNTHETIC_ROOT/config/projects"
cat > "$SYNTHETIC_ROOT/config/projects/synthetic-project.toml" <<'TOML'
rig_dir = "rigs/synthetic-project"
repo = "synthetic-org/synthetic-repo"
protected_branch = "dev"
required_ci = "Factory CI"
TOML

run_auto() {
  local scenario=$1
  shift
  : > "$CALL_LOG"
  DELIVER_SCENARIO="$scenario" \
    GC_BIN="$FIXTURE_ROOT/gc" \
    GH_BIN="$FIXTURE_ROOT/gh" \
    DELIVER_CLOSE_CALL_LOG="$CALL_LOG" \
    FACTORY_ROOT="$SYNTHETIC_ROOT" \
    "$SCRIPT" "$@"
}

TESTS_RUN=$((TESTS_RUN + 1))
run_auto merged af-outcome --repo synthetic-org/synthetic-repo --pr 42 >/dev/null \
  || fail_test "a repo known only via config/projects should auto-resolve its required workflow and close"
call=$(<"$CALL_LOG")
[[ $call == *"gc.required_ci_workflow=Factory CI"* ]] \
  || fail_test "auto-resolved required workflow missing from Beads write: $call"
[[ $call == *"gc.github_repo=synthetic-org/synthetic-repo"* ]] \
  || fail_test "auto-resolved close missing repo field: $call"

TESTS_RUN=$((TESTS_RUN + 1))
if output=$(run_auto merged af-outcome --repo unknown-org/unknown-repo --pr 42 2>&1); then
  fail_test "a repo named in no project file and no --required-workflow should refuse to close"
fi
[[ $output == *"--required-workflow is required for unknown-org/unknown-repo"* ]] \
  || fail_test "unresolvable-repo refusal did not name the repo: $output"


# 2026-10-07 (af-3yo0we, af-yc2ly0, af-1ai5e3, af-r2y2w9): a verified merge
# close resolves, through bin/proposal-door resoudre, every still-pending
# proposal the merged PR explicitly names (title, body, a commit message, or
# gc.resolves_proposal on the delivered bead) -- and nothing else: a pending
# proposal the PR does not name stays pending, an accepted/rejected one is
# left to the door (which refuses), and a refused close resolves nothing.
PD_LOG=$(mktemp)
PD_STUB=$(mktemp)
trap 'rm -f "$CALL_LOG" "$PD_LOG" "$PD_STUB"' EXIT
cat >"$PD_STUB" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$PROPOSAL_DOOR_CALL_LOG"
[[ ${PROPOSAL_DOOR_STUB_FAIL:-0} == 1 ]] && { echo "stub: refused" >&2; exit 1; }
exit 0
STUB
chmod +x "$PD_STUB"
PROPOSALS='[{"id":"af-prop1","status":"open","labels":["proposal"],"metadata":{"gc.proposal_state":"ouverte"}},
            {"id":"af-prop2","status":"open","labels":["proposal"],"metadata":{"gc.proposal_state":"ouverte"}},
            {"id":"af-prop3","status":"open","labels":["proposal"],"metadata":{"gc.proposal_state":"rejetee"}},
            {"id":"af-legacy","status":"open","labels":["proposal"],"metadata":null}]'
run_pd() {  # scenario args... (PROPOSAL_DOOR_* and DELIVER_CLOSE_PR_* from the caller's env)
  : >"$PD_LOG"
  PROPOSAL_DOOR_BIN="$PD_STUB" PROPOSAL_DOOR_CALL_LOG="$PD_LOG" \
    DELIVER_CLOSE_PROPOSALS_JSON="$PROPOSALS" run "$@"
}

# The PR body names af-prop1 (pending) and af-prop3 (rejected, never touched);
# af-prop2 is not named; the delivered bead itself (af-work, "Closes af-work")
# is not a proposal.
TESTS_RUN=$((TESTS_RUN + 1))
DELIVER_CLOSE_PR_BODY=$'Closes af-work.\n\nRésout la proposition af-prop1 (et af-prop3 reste à l\'opérateur).' \
  run_pd merged af-work --repo owner/repo --pr 42 >/dev/null \
  || fail_test "a merged PR naming a proposal should still close its bead"
[[ $(<"$CALL_LOG") == *"--status=closed"* ]] || fail_test "proposal resolution must not skip the bead close"
[[ $(wc -l <"$PD_LOG") -eq 1 ]] || fail_test "expected exactly one proposal-door call, got: $(cat "$PD_LOG")"
[[ $(<"$PD_LOG") == "resoudre af-prop1 PR #42 (owner/repo, merge bbbbbbbbbbbb) deliver-close" ]] \
  || fail_test "unexpected proposal-door call: $(cat "$PD_LOG")"

# A proposal named in a commit message of the PR.
TESTS_RUN=$((TESTS_RUN + 1))
DELIVER_CLOSE_PR_COMMIT_HEADLINE="fix(guard): exempt bd.dog wisps (af-legacy)" \
  run_pd merged af-work --repo owner/repo --pr 42 >/dev/null \
  || fail_test "a merged PR whose commit names a proposal should close its bead"
[[ $(<"$PD_LOG") == "resoudre af-legacy PR #42 (owner/repo, merge bbbbbbbbbbbb) deliver-close" ]] \
  || fail_test "a proposal named by a commit message was not resolved: $(cat "$PD_LOG")"

# A proposal named by the delivered bead's own gc.resolves_proposal.
TESTS_RUN=$((TESTS_RUN + 1))
DELIVER_CLOSE_BEAD_METADATA='{"gc.resolves_proposal":"af-prop2"}' \
  run_pd merged af-work --repo owner/repo --pr 42 >/dev/null \
  || fail_test "a bead carrying gc.resolves_proposal should close"
[[ $(<"$PD_LOG") == "resoudre af-prop2 PR #42 (owner/repo, merge bbbbbbbbbbbb) deliver-close" ]] \
  || fail_test "gc.resolves_proposal was not honoured: $(cat "$PD_LOG")"

# A merged PR naming no proposal resolves nothing; a prefix match
# (af-prop1 vs af-prop10) is not a mention.
TESTS_RUN=$((TESTS_RUN + 1))
DELIVER_CLOSE_PR_BODY="Closes af-work. See also af-prop10 and af-prop1x." \
  run_pd merged af-work --repo owner/repo --pr 42 >/dev/null \
  || fail_test "a merged PR naming no proposal should close its bead"
[[ ! -s $PD_LOG ]] || fail_test "a PR naming no pending proposal must resolve none: $(cat "$PD_LOG")"

# A refused close resolves nothing, whatever the PR says.
TESTS_RUN=$((TESTS_RUN + 1))
if DELIVER_CLOSE_PR_BODY="Résout af-prop1" run_pd not-merged af-work --repo owner/repo --pr 42 >/dev/null 2>&1; then
  fail_test "an unmerged PR must be refused"
fi
[[ ! -s $PD_LOG ]] || fail_test "a refused close must resolve no proposal: $(cat "$PD_LOG")"

# The proposal door refusing (or failing) never fails the close: the bead is
# already closed on verified proof; the failure is logged for a hand resolve.
TESTS_RUN=$((TESTS_RUN + 1))
output=$(DELIVER_CLOSE_PR_BODY="Résout af-prop1" PROPOSAL_DOOR_STUB_FAIL=1 \
  run_pd merged af-work --repo owner/repo --pr 42 2>&1) \
  || fail_test "a proposal-door failure must not fail a verified close: $output"
[[ $output == *"WARNING: proposal af-prop1"*"was not resolved"* ]] \
  || fail_test "a proposal-door failure must be logged: $output"

printf 'PASS: %d deterministic deliver-close checks\n' "$TESTS_RUN"
