#!/usr/bin/env bash
# Every test marked `# ci: local-only` runs somewhere (T49, af-xcfup7).
#
# CI cannot run a local-only test, so bin/local-only-tests is the one place
# that does, nightly. It used to carry a list of four names: seven adoption
# trials of D01 were red on main and nothing said so. This test holds the
# runner to the marker itself: a marked file is either run or named, with its
# reason, in the versioned exclusions (config/local-only-tests-exclusions.txt).
#
# What is checked, through the command line of the runner only:
#   1. on this repository, the marked files are exactly the files the runner
#      says it runs plus the files it says it excludes;
#   2. on a fake root, a marked file added to tests/ is run without touching
#      the runner, an excluded one is not run, an unmarked one is ignored;
#   3. an exclusion that names no marked file, or gives no reason, is refused;
#   4. a run names every test it ran and every test it excluded, exits 0 when
#      all pass, and files a bead and pages the Mayor when one fails.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
TOOL="$ROOT/bin/local-only-tests"
MARKER='^#[[:space:]]*ci:[[:space:]]*local-only'

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

TMP=$(mktemp -d /tmp/af-xcfup7-local-only-coverage.XXXXXX)
trap 'rm -rf -- "$TMP"' EXIT

# --- 1. This repository: nothing marked is left out -------------------------
listing=$(FACTORY_ROOT="$ROOT" "$TOOL" --list) || fail "--list refused this repository: $listing"
marked=$(cd "$ROOT" && grep -lE "$MARKER" tests/*.sh tests/*.py | sort)
[ -n "$marked" ] || fail "no marked file found: the check would pass on nothing"
covered=$(printf '%s\n' "$listing" | awk '$1 == "run" || $1 == "excluded" { print $2 }' | sort)
[ "$marked" = "$covered" ] || fail "marked files and files run or excluded differ:
$(diff <(printf '%s\n' "$marked") <(printf '%s\n' "$covered") || true)"
twice=$(printf '%s\n' "$covered" | uniq -d)
[ -z "$twice" ] || fail "listed both as run and as excluded: $twice"
while read -r kind path reason; do
  [ "$kind" = excluded ] || continue
  [ -n "$reason" ] || fail "$path is excluded without a reason"
done <<<"$listing"
printf '%s\n' "$listing" | grep -q '^run ' || fail "the runner runs nothing on this repository"

# --- 2. A fake root: the marker alone decides -------------------------------
FAKE="$TMP/root"
mkdir -p "$FAKE/tests" "$FAKE/config" "$TMP/bin" "$TMP/ran"
fake_test() { # <name> <marked: yes|no> <exit code>
  {
    echo '#!/usr/bin/env bash'
    [ "$2" = yes ] && echo '# ci: local-only — fake test of the coverage check'
    echo "touch '$TMP/ran/$1'"
    echo "echo 'output of $1'"
    echo "exit $3"
  } >"$FAKE/tests/$1"
  chmod +x "$FAKE/tests/$1"
}
fake_test alpha-test.sh yes 0
fake_test needs-mayor-test.sh yes 1
fake_test plain-test.sh no 1
printf '%s\n' '# path  reason' \
  'tests/needs-mayor-test.sh  vraie session du Mayor' >"$FAKE/config/local-only-tests-exclusions.txt"

list() { FACTORY_ROOT="$FAKE" "$TOOL" --list; }
out=$(list) || fail "--list refused the fake root: $out"
[ "$out" = "run tests/alpha-test.sh
excluded tests/needs-mayor-test.sh vraie session du Mayor" ] || fail "unexpected listing of the fake root:
$out"

fake_test added-later-test.sh yes 0
out=$(list)
grep -qx 'run tests/added-later-test.sh' <<<"$out" \
  || fail "a marked test added to tests/ is not run: $out"

# --- 3. A stale or unexplained exclusion is refused -------------------------
refused() { # <label> <exclusions content>
  local saved="$TMP/exclusions.saved" out
  cp "$FAKE/config/local-only-tests-exclusions.txt" "$saved"
  printf '%s\n' "$2" >"$FAKE/config/local-only-tests-exclusions.txt"
  if out=$(list 2>&1); then
    cp "$saved" "$FAKE/config/local-only-tests-exclusions.txt"
    fail "$1: --list accepted it: $out"
  fi
  cp "$saved" "$FAKE/config/local-only-tests-exclusions.txt"
  grep -q "$3" <<<"$out" || fail "$1: the refusal does not name $3: $out"
}
refused "an exclusion without a reason" 'tests/needs-mayor-test.sh' 'tests/needs-mayor-test.sh'
refused "an exclusion of a file that does not exist" 'tests/gone-test.sh  vraie session de modèle' 'tests/gone-test.sh'
refused "an exclusion of an unmarked file" 'tests/plain-test.sh  vraie session de modèle' 'tests/plain-test.sh'

# --- 4. A run: names what it ran and what it left out, pages on failure -----
# Stand-ins for gc and the escalation door: the run must not reach a city.
cat >"$TMP/bin/gc" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >>"$TMP/gc.calls"
case "\$*" in *"bd create"*) echo '{"id":"fake-1"}' ;; esac
EOF
cat >"$TMP/bin/door" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >>"$TMP/door.calls"
EOF
chmod +x "$TMP/bin/gc" "$TMP/bin/door"
run() { PATH="$TMP/bin:$PATH" FACTORY_ROOT="$FAKE" ESCALATION_DOOR_BIN="$TMP/bin/door" "$TOOL" "$@"; }

rm -f "$TMP/ran"/*
out=$(run) || fail "a run where every test passes exited non-zero: $out"
for t in alpha-test.sh added-later-test.sh; do
  [ -e "$TMP/ran/$t" ] || fail "$t was not run"
  grep -q "PASS tests/$t" <<<"$out" || fail "the output does not name $t as run: $out"
done
[ ! -e "$TMP/ran/needs-mayor-test.sh" ] || fail "an excluded test was run"
[ ! -e "$TMP/ran/plain-test.sh" ] || fail "an unmarked test was run"
grep -q 'EXCLUDED tests/needs-mayor-test.sh.*vraie session du Mayor' <<<"$out" \
  || fail "the output does not name the excluded test with its reason: $out"
[ ! -e "$TMP/door.calls" ] || fail "a green run paged somebody"

fake_test broken-test.sh yes 1
if out=$(run); then fail "a run with a failing test exited 0: $out"; fi
grep -q 'FAIL tests/broken-test.sh' <<<"$out" || fail "the output does not name the failing test: $out"
grep -q 'PASS tests/alpha-test.sh' <<<"$out" || fail "a failure stopped the other tests: $out"
grep -q 'bd create' "$TMP/gc.calls" 2>/dev/null || fail "no bead was filed for the failing test"
grep -q '^mayor fake-1 ' "$TMP/door.calls" 2>/dev/null || fail "the Mayor was not paged through the escalation door"
grep -q 'tests/broken-test.sh' "$TMP/gc.calls" || fail "the bead does not name the failing test"

echo "PASS: every local-only test is run by bin/local-only-tests or excluded with its reason"
