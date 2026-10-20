#!/usr/bin/env bash
#
# bin/ci-run-tests --rule-checks (af-66bfyx): the rule checks have one
# command, and it lists exactly the files measured at 5 s or less, plus the
# test files a change touches.
#
# Intent (Benjamin, his words, 2026-10-08): « ok pour ta reco »
# Mechanism (agent interpretation): the accepted recommendation lets a change
# to docs, CI or tests alone run the rule checks and the tests it touches
# before its pull request, instead of the whole battery. It does not mean a
# change of the merge gate: CI still runs the battery on every pull request.
#
# Proven against a throwaway Git repository, then against the real list.

set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
RUNNER="$ROOT/bin/ci-run-tests"
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
# Run from a Git hook (the main-landing gate), these would point every git
# call below at the repository being pushed.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX

REPO="$TMP/repo"
mkdir -p "$REPO/tests" "$REPO/config"
g() { git -C "$REPO" -c user.name=test -c user.email=test@example.invalid -c commit.gpgsign=false "$@"; }
g init -q -b main
printf 'tests/short-test.sh\t1\ntests/edge-test.sh\t5\ntests/mid-test.sh\t6\ntests/long-test.sh\t100\n' >"$REPO/config/ci-test-seconds.tsv"
for t in short edge mid long unmeasured; do printf '#!/usr/bin/env bash\nexit 0\n' >"$REPO/tests/$t-test.sh"; done
g add -A && g commit -q -m base
BASE=$(g rev-parse HEAD)

runner() {
  env -u CI_RUN_TESTS_FULL -u CI_RUN_TESTS_JOBS CI_RUN_TESTS_HOST_LOCK_FILE="$TMP/lock" \
    FACTORY_ROOT="$REPO" "$RUNNER" "$@" 2>&1
}
listed() { runner "$@" --list | tr '\n' ' '; }

# --- 5 s or less, measured: nothing else -------------------------------------
RULES="tests/edge-test.sh tests/short-test.sh "
[ "$(listed --rule-checks)" = "$RULES" ] \
  || fail "--rule-checks listed '$(listed --rule-checks)', not the two files measured at 5 s or less"
[ "$(listed --rule-checks --changed-since "$BASE")" = "$RULES" ] \
  || fail "with nothing changed, --changed-since added a file to the rule checks"
echo "ok   the rule checks are the files measured at 5 s or less, not the unmeasured one"

# --- the tests a change touches run too, committed or not --------------------
echo "# committed change" >>"$REPO/tests/long-test.sh"
g add -A && g commit -q -m "change a long test"
echo "# uncommitted change" >>"$REPO/tests/mid-test.sh"
printf '#!/usr/bin/env bash\nexit 0\n' >"$REPO/tests/new-test.sh"
TOUCHED="tests/edge-test.sh tests/long-test.sh tests/mid-test.sh tests/new-test.sh tests/short-test.sh "
[ "$(listed --rule-checks --changed-since "$BASE")" = "$TOUCHED" ] \
  || fail "--rule-checks --changed-since listed '$(listed --rule-checks --changed-since "$BASE")', not the rule checks and the three changed tests"
[ "$(listed --rule-checks)" = "$RULES" ] || fail "without --changed-since a changed test joined the rule checks"
out=$(runner --rule-checks --changed-since "$BASE") || { echo "$out" >&2; fail "the rule checks failed"; }
grep -Fq 'NOT the battery' <<<"$out" || { echo "$out" >&2; fail "the run does not say it is not the battery"; }
grep -Fq '2 file(s) of 5s or less' <<<"$out" || { echo "$out" >&2; fail "the run does not count its rule checks"; }
grep -Fq '3 changed test file(s)' <<<"$out" || { echo "$out" >&2; fail "the run does not count the changed tests"; }
grep -Fq 'ran 5 test(s), 0 failure(s)' <<<"$out" || { echo "$out" >&2; fail "the run did not run exactly the five files"; }
echo "ok   with --changed-since, the changed tests run too, and the run says it is not the battery"

# --- a red rule check is a red run; an unreadable commit is not a green one --
printf '#!/usr/bin/env bash\nexit 1\n' >"$REPO/tests/short-test.sh"
if out=$(runner --rule-checks); then echo "$out" >&2; fail "a failing rule check left the run green"; fi
grep -Fq 'FAILED: tests/short-test.sh' <<<"$out" || { echo "$out" >&2; fail "the run does not name the failing rule check"; }
status=0; out=$(runner --rule-checks --changed-since no-such-commit) || status=$?
[ "$status" -eq 2 ] || { echo "$out" >&2; fail "an unreadable commit ended with $status, not 2"; }
echo "ok   a failing rule check fails the run; an unreadable commit runs nothing and says so"

# --- the battery itself is unchanged -----------------------------------------
[ "$(listed)" = "tests/edge-test.sh tests/long-test.sh tests/mid-test.sh tests/new-test.sh tests/short-test.sh tests/unmeasured-test.sh " ] \
  || fail "without --rule-checks the run is no longer every discovered test"
