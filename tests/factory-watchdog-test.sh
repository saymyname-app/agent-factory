#!/usr/bin/env bash
#
# factory-watchdog must page three gaps the campaign-liveness check does not
# cover (Incident 2026-09-16): an aged "Gate: human" issue, a Factory-repo PR
# that is CONFLICTING or never ran CI, and a molecule/workflow bead that
# closed CLOSED with a non-pass gc.outcome. It must also re-nudge about a
# still-open liveness defect. Every page is throttled (never every run) and
# --check-only must mutate nothing. gc and gh are stubs on PATH here; the
# watchdog must never reach a live store or GitHub from a test.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
WATCHDOG="$REPO_ROOT/bin/factory-watchdog"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

NOW=1789555200   # 2026-09-16T10:40:00Z
iso() { date -u -d "@$1" +%Y-%m-%dT%H:%M:%SZ; }

mkdir -p "$TMP/city/.gc" "$TMP/bin"
printf '[workspace]\nprovider = "claude"\n' > "$TMP/city/city.toml"

GATES="$TMP/gates.json";         printf '[]' > "$GATES"
PRS="$TMP/prs.json";             printf '[]' > "$PRS"
WORKFLOWS="$TMP/workflows.json"; printf '[]' > "$WORKFLOWS"
COORD="$TMP/coord.json";         printf '[{"id":"af-1vr4","metadata":{}}]' > "$COORD"
BEADS_DIR="$TMP/beads"; mkdir -p "$BEADS_DIR"
CALLS="$TMP/calls.log"; : > "$CALLS"
MAIL="$TMP/mail.log"; : > "$MAIL"

cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$CALLS"
case "\$1 \$2" in
  "bd gate")
    [[ "\$3" == list ]] && { cat "$GATES"; exit 0; }
    ;;
  "bd list")
    if [[ "\$*" == *"gc.kind=workflow"* ]]; then cat "$WORKFLOWS"; exit 0; fi
    if [[ "\$*" == *"--title-contains"* ]]; then
      for f in "$BEADS_DIR"/pr-open-*.json; do [[ -f "\$f" ]] && cat "\$f"; done | jq -s 'add // []'
      exit 0
    fi
    echo '[]'; exit 0 ;;
  "bd show")
    id="\$3"
    if [[ "\$id" == af-1vr4 ]]; then cat "$COORD"; exit 0; fi
    f="$BEADS_DIR/\$id.json"
    if [[ -f "\$f" ]]; then cat "\$f"; else echo '[]'; fi
    exit 0 ;;
  "bd create")
    id="af-new-\$RANDOM"
    printf '[{"id":"%s","status":"open","title":"unused"}]' "\$id" > "$BEADS_DIR/pr-open-\$id.json"
    printf '{"id":"%s"}' "\$id"
    exit 0 ;;
  "bd update")
    id="\$3"
    f="$BEADS_DIR/\$id.json"
    [[ "\$id" == af-1vr4 ]] && f="$COORD"
    if [[ ! -f "\$f" ]]; then echo '[{"id":"'"\$id"'","status":"open","metadata":{}}]' > "\$f"; fi
    shift 3
    while [[ \$# -gt 0 ]]; do
      if [[ "\$1" == "--set-metadata" ]]; then
        pair="\$2"; key="\${pair%%=*}"; value="\${pair#*=}"
        jq --arg k "\$key" --arg v "\$value" '(.[0].metadata // {}) as \$m | .[0].metadata = (\$m + {(\$k):\$v})' "\$f" > "\$f.next"
        mv "\$f.next" "\$f"
        shift 2
      else
        shift
      fi
    done
    exit 0 ;;
  "mail send")
    printf '%s\n' "\$*" >> "$MAIL"
    exit 0 ;;
esac
exit 0
STUB
chmod +x "$TMP/bin/gc"

cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$CALLS"
if [[ "\$1 \$2" == "pr list" ]]; then cat "$PRS"; exit 0; fi
exit 0
STUB
chmod +x "$TMP/bin/gh"

export PATH="$TMP/bin:$PATH"
export FACTORY_GUARD_NOW=$NOW
export FACTORY_WATCHDOG_REPO="saymyname-app/agent-factory"

watchdog() { FACTORY_ROOT="$TMP/city" "$WATCHDOG" "$@" 2>&1 || true; }
mails()   { grep -c '^mail send' "$MAIL" || true; }
creates() { grep -c '^bd create' "$CALLS" || true; }
reset_logs() { : > "$CALLS"; : > "$MAIL"; }

# 1. a quiet factory pages nothing -------------------------------------------
out=$(watchdog)
grep -q "quiet — nothing aged past its threshold" <<<"$out" || { echo "$out" >&2; fail "a quiet run was not reported quiet"; }
[ "$(mails)" = "0" ] || fail "a quiet run must not send mail"

# 2. an aged human gate is paged, and throttled on immediate re-run ----------
jq -n --arg c "$(iso $((NOW - 3000)))" '[{"id":"af-oihx","status":"open","await_type":"human","created_at":$c,"description":"Ad-hoc gate blocking af-u8id.4"}]' > "$GATES"
reset_logs
out=$(watchdog)
grep -q "aged gate — gate af-oihx open" <<<"$out" || { echo "$out" >&2; fail "aged gate not reported"; }
grep -q "^ATTENTION" <<<"$out" || fail "an aged gate must not read as healthy"
[ "$(mails)" = "1" ] || fail "aged gate should send exactly one mail"
grep -q "gc.watchdog_nudged_at" "$CALLS" || fail "aged gate nudge was not stamped on the gate bead"

reset_logs
out=$(watchdog)
grep -q "aged gate —" <<<"$out" || fail "the gate should still be reported while open"
[ "$(mails)" = "0" ] || fail "an immediate re-run must be throttled, not re-mailed"
printf '[]' > "$GATES"

# 3. --check-only reports but sends no mail and creates/updates nothing -------
jq -n --arg c "$(iso $((NOW - 3000)))" '[{"id":"af-oihx2","status":"open","await_type":"human","created_at":$c}]' > "$GATES"
reset_logs
out=$(watchdog --check-only)
grep -q "aged gate —" <<<"$out" || fail "--check-only should still report the finding"
[ "$(mails)" = "0" ] || fail "--check-only must never send mail"
grep -q '^bd update' "$CALLS" && fail "--check-only must never mutate a bead"
printf '[]' > "$GATES"

# 4. a conflicting PR is filed as a bead and paged once -----------------------
jq -n --arg c "$(iso $((NOW - 3000)))" '[{"number":57,"isDraft":false,"mergeStateStatus":"CONFLICTING","statusCheckRollup":[{"conclusion":"SUCCESS"}],"createdAt":$c}]' > "$PRS"
reset_logs
out=$(watchdog)
grep -q "stuck PR — PR #57 has a merge conflict" <<<"$out" || { echo "$out" >&2; fail "conflicting PR not reported"; }
[ "$(creates)" = "1" ] || fail "a stuck PR should be filed exactly once"
[ "$(mails)" = "1" ] || fail "a stuck PR should be paged exactly once"

# ...re-run must not duplicate the bead (title-contains match finds it).
reset_logs
out=$(watchdog)
grep -q "stuck PR — PR #57" <<<"$out" || fail "the PR should still be reported while unresolved"
[ "$(creates)" = "0" ] || fail "a stuck PR bead must not be filed twice"
printf '[]' > "$PRS"

# 5. a PR that never ran CI is flagged distinctly from a conflicting one ------
jq -n --arg c "$(iso $((NOW - 3000)))" '[{"number":58,"isDraft":false,"mergeStateStatus":"CLEAN","statusCheckRollup":[],"createdAt":$c}]' > "$PRS"
reset_logs
out=$(watchdog)
grep -q "has never triggered a CI check" <<<"$out" || { echo "$out" >&2; fail "CI-never-ran PR not distinguished"; }
printf '[]' > "$PRS"

# 6. a false-success workflow close is paged once, then throttled forever ----
jq -n '[{"id":"af-g7ts","status":"closed","title":"mol-scoped-work","metadata":{"gc.kind":"workflow","gc.outcome":"fail"}}]' > "$WORKFLOWS"
# `gc bd show` must agree with the `gc bd list` view above -- the watchdog now
# reads status/outcome off it to fingerprint what was reported.
cp "$WORKFLOWS" "$BEADS_DIR/af-g7ts.json"
reset_logs
out=$(watchdog)
grep -q "false-success close — af-g7ts closed CLOSED but gc.outcome=fail" <<<"$out" || { echo "$out" >&2; fail "false-success close not reported"; }
[ "$(mails)" = "1" ] || fail "a false-success close should be paged exactly once"

reset_logs
out=$(watchdog)
grep -q "false-success close — af-g7ts" <<<"$out" || fail "the false-success close should still be reported"
[ "$(mails)" = "0" ] || fail "a false-success close must only ever be paged once (permanently throttled)"

# ...but if the bead's own state later changes (outcome corrected, or flipped
# back to something worth reporting again), af-u61xq's fingerprint re-fires --
# "already flagged" alone must not throttle forever once the state moves.
jq '.[0].metadata["gc.outcome"] = "abort"' "$BEADS_DIR/af-g7ts.json" > "$BEADS_DIR/af-g7ts.json.next"
mv "$BEADS_DIR/af-g7ts.json.next" "$BEADS_DIR/af-g7ts.json"
reset_logs
out=$(watchdog)
[ "$(mails)" = "1" ] || fail "a changed outcome on an already-flagged bead must be re-reported, not throttled forever"

reset_logs
out=$(watchdog)
[ "$(mails)" = "0" ] || fail "the changed state must itself now be throttled once reported"
printf '[]' > "$WORKFLOWS"

# ...a bead already flagged under the pre-af-u61xq idiom (timestamp only, no
# fingerprint) must not be re-mailed on the first run after upgrade -- it
# backfills the fingerprint silently instead (the 7 known af-x4p4-class
# historical offenders this fix targets).
jq -n '[{"id":"af-x4p4","status":"closed","title":"mol-scoped-work","metadata":{"gc.kind":"workflow","gc.outcome":"fail"}}]' > "$WORKFLOWS"
printf '[{"id":"af-x4p4","status":"closed","metadata":{"gc.kind":"workflow","gc.outcome":"fail","gc.watchdog_flagged_false_success":"2026-09-01T00:00:00Z"}}]' > "$BEADS_DIR/af-x4p4.json"
reset_logs
out=$(watchdog)
grep -q "false-success close — af-x4p4" <<<"$out" || fail "the legacy-flagged close should still be reported in stdout"
[ "$(mails)" = "0" ] || fail "a legacy-flagged bead (timestamp only, unchanged state) must not be re-mailed on upgrade"
grep -q "gc.watchdog_false_success_fp=closed:fail" "$CALLS" || fail "the fingerprint was not backfilled for the legacy-flagged bead"
printf '[]' > "$WORKFLOWS"

# 7. a still-open campaign-liveness defect is re-nudged on a cooldown --------
printf '[{"id":"af-1vr4","metadata":{"gc.campaign_liveness_bead":"af-live1"}}]' > "$COORD"
echo '[{"id":"af-live1","status":"open","created_at":"'"$(iso $((NOW - 3000)))"'"}]' > "$BEADS_DIR/af-live1.json"
reset_logs
out=$(watchdog)
grep -q "campaign-liveness defect af-live1 still open" <<<"$out" || { echo "$out" >&2; fail "open liveness defect not re-checked"; }
[ "$(mails)" = "1" ] || fail "an aging open liveness defect should be re-nudged exactly once here"

reset_logs
out=$(watchdog)
[ "$(mails)" = "0" ] || fail "the liveness re-nudge must be throttled on immediate re-run"

# ...once closed, it is no longer paged.
echo '[{"id":"af-live1","status":"closed"}]' > "$BEADS_DIR/af-live1.json"
reset_logs
out=$(watchdog)
grep -q "campaign-liveness defect" <<<"$out" && fail "a closed liveness defect must not still be reported"

# 8. exit-code contract (af-u61xq, same contract as factory-guard since PR
#    #75): finding something is NOT a failure. Only the watchdog itself
#    failing to run (unreachable root) is a nonzero exit. This was previously
#    exit 1 on every ATTENTION finding, which fed recurring order.failed noise
#    into on-order-failed every 5-minute tick.
jq -n --arg c "$(iso $((NOW - 3000)))" '[{"id":"af-oihx3","status":"open","await_type":"human","created_at":$c}]' > "$GATES"
reset_logs
set +e
FACTORY_ROOT="$TMP/city" "$WATCHDOG" >/dev/null 2>&1
rc=$?
set -e
[ "$rc" = "0" ] || fail "exit code must be 0 when the watchdog ran and merely found something (was $rc)"
printf '[]' > "$GATES"

set +e
FACTORY_ROOT="$TMP/does-not-exist" "$WATCHDOG" >/dev/null 2>&1
rc=$?
set -e
[ "$rc" != "0" ] || fail "exit code must be nonzero when the watchdog itself could not run (unreachable root)"

printf 'PASS: factory-watchdog pages aged gates, stuck PRs, false-success closes, and re-nudges an open liveness defect, all throttled and silent under --check-only\n'
