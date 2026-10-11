# --- 4. bin/factory-dispatch-guard on a drift held in progress ----------------
# None of the three guards below is ever the holder of the bead it releases
# (af-33wuoh): each one clears the assignee it has just read, by
# compare-and-set.
drift=$(new "slung to a pool while a session still holds it in progress")
gc bd --actor "$TAKER" update "$drift" --claim >/dev/null 2>&1 || fail "could not claim the drifted bead"
gc bd --actor "$TAKER" update "$drift" --set-metadata gc.routed_to=trial-pool >/dev/null 2>&1 \
  || fail "could not route the drifted bead"
# The guard pages the Mayor with `gc mail send --notify`, which waits about a
# minute for a session this unstarted city does not have. GC_BIN, the guard's
# own seam, names a wrapper that drops that one call and hands every other
# one to the real gc. It is not BD_BIN, gc never runs it, and it is not
# called `gc`: section 6 puts this directory first in PATH.
GC_REAL=$(command -v gc)
mkdir -p "$TRIAL/bin"
cat > "$TRIAL/bin/gc-without-mail" <<STUB
#!/usr/bin/env bash
for arg in "\$@"; do [ "\$arg" != mail ] || exit 0; done
exec "$GC_REAL" "\$@"
STUB
chmod +x "$TRIAL/bin/gc-without-mail"
out=$(GC_BIN="$TRIAL/bin/gc-without-mail" FACTORY_DISPATCH_STALE_MINUTES=0 "$ROOT/bin/factory-dispatch-guard" 2>&1) \
  || fail "factory-dispatch-guard failed: $out"
expect "$drift" '.assignee // ""' "" "factory-dispatch-guard (said: $out)"
expect "$drift" '.status' in_progress "factory-dispatch-guard"

# --- 5. bin/on-session-stranded on a bead its dead session still holds --------
stranded=$(new "work bead of a session that died")
gc bd --actor trial-dead-session update "$stranded" --claim >/dev/null 2>&1 \
  || fail "could not claim the stranded bead"
gc event emit session.stranded --message "pool session terminated without clean drain" \
  --payload "{\"session_id\":\"trial-dead\",\"session_name\":\"trial-dead-session\",\"work_bead_ids\":[\"$stranded\"]}" \
  >/dev/null 2>&1
gc events --type session.stranded --since 30m 2>/dev/null | grep -qF "$stranded" \
  || fail "the isolated city does not return the session.stranded event this test emitted"
# The order pages the Mayor through bin/escalation-door, whose seam is GC_BIN
# too: same wrapper, same minute not spent waiting.
out=$(GC_BIN="$TRIAL/bin/gc-without-mail" ON_SESSION_STRANDED_STATE_FILE="$TRIAL/stranded-state.json" \
  "$ROOT/bin/on-session-stranded" 2>&1) \
  || fail "on-session-stranded failed: $out"
expect "$stranded" '.status' open "on-session-stranded (said: $out)"
expect "$stranded" '.assignee // ""' "" "on-session-stranded"
expect "$stranded" '.metadata["gc.session_stranded"] // ""' trial-dead "on-session-stranded"

# --- 6. bin/pr-autopilot, rejection of a ticket a worker still holds ----------
# GitHub is a stub (one conflicted pull request on the ticket's branch); the
# tracker is the real one.
rejected=$(new "ticket whose pull request went into conflict")
gc bd --actor "$TAKER" update "$rejected" --claim >/dev/null 2>&1 || fail "could not claim the ticket"
gc bd --actor "$TAKER" update "$rejected" --set-metadata gc.work_branch=do-work/trial >/dev/null 2>&1 \
  || fail "could not stamp the ticket's branch"
mkdir -p "$TRIAL/bin" "$TEST_CITY/rigs/saymyname-backend" "$TEST_CITY/rigs/saymyname-frontend"
cat > "$TRIAL/bin/gh" <<'STUB'
#!/usr/bin/env bash
if [[ "$1 $2" == "pr list" ]]; then
  if [[ "$*" == *Say-my-name-back* && "$*" == *"--state open"* ]]; then
    echo '[{"number":10,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"DIRTY","statusCheckRollup":[],"headRefOid":"sha10a","labels":[]}]'
  else
    echo '[]'
  fi
elif [[ "$1 $2" == "pr view" && "$*" == *"--json headRefName"* ]]; then
  echo "do-work/trial"
elif [[ "$1 $2" == "pr view" && "$*" == *"--json comments"* ]]; then
  :
elif [[ "$1 $2" == "pr view" ]]; then
  printf 'OPEN\tfalse\n'
elif [[ "$1" == api && "$*" == */commits/* ]]; then
  echo "deadbeefcafefeed1234567890abcdef12345678"
elif [[ "$1" == api ]]; then
  exit 1
fi
exit 0
STUB
chmod +x "$TRIAL/bin/gh"
out=$(PATH="$TRIAL/bin:$PATH" REVERSIBILITY_CHECK_BIN="$TRIAL/bin/gh" ESCALATION_DOOR_BIN="$TRIAL/bin/gh" \
  "$ROOT/bin/pr-autopilot" 2>&1) || fail "pr-autopilot failed: $out"
expect "$rejected" '.status' open "pr-autopilot ticket rejection (said: $out)"
expect "$rejected" '.assignee // ""' "" "pr-autopilot ticket rejection"
expect "$rejected" '.metadata["gc.pr_rejection_count"] // ""' 1 "pr-autopilot ticket rejection"

