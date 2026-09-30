#!/usr/bin/env bash
#
# T08 (af-v7skkf): a worker with no ticket in hand, facing a suspended city,
# must end its session instead of looping on CLAIM_REJECTED. A worker that
# already has a ticket in progress (an `existing_assignment` claim) must
# finish it regardless of suspension. Outside suspension, a claim rejection
# must still retry exactly as before.
#
# This drives the ACTUAL Startup Claim Protocol script embedded in
# agents/factory-worker/prompt.template.md -- extracted verbatim, so a future
# edit to that script is exercised by this test without any duplication. gc
# is a stub on PATH here; the claim script must never reach a live city.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
PROMPT="$REPO_ROOT/agents/factory-worker/prompt.template.md"
. "$REPO_ROOT/tests/lib/sandbox.sh"
sandbox_init
TMP="$SANDBOX_DIR"
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

# Extract the claim script verbatim: from the `bash <<'GC_CLAIM'` line to its
# closing `GC_CLAIM` delimiter (inclusive), so running it re-enacts exactly
# what a session pastes as its first command.
START=$(grep -n "^bash <<'GC_CLAIM'$" "$PROMPT" | head -1 | cut -d: -f1)
[ -n "$START" ] || fail "could not find the GC_CLAIM heredoc start in $PROMPT"
END=$(awk -v s="$START" 'NR > s && /^GC_CLAIM$/ { print NR; exit }' "$PROMPT")
[ -n "$END" ] || fail "could not find the GC_CLAIM heredoc end in $PROMPT"
CLAIM_SCRIPT="$TMP/claim.sh"
sed -n "${START},${END}p" "$PROMPT" > "$CLAIM_SCRIPT"
grep -q "CITY_SUSPENDED" "$CLAIM_SCRIPT" || fail "extracted claim script is missing the CITY_SUSPENDED branch -- extraction range is wrong"

mkdir -p "$TMP/bin"
CALLS="$TMP/calls.log"
DRAIN_ACK="$TMP/drain-ack.log"

# fast, deterministic retries -- the real script sleeps 2s between attempts
cat > "$TMP/bin/sleep" <<'STUB'
#!/usr/bin/env bash
exit 0
STUB
chmod +x "$TMP/bin/sleep"

write_gc_stub() {
  # write_gc_stub <suspended: true|false> <attempts before a claim succeeds>
  # `gc hook --claim` fails (exit 1, no stdout) until the call count exceeds
  # <attempts>, then returns the contents of $TMP/hook-success.json.
  local suspended="$1" attempts_before_success="$2"
  cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$CALLS"
case "\$1 \$2" in
  "hook --claim")
    n=\$(grep -c '^hook --claim' "$CALLS" || true)
    if [ "\$n" -gt "$attempts_before_success" ]; then
      cat "$TMP/hook-success.json"
      exit 0
    fi
    echo "no routed work (stub)" >&2
    exit 1
    ;;
  "status --json")
    printf '{"suspended": %s}\n' "$suspended"
    exit 0
    ;;
  "runtime drain-ack")
    echo 1 >> "$DRAIN_ACK"
    exit 0
    ;;
esac
exit 0
STUB
  chmod +x "$TMP/bin/gc"
}

write_bd_stub() {
  # write_bd_stub <bead-json-file>
  local bead_json="$1"
  cat > "$TMP/bin/bd" <<STUB
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$CALLS"
case "\$1" in
  show)
    cat "$bead_json"
    exit 0
    ;;
esac
exit 0
STUB
  chmod +x "$TMP/bin/bd"
}

export PATH="$TMP/bin:$PATH"
export GC_BIN="$TMP/bin/gc"
export BD_BIN="$TMP/bin/bd"
export GC_SESSION_NAME="factory-worker-af-test"
export GC_TEMPLATE="factory-worker"
# BEADS_ACTOR is set in a live factory-worker session's own environment and
# is not one of the vars tests/lib/sandbox.sh scrubs; it would otherwise leak
# through and outrank GC_SESSION_NAME as EXPECTED_ASSIGNEE in the claim
# script, breaking assignee verification against this test's fixtures.
unset BEADS_ACTOR

