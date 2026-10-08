#!/usr/bin/env bash
#
# Workers dispatched via mol-do-work on the HQ (agent-factory) rig must work
# in a git worktree, never the live root -- af-ogg8z, same incident as
# tests/factory-live-root-guard-test.sh: on 2026-09-17 a worker running this
# formula committed af-lb3q straight into the live root (no branch, no PR).
#
# bin/factory-do-work-workspace is what mol-do-work's workspace-setup and
# push-and-pr steps call to fix that. This test drives the script directly
# (not the formula prose, which an LLM interprets, not a test harness) and
# proves: `enter` creates an isolated worktree on its own branch when cwd IS
# the live root, `finish` pushes that branch and removes the worktree, and
# both are a documented no-op anywhere else (a rig checkout, or a worktree
# that already exists).

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SCRIPT="$REPO_ROOT/bin/factory-do-work-workspace"
TMP=$(mktemp -d)
trap 'git -C "$TMP/root" worktree remove --force "$WT" 2>/dev/null || true; rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

[ -x "$SCRIPT" ] || fail "$SCRIPT is not executable"

# --- a throwaway "live root" with an origin ----------------------------------
git init -q --bare "$TMP/origin.git"
git init -q "$TMP/root"
cd "$TMP/root"
git config user.email t@t; git config user.name t; git config commit.gpgsign false
git remote add origin "$TMP/origin.git"
echo one > f && git add -A && git commit -qm one
git branch -M main
git push -q origin main

export FACTORY_ROOT="$TMP/root"
export HOME="$TMP/home"
mkdir -p "$HOME"

# a lib/protected_rigs.sh at FACTORY_ROOT, mirroring production's table (the
# live root's own branch, plus a stand-in product rig used by test 6 below)
mkdir -p "$FACTORY_ROOT/lib" "$FACTORY_ROOT/rigs/protected-rig-test"
cat > "$FACTORY_ROOT/lib/protected_rigs.sh" <<'EOF'
PROTECTED_RIGS=(
  "rigs/protected-rig-test|test/protected-rig|dev|Test CI"
  ".|test/live-root|main|Test CI"
)
EOF

# ---------------------------------------------------------------------------
# 1. `enter` in the live root creates an isolated worktree on its own branch
# ---------------------------------------------------------------------------
WT=$("$SCRIPT" enter af-workspace-test)
[ -n "$WT" ] && [ "$WT" != "." ] || fail "enter did not return a worktree path in the live root"
[ -d "$WT" ] || fail "enter reported worktree path $WT but it does not exist"
[ "$WT" != "$TMP/root" ] || fail "enter returned the live root itself"
branch=$(git -C "$WT" rev-parse --abbrev-ref HEAD)
[ "$branch" = "do-work/af-workspace-test" ] \
  || fail "worktree is on branch '$branch', expected 'do-work/af-workspace-test'"

# the live root itself must be untouched
[ "$(git -C "$TMP/root" rev-parse --abbrev-ref HEAD)" = "main" ] \
  || fail "enter moved the live root off its own branch"

# ---------------------------------------------------------------------------
# 2. `enter` again (resume) reuses the same worktree, does not recreate it
# ---------------------------------------------------------------------------
WT2=$("$SCRIPT" enter af-workspace-test)
[ "$WT2" = "$WT" ] || fail "a second 'enter' for the same bead did not reuse the existing worktree"

# ---------------------------------------------------------------------------
# 3. `finish` pushes the branch and removes the worktree
# ---------------------------------------------------------------------------
echo work > "$WT/g"
git -C "$WT" add g
git -C "$WT" commit -qm "work"
"$SCRIPT" finish af-workspace-test "$WT" do-work/af-workspace-test main >finish.out 2>finish.err \
  || { cat finish.err >&2; fail "finish exited non-zero"; }

