#!/usr/bin/env bash
#
# O12: the Mayor's upkeep gestures (worktree cleanup, branch pruning, log
# rotation, dispatcher/preview restart, city config reload) used to be a
# free-text permission with no shared refusal criteria or record of what
# ran. bin/factory-maintain replaces that with one script per gesture; this
# test drives each directly and proves: refusal on unmerged/unpushed/unknown
# targets, that a successful action is undoable, and that every action is
# logged.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SCRIPT="$REPO_ROOT/bin/factory-maintain"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

[ -x "$SCRIPT" ] || fail "$SCRIPT is not executable"

git_init_repo() {
  local dir="$1"
  git init -q --bare "$dir/origin.git"
  git init -q "$dir/repo"
  git -C "$dir/repo" config user.email t@t
  git -C "$dir/repo" config user.name t
  git -C "$dir/repo" config commit.gpgsign false
  git -C "$dir/repo" remote add origin "$dir/origin.git"
  echo one > "$dir/repo/f" && git -C "$dir/repo" add -A && git -C "$dir/repo" commit -qm one
  git -C "$dir/repo" branch -M main
  git -C "$dir/repo" push -q origin main
  git -C "$dir/repo" remote set-head origin main >/dev/null 2>&1 || true
}

export FACTORY_ROOT="$TMP/root"
mkdir -p "$FACTORY_ROOT"
export FACTORY_MAINTAIN_LOG="$TMP/root/var/factory-maintain.log"
export HOME="$TMP/home"
mkdir -p "$HOME"

# ===========================================================================
# prune-merged-branches
# ===========================================================================
git_init_repo "$TMP/prune"
REPO="$TMP/prune/repo"

# a merged, fully-pushed branch -- eligible for deletion
git -C "$REPO" checkout -qb merged-and-pushed
git -C "$REPO" push -q origin merged-and-pushed
git -C "$REPO" checkout -q main
MERGED_SHA=$(git -C "$REPO" rev-parse merged-and-pushed)

# an unmerged branch -- must be refused
git -C "$REPO" checkout -qb unmerged-work
echo two > "$REPO/g" && git -C "$REPO" add -A && git -C "$REPO" commit -qm two
git -C "$REPO" push -q origin unmerged-work
git -C "$REPO" checkout -q main

# a branch with commits that were never pushed anywhere -- must be refused
# even though it has no unmerged content once merged locally, because there
# is no upstream to prove the deletion is recoverable
git -C "$REPO" checkout -qb merged-but-unpushed
echo three > "$REPO/h" && git -C "$REPO" add -A && git -C "$REPO" commit -qm three
git -C "$REPO" checkout -q main

OUT=$("$SCRIPT" prune-merged-branches --repo "$REPO" 2>&1) || fail "prune-merged-branches exited non-zero: $OUT"

git -C "$REPO" show-ref --verify --quiet refs/heads/merged-and-pushed \
  && fail "prune-merged-branches did not delete a merged, fully-pushed branch"
git -C "$REPO" show-ref --verify --quiet refs/heads/unmerged-work \
  || fail "prune-merged-branches deleted an unmerged branch"
git -C "$REPO" show-ref --verify --quiet refs/heads/merged-but-unpushed \
  || fail "prune-merged-branches deleted a branch with no upstream (never pushed)"

[ -f "$FACTORY_MAINTAIN_LOG" ] || fail "prune-merged-branches did not write a log entry"
grep -q "gesture=prune-merged-branches.*status=deleted.*branch=merged-and-pushed" "$FACTORY_MAINTAIN_LOG" \
  || fail "log entry for the deleted branch is missing"
grep -q "sha=$MERGED_SHA" "$FACTORY_MAINTAIN_LOG" || fail "log entry is missing the deleted branch's sha (needed for undo)"
grep -q "undo='git -C $REPO branch merged-and-pushed $MERGED_SHA'" "$FACTORY_MAINTAIN_LOG" \
  || fail "log entry did not record an undo command"

