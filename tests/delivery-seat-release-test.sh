#!/usr/bin/env bash
#
# af-epkrcv: the one seat of a delivery verification role (reviewer,
# Evaluator) must not stay held by a session that has served its workflow
# while routed work of another workflow waits. Gas City keeps that warm seat
# for the waiting work and cancels its drain-ack; the role's work query
# offers it nothing (T42), so the seat sat idle until idle_timeout (2 h) and
# the waiting launches expired (17/10, af-wisp-clbc8c). bin/delivery-seat-release
# closes such a seat, and only such a seat. gc is a stub here.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
. "$ROOT/tests/lib/sandbox.sh"
sandbox_init
TMP="$SANDBOX_DIR"
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
SCRIPT="$ROOT/bin/delivery-seat-release"
[ -x "$SCRIPT" ] || fail "bin/delivery-seat-release is missing or not executable"

FIX="$TMP/fix"; mkdir -p "$FIX" "$TMP/bin"
CALLS="$TMP/calls.log"
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$CALLS"
args="\$*"
case "\$args" in
  "session list --json") cat "$FIX/sessions.json" ;;
  "session close "*) exit 0 ;;
  "bd list --all --assignee="*)
    who=\${args#bd list --all --assignee=}; who=\${who%% *}
    f="$FIX/served-\$who.json"; [ -f "\$f" ] && cat "\$f" || echo '[]' ;;
  "bd ready --metadata-field gc.routed_to="*)
    role=\${args#bd ready --metadata-field gc.routed_to=}; role=\${role%% *}
    f="$FIX/ready-\$role.json"; [ -f "\$f" ] && cat "\$f" || echo '[]' ;;
  *) echo "unexpected gc call: \$args" >&2; exit 3 ;;
esac
STUB
chmod +x "$TMP/bin/gc"
export GC_BIN="$TMP/bin/gc"
export DELIVERY_SEAT_RELEASE_LOG="$TMP/release.log"