[ -d "$WT" ] && fail "finish did not remove the worktree"
git -C "$TMP/root" fetch -q origin
git -C "$TMP/root" show-ref --verify --quiet refs/remotes/origin/do-work/af-workspace-test \
  || fail "finish did not push the branch to origin"

# ---------------------------------------------------------------------------
# 4. `finish` is a no-op given enter's own "." marker (not an HQ dispatch)
# ---------------------------------------------------------------------------
"$SCRIPT" finish af-noop . do-work/af-noop main \
  || fail "'finish . ...' (enter's no-op marker) must exit 0, not fail"

# ---------------------------------------------------------------------------
# 5. `enter` is a documented no-op anywhere that is NOT the live root and NOT
#    a rig listed in lib/protected_rigs.sh
# ---------------------------------------------------------------------------
mkdir -p "$TMP/some-rig"
(
  cd "$TMP/some-rig"
  git init -q
  out=$("$SCRIPT" enter af-other-rig)
  [ "$out" = "." ] || { echo "expected '.', got '$out'" >&2; exit 1; }
) || fail "enter created a worktree outside the live root -- it must be a no-op there"

# ---------------------------------------------------------------------------
# 6. af-09hxz: `enter` isolates a product-rig checkout on its protected
#    branch too, not only the live HQ root -- this is the regression that
#    let mol-do-work commit straight to saymyname-backend's `dev` (smb-u3zzt).
# ---------------------------------------------------------------------------
git init -q --bare "$TMP/rig-origin.git"
git init -q "$FACTORY_ROOT/rigs/protected-rig-test"
(
  cd "$FACTORY_ROOT/rigs/protected-rig-test"
  git config user.email t@t; git config user.name t; git config commit.gpgsign false
  git remote add origin "$TMP/rig-origin.git"
  echo one > f && git add -A && git commit -qm one
  git branch -M dev
  git push -q origin dev
)

RIG_WT=$(cd "$FACTORY_ROOT/rigs/protected-rig-test" && "$SCRIPT" enter af-rig-workspace-test)
[ -n "$RIG_WT" ] && [ "$RIG_WT" != "." ] || fail "enter did not isolate a product rig on its protected 'dev' branch"
[ -d "$RIG_WT" ] || fail "enter reported rig worktree path $RIG_WT but it does not exist"
rig_branch=$(git -C "$RIG_WT" rev-parse --abbrev-ref HEAD)
[ "$rig_branch" = "do-work/af-rig-workspace-test" ] \
  || fail "rig worktree is on branch '$rig_branch', expected 'do-work/af-rig-workspace-test'"
[ "$(git -C "$FACTORY_ROOT/rigs/protected-rig-test" rev-parse --abbrev-ref HEAD)" = "dev" ] \
  || fail "enter moved the rig checkout off its own 'dev' branch"

echo work > "$RIG_WT/g"
git -C "$RIG_WT" add g
git -C "$RIG_WT" commit -qm "work"
"$SCRIPT" finish af-rig-workspace-test "$RIG_WT" do-work/af-rig-workspace-test dev \
  || fail "finish exited non-zero for a product-rig worktree"
[ -d "$RIG_WT" ] && fail "finish did not remove the product-rig worktree"
git -C "$FACTORY_ROOT/rigs/protected-rig-test" fetch -q origin
git -C "$FACTORY_ROOT/rigs/protected-rig-test" show-ref --verify --quiet refs/remotes/origin/do-work/af-rig-workspace-test \
  || fail "finish did not push the product-rig branch to its own origin"

# a feature branch on the same rig must NOT be isolated (only the protected
# branch itself is)
(
  cd "$FACTORY_ROOT/rigs/protected-rig-test"
  git checkout -q -b feature/not-protected
  out=$("$SCRIPT" enter af-feature-branch-test)
  [ "$out" = "." ] || { echo "expected '.', got '$out'" >&2; exit 1; }
) || fail "enter isolated a non-protected feature branch on a tracked rig"

