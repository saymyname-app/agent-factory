#!/usr/bin/env bash
#
# factory-guard must check campaign LIVENESS, not only health (af-vc39).
#
# On the night of 2026-09-15 every structural check was green while the wake
# loop was dead from 01:06 to 07:50. The guard answered "are the parts in
# place" and never "did anything move". This drives the guard against a fake
# city whose coordination bead carries the sentinel's heartbeats, and asserts:
# a stalled campaign is flagged and filed exactly once, a silent wake loop is
# flagged, a deliberate pause is not, and --check-only files nothing.
#
# The gc here is a stub on PATH. The guard must never reach the live store
# from a test, which is also why it skips liveness outside a city root.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/factory-guard"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

NOW=1789555200   # 2026-09-16T10:40:00Z
iso() { date -u -d "@$1" +%Y-%m-%dT%H:%M:%SZ; }

# --- a throwaway city: committed city.toml, ignored .gc ----------------------
git init -q --bare "$TMP/origin.git"
git init -q "$TMP/city"
cd "$TMP/city"
git config user.email t@t; git config user.name t; git config commit.gpgsign false
git remote add origin "$TMP/origin.git"
mkdir -p .gc
printf '.gc/\n' > .gitignore
printf '[workspace]\nprovider = "claude"\n' > city.toml
git add -A; git commit -qm city; git branch -M main; git push -q origin main; git fetch -q origin

COORD="$TMP/coord.json"
CALLS="$TMP/calls.log"; : > "$CALLS"
mkdir -p "$TMP/beads" "$TMP/bin"
SESSIONS="$TMP/sessions.json"; echo '{"sessions":[]}' > "$SESSIONS"

cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$CALLS"
if [[ \$1 == bd && \$2 == show && \$3 == af-1vr4 ]]; then
  [[ \${LIVENESS_STORE_DOWN:-0} == 1 ]] && { echo 'store down' >&2; exit 42; }
  cat "$COORD"; exit 0
fi
if [[ \$1 == bd && \$2 == show ]]; then
  f="$TMP/beads/\$3.json"
  if [[ -f \$f ]]; then cat "\$f"; else echo '[]'; fi
  exit 0
fi
if [[ \$1 == bd && \$2 == list ]]; then
  metadata_field=""
  prev=""
  for arg in "\$@"; do
    [[ \$prev == --metadata-field ]] && metadata_field="\$arg"
    prev="\$arg"
  done
  if [[ -n \$metadata_field ]]; then
    f="$TMP/children-\${metadata_field#gc.root_bead_id=}.json"
  else
    f="$TMP/workflows.json"
  fi
  if [[ -f \$f ]]; then cat "\$f"; else echo '[]'; fi
  exit 0
fi
if [[ \$1 == bd && \$2 == create ]]; then
  echo '{"id":"af-live1","status":"open"}' > "$TMP/beads/af-live1.json"
  echo '{"id":"af-live1"}'; exit 0
