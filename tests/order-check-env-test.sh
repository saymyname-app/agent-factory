#!/usr/bin/env bash
# af-37a1xn: a condition order's check runs in the environment the controller
# gives it, not in a shell's. Two of them answered wrong there while they
# answered right from a shell:
#
#   - bin/backup-freshness read GC_PACK_STATE_DIR as the core pack's state
#     dir. gc sets it to the state dir of the pack that owns the order (the
#     city's), so the archive was "missing", the check said "skipping" and
#     exited 0: due on every 30 s tick (221 order.fired in 2 h, 2026-10-11).
#   - gc 1.5.0 exports BD_BIN= (empty). `os.environ.get("BD_BIN", "bd")`
#     read it as a binary name: mail-reply-reap and idle-ready-work-wake
#     crashed (exit 1) and never fired again (their own tests hold that case).
#
# The class: a check that cannot evaluate its question must not exit 0.
# No live city, no real gc: a throwaway root and a stub `gc`.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

T=$(mktemp -d /tmp/af-order-check-env.XXXXXX)
trap 'rm -rf -- "$T"' EXIT

CITY="$T/city"
ARCHIVE="$CITY/.gc/runtime/packs/core/jsonl-archive"
mkdir -p "$ARCHIVE" "$CITY/.gc/runtime/packs/city" "$T/stub" "$T/bare"
printf '#!/usr/bin/env bash\nexit 0\n' >"$T/stub/gc"
chmod +x "$T/stub/gc"
cp "$T/stub/gc" "$T/bare/gc"
ln -s "$(command -v bash)" "$T/bare/bash"

git -C "$ARCHIVE" init -q
git -C "$ARCHIVE" config user.email "test@example.com"
git -C "$ARCHIVE" config user.name "test"
STALE_EPOCH=$(($(date +%s) - 25 * 3600))
GIT_AUTHOR_DATE="@$STALE_EPOCH +0000" GIT_COMMITTER_DATE="@$STALE_EPOCH +0000" \
  git -C "$ARCHIVE" commit -q --allow-empty -m "seed"

# The check as the controller runs it for this city-level order: the pack
# variables name the city pack, never core (measured on gc 1.5.0).
controller_check() {
  local path="$1" status=0
  env -u GC_JSONL_ARCHIVE_REPO \
    FACTORY_ROOT="$CITY" \
    GC_PACK_NAME=city GC_PACK_DIR="$CITY" \
    GC_PACK_STATE_DIR="$CITY/.gc/runtime/packs/city" \
    BD_BIN= \
    BACKUP_FRESHNESS_CHANGED_OVERRIDE=3 \
    PATH="$path" \
    "$ROOT/bin/backup-freshness" --check-only --quiet 2>"$T/stderr" || status=$?
  printf '%s\n' "$status"
}

# 1. Stale archive, beads changed: still due under the controller's variables.
[ "$(controller_check "$T/stub:$PATH")" = 0 ] \
  || fail "stale archive with bead changes must be due (exit 0) in the controller's environment"

# 2. Fresh archive: not due. This is the live case that fired every tick.
git -C "$ARCHIVE" commit -q --allow-empty -m "fresh"
[ "$(controller_check "$T/stub:$PATH")" = 1 ] \
  || fail "fresh archive must not be due (exit 1) in the controller's environment"

# 3. A required tool is missing: cannot evaluate, so not due, and it says why.
status=$(controller_check "$T/bare")
[ "$status" = 2 ] || fail "missing tool must exit 2 (cannot evaluate), got $status"
grep -q 'cannot evaluate' "$T/stderr" || fail "missing tool must say so on stderr"

# 4. The archive is missing: cannot evaluate, so not due, and it says why.
rm -rf -- "$ARCHIVE"
status=$(controller_check "$T/stub:$PATH")
[ "$status" = 2 ] || fail "missing archive must exit 2 (cannot evaluate), got $status"
grep -q 'cannot evaluate' "$T/stderr" || fail "missing archive must say so on stderr"

# 5. No tool reads an empty BD_BIN as a binary name (gc exports BD_BIN=).
offenders=$(grep -rnE 'environ\.get\("BD_BIN", *"' "$ROOT/bin" --exclude-dir=__pycache__ || true)
[ -z "$offenders" ] || fail "empty BD_BIN read as a binary name (use: os.environ.get(\"BD_BIN\") or \"bd\"):
$offenders"

echo "PASS: a check that cannot evaluate is never due, and backup-freshness answers right in the controller's environment"