# ---------------------------------------------------------------------------
# 7. O04: a session that dies mid-run without ever calling `finish` still
#    leaves its commits on the remote branch (the post-commit push hook
#    `enter` installs, not a final push at the end).
# ---------------------------------------------------------------------------
WT7=$("$SCRIPT" enter af-interrupted-test)
echo interrupted > "$WT7/h"
git -C "$WT7" add h
git -C "$WT7" commit -qm "interrupted work"
git -C "$TMP/root" fetch -q origin
git -C "$TMP/root" show-ref --verify --quiet refs/remotes/origin/do-work/af-interrupted-test \
  || fail "enter's post-commit hook did not push do-work/af-interrupted-test after a commit"
remote_head=$(git -C "$TMP/root" rev-parse origin/do-work/af-interrupted-test)
local_head=$(git -C "$WT7" rev-parse HEAD)
[ "$remote_head" = "$local_head" ] \
  || fail "remote branch is not at the same commit as the worktree after an unfinished commit"
git -C "$TMP/root" worktree remove --force "$WT7" 2>/dev/null || true

# ---------------------------------------------------------------------------
# 8. O04: `finish` resumes an already-open PR instead of trying (and
#    silently failing) to create a duplicate one on re-dispatch.
# ---------------------------------------------------------------------------
FAKE_GH_DIR="$TMP/fake-gh-bin"
mkdir -p "$FAKE_GH_DIR"
GH_PR_STATE="$TMP/gh-pr-state"
cat > "$FAKE_GH_DIR/gh" <<EOF
#!/usr/bin/env bash
STATE="$GH_PR_STATE"
if [ "\$1 \$2" = "pr create" ]; then
  if [ -f "\$STATE" ]; then
    echo "a pull request for branch already exists" >&2
    exit 1
  fi
  echo "https://github.com/example/example/pull/99" | tee "\$STATE"
  exit 0
fi
if [ "\$1 \$2" = "pr view" ]; then
  [ -f "\$STATE" ] || exit 1
  cat "\$STATE"
  exit 0
fi
exit 1
EOF
chmod +x "$FAKE_GH_DIR/gh"
export PATH="$FAKE_GH_DIR:$PATH"

WT8=$("$SCRIPT" enter af-pr-resume-test)
echo first > "$WT8/i"
git -C "$WT8" add i
git -C "$WT8" commit -qm "first"
PR_URL_1=$("$SCRIPT" finish af-pr-resume-test "$WT8" do-work/af-pr-resume-test main)
[ "$PR_URL_1" = "https://github.com/example/example/pull/99" ] \
  || fail "finish did not report the PR opened by the (fake) gh pr create: got '$PR_URL_1'"

# simulate a re-dispatch: resume the same bead, add more work, finish again
WT8b=$("$SCRIPT" enter af-pr-resume-test)
[ "$WT8b" != "." ] || fail "enter did not resume the existing do-work/af-pr-resume-test branch on re-dispatch"
branch8b=$(git -C "$WT8b" rev-parse --abbrev-ref HEAD)
[ "$branch8b" = "do-work/af-pr-resume-test" ] \
  || fail "re-dispatch worktree is on branch '$branch8b', expected the resumed do-work branch"
echo second > "$WT8b/j"
git -C "$WT8b" add j
git -C "$WT8b" commit -qm "second"
PR_URL_2=$("$SCRIPT" finish af-pr-resume-test "$WT8b" do-work/af-pr-resume-test main)
[ "$PR_URL_2" = "$PR_URL_1" ] \
  || fail "re-dispatch finish did not resume the existing open PR (got '$PR_URL_2', expected '$PR_URL_1')"

# ---------------------------------------------------------------------------
# 9. O04: starting over (discarding an existing do-work branch/worktree)
#    without a written reason is refused; with one, it proceeds.
# ---------------------------------------------------------------------------
WT9=$("$SCRIPT" enter af-restart-test)
echo before > "$WT9/k"
git -C "$WT9" add k
git -C "$WT9" commit -qm "before restart"