reset() { : > "$CALLS"; : > "$DRAIN_ACK"; }
hook_calls() { grep -c '^hook --claim' "$CALLS" || true; }
status_calls() { grep -c '^status --json' "$CALLS" || true; }
drain_acks() { wc -l < "$DRAIN_ACK" 2>/dev/null | tr -d ' ' || echo 0; }

# 1. No ticket in hand, city suspended: one rejected claim, then stop. ------
echo '{}' > "$TMP/hook-success.json"   # unreachable in this scenario
write_gc_stub true 999                 # suspended=true; claim never succeeds
write_bd_stub "$TMP/bd-unused.json"
reset
out=$(bash "$CLAIM_SCRIPT" 2>&1) || fail "claim script must exit 0 on CITY_SUSPENDED, got: $out"
grep -q "CITY_SUSPENDED" <<<"$out" || { echo "$out" >&2; fail "suspended+no-ticket must print CITY_SUSPENDED"; }
[ "$(hook_calls)" = "1" ] || fail "must not retry gc hook --claim after learning the city is suspended (got $(hook_calls) calls)"
[ "$(drain_acks)" = "1" ] || fail "must drain-ack exactly once before stopping"

# 2. Ticket already in progress (existing_assignment): finish it regardless
#    of suspension -- claim succeeds immediately, suspension is never
#    consulted. ----------------------------------------------------------
jq -n --arg assignee "$GC_SESSION_NAME" --arg route "$GC_TEMPLATE" \
  '{schema_version:"1", ok:true, command:"hook", action:"work", reason:"existing_assignment", bead_id:"af-inprogress", assignee:$assignee, route:$route}' \
  > "$TMP/hook-success.json"
jq -n --arg assignee "$GC_SESSION_NAME" --arg route "$GC_TEMPLATE" \
  '[{id:"af-inprogress", status:"in_progress", assignee:$assignee, metadata:{"gc.routed_to":$route}}]' \
  > "$TMP/bead.json"
write_gc_stub true 0   # suspended=true, but the FIRST attempt already succeeds
write_bd_stub "$TMP/bead.json"
reset
out=$(bash "$CLAIM_SCRIPT" 2>&1) || fail "claim script must exit 0 when a ticket is already assigned, got: $out"
grep -q "^CLAIMED_BEAD_ID=af-inprogress$" <<<"$out" || { echo "$out" >&2; fail "must hand back the existing in-progress ticket"; }
[ "$(hook_calls)" = "1" ] || fail "an existing assignment must claim on the first attempt"
[ "$(status_calls)" = "0" ] || fail "suspension must never be consulted when a claim succeeds (an in-progress ticket finishes regardless)"
[ "$(drain_acks)" = "0" ] || fail "must not drain-ack when handing back real work"

# 3. Not suspended: a rejected claim still retries exactly as before, and
#    succeeds once real work appears. ------------------------------------
jq -n --arg assignee "$GC_SESSION_NAME" --arg route "$GC_TEMPLATE" \
  '{schema_version:"1", ok:true, command:"hook", action:"work", reason:"claimed", bead_id:"af-fresh", assignee:$assignee, route:$route}' \
  > "$TMP/hook-success.json"
jq -n --arg assignee "$GC_SESSION_NAME" --arg route "$GC_TEMPLATE" \
  '[{id:"af-fresh", status:"open", assignee:$assignee, metadata:{"gc.routed_to":$route}}]' \
  > "$TMP/bead.json"
write_gc_stub false 2   # not suspended; succeeds on the 3rd attempt
write_bd_stub "$TMP/bead.json"
reset
out=$(bash "$CLAIM_SCRIPT" 2>&1) || fail "claim script must eventually succeed once work appears, got: $out"
grep -q "^CLAIMED_BEAD_ID=af-fresh$" <<<"$out" || { echo "$out" >&2; fail "must claim the bead once the race resolves"; }
[ "$(hook_calls)" = "3" ] || fail "outside suspension a rejected claim must keep retrying (expected 3 attempts, got $(hook_calls))"
[ "$(drain_acks)" = "0" ] || fail "must not drain-ack once real work is claimed"

printf 'PASS: factory-worker claim script stops on CITY_SUSPENDED with no ticket in hand, finishes an in-progress ticket regardless of suspension, and retries as before outside suspension\n'
