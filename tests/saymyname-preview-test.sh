#!/usr/bin/env bash

set -Eeuo pipefail

TEST_ROOT=$(mktemp -d)
trap 'rm -rf -- "$TEST_ROOT"' EXIT

export SAYMYNAME_PREVIEW_SOURCE_ONLY=1
# shellcheck source=../bin/saymyname-preview
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)/bin/saymyname-preview"

TESTS_RUN=0

fail_test() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

assert_passes() {
  local description=$1
  shift
  TESTS_RUN=$((TESTS_RUN + 1))
  if ! ("$@") >/dev/null 2>&1; then
    fail_test "$description"
  fi
}

assert_fails() {
  local description=$1
  shift
  TESTS_RUN=$((TESTS_RUN + 1))
  if ("$@") >/dev/null 2>&1; then
    fail_test "$description"
  fi
}

create_remote_and_clone() {
  local name=$1
  local remote="$TEST_ROOT/$name.git"
  local seed="$TEST_ROOT/$name-seed"
  local clone="$TEST_ROOT/$name-clone"

  git init --quiet --bare "$remote"
  git init --quiet "$seed"
  git -C "$seed" config user.name "Preview Test"
  git -C "$seed" config user.email "preview-test@example.invalid"
  printf 'seed\n' >"$seed/README.md"
  git -C "$seed" add README.md
  git -C "$seed" commit --quiet -m seed
  git -C "$seed" branch -M dev
  git -C "$seed" remote add origin "$remote"
  git -C "$seed" push --quiet -u origin dev
  git --git-dir="$remote" symbolic-ref HEAD refs/heads/dev
  git clone --quiet --branch dev "$remote" "$clone"
  git -C "$clone" config user.name "Preview Test"
  git -C "$clone" config user.email "preview-test@example.invalid"
  printf '%s\n' "$clone"
}

write_fake_gc() {
  local active=$1
  local fake_gc="$TEST_ROOT/fake-gc"

  cat >"$fake_gc" <<EOF
#!/usr/bin/env bash
cat <<'JSON'
{
  "health": {"usable": true},
  "rigs": [
    {"name": "saymyname-backend", "suspended": true},
    {"name": "saymyname-frontend", "suspended": true}
  ],
  "agents": [
    {"qualified_name": "saymyname-backend/core.control-dispatcher", "running": $active},
    {"qualified_name": "saymyname-frontend/core.control-dispatcher", "running": false}
  ]
}
JSON
EOF
  chmod +x "$fake_gc"
  printf '%s\n' "$fake_gc"
}

clean_repo=$(create_remote_and_clone clean)
clean_origin=$(git -C "$clean_repo" remote get-url origin)
assert_passes "clean dev repository should pass" \
  assert_repo_safe "$clean_repo" "$clean_origin" test

printf 'dirty\n' >"$clean_repo/untracked.txt"
assert_fails "untracked content must fail closed" \
  assert_repo_safe "$clean_repo" "$clean_origin" test
rm -- "$clean_repo/untracked.txt"

extra_worktree="$TEST_ROOT/extra-worktree"
git -C "$clean_repo" worktree add --quiet --detach "$extra_worktree"
assert_fails "an additional worktree must fail closed" \
  assert_repo_safe "$clean_repo" "$clean_origin" test
git -C "$clean_repo" worktree remove --force "$extra_worktree"

printf 'ahead\n' >>"$clean_repo/README.md"
git -C "$clean_repo" add README.md
git -C "$clean_repo" commit --quiet -m ahead
assert_fails "a local-ahead dev branch must fail closed" \
  assert_repo_safe "$clean_repo" "$clean_origin" test

GC_BIN=$(write_fake_gc false)
assert_passes "suspended rigs without active agents should pass" \
  assert_no_active_rig_agents

GC_BIN=$(write_fake_gc true)
assert_fails "an active rig agent must fail closed" \
  assert_no_active_rig_agents

ss() {
  printf 'LISTEN 0 511 127.0.0.1:8080 0.0.0.0:*\n'
}
assert_passes "an occupied port must be detected" port_is_listening 8080
ss() {
  :
}
assert_fails "a free port must not be reported as occupied" port_is_listening 8080
unset -f ss

STATE_DIR="$TEST_ROOT/state"
RUN_DIR="$STATE_DIR/run"
STATE_INITIALIZED=1
mkdir -p "$RUN_DIR"
printf '%s\n' "$STATE_MARKER_VALUE" >"$STATE_DIR/.owner"
printf 'owned\n' >"$RUN_DIR/probe"
assert_passes "owned runtime directory should be removable" clear_run_dir
[[ ! -e $RUN_DIR ]] || fail_test "owned runtime directory was not removed"

mkdir -p "$TEST_ROOT/not-owned"
ln -s "$TEST_ROOT/not-owned" "$RUN_DIR"
assert_fails "a symlinked runtime directory must never be removed" clear_run_dir
[[ -d $TEST_ROOT/not-owned ]] || fail_test "symlink target was unexpectedly removed"

printf 'PASS: %d deterministic preview safety checks\n' "$TESTS_RUN"