fi
if [[ \$1 == bd && \$2 == update && \$3 == af-1vr4 ]]; then
  pair=\$5; key=\${pair%%=*}; value=\${pair#*=}
  jq --arg k "\$key" --arg v "\$value" '.[0].metadata[\$k] = \$v' "$COORD" > "$COORD.next"
  mv "$COORD.next" "$COORD"; exit 0
fi
if [[ \$1 == session && \$2 == list ]]; then
  cat "$SESSIONS"; exit 0
fi
exit 0
STUB
chmod +x "$TMP/bin/gc"
export PATH="$TMP/bin:$PATH"
# ADR-0023: the durable-failure path shells out to bin/campaign-pointer,
# a separate process. Relying on PATH alone to shadow `gc` for that nested
# exec is not reliable everywhere `gc` is a real command already on PATH;
# GC_BIN is an explicit environment variable campaign-pointer reads itself,
# so export it too -- the same belt-and-braces pattern
# tests/campaign-pointer-test.sh already uses.
export GC_BIN="$TMP/bin/gc"
export CAMPAIGN_LOCK_FILE="$TMP/campaign-pointer.lock"
export FACTORY_GUARD_NOW=$NOW

coord() {  # coord <sentinel-age-s> <progress-age-s|-> [state] [kind] [cause]
  local s p
  s=$(iso $((NOW - $1)))
  if [[ $2 == - ]]; then p=""; else p=$(iso $((NOW - $2))); fi
  jq -n --arg s "$s" --arg p "$p" --arg st "${3:-active}" --arg k "${4:-}" --arg c "${5:-}" '
    [{id:"af-1vr4", metadata:({
      "gc.campaign_mode":"automatic", "gc.campaign_state":$st,
      "gc.campaign_block_kind":$k, "gc.campaign_cause":$c,
      "gc.campaign_sentinel_at":$s, "gc.campaign_failure_count":"0"}
      + (if $p == "" then {} else {"gc.campaign_progress_at":$p} end))}]' > "$COORD"
}
guard() { FACTORY_ROOT="$TMP/city" "$GUARD" "$@" 2>&1 || true; }
creates() { grep -c '^bd create' "$CALLS" || true; }

# 1. alive and advancing ---------------------------------------------------------
coord 30 600
out=$(guard --check-only)
grep -q "✓ liveness — last progress 10 min ago" <<<"$out" || { echo "$out" >&2; fail "fresh progress not reported ok"; }

# 2. alive but not advancing: flagged, and --check-only files nothing -------------
coord 30 5400
out=$(guard --check-only)
grep -q "liveness — no campaign progress for 90 min" <<<"$out" || { echo "$out" >&2; fail "stalled campaign not flagged"; }
grep -q "^UNRESOLVED" <<<"$out" || fail "a stalled campaign must not read as healthy"
[ "$(creates)" = "0" ] || fail "--check-only filed a defect"

# 2b. af-ooob8: progress stamp is stale, but the current result bead itself
# has a recent heartbeat -- e.g. a review sub-session running after delivery,
# outside the transition reasons that refresh gc.campaign_progress_at. That
# is real activity, not a stall, and must not be flagged or filed.
coord 30 5400
jq --arg id af-cur1 '.[0].metadata["gc.current_jit"] = $id' "$COORD" > "$COORD.next" && mv "$COORD.next" "$COORD"
jq -n --arg hb "$(iso $((NOW - 5 * 60)))" '{id:"af-cur1", metadata:{"gc.last_heartbeat_at":$hb}}' > "$TMP/beads/af-cur1.json"
before=$(creates)
out=$(guard --check-only)
grep -q "✓ liveness — campaign progress stamp is 90 min old, but the current result was active 5 min ago" <<<"$out" \
  || { echo "$out" >&2; fail "recent result activity did not override a stale progress stamp"; }
grep -q "! liveness" <<<"$out" && fail "a result with recent activity was reported as a liveness defect"
[ "$(creates)" = "$before" ] || fail "recent result activity still filed a liveness defect"
rm -f "$TMP/beads/af-cur1.json"
jq '.[0].metadata |= del(.["gc.current_jit"])' "$COORD" > "$COORD.next" && mv "$COORD.next" "$COORD"

# 2c. af-py8n1: the current result delegates to a workflow tracked only by a
# convoy "tracks" link (no --parent edge) -- both the result bead and the
# workflow root are stale, but one of the workflow's decomposed/review steps
# (linked back only via gc.root_bead_id) has a recent heartbeat. That is
# real activity too, and must not be flagged or filed, exactly like 2b.
coord 30 5400
jq --arg id af-cur2 '.[0].metadata["gc.current_jit"] = $id' "$COORD" > "$COORD.next" && mv "$COORD.next" "$COORD"
jq -n --arg old "$(iso $((NOW - 200 * 60)))" '{id:"af-cur2", updated_at:$old}' > "$TMP/beads/af-cur2.json"
jq -n --arg old "$(iso $((NOW - 200 * 60)))" \
  '[{id:"af-wf1", status:"in_progress", updated_at:$old,
     metadata:{"gc.kind":"workflow", "gc.input_convoy_id":"af-conv1"}}]' \
  > "$TMP/workflows.json"
