#!/usr/bin/env bash
#
# bin/ci-run-tests --changed-since REF (af-5mw6z0): the long tests are left
# out only when every changed file is in an area they cannot reach, and a
# long test that reads such an area fails the run.
#
# Intent (Benjamin, his words, 2026-10-08): « y'a pas moyen aussi de ne pas
# tester toute l'usine comme ça à chaque fois ? »
# Mechanism (agent interpretation): a closed list of areas
# (config/ci-long-test-blind-areas.txt); one changed file outside it, or any
# doubt, is a full run. It does not mean a selection guessed from names.
#
# Proven against a throwaway Git repository that holds the real list of
# areas, one long test, one short test and one long Cockpit test.

set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
RUNNER="$ROOT/bin/ci-run-tests"
AREAS="config/ci-long-test-blind-areas.txt"
CI="$ROOT/.github/workflows/ci.yml"
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
# Run from a Git hook (the main-landing gate), these would point every git
# call below at the repository being pushed.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX

REPO="$TMP/repo"
mkdir -p "$REPO/tests" "$REPO/config" "$REPO/docs/guide" "$REPO/lib/cockpit/ui" "$REPO/bin"
g() { git -C "$REPO" -c user.name=test -c user.email=test@example.invalid -c commit.gpgsign=false "$@"; }
g init -q -b main
cp "$ROOT/$AREAS" "$REPO/$AREAS"
printf 'tests/long-test.sh\t100\ntests/short-test.sh\t1\ntests/cockpit-ui-test.sh\t100\n' >"$REPO/config/ci-test-seconds.tsv"
echo "a page" >"$REPO/docs/guide/page.md"
echo "x = 1" >"$REPO/lib/cockpit/ui/view.py"
echo "echo tool" >"$REPO/bin/tool"
for t in long short cockpit-ui; do printf '#!/usr/bin/env bash\nexit 0\n' >"$REPO/tests/$t-test.sh"; done
g add -A && g commit -q -m base
BASE=$(g rev-parse HEAD)

ALL="tests/cockpit-ui-test.sh tests/long-test.sh tests/short-test.sh "
REDUCED="tests/cockpit-ui-test.sh tests/short-test.sh "
runner() { env -u CI_RUN_TESTS_FULL -u CI_RUN_TESTS_JOBS FACTORY_ROOT="$REPO" "$RUNNER" "$@" 2>&1; }
listed() { runner "$@" --list | tr '\n' ' '; }
commit() { g add -A && g commit -q -m "$1"; }
back_to_base() { g checkout -q -f -B work "$BASE" && g clean -q -fd; }

# --- every changed file in an area: the long test is left out, and said so --
back_to_base
echo "more" >>"$REPO/docs/guide/page.md"
echo "y = 2" >>"$REPO/lib/cockpit/ui/view.py"
echo "# touched" >>"$REPO/tests/cockpit-ui-test.sh"
commit "docs and Cockpit only"
[ "$(listed --changed-since "$BASE")" = "$REDUCED" ] \
  || fail "a change to docs, lib/cockpit and a Cockpit test selected '$(listed --changed-since "$BASE")', not the short tests alone"
out=$(runner --changed-since "$BASE") || { echo "$out" >&2; fail "the reduced run failed"; }
grep -Fq '1 long test(s) NOT run' <<<"$out" || { echo "$out" >&2; fail "the run does not say it left a long test out"; }
grep -Fq 'not run: tests/long-test.sh (100s' <<<"$out" || { echo "$out" >&2; fail "the run does not name the test it left out"; }
grep -Fq "$AREAS" <<<"$out" || { echo "$out" >&2; fail "the run does not say why (the list of areas)"; }
grep -Fq 'CI_RUN_TESTS_FULL=1' <<<"$out" || { echo "$out" >&2; fail "the run does not say how to force a full run"; }
grep -Fq 'ran 2 test(s), 0 failure(s)' <<<"$out" || { echo "$out" >&2; fail "the reduced run did not run exactly the two other files"; }
echo "ok   docs and Cockpit only: the long test is left out, named, with the reason"

# A long file that is itself in an area (a Cockpit test) is never left out:
# it is in $REDUCED above although the list gives it 100 s.
union=$( { listed --changed-since "$BASE" --shard 1/2; listed --changed-since "$BASE" --shard 2/2; } | tr ' ' '\n' | sed '/^$/d' | sort | tr '\n' ' ')
[ "$union" = "$REDUCED" ] || fail "the two lots of a reduced run are '$union', not the reduced list"
echo "ok   the lots of a reduced run hold the reduced list, each file once"

