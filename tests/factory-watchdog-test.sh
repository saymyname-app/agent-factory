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
DEPS_DIR="$TMP/deps"; mkdir -p "$DEPS_DIR"
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
  "bd dep")
    # bd dep list ID... --direction=up -t TYPE --json: the dependents of
    # the first id, from a fixture file; none unless the test wrote one.
    f="$DEPS_DIR/\$4.\${*: -2:1}.json"
    if [[ -f "\$f" ]]; then cat "\$f"; else echo '[]'; fi
    exit 0 ;;
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
    shift 2
    for id in "\$@"; do
      [[ "\$id" == --json ]] && continue
      if [[ "\$id" == af-1vr4 ]]; then cat "$COORD"; continue; fi
      f="$BEADS_DIR/\$id.json"
      if [[ -f "\$f" ]]; then
        cat "\$f"
      else
        # Every id watchdog/escalation-door ever shows here is a real bead in
        # production (gate ids included); synthesize a minimal open one so
        # escalation-door's show_bead never dies on a fixture gap.
        echo '[{"id":"'"\$id"'","status":"open","metadata":{}}]'
      fi
    done | jq -s 'add // []'
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

cat > "$TMP/bin/factory-observe" <<STUB
#!/usr/bin/env bash
printf 'factory-observe %s\n' "\$*" >> "$CALLS"
printf '{"ok":true,"action":"none"}\n'
STUB
chmod +x "$TMP/bin/factory-observe"

export PATH="$TMP/bin:$PATH"
# sandbox_init pointed GC_BIN/GH_BIN at its own generic fakes in
# $SANDBOX_STUB_BIN; bin/escalation-door and bin/factory-watchdog resolve
# $GC_BIN/$GH_BIN directly (not just via PATH), so they must be repointed at
# this test's own scripted stubs above it, not just left on PATH.
export GC_BIN="$TMP/bin/gc"
export GH_BIN="$TMP/bin/gh"
export FACTORY_GUARD_NOW=$NOW
export FACTORY_WATCHDOG_REPO="acme/factory-hq"
export FACTORY_WATCHDOG_OBSERVE_BIN="$TMP/bin/factory-observe"

watchdog() { FACTORY_ROOT="$TMP/city" "$WATCHDOG" "$@" 2>&1 || true; }
mails()   { grep -c '^mail send' "$MAIL" || true; }
creates() { grep -c '^bd create' "$CALLS" || true; }
reset_logs() { : > "$CALLS"; : > "$MAIL"; }

# 1. a quiet factory pages nothing -------------------------------------------
out=$(watchdog)
grep -q "quiet — nothing aged past its threshold" <<<"$out" || { echo "$out" >&2; fail "a quiet run was not reported quiet"; }
[ "$(mails)" = "0" ] || fail "a quiet run must not send mail"
grep -q '^factory-observe live$' "$CALLS" || fail "the existing watchdog order did not run live observation"

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

# 2b. an aged gate whose wait is already a request on the operator's list is
# reported but never paged: on the bead it blocks, or on the convoy tracking
# that bead (af-brjmv6: af-fmeaj6 paged every 30 min for three days) ----------
jq -n --arg c "$(iso $((NOW - 3000)))" '[{"id":"af-gate1","status":"open","await_type":"human","created_at":$c,"description":"Ad-hoc gate blocking af-t32"}]' > "$GATES"
printf '[{"id":"af-t32","status":"in_progress","metadata":{}}]' > "$DEPS_DIR/af-gate1.blocks.json"
printf '[{"id":"af-convoy","status":"open","metadata":{"gc.needs_benjamin":"La barriere attend tes mots"}}]' > "$DEPS_DIR/af-t32.tracks.json"
reset_logs
out=$(watchdog)
grep -q "aged gate — already on the operator's list (af-convoy), not paged: gate af-gate1 open" <<<"$out" \
  || { echo "$out" >&2; fail "a gate already on the operator's list (convoy) was not reported as such"; }
grep -q "^ATTENTION" <<<"$out" && fail "a wait already on the operator's list is not a problem"
[ "$(mails)" = "0" ] || fail "a gate already on the operator's list must not page the Mayor"
grep -q '^bd update af-gate1' "$CALLS" && fail "a gate that is not paged must not be stamped as nudged"

printf '[{"id":"af-t32","status":"blocked","metadata":{"gc.needs_benjamin":"Choisis une variante"}}]' > "$DEPS_DIR/af-gate1.blocks.json"
rm -f "$DEPS_DIR/af-t32.tracks.json"
reset_logs
out=$(watchdog)
grep -q "already on the operator's list (af-t32), not paged" <<<"$out" \
  || { echo "$out" >&2; fail "a gate whose blocked bead holds the request was not recognised"; }
[ "$(mails)" = "0" ] || fail "a gate whose blocked bead holds the request must not page the Mayor"

