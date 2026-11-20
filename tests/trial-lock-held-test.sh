#!/usr/bin/env bash
#
# A test city outlives no trial, however the trial ends (af-myowqa,
# docs/DEFECT_CLASSES.md, P).
#
# Every test that starts a real city stops it in its cleanup, but a cleanup
# runs only when the trial lives to run it. On 20/11/2026 three test cities
# whose trial had ended ran up to 8 h 52 under systemd --user, their Dolt at
# 20 to 49 %, and held the host at a load of 20 on 8 cores: six orders
# failed their budget. Now a trial holds its trial lock (lib/trial_lock.py)
# for as long as it lives, and `bin/project-launch sweep` stops what a trial
# whose lock is free left to init.
#
#   1. every test that kills its trial's processes by path holds the trial
#      lock of that path: isolated_city_hold_trial (tests/lib/isolated-city.sh)
#      in a shell test, trial_lock.hold in a Python one; a test that does
#      not is refused;
#   2. a trial killed with SIGKILL frees its lock and keeps its lock file;
#      the sweep then stops the city process it left to init, found by its
#      GC_HOME though it works from /, and stops nothing while the trial
#      lives;
#   3. a trial that ends after removing its directory leaves no lock file,
#      stopped with its whole group by a caller's deadline too.

set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SELF=$(basename -- "${BASH_SOURCE[0]}")
TMP=$(mktemp -d)
PIDS=()
cleanup() {
  for pid in ${PIDS[@]+"${PIDS[@]}"}; do kill -9 "$pid" 2>/dev/null || true; done
  rm -rf -- "$TMP"
}
trap cleanup EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

# --- 1. every test that kills by path holds its trial lock -------------------
# The variables a shell test kills by path (`pkill [-9] -f -- "$VAR...`) and
# does not hold the trial lock of.
# host-process: allow — the pattern of the check, not a call
KILL_BY_PATH='pkill[^|;]*-f[[:space:]]+--[[:space:]]+"\$\{?[A-Za-z_]+'
unheld_shell() {
  local var
  for var in $(grep -vE '^[[:space:]]*#' "$1" | grep -oE "$KILL_BY_PATH" \
      | grep -oE '[A-Za-z_]+$' | sort -u); do
    grep -qE "^[[:space:]]*isolated_city_hold_trial \"\\\$\\{?$var\\}?\"" "$1" || printf '%s\n' "$var"
  done
}
unheld_python() {
  # host-process: allow — the pattern of the check, not a call
  grep -qE '"pkill",[[:space:]]*("-[A-Za-z0-9]+",[[:space:]]*)*"-f",[[:space:]]*"--"' "$1" \
    && ! grep -qE 'trial_lock\.hold\(' "$1"
}

