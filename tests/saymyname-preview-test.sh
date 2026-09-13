#!/usr/bin/env bash

set -Eeuo pipefail

TEST_ROOT=$(mktemp -d)
trap 'rm -rf -- "$TEST_ROOT"' EXIT

export SAYMYNAME_PREVIEW_SOURCE_ONLY=1
# shellcheck source=../bin/saymyname-preview
PREVIEW_SCRIPT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)/bin/saymyname-preview"
source "$PREVIEW_SCRIPT"

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

assert_exit_code() {
  local expected=$1
  local description=$2
  local actual
  shift 2
  TESTS_RUN=$((TESTS_RUN + 1))
  if ("$@") >/dev/null 2>&1; then
    actual=0
  else
    actual=$?
  fi
  [[ $actual -eq $expected ]] || fail_test "$description (expected $expected, got $actual)"
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

write_fake_gc_without_agents() {
  local fake_gc="$TEST_ROOT/fake-gc-without-agents"

  cat >"$fake_gc" <<'EOF'
#!/usr/bin/env bash
cat <<'JSON'
{
  "health": {"usable": true},
  "rigs": [
    {"name": "saymyname-backend", "suspended": true},
    {"name": "saymyname-frontend", "suspended": true}
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

GC_BIN=$(write_fake_gc_without_agents)
assert_fails "a missing agent inventory must fail closed" \
  assert_no_active_rig_agents

GC_BIN=$(write_fake_gc true)
assert_fails "an active rig agent must fail closed" \
  assert_no_active_rig_agents

GC_BIN=false
assert_fails "unavailable Gas City must fail the writer check closed" \
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

assert_fails "the filesystem root must never be accepted as preview state" \
  assert_safe_state_dir_path /
assert_passes "a namespaced preview state path should be accepted" \
  assert_safe_state_dir_path "$TEST_ROOT/agent-factory/saymyname-preview"

broad_state_dir="$TEST_ROOT/broad-state"
mkdir -p "$broad_state_dir"
chmod 755 "$broad_state_dir"
assert_fails "an override without the preview namespace must fail before mutation" \
  env -u SAYMYNAME_PREVIEW_SOURCE_ONLY GC_BIN=false \
    SAYMYNAME_PREVIEW_STATE_DIR="$broad_state_dir" "$PREVIEW_SCRIPT" status
[[ $(stat -c '%a' "$broad_state_dir") == 755 ]] \
  || fail_test "rejected broad state directory permissions were changed"
[[ ! -e $broad_state_dir/.owner ]] \
  || fail_test "rejected broad state directory received an ownership marker"

recovery_state_dir="$TEST_ROOT/recovery/agent-factory/saymyname-preview"
assert_exit_code 3 "status must report stopped while Gas City is unavailable" \
  env -u SAYMYNAME_PREVIEW_SOURCE_ONLY GC_BIN=false \
    SAYMYNAME_PREVIEW_STATE_DIR="$recovery_state_dir" "$PREVIEW_SCRIPT" status

fake_docker="$TEST_ROOT/fake-docker"
printf '#!/usr/bin/env bash\nexit 1\n' >"$fake_docker"
chmod +x "$fake_docker"
mkdir -p "$recovery_state_dir/run"
printf '%s\n' "$STATE_MARKER_VALUE" >"$recovery_state_dir/.owner"
printf 'stale\n' >"$recovery_state_dir/run/probe"
assert_passes "stop must clean owned stale state while Gas City is unavailable" \
  env -u SAYMYNAME_PREVIEW_SOURCE_ONLY GC_BIN=false DOCKER_BIN="$fake_docker" \
    SAYMYNAME_PREVIEW_STATE_DIR="$recovery_state_dir" "$PREVIEW_SCRIPT" stop
[[ ! -e $recovery_state_dir/run ]] \
  || fail_test "stop left owned stale state behind while Gas City was unavailable"

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