# An answered request ("none") or one on a closed bead is no longer on the
# list: the gate is paged again.
printf '[{"id":"af-t32","status":"in_progress","metadata":{"gc.needs_benjamin":"none"}}]' > "$DEPS_DIR/af-gate1.blocks.json"
printf '[{"id":"af-convoy","status":"closed","metadata":{"gc.needs_benjamin":"La barriere attend tes mots"}}]' > "$DEPS_DIR/af-t32.tracks.json"
reset_logs
out=$(watchdog)
grep -q "^ATTENTION" <<<"$out" || { echo "$out" >&2; fail "a gate with no active request must still be a problem"; }
[ "$(mails)" = "1" ] || fail "a gate with no active request on the list must still page the Mayor"
rm -f "$DEPS_DIR"/*.json
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

# ...a failed workflow whose new-flow ticket code already stopped is not paged
# (af-it6qbk): root -> input convoy -> ticket, read through gc bd show.
jq -n '[{"id":"af-pau68a","status":"closed","title":"mol-test-review","metadata":{"gc.kind":"workflow","gc.outcome":"fail","gc.formula_name":"mol-test-review","gc.input_convoy_id":"af-tzx0my"}}]' > "$WORKFLOWS"
cp "$WORKFLOWS" "$BEADS_DIR/af-pau68a.json"
jq -n '[{"id":"af-tzx0my","issue_type":"convoy","dependencies":[{"id":"af-d0o8ae","dependency_type":"tracks","metadata":{},"description":"convoy: af-pqfxmd\nticket: af-qjq1t6\n"}]}]' > "$BEADS_DIR/af-tzx0my.json"
jq -n '[{"id":"af-qjq1t6","status":"in_progress","metadata":{"gc.flow.mark":"new-flow/v1","gc.flow.stop":"{\"reason\":\"test_review_no_result\",\"detail\":\"2 launches\",\"at\":\"2026-10-15T22:20:23Z\"}"}}]' > "$BEADS_DIR/af-qjq1t6.json"
reset_logs
out=$(watchdog)
grep -q "af-pau68a failed, ticket af-qjq1t6 already stopped (test_review_no_result) by code — not paged" <<<"$out" || { echo "$out" >&2; fail "a failure code already stopped should be named as not paged"; }
[ "$(mails)" = "0" ] || fail "a failure whose ticket code already stopped must not be paged"
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

# 9. a started ticket of a marked convoy that nobody moves goes to the
# operator's list once, and is withdrawn once it moves again (af-1fvzns) ------
CONVOY_SHOW="$TMP/convoy-show.json"
cat > "$TMP/bin/convoy-state" <<STUB
#!/usr/bin/env bash
case "\$1" in
  list) echo '{"ok":true,"convoys":["af-cv1"],"closed":[],"closed_outside":[]}' ;;
  show) cat "$CONVOY_SHOW" ;;
esac
STUB
chmod +x "$TMP/bin/convoy-state"
export FACTORY_WATCHDOG_CONVOY_STATE_BIN="$TMP/bin/convoy-state"
stalled_show() {  # stalled_show <status> -> a convoy with one ticket left since 50 min
  jq -n --arg s "$1" --arg at "$(iso $((NOW - 3000)))" '{convoy:{id:"af-cv1"},tickets:[{id:"af-t9",title:"T09",status:$s,
    gates:{dispatch:{at:$at}},session:{at:$at,name:"delivery-author-gone"},exit:{at:$at,exit:"finished"},
    stop:{at:$at,raised:$at,reason:"still_refused"}}]}' > "$CONVOY_SHOW"
}
stalled_show in_progress
reset_logs
out=$(watchdog --check-only)
grep -q "ticket sans suite — af-t9 (T09) du convoi af-cv1 : sans suite depuis" <<<"$out" \
  || { echo "$out" >&2; fail "--check-only should still report a ticket without a next step"; }
[ "$(creates)" = "0" ] || fail "--check-only must never file a bead for a ticket without a next step"
[ "$(grep -c '^bd show ' "$CALLS")" = "1" ] \
  || fail "ticket scan must read the convoy and ticket in one batched tracker call"
grep -q '^bd show af-cv1 af-t9 --json$' "$CALLS" \
  || { cat "$CALLS" >&2; fail "ticket scan did not batch its tracker reads"; }

printf '[{"id":"af-cv1","status":"open","metadata":{"gc.needs_benjamin":"Decision attendue"}}]' > "$BEADS_DIR/af-cv1.json"
reset_logs
out=$(watchdog --check-only)
grep -q "ticket sans suite —" <<<"$out" \
  && { echo "$out" >&2; fail "a ticket whose convoy is on the operator list must not be reported"; }
unlink "$BEADS_DIR/af-cv1.json"

reset_logs
out=$(watchdog)
grep -q "flagged ticket af-t9 without a next step" <<<"$out" || { echo "$out" >&2; fail "a ticket without a next step was not paged"; }
[ "$(creates)" = "1" ] || fail "a ticket without a next step should be filed exactly once"
stall_bead=$(grep -l '\[watchdog\] ticket sans suite : af-t9' "$BEADS_DIR"/*.json | head -1)
jq -e '.[0].metadata["gc.needs_benjamin"] | startswith("Incident d'"'"'usine : ticket af-t9 sans suite")' "$stall_bead" >/dev/null \
  || { cat "$stall_bead" >&2; fail "the ticket without a next step is not on the operator's list"; }
grep -q '^mail send' "$MAIL" || fail "the operator was not mailed about the ticket without a next step"

reset_logs
out=$(watchdog)
[ "$(creates)" = "0" ] || fail "a ticket without a next step must not be filed twice"

# ...moving again (here: closed through its gate) withdraws the request.
stalled_show closed
reset_logs
out=$(watchdog)
grep -q "ticket sans suite —" <<<"$out" && fail "a ticket that moved must not be reported any more"
grep -q "auto-resolved ticket without a next step" <<<"$out" || { echo "$out" >&2; fail "the request was not withdrawn"; }
jq -e '(.[0].metadata["gc.needs_benjamin"] // "none") == "none"' "$stall_bead" >/dev/null \
  || { cat "$stall_bead" >&2; fail "the withdrawn request is still on the operator's list"; }
unset FACTORY_WATCHDOG_CONVOY_STATE_BIN

printf 'PASS: factory-watchdog pages aged gates, stuck PRs, false-success closes, broken gh auth, aggregated control-step quarantines, tickets without a next step, and open liveness defects, all throttled and silent under --check-only\n'
