#!/usr/bin/env bash
#
# factory-watchdog must page gaps the campaign-liveness check does not cover
# (Incident 2026-09-16): an aged "Gate: human" issue, a Factory-repo PR that
# is CONFLICTING or never ran CI, and a molecule/workflow bead that closed
# CLOSED with a non-pass gc.outcome. It must also flag a broken `gh auth`
# (Incident 2026-09-18, af-539b0) as one shared bead,
# aggregated control-step quarantines grouped by (rig, failure_reason)
# (af-uxz57: 126 quarantines over 8 days, zero signal). Every page is throttled (never every run) and
# --check-only must mutate nothing. gc and gh are stubs on PATH here; the
# watchdog must never reach a live store or GitHub from a test.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
WATCHDOG="$REPO_ROOT/bin/factory-watchdog"
# tests/lib/sandbox.sh (P10, af-ygibh): a throwaway HOME/city and, crucially,
# GC_BIN/BD_BIN/GH_BIN pointed off the real binaries -- every Gas City agent
# session (this one included) pre-exports GC_BIN to the real `gc`, and
# bin/escalation-door resolves `${GC_BIN:-gc}`, so a PATH-only stub here is
# not enough on its own (live incident 2026-09-29, af-0h4vnc: this test paged
# the live Mayor with fixture gate "af-oihx").
. "$REPO_ROOT/tests/lib/sandbox.sh"
sandbox_init
TMP="$SANDBOX_DIR"
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

NOW=1789555200   # 2026-09-16T10:40:00Z
iso() { date -u -d "@$1" +%Y-%m-%dT%H:%M:%SZ; }

mkdir -p "$TMP/city/.gc" "$TMP/bin"
printf '[workspace]\nprovider = "claude"\n' > "$TMP/city/city.toml"

GATES="$TMP/gates.json";         printf '[]' > "$GATES"
PRS="$TMP/prs.json";             printf '[]' > "$PRS"
WORKFLOWS="$TMP/workflows.json"; printf '[]' > "$WORKFLOWS"
QUARANTINE="$TMP/quarantine.json"; printf '[]' > "$QUARANTINE"
RIG_LIST="$TMP/rigs.json"
jq -n --arg path "$TMP/city" '{"rigs":[{"name":"acme-backend","path":$path,"hq":false}]}' > "$RIG_LIST"
EVENTS="$TMP/events.jsonl";       : > "$EVENTS"
COORD="$TMP/coord.json";         printf '[{"id":"af-1vr4","metadata":{}}]' > "$COORD"
GH_AUTH_RC="$TMP/gh-auth-rc";   printf '0' > "$GH_AUTH_RC"
GH_AUTH_OUT="$TMP/gh-auth-out"; printf 'Logged in to github.com account operator-1' > "$GH_AUTH_OUT"
mkdir -p "$TMP/city/.gc/runtime"
BEADS_DIR="$TMP/beads"; mkdir -p "$BEADS_DIR"
CALLS="$TMP/calls.log"; : > "$CALLS"
MAIL="$TMP/mail.log"; : > "$MAIL"

cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$CALLS"
case "\$1 \$2" in
  "events --since") cat "$EVENTS"; exit 0 ;;
  "bd gate")
    [[ "\$3" == list ]] && { cat "$GATES"; exit 0; }
    ;;
  "rig list")
    cat "$RIG_LIST"; exit 0 ;;
  "bd list")
    if [[ "\$*" == *"gc.kind=workflow"* ]]; then cat "$WORKFLOWS"; exit 0; fi
    if [[ "\$*" == *"--label gc:control-quarantined"* ]]; then cat "$QUARANTINE"; exit 0; fi
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
    if [[ "\$id" == af-1vr4 ]]; then cat "$COORD"; exit 0; fi
    f="$BEADS_DIR/\$id.json"
    if [[ -f "\$f" ]]; then
      cat "\$f"
    else
      # Every id watchdog/escalation-door ever shows here is a real bead in
      # production (gate ids included); synthesize a minimal open one so
      # escalation-door's show_bead never dies on a fixture gap.
      echo '[{"id":"'"\$id"'","status":"open","metadata":{}}]'
    fi
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
if [[ "\$1 \$2" == "auth status" ]]; then
  cat "$GH_AUTH_OUT"
  exit "\$(cat "$GH_AUTH_RC")"
fi
exit 0
STUB
chmod +x "$TMP/bin/gh"

