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
#
# A test that invokes bin/escalation-door, or a script that shells out to it
# (bin/factory-watchdog, bin/on-order-failed, bin/on-session-stranded), needs
# more than a PATH stub: every Gas City agent session pre-exports GC_BIN to
# the real installed `gc`, escalation-door resolves `${GC_BIN:-gc}`, and that
# indirection silently bypasses a stubbed PATH and reaches the live city
# (live incident 2026-09-29, af-0h4vnc: factory-watchdog-test.sh's PATH-only
# stub was bypassed exactly this way, paging the live Mayor and filing a real
# bead). Such a test must show an actual `GC_BIN=<something>` assignment, not
# merely the bare substring "GC_BIN" somewhere in the file, or source the
# shared harness (which now sets GC_BIN itself). The script list below is
# hand-picked to this one incident class -- other GC_BIN-resolving scripts
# (bin/deliver-close, bin/provider-failover, bin/ticket-graph-publish, ...)
# are a separate, broader gap tracked outside this ticket, not enforced here.

set -Eeuo pipefail
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SELF=$(basename -- "${BASH_SOURCE[0]}")
LIVE_ROOT="/home/benja/agent-factory"

fail() { printf 'FAIL: %s\n' "$1" >&2; }

is_local_only() {
  grep -qE '^#[[:space:]]*ci:[[:space:]]*local-only' "$1"
}

# The non-comment lines of a file, read whole before any question is asked
# of them. Never `producer | grep -q` here: this script runs under pipefail,
# grep -q exits at its first match, a producer that still has output to
# write then dies of SIGPIPE, and the pipeline reads a real match as "no
# match". On 2026-10-07, under host load, that reported a different
# compliant test as a violation on each run. The rule is enforced on every
# script by tests/pipefail-early-exit-check-test.sh.
code_lines() {
  grep -vE '^[[:space:]]*#' "$1" || true
}

# Live-root literal check: every match must be either in a local-only file,
# or have an allow-live-root marker on its own line or the line before it.
check_live_root() {
  local f=$1 lineno prev
  [ -e "$f" ] || return 0
  is_local_only "$f" && return 0
  while IFS=: read -r lineno _; do
    [ -n "$lineno" ] || continue
    if [[ $(sed -n "${lineno}p" "$f") == *'sandbox: allow-live-root'* ]]; then
      continue
    fi
    prev=$((lineno - 1))
    if [ "$prev" -ge 1 ] && [[ $(sed -n "${prev}p" "$f") == *'sandbox: allow-live-root'* ]]; then
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
  local f=$1 code
  [ -e "$f" ] || return 0
  code=$(code_lines "$f")
  grep -qE '(^|;|&&|\|\||\$\()[[:space:]]*(gc|bd)[[:space:]]' <<<"$code" || return 0
  is_local_only "$f" && return 0
  grep -qE 'tests/lib/sandbox\.(sh|py)|sandbox_init|from sandbox import Sandbox|sandbox\.Sandbox\(|PATH=|GC_BIN|BD_BIN' "$f" && return 0
  echo "$f calls gc/bd with no isolation opt-in (source tests/lib/sandbox.sh, use tests/lib/sandbox.py's Sandbox, put a stub first on PATH, or mark # ci: local-only)"
  return 1
}

# escalation-door itself, plus every bin/ script known to shell out to it.
GCBIN_ESCALATION_SCRIPTS="escalation-door factory-watchdog on-order-failed on-session-stranded"

check_gcbin_opt_in() {
  local f=$1 script code
  [ -e "$f" ] || return 0
  is_local_only "$f" && return 0
  grep -qE 'tests/lib/sandbox\.(sh|py)|sandbox_init|from sandbox import Sandbox|sandbox\.Sandbox\(' "$f" && return 0
  code=$(code_lines "$f")
  for script in $GCBIN_ESCALATION_SCRIPTS; do
    # Require a path-like reference (preceded by "/") so a prose mention
    # like "escalation-door's mayor-first class" in a comment or fail
    # message doesn't count as an invocation.
    grep -qE "/${script}([[:space:]\"'\`]|\$)" <<<"$code" || continue
    grep -qE 'GC_BIN[[:space:]]*=[^=]|"GC_BIN"[[:space:]]*:' <<<"$code" && return 0
    echo "$f invokes $script (resolves \${GC_BIN:-gc}) with no actual GC_BIN= assignment and no shared sandbox harness -- a PATH stub alone does not protect it"
    return 1
  done
  return 0
}