"$SCRIPT" restart af-restart-test "$WT9" do-work/af-restart-test 2>/dev/null \
  && fail "restart without a reason must be refused, not succeed"
[ -d "$WT9" ] || fail "restart without a reason must not remove the worktree"

"$SCRIPT" restart af-restart-test "$WT9" do-work/af-restart-test "operator asked to abandon this approach" \
  || fail "restart with a written reason should succeed"
[ -d "$WT9" ] && fail "restart with a reason did not remove the worktree"
grep -q . <<<"$(git -C "$TMP/root" branch --list do-work/af-restart-test)" \
  && fail "restart with a reason did not delete the local do-work/af-restart-test branch"

WT9b=$("$SCRIPT" enter af-restart-test)
[ -f "$WT9b/k" ] && fail "enter after a restart resumed the discarded branch instead of starting clean"

# ---------------------------------------------------------------------------
# 10. af-jz4zb (P08): two concurrent `enter` calls for different bead ids on
#     the same repository both succeed, each producing its own worktree
#     based on `origin/main` with the auto-push hook installed -- the
#     per-repository lock must serialize them, not deadlock or corrupt
#     either one.
# ---------------------------------------------------------------------------
echo two > "$TMP/root/f2" && git -C "$TMP/root" add f2 && git -C "$TMP/root" commit -qm two
git -C "$TMP/root" push -q origin main

"$SCRIPT" enter af-concurrent-a >"$TMP/wt-a.out" 2>"$TMP/wt-a.err" &
PID_A=$!
"$SCRIPT" enter af-concurrent-b >"$TMP/wt-b.out" 2>"$TMP/wt-b.err" &
PID_B=$!
wait "$PID_A" || { cat "$TMP/wt-a.err" >&2; fail "concurrent enter af-concurrent-a failed"; }
wait "$PID_B" || { cat "$TMP/wt-b.err" >&2; fail "concurrent enter af-concurrent-b failed"; }
WT_A=$(cat "$TMP/wt-a.out")
WT_B=$(cat "$TMP/wt-b.out")
[ -d "$WT_A" ] || fail "concurrent enter did not produce a worktree for af-concurrent-a"
[ -d "$WT_B" ] || fail "concurrent enter did not produce a worktree for af-concurrent-b"
[ "$WT_A" != "$WT_B" ] || fail "concurrent enter for two different bead ids returned the same worktree"
[ "$(git -C "$WT_A" rev-parse HEAD)" = "$(git -C "$TMP/root" rev-parse origin/main)" ] \
  || fail "af-concurrent-a's worktree is not based on the freshly fetched origin/main"
[ "$(git -C "$WT_B" rev-parse HEAD)" = "$(git -C "$TMP/root" rev-parse origin/main)" ] \
  || fail "af-concurrent-b's worktree is not based on the freshly fetched origin/main"
git -C "$WT_A" config --worktree --get core.hooksPath >/dev/null \
  || fail "af-concurrent-a's worktree has no auto-push hook installed"
git -C "$WT_B" config --worktree --get core.hooksPath >/dev/null \
  || fail "af-concurrent-b's worktree has no auto-push hook installed"
git -C "$TMP/root" worktree remove --force "$WT_A" 2>/dev/null || true
git -C "$TMP/root" worktree remove --force "$WT_B" 2>/dev/null || true

# ---------------------------------------------------------------------------
# 11. af-jz4zb (P08): a forced hook-install failure makes `enter` exit
#     non-zero with a readable reason, and does not hand back a worktree
#     with no safety net.
# ---------------------------------------------------------------------------
REAL_GIT=$(command -v git)
FAKE_GIT_DIR="$TMP/fake-git-bin"
mkdir -p "$FAKE_GIT_DIR"
cat > "$FAKE_GIT_DIR/git" <<EOF
#!/usr/bin/env bash
case " \$* " in
  *" config --worktree core.hooksPath "*)
    echo "fake git: simulated hooksPath config failure" >&2
    exit 1
    ;;