for f in "$ROOT"/tests/*.sh; do
  case "$(basename -- "$f")" in
    "$SELF") continue ;;
    # Its pkill lines are fixtures of its own lint, never run.
    host-wide-process-check-test.sh) continue ;;
  esac
  missing=$(unheld_shell "$f")
  [ -z "$missing" ] || fail "$(basename -- "$f") kills its trial's processes by path (\$$missing) without holding its trial lock: call isolated_city_hold_trial \"\$$missing\" (tests/lib/isolated-city.sh) right after making it"
done
for f in "$ROOT"/tests/*.py; do
  ! unheld_python "$f" || fail "$(basename -- "$f") kills its trial's processes by path without holding its trial lock (lib/trial_lock.py, trial_lock.hold)"
done

# The check refuses what it is there to refuse.
printf 'TRIAL=$(mktemp -d)\ncleanup() { pkill -f -- "$TRIAL/" || true; }\n' > "$TMP/unheld.sh"
[ "$(unheld_shell "$TMP/unheld.sh")" = TRIAL ] || fail "the check accepts a shell test that kills by path without its trial lock"
printf 'subprocess.run(["pkill", "-9", "-f", "--", str(trial) + "/"])\n' > "$TMP/unheld.py"
unheld_python "$TMP/unheld.py" || fail "the check accepts a Python test that kills by path without its trial lock"
echo "OK 1: every test that kills its trial's processes by path holds its trial lock"

# --- 2. a killed trial's city is stopped by the sweep -------------------------
WORK_ROOT="$TMP/root"
TRIAL="$WORK_ROOT/af-trial.XXXX"
mkdir -p "$TRIAL"
cat > "$TMP/trial.sh" <<EOF
. "$ROOT/tests/lib/isolated-city.sh"
isolated_city_hold_trial "$TRIAL"
# A city process that works from / and is handed to init at once.
( cd /; GC_HOME="$TRIAL/h" setsid sleep 300 </dev/null >/dev/null 2>&1 & echo \$! > "$TMP/city.pid" )
echo ready
exec sleep 300
EOF
coproc TRIAL_SHELL { exec bash "$TMP/trial.sh"; }
trial_pid=$TRIAL_SHELL_PID
PIDS+=("$trial_pid")
read -r -t 30 ready <&"${TRIAL_SHELL[0]}" || true
[ "${ready:-}" = ready ] || fail "the trial did not start"
city=$(cat "$TMP/city.pid")
PIDS+=("$city")

sweep() {
  FACTORY_LAUNCH_TRACE="$TMP/stops.jsonl" TMPDIR="$TMP" \
    "$ROOT/bin/project-launch" sweep --launch-id none --work-root "$WORK_ROOT"
}
lock_free() { flock -n "$TRIAL.trial" true 2>/dev/null; }

lock_free && fail "the trial lock is free while the trial lives"
stopped=$(sweep | jq -c '.stopped')
[ "$stopped" = "[]" ] || fail "the sweep stopped a process of a trial that lives: $stopped"

kill -9 "$trial_pid"
wait "$trial_pid" 2>/dev/null || true
for _ in $(seq 50); do lock_free && break; sleep 0.1; done
lock_free || fail "the trial lock is still held 5 s after the trial was killed"
[ -e "$TRIAL.trial" ] || fail "the lock file of a killed trial whose directory is there was removed: the sweep cannot see it ended"

stopped=$(sweep | jq -c --argjson city "$city" '[.stopped[] | select(.pids | index($city)) | [.reason, .stopped]]')
[ "$stopped" = '[["trial_gone",true]]' ] || fail "the sweep did not stop the city of a killed trial by its GC_HOME: $stopped"
for _ in $(seq 50); do kill -0 "$city" 2>/dev/null || break; sleep 0.1; done
! kill -0 "$city" 2>/dev/null || fail "the city of a killed trial is still alive after the sweep"
echo "OK 2: a killed trial frees its lock and the sweep stops the city it left"

# --- 3. a trial that removes its directory leaves no lock file ---------------
DONE="$WORK_ROOT/af-done.XXXX"
mkdir -p "$DONE"
bash -c ". '$ROOT/tests/lib/isolated-city.sh'; isolated_city_hold_trial '$DONE'; isolated_city_remove '$DONE'"
for _ in $(seq 50); do [ -e "$DONE.trial" ] || break; sleep 0.1; done
[ ! -e "$DONE.trial" ] || fail "a trial that removed its directory left its lock file"
# A deadline stops the trial's whole group, the lock's holder with it.
STOPPED="$WORK_ROOT/af-stopped.XXXX"
mkdir -p "$STOPPED"
timeout 3 bash -c ". '$ROOT/tests/lib/isolated-city.sh'; isolated_city_hold_trial '$STOPPED'
  trap \"isolated_city_remove '$STOPPED'\" EXIT; sleep 30" || true
for _ in $(seq 50); do [ -e "$STOPPED.trial" ] || break; sleep 0.1; done
[ ! -d "$STOPPED" ] || fail "the trial stopped by its deadline did not remove its directory"
[ ! -e "$STOPPED.trial" ] || fail "a trial stopped with its group by a deadline left its lock file"
echo "OK 3: a trial that removes its directory leaves no lock file"
