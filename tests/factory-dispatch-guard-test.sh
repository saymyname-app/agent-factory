#!/usr/bin/env bash
#
# bin/factory-dispatch-guard: detects a bead `gc sling`d to a target while
# its assignee still holds a stale, different value -- invisible to the
# target's own claim query even though dispatch reported success (af-33a4e).
# Regression for the 2026-09-18 incident: the Mayor ran
# `gc sling bd.dog af-c6tdz` without --reassign; af-c6tdz's assignee stayed
# `mayor` (its pre-existing value), and bd.dog kept reporting "no assigned
# work" for about 2 hours. This drives the guard against a stub gc binary
# and proves: a bead whose assignee matches its routed target is left
# alone; a freshly-drifted bead (within the grace window) is left alone; a
# genuinely stale drift is reported and left untouched under --check-only;
# a genuinely stale drift is repaired (assignee cleared) and the Mayor
# paged exactly once by a default run; and a bead with no assignee at all
# is never flagged.
#
# Also regression for the same-day af-7qxzh incident: the guard cleared the
# assignee on later `gc.session_affinity=require` formula steps whose owning
# session was still 17m50s into an earlier step of the same workflow, not
# stale at all. Proves: a session_affinity=require bead whose named session
# is still alive is left alone no matter how stale it looks; the same bead
# is treated as ordinary drift (cleared, Mayor paged) once that session is
# gone.
#
# Also regression for the empty-heartbeat bug (2026-09-29): `date -d ""`
# turned a missing heartbeat into midnight UTC today, so a drift was invisible
# 00:00-00:15 UTC and this very test failed daily 00:00-00:30 UTC. The clock
# is now pinned (FACTORY_DISPATCH_NOW_EPOCH) to 00:05 UTC -- inside the old
# blind window -- so the test is time-of-day independent AND proves: a
# missing, empty or unparseable heartbeat falls back to updated_at; a bead
# with no parseable timestamp at all is stale with an "unknown" age.
#
# All bead ids here are synthetic fixtures (zz-fixture*), never a real af-*
# id from the live store.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/factory-dispatch-guard"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

export BEADS_FILE="$TMP/routed_beads.json"
export SESSIONS_FILE="$TMP/sessions.json"; echo '{"sessions":[]}' > "$SESSIONS_FILE"
export UPDATE_LOG="$TMP/updates.log"; : > "$UPDATE_LOG"
export MAIL_LOG="$TMP/mail.log"; : > "$MAIL_LOG"
mkdir -p "$TMP/bin"

# --- stub gc: serves `bd list` and `session list` from BEADS_FILE /
# SESSIONS_FILE, records `bd update` and `mail send` calls --------------
cat > "$TMP/bin/gc" <<'STUB'
#!/usr/bin/env bash
set -Eeuo pipefail
# The guard pins --city "$ROOT" ahead of the subcommand (a scratch/test root
# with no discoverable rig has been observed to fall back to the live
# production store otherwise); strip it before matching.
if [[ ${1:-} == --city ]]; then shift 2; fi
if [[ ${1:-} == bd && ${2:-} == list ]]; then
  cat "$BEADS_FILE"
  exit 0
fi
if [[ ${1:-} == session && ${2:-} == list ]]; then
  cat "$SESSIONS_FILE"
  exit 0
fi
if [[ ${1:-} == bd && ${2:-} == update ]]; then
  id=$3
  shift 3
  printf '%s %s\n' "$id" "$*" >> "$UPDATE_LOG"
  exit 0
fi
if [[ ${1:-} == mail && ${2:-} == send ]]; then
  printf 'mail-to=%s\n' "$3" >> "$MAIL_LOG"
  exit 0
fi
exit 64
STUB
chmod +x "$TMP/bin/gc"
# `bd` itself is only require_command-checked, never invoked directly by the
# guard (it always calls through `$GC_BIN bd ...`); a no-op stub is enough.
cat > "$TMP/bin/bd" <<'STUB'
#!/usr/bin/env bash
exit 0
STUB
chmod +x "$TMP/bin/bd"

export PATH="$TMP/bin:$PATH"
# Every Gas City agent session (this one included) has GC_BIN pre-exported
# to the real `gc` binary, which silently outranks a PATH-only stub --
# override it explicitly, the same belt-and-braces pattern
# tests/factory-queue-guard-test.sh and tests/factory-delivery-guard-test.sh
# already use (af-ylndd/af-txnw2).
export GC_BIN="$TMP/bin/gc"
export BD_BIN="$TMP/bin/bd"
touch "$TMP/city.toml"