esac
exec "$REAL_GIT" "\$@"
EOF
chmod +x "$FAKE_GIT_DIR/git"

set +e
PATH="$FAKE_GIT_DIR:$PATH" "$SCRIPT" enter af-hook-failure-test >"$TMP/hook-fail.out" 2>"$TMP/hook-fail.err"
HOOK_FAIL_RC=$?
set -e
[ "$HOOK_FAIL_RC" -ne 0 ] || fail "enter must exit non-zero when the auto-push hook cannot be installed"
grep -q "." "$TMP/hook-fail.err" || fail "enter gave no readable reason for the forced hook-install failure"
[ -d "$HOME/.local/share/agent-factory-runtime-worktrees/af-hook-failure-test" ] \
  && fail "enter left behind a worktree with no working auto-push hook after a forced install failure"

# ---------------------------------------------------------------------------
# 13. D01 (af-wtjo2x, T01's PR #384 merged with the body "Closes af-m8m1kc."
#     and nothing else): a ticket whose description demands the PR sections
#     « Non fait », « Écarts », « Constats hors ticket » cannot get them into
#     the PR while `finish` writes a fixed body. `finish` now takes the body
#     from <worktree git dir>/PR_BODY.md, and refuses (exit 3, nothing
#     pushed away, worktree kept, no PR) when such a ticket has no body
#     carrying the three sections. A ticket that does not demand them keeps
#     the old behaviour.
# ---------------------------------------------------------------------------
FAKE_BD_DIR="$TMP/fake-bd-bin"
mkdir -p "$FAKE_BD_DIR"
cat > "$FAKE_BD_DIR/bd" <<'EOF'
#!/usr/bin/env bash
if [ "$1" = "show" ]; then
  case "$2" in
    af-sections-*)
      printf '[{"id":"%s","description":"no_silent_deferral: écrit dans la PR sous « Non fait », « Écarts », « Constats hors ticket »"}]\n' "$2"
      ;;
    *)
      printf '[{"id":"%s","description":"a plain ticket"}]\n' "$2"
      ;;
  esac
  exit 0
fi
exit 1
EOF
chmod +x "$FAKE_BD_DIR/bd"

export GH_FAKE_DIR="$TMP/fake-gh-state"
FAKE_GH2_DIR="$TMP/fake-gh2-bin"
mkdir -p "$GH_FAKE_DIR" "$FAKE_GH2_DIR"
cat > "$FAKE_GH2_DIR/gh" <<'EOF'
#!/usr/bin/env bash
D="$GH_FAKE_DIR"
sub="$1 $2"; shift 2
branch=""; body=""; want=""
case "$sub" in "pr view"|"pr edit") branch="$1"; shift ;; esac
while [ $# -gt 0 ]; do
  case "$1" in
    --head) branch="$2"; shift 2 ;;
    --body-file) body="$2"; shift 2 ;;
    --json) want="$2"; shift 2 ;;
    *) shift ;;
  esac
done
key=$(printf '%s' "$branch" | tr '/' '_')
case "$sub" in
  "pr create")
    if [ -f "$D/$key.url" ]; then echo "a pull request for branch already exists" >&2; exit 1; fi
    [ -n "$body" ] && [ -f "$body" ] || { echo "fake gh: pr create without --body-file" >&2; exit 1; }
    cp "$body" "$D/$key.body"
    echo "https://github.com/example/example/pull/$key" | tee "$D/$key.url"
    exit 0 ;;
  "pr view")
    [ -f "$D/$key.url" ] || exit 1
    if [ "$want" = "body" ]; then cat "$D/$key.body"; else cat "$D/$key.url"; fi
    exit 0 ;;
  "pr edit")
    [ -f "$D/$key.url" ] || exit 1
    cp "$body" "$D/$key.body"; echo edited >> "$D/$key.edits"
    exit 0 ;;
