#!/usr/bin/env bash
#
# factory-session-loop-guard must page and pause any session that wakes and
# stops more than 10 times in a rolling hour, whatever the cause (P14,
# af-llc2y; af-6675l safety net). 11 cycles trigger one alert and one pause;
# 10 do not. The pause must be reversible by a named, logged gesture
# ("resume"). gc and gh are stubs on PATH here; the guard must never reach a
# live store from a test.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/factory-session-loop-guard"
# See tests/factory-watchdog-test.sh (af-0h4vnc): a PATH-only stub is not
# enough -- bin/escalation-door resolves ${GC_BIN:-gc} directly, so GC_BIN
# must be repointed at this test's own scripted stub too.
. "$REPO_ROOT/tests/lib/sandbox.sh"
sandbox_init
TMP="$SANDBOX_DIR"
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

NOW=1789555200   # 2026-09-16T10:40:00Z
iso() { date -u -d "@$1" +%Y-%m-%dT%H:%M:%SZ; }

mkdir -p "$TMP/city/.gc" "$TMP/bin" "$TMP/city/var"
printf '[workspace]\nprovider = "claude"\n' > "$TMP/city/city.toml"

EVENTS="$TMP/events.jsonl"; : > "$EVENTS"
BEADS_DIR="$TMP/beads"; mkdir -p "$BEADS_DIR"
CALLS="$TMP/calls.log"; : > "$CALLS"
MAIL="$TMP/mail.log"; : > "$MAIL"
SUSPENDS="$TMP/suspends.log"; : > "$SUSPENDS"
WAKES="$TMP/wakes.log"; : > "$WAKES"

# Emit N wake/stop cycles for a session, spaced 5 minutes apart, ending
# `end_ago` seconds before NOW.
emit_cycles() {
  local session="$1" count="$2" end_ago="$3" i t
  : > "$EVENTS"
  for ((i = 0; i < count; i++)); do
    t=$((NOW - end_ago - (count - i) * 300))
    printf '{"type":"session.woke","session_id":"%s","subject":"factory-worker","ts":"%s"}\n' "$session" "$(iso "$t")" >> "$EVENTS"
    printf '{"type":"session.stopped","session_id":"%s","subject":"factory-worker","ts":"%s"}\n' "$session" "$(iso $((t + 30)))" >> "$EVENTS"
  done
}

cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$CALLS"
case "\$1 \$2" in
  "events --since")
    cat "$EVENTS"; exit 0 ;;
  "session suspend")
    printf '%s\n' "\$3" >> "$SUSPENDS"; exit 0 ;;
  "session wake")
    printf '%s\n' "\$3" >> "$WAKES"; exit 0 ;;
  "bd list")
    if [[ "\$*" == *"--title-contains"* ]]; then
      needle=""
      argv=("\$@")
      for ((i=0; i<\${#argv[@]}; i++)); do
        [[ "\${argv[i]}" == "--title-contains" ]] && needle="\${argv[i+1]}"
      done
      for f in "$BEADS_DIR"/*.json; do
        [[ -f "\$f" ]] || continue
        if [[ -z "\$needle" ]] || jq -e --arg n "\$needle" '(.[0].title // "") | contains(\$n)' "\$f" >/dev/null 2>&1; then
          cat "\$f"
        fi
      done | jq -s 'add // []'
      exit 0
    fi
    echo '[]'; exit 0 ;;
  "bd show")
    id="\$3"
    f="$BEADS_DIR/\$id.json"
    if [[ -f "\$f" ]]; then cat "\$f"; else echo '[{"id":"'"\$id"'","status":"open","metadata":{}}]'; fi
    exit 0 ;;
  "bd create")
    id="af-new\$RANDOM"
    title="\$3"
    printf '%s' "\$title" | jq -R --arg id "\$id" '[{"id":\$id,"status":"open","title":.,"metadata":{}}]' > "$BEADS_DIR/\$id.json"
    printf '{"id":"%s"}' "\$id"
    exit 0 ;;
  "bd update")
    id="\$3"
    f="$BEADS_DIR/\$id.json"
    [[ -f "\$f" ]] || echo '[{"id":"'"\$id"'","status":"open","metadata":{}}]' > "\$f"
    shift 3
    while [[ \$# -gt 0 ]]; do
      case "\$1" in
        --set-metadata)
          pair="\$2"; key="\${pair%%=*}"; value="\${pair#*=}"
          jq --arg k "\$key" --arg v "\$value" '(.[0].metadata // {}) as \$m | .[0].metadata = (\$m + {(\$k):\$v})' "\$f" > "\$f.next"
          mv "\$f.next" "\$f"
          shift 2 ;;
        --status=closed)
          jq '.[0].status = "closed"' "\$f" > "\$f.next"; mv "\$f.next" "\$f"
          shift ;;
        *) shift ;;
      esac
    done
    exit 0 ;;
  "mail send")
    printf '%s\n' "\$*" >> "$MAIL"
    exit 0 ;;
esac
exit 0
STUB
chmod +x "$TMP/bin/gc"

export PATH="$TMP/bin:$PATH"
export GC_BIN="$TMP/bin/gc"
export FACTORY_SESSION_LOOP_GUARD_LOG="$TMP/city/var/factory-session-loop-guard.log"
export FACTORY_SESSION_LOOP_GUARD_NOW=$NOW

guard() { FACTORY_ROOT="$TMP/city" "$GUARD" "$@" 2>&1 || true; }
resume() { FACTORY_ROOT="$TMP/city" GC_BIN="$TMP/bin/gc" "$GUARD" resume "$@" 2>&1 || true; }
mails()    { grep -c '^mail send' "$MAIL" || true; }
creates()  { grep -c '^bd create' "$CALLS" || true; }
suspends() { wc -l < "$SUSPENDS" | tr -d ' '; }
wakes()    { wc -l < "$WAKES" | tr -d ' '; }
reset_logs() { : > "$CALLS"; : > "$MAIL"; : > "$SUSPENDS"; : > "$WAKES"; }

# 1. 10 cycles in the hour must NOT trigger anything -------------------------
emit_cycles "af-quiet10" 10 60
reset_logs
out=$(guard)
grep -q "quiet — no session over 10 wake/stop cycles" <<<"$out" || { echo "$out" >&2; fail "10 cycles must read as quiet"; }
[ "$(mails)" = "0" ] || fail "10 cycles must not page"
[ "$(suspends)" = "0" ] || fail "10 cycles must not suspend"

# 2. 11 cycles in the hour trigger exactly one alert and one pause -----------
emit_cycles "af-loopy" 11 60
reset_logs
out=$(guard)
grep -q "wake/stop loop — session af-loopy woke and stopped 11 times" <<<"$out" || { echo "$out" >&2; fail "11 cycles not reported"; }
[ "$(creates)" = "1" ] || fail "a looping session should be filed exactly once"
[ "$(mails)" = "1" ] || fail "a looping session should be paged exactly once"
[ "$(suspends)" = "1" ] || fail "a looping session should be suspended exactly once"
grep -q "^af-loopy$" "$SUSPENDS" || fail "the looping session id was not the one suspended"
grep -q "^mail send mayor" "$MAIL" || { cat "$MAIL" >&2; fail "did not route through escalation-door's mayor-first class"; }
[ -f "$FACTORY_SESSION_LOOP_GUARD_LOG" ] || fail "no gesture log was written"
grep -q "gesture=pause" "$FACTORY_SESSION_LOOP_GUARD_LOG" || fail "the pause gesture was not logged"
grep -q "session=af-loopy" "$FACTORY_SESSION_LOOP_GUARD_LOG" || fail "the pause log did not name the session"

# ...re-run while still looping must not duplicate the bead, page, or re-suspend.
reset_logs
out=$(guard)
grep -q "wake/stop loop — session af-loopy" <<<"$out" || fail "the loop should still be reported while active"
[ "$(creates)" = "0" ] || fail "a looping-session bead must not be filed twice"
[ "$(mails)" = "0" ] || fail "an immediate re-run must not re-page"
[ "$(suspends)" = "0" ] || fail "an immediate re-run must not re-suspend"

# 3. --check-only reports but mutates nothing --------------------------------
emit_cycles "af-checkonly" 11 60
reset_logs
out=$(guard --check-only)
grep -q "wake/stop loop — session af-checkonly" <<<"$out" || fail "--check-only should still report the finding"
[ "$(mails)" = "0" ] || fail "--check-only must never page"
[ "$(suspends)" = "0" ] || fail "--check-only must never suspend"
grep -q '^bd create' "$CALLS" && fail "--check-only must never file a bead"

# 4. the pause is reversible by a named, logged Mayor gesture ---------------
reset_logs
out=$(resume af-loopy --reason "cause fixed by P13")
grep -q "^af-loopy$" "$WAKES" || { echo "$out" >&2; fail "resume did not call gc session wake on the right session"; }
grep -q "gesture=resume" "$FACTORY_SESSION_LOOP_GUARD_LOG" || fail "the resume gesture was not logged"
grep -q "status=resumed" "$FACTORY_SESSION_LOOP_GUARD_LOG" || fail "the resume gesture did not log a resumed status"
grep -q "reason=cause fixed by P13" "$FACTORY_SESSION_LOOP_GUARD_LOG" || fail "the resume reason was not logged"
bead_file=""
for f in "$BEADS_DIR"/*.json; do
  [ -f "$f" ] || continue
  if jq -e '.[0].title == "[session-loop] af-loopy"' "$f" >/dev/null 2>&1; then bead_file="$f"; break; fi
done
[ -n "$bead_file" ] || fail "could not find the tracking bead for af-loopy"
jq -e '.[0].status == "closed"' "$bead_file" >/dev/null || fail "resume must close the tracking bead"

# ...resuming an unknown/untracked session still calls gc session wake and logs.
reset_logs
out=$(resume af-untracked)
grep -q "^af-untracked$" "$WAKES" || fail "resume must work even with no tracking bead on file"
grep -q "gesture=resume" "$FACTORY_SESSION_LOOP_GUARD_LOG" || fail "resume must log even with no tracking bead"

# 5. a session that stops looping has its bead auto-resolved -----------------
emit_cycles "af-recovered" 11 60
reset_logs
guard >/dev/null
: > "$EVENTS"   # no more events at all -- the session is quiet now
reset_logs
out=$(guard)
grep -q "wake/stop loop — session af-recovered" <<<"$out" && fail "a recovered session must not still be reported as looping"
grep -q -- '--status=closed' "$CALLS" || fail "a recovered session's bead should be auto-resolved"

# 6. exit-code contract: a finding is not a failure; only guard-cannot-run is
emit_cycles "af-loopy2" 11 60
reset_logs
set +e
FACTORY_ROOT="$TMP/city" "$GUARD" >/dev/null 2>&1
rc=$?
set -e
[ "$rc" = "0" ] || fail "exit code must be 0 when the guard ran and merely found a loop (was $rc)"

set +e
FACTORY_ROOT="$TMP/does-not-exist" "$GUARD" >/dev/null 2>&1
rc=$?
set -e
[ "$rc" != "0" ] || fail "exit code must be nonzero when the guard itself could not run (unreachable root)"

printf 'PASS: factory-session-loop-guard pages and pauses an 11-cycle wake/stop loop, ignores 10, auto-resolves recovery, and the pause is reversible via the logged resume gesture\n'