jq -n '{id:"af-conv1", dependencies:[{id:"af-cur2", dependency_type:"tracks", status:"in_progress"}]}' \
  > "$TMP/beads/af-conv1.json"
jq -n --arg old "$(iso $((NOW - 200 * 60)))" '{id:"af-wf1", updated_at:$old}' > "$TMP/beads/af-wf1.json"
jq -n --arg hb "$(iso $((NOW - 8 * 60)))" \
  '[{id:"af-step1", status:"in_progress", metadata:{"gc.root_bead_id":"af-wf1", "gc.last_heartbeat_at":$hb}}]' \
  > "$TMP/children-af-wf1.json"
before=$(creates)
out=$(guard --check-only)
grep -q "✓ liveness — campaign progress stamp is 90 min old, but the current result was active 8 min ago" <<<"$out" \
  || { echo "$out" >&2; fail "recent activity on a workflow tracked only via convoy link did not override a stale progress stamp"; }
grep -q "! liveness" <<<"$out" && fail "a delegated workflow with recent step activity was reported as a liveness defect"
[ "$(creates)" = "$before" ] || fail "recent delegated-workflow activity still filed a liveness defect"
rm -f "$TMP/beads/af-cur2.json" "$TMP/beads/af-conv1.json" "$TMP/beads/af-wf1.json" \
      "$TMP/workflows.json" "$TMP/children-af-wf1.json"
jq '.[0].metadata |= del(.["gc.current_jit"])' "$COORD" > "$COORD.next" && mv "$COORD.next" "$COORD"

# 3. the default run files it exactly once, and pages the Mayor -----------------
out=$(guard)
grep -q "filed liveness defect af-live1" <<<"$out" || { echo "$out" >&2; fail "stalled campaign not filed"; }
[ "$(jq -r '.[0].metadata["gc.campaign_liveness_bead"]' "$COORD")" = "af-live1" ] \
  || fail "the filed defect is not remembered on the coordination bead"
grep -q "^mail send mayor --notify" "$CALLS" \
  || fail "filing a liveness defect must page the Mayor, not just file it (incident gap 1)"
out=$(guard)
grep -q "already filed: af-live1" <<<"$out" || { echo "$out" >&2; fail "second run did not recognise the open defect"; }
[ "$(creates)" = "1" ] || fail "the defect was filed more than once"

# ...and once it is closed with the SAME known cause (the underlying progress
# anchor has not moved), af-ii0mj: it must not immediately refile -- a
# cooldown defers the next check instead of re-diagnosing an already-known,
# still-true cause every ~5-10 min.
echo '{"id":"af-live1","status":"closed"}' > "$TMP/beads/af-live1.json"
before=$(creates)
out=$(guard)
grep -q "known cause already diagnosed (af-live1) — deferring next check" <<<"$out" \
  || { echo "$out" >&2; fail "a same-cause closed defect was not recognised as a known cause"; }
[ "$(creates)" = "$before" ] || fail "a known-cause diagnosis was re-filed immediately"
cooldown_until=$(jq -r '.[0].metadata["gc.campaign_liveness_cooldown_until"]' "$COORD")
[ -n "$cooldown_until" ] && [ "$cooldown_until" != "null" ] || fail "no cooldown was armed for the known cause"

# ...and while that cooldown holds, repeat ticks stay quiet too.
out=$(guard)
grep -q "cooldown active until $cooldown_until" <<<"$out" \
  || { echo "$out" >&2; fail "an active cooldown was not recognised on a repeat tick"; }
[ "$(creates)" = "$before" ] || fail "a repeat tick inside the cooldown window re-filed"

# ...but a genuinely new stall -- the progress anchor moved, meaning real
# progress happened and then it stalled again -- files immediately, a
# cooldown armed for the OLD anchor notwithstanding.
jq --arg p "$(iso $((NOW - 4000)))" '.[0].metadata["gc.campaign_progress_at"] = $p' "$COORD" > "$COORD.next" \
  && mv "$COORD.next" "$COORD"
