#!/usr/bin/env bash
#
# af-3ewcxf: bin/mayor-context-guard rotates the Mayor's provider conversation
# once it carries more than 150k context tokens or is older than 8h, with a
# handoff mail first and `gc session reset mayor` (fresh conversation, same
# bead/alias/mail). It must act once per conversation, wait while the Mayor
# is mid-turn, and never touch another session. gc is a stub on PATH.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/mayor-context-guard"
. "$REPO_ROOT/tests/lib/sandbox.sh"
sandbox_init
TMP="$SANDBOX_DIR"
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

NOW=1789555200   # 2026-09-16T10:40:00Z
iso() { date -u -d "@$1" +%Y-%m-%dT%H:%M:%SZ; }

mkdir -p "$TMP/city/.gc/runtime" "$TMP/city/var" "$TMP/bin" "$TMP/transcripts"
printf '[workspace]\nprovider = "claude"\n' > "$TMP/city/city.toml"
CALLS="$TMP/calls.log"; : > "$CALLS"
KEY_FILE="$TMP/mayor-key"
ATTACHED_FILE="$TMP/mayor-attached"; printf 'false' > "$ATTACHED_FILE"
RESET_RC_FILE="$TMP/reset-rc"; printf '0' > "$RESET_RC_FILE"

cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$CALLS"
if [ "\$1 \$2" = "session list" ]; then
  jq -n --arg k "\$(cat "$KEY_FILE")" --argjson a "\$(cat "$ATTACHED_FILE")" '{ok:true, sessions:[
    {id:"af-worker", alias:"factory-worker", name:"factory-worker", state:"active", session_key:"worker-key"},
    {id:"af-mayor", alias:"mayor", name:"mayor", state:"active", attached:\$a, session_key:\$k}]}'
fi
[ "\$1 \$2" = "session reset" ] && exit "\$(cat "$RESET_RC_FILE")"
exit 0
STUB
chmod +x "$TMP/bin/gc"

export GC_BIN="$TMP/bin/gc"
export MAYOR_CONTEXT_GUARD_TRANSCRIPTS="$TMP/transcripts"
export MAYOR_CONTEXT_GUARD_NOW=$NOW

# transcript <key> <context-tokens> <started-seconds-ago> <last stop_reason>
transcript() {
  local key="$1" tokens="$2" ago="$3" stop="$4"
  printf '%s' "$key" > "$KEY_FILE"
  {
    printf '{"type":"user","timestamp":"%s","message":{"role":"user","content":"hi"}}\n' "$(iso $((NOW - ago)))"
    printf '{"type":"assistant","timestamp":"%s","message":{"stop_reason":"%s","usage":{"input_tokens":2,"cache_creation_input_tokens":1000,"cache_read_input_tokens":%s}}}\n' \
      "$(iso $((NOW - 60)))" "$stop" "$((tokens - 1002))"
  } > "$TMP/transcripts/$key.jsonl"
}
# A worker transcript far over threshold: the guard must ignore it.
printf '{"type":"assistant","timestamp":"%s","message":{"stop_reason":"end_turn","usage":{"input_tokens":900000}}}\n' "$(iso $NOW)" > "$TMP/transcripts/worker-key.jsonl"

guard() { FACTORY_ROOT="$TMP/city" "$GUARD" "$@" 2>&1; }
mails()  { grep -c '^mail send mayor' "$CALLS" || true; }
resets() { grep -c '^session reset' "$CALLS" || true; }
field()  { jq -r ".$1" <<<"$2"; }

# 1. below both bounds -> no action ------------------------------------------
transcript conv-a 100000 3600 end_turn
: > "$CALLS"; out=$(guard)
[ "$(field action "$out")" = "none" ] || fail "below threshold must not act: $out"
[ "$(field tokens "$out")" = "100000" ] || fail "tokens must be input+cache_read+cache_creation: $out"
[ "$(mails)$(resets)" = "00" ] || fail "below threshold must not mail or reset"

# 2. --check above threshold reports the decision but changes nothing --------
transcript conv-b 160000 3600 end_turn
: > "$CALLS"; out=$(guard --check)
[ "$(field action "$out")" = "rotate" ] || fail "--check should report rotate: $out"
[ "$(mails)$(resets)" = "00" ] || fail "--check must never mail or reset"

