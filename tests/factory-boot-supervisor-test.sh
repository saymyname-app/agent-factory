#!/usr/bin/env bash
#
# bin/factory-boot starts a stopped supervisor through its systemd unit when
# that unit is installed, and only otherwise with `gc supervisor start`
# (af-v9t5vz).
#
# On 2026-10-08, 05:22 Paris, factory-boot brought the Factory back after an
# unrequested stop with `gc supervisor start`, which forks a supervisor
# outside systemd. `gc start` then enabled the installed unit, which found
# the place taken and failed, restarted by systemd every 5 seconds (84
# failed starts in 7 minutes), while the supervisor that did run lacked the
# unit's environment.
#
# Everything is fake: gc, systemctl and the scripts factory-boot calls.
#   1. supervisor down, unit installed   -> systemctl --user start <unit>,
#                                           never `gc supervisor start`
#   2. supervisor down, no unit          -> `gc supervisor start`
#   3. supervisor already running        -> neither
#   4. unit installed, but its start does not bring the supervisor up
#                                        -> the step fails, and says so

set -Eeuo pipefail
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SELF=$(basename -- "${BASH_SOURCE[0]}")
BOOT="$REPO_ROOT/bin/factory-boot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

ROOT="$TMP/city"
STUB="$TMP/stub"
CALLS="$TMP/calls.log"
SUPERVISOR="$TMP/supervisor-state"   # "up" or "down"
UNIT="$TMP/unit-state"               # "installed", "absent" or "broken"
mkdir -p "$ROOT/bin" "$ROOT/.gc/runtime" "$STUB"
for name in provider-failover factory-build-gates cockpit; do
  printf '#!/usr/bin/env bash\nexit 0\n' > "$ROOT/bin/$name"
  chmod +x "$ROOT/bin/$name"
done

cat > "$STUB/gc" <<STUBEOF
#!/usr/bin/env bash
case "\$*" in
  "supervisor status")
    if [ "\$(cat "$SUPERVISOR")" = up ]; then echo "Supervisor is running (PID 4242)"; exit 0; fi
    echo "Supervisor is not running"; exit 1 ;;
  "supervisor start")
    printf 'gc supervisor start\n' >> "$CALLS"; echo up > "$SUPERVISOR" ;;
  "status --json")
    echo '{"running": true, "suspended": false}' ;;
  *) printf 'gc %s\n' "\$*" >> "$CALLS" ;;
esac
STUBEOF
cat > "$STUB/systemctl" <<STUBEOF
#!/usr/bin/env bash
case "\$*" in
  "--user cat gascity-supervisor.service")
    [ "\$(cat "$UNIT")" != absent ] ;;
  "--user start gascity-supervisor.service")
    printf 'systemctl start\n' >> "$CALLS"
    [ "\$(cat "$UNIT")" = installed ] && echo up > "$SUPERVISOR"
    exit 0 ;;
  *) printf 'systemctl %s\n' "\$*" >> "$CALLS" ;;
esac
STUBEOF
chmod +x "$STUB"/*

boot() {  # boot <supervisor up|down> <unit installed|absent|broken>
  : > "$CALLS"
  echo "$1" > "$SUPERVISOR"
  echo "$2" > "$UNIT"
  env FACTORY_ROOT="$ROOT" GC_BIN="$STUB/gc" SYSTEMCTL_BIN="$STUB/systemctl" \
    FACTORY_BOOT_LOG="$TMP/factory-boot.log" FACTORY_BOOT_LOCK="$TMP/factory-boot.lock" \
    FACTORY_BOOT_WAIT_SECONDS=1 FACTORY_BOOT_SUPERVISOR_WAIT_SECONDS=1 "$BOOT"
}
calls() { cat "$CALLS"; }

out=$(boot down installed) || fail "1: factory-boot failed: $out"
[ "$(calls)" = "systemctl start" ] || fail "1: with the unit installed the supervisor starts through systemd only, got:
$(calls)"
[ "$(cat "$SUPERVISOR")" = up ] || fail "1: the supervisor is still down"

out=$(boot down absent) || fail "2: factory-boot failed: $out"
[ "$(calls)" = "gc supervisor start" ] || fail "2: without a unit the supervisor starts with gc supervisor start, got:
$(calls)"

out=$(boot up installed) || fail "3: factory-boot failed: $out"
[ -z "$(calls)" ] || fail "3: a running supervisor is not started again, got: $(calls)"
grep -q 'supervisor already running' <<<"$out" || fail "3: the boot log does not say the supervisor was already running"

if out=$(boot down broken); then fail "4: a unit that does not bring the supervisor up must fail the boot"; fi
grep -q 'FAILED supervisor start' <<<"$out" || fail "4: the failed start is not reported: $out"
[ "$(calls)" = "systemctl start" ] || fail "4: a second supervisor must not be forked beside a unit that failed, got:
$(calls)"

echo "PASS: $SELF"
