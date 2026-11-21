#!/usr/bin/env bash
# bin/human-mail-archive (af-q55qqx.10): only mail to human older than the
# cutoff is archived, at most one batch a run; an unreadable mailbox or a
# failed archive is an error, never a silent green.
set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
TOOL="$REPO_ROOT/bin/human-mail-archive"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

old=$(date -u -d '-10 days' +%Y-%m-%dT%H:%M:%SZ)
new=$(date -u -d '-1 hours' +%Y-%m-%dT%H:%M:%SZ)
cat >"$TMP/inbox.json" <<JSON
{"ok":true,"recipient":"human","messages":[
 {"id":"af-wisp-old1","to":"human","created_at":"$old"},
 {"id":"af-wisp-old2","to":"human","created_at":"$old"},
 {"id":"af-wisp-old3","to":"human","created_at":"$old"},
 {"id":"af-wisp-new1","to":"human","created_at":"$new"}]}
JSON
# A backlog far larger than a batch, as on 21/11 (3324): jq | head failed on it.
big=$(for i in $(seq 1 5000); do printf '{"id":"af-wisp-b%s","to":"human","created_at":"%s"},' "$i" "$old"; done)
printf '{"ok":true,"messages":[%s{"id":"af-wisp-last","created_at":"%s"}]}' "$big" "$old" >"$TMP/big.json"
cat >"$TMP/gc" <<SH
#!/usr/bin/env bash
case "\$1 \$2" in
  "mail inbox") [ -n "\${FAKE_INBOX_FAILS:-}" ] && exit 1; cat "$TMP/inbox.json" ;;
  "mail archive") [ -n "\${FAKE_ARCHIVE_FAILS:-}" ] && exit 1; shift 2; printf '%s\n' "\$@" >>"$TMP/archived" ;;
  *) exit 3 ;;
esac
SH
chmod +x "$TMP/gc"
run() { GC_BIN="$TMP/gc" "$TOOL" "$@"; }

out=$(run --dry-run); [ ! -e "$TMP/archived" ] || fail "--dry-run archived"
grep -q "would archive 3" <<<"$out" || fail "--dry-run did not count the 3 old messages: $out"

out=$(HUMAN_MAIL_ARCHIVE_BATCH=2 run)
[ "$(cat "$TMP/archived")" = "$(printf 'af-wisp-old1\naf-wisp-old2')" ] \
  || fail "one batch of the oldest-cut messages expected, got: $(cat "$TMP/archived")"
grep -q "archived 2 message" <<<"$out" || fail "no report of what was archived: $out"
grep -q new1 "$TMP/archived" && fail "a message younger than the cutoff was archived"

cp "$TMP/inbox.json" "$TMP/small.json"; cp "$TMP/big.json" "$TMP/inbox.json"; rm -f "$TMP/archived"
out=$(run) || fail "a backlog larger than a batch failed: $out"
[ "$(wc -l <"$TMP/archived")" = "200" ] || fail "one batch of 200 expected from a large backlog"
cp "$TMP/small.json" "$TMP/inbox.json"

FAKE_INBOX_FAILS=1 run 2>/dev/null && fail "an unreadable mailbox exited 0"
FAKE_ARCHIVE_FAILS=1 run 2>/dev/null && fail "a failed archive exited 0"
echo '{"ok":true,"messages":[]}' >"$TMP/inbox.json"
grep -q "nothing to human" <<<"$(run)" || fail "an empty mailbox was not reported as such"

echo "OK human-mail-archive archives only old mail to human, one batch a run, and fails loudly"
