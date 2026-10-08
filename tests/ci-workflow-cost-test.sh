#!/usr/bin/env bash
#
# af-mzuprx: the three choices that keep Factory CI's billed minutes down
# stay in .github/workflows/ci.yml (docs/OPERATIONS.md, "Factory CI cost and
# the Actions quota"). Each one was measured; losing one silently brings the
# bill back without any test going red:
#   - no run on `push` to main (it repeated the pull request's run);
#   - a new commit cancels the run of the commit it replaces;
#   - each runner runs as many test files at once as it has cores.
# The pull request run itself, the merge gate, must stay.

set -Eeuo pipefail
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
CI="$REPO_ROOT/.github/workflows/ci.yml"
fail() { echo "FAIL: $*" >&2; exit 1; }

# The `on:` block, without its comments: from `on:` to the next top-level key.
triggers=$(awk '/^on:/{p=1; next} p && /^[a-z]/{exit} p' "$CI" | sed 's/#.*//')
grep -qE '^  pull_request:' <<<"$triggers" || fail "$CI no longer runs on pull_request: nothing would gate a merge"
if grep -qE '^  push:' <<<"$triggers"; then
  fail "$CI runs on push again: with up-to-date branches required, that repeats the pull request's run"
fi
echo "ok   runs on pull requests, not again after the merge"

concurrency=$(awk '/^concurrency:/{p=1; next} p && /^[a-z]/{exit} p' "$CI" | sed 's/#.*//')
grep -qF 'github.event.pull_request.number' <<<"$concurrency" || fail "$CI has no concurrency group per pull request"
grep -qE '^  cancel-in-progress: true' <<<"$concurrency" || fail "$CI does not cancel the run of a replaced commit"
echo "ok   a new commit cancels the run it replaces"

grep -qF -- '--jobs "$(nproc)"' "$CI" || fail "$CI does not run one test file per core: idle cores are billed"
echo "ok   each runner uses all its cores"
