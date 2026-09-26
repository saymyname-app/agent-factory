#!/usr/bin/env bash
#
# factory-guard must detect a named always-on session stuck at creation
# (af-jj9u7 / af-88za4) as its own alert, distinct from campaign-progress
# liveness (tests/factory-guard-liveness-test.sh). On 2026-09-18 the Mayor
# session cycled creating -> failed-create -> creating for hours because a
# misconfigured provider hard-rejected every boot attempt; campaign-progress
# liveness never caught it because it only asks whether the campaign is
# advancing, a question a Mayor that cannot boot cannot even begin to
# answer. This drives the guard against a fake `gc events` stream and
# asserts: a stuck session is flagged and filed exactly once (paging the
# human, not the possibly-unreachable Mayor), a session still within the
# grace window is not, a healthy session is not, and --check-only files
# nothing.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/factory-guard"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

NOW=1789555200   # 2026-09-16T10:40:00Z
iso() { date -u -d "@$1" +%Y-%m-%dT%H:%M:%SZ; }

# --- a throwaway city: committed city.toml, ignored .gc ----------------------
git init -q --bare "$TMP/origin.git"
git init -q "$TMP/city"
cd "$TMP/city"
git config user.email t@t; git config user.name t; git config commit.gpgsign false
git remote add origin "$TMP/origin.git"
mkdir -p .gc
printf '.gc/\n' > .gitignore
printf '[workspace]\nprovider = "claude"\n' > city.toml
git add -A; git commit -qm city; git branch -M main; git push -q origin main; git fetch -q origin

EVENTS="$TMP/events.ndjson"; : > "$EVENTS"
CALLS="$TMP/calls.log"; : > "$CALLS"
mkdir -p "$TMP/beads" "$TMP/bin"

# The coordination bead starts empty; the stub creates it on the first
# metadata write (dedup pointers of sections 7 and 7b).
echo '[]' > "$TMP/coord.json"
SESSIONS="$TMP/sessions.json"; echo '{"sessions":[]}' > "$SESSIONS"

cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$CALLS"
if [[ \$1 == events ]]; then
  cat "$EVENTS"; exit 0
fi
if [[ \$1 == session && \$2 == list ]]; then
  cat "$SESSIONS"; exit 0
fi
if [[ \$1 == bd && \$2 == show && \$3 == af-1vr4 ]]; then
  cat "$TMP/coord.json"; exit 0
fi
if [[ \$1 == bd && \$2 == show ]]; then
  f="$TMP/beads/\$3.json"
  if [[ -f \$f ]]; then cat "\$f"; else echo '[]'; fi
  exit 0
fi
if [[ \$1 == bd && \$2 == create ]]; then
  echo '{"id":"af-boot1","status":"open"}' > "$TMP/beads/af-boot1.json"
  echo '{"id":"af-boot1"}'; exit 0
