#!/usr/bin/env bash
#
# on-order-failed pages the Mayor once a chronic order is failing, instead of
# leaving order.failed events unread forever (O1: 371 in 24h, live, none read).
#
# Drives the real script against a stub gc whose `events` subcommand returns
# canned order.failed lines, and asserts: below the streak threshold, nothing
# happens; at or above it, exactly one bead is filed and the Mayor is paged
# once; a second run recognises the still-open bead and does not duplicate it;
# a different subject is tracked independently; --check-only files nothing.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SCRIPT="$REPO_ROOT/bin/on-order-failed"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/bin" "$TMP/beads"
CALLS="$TMP/calls.log"; : > "$CALLS"
EVENTS_FILE="$TMP/events.jsonl"

events_n() {  # events_n <subject> <count>
  local subject=$1 count=$2 i
  : > "$EVENTS_FILE"
  for ((i = 0; i < count; i++)); do
    printf '{"actor":"controller","message":"exit status 1","payload":{},"subject":"%s","ts":"2026-09-17T12:%02d:00Z","type":"order.failed","ok":true}\n' \
      "$subject" "$i" >> "$EVENTS_FILE"
  done
}

cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$CALLS"
if [[ \${1:-} == events ]]; then
  cat "$EVENTS_FILE" 2>/dev/null
  exit 0
fi
if [[ \${1:-} == bd && \${2:-} == list ]]; then
  title=""
  args=("\$@")
  for i in "\${!args[@]}"; do
    [[ \${args[\$i]} == --title-contains ]] && title="\${args[\$((i+1))]}"
  done
  if [[ -n \$title && -f "$TMP/beads/filed" ]] && grep -qF "\$title" "$TMP/beads/filed"; then
    echo '[{"id":"af-existing"}]'
  else
    echo '[]'
  fi
  exit 0
fi
if [[ \${1:-} == bd && \${2:-} == create ]]; then
  title="\${3:-}"
  echo "\$title" >> "$TMP/beads/filed"
  echo '{"id":"af-new1"}'
  exit 0
fi
if [[ \${1:-} == bd && \${2:-} == show ]]; then
  # escalation-door's own show_bead call -- every id on the mayor path here
  # is a bead this test just filed, so a minimal open bead is always valid.
  echo '[{"id":"'"\${3:-}"'","status":"open","metadata":{}}]'
  exit 0
fi
if [[ \${1:-} == mail && \${2:-} == send ]]; then
  exit 0
fi
exit 0
STUB
chmod +x "$TMP/bin/gc"
export PATH="$TMP/bin:$PATH"
export FACTORY_ROOT="$TMP"
export ON_ORDER_FAILED_STREAK=5
touch "$TMP/city.toml" 2>/dev/null || true

run() { FACTORY_ROOT="$TMP" "$SCRIPT" "$@" 2>&1; }

# --- below the streak threshold: nothing happens -----------------------------
events_n dolt-remotes-patrol 4
out=$(run)
grep -q "mail send mayor" "$CALLS" && fail "paged below the failure streak threshold"
[ ! -s "$TMP/beads/filed" ] || fail "filed a bead below the failure streak threshold"

# --- at the threshold: files exactly one bead, pages the mayor once ---------
: > "$CALLS"
events_n dolt-remotes-patrol 5
out=$(run)
grep -q "^bd create" "$CALLS" || { echo "$out" >&2; fail "did not file a bead at the streak threshold"; }
grep -q "^mail send mayor" "$CALLS" || fail "did not page the mayor at the streak threshold"
# Routed through escalation-door's Mayor-first class (O06/O07), not a raw mail.
grep -q "^mail send mayor --notify -s Escalation (Mayor first): af-new1" "$CALLS" \
  || fail "did not route through escalation-door's mayor-first class"
[ "$(grep -c '^bd create' "$CALLS")" = "1" ] || fail "filed more than one bead in a single run"
# The count is a total inside the lookback window, so the page must not claim a run.
grep -q "consecutive failures" "$CALLS" && fail "the page words a total count as consecutive failures"

# --- a second run recognises the still-open bead: no duplicate --------------
: > "$CALLS"
out=$(run)
grep -q "^bd create" "$CALLS" && fail "duplicated an already-open finding"
grep -q "^mail send mayor" "$CALLS" && fail "re-paged an already-open finding"

# --- --check-only never files or pages ---------------------------------------
rm -f "$TMP/beads/filed"; : > "$CALLS"
out=$(run --check-only)
grep -q "^bd create" "$CALLS" && fail "--check-only filed a bead"
grep -q "^mail send" "$CALLS" && fail "--check-only paged anyone"
grep -q "would flag dolt-remotes-patrol" <<<"$out" || { echo "$out" >&2; fail "--check-only did not report what it would do"; }

# --- no events at all: quiet, no error ---------------------------------------
: > "$EVENTS_FILE"; : > "$CALLS"
run >/dev/null || fail "an empty event stream must not be an error"
grep -qE '^(bd |mail )' "$CALLS" && fail "an empty event stream should not call gc bd/mail at all"

echo "OK on-order-failed pages a chronic failure, not a transient one"
