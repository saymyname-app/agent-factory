#!/usr/bin/env bash
#
# bin/factory-setup must turn a fresh clone's tracked .githooks/ into this
# clone's active core.hooksPath (O14, F17) — git clone never does this on
# its own, since core.hooksPath lives only in a checked-out .git/config, not
# in anything tracked. This proves a real `git clone` of a throwaway repo
# starts with hooks inactive, and that running the script activates them —
# idempotently, and without requiring the hooks to be executable already.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SETUP="$REPO_ROOT/bin/factory-setup"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

[ -x "$SETUP" ] || fail "$SETUP is not executable"

# --- a throwaway origin with a tracked, non-executable hook -----------------
git init -q --bare "$TMP/origin.git"
git init -q "$TMP/seed"
cd "$TMP/seed"
git config user.email t@t; git config user.name t; git config commit.gpgsign false
mkdir -p .githooks
printf '#!/usr/bin/env bash\nexit 0\n' > .githooks/pre-push
chmod -x .githooks/pre-push
git add .githooks/pre-push
git commit -q -m seed
git remote add origin "$TMP/origin.git"
git push -q origin HEAD:refs/heads/main
git -C "$TMP/origin.git" symbolic-ref HEAD refs/heads/main

# --- a fresh clone starts with no hooks active ------------------------------
# factory-setup resolves its target repo from its own on-disk location
# (BASH_SOURCE), not from cwd, so exercising it against a throwaway clone
# means running the clone's own copy of the script, at the same relative
# path it lives at in the real repository.
git clone -q "$TMP/origin.git" "$TMP/clone"
mkdir -p "$TMP/clone/bin"
cp "$SETUP" "$TMP/clone/bin/factory-setup"
chmod +x "$TMP/clone/bin/factory-setup"
cd "$TMP/clone"
git config user.email t@t; git config user.name t; git config commit.gpgsign false

hooks_path=$(git config --get core.hooksPath || true)
[ -z "$hooks_path" ] || fail "fresh clone already has core.hooksPath=$hooks_path set — fixture invalid"

# --- factory-setup activates them, and restores the executable bit ---------
./bin/factory-setup

hooks_path=$(git config --get core.hooksPath || true)
[ "$hooks_path" = ".githooks" ] || fail "core.hooksPath is '$hooks_path', expected '.githooks'"
[ -x .githooks/pre-push ] || fail ".githooks/pre-push is still not executable after factory-setup"

# --- idempotent: a second run does not fail or change the outcome ----------
./bin/factory-setup || fail "a second run of factory-setup failed"
hooks_path=$(git config --get core.hooksPath || true)
[ "$hooks_path" = ".githooks" ] || fail "core.hooksPath drifted on a second run: $hooks_path"

# --- refuses outside a git working copy -------------------------------------
cd "$TMP"
mkdir -p not-a-repo/bin
cp "$SETUP" not-a-repo/bin/factory-setup
mkdir -p not-a-repo/.githooks
if (cd not-a-repo && ./bin/factory-setup >/dev/null 2>&1); then
  fail "factory-setup did not refuse a directory with no .git/"
fi

echo "PASS: factory-setup activates a fresh clone's .githooks, restores exec bits, and is idempotent"