# Fixed clock at 00:05 UTC: inside the window the empty-heartbeat bug hid.
export FACTORY_DISPATCH_NOW_EPOCH=$(date -u -d '2026-09-29T00:05:00Z' +%s)
STALE='2026-09-28T23:35:00Z'   # 30 minutes before the pinned clock
FRESH='2026-09-29T00:03:00Z'   # 2 minutes before the pinned clock

guard() { FACTORY_ROOT="$TMP" "$GUARD" "$@" 2>&1 || true; }
update_count() { grep -c "^$1 " "$UPDATE_LOG" 2>/dev/null || true; }
mail_count() { grep -c "^mail-to=$1$" "$MAIL_LOG" 2>/dev/null || true; }

matched_target='{
  "id": "zz-fixture-matched", "status": "in_progress", "title": "Routed and claimed",
  "assignee": "bd.dog", "updated_at": "'"$STALE"'",
  "metadata": {"gc.routed_to": "bd.dog"}
}'
fresh_drift='{
  "id": "zz-fixture-fresh", "status": "in_progress", "title": "Just slung, not claimed yet",
  "assignee": "mayor", "updated_at": "'"$FRESH"'",
  "metadata": {"gc.routed_to": "bd.dog"}
}'
stale_drift='{
  "id": "zz-fixture-stale", "status": "in_progress", "title": "Dolt cleanup",
  "assignee": "mayor", "updated_at": "'"$STALE"'",
  "metadata": {"gc.routed_to": "bd.dog"}
}'
no_assignee='{
  "id": "zz-fixture-unclaimed", "status": "open", "title": "Routed, never claimed",
  "assignee": "", "updated_at": "'"$STALE"'",
  "metadata": {"gc.routed_to": "bd.dog"}
}'

# 1. matched assignee/target and a fresh drift within the grace window: left
#    alone, reported healthy --------------------------------------------------
jq -n --argjson a "$matched_target" --argjson b "$fresh_drift" --argjson c "$no_assignee" \
  '[$a, $b, $c]' > "$BEADS_FILE"
out=$(guard --check-only)
grep -q "healthy — 3 routed bead(s) checked, no stale dispatch drift" <<<"$out" \
  || { echo "$out" >&2; fail "matched/fresh/unclaimed beads were not reported healthy"; }
[ "$(update_count zz-fixture-matched)" = "0" ] || fail "touched a bead whose assignee already matches its target"
[ "$(update_count zz-fixture-fresh)" = "0" ] || fail "touched a bead still inside the grace window"
[ "$(update_count zz-fixture-unclaimed)" = "0" ] || fail "touched a bead with no assignee at all"
[ "$(mail_count mayor)" = "0" ] || fail "paged the Mayor with nothing wrong"

# 2. genuinely stale drift: --check-only reports it, writes and pages nothing
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
jq -n --argjson d "$stale_drift" '[$d]' > "$BEADS_FILE"
out=$(guard --check-only)
grep -q "zz-fixture-stale routed to 'bd.dog' but assignee is still 'mayor'" <<<"$out" \
  || { echo "$out" >&2; fail "stale drift was not reported under --check-only"; }
[ "$(update_count zz-fixture-stale)" = "0" ] || fail "--check-only wrote to Beads"
[ "$(mail_count mayor)" = "0" ] || fail "--check-only paged the Mayor"
grep -q "^UNRESOLVED" <<<"$out" || fail "a real stale drift under --check-only must not read as healthy"

# 3. genuinely stale drift: default run clears the assignee and pages the
#    Mayor exactly once -------------------------------------------------------
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
out=$(guard)
grep -q "cleared stale assignee 'mayor' (routed to 'bd.dog', stale 30m) and paged the Mayor" <<<"$out" \
  || { echo "$out" >&2; fail "stale drift was not repaired and reported"; }
call=$(grep "^zz-fixture-stale " "$UPDATE_LOG" || true)
[[ $call == *'--assignee '* ]] || fail "repair call did not clear the assignee: $call"
[[ $call == *"--append-notes"* ]] || fail "repair call left no note: $call"
[ "$(mail_count mayor)" = "1" ] || fail "expected exactly one page to the Mayor"

# 4. session_affinity=require, assignee is a still-alive session: left alone
#    however stale it looks (af-7qxzh) -------------------------------------
affinity_alive='{
  "id": "zz-fixture-affinity-alive", "status": "in_progress", "title": "Later step, owning session mid-workflow",
  "assignee": "claude-af-c9a25", "updated_at": "'"$STALE"'",
  "metadata": {"gc.routed_to": "claude", "gc.session_affinity": "require"}
}'
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
echo '{"sessions":[{"session_name":"claude-af-c9a25","closed":false}]}' > "$SESSIONS_FILE"
jq -n --argjson e "$affinity_alive" '[$e]' > "$BEADS_FILE"
out=$(guard --check-only)
grep -q "healthy — 1 routed bead(s) checked, no stale dispatch drift" <<<"$out" \
  || { echo "$out" >&2; fail "session_affinity=require bead with a live session was not left alone"; }
