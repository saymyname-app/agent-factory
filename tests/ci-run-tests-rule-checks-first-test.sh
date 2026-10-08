#!/usr/bin/env bash
#
# bin/ci-run-tests --rule-checks-first: the same tests in another order, the
# rule checks first, and a red rule check stops the run before the others.
#
# Intent (Benjamin, his words, 2026-10-08): « oui, vas-y pour la première
# tranche », the first slice being "the rule checks first in CI, and a
# measure of the long tests".
# Mechanism (agent interpretation): on the host's own runner Factory CI
# passes this option, so a stale catalogue or a lint is seen after a minute
# instead of after the long tests. It does not mean a test left out of a
# green run: green, every discovered test ran.
#
# Proven against a throwaway Git repository, then against the workflow.

set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
RUNNER="$ROOT/bin/ci-run-tests"
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX

REPO="$TMP/repo"
mkdir -p "$REPO/tests" "$REPO/config"
g() { git -C "$REPO" -c user.name=test -c user.email=test@example.invalid -c commit.gpgsign=false "$@"; }
g init -q -b main
printf 'tests/short-test.sh\t1\ntests/edge-test.sh\t5\ntests/mid-test.sh\t6\ntests/long-test.sh\t100\n' >"$REPO/config/ci-test-seconds.tsv"
# Each test writes its name in a journal: the order the run started them in.
for t in short edge mid long unmeasured; do
  printf '#!/usr/bin/env bash\necho %s >> "%s"\nexit 0\n' "$t" "$TMP/journal" >"$REPO/tests/$t-test.sh"
done
g add -A && g commit -q -m base

runner() {
  env -u CI_RUN_TESTS_FULL -u CI_RUN_TESTS_JOBS CI_RUN_TESTS_HOST_LOCK_FILE="$TMP/lock" \
    FACTORY_ROOT="$REPO" "$RUNNER" "$@" 2>&1
}
started() { tr '\n' ' ' <"$TMP/journal"; }

# --- green: every test ran, the rule checks before the others ---------------
: >"$TMP/journal"
out=$(runner --rule-checks-first --jobs 1) || { echo "$out" >&2; fail "a green run failed"; }
grep -Fq 'ran 5 test(s), 0 failure(s)' <<<"$out" || { echo "$out" >&2; fail "a green run did not run the five discovered tests"; }
case "$(started)" in
  "edge short "*|"short edge "*) ;;
  *) fail "the two rule checks did not start first: $(started)" ;;
esac
[ "$(tr ' ' '\n' <<<"$(started)" | grep -c .)" -eq 5 ] || fail "not every test started: $(started)"
echo "ok   green: the rule checks first, then every other test"

# --- several at once: still nothing but rule checks until they are done -----
: >"$TMP/journal"
out=$(runner --rule-checks-first --jobs 4) || { echo "$out" >&2; fail "a green run with 4 at once failed"; }
case "$(head -2 "$TMP/journal" | sort | tr '\n' ' ')" in
  "edge short ") ;;
  *) fail "with 4 at once another test started before the rule checks ended: $(started)" ;;
esac
echo "ok   with several at once, the others wait for the rule checks"

# --- a red rule check stops the run, and the run says what it did not run ---
printf '#!/usr/bin/env bash\necho short >> "%s"\nexit 1\n' "$TMP/journal" >"$REPO/tests/short-test.sh"
: >"$TMP/journal"
if out=$(runner --rule-checks-first --jobs 4); then echo "$out" >&2; fail "a failing rule check left the run green"; fi
grep -Fq 'FAILED: tests/short-test.sh' <<<"$out" || { echo "$out" >&2; fail "the run does not name the failing rule check"; }
grep -Fq 'the 3 other test(s) were NOT run' <<<"$out" || { echo "$out" >&2; fail "the run does not say how many tests it did not run"; }
grep -Fq 'ran 2 test(s), 1 failure(s)' <<<"$out" || { echo "$out" >&2; fail "the run does not count what it ran"; }
if grep -qE '^(mid|long|unmeasured)$' "$TMP/journal"; then fail "a test ran after a rule check failed: $(started)"; fi
echo "ok   a red rule check: the run stops red and says the others were not run"

# --- without the option, a red rule check still lets every test run ---------
: >"$TMP/journal"
if out=$(runner --jobs 1); then echo "$out" >&2; fail "a failing test left the plain run green"; fi
grep -Fq 'ran 5 test(s), 1 failure(s)' <<<"$out" || { echo "$out" >&2; fail "the plain run no longer runs every test"; }
echo "ok   without the option the run is unchanged"

# --- a red test that is not a rule check does not hide behind the option ----
printf '#!/usr/bin/env bash\nexit 0\n' >"$REPO/tests/short-test.sh"
printf '#!/usr/bin/env bash\nexit 1\n' >"$REPO/tests/long-test.sh"
if out=$(runner --rule-checks-first --jobs 2); then echo "$out" >&2; fail "a failing long test left the run green"; fi
grep -Fq 'ran 5 test(s), 1 failure(s)' <<<"$out" || { echo "$out" >&2; fail "with green rule checks the run must run every test"; }
echo "ok   green rule checks: every test runs and a red long test is a red run"

# --- the workflow passes it on the host's own runner only -------------------
CI="$ROOT/.github/workflows/ci.yml"
grep -qF 'if [ "$RUNNER_ENVIRONMENT" = self-hosted ]; then first=(--rule-checks-first); fi' "$CI" \
  || fail "$CI no longer runs the rule checks first on the host's own runner, or does it on GitHub's billed lots too"
echo "ok   Factory CI asks for it on the host's own runner only"

printf 'PASS: --rule-checks-first changes the order and stops on a red rule check, never what a green run ran\n'