# --- the switch back, and no option at all -----------------------------------
[ "$(CI_RUN_TESTS_FULL=1 FACTORY_ROOT="$REPO" "$RUNNER" --changed-since "$BASE" --list | tr '\n' ' ')" = "$ALL" ] \
  || fail "CI_RUN_TESTS_FULL=1 did not make the run a full run"
[ "$(listed)" = "$ALL" ] || fail "without --changed-since the run is not a full run"
echo "ok   CI_RUN_TESTS_FULL=1, or no --changed-since, runs everything"

# --- one changed file outside the list: everything runs ----------------------
echo "echo changed" >>"$REPO/bin/tool"
commit "and a tool"
[ "$(listed --changed-since "$BASE")" = "$ALL" ] || fail "a change to bin/tool next to docs did not run everything"
out=$(runner --changed-since "$BASE") || { echo "$out" >&2; fail "the full run failed"; }
grep -Fq 'full run: bin/tool changed' <<<"$out" || { echo "$out" >&2; fail "the full run does not name the file that caused it"; }
grep -Fq 'ran 3 test(s), 0 failure(s)' <<<"$out" || { echo "$out" >&2; fail "the full run did not run the three files"; }
echo "ok   a change outside the list runs everything, and the run names the file"

# A file that leaves or enters an area is a change outside it.
for move in "docs/guide/page.md bin/page.md" "bin/tool docs/tool"; do
  back_to_base
  # shellcheck disable=SC2086  # two paths
  g mv $move && commit "move $move"
  [ "$(listed --changed-since "$BASE")" = "$ALL" ] || fail "moving $move did not run everything"
done
# The list itself, the measured seconds and a new test are outside it too.
for path in "$AREAS" config/ci-test-seconds.tsv tests/new-test.sh docs-like.md lib/cockpit.py tests/fixtures/cockpit-x; do
  back_to_base
  mkdir -p "$REPO/$(dirname "$path")" && echo "# changed" >>"$REPO/$path" && commit "change $path"
  [ "$(listed --changed-since "$BASE" | tr ' ' '\n' | grep -c '^tests/long-test.sh$')" -eq 1 ] \
    || fail "a change to $path left the long test out"
done
echo "ok   a moved file, the list itself, a new test, a look-alike path: everything runs"

# --- any doubt is a full run --------------------------------------------------
back_to_base
echo "more" >>"$REPO/docs/guide/page.md" && commit "docs only"
[ "$(listed --changed-since "$BASE")" = "$REDUCED" ] || fail "docs only is not a reduced run"
[ "$(listed --changed-since no-such-ref)" = "$ALL" ] || fail "an unknown commit did not run everything"
[ "$(listed --changed-since HEAD)" = "$ALL" ] || fail "no changed file did not run everything"
echo "echo not committed" >>"$REPO/bin/tool"
[ "$(listed --changed-since "$BASE")" = "$ALL" ] || fail "an uncommitted change did not run everything"
g checkout -q -- bin/tool
echo "new" >"$REPO/bin/untracked-tool"
[ "$(listed --changed-since "$BASE")" = "$ALL" ] || fail "an untracked file did not run everything"
rm "$REPO/bin/untracked-tool"
mv "$REPO/$AREAS" "$TMP/areas" && g add -A && commit "no list"
[ "$(listed --changed-since HEAD~1 | tr ' ' '\n' | grep -c '^tests/long-test.sh$')" -eq 1 ] || fail "without the list of areas the long test was left out"
if runner --changed-since >/dev/null; then fail "--changed-since without a commit was accepted"; fi
echo "ok   unknown commit, nothing changed, uncommitted or untracked file, no list: everything runs"

# --- the merge commit Factory CI tests ---------------------------------------
# A pull request run checks out the merge of the branch into main: its first
# parent is main. What the pull request brings is first parent..merge, whatever
# main received meanwhile.
back_to_base
echo "more" >>"$REPO/docs/guide/page.md" && commit "pull request: docs only"
g checkout -q -B main "$BASE"
echo "echo main moved" >>"$REPO/bin/tool" && commit "main: a tool changed"
g checkout -q --detach main && g merge -q --no-ff -m "merge of the pull request" work
[ "$(listed --changed-since 'HEAD^1')" = "$REDUCED" ] \
  || fail "on the merge commit of a docs-only pull request, the tool main received counted as a change of the pull request"
