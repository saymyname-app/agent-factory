#!/usr/bin/env bash
#
# factory-guard must self-heal a lost executable bit on a tracked bin/ file.
#
# This is not hypothetical (af-ogg8z): between 2026-09-17 23:08 and
# 2026-09-18 01:01, bin/provider-failover lost its executable bit when the
# Mayor ran git commands directly in the live root. It still existed (the
# guard's `-e` runtime-files check stayed green) but every invocation failed
# exit 126, silently, for ~2 hours -- nothing checked `-x`. This test proves
# the guard now does, and repairs it within one run.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/factory-guard"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

[ -x "$GUARD" ] || fail "$GUARD is not executable"

# --- a throwaway city with the critical files factory-guard also checks ----
git init -q --bare "$TMP/origin.git"
git init -q "$TMP/city"
cd "$TMP/city"
git config user.email t@t; git config user.name t; git config commit.gpgsign false
git remote add origin "$TMP/origin.git"
mkdir -p .gc bin orders
printf '[workspace]\nprovider = "claude"\n' > city.toml
for f in pr-autopilot factory-guard provider-failover factory-watchdog; do
  printf '#!/usr/bin/env bash\necho %s\n' "$f" > "bin/$f"
  chmod +x "bin/$f"
  touch "orders/$f.toml"
done
git add -A
git commit -qm city
git branch -M main
git push -q origin main
git fetch -q origin

guard() { FACTORY_ROOT="$TMP/city" "$GUARD" "$@" 2>&1 || true; }

# --- baseline: everything executable, guard reports it and repairs nothing --
out=$(guard --check-only)
grep -q "exec-bits — every bin/ file" <<<"$out" \
  || { printf '%s\n' "$out" >&2; fail "guard did not report a clean exec-bit state"; }

# --- lose the bit on a tracked 100755 file, like the 2026-09-17 incident ---
chmod -x bin/provider-failover
[ -x bin/provider-failover ] && fail "test setup broken: chmod -x did not take"

# --check-only must report, not repair
out=$(guard --check-only)
grep -q "tracked executable(s) under bin/ lost their +x bit" <<<"$out" \
  || { printf '%s\n' "$out" >&2; fail "--check-only did not flag the lost executable bit"; }
[ -x bin/provider-failover ] && fail "--check-only must not mutate the file"

# a normal (repairing) run must restore it and log a FIXED-style line
out=$(guard)
grep -q "FIXED: restored the executable bit on bin/provider-failover" <<<"$out" \
  || { printf '%s\n' "$out" >&2; fail "guard did not log a FIXED line for the repair"; }
[ -x bin/provider-failover ] \
  || fail "guard did not actually restore the executable bit on disk"

# --- and it must go quiet once repaired -------------------------------------
out=$(guard --check-only)
grep -q "tracked executable(s)" <<<"$out" && { printf '%s\n' "$out" >&2; fail "guard still complains after the bit was restored"; }
grep -q "exec-bits — every bin/ file" <<<"$out" \
  || { printf '%s\n' "$out" >&2; fail "guard did not report a clean exec-bit state after repair"; }

# --- a file git does NOT track as 100755 is none of this check's business --
echo "not a script" > bin/notes.txt
git add bin/notes.txt
git commit -qm "add a non-executable tracked file"
out=$(guard --check-only)
grep -q "notes.txt" <<<"$out" && { printf '%s\n' "$out" >&2; fail "guard flagged a file git does not track as 100755"; }

echo "OK factory-guard repairs a lost bin/ executable bit and reports cleanly otherwise"