esac
exit 1
EOF
chmod +x "$FAKE_GH2_DIR/gh"
export PATH="$FAKE_BD_DIR:$FAKE_GH2_DIR:$PATH"

pr_body_path() { printf '%s/PR_BODY.md' "$(git -C "$1" rev-parse --absolute-git-dir)"; }

# 13a. sections demanded, no body file: refused, nothing opened, worktree kept
WT13=$("$SCRIPT" enter af-sections-a)
echo work > "$WT13/s"
git -C "$WT13" add s
git -C "$WT13" commit -qm "sections work"
rc=0
"$SCRIPT" finish af-sections-a "$WT13" do-work/af-sections-a main >"$TMP/s13a.out" 2>"$TMP/s13a.err" || rc=$?
[ "$rc" = "3" ] || fail "finish on a ticket that demands the PR sections, with no PR_BODY.md, exited $rc (expected 3)"
[ -d "$WT13" ] || fail "a refused finish must leave the worktree in place"
[ -f "$GH_FAKE_DIR/do-work_af-sections-a.url" ] && fail "a refused finish must not open a PR"
for s in "Non fait" "Écarts" "Constats hors ticket"; do
  grep -qF -- "$s" "$TMP/s13a.err" || fail "the refusal does not name the missing section '$s'"
done
grep -qF -- "$(pr_body_path "$WT13")" "$TMP/s13a.err" || fail "the refusal does not name the file to write"

# 13b. two sections out of three: still refused, names only the missing one
printf '## Non fait\naucun\n\n## Écarts\naucun\n' > "$(pr_body_path "$WT13")"
rc=0
"$SCRIPT" finish af-sections-a "$WT13" do-work/af-sections-a main >"$TMP/s13b.out" 2>"$TMP/s13b.err" || rc=$?
[ "$rc" = "3" ] || fail "finish with a PR_BODY.md missing one section exited $rc (expected 3)"
grep -qF -- "« Constats hors ticket »" <<<"$(grep -F -- "Missing:" "$TMP/s13b.err")" \
  || fail "the refusal does not list the one missing section"
grep -qF -- "« Non fait »" <<<"$(grep -F -- "Missing:" "$TMP/s13b.err")" \
  && fail "the refusal lists as missing a section that is present"

# 13c. the three sections: PR opened with them in its body, worktree removed
printf '## Non fait\naucun\n\n## Écarts\nle port est choisi par le système\n\n## Constats hors ticket\naucun\n' > "$(pr_body_path "$WT13")"
PR_URL_13=$("$SCRIPT" finish af-sections-a "$WT13" do-work/af-sections-a main 2>"$TMP/s13c.err") \
  || { cat "$TMP/s13c.err" >&2; fail "finish with the three sections exited non-zero"; }
[ -n "$PR_URL_13" ] || fail "finish with the three sections did not report a PR"
[ -d "$WT13" ] && fail "finish with the three sections did not remove the worktree"
B13="$GH_FAKE_DIR/do-work_af-sections-a.body"
grep -qF -- "Closes af-sections-a." "$B13" || fail "the PR body lost its 'Closes <bead>.' line"
grep -qF -- "le port est choisi par le système" "$B13" || fail "the PR body does not carry PR_BODY.md"

# 13d. re-dispatch, no new body file: the open PR already carries the
#      sections, so finish passes and leaves the PR body alone
WT13d=$("$SCRIPT" enter af-sections-a)
echo more > "$WT13d/s2"
git -C "$WT13d" add s2
git -C "$WT13d" commit -qm "more"
"$SCRIPT" finish af-sections-a "$WT13d" do-work/af-sections-a main >/dev/null 2>"$TMP/s13d.err" \
  || { cat "$TMP/s13d.err" >&2; fail "re-dispatch finish was refused although the open PR already carries the sections"; }
