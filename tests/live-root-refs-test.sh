#!/usr/bin/env bash
# tests/lib/live-root-refs.sh (af-pw867q, T53): a run that watches the
# repository of the live Factory names every branch or tag it created, moved
# or deleted there, from any work tree, and names nothing when another
# session moved a reference during the run.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
fail() {
  echo "FAIL: $*" >&2
  exit 1
}
WORK=$(mktemp -d "${TMPDIR:-/tmp}/live-root-refs.XXXXXX")
WORK=$(cd "$WORK" && pwd -P)
trap 'rm -rf -- "$WORK"' EXIT

# Nothing of the caller's Git reaches the repositories of this test.
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^GIT_' || true)
export HOME="$WORK/home" GIT_CONFIG_NOSYSTEM=1
mkdir -p "$HOME"
git config --global user.name "live-root-refs test"
git config --global user.email "test@example.invalid"
git config --global init.defaultBranch main

# What stands for the live Factory: a repository with a branch, a tag and a
# second work tree, and its own hooks directory as the Factory configures one.
LIVE="$WORK/live"
git init -q "$LIVE"
git -C "$LIVE" commit -q --allow-empty -m "premier"
git -C "$LIVE" commit -q --allow-empty -m "second"
FIRST=$(git -C "$LIVE" rev-parse HEAD~1)
git -C "$LIVE" branch kept "$FIRST"
git -C "$LIVE" tag v1 "$FIRST"
git -C "$LIVE" branch foreign "$FIRST"
git -C "$LIVE" config core.hooksPath .githooks
git -C "$LIVE" worktree add -q "$WORK/tree" -b tree-branch
OTHER="$WORK/other"
git init -q "$OTHER"
git -C "$OTHER" commit -q --allow-empty -m "ailleurs"

# Another session: the same commands, without the environment of the run.
elsewhere() { env -u GIT_CONFIG_COUNT -u GIT_CONFIG_KEY_0 -u GIT_CONFIG_VALUE_0 "$@"; }

# shellcheck source=tests/lib/live-root-refs.sh
. "$ROOT/tests/lib/live-root-refs.sh"
live_root_refs_watch "$WORK/watch" || fail "the watch did not see the reference its own probe wrote"

written() { live_root_refs_written "$LIVE"; }
[ -z "$(written)" ] || fail "a run that wrote nothing names a reference: $(written)"

# --- what leaves the repository as it was names nothing ------------------------
git -C "$LIVE" status --porcelain >/dev/null
git -C "$LIVE" log --oneline -1 >/dev/null
git -C "$OTHER" branch elsewhere
git -C "$OTHER" tag t-elsewhere
[ -z "$(written)" ] || fail "reading the repository, or writing another one, names a reference: $(written)"

# --- another session moves references during the run: nothing is named ---------
elsewhere git -C "$LIVE" branch do-work/af-other "$FIRST"
elsewhere git -C "$LIVE" branch -f foreign HEAD
elsewhere git -C "$LIVE" tag v-other
elsewhere git -C "$LIVE" branch -D do-work/af-other >/dev/null
elsewhere git -C "$WORK/tree" commit -q --allow-empty -m "travail d'une autre session"
[ -z "$(written)" ] || fail "a reference moved by another session is charged to the run: $(written)"

# --- each write of the run is named, one case at a time ------------------------
expect() {  # WHAT LINE-PATTERN: the last write is the only new line, and matches
  local now
  now=$(written)
  [ "$(printf '%s\n' "$now" | grep -c .)" = "$((SEEN + 1))" ] || fail "$1: expected one more reference named, got: $now"
  printf '%s\n' "$now" | tail -1 | grep -Eq "$2" || fail "$1 is not named as « $2 »: $(printf '%s\n' "$now" | tail -1)"
  SEEN=$((SEEN + 1))
}
SEEN=0
git -C "$LIVE" branch leaked "$FIRST";            expect "a branch created" "^set refs/heads/leaked to $FIRST$"
git -C "$LIVE" branch -f kept HEAD;                expect "a branch moved" "^set refs/heads/kept to $(git -C "$LIVE" rev-parse HEAD)$"
git -C "$LIVE" branch -D leaked >/dev/null;        expect "a branch deleted" "^deleted refs/heads/leaked$"
git -C "$LIVE" tag v2;                             expect "a tag created" "^set refs/tags/v2 to "
git -C "$LIVE" tag -f v1 HEAD >/dev/null;          expect "a tag moved" "^set refs/tags/v1 to $(git -C "$LIVE" rev-parse HEAD)$"
git -C "$LIVE" tag -d v2 >/dev/null;               expect "a tag deleted" "^deleted refs/tags/v2$"
git -C "$WORK/tree" branch from-the-tree;          expect "a branch created from another work tree" "^set refs/heads/from-the-tree to "
git -C "$WORK/tree" commit -q --allow-empty -m "x"; expect "a commit on the branch of another work tree" "^set refs/heads/tree-branch to "
( cd "$LIVE" && python3 -c 'import subprocess; subprocess.run(["git", "update-ref", "refs/heads/by-a-tool", "HEAD"], check=True)' )
expect "a reference written by a tool the run started" "^set refs/heads/by-a-tool to "

# --- nothing was written in the watched repository to watch it -----------------
[ "$(git -C "$LIVE" config --local --get core.hooksPath)" = .githooks ] || fail "the watch changed the configuration of the repository"
[ ! -e "$LIVE/.githooks" ] && [ -z "$(find "$LIVE/.git/hooks" -type f ! -name '*.sample')" ] \
  || fail "the watch left a hook in the repository"
[ -z "$(git -C "$LIVE" status --porcelain --untracked-files=all)" ] || fail "the watch left a file in the repository"

# --- a watch that cannot see refuses to start ----------------------------------
set +e
( PATH="$WORK/nogit:$PATH"; mkdir -p "$WORK/nogit"
  printf '#!/bin/sh\nexec env -u GIT_CONFIG_COUNT %s "$@"\n' "$(command -v git)" > "$WORK/nogit/git"; chmod +x "$WORK/nogit/git"
  live_root_refs_watch "$WORK/blind" ); rc=$?
set -e
[ "$rc" != 0 ] || fail "a watch whose hook never runs started as if it saw"

echo "PASS: a watched run names every branch or tag it created, moved or deleted in the repository, from any work tree, and nothing another session moved"