violations=0
for f in "$REPO_ROOT"/tests/*.sh "$REPO_ROOT"/tests/*.py; do
  [ -e "$f" ] || continue
  [ "$(basename -- "$f")" = "$SELF" ] && continue
  out=$(check_live_root "$f") || { fail "$out"; violations=$((violations + 1)); }
  out=$(check_gc_opt_in "$f") || { fail "$out"; violations=$((violations + 1)); }
  out=$(check_gcbin_opt_in "$f") || { fail "$out"; violations=$((violations + 1)); }
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

# Same proof for the escalation-door check: a synthetic test that invokes
# bin/escalation-door with only a PATH stub must be flagged; the same test
# with an actual GC_BIN= assignment must not be; and a file that only
# mentions "escalation-door" in prose (no leading "/") must not be flagged.
cat >"$tmp/gcbin-offender.sh" <<'EOF'
#!/usr/bin/env bash
export PATH="$TMP/bin:$PATH"
"$REPO_ROOT/bin/escalation-door" mayor af-fixture "test"
EOF
gcbin_canary=0
out=$(check_gcbin_opt_in "$tmp/gcbin-offender.sh") || gcbin_canary=$((gcbin_canary + 1))
[ "$gcbin_canary" -eq 1 ] || { fail "the escalation-door check does not catch a PATH-only stub invoking bin/escalation-door"; violations=$((violations + 1)); }

cat >"$tmp/gcbin-compliant.sh" <<'EOF'
#!/usr/bin/env bash
export PATH="$TMP/bin:$PATH"
export GC_BIN="$TMP/bin/gc"
"$REPO_ROOT/bin/escalation-door" mayor af-fixture "test"
EOF
out=$(check_gcbin_opt_in "$tmp/gcbin-compliant.sh") || { fail "the escalation-door check false-positives on a test that actually assigns GC_BIN"; violations=$((violations + 1)); }

cat >"$tmp/gcbin-prose-only.sh" <<'EOF'
#!/usr/bin/env bash
fail() { echo "did not route through escalation-door's mayor-first class"; }
EOF
out=$(check_gcbin_opt_in "$tmp/gcbin-prose-only.sh") || { fail "the escalation-door check false-positives on a file that only mentions escalation-door in prose"; violations=$((violations + 1)); }

# A match must be found wherever it sits in a file of any size. A file
# larger than a pipe holds makes the 2026-10-07 false answers deterministic
# for any check that pipes it into `grep -q` under pipefail: the GC_BIN
# assignment at the top of a compliant test was read as absent (a false
# violation), and a bare gc call at the top of an offender was read as
# absent too (a missed violation).
large_filler() {
  seq -f 'echo "filler line %.0f, long enough for the file to exceed what one pipe can hold"' 1 40000
}
{
  printf '%s\n' '#!/usr/bin/env bash' 'export GC_BIN="$TMP/bin/gc"'
  large_filler
  printf '%s\n' '"$REPO_ROOT/bin/escalation-door" mayor af-fixture "test"'
} >"$tmp/gcbin-compliant-large.sh"
out=$(check_gcbin_opt_in "$tmp/gcbin-compliant-large.sh") || { fail "the escalation-door check false-positives on a large test whose GC_BIN assignment comes first (a match cut short by an early-exit pipeline)"; violations=$((violations + 1)); }

{
  printf '%s\n' '#!/usr/bin/env bash' 'gc bd list'
  large_filler
} >"$tmp/offender-large.sh"
out=$(check_gc_opt_in "$tmp/offender-large.sh") && { fail "the gc/bd check misses a bare gc call at the top of a large test (a match cut short by an early-exit pipeline)"; violations=$((violations + 1)); }

if [ "$violations" -gt 0 ]; then
  echo "sandbox-isolation-check: $violations violation(s)" >&2
  exit 1
fi

printf 'PASS: no test names the live Factory root or calls gc/bd without an isolation opt-in\n'
