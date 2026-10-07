#!/usr/bin/env bash
#
# No shell script of the Factory pipes a process into `grep -q`.
#
# Under `set -o pipefail`, `producer | grep -q PATTERN` is not a reliable
# question. grep -q exits at its first match; a producer that still has
# output to write then dies of SIGPIPE (exit 141), pipefail makes that the
# status of the pipeline, and a real match is read as "no match". Whether
# the producer is still writing at that instant is a race the host load
# decides, so the wrong answer comes and goes: on 2026-10-07, under a host
# load of 15 to 25, tests/sandbox-isolation-check-test.sh reported a
# different compliant test as a violation on each run, and passed again once
# the load dropped. The same race turns `... | grep -q X || fail` into a
# false failure and `... | grep -q X && fail` into a false pass.
#
# The rule: read the producer's output whole, then ask.
#   grep -q PATTERN <<<"$(producer)"        # or a variable filled earlier
# `producer | grep PATTERN >/dev/null` also reads everything with the grep
# measured here (GNU grep 3.11), and this check does not flag it; the
# here-string form is preferred because it has no producer left to kill,
# whatever the reader does.
#
# One producer is accepted: the shell builtins `printf` and `echo` printing
# a value already in memory. They hand the value to the pipe in one write,
# which is complete before grep can exit, so nothing is left to be cut off.
# That holds while the value fits in a pipe (64 KiB on Linux); for anything
# that may grow past it, use the here-string form above.
#
# A line that must keep the shape for a reason this check cannot see carries
#   # pipefail: allow-early-exit — <reason>
# on itself or on the line before it.
#
# The check covers every shell script under bin/, tests/, assets/, lib/ and
# .githooks/, with or without pipefail in the file itself: a library is
# sourced by callers that set it, and a script may gain it later. `| head`
# and other readers that stop early have the same mechanism but are not
# covered here: their producers in this repository print a few lines in one
# write, and their result is rarely a yes/no answer.

set -Eeuo pipefail
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SELF=$(basename -- "${BASH_SOURCE[0]}")

fail() { printf 'FAIL: %s\n' "$1" >&2; }

# A single `|`: `a || grep -q b file` is two commands, not a pipeline.
EARLY_EXIT='(^|[^|])\|[[:space:]]*(grep|egrep|fgrep)[[:space:]]+(-[A-Za-z-]+[[:space:]]+)*(-[A-Za-z]*q|--quiet)'
IN_MEMORY='(^|[^[:alnum:]_./-])(printf|echo)[[:space:]][^|]*'"$EARLY_EXIT"
MARKER='pipefail: allow-early-exit'

is_shell_script() {
  local f=$1 first=""
  case "$f" in *.sh) return 0 ;; esac
  IFS= read -r first <"$f" 2>/dev/null || true
  [[ $first == '#!'*sh* ]]
}

# Prints one line per offending pipeline of <file>; exits 1 if there is any.
check_file() {
  local f=$1 lineno text prev found=0
  while IFS=: read -r lineno text; do
    [ -n "$lineno" ] || continue
    [[ $text =~ ^[[:space:]]*# ]] && continue
    [[ $text =~ $IN_MEMORY ]] && continue
    [[ $text == *"$MARKER"* ]] && continue
    prev=$((lineno - 1))
    if [ "$prev" -ge 1 ] && [[ $(sed -n "${prev}p" "$f") == *"$MARKER"* ]]; then
      continue
    fi
    echo "$f:$lineno pipes a process into grep -q: under pipefail a real match reads as no match when the producer dies of SIGPIPE -- use grep -q PATTERN <<<\"\$(producer)\""
    found=1
  done < <(grep -nE "$EARLY_EXIT" "$f" || true)
  [ "$found" -eq 0 ]
}

violations=0
while IFS= read -r f; do
  [ "$(basename -- "$f")" = "$SELF" ] && continue
  is_shell_script "$f" || continue
  out=$(check_file "$f") || { fail "$out"; violations=$((violations + 1)); }
done < <(
  for d in bin tests assets lib .githooks; do
    [ -d "$REPO_ROOT/$d" ] && find "$REPO_ROOT/$d" -type f
  done | sort
)

tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT

# The mechanism itself, so this file stays honest about what it forbids: a
# producer that writes more than a pipe holds, whose first line matches, is
# killed before it finishes, and pipefail reports the match as a failure.
# Read whole first, the same question gets the right answer.
seq -f 'needle %.0f: a line long enough for the whole output to exceed what one pipe can hold' 1 40000 >"$tmp/large.txt"
# (141 when SIGPIPE kills the producer; its own write error when the caller
# ignores SIGPIPE, as a systemd service does by default. Wrong either way.)
rc=0
cat "$tmp/large.txt" 2>/dev/null | grep -q 'needle 1:' || rc=$? # pipefail: allow-early-exit — this line is the reproduction
[ "$rc" -ne 0 ] || { fail "the early-exit pipeline did not reproduce the false negative (status 0) -- the premise of this check no longer holds on this host"; violations=$((violations + 1)); }
grep -q 'needle 1:' <<<"$(cat "$tmp/large.txt")" || { fail "the here-string form does not find a match that is there"; violations=$((violations + 1)); }

# The check catches what it claims to: a process piped into grep -q is
# flagged, on one line or continued on the next, whatever the flags.
cat >"$tmp/offender.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
git diff --name-only | grep -qE '^orders/' && echo reload
grep -v '^#' "$1" | grep -Fxq -- "$2" || exit 1
(cd "$ROOT" && tracker show "$1" --json) \
  | grep -q 'Constats hors ticket'
status | grep -i --quiet running
EOF
out=$(check_file "$tmp/offender.sh") && { fail "the check does not flag a process piped into grep -q"; violations=$((violations + 1)); }
flagged=$(grep -c . <<<"$out")
[ "$flagged" -eq 4 ] || { fail "the check flagged $flagged of the 4 early-exit pipelines of its synthetic offender: $out"; violations=$((violations + 1)); }

# ... and leaves alone what is safe: a value read whole first, a builtin
# printing a value in memory, a comment, a marked line, a grep that reads
# everything (no -q), and a shebang-less file that only looks like shell.
cat >"$tmp/compliant.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
grep -qE '^orders/' <<<"$(git diff --name-only)" && echo reload
printf '%s\n' "$out" | grep -qF "PR #20" || exit 1
[ -n "$x" ] && echo "$x" | grep -Fxq -- "$y"
# never: git log | grep -q fix
# pipefail: allow-early-exit — fixture reason
tail -f "$LOG" | grep -q ready
git log --oneline | grep -c fix
grep -q one "$OUT" || grep -q two "$ERR"
EOF
out=$(check_file "$tmp/compliant.sh") || { fail "the check false-positives on safe forms: $out"; violations=$((violations + 1)); }

printf 'notes: status | grep -q running\n' >"$tmp/notes.txt"
is_shell_script "$tmp/notes.txt" && { fail "a file that is not a shell script is treated as one"; violations=$((violations + 1)); }

if [ "$violations" -gt 0 ]; then
  echo "pipefail-early-exit-check: $violations violation(s)" >&2
  exit 1
fi

printf 'PASS: no shell script pipes a process into grep -q\n'