export PATH="$TMP/bin:$PATH"
# sandbox_init pointed GC_BIN/GH_BIN at its own generic fakes in
# $SANDBOX_STUB_BIN; bin/escalation-door and bin/factory-watchdog resolve
# $GC_BIN/$GH_BIN directly (not just via PATH), so they must be repointed at
# this test's own scripted stubs above it, not just left on PATH.
export GC_BIN="$TMP/bin/gc"
export GH_BIN="$TMP/bin/gh"
export FACTORY_GUARD_NOW=$NOW
export FACTORY_WATCHDOG_REPO="acme/factory-hq"

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
# Routed through escalation-door's Mayor-first class (O06/O07), not a raw mail.
grep -q "^mail send mayor --notify -s Escalation (Mayor first): af-oihx" "$MAIL" \
  || { cat "$MAIL" >&2; fail "aged gate did not route through escalation-door's mayor-first class"; }

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
# fingerprint) MUST be mailed on the first run after upgrade, exactly like
# any other fingerprint-empty bead -- af-nf8en: an earlier version special-
# cased this to backfill the fingerprint silently, which meant the alert
# flashed in the cockpit signal file for exactly one tick (add_alert still
# fired) and then vanished forever with no mail ever sent, for any legacy
# bead whose state had actually moved since the old idiom flagged it. There
# is no way to tell "unchanged since the old flag" apart from "moved since
# the old flag" from a timestamp alone, so the safe default is to report it.
jq -n '[{"id":"af-x4p4","status":"closed","title":"mol-scoped-work","metadata":{"gc.kind":"workflow","gc.outcome":"fail"}}]' > "$WORKFLOWS"
printf '[{"id":"af-x4p4","status":"closed","metadata":{"gc.kind":"workflow","gc.outcome":"fail","gc.watchdog_flagged_false_success":"2026-09-01T00:00:00Z"}}]' > "$BEADS_DIR/af-x4p4.json"
reset_logs
out=$(watchdog)
grep -q "false-success close — af-x4p4" <<<"$out" || fail "the legacy-flagged close should still be reported in stdout"
[ "$(mails)" = "1" ] || fail "a legacy-flagged bead with an empty fingerprint must be mailed once on upgrade, not silently backfilled"
grep -q "gc.watchdog_false_success_fp=closed:fail" "$CALLS" || fail "the fingerprint was not backfilled for the legacy-flagged bead"
reset_logs
out=$(watchdog)
[ "$(mails)" = "0" ] || fail "the legacy-flagged bead's now-known state must be throttled on the next run"
printf '[]' > "$WORKFLOWS"

# 7. a failing gh auth is filed as one shared bead and paged once ------------
printf '1' > "$GH_AUTH_RC"
printf 'You are not logged into any GitHub hosts' > "$GH_AUTH_OUT"
reset_logs
out=$(watchdog)
grep -q "gh auth — gh auth status failed (exit 1)" <<<"$out" || { echo "$out" >&2; fail "gh auth failure not reported"; }
[ "$(creates)" = "1" ] || fail "gh auth failure should file exactly one shared bead"
[ "$(mails)" = "1" ] || fail "gh auth failure should be paged exactly once"

# ...re-run while still failing must not duplicate the bead, and must be throttled.
reset_logs
out=$(watchdog)
grep -q "gh auth — gh auth status failed" <<<"$out" || fail "gh auth failure should still be reported while unresolved"
[ "$(creates)" = "0" ] || fail "gh auth bead must not be filed twice"
[ "$(mails)" = "0" ] || fail "an immediate gh auth re-run must be throttled, not re-mailed"

# ...--check-only reports but mutates nothing.
reset_logs
out=$(watchdog --check-only)
grep -q "gh auth — gh auth status failed" <<<"$out" || fail "--check-only should still report the gh auth failure"
[ "$(mails)" = "0" ] || fail "--check-only must never send mail for gh auth"
grep -q '^bd create' "$CALLS" && fail "--check-only must never file a bead for gh auth"

# ...recovery auto-resolves the shared bead without a human closing it by hand.
printf '0' > "$GH_AUTH_RC"
printf 'Logged in to github.com account operator-1' > "$GH_AUTH_OUT"
reset_logs
out=$(watchdog)
grep -q "gh auth —" <<<"$out" && fail "a recovered gh auth must not still be reported as a problem"
grep -q -- '--status=closed' "$CALLS" || fail "gh auth recovery should auto-resolve the shared bead"

# 10. exit-code contract (af-u61xq, same contract as factory-guard since PR
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

# 12. control-step quarantines are aggregated by (rig, failure_reason), paged
#     once as a group -- not once per bead (af-uxz57: 126 quarantines, zero
#     signal) -- throttled on re-run, and auto-resolve once the group clears.
jq -n --arg t "$(iso $((NOW - 3000)))" '
  [range(0;3) | {
    "id": ("acme-q" + (. | tostring)),
    "metadata": {
      "gc.control_quarantined": true,
      "gc.control_quarantined_at": $t,
      "gc.failure_reason": "control_dispatch_error",
      "gc.controller_error": "resolving gate condition path: lstat .../.gc/scripts: no such file or directory"
    }
  }]' > "$QUARANTINE"
reset_logs
out=$(watchdog)
grep -q "control quarantine — 3 control step(s) quarantined in acme-backend with failure_reason=control_dispatch_error" <<<"$out" \
  || { echo "$out" >&2; fail "control quarantine group not reported"; }
[ "$(creates)" = "1" ] || fail "a control-quarantine group should be filed exactly once, not once per bead"
[ "$(mails)" = "1" ] || fail "a control-quarantine group should be paged exactly once"

# ...re-run while still active must not duplicate the bead, and must be throttled.
reset_logs
out=$(watchdog)
grep -q "control quarantine —" <<<"$out" || fail "the control-quarantine group should still be reported while active"
[ "$(creates)" = "0" ] || fail "a control-quarantine bead must not be filed twice"
[ "$(mails)" = "0" ] || fail "an immediate control-quarantine re-run must be throttled, not re-mailed"

# ...--check-only reports but mutates nothing.
reset_logs
out=$(watchdog --check-only)
grep -q "control quarantine —" <<<"$out" || fail "--check-only should still report the control-quarantine group"
[ "$(mails)" = "0" ] || fail "--check-only must never send mail for control quarantine"

# ...recovery (no new quarantine in the group) auto-resolves the bead.
printf '[]' > "$QUARANTINE"
reset_logs
out=$(watchdog)
grep -q "control quarantine —" <<<"$out" && fail "a recovered control-quarantine group must not still be reported as a problem"
grep -q -- '--status=closed' "$CALLS" || fail "control-quarantine recovery should auto-resolve the bead"

printf 'PASS: factory-watchdog pages aged gates, stuck PRs, false-success closes, broken gh auth, aggregated control-step quarantines, and open liveness defects, all throttled and silent under --check-only\n'