[ "$(update_count zz-fixture-affinity-alive)" = "0" ] || fail "touched a session_affinity=require bead whose session is still alive"
[ "$(mail_count mayor)" = "0" ] || fail "paged the Mayor over a live session-affinity step"

# 5. session_affinity=require, assignee's session is gone: ordinary drift
#    handling applies (cleared, Mayor paged) -------------------------------
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
echo '{"sessions":[]}' > "$SESSIONS_FILE"
out=$(guard)
grep -q "cleared stale assignee 'claude-af-c9a25' (routed to 'claude', stale 30m) and paged the Mayor" <<<"$out" \
  || { echo "$out" >&2; fail "session_affinity=require bead with a gone session was not repaired"; }
call=$(grep "^zz-fixture-affinity-alive " "$UPDATE_LOG" || true)
[[ $call == *'--assignee '* ]] || fail "repair call did not clear the assignee: $call"
[ "$(mail_count mayor)" = "1" ] || fail "expected exactly one page to the Mayor once the owning session is gone"

# 6. empty-heartbeat regression: no heartbeat key, an empty one and an
#    unparseable one all fall back to updated_at (30m stale, at 00:05 UTC);
#    a bead with no parseable timestamp at all is stale, age "unknown" ------
hb_missing='{
  "id": "zz-fixture-hb-missing", "status": "in_progress", "title": "No heartbeat key",
  "assignee": "mayor", "updated_at": "'"$STALE"'",
  "metadata": {"gc.routed_to": "bd.dog"}
}'
hb_empty='{
  "id": "zz-fixture-hb-empty", "status": "in_progress", "title": "Empty heartbeat",
  "assignee": "mayor", "updated_at": "'"$STALE"'",
  "metadata": {"gc.routed_to": "bd.dog", "gc.last_heartbeat_at": ""}
}'
hb_garbage='{
  "id": "zz-fixture-hb-garbage", "status": "in_progress", "title": "Unparseable heartbeat",
  "assignee": "mayor", "updated_at": "'"$STALE"'",
  "metadata": {"gc.routed_to": "bd.dog", "gc.last_heartbeat_at": "not-a-time"}
}'
no_time='{
  "id": "zz-fixture-no-time", "status": "in_progress", "title": "No timestamp at all",
  "assignee": "mayor", "updated_at": "",
  "metadata": {"gc.routed_to": "bd.dog"}
}'
hb_fresh='{
  "id": "zz-fixture-hb-fresh", "status": "in_progress", "title": "Old update, fresh heartbeat",
  "assignee": "mayor", "updated_at": "'"$STALE"'",
  "metadata": {"gc.routed_to": "bd.dog", "gc.last_heartbeat_at": "'"$FRESH"'"}
}'
: > "$UPDATE_LOG"; : > "$MAIL_LOG"
echo '{"sessions":[]}' > "$SESSIONS_FILE"
jq -n --argjson a "$hb_missing" --argjson b "$hb_empty" --argjson c "$hb_garbage" \
  --argjson d "$no_time" --argjson e "$hb_fresh" '[$a, $b, $c, $d, $e]' > "$BEADS_FILE"
out=$(guard --check-only)
for id in zz-fixture-hb-missing zz-fixture-hb-empty zz-fixture-hb-garbage; do
  grep -q "$id routed to 'bd.dog' but assignee is still 'mayor' (stale 30m, threshold 15m)" <<<"$out" \
    || { echo "$out" >&2; fail "$id: a missing/empty/unparseable heartbeat did not fall back to updated_at (stale 30m at 00:05 UTC)"; }
done
grep -q "zz-fixture-no-time routed to 'bd.dog' but assignee is still 'mayor' (stale unknown age" <<<"$out" \
  || { echo "$out" >&2; fail "a bead with no parseable timestamp was not reported stale with an unknown age"; }
grep -q "zz-fixture-hb-fresh" <<<"$out" \
  && { echo "$out" >&2; fail "a bead with a fresh heartbeat was flagged"; }
[ -s "$UPDATE_LOG" ] && fail "--check-only wrote to Beads"

echo "PASS: factory-dispatch-guard clears stale dispatch-drift assignees, leaves matched/fresh/unclaimed beads alone, and respects session-affinity liveness"
