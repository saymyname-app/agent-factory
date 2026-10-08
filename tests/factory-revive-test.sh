#!/usr/bin/env bash
#
# bin/factory-revive restarts a supervisor nobody stopped on purpose, and
# leaves a deliberate stop alone (af-v9t5vz).
#
# Everything is fake: `gc supervisor status` reads a file, factory-boot is a
# stub that records its call and may bring the fake supervisor back, `bd`
# and the escalation door record theirs, systemctl too. Nothing of the host
# is read or touched.
#
#   1. supervisor answers                      -> nothing is run
#   2. down, city not registered (gc stop)     -> nothing is run, one log line
#   3. down, city registered                   -> factory-boot once, one bead,
#                                                 one Mayor-first escalation
#   4. down, but back within the grace delay   -> nothing is run
#   5. down, factory-boot fails                -> exit 1, no bead, retried
#   6. check                                   -> verdict only
#   7. install / uninstall                     -> the timer units, written for
#                                                 the registered city only

set -Eeuo pipefail
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SELF=$(basename -- "${BASH_SOURCE[0]}")
REVIVE="$REPO_ROOT/bin/factory-revive"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

CITY="$TMP/city"
STUB="$TMP/stub"
CALLS="$TMP/calls.log"
SUPERVISOR="$TMP/supervisor-state"   # "up" or "down"
BOOT_EFFECT="$TMP/boot-effect"       # what the fake factory-boot does: "up" or "nothing"
mkdir -p "$CITY/.gc/runtime" "$STUB" "$TMP/gc-home" "$TMP/units"

cat > "$STUB/gc" <<STUBEOF
#!/usr/bin/env bash
if [ "\$1 \$2" = "supervisor status" ]; then
  # The grace delay of case 4: the supervisor comes back between two looks.
  if [ -f "$TMP/back-at-second-look" ] && [ -f "$TMP/looked-once" ]; then echo up > "$SUPERVISOR"; fi
  : > "$TMP/looked-once"
  if [ "\$(cat "$SUPERVISOR")" = up ]; then echo "Supervisor is running (PID 4242)"; exit 0; fi
  echo "Supervisor is not running"; exit 1