# the logged undo actually restores the branch
eval "$(grep "branch=merged-and-pushed" "$FACTORY_MAINTAIN_LOG" | sed -n "s/.*undo='\(.*\)'.*/\1/p")"
git -C "$REPO" show-ref --verify --quiet refs/heads/merged-and-pushed \
  || fail "the logged undo command did not restore the deleted branch"

echo "PASS: prune-merged-branches"

# ===========================================================================
# clean-worktrees
# ===========================================================================
git_init_repo "$TMP/clean"
REPO2="$TMP/clean/repo"
WT_ROOT="$TMP/clean-worktrees"
mkdir -p "$WT_ROOT"

# stub `gc` (bd list/create) and $FACTORY_ROOT/bin/escalation-door so the
# unpushed-worktree case below never touches a real Beads store or pages a
# real Mayor -- it only proves factory-maintain called the escalation door.
FAKE_BIN="$TMP/fakebin"
mkdir -p "$FAKE_BIN"
export BD_CREATE_LOG="$TMP/bd-create.log"
: > "$BD_CREATE_LOG"
cat > "$FAKE_BIN/gc" <<'FAKEGC'
#!/usr/bin/env bash
case "$1 $2" in
  "bd list")
    echo '[]'
    ;;
  "bd create")
    printf '%s\n' "$*" >> "$BD_CREATE_LOG"
    echo '[{"id":"fake-bead-1"}]'
    ;;
  *)
    echo "fake-gc: unexpected invocation: $*" >&2
    exit 1
    ;;
esac
FAKEGC
chmod +x "$FAKE_BIN/gc"
export PATH="$FAKE_BIN:$PATH"
export GC_BIN="$FAKE_BIN/gc"

mkdir -p "$FACTORY_ROOT/bin"
ESCALATION_LOG="$TMP/escalation.log"
: > "$ESCALATION_LOG"
cat > "$FACTORY_ROOT/bin/escalation-door" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$ESCALATION_LOG"
exit 0
EOF
chmod +x "$FACTORY_ROOT/bin/escalation-door"

# a merged, fully-pushed worktree -- eligible for removal regardless of age
git -C "$REPO2" worktree add -q -b clean-merged-pushed "$WT_ROOT/clean-merged-pushed" main
git -C "$REPO2" -C "$WT_ROOT/clean-merged-pushed" push -q origin clean-merged-pushed 2>/dev/null \
  || git -C "$WT_ROOT/clean-merged-pushed" push -q origin clean-merged-pushed
CLEAN_SHA=$(git -C "$WT_ROOT/clean-merged-pushed" rev-parse HEAD)

# a worktree with uncommitted changes -- must be refused
git -C "$REPO2" worktree add -q -b dirty-worktree "$WT_ROOT/dirty-worktree" main
echo dirty > "$WT_ROOT/dirty-worktree/uncommitted.txt"

# a worktree with unpushed commits -- must never be removed, and must be
# reported through the escalation door instead of silently skipped
git -C "$REPO2" worktree add -q -b unpushed-worktree "$WT_ROOT/unpushed-worktree" main
echo more > "$WT_ROOT/unpushed-worktree/h"
git -C "$WT_ROOT/unpushed-worktree" add -A
git -C "$WT_ROOT/unpushed-worktree" commit -qm "not pushed"

# a not-merged, clean, fully-pushed worktree, untouched for 10 days -- old
# enough to be eligible for removal even though its branch never merged
git -C "$REPO2" worktree add -q -b clean-pushed-old "$WT_ROOT/clean-pushed-old" main
echo old > "$WT_ROOT/clean-pushed-old/old.txt"
git -C "$WT_ROOT/clean-pushed-old" add -A
TEN_DAYS_AGO=$(date -u -d "10 days ago" +%Y-%m-%dT%H:%M:%S)
GIT_AUTHOR_DATE="$TEN_DAYS_AGO" GIT_COMMITTER_DATE="$TEN_DAYS_AGO" \
  git -C "$WT_ROOT/clean-pushed-old" commit -qm old