[ -f "$GH_FAKE_DIR/do-work_af-sections-a.edits" ] && fail "re-dispatch finish with no new PR_BODY.md rewrote the PR body"

# 13e. re-dispatch with a new body file: the open PR's body is replaced
WT13e=$("$SCRIPT" enter af-sections-a)
echo again > "$WT13e/s3"
git -C "$WT13e" add s3
git -C "$WT13e" commit -qm "again"
printf '## Non fait\nla sonde\n\n## Écarts\naucun\n\n## Constats hors ticket\naucun\n' > "$(pr_body_path "$WT13e")"
"$SCRIPT" finish af-sections-a "$WT13e" do-work/af-sections-a main >/dev/null 2>"$TMP/s13e.err" \
  || { cat "$TMP/s13e.err" >&2; fail "re-dispatch finish with a new PR_BODY.md exited non-zero"; }
grep -qF -- "la sonde" "$B13" || fail "re-dispatch finish did not update the open PR's body from the new PR_BODY.md"

# 13f. a ticket that does not demand the sections: no file needed, old body
WT13f=$("$SCRIPT" enter af-plain-ticket)
echo plain > "$WT13f/p"
git -C "$WT13f" add p
git -C "$WT13f" commit -qm "plain"
"$SCRIPT" finish af-plain-ticket "$WT13f" do-work/af-plain-ticket main >/dev/null 2>"$TMP/s13f.err" \
  || { cat "$TMP/s13f.err" >&2; fail "finish on a ticket that does not demand the sections was refused"; }
[ "$(cat "$GH_FAKE_DIR/do-work_af-plain-ticket.body")" = "Closes af-plain-ticket." ] \
  || fail "a plain ticket's PR body is no longer exactly 'Closes <bead>.'"

# ---------------------------------------------------------------------------
# 14. af-cjaj8o (2026-10-08, af-cbp84n): the post-commit hook pushes every
#     commit, so a re-dispatched ticket's PR can merge before `finish` runs.
#     `finish` then opened a second, empty PR (#445 after #444) and the step
#     rewrote the closed ticket's merge record. When there is nothing left
#     to deliver, `finish` opens no PR, prints no URL, removes the worktree
#     and exits 4.
# ---------------------------------------------------------------------------
export GH_FAKE_MERGED="$TMP/fake-gh-merged"
export GH_FAKE_NEXT="$FAKE_GH2_DIR/gh"
FAKE_GH3_DIR="$TMP/fake-gh3-bin"
mkdir -p "$GH_FAKE_MERGED" "$FAKE_GH3_DIR"
cat > "$FAKE_GH3_DIR/gh" <<'EOF'
#!/usr/bin/env bash
# answers "pr list --state merged" from $GH_FAKE_MERGED/<branch>.head (the
# merged PR's head SHA); everything else goes to the fake gh of test 13
if [ "$1 $2" = "pr list" ]; then
  branch=""; q=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --head) branch="$2"; shift 2 ;;
      -q|--jq) q="$2"; shift 2 ;;
      *) shift ;;
    esac
  done
  key=$(printf '%s' "$branch" | tr '/' '_')
  [ -f "$GH_FAKE_MERGED/$key.head" ] || exit 0
  case "$q" in
    *"$(cat "$GH_FAKE_MERGED/$key.head")"*) echo "https://github.com/example/example/pull/merged-$key" ;;
  esac
  exit 0
fi
exec "$GH_FAKE_NEXT" "$@"
EOF
chmod +x "$FAKE_GH3_DIR/gh"
export PATH="$FAKE_GH3_DIR:$PATH"

# 14a. the ticket's PR merged (squash) with this exact head during the
#      dispatch, and the base has moved on since: no second PR
WT14=$("$SCRIPT" enter af-merged-ticket)
echo delivered > "$WT14/m"
git -C "$WT14" add m
git -C "$WT14" commit -qm "delivered"
"$SCRIPT" finish af-merged-ticket "$WT14" do-work/af-merged-ticket main >/dev/null 2>"$TMP/s14.err" \
  || { cat "$TMP/s14.err" >&2; fail "first finish of af-merged-ticket exited non-zero"; }