fi
if [[ \$1 == bd && \$2 == update && \$3 == af-1vr4 ]]; then
  pair=\$5; key=\${pair%%=*}; value=\${pair#*=}
  jq --arg k "\$key" --arg v "\$value" '(if (. | length) == 0 then [{id:"af-1vr4", metadata:{}}] else . end) | .[0].metadata[\$k] = \$v' "$TMP/coord.json" > "$TMP/coord.json.next"
  mv "$TMP/coord.json.next" "$TMP/coord.json"; exit 0
fi
exit 0
STUB
chmod +x "$TMP/bin/gc"
export PATH="$TMP/bin:$PATH"
export GC_BIN="$TMP/bin/gc"
export CAMPAIGN_LOCK_FILE="$TMP/campaign-pointer.lock"
export FACTORY_GUARD_NOW=$NOW

# session_event <identity> <state> <age-seconds> [extra-metadata-json]
session_event() {
  local identity="$1" state="$2" age="$3" extra="${4:-}"
  [ -z "$extra" ] && extra='{}'
  local ts; ts=$(iso $((NOW - age)))
  jq -nc --arg id "$identity" --arg st "$state" --arg ts "$ts" --argjson extra "$extra" '
    {type:"bead.updated", ts:$ts, payload:{bead:{id:"af-evt", metadata:({
      configured_named_mode:"always", configured_named_identity:$id, agent_name:$id,
      state:$st, command:"codex --model gpt-5.5", provider:"codex"} + $extra)}}}' >> "$EVENTS"
}
guard() { FACTORY_ROOT="$TMP/city" "$GUARD" "$@" 2>&1 || true; }
creates() { grep -c '^bd create' "$CALLS" || true; }

# 1. a healthy awake session is not a defect ---------------------------------
: > "$EVENTS"
session_event mayor awake 300
out=$(guard --check-only)
grep -q "✓ session-boot — mayor is awake" <<<"$out" || { echo "$out" >&2; fail "healthy session not reported ok"; }

# 2. freshly creating, still inside the grace window: not yet a defect -------
: > "$EVENTS"
session_event mayor creating 300   # 5 min ago
out=$(guard --check-only)
grep -q "· session-boot — mayor stuck in 'creating' for 5 min" <<<"$out" \
  || { echo "$out" >&2; fail "within-window creating not reported as info" ; }
grep -q "! session-boot" <<<"$out" && fail "a session still inside the grace window was flagged as a defect"

# 3. stuck past the threshold: flagged, and --check-only files nothing -------
: > "$EVENTS"
session_event mayor creating 1200   # 20 min ago
out=$(guard --check-only)
grep -q "session-boot — mayor stuck in 'creating' for 20 min" <<<"$out" \
  || { echo "$out" >&2; fail "stuck session not flagged"; }
grep -q "^UNRESOLVED" <<<"$out" || fail "a stuck session must not read as healthy"
[ "$(creates)" = "0" ] || fail "--check-only filed a defect"

# 4. the default run files it exactly once, and pages the human, not mayor --
out=$(guard)
grep -q "filed session-boot-stuck defect af-boot1 for mayor" <<<"$out" \
  || { echo "$out" >&2; fail "stuck session not filed"; }
[ "$(jq -r '.[0].metadata["gc.session_boot_stuck_bead.mayor"]' "$TMP/coord.json")" = "af-boot1" ] \
  || fail "the filed defect is not remembered"
grep -q "^mail send human --notify" "$CALLS" \
  || fail "a stuck session must page a human directly (the orchestrator itself may be unreachable)"
grep -q "^mail send mayor" "$CALLS" \
  && fail "must not page the Mayor about the Mayor being unable to boot"
out=$(guard)
grep -q "already filed: af-boot1" <<<"$out" || { echo "$out" >&2; fail "second run did not recognise the open defect"; }
[ "$(creates)" = "1" ] || fail "the defect was filed more than once"

# ...and once it is closed, a new stall files a new one.
echo '{"id":"af-boot1","status":"closed"}' > "$TMP/beads/af-boot1.json"
guard >/dev/null
[ "$(creates)" = "2" ] || fail "a closed defect must not suppress a new stall"

# 5. churn across bead ids (creating -> failed-create -> creating) counts ----
# as one unbroken streak, exactly like the real 2026-09-18 incident.
: > "$EVENTS"
session_event mayor creating 1800                                              # 30 min ago
session_event mayor failed-create 1500 '{"close_reason":"provider 400: model not supported"}'
session_event mayor creating 1400
out=$(guard --check-only)
grep -q "mayor stuck in 'creating' for 30 min" <<<"$out" \
  || { echo "$out" >&2; fail "churn across bead ids was not treated as one streak"; }

# 6. --check-only never touches the store --------------------------------------
: > "$CALLS"
: > "$EVENTS"
session_event mayor creating 1200
guard --check-only >/dev/null
grep -q '^bd create' "$CALLS" && fail "--check-only must never create a bead"

# 8. the Mayor session itself, quarantined past the grace window, is paged to
#    a human once per streak (section 7); inside the window, or with
#    --check-only, it is not ------------------------------------------------
pages() { grep -c '^mail send human --notify -s Mayor session down' "$CALLS" || true; }
: > "$EVENTS"; : > "$CALLS"
echo '{"sessions":[{"id":"af-m1","alias":"mayor","state":"quarantined","last_active":"'"$(iso $((NOW - 5 * 60)))"'"}]}' > "$SESSIONS"
guard >/dev/null
[ "$(pages)" = "0" ] || fail "a Mayor session inside the grace window was paged"
echo '{"sessions":[{"id":"af-m1","alias":"mayor","state":"quarantined","last_active":"'"$(iso $((NOW - 40 * 60)))"'"}]}' > "$SESSIONS"
guard --check-only >/dev/null
[ "$(pages)" = "0" ] || fail "--check-only paged the Mayor session"
guard >/dev/null
[ "$(pages)" = "1" ] || { cat "$CALLS" >&2; fail "a quarantined Mayor session was not paged exactly once"; }
guard >/dev/null
[ "$(pages)" = "1" ] || fail "the same down streak paged a second time"
echo '{"sessions":[]}' > "$SESSIONS"

# 7. outside a city root the check stands down -------------------------------
mkdir -p "$TMP/plain" && git -C "$TMP/plain" init -q
: > "$CALLS"
out=$(FACTORY_ROOT="$TMP/plain" "$GUARD" --check-only 2>&1 || true)
grep -q "· session-boot — not checked" <<<"$out" || { echo "$out" >&2; fail "session-boot ran outside a city"; }
grep -q 'events' "$CALLS" && fail "a non-city run queried gc events"

echo "OK factory-guard detects a stuck-at-creation named session distinctly"