git -C "$WT_ROOT/clean-pushed-old" push -q origin clean-pushed-old
OLD_SHA=$(git -C "$WT_ROOT/clean-pushed-old" rev-parse HEAD)

# a not-merged, clean, fully-pushed worktree, touched just now -- too recent
# to remove even though it will never merge on its own
git -C "$REPO2" worktree add -q -b clean-pushed-recent "$WT_ROOT/clean-pushed-recent" main
echo recent > "$WT_ROOT/clean-pushed-recent/recent.txt"
git -C "$WT_ROOT/clean-pushed-recent" add -A
git -C "$WT_ROOT/clean-pushed-recent" commit -qm recent
git -C "$WT_ROOT/clean-pushed-recent" push -q origin clean-pushed-recent

OUT2=$("$SCRIPT" clean-worktrees --worktree-root "$WT_ROOT" 2>&1) || fail "clean-worktrees exited non-zero: $OUT2"

[ -d "$WT_ROOT/clean-merged-pushed" ] && fail "clean-worktrees did not remove a merged, fully-pushed, clean worktree"
[ -d "$WT_ROOT/dirty-worktree" ] || fail "clean-worktrees removed a worktree with uncommitted changes"
[ -d "$WT_ROOT/unpushed-worktree" ] || fail "clean-worktrees removed a worktree with unpushed commits"
[ -d "$WT_ROOT/clean-pushed-old" ] && fail "clean-worktrees did not remove a clean, pushed worktree untouched for over 7 days"
[ -d "$WT_ROOT/clean-pushed-recent" ] || fail "clean-worktrees removed a clean, pushed worktree that was recently touched"

grep -q "gesture=clean-worktrees.*status=removed.*path=$WT_ROOT/clean-merged-pushed" "$FACTORY_MAINTAIN_LOG" \
  || fail "clean-worktrees did not log the removal of the merged worktree"
grep -q "sha=$CLEAN_SHA" "$FACTORY_MAINTAIN_LOG" || fail "clean-worktrees log entry is missing the sha (needed for undo)"
grep -q "gesture=clean-worktrees.*undo=.*factory-do-work-workspace enter" "$FACTORY_MAINTAIN_LOG" \
  || fail "clean-worktrees log entry did not record how to undo it"
grep -q "gesture=clean-worktrees.*status=removed.*path=$WT_ROOT/clean-pushed-old.*sha=$OLD_SHA" "$FACTORY_MAINTAIN_LOG" \
  || fail "clean-worktrees did not log the removal of the stale, clean, pushed worktree"

# the branch clean-worktrees removed the worktree for is still recoverable (undo path)
git -C "$REPO2" show-ref --verify --quiet refs/heads/clean-merged-pushed \
  || fail "clean-worktrees deleted the underlying branch, not just the worktree (undo would be impossible)"

# the unpushed worktree was reported through the escalation door, not silently skipped
grep -q "unpushed-worktree" "$BD_CREATE_LOG" \
  || fail "clean-worktrees did not file a bead for the unpushed worktree"
grep -q "unpushed-worktree" "$ESCALATION_LOG" \
  || fail "clean-worktrees did not page the escalation door for the unpushed worktree"
grep -q "gesture=clean-worktrees.*status=escalated.*path=$WT_ROOT/unpushed-worktree" "$FACTORY_MAINTAIN_LOG" \
  || fail "clean-worktrees did not log the escalation for the unpushed worktree"

echo "PASS: clean-worktrees"

# ===========================================================================
# rotate-logs
# ===========================================================================
LOG_DIR="$TMP/logs"
mkdir -p "$LOG_DIR"

# a small log -- below threshold, must be left alone
printf 'small\n' > "$LOG_DIR/small.log"

# a large log -- over threshold, must be archived and truncated, not deleted
python3 -c "open('$LOG_DIR/big.log','w').write('x'*2000)"
ORIGINAL_CONTENT=$(cat "$LOG_DIR/big.log")

