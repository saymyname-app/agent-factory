#!/usr/bin/env bash
#
# No test asks, or signals, the host's process list by a fixed name.
#
# The host runs more than one copy of the tests at a time: a local battery,
# and the Factory CI jobs of its own runner, which do not queue behind the
# battery lock (af-r1ymfm). `pgrep NAME` and `pkill NAME` answer for the
# whole host, so a test that reads them sees the other copy's processes, and
# one that signals them kills the other copy's. On 2026-10-08
# tests/project-launch-test.py compared two `pgrep -fa project-launch`
# snapshots to prove a refused start had started nothing, and failed because
# a CI job running the same tests ended a process between the two
# (af-29xv7v).
#
# The rule: a test reads what it created itself -- the children of its own
# process, its own state file -- or matches on a path only it owns:
#   pkill -f -- "$TRIAL/"                      # shell: the pattern is a variable
#   ["pgrep", "-f", "--", str(self.dir)]       # Python: the pattern is computed
# `killall` has no such form and is always refused.
#
# A line that must name these commands for a reason this check cannot see
# carries
#   # host-process: allow — <reason>
# on itself or on the line before it.
#
# What this check does not see: whether the variable holds a path only this
# run owns (a `mktemp -d` directory does, a fixed directory does not), fixed
# ports and fixed names under /tmp. Those were searched by hand on
# 2026-10-08 (af-29xv7v).

set -Eeuo pipefail
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SELF=$(basename -- "${BASH_SOURCE[0]}")

fail() { printf 'FAIL: %s\n' "$1" >&2; }

CALL='(^|[^[:alnum:]_.-])(pgrep|pkill|killall)([^[:alnum:]_-]|$)'
OWN_SHELL='(pgrep|pkill)[[:space:]]+(-[A-Za-z0-9]+[[:space:]]+)*-f[[:space:]]+--[[:space:]]+"\$\{?[A-Za-z_]'
OWN_PYTHON='"(pgrep|pkill)",[[:space:]]*("-[A-Za-z0-9]+",[[:space:]]*)*"-f",[[:space:]]*"--",[[:space:]]*str\('
MARKER='host-process: allow'

# Prints one line per offending line of <file>; exits 1 if there is any.
check_file() {
  local f=$1 lineno text prev found=0
  while IFS=: read -r lineno text; do
    [ -n "$lineno" ] || continue
    [[ $text =~ ^[[:space:]]*# ]] && continue
    [[ $text =~ $OWN_SHELL ]] && continue
    [[ $text =~ $OWN_PYTHON ]] && continue
    [[ $text == *"$MARKER"* ]] && continue
    prev=$((lineno - 1))
    if [ "$prev" -ge 1 ] && [[ $(sed -n "${prev}p" "$f") == *"$MARKER"* ]]; then
      continue
    fi
    echo "$f:$lineno reads or signals the host's process list by a fixed name: another battery or a CI job on the same host changes the answer -- read the children of your own process, or match a path only this run owns (pgrep -f -- \"\$OWN_DIR/\")"
    found=1
  done < <(grep -InE "$CALL" "$f" || true)
  [ "$found" -eq 0 ]
}

violations=0
while IFS= read -r f; do
  [ "$(basename -- "$f")" = "$SELF" ] && continue
  out=$(check_file "$f") || { fail "$out"; violations=$((violations + 1)); }
done < <(find "$REPO_ROOT/tests" -type f | sort)

tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT

# The check catches what it claims to: a fixed name, in shell or in Python,
# whatever the flags, and killall in any form.
cat >"$tmp/offender.sh" <<'EOF'
#!/usr/bin/env bash
pgrep -fa project-launch >"$before"
pkill -9 -f "fixture-server"
[ -z "$(pgrep dolt)" ] || exit 1
killall -q "$NAME"
EOF
cat >"$tmp/offender.py" <<'EOF'
before = subprocess.run(("pgrep", "-fa", "project-launch"), capture_output=True)
subprocess.run(["pkill", "-f", "fixture-server"])
EOF
out=$(check_file "$tmp/offender.sh") && { fail "the check does not flag a fixed name in a shell test"; violations=$((violations + 1)); }
flagged=$(grep -c . <<<"$out")
[ "$flagged" -eq 4 ] || { fail "the check flagged $flagged of the 4 lines of its shell offender: $out"; violations=$((violations + 1)); }
out=$(check_file "$tmp/offender.py") && { fail "the check does not flag a fixed name in a Python test"; violations=$((violations + 1)); }
flagged=$(grep -c . <<<"$out")
[ "$flagged" -eq 2 ] || { fail "the check flagged $flagged of the 2 lines of its Python offender: $out"; violations=$((violations + 1)); }

# ... and leaves alone a pattern that is a path of the run's own, a comment,
# a marked line, and a word that only contains the name.
cat >"$tmp/compliant.sh" <<'EOF'
#!/usr/bin/env bash
pkill -f -- "$TRIAL/" >/dev/null 2>&1 || true
pgrep -f -- "${SANDBOX_DIR}" >/dev/null 2>&1 || break
pkill -9 -f -- "$TEST_TMPDIR" >/dev/null 2>&1 || true
# never: pgrep -fa project-launch
# host-process: allow — fixture reason
for name in tmux pkill pgrep; do :; done
my-pgrep-wrapper "$x"
EOF
cat >"$tmp/compliant.py" <<'EOF'
subprocess.run(["pkill", "-f", "--", str(self.dir)], capture_output=True)
found = subprocess.run(["pgrep", "-f", "--", str(self.dir)],
subprocess.run(["pkill", "-9", "-f", "--", str(self.dir)], capture_output=True)
EOF
out=$(check_file "$tmp/compliant.sh") || { fail "the check false-positives on safe shell forms: $out"; violations=$((violations + 1)); }
out=$(check_file "$tmp/compliant.py") || { fail "the check false-positives on safe Python forms: $out"; violations=$((violations + 1)); }

if [ "$violations" -gt 0 ]; then
  echo "host-wide-process-check: $violations violation(s)" >&2
  exit 1
fi

printf 'PASS: no test reads or signals the host process list by a fixed name\n'