# 3. mid-turn above threshold -> deferred, nothing done ---------------------
transcript conv-b 160000 3600 tool_use
: > "$CALLS"; out=$(guard)
[ "$(field action "$out")" = "deferred-busy" ] || fail "mid-turn Mayor must be deferred: $out"
[ "$(mails)$(resets)" = "00" ] || fail "mid-turn Mayor must not be rotated"

# 4. idle above threshold -> exactly one handoff mail and one reset ---------
transcript conv-b 160000 3600 end_turn
: > "$CALLS"; out=$(guard)
[ "$(field action "$out")" = "rotated" ] || fail "idle Mayor over threshold must be rotated: $out"
[ "$(field reason "$out")" = "tokens" ] || fail "reason should be tokens: $out"
[ "$(mails)" = "1" ] || { cat "$CALLS" >&2; fail "expected one handoff mail to mayor"; }
grep -q 'OPEN_MAIL' "$CALLS" || fail "handoff mail must carry the prompt's handoff fields"
[ "$(resets)" = "1" ] || fail "expected one session reset"
grep -q '^session reset mayor' "$CALLS" || fail "reset must target the mayor only"
grep -q 'worker' <(grep -E '^(session reset|session kill|mail send|handoff)' "$CALLS") && fail "another session was touched"
grep -q 'conv-b' "$TMP/city/var/mayor-context-guard.log" || fail "rotation must be logged"

# 5. same conversation again -> no second rotation -------------------------
: > "$CALLS"; out=$(guard)
[ "$(field action "$out")" = "already-rotated" ] || fail "same conversation must not rotate twice: $out"
[ "$(mails)$(resets)" = "00" ] || fail "second run must not mail or reset"

# 6. age bound: low tokens but conversation older than 8h -> rotated --------
transcript conv-c 20000 $((9 * 3600)) end_turn
: > "$CALLS"; out=$(guard)
[ "$(field action "$out")" = "rotated" ] || fail "conversation over 8h must rotate: $out"
[ "$(field reason "$out")" = "age" ] || fail "reason should be age: $out"
[ "$(resets)" = "1" ] || fail "age bound should reset once"

# 7. thresholds are configurable --------------------------------------------
transcript conv-d 100000 3600 end_turn
: > "$CALLS"; out=$(MAYOR_CONTEXT_GUARD_TOKENS=50000 guard --check)
[ "$(field action "$out")" = "rotate" ] || fail "MAYOR_CONTEXT_GUARD_TOKENS must lower the bound: $out"

# 8. no transcript -> quiet skip, exit 0 ------------------------------------
printf 'conv-missing' > "$KEY_FILE"
: > "$CALLS"; out=$(guard) || fail "a missing transcript must not fail the order"
[ "$(field action "$out")" = "skip" ] || fail "missing transcript should skip: $out"
[ "$(mails)$(resets)" = "00" ] || fail "skip must not act"

# 9. someone attached -> deferred, nothing done -----------------------------
transcript conv-e 160000 3600 end_turn
printf 'true' > "$ATTACHED_FILE"
: > "$CALLS"; out=$(guard)
[ "$(field action "$out")" = "deferred-attached" ] || fail "attached Mayor must be deferred: $out"
[ "$(mails)$(resets)" = "00" ] || fail "attached Mayor must not be rotated"
printf 'false' > "$ATTACHED_FILE"

# 10. failed reset -> exit 1, no mail, not recorded, retried next run -------
printf '1' > "$RESET_RC_FILE"
: > "$CALLS"; rc=0; out=$(guard) || rc=$?
[ "$rc" = "1" ] || fail "a failed reset must fail the order: rc=$rc $out"
[ "$(field action "$out")" = "reset-failed" ] || fail "expected reset-failed: $out"
[ "$(mails)" = "0" ] || fail "no handoff mail when the reset failed"
printf '0' > "$RESET_RC_FILE"
: > "$CALLS"; out=$(guard)
[ "$(field action "$out")" = "rotated" ] || fail "a failed reset must be retried: $out"

printf 'PASS: mayor-context-guard rotates the Mayor once per conversation above 150k tokens or 8h\n'
