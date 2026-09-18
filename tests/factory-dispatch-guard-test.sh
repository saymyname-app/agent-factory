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
# All bead ids here are synthetic fixtures (zz-fixture*), never a real af-*
# id from the live store.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/factory-dispatch-guard"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

export BEADS_FILE="$TMP/routed_beads.json"
export UPDATE_LOG="$TMP/updates.log"; : > "$UPDATE_LOG"
export MAIL_LOG="$TMP/mail.log"; : > "$MAIL_LOG"
mkdir -p "$TMP/bin"

# --- stub gc: serves `bd list` from BEADS_FILE, records `bd update` and
# `mail send` calls ------------------------------------------------------
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

NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
STALE=$(date -u -d '-30 minutes' +%Y-%m-%dT%H:%M:%SZ)
FRESH=$(date -u -d '-2 minutes' +%Y-%m-%dT%H:%M:%SZ)

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

echo "PASS: factory-dispatch-guard clears stale dispatch-drift assignees and leaves matched/fresh/unclaimed beads alone"
