#!/usr/bin/env bash
#
# af-fyc8eo: the "Syntax check" step of .github/workflows/ci.yml can fail.
#
# From the first commit of Factory CI (2026-09-15) its shell line ended with
# `|| true`, there to skip the files of bin/ that are not shell. It also hid
# every failure of `bash -n`: on 2026-10-06 the step printed a syntax error
# of bin/escalation-door, stayed green, and 8 test files went red later in
# the same run. Nothing reported that the step could not fail, because a
# check that never fails looks like a check that passes.
#
# So this does not read the step, it runs it: the script of the step is
# taken out of the workflow and run on small trees, one clean and one per
# kind of broken file. Any wording of the step that lets one of them through
# turns this red.

set -Eeuo pipefail
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
CI="$REPO_ROOT/.github/workflows/ci.yml"
STEP='Syntax check every Python and shell entry point'
fail() { echo "FAIL: $*" >&2; exit 1; }

# The `run: |` block of the step, without its ten columns of indentation.
script=$(awk -v name="      - name: $STEP" '
  $0 == name { s = 1; next }
  s && !p && /^        run: \|$/ { p = 1; next }
  s && !p && /^      - / { exit }
  p && /^          / { print substr($0, 11); next }
  p && /^$/ { print ""; next }
  p { exit }' "$CI")
[ -n "$script" ] || fail "$CI has no step named \"$STEP\" with a \`run: |\` block: nothing checks the syntax of bin/ before the tests"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# The step calls `python`, which the runner has; a host may only have python3.
if ! command -v python >/dev/null; then
  mkdir "$WORK/shim"
  ln -s "$(command -v python3)" "$WORK/shim/python"
  PATH="$WORK/shim:$PATH"
fi

# A clean tree. Its last file of bin/ is Python, as in the repository: the
# file the old `|| true` was there for.
new_tree() {
  local dir="$WORK/$1"
  mkdir -p "$dir/bin" "$dir/lib" "$dir/tests"
  printf 'VALUE = 1\n' > "$dir/lib/module.py"
  printf 'import unittest\n' > "$dir/tests/some-test.py"
  printf '#!/usr/bin/env bash\necho ok\n' > "$dir/bin/good-shell"
  printf '#!/usr/bin/env python3\nprint("ok")\n' > "$dir/bin/zz-good-python"
  printf '%s\n' "$dir"
}

OUT="$WORK/out"
run_step() { (cd "$1" && bash -c "$script") >"$OUT" 2>&1; }

tree=$(new_tree clean)
run_step "$tree" || { cat "$OUT" >&2; fail "the step fails on a tree with no syntax error"; }
echo "ok   a tree with no syntax error passes"

# must_fail <case> <file, relative to the tree> <what the step let through>
must_fail() {
  local tree="$WORK/$1" file=$2
  if run_step "$tree"; then
    cat "$OUT" >&2
    fail "the step is green on $3 ($file): it cannot fail on it"
  fi
  grep -qF "$file" "$OUT" || { cat "$OUT" >&2; fail "the step fails on $3 without naming $file"; }
  echo "ok   fails on $3"
}

tree=$(new_tree shell)
printf '#!/usr/bin/env bash\nif true; then\n' > "$tree/bin/aa-broken"
must_fail shell bin/aa-broken "a shell script with a syntax error, first of bin/"
grep -qF "ok bin/good-shell" "$OUT" || { cat "$OUT" >&2; fail "the step stops at the first broken file: the others are not checked"; }
echo "ok   the files after a broken one are still checked"

tree=$(new_tree shell-last)
printf '#!/bin/sh\nfor x in a; do\n' > "$tree/bin/zzz-broken"
must_fail shell-last bin/zzz-broken "a /bin/sh script with a syntax error, last of bin/"

tree=$(new_tree shell-flag)
printf '#!/bin/bash -e\ncase x in\n' > "$tree/bin/broken-flag"
must_fail shell-flag bin/broken-flag "a shell script whose first line carries an option"

tree=$(new_tree python-bin)
printf '#!/usr/bin/env python3\ndef broken(:\n' > "$tree/bin/broken-python"
must_fail python-bin bin/broken-python "a Python entry point of bin/ with a syntax error"

tree=$(new_tree python-lib)
printf 'def broken(:\n' > "$tree/lib/broken.py"
must_fail python-lib lib/broken.py "a Python module of lib/ with a syntax error"

tree=$(new_tree unknown)
printf 'echo "no first line saying what runs me"\n' > "$tree/bin/unknown"
must_fail unknown bin/unknown "a file of bin/ whose first line names neither Python nor a shell"