session() { # id template
  jq -n --arg id "$1" --arg t "$2" '{id:$id, template:$t, state:"active", alias:$t, session_name:($t+"-"+$id)}'
}
bead() { # id status root
  jq -n --arg id "$1" --arg s "$2" --arg r "$3" '{id:$id, status:$s, metadata:{"gc.root_bead_id":$r}}'
}
reset() { : > "$CALLS"; rm -f "$FIX"/*.json "$DELIVERY_SEAT_RELEASE_LOG"; }
closed() { grep '^session close ' "$CALLS" | awk '{print $3}' | sort | tr '\n' ' ' | sed 's/ $//'; }

# 1. The 17/10 seat: served one review, holds nothing, a review of another
#    workflow waits -> closed and logged. A fresh reviewer seat (never served)
#    with the same waiting work, and seats of other templates, are left alone.
reset
jq -s '{sessions: .}' <(session s-served delivery-reviewer) <(session s-author delivery-author) <(session s-mayor mayor) > "$FIX/sessions.json"
jq -s . <(bead st-1 closed root-a) > "$FIX/served-s-served.json"
jq -s . <(bead st-1 closed root-a) > "$FIX/served-delivery-reviewer.json"
jq -s . <(bead st-2 open root-b) > "$FIX/ready-delivery-reviewer.json"
out=$("$SCRIPT" 2>&1) || fail "must exit 0, got: $out"
[ "$(closed)" = "s-served" ] || { cat "$CALLS" >&2; fail "must close exactly the served seat, closed: '$(closed)'"; }
grep -q "s-served" "$DELIVERY_SEAT_RELEASE_LOG" || fail "a close must be logged"
grep -q "st-2" "$DELIVERY_SEAT_RELEASE_LOG" || fail "the log must name the waiting work"

# 2. A seat that never served is the one Gas City started for the waiting
#    work: never closed, even with work waiting.
reset
jq -s '{sessions: .}' <(session s-fresh delivery-evaluator) > "$FIX/sessions.json"
jq -s . <(bead st-3 open root-c) > "$FIX/ready-delivery-evaluator.json"
"$SCRIPT" >/dev/null 2>&1 || fail "must exit 0 on a fresh seat"
[ -z "$(closed)" ] || fail "a seat that never served must not be closed"

# 3. A served seat still holding a bead in progress is working: kept.
reset
jq -s '{sessions: .}' <(session s-busy delivery-reviewer) > "$FIX/sessions.json"
jq -s . <(bead st-4 closed root-a) <(bead st-5 in_progress root-d) > "$FIX/served-s-busy.json"
jq -s . <(bead st-6 open root-b) > "$FIX/ready-delivery-reviewer.json"
"$SCRIPT" >/dev/null 2>&1 || fail "must exit 0 on a busy seat"
[ -z "$(closed)" ] || fail "a seat with a bead in progress must not be closed"

# 4. Waiting work of the seat's own workflow is offered to it by its work
#    query: kept. No waiting work at all: Gas City honours the drain-ack itself.
reset
jq -s '{sessions: .}' <(session s-own delivery-reviewer) > "$FIX/sessions.json"
jq -s . <(bead st-7 closed root-a) > "$FIX/served-s-own.json"
jq -s . <(bead st-8 open root-a) > "$FIX/ready-delivery-reviewer.json"
"$SCRIPT" >/dev/null 2>&1 || fail "must exit 0"
[ -z "$(closed)" ] || fail "a seat whose own workflow has ready work must not be closed"
rm -f "$FIX/ready-delivery-reviewer.json"; : > "$CALLS"
"$SCRIPT" >/dev/null 2>&1 || fail "must exit 0"
[ -z "$(closed)" ] || fail "a seat with no waiting work is left to Gas City's drain-ack"

# 4b. Ready work of its own workflow and of another one at once: the work
#     query still offers it its own, so it is kept.
reset
jq -s '{sessions: .}' <(session s-both delivery-reviewer) > "$FIX/sessions.json"
jq -s . <(bead st-9 closed root-a) > "$FIX/served-s-both.json"
jq -s . <(bead st-10 open root-b) <(bead st-11 open root-a) > "$FIX/ready-delivery-reviewer.json"
"$SCRIPT" >/dev/null 2>&1 || fail "must exit 0"
[ -z "$(closed)" ] || fail "a seat with ready work of its own workflow must not be closed, even when other work waits"

# 4c. A bead assigned to it and still open (ready for it, not yet claimed)
#     is work it holds: kept.
reset
jq -s '{sessions: .}' <(session s-assigned delivery-evaluator) > "$FIX/sessions.json"
jq -s . <(bead st-12 closed root-a) <(bead st-13 open root-e) > "$FIX/served-s-assigned.json"
jq -s . <(bead st-14 open root-b) > "$FIX/ready-delivery-evaluator.json"
"$SCRIPT" >/dev/null 2>&1 || fail "must exit 0"
[ -z "$(closed)" ] || fail "a seat with an assigned open bead must not be closed"

# 5. --check-only names the seat and closes nothing; an unreadable session
#    list or tracker closes nothing and exits 1.
reset
jq -s '{sessions: .}' <(session s-served delivery-reviewer) > "$FIX/sessions.json"
jq -s . <(bead st-1 closed root-a) > "$FIX/served-s-served.json"
jq -s . <(bead st-2 open root-b) > "$FIX/ready-delivery-reviewer.json"
out=$("$SCRIPT" --check-only 2>&1) || fail "--check-only must exit 0"
grep -q "s-served" <<<"$out" || fail "--check-only must name the seat: $out"
[ -z "$(closed)" ] || fail "--check-only must close nothing"
echo 'not json' > "$FIX/served-s-served.json"; : > "$CALLS"
if "$SCRIPT" >/dev/null 2>&1; then fail "an unreadable tracker answer must exit 1"; fi
[ -z "$(closed)" ] || fail "an unreadable tracker answer must close nothing"

printf 'PASS: delivery-seat-release frees a served, idle verification seat for waiting work, and nothing else\n'
