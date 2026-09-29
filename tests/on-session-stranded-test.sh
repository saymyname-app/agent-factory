#!/usr/bin/env bash
#
# on-session-stranded reopens in-progress beads a dead pool session left
# orphaned, instead of leaving them stuck forever (O4: 13 session.stranded
# events in 24h, live, none acted on).
#
# Drives the real script against a stub gc whose `events` subcommand returns a
# canned session.stranded event, and asserts: an in_progress bead is reopened
# and the Mayor paged once; an already-closed bead in the same event is left
# alone; the same event is never reprocessed on a second run (dedup by
# session_id survives across runs via the on-disk state file); --check-only
# reopens nothing.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SCRIPT="$REPO_ROOT/bin/on-session-stranded"
# tests/lib/sandbox.sh (P10, af-ygibh): a throwaway HOME/city and, crucially,
# GC_BIN pointed off the real binary. on-session-stranded shells out to
# bin/escalation-door, which resolves ${GC_BIN:-gc} directly, so a PATH-only
# stub does not stop it reaching the live city (same class of live incident
# as factory-watchdog-test.sh and on-order-failed-test.sh, 2026-09-29,
# af-0h4vnc).
. "$REPO_ROOT/tests/lib/sandbox.sh"
sandbox_init
TMP="$SANDBOX_DIR"
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/bin" "$TMP/beads"
CALLS="$TMP/calls.log"; : > "$CALLS"
STATE_FILE="$TMP/state.json"
EVENTS_FILE="$TMP/events.jsonl"

cat > "$EVENTS_FILE" <<'JSON'
{"actor":"gc","message":"pool session terminated without clean drain","payload":{"session_id":"af-br7i","session_name":"claude-af-br7i","template":"claude","work_bead_ids":["af-stuck1","af-done1"]},"session_id":"af-br7i","type":"session.stranded","ts":"2026-09-16T21:24:33Z","ok":true}
JSON

cat > "$TMP/beads/af-stuck1.json" <<'JSON'
[{"id":"af-stuck1","status":"in_progress"}]
JSON
cat > "$TMP/beads/af-done1.json" <<'JSON'
[{"id":"af-done1","status":"closed"}]
JSON

cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$CALLS"
if [[ \${1:-} == events ]]; then
  cat "$EVENTS_FILE" 2>/dev/null
  exit 0
fi
if [[ \${1:-} == bd && \${2:-} == show ]]; then
  f="$TMP/beads/\${3}.json"
  [[ -f \$f ]] && cat "\$f" || echo '[]'
  exit 0
fi
if [[ \${1:-} == bd && \${2:-} == update ]]; then
  bead_id=\$3
  [[ -f "$TMP/fail-update" ]] && exit 1
  echo "in_progress" # unused, keep for shellcheck happiness
  echo "\$bead_id updated" >> "$TMP/updated.log"
  exit 0
fi
if [[ \${1:-} == mail && \${2:-} == send ]]; then
  exit 0
fi
exit 0
STUB
chmod +x "$TMP/bin/gc"
export PATH="$TMP/bin:$PATH"
export GC_BIN="$TMP/bin/gc"
touch "$TMP/city.toml" 2>/dev/null || true

run() {
  FACTORY_ROOT="$TMP" ON_SESSION_STRANDED_STATE_FILE="$STATE_FILE" "$SCRIPT" "$@" 2>&1
}

# --- --check-only reopens nothing ---------------------------------------------
out=$(run --check-only)
[ ! -f "$TMP/updated.log" ] || fail "--check-only reopened a bead"
grep -q "would process af-br7i" <<<"$out" || { echo "$out" >&2; fail "--check-only did not report the pending session"; }
[ ! -s "$STATE_FILE" ] || fail "--check-only must not persist dedup state"

# --- the real pass: only the in_progress bead is reopened, mayor paged once --
out=$(run)
grep -q "af-stuck1 updated" "$TMP/updated.log" || { echo "$out" >&2; fail "the in_progress bead was not reopened"; }
grep -q "af-done1 updated" "$TMP/updated.log" 2>/dev/null && fail "an already-closed bead must not be touched"
[ "$(grep -c 'mail send mayor' "$CALLS")" = "1" ] || fail "the mayor was not paged exactly once"
# Routed through escalation-door's Mayor-first class (O06/O07), not a raw mail.
grep -q "^mail send mayor --notify -s Escalation (Mayor first): af-stuck1" "$CALLS" \
  || fail "did not route through escalation-door's mayor-first class"
grep -q '"af-br7i"' "$STATE_FILE" || fail "the session was not recorded as handled"
# "$*" logging turns the empty --assignee value into a double space.
grep -q -- "^bd update af-stuck1 --status open --assignee  --set-metadata" "$CALLS" \
  || fail "the reopened bead was left assigned to the dead session"

# --- a second run does not reprocess the same session -------------------------
rm -f "$TMP/updated.log"; : > "$CALLS"
run >/dev/null
[ ! -f "$TMP/updated.log" ] || fail "an already-handled session was reprocessed"
grep -q "mail send mayor" "$CALLS" && fail "an already-handled session paged the mayor again"

# --- state survives being invoked as a fresh process (dedup is on disk) ------
[ -s "$STATE_FILE" ] || fail "dedup state was not written to disk"

# --- a failed reopen is not recorded as handled: the next pass retries it -----
cat > "$EVENTS_FILE" <<'JSON'
{"actor":"gc","message":"pool session terminated without clean drain","payload":{"session_id":"af-zz9k","session_name":"claude-af-zz9k","template":"claude","work_bead_ids":["af-stuck2"]},"session_id":"af-zz9k","type":"session.stranded","ts":"2026-09-16T22:00:00Z","ok":true}
JSON
cat > "$TMP/beads/af-stuck2.json" <<'JSON'
[{"id":"af-stuck2","status":"in_progress"}]
JSON
rm -f "$TMP/updated.log"; : > "$CALLS"; touch "$TMP/fail-update"
run >/dev/null
grep -q '"af-zz9k"' "$STATE_FILE" && fail "a session whose bead update failed was recorded as handled"
grep -q "mail send mayor" "$CALLS" && fail "the mayor was paged although nothing was reopened"
rm -f "$TMP/fail-update"; : > "$CALLS"
run >/dev/null
grep -q "af-stuck2 updated" "$TMP/updated.log" || fail "the failed reopen was not retried on the next pass"
grep -q '"af-zz9k"' "$STATE_FILE" || fail "the retried session was not recorded as handled"

echo "OK on-session-stranded reopens orphaned work, once per session"
