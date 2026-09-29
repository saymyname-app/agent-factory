#!/usr/bin/env bash
#
# factory-guard must finish inside its order's 180 s timeout with a report,
# even when the host is saturated.
#
# On 2026-09-28 14:09 the Windows host was saturated (a game froze mouse and
# screen). Unbounded gh/git/gc calls stretched a ~32 s run past 180 s and the
# controller killed the guard: order.failed "context deadline exceeded", no
# report at all, every check lost at once. Now each external call is bounded,
# a run deadline stops new sections, and whatever was not checked is reported
# as a problem -- a cut call is "unknown", never green and never a reason to
# act (a timed-out `gh pr list` must not remove a worktree).

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/factory-guard"
TMP=$(mktemp -d)
trap 'git -C "$TMP/repo" worktree remove --force "$TMP/wt" 2>/dev/null || true; rm -rf "$TMP"' EXIT

fail() { printf 'FAIL: %s\n' "$1" >&2; [ -n "${out:-}" ] && printf '%s\n' "$out" >&2; exit 1; }

# --- a throwaway repo whose worktree pins a squash-merged branch -------------
git init -q --bare "$TMP/origin.git"
git init -q "$TMP/repo"
cd "$TMP/repo"
git config user.email t@t; git config user.name t; git config commit.gpgsign false
git remote add origin "$TMP/origin.git"
echo one > file; git add file; git commit -qm one
git branch -M main; git push -q origin main
git checkout -qb feat/squashed
echo two > file; git commit -qam two; git push -q origin feat/squashed
git checkout -q main
echo three > file; git commit -qam three; git push -q origin main
git fetch -q origin
git worktree add -q "$TMP/wt" feat/squashed

# --- stubs: gh hangs on `pr list` (the saturated host); gc has no sessions ---
mkdir -p "$TMP/bin"
cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
case "\$*" in
  *"pr list"*) touch "$TMP/gh-called"; exec sleep 120 ;;
  *) exit 1 ;;
esac
STUB
cat > "$TMP/bin/gc" <<'STUB'
#!/usr/bin/env bash
case "$*" in *"session list"*) exit 0 ;; *) exit 1 ;; esac
STUB
chmod +x "$TMP/bin/gh" "$TMP/bin/gc"
export PATH="$TMP/bin:$PATH"

# --- (a) a hung gh is cut, the worktree stays, the run ends inside budget ----
# Budget 8 s, no grace: gh gets whatever is left before the hard stop.
start=$SECONDS
rc=0
out=$(FACTORY_ROOT="$TMP/repo" FACTORY_GUARD_BUDGET_SECONDS=8 FACTORY_GUARD_GRACE_SECONDS=0 \
  "$GUARD" --quiet 2>&1) || rc=$?
elapsed=$((SECONDS - start))
[ "$rc" = 0 ] || fail "(a) guard exited $rc instead of reporting and exiting 0"
[ -f "$TMP/gh-called" ] || fail "(a) the worktree check never reached gh"
[ "$elapsed" -lt 20 ] || fail "(a) guard ran ${elapsed}s: the hung gh was not cut"
[ -d "$TMP/wt" ] || fail "(a) guard removed a worktree while its PR state was unknown"
grep -q "PR state unknown (gh pr list timed out) — left in place" <<<"$out" \
  || fail "(a) the unknown PR state was not reported"
grep -q "✓ worktrees" <<<"$out" && fail "(a) worktrees reported green after a timeout"
grep -q "^timing: .* budget — loadavg [0-9]" <<<"$out" \
  || fail "(a) quiet run with a timeout printed no timing/loadavg line"
grep -q "sections: .*worktrees [0-9]*s" <<<"$out" || fail "(a) per-section durations missing"
grep -q "timed out: worktrees: gh pr list" <<<"$out" || fail "(a) the cut call was not named"
# the call ate the rest of the budget, so every later section is reported
grep -q "runtime-worktrees — not checked (time budget exhausted" <<<"$out" \
  || fail "(a) sections after the budget were not reported as not checked"

# --- (b) budget already spent: later sections reported, never silently green -
rm -f "$TMP/gh-called"
rc=0
out=$(FACTORY_ROOT="$TMP/repo" FACTORY_GUARD_BUDGET_SECONDS=0 "$GUARD" --quiet 2>&1) || rc=$?
[ "$rc" = 0 ] || fail "(b) guard exited $rc instead of reporting and exiting 0"
[ -f "$TMP/gh-called" ] && fail "(b) a section ran after the budget was spent"
[ -d "$TMP/wt" ] || fail "(b) a skipped section still removed the worktree"
for s in live-root-sync rig-sync work-backup worktrees runtime-worktrees delivery-proof planning-exception; do
  grep -q "! $s — not checked (time budget exhausted" <<<"$out" \
    || fail "(b) section '$s' was not reported as not checked"
done
grep -q "! invariants — not checked" <<<"$out" && fail "(b) the first section must always run"
grep -q "^timing: " <<<"$out" || fail "(b) a cut-short run printed no timing line"

# --- (c) a fast healthy gh: default budget, no timing noise, cleanup works ---
cat > "$TMP/bin/gh" <<'STUB'
#!/usr/bin/env bash
case "$*" in *"pr list"*"feat/squashed"*) echo MERGED ;; *) exit 1 ;; esac
STUB
out=$(FACTORY_ROOT="$TMP/repo" "$GUARD" --quiet 2>&1) || fail "(c) guard failed"
grep -q "^timing: " <<<"$out" && fail "(c) a fast run printed timing noise"
grep -q "not checked (time budget" <<<"$out" && fail "(c) a fast run skipped sections"
[ -d "$TMP/wt" ] && fail "(c) the stale worktree was not removed once gh answered MERGED"

echo "OK factory-guard time budget"