echo "ok   without --rule-checks every discovered test still runs"

# --- the tests naming a changed tool are left to CI, or run on demand ------
# PR #602 changed bin/ticket-evaluation; tests/convoy-advance-test.py, a long
# test, runs tests/fixtures/ticket-evaluation/evaluator and went red in CI.
# af-awyj8z made the rule checks bring such tests. af-sgsh4g leaves them to
# CI by default: for bin/convoy-advance alone they were 11 files and 32 min
# against 131 s for the 124 rule checks (20/10/2026). They are named in the
# output, and --with-naming runs them.
REPO="$TMP/repo602"
mkdir -p "$REPO/bin" "$REPO/lib" "$REPO/tests/fixtures/ticket-evaluation" "$REPO/config"
g init -q -b main
printf 'tests/short-test.sh\t1\ntests/convoy-advance-test.py\t200\ntests/other-test.py\t200\ntests/lib-user-test.py\t200\n' >"$REPO/config/ci-test-seconds.tsv"
printf '#!/usr/bin/env bash\nexit 0\n' >"$REPO/tests/short-test.sh"
printf '# EVALUATOR = "tests/fixtures/ticket-evaluation/evaluator"\n' >"$REPO/tests/convoy-advance-test.py"
printf '# reaches bin/ticket-evaluations-report, not the tool\n' >"$REPO/tests/other-test.py"
printf '# from ticket_graph import load\n' >"$REPO/tests/lib-user-test.py"
for f in bin/ticket-evaluation lib/ticket_graph.py tests/fixtures/ticket-evaluation/evaluator docs.md; do echo v1 >"$REPO/$f"; done
g add -A && g commit -q -m base
BASE=$(g rev-parse HEAD)
echo v2 >>"$REPO/bin/ticket-evaluation" && g commit -qam "change the tool"
[ "$(listed --rule-checks --changed-since "$BASE")" = "tests/short-test.sh " ] \
  || fail "by default a change to bin/ticket-evaluation listed '$(listed --rule-checks --changed-since "$BASE")', not the rule checks alone"
out=$(runner --rule-checks --changed-since "$BASE") || { echo "$out" >&2; fail "the run failed"; }
grep -Fq '1 test file(s) naming a changed file left to CI (--with-naming runs them): tests/convoy-advance-test.py' <<<"$out" \
  || { echo "$out" >&2; fail "the run does not name the test it leaves to CI"; }
grep -Fq 'ran 1 test(s), 0 failure(s)' <<<"$out" || { echo "$out" >&2; fail "the run ran a test it leaves to CI"; }
[ "$(listed --rule-checks --changed-since "$BASE" --with-naming)" = "tests/convoy-advance-test.py tests/short-test.sh " ] \
  || fail "with --with-naming a change to bin/ticket-evaluation listed '$(listed --rule-checks --changed-since "$BASE" --with-naming)', not the test that runs its fixture"
out=$(runner --rule-checks --changed-since "$BASE" --with-naming) || { echo "$out" >&2; fail "the run failed"; }
grep -Fq '1 test file(s) naming a changed file.' <<<"$out" || { echo "$out" >&2; fail "the run does not count the test naming the tool"; }
g reset -q --hard "$BASE"
echo v2 >>"$REPO/tests/fixtures/ticket-evaluation/evaluator"
echo v2 >>"$REPO/lib/ticket_graph.py"
echo v2 >>"$REPO/docs.md"
[ "$(listed --rule-checks --changed-since "$BASE" --with-naming)" = "tests/convoy-advance-test.py tests/lib-user-test.py tests/short-test.sh " ] \
  || fail "an uncommitted change to a fixture and a library listed '$(listed --rule-checks --changed-since "$BASE" --with-naming)', not the two tests naming them"
[ "$(listed --rule-checks --changed-since "$BASE")" = "tests/short-test.sh " ] \
  || fail "by default an uncommitted change to a fixture and a library listed '$(listed --rule-checks --changed-since "$BASE")', not the rule checks alone"
echo "ok   the tests naming a changed tool, fixture or library are left to CI, named, and run with --with-naming"

# --- on the real list ---------------------------------------------------------
expected=$(cd "$ROOT" && comm -12 <("$RUNNER" --list | sort) \
  <(awk -F'\t' '$2 ~ /^[0-9]+$/ && $2 <= 5 { print $1 }' config/ci-test-seconds.tsv | sort))
[ -n "$expected" ] || fail "config/ci-test-seconds.tsv gives no discovered test 5 s or less"
[ "$(cd "$ROOT" && "$RUNNER" --rule-checks --list | sort)" = "$expected" ] \
  || fail "on this repository --rule-checks does not list exactly the discovered tests config/ci-test-seconds.tsv gives 5 s or less"
echo "ok   on this repository: $(wc -l <<<"$expected") rule checks, exactly the files of 5 s or less"
