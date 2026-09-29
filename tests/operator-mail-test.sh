#!/usr/bin/env bash
#
# bin/operator-mail: the operator entry path (docs/OPERATOR_BRIDGE.md) must
# never let mail resolve to gc mail send's "human" fallback -- that reads as
# Benjamin himself even though the operator's Codex session is an agent
# acting on his stated intent, not Benjamin (P15,
# spec-parallel-delivery-2026-09-29). Proves: a mail sent through
# bin/operator-mail is sent with an explicit sender identity (po-agent by
# default, or config/operator.toml's mail_alias override), never with no
# --from at all (which is how "human" happens); the body self-identifies the
# true actor; missing subject/message is rejected before any send is
# attempted.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SCRIPT="$REPO_ROOT/bin/operator-mail"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/bin"
MAIL_LOG="$TMP/mail.log"

cat > "$TMP/bin/gc" <<'STUB'
#!/usr/bin/env bash
set -Eeuo pipefail
if [[ ${1:-} == mail && ${2:-} == send ]]; then
  printf '%s\n' "$*" >> "$MAIL_LOG"
  exit 0
fi
exit 64
STUB
chmod +x "$TMP/bin/gc"
export GC_BIN="$TMP/bin/gc"
export MAIL_LOG

# --- default identity: po-agent, from config/operator.toml -----------------
: > "$MAIL_LOG"
"$SCRIPT" mayor -s "test subject" -m "test body" --notify
record=$(cat "$MAIL_LOG")
[[ "$record" == *"--from po-agent"* ]] || fail "did not send with --from po-agent: $record"
[[ "$record" == *"ACTION: po-agent"* ]] || fail "body does not self-identify po-agent: $record"
[[ "$record" != *"--from human"* ]] || fail "sender resolved to human: $record"
[[ "$record" == *"--notify"* ]] || fail "--notify was not forwarded: $record"

# --- override via GC_OPERATOR_MAIL_ALIAS ------------------------------------
: > "$MAIL_LOG"
GC_OPERATOR_MAIL_ALIAS=custom-agent "$SCRIPT" mayor -s "s" -m "m"
record=$(cat "$MAIL_LOG")
[[ "$record" == *"--from custom-agent"* ]] || fail "override alias not honored: $record"
[[ "$record" == *"ACTION: custom-agent"* ]] || fail "body did not self-identify override alias: $record"

# --- missing subject/message is rejected, no send attempted ----------------
: > "$MAIL_LOG"
if "$SCRIPT" mayor -m "m" >/dev/null 2>&1; then
  fail "missing subject should have been rejected"
fi
[[ ! -s "$MAIL_LOG" ]] || fail "a send was attempted despite the missing subject"

printf 'PASS: bin/operator-mail always sends with an explicit non-human sender\n'
