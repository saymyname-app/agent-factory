#!/usr/bin/env bash
#
# A test that reaches the live Factory city, or names its absolute path,
# fails silently on the author's own machine (the path exists, the city is
# there) and either fails mysteriously or corrupts shared state on any other
# machine or CI runner. tests/lib/sandbox.sh|py (P10, af-ygibh) gives every
# test a throwaway HOME/city/beads-dir/tmux-dir with fake gc/bd/gh/codex/
# claude first on PATH; this check is what keeps a new test from skipping
# that and reaching for the real thing by mistake.
#
# A file is exempt from the "no literal live root" rule if it is marked
#   # ci: local-only — <reason>
# (it only ever runs on the live host testing live-host-specific state, so
# naming that host's path is the point, not a bug), or if the specific
# offending line carries a trailing/preceding
#   # sandbox: allow-live-root — <reason>
# marker (e.g. a test asserting on real operator-facing documentation text
# that itself names the path).
#
# A file is exempt from the "no real gc/bd without opting in" rule if it
# sources tests/lib/sandbox.sh, imports tests/lib/sandbox.py's Sandbox, is
# marked # ci: local-only (the existing, narrower opt-in this repo already
# used before the shared harness existed), or routes gc/bd through its own
# PATH/GC_BIN/BD_BIN indirection instead of calling the installed binary
# directly.

set -Eeuo pipefail
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SELF=$(basename -- "${BASH_SOURCE[0]}")
LIVE_ROOT="/home/benja/agent-factory"

fail() { printf 'FAIL: %s\n' "$1" >&2; }

is_local_only() {
  grep -qE '^#[[:space:]]*ci:[[:space:]]*local-only' "$1"
}

# Live-root literal check: every match must be either in a local-only file,
# or have an allow-live-root marker on its own line or the line before it.
check_live_root() {
  local f=$1 lineno prev
  [ -e "$f" ] || return 0
  is_local_only "$f" && return 0
  while IFS=: read -r lineno _; do
    [ -n "$lineno" ] || continue
    if sed -n "${lineno}p" "$f" | grep -qF 'sandbox: allow-live-root'; then
      continue
    fi
    prev=$((lineno - 1))
    if [ "$prev" -ge 1 ] && sed -n "${prev}p" "$f" | grep -qF 'sandbox: allow-live-root'; then
      continue
    fi
    echo "$f:$lineno names the live Factory root ($LIVE_ROOT) with no # sandbox: allow-live-root marker"
    return 1
  done < <(grep -nF "$LIVE_ROOT" "$f")
  return 0
}

# Real-gc-without-opt-in check: a file that invokes `gc` or `bd` as an
# actual shell command (line start, or after a command separator) -- not
# just naming "gc"/"bd" inside a comment, docstring or a quoted grep
# pattern -- must show one of the recognized isolation opt-ins somewhere in
# it.
check_gc_opt_in() {
  local f=$1
  [ -e "$f" ] || return 0
  grep -vE '^[[:space:]]*#' "$f" \
    | grep -qE '(^|;|&&|\|\||\$\()[[:space:]]*(gc|bd)[[:space:]]' || return 0
  is_local_only "$f" && return 0
  grep -qE 'tests/lib/sandbox\.(sh|py)|sandbox_init|from sandbox import Sandbox|sandbox\.Sandbox\(|PATH=|GC_BIN|BD_BIN' "$f" && return 0
  echo "$f calls gc/bd with no isolation opt-in (source tests/lib/sandbox.sh, use tests/lib/sandbox.py's Sandbox, put a stub first on PATH, or mark # ci: local-only)"
  return 1
}

violations=0
for f in "$REPO_ROOT"/tests/*.sh "$REPO_ROOT"/tests/*.py; do
  [ -e "$f" ] || continue
  [ "$(basename -- "$f")" = "$SELF" ] && continue
  out=$(check_live_root "$f") || { fail "$out"; violations=$((violations + 1)); }
  out=$(check_gc_opt_in "$f") || { fail "$out"; violations=$((violations + 1)); }
done

# Prove the check actually catches what it claims to, not just that the
# current tree is clean (the same shape as tests/ci-registration-test.sh's
# own self-check): a synthetic file with both violations must be flagged.
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
cat >"$tmp/offender.sh" <<EOF
#!/usr/bin/env bash
echo "$LIVE_ROOT"
gc bd list
EOF
canary=0
out=$(check_live_root "$tmp/offender.sh") || canary=$((canary + 1))
out=$(check_gc_opt_in "$tmp/offender.sh") || canary=$((canary + 1))
[ "$canary" -eq 2 ] || { fail "the check does not catch its own synthetic violations -- it would pass anything"; violations=$((violations + 1)); }

if [ "$violations" -gt 0 ]; then
  echo "sandbox-isolation-check: $violations violation(s)" >&2
  exit 1
fi

printf 'PASS: no test names the live Factory root or calls gc/bd without an isolation opt-in\n'
