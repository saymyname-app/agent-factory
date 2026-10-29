#!/usr/bin/env bash
# bin/operator-bd: operator tracker writes always use the durable
# po-agent/<Codex-session> identity, whatever actor the parent shell exports.
set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SCRIPT="$ROOT/bin/operator-bd"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

[ -x "$SCRIPT" ] || fail "$SCRIPT is missing or not executable"

TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
FAKE_BD="$TMP/bd"
LOG_PREFIX="$TMP/call"

cat >"$FAKE_BD" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$PWD" >"$BD_LOG_PREFIX.cwd"
printf '%s\n' "$@" >"$BD_LOG_PREFIX.args"
SH
chmod +x "$FAKE_BD"

(
  cd "$TMP"
  CODEX_THREAD_ID=thread-123 \
    CODEX_SESSION_ID=session-fallback \
    BEADS_ACTOR=operateur-windows \
    BD_BIN="$FAKE_BD" \
    BD_LOG_PREFIX="$LOG_PREFIX" \
    "$SCRIPT" update af-example --claim
)

[ "$(cat "$LOG_PREFIX.cwd")" = "$ROOT" ] \
  || fail "operator-bd must run bd from the Factory root"
diff -u <(printf '%s\n' --actor po-agent/thread-123 update af-example --claim) \
  "$LOG_PREFIX.args" \
  || fail "operator-bd did not force the canonical per-session actor"

rm -f "$LOG_PREFIX.cwd" "$LOG_PREFIX.args"
env -u CODEX_THREAD_ID CODEX_SESSION_ID=session-fallback \
  BD_BIN="$FAKE_BD" BD_LOG_PREFIX="$LOG_PREFIX" \
  "$SCRIPT" show af-example
diff -u <(printf '%s\n' --actor po-agent/session-fallback show af-example) \
  "$LOG_PREFIX.args" \
  || fail "operator-bd did not use CODEX_SESSION_ID as its fallback"

rm -f "$LOG_PREFIX.cwd" "$LOG_PREFIX.args"
if CODEX_THREAD_ID=thread-123 BD_BIN="$FAKE_BD" BD_LOG_PREFIX="$LOG_PREFIX" \
  "$SCRIPT" --actor operateur-windows update af-example --claim >/dev/null 2>&1; then
  fail "operator-bd accepted a caller-supplied actor override"
fi
[ ! -e "$LOG_PREFIX.args" ] || fail "operator-bd called bd after refusing an actor override"

if env -u CODEX_THREAD_ID -u CODEX_SESSION_ID \
  BD_BIN="$FAKE_BD" BD_LOG_PREFIX="$LOG_PREFIX" \
  "$SCRIPT" update af-example --claim >/dev/null 2>&1; then
  fail "operator-bd accepted a write without a Codex session identity"
fi
[ ! -e "$LOG_PREFIX.args" ] || fail "operator-bd called bd without a Codex session identity"

echo "PASS: operator-bd forces po-agent/<Codex-session> and refuses unsafe identity fallbacks"