OUT3=$("$SCRIPT" rotate-logs --dir "$LOG_DIR" --max-bytes 1000 --keep 2 2>&1) || fail "rotate-logs exited non-zero: $OUT3"

[ -s "$LOG_DIR/small.log" ] || fail "rotate-logs touched a log below the size threshold"
[ ! -s "$LOG_DIR/big.log" ] || fail "rotate-logs did not truncate the rotated log"
ARCHIVE=$(ls "$LOG_DIR"/big.log.rotated.*.gz 2>/dev/null | head -n1)
[ -n "$ARCHIVE" ] || fail "rotate-logs did not create an archive for the rotated log"

RESTORED=$(gunzip -c "$ARCHIVE")
[ "$RESTORED" = "$ORIGINAL_CONTENT" ] || fail "rotate-logs archive does not contain the original content (undo would lose data)"

grep -q "gesture=rotate-logs.*status=rotated.*file=$LOG_DIR/big.log" "$FACTORY_MAINTAIN_LOG" \
  || fail "rotate-logs did not log the rotation"

# --keep prunes older archives instead of growing without bound
python3 -c "open('$LOG_DIR/big.log','w').write('y'*2000)"
sleep 1
"$SCRIPT" rotate-logs --dir "$LOG_DIR" --max-bytes 1000 --keep 2 >/dev/null
python3 -c "open('$LOG_DIR/big.log','w').write('z'*2000)"
sleep 1
"$SCRIPT" rotate-logs --dir "$LOG_DIR" --max-bytes 1000 --keep 2 >/dev/null
ARCHIVE_COUNT=$(ls "$LOG_DIR"/big.log.rotated.*.gz 2>/dev/null | wc -l | tr -d ' ')
[ "$ARCHIVE_COUNT" -le 2 ] || fail "rotate-logs did not prune archives beyond --keep (found $ARCHIVE_COUNT)"

echo "PASS: rotate-logs"

# ===========================================================================
# restart-service and reload-city-config: refuse an unknown service, wrap gc
# ===========================================================================
FAKE_BIN="$TMP/fakebin"
mkdir -p "$FAKE_BIN"
cat > "$FAKE_BIN/gc" <<'FAKEGC'
#!/usr/bin/env bash
case "$*" in
  "service list --json")
    echo '{"services":[{"name":"dispatcher"},{"name":"preview"}]}'
    ;;
  "service restart dispatcher")
    echo "restarted dispatcher"
    ;;
  "reload --json")
    echo '{"ok":true}'
    ;;
  *)
    echo "fake-gc: unexpected invocation: $*" >&2
    exit 1
    ;;
esac
FAKEGC
chmod +x "$FAKE_BIN/gc"
export PATH="$FAKE_BIN:$PATH"

"$SCRIPT" restart-service unknown-service >"$TMP/restart.out" 2>&1 \
  && fail "restart-service did not refuse an unknown service name"
grep -q "gesture=restart-service.*status=refused.*name=unknown-service" "$FACTORY_MAINTAIN_LOG" \
  || fail "restart-service did not log the refusal"

"$SCRIPT" restart-service dispatcher >"$TMP/restart2.out" 2>&1 \
  || fail "restart-service refused a known service: $(cat "$TMP/restart2.out")"
grep -q "gesture=restart-service.*status=restarted.*name=dispatcher" "$FACTORY_MAINTAIN_LOG" \
  || fail "restart-service did not log a successful restart"

"$SCRIPT" reload-city-config >"$TMP/reload.out" 2>&1 \
  || fail "reload-city-config failed: $(cat "$TMP/reload.out")"
grep -q "gesture=reload-city-config.*status=reloaded" "$FACTORY_MAINTAIN_LOG" \
  || fail "reload-city-config did not log success"

echo "PASS: restart-service, reload-city-config"

echo "ALL PASS: factory-maintain"