back_to_base
echo "echo new" >"$REPO/bin/other-tool" && commit "pull request: a tool"
g checkout -q --detach main && g merge -q --no-ff -m "merge of the pull request" work
[ "$(listed --changed-since 'HEAD^1')" = "$ALL" ] || fail "on the merge commit of a pull request that changes a tool, the long test was left out"
echo "ok   on the merge commit, only what the pull request brings is counted"

# --- a long test that reads an area fails the run ----------------------------
back_to_base
blind_run() {  # body of the long test -> runner output (full run)
  printf '#!/usr/bin/env bash\ncd "$(dirname "$0")/.."\n%s\n' "$1" >"$REPO/tests/long-test.sh"
  runner
}
out=$(blind_run 'cat bin/tool >/dev/null; test -e docs/guide/page.md') || { echo "$out" >&2; fail "a long test that reads a tool failed"; }
if out=$(blind_run 'grep -q page docs/guide/page.md'); then echo "$out" >&2; fail "a long test that reads a page of docs passed"; fi
grep -Fq 'tests/long-test.sh is a long test and read an area' <<<"$out" || { echo "$out" >&2; fail "the failure does not say what is wrong"; }
grep -Eq '^ +docs/guide/page\.md$' <<<"$out" || { echo "$out" >&2; fail "the failure does not name the file that was read"; }
if out=$(blind_run 'ls lib/cockpit/ui >/dev/null'); then echo "$out" >&2; fail "a long test that lists lib/cockpit passed"; fi
grep -Eq '^ +lib/cockpit/ui$' <<<"$out" || { echo "$out" >&2; fail "the failure does not name the directory that was listed"; }
if out=$(blind_run 'python3 -c "open(\"tests/cockpit-ui-test.sh\").read()" & wait'); then echo "$out" >&2; fail "a long test whose child reads a Cockpit test passed"; fi
grep -Eq '^ +tests/cockpit-ui-test\.sh$' <<<"$out" || { echo "$out" >&2; fail "the failure does not name the Cockpit test that was read"; }
# The long test sees the same content as everyone, and a short test or a
# Cockpit test may read the areas.
out=$(blind_run '[ "$(cat bin/tool)" = "echo tool" ]') || { echo "$out" >&2; fail "the long test does not see the repository as it is"; }
printf '#!/usr/bin/env bash\ncat "$(dirname "$0")/../docs/guide/page.md" >/dev/null\n' | tee "$REPO/tests/short-test.sh" >"$REPO/tests/cockpit-ui-test.sh"
out=$(blind_run 'exit 0') || { echo "$out" >&2; fail "a short test or a Cockpit test that reads docs failed"; }
echo "ok   a long test that opens or lists an area, itself or through a child, fails the run"

# --- the versioned list and the workflow --------------------------------------
[ -r "$ROOT/$AREAS" ] || fail "$AREAS is missing: no run can be reduced"
long=$(awk -F'\t' '$2 ~ /^[0-9]+$/ && $2 >= 30' "$ROOT/config/ci-test-seconds.tsv" | wc -l)
[ "$long" -ge 1 ] || fail "config/ci-test-seconds.tsv names no long test: nothing would ever be left out"
[ "$(FACTORY_ROOT="$ROOT" "$RUNNER" --changed-since no-such-ref --list)" = "$(FACTORY_ROOT="$ROOT" "$RUNNER" --list)" ] \
  || fail "on this repository an unknown commit does not run everything"
grep -Eq '^ +fetch-depth: 2 *$' "$CI" || fail "$CI does not fetch the first parent of the merge commit: every run would be a full run"
grep -Fq -- "--changed-since 'HEAD^1'" "$CI" || fail "$CI does not pass --changed-since: every run is a full run"
grep -Fq 'rev-list --parents -n 1 HEAD' "$CI" || fail "$CI no longer checks that HEAD is a merge commit before trusting its first parent"
grep -Eq "^  CI_RUN_TESTS_FULL: '[01]' *\$" "$CI" || fail "$CI lost its switch CI_RUN_TESTS_FULL"
echo "ok   the list is versioned and the workflow asks for the selection on the merge commit"

printf 'PASS: long tests are left out only when the change cannot reach them\n'