out=$(guard)
grep -q "filed liveness defect af-live1" <<<"$out" \
  || { echo "$out" >&2; fail "a new stall (moved anchor) was suppressed by a cooldown armed for the old anchor"; }
[ "$(creates)" = "$((before + 1))" ] || fail "the new stall was not filed exactly once"

# ...and once ITS cooldown expires while the same (new) anchor is still
# stale, it pings again instead of staying quiet forever.
echo '{"id":"af-live1","status":"closed"}' > "$TMP/beads/af-live1.json"
before=$(creates)
out=$(guard)
grep -q "known cause already diagnosed (af-live1) — deferring next check" <<<"$out" \
  || { echo "$out" >&2; fail "the new anchor's closure did not arm a fresh cooldown"; }
[ "$(creates)" = "$before" ] || fail "arming a fresh cooldown must not itself file"
LATER=$((NOW + 3601))
jq --arg s "$(iso $((LATER - 30)))" '.[0].metadata["gc.campaign_sentinel_at"] = $s' "$COORD" > "$COORD.next" \
  && mv "$COORD.next" "$COORD"
FACTORY_GUARD_NOW=$LATER
out=$(guard)
FACTORY_GUARD_NOW=$NOW
grep -q "filed liveness defect af-live1" <<<"$out" \
  || { echo "$out" >&2; fail "an expired cooldown on a still-stale campaign never re-pinged"; }
[ "$(creates)" = "$((before + 1))" ] || fail "the expired-cooldown ping was not filed exactly once"

# 4. the wake loop itself is silent ----------------------------------------------
coord 1800 60
out=$(guard --check-only)
grep -q "wake loop silent for 30 min" <<<"$out" || { echo "$out" >&2; fail "silent sentinel not flagged"; }

# 5. a deliberate pause is not a defect -------------------------------------------
coord 30 99999 blocked admin "Fenêtre de maintenance"
out=$(guard --check-only)
grep -q "· liveness — paused on purpose (admin): Fenêtre de maintenance" <<<"$out" \
  || { echo "$out" >&2; fail "admin pause not recognised"; }
grep -q "! liveness" <<<"$out" && fail "a deliberate pause was reported as a liveness defect"

# ...but a durable failure is.
coord 30 60 blocked durable_failure "sentinelle en échec"
out=$(guard --check-only)
grep -q "liveness — campaign stopped by a durable failure" <<<"$out" || fail "durable failure not flagged"
[ "$(creates)" = "3" ] || fail "--check-only must not file a durable-failure defect either"

# C2: unlike silent/stale, a durable failure was never filed nor paged to a
# human -- only re-reported forever. The default run must file it and mail
# both the Mayor and Benjamin (the one escalation contract).
: > "$CALLS"
out=$(guard)
grep -q "filed liveness defect af-live1" <<<"$out" || { echo "$out" >&2; fail "durable failure not filed"; }
grep -q "^mail send mayor --notify" "$CALLS" || fail "durable failure did not page the Mayor"
grep -q "^mail send human --notify" "$CALLS" || fail "durable failure did not page Benjamin (C2)"
[ "$(jq -r '.[0].metadata["gc.needs_benjamin"]' "$COORD")" != "null" ] \
  || fail "durable failure did not set gc.needs_benjamin"
out=$(guard)
grep -q "already filed: af-live1" <<<"$out" || fail "a second durable-failure run should recognise the open defect"
[ "$(creates)" = "1" ] || fail "the durable-failure defect was filed more than once"

# 6. an unreadable store is flagged but never filed (it could not be) -------------
before=$(creates)
out=$(LIVENESS_STORE_DOWN=1 guard)
grep -q "liveness — coordination bead unreadable" <<<"$out" || { echo "$out" >&2; fail "store outage not flagged"; }
[ "$(creates)" = "$before" ] || fail "tried to file a defect into an unreachable store"