WT14b=$("$SCRIPT" enter af-merged-ticket)
git -C "$WT14b" rev-parse HEAD > "$GH_FAKE_MERGED/do-work_af-merged-ticket.head"
rm -f "$GH_FAKE_DIR/do-work_af-merged-ticket.url"   # merged: `gh pr create` would succeed again
git -C "$TMP/root" pull -q origin main
echo delivered > "$TMP/root/m" && echo later > "$TMP/root/n"
git -C "$TMP/root" add m n && git -C "$TMP/root" commit -qm "squash of af-merged-ticket, then another ticket"
git -C "$TMP/root" push -q origin main
rc=0
"$SCRIPT" finish af-merged-ticket "$WT14b" do-work/af-merged-ticket main >"$TMP/s14a.out" 2>"$TMP/s14a.err" || rc=$?
[ "$rc" = "4" ] || { cat "$TMP/s14a.err" >&2; fail "finish on a ticket whose PR already merged with this head exited $rc (expected 4)"; }
[ -s "$TMP/s14a.out" ] && fail "finish on an already-merged ticket printed a PR URL: $(cat "$TMP/s14a.out")"
[ -f "$GH_FAKE_DIR/do-work_af-merged-ticket.url" ] && fail "finish opened a duplicate PR for an already-merged ticket"
[ -d "$WT14b" ] && fail "finish on an already-merged ticket did not remove the worktree"
grep -qF -- "pull/merged-do-work_af-merged-ticket" "$TMP/s14a.err" \
  || fail "finish on an already-merged ticket does not name the merged PR"

# 14b. new commits after the merge are real work: a PR is opened as before
WT14c=$("$SCRIPT" enter af-merged-ticket)
echo followup > "$WT14c/m2"
git -C "$WT14c" add m2
git -C "$WT14c" commit -qm "follow-up after the merge"
PR_URL_14=$("$SCRIPT" finish af-merged-ticket "$WT14c" do-work/af-merged-ticket main 2>"$TMP/s14b.err") \
  || { cat "$TMP/s14b.err" >&2; fail "finish with new commits after a merge exited non-zero"; }
[ -n "$PR_URL_14" ] || fail "finish with new commits after a merge did not open a PR"

# 14c. a branch with no difference with the base (its whole content landed
#      there, and gh knows no merged PR for it): no PR
WT14d=$("$SCRIPT" enter af-no-diff-ticket)
echo landed > "$WT14d/o"
git -C "$WT14d" add -A
git -C "$WT14d" commit -qm "landed"
git -C "$TMP/root" fetch -q origin
git -C "$TMP/root" merge -q --squash origin/do-work/af-no-diff-ticket >/dev/null
git -C "$TMP/root" commit -qm "squash of af-no-diff-ticket"
git -C "$TMP/root" push -q origin main
rc=0
"$SCRIPT" finish af-no-diff-ticket "$WT14d" do-work/af-no-diff-ticket main >"$TMP/s14c.out" 2>"$TMP/s14c.err" || rc=$?
[ "$rc" = "4" ] || { cat "$TMP/s14c.err" >&2; fail "finish on a branch with no difference with the base exited $rc (expected 4)"; }
[ -s "$TMP/s14c.out" ] && fail "finish on a branch with no difference with the base printed a PR URL"
[ -f "$GH_FAKE_DIR/do-work_af-no-diff-ticket.url" ] && fail "finish opened an empty PR for a branch with no difference with the base"
[ -d "$WT14d" ] && fail "finish on a branch with no difference with the base did not remove the worktree"

echo "OK bin/factory-do-work-workspace isolates HQ dispatches AND protected product-rig branches in a worktree, pushes and cleans up on finish, and is a no-op elsewhere"