fi
printf 'gc %s\n' "\$*" >> "$CALLS"
STUBEOF
cat > "$STUB/factory-boot" <<STUBEOF
#!/usr/bin/env bash
printf 'factory-boot\n' >> "$CALLS"
[ "\$(cat "$BOOT_EFFECT")" = up ] && echo up > "$SUPERVISOR"
exit 0
STUBEOF
cat > "$STUB/bd" <<STUBEOF
#!/usr/bin/env bash
printf 'bd %s\n' "\$1" >> "$CALLS"
echo af-revive1
STUBEOF
cat > "$STUB/escalation-door" <<STUBEOF
#!/usr/bin/env bash
printf 'escalation-door %s %s\n' "\$1" "\$2" >> "$CALLS"
STUBEOF
cat > "$STUB/systemctl" <<STUBEOF
#!/usr/bin/env bash
printf 'systemctl %s\n' "\$*" >> "$CALLS"
STUBEOF
chmod +x "$STUB"/*

register() { printf '[[cities]]\n  path = "%s"\n  name = "city"\n' "$CITY" > "$TMP/gc-home/cities.toml"; }
unregister() { : > "$TMP/gc-home/cities.toml"; }

revive() {
  env FACTORY_ROOT="$CITY" GC_HOME="$TMP/gc-home" GC_BIN="$STUB/gc" BD_BIN="$STUB/bd" \
    SYSTEMCTL_BIN="$STUB/systemctl" FACTORY_BOOT_BIN="$STUB/factory-boot" \
    ESCALATION_DOOR_BIN="$STUB/escalation-door" FACTORY_REVIVE_GRACE_SECONDS=0 \
    FACTORY_REVIVE_UNIT_DIR="$TMP/units" "$REVIVE" "$@"
}
reset() {  # reset <supervisor up|down> <boot effect up|nothing>
  : > "$CALLS"
  rm -f "$TMP/looked-once" "$TMP/back-at-second-look" "$CITY/.gc/runtime/factory-revive.state"
  : > "$CITY/.gc/runtime/factory-revive.log"
  echo "$1" > "$SUPERVISOR"
  echo "$2" > "$BOOT_EFFECT"
}
calls() { cat "$CALLS"; }
log_lines() { grep -c "$1" "$CITY/.gc/runtime/factory-revive.log" || true; }

# 1. the supervisor answers
register; reset up up
revive run >/dev/null || fail "1: a running supervisor is not an error"
[ -z "$(calls)" ] || fail "1: a running supervisor must leave everything alone, got: $(calls)"

# 2. deliberate stop: gc stop took the city off the list
unregister; reset down up
revive run >/dev/null || fail "2: a deliberate stop is not an error"
revive run >/dev/null || fail "2: a deliberate stop is not an error (second run)"
[ -z "$(calls)" ] || fail "2: a deliberate stop must not be undone, got: $(calls)"
[ "$(cat "$SUPERVISOR")" = down ] || fail "2: the supervisor of a deliberate stop was restarted"
[ "$(log_lines 'deliberate stop')" = 1 ] || fail "2: a deliberate stop is logged once, not at every run"

# 3. the incident: supervisor down, city still registered
register; reset down up
revive run >/dev/null || fail "3: a successful revival must exit 0"
expected=$(printf '%s\n' "factory-boot" "bd create" "escalation-door mayor af-revive1")
[ "$(calls)" = "$expected" ] || fail "3: expected factory-boot, one bead, one Mayor-first escalation, got:
$(calls)"
[ "$(cat "$SUPERVISOR")" = up ] || fail "3: the supervisor is still down"
[ "$(log_lines 'REVIVE')" = 1 ] || fail "3: the revival is not in the log"
: > "$CALLS"
revive run >/dev/null || fail "3: the run after a revival must exit 0"
[ -z "$(calls)" ] || fail "3: once the supervisor answers again nothing more is run, got: $(calls)"

# 4. a restart was already under way
register; reset down up
: > "$TMP/back-at-second-look"
revive run >/dev/null || fail "4: a supervisor back within the grace delay is not an error"
[ -z "$(calls)" ] || fail "4: a supervisor back within the grace delay needs nothing, got: $(calls)"

# 5. factory-boot does not bring it back
register; reset down nothing
if revive run >/dev/null; then fail "5: a failed revival must exit non-zero"; fi
[ "$(calls)" = "factory-boot" ] || fail "5: a failed revival files nothing, got: $(calls)"
if revive run >/dev/null; then fail "5: a second failed revival must exit non-zero"; fi
[ "$(calls)" = "$(printf '%s\n' factory-boot factory-boot)" ] || fail "5: a failed revival is tried again at the next run, got: $(calls)"

# 6. check says, and does nothing
register; reset down up
if out=$(revive check); then fail "6: check must exit 1 on a stop nobody asked for"; fi
grep -q 'nobody asked' <<<"$out" || fail "6: check does not name the unrequested stop: $out"
unregister
out=$(revive check) || fail "6: check must exit 0 on a deliberate stop"
grep -q 'deliberate' <<<"$out" || fail "6: check does not name the deliberate stop: $out"
echo up > "$SUPERVISOR"
revive check >/dev/null || fail "6: check must exit 0 when the supervisor answers"
[ -z "$(calls)" ] || fail "6: check must run nothing, got: $(calls)"

# 7. the timer
unregister; reset up up
if revive install >/dev/null 2>&1; then fail "7: install must refuse a root that is not the registered city"; fi
[ ! -e "$TMP/units/factory-revive.timer" ] || fail "7: a refused install wrote a unit"
register
revive install >/dev/null || fail "7: install failed for the registered city"
grep -qF "\"$CITY/bin/factory-revive\" run" "$TMP/units/factory-revive.service" || fail "7: the service does not run the city's own factory-revive"
grep -q '^OnUnitActiveSec=5min$' "$TMP/units/factory-revive.timer" || fail "7: the timer does not fire every 5 minutes"
expected=$(printf '%s\n' "systemctl --user daemon-reload" "systemctl --user enable --now factory-revive.timer")
[ "$(calls)" = "$expected" ] || fail "7: install must reload systemd then enable the timer, got:
$(calls)"
revive uninstall >/dev/null || fail "7: uninstall failed"
[ ! -e "$TMP/units/factory-revive.timer" ] && [ ! -e "$TMP/units/factory-revive.service" ] || fail "7: uninstall left a unit behind"

echo "PASS: $SELF"