# 6b. replay of 2026-09-18 03:21Z-08:30Z (af-9ur0s/af-umyad): a stale
# campaign must name WHY nothing advances instead of only "up but not
# advancing" -- first the provider cause, then the mayor-session cause, then
# an honest "cause unknown" when neither is provable.
mkdir -p "$TMP/city/config" "$TMP/city/.gc"
cat > "$TMP/city/config/provider-policy.json" <<POLICY
{
  "contract": "agent-factory-provider-policy/v1",
  "unknown_reset_minutes": 60, "low_percent": 20, "low_hold_minutes": 30,
  "pools": {"p1": {"label": "Pool 1"}},
  "providers": {"prov1": {"pool": "p1", "label": "Prov 1"}},
  "targets": {
    "workspace": {"label": "Workspace", "chain": ["prov1"]},
    "mayor": {"label": "Mayor", "chain": ["prov1"]}
  }
}
POLICY

# 6b-i. no provider available: a DETECTED exhaustion with no known reset,
# marked hours ago -- the exact shape that misled a PO session live.
jq -n --arg until "$(iso $((NOW + 3600)))" --arg at "$(iso $((NOW - 3 * 3600)))" '
  {contract:"agent-factory-provider-state/v1", auto:true,
   pools:{p1:{status:"exhausted", until:$until, source:"detected",
              evidence:"You have hit your session limit", at:$at,
              reset_known:false, strikes:3}},
   disabled:{}, forced:{}, chains:{}, effective:{}, parked:false,
   sessions:[], sessions_at:null, model_staleness:{}, history:[]}' \
  > "$TMP/city/.gc/provider-state.json"
coord 30 5400
out=$(guard --check-only)
grep -q "aucun fournisseur disponible" <<<"$out" || { echo "$out" >&2; fail "provider-unavailable cause not stated"; }
grep -q "marque suspecte" <<<"$out" || { echo "$out" >&2; fail "a stale DETECTED mark was not flagged suspect"; }

# 6b-ii. pool cleared, Mayor session quarantined -----------------------------
rm -f "$TMP/city/.gc/provider-state.json"
echo '{"sessions":[{"id":"af-m1","alias":"mayor","state":"quarantined","state_reason":"provider config rejected","last_active":"'"$(iso $((NOW - 40 * 60)))"'"}]}' > "$SESSIONS"
out=$(guard --check-only)
grep -q "le Mayor ne démarre pas" <<<"$out" || { echo "$out" >&2; fail "mayor-session-down cause not stated"; }

# 6b-iii. neither is provable -------------------------------------------------
echo '{"sessions":[]}' > "$SESSIONS"
out=$(guard --check-only)
grep -q "cause inconnue" <<<"$out" || { echo "$out" >&2; fail "an unprovable cause did not fall back to 'cause inconnue'"; }

# 6c. the Mayor session itself, quarantined past the grace window, is paged
# once per streak -- it cannot receive the 'mail send mayor' page above.
: > "$CALLS"
echo '{"sessions":[{"id":"af-m1","alias":"mayor","state":"quarantined","state_reason":"provider config rejected","last_active":"'"$(iso $((NOW - 40 * 60)))"'"}]}' > "$SESSIONS"
guard >/dev/null
grep -q "^mail send human --notify" "$CALLS" || { cat "$CALLS" >&2; fail "a quarantined Mayor session was not paged"; }
[ "$(grep -c '^mail send human --notify' "$CALLS")" = "1" ] || fail "the mayor-session-down page fired more than once"
: > "$CALLS"
guard >/dev/null
grep -q "^mail send human --notify" "$CALLS" && fail "the same down streak paged a second time"
echo '{"sessions":[]}' > "$SESSIONS"

# 7. outside a city root the check stands down ------------------------------------
mkdir -p "$TMP/plain" && git -C "$TMP/plain" init -q
: > "$CALLS"
out=$(FACTORY_ROOT="$TMP/plain" "$GUARD" --check-only 2>&1 || true)
grep -q "· liveness — not checked" <<<"$out" || { echo "$out" >&2; fail "liveness ran outside a city"; }
grep -q 'af-1vr4' "$CALLS" && fail "a non-city run touched the coordination bead"

echo "OK factory-guard checks liveness, not only health"
