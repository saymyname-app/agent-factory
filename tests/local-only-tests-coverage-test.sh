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
#      all pass, and files a bead and pages the Mayor when one fails;
#   5. a test that exits 77 is SKIPPED, not failed: the run names it with its
#      reason even under --quiet, pages nobody for it alone, and the bead of a
#      failing run names it too;
#   6. tests/lib/capture-browser.sh skips only on the browser's own "No usable
#      sandbox" refusal (af-yb2cb5); a browser that starts, or fails another
#      way, lets the test run.

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

# --- 5. A test that cannot run on this host is SKIPPED, visibly -------------
cat >"$FAKE/tests/host-cannot-test.sh" <<'EOF'
#!/usr/bin/env bash
# ci: local-only — fake test whose host lacks what it needs
echo 'some setup output'
echo 'SKIP: the capture browser does not start on this host (af-yb2cb5)'
exit 77
EOF
chmod +x "$FAKE/tests/host-cannot-test.sh"
rm -f "$TMP/gc.calls" "$TMP/door.calls"
if out=$(run --quiet); then fail "a run with a failing and a skipped test exited 0: $out"; fi
grep -q 'SKIPPED tests/host-cannot-test.sh.*capture browser does not start.*af-yb2cb5' <<<"$out" \
  || fail "a quiet run does not name the skipped test with its reason: $out"
if grep -q 'FAIL tests/host-cannot-test.sh' <<<"$out"; then fail "a skipped test was counted as failed: $out"; fi
grep -q 'tests/host-cannot-test.sh.*af-yb2cb5' "$TMP/gc.calls" || fail "the bead does not name the skipped test: $(cat "$TMP/gc.calls")"
grep -q 'found 1 failing test' "$TMP/gc.calls" || fail "the bead counts the skipped test as a failure: $(cat "$TMP/gc.calls")"

rm -f "$FAKE/tests/broken-test.sh" "$TMP/gc.calls" "$TMP/door.calls"
out=$(run --quiet) || fail "a run with a skipped test and no failure exited non-zero: $out"
grep -q 'SKIPPED tests/host-cannot-test.sh.*af-yb2cb5' <<<"$out" || fail "the skip is not named on a green run: $out"
[ ! -e "$TMP/door.calls" ] || fail "a run with nothing failed paged somebody"
if grep -q 'bd create' "$TMP/gc.calls" 2>/dev/null; then fail "a run with nothing failed filed a bead"; fi

# exit 77 alone (e.g. a fixture's own 77 leaking through set -e) is a failure:
# only a test that says why with a SKIP: line is skipped.
printf '#!/usr/bin/env bash\n# ci: local-only — fake test exiting 77 silently\nexit 77\n' >"$FAKE/tests/silent-77-test.sh"
chmod +x "$FAKE/tests/silent-77-test.sh"
rm -f "$TMP/gc.calls" "$TMP/door.calls"
if out=$(run --quiet); then fail "a test exiting 77 without a SKIP: line was not counted as failed: $out"; fi
if grep -q 'SKIPPED tests/silent-77-test.sh' <<<"$out"; then fail "a silent exit 77 was skipped: $out"; fi
grep -q 'tests/silent-77-test.sh' "$TMP/gc.calls" || fail "the bead does not name the silent exit 77 as failing"
rm -f "$FAKE/tests/silent-77-test.sh" "$TMP/gc.calls" "$TMP/door.calls"

# --- 6. The capture-browser probe skips on the sandbox refusal only ---------
fake_browser() { # <name> <stderr line> <exit code>
  printf '#!/usr/bin/env bash\necho %q >&2\nexit %s\n' "$2" "$3" >"$TMP/bin/$1"
  chmod +x "$TMP/bin/$1"
}
fake_browser refused '[1015:FATAL:zygote_host_impl_linux.cc:129] No usable sandbox! If you are running on Ubuntu 23.10+' 133
fake_browser starts '' 0
fake_browser broken 'error while loading shared libraries: libnss3.so' 127
probe() { bash -c '. "$1/tests/lib/capture-browser.sh"; skip_unless_capture_browser_sandbox "$2"; echo ran' _ "$ROOT" "$TMP/bin/$1"; }
rc=0; out=$(probe refused) || rc=$?
[ "$rc" = 77 ] || fail "a browser refused by the host sandbox exits $rc, not the skip code 77: $out"
grep -q '^SKIP: .*No usable sandbox.*af-yb2cb5' <<<"$out" || fail "the skip does not say why nor name af-yb2cb5: $out"
[ "$(probe starts)" = ran ] || fail "a browser that starts did not let the test run"
[ "$(probe broken 2>/dev/null)" = ran ] || fail "a browser broken another way was skipped instead of failing the test"

echo "PASS: every local-only test is run by bin/local-only-tests or excluded with its reason; one its host cannot run is named SKIPPED"
