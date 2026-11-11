#!/usr/bin/env bash
#
# A fragment of an isolated-city trial, run without the trial's environment,
# cannot stop a supervisor (af-v9t5vz).
#
# On 2026-10-08 a worker built a probe from two `sed -n` ranges of
# tests/convoy-advance-isolated-city-test.sh. The first range began one line
# after `cleanup() {`: the cleanup body became plain top-level commands and
# ran before the lines that point GC_HOME at the trial directory. Its bare
# `gc supervisor stop` stopped the live supervisor; the Factory stayed down
# 56 minutes.
#
# This test replays that mistake on every tests/*-isolated-city-test.sh,
# with a fake `gc` that only records what it is asked:
#   1. no test script stops a city or a supervisor except through
#      isolated_city_stop (tests/lib/isolated-city.sh), and every
#      isolated-city trial sources that file;
#   2. the cleanup body of each trial, run as top-level commands in a
#      session-like environment, asks gc for nothing -- without the helper,
#      and with the helper but without the trial's GC_HOME;
#   3. the helper itself stops the trial's city and supervisor when GC_HOME
#      is inside the trial directory, and refuses every other case;
#   4. every trial disables the imported bd.dog pool, and the helper writes
#      that patch once only inside the trial city.
#   5. latest-failure retention replaces only an earlier sibling trial with
#      the same prefix and refuses unsafe targets.
#   6. every trial waits through isolated_city_wait_for, never on a
#      wall-clock deadline of its own, and that wait counts host time: a
#      second at twice the CPUs counts half, up to a stretch ceiling, and
#      giving up names the load (af-2crkwu).

set -Eeuo pipefail
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SELF=$(basename -- "${BASH_SOURCE[0]}")
HELPER="$REPO_ROOT/tests/lib/isolated-city.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

# --- fakes: gc records its arguments; nothing else reaches the host ---------
STUB="$TMP/stub"
CALLS="$TMP/gc-calls.log"
mkdir -p "$STUB" "$TMP/home"
cat > "$STUB/gc" <<STUBEOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$CALLS"
STUBEOF
# host-process: allow — the names of the stubs written below, not calls
for name in tmux pkill pgrep systemctl; do
  printf '#!/usr/bin/env bash\nexit 1\n' > "$STUB/$name"
done
chmod +x "$STUB"/*
GC_BIN="$STUB/gc"
export GC_BIN

# What a Gas City session exports: a GC_HOME that is the live one, never the
# trial's. Here it is a directory of this test.
LIVE_HOME="$TMP/live-gc-home"
run_fragment() {  # run_fragment <script>
  env -u XDG_RUNTIME_DIR HOME="$TMP/home" GC_HOME="$LIVE_HOME" \
    PATH="$STUB:/usr/bin:/bin" bash "$1" >/dev/null 2>&1 || true
}

shopt -s nullglob
trials=("$REPO_ROOT"/tests/*-isolated-city-test.sh)
[ "${#trials[@]}" -gt 0 ] || fail "no tests/*-isolated-city-test.sh found: this check would pass on nothing"

# --- 1. one way to stop, in every test script -------------------------------
STOP_RE='(^|[^[:alnum:]_.-])gc([[:space:]]+--city[[:space:]]+[^[:space:]]+)?[[:space:]]+(supervisor[[:space:]]+)?stop([^[:alnum:]_-]|$)'
for f in "$REPO_ROOT"/tests/*.sh; do
  [ "$(basename -- "$f")" != "$SELF" ] || continue
  bare=$(grep -vE '^[[:space:]]*#' "$f" | grep -nE "$STOP_RE" || true)
  [ -z "$bare" ] || fail "$(basename -- "$f") stops a city or a supervisor without isolated_city_stop (tests/lib/isolated-city.sh):
$bare"
done
for f in "${trials[@]}"; do
  grep -qE '^\. "\$ROOT/tests/lib/isolated-city\.sh"$' "$f" \
    || fail "$(basename -- "$f") does not source tests/lib/isolated-city.sh"
  grep -qE '^[[:space:]]+isolated_city_stop "\$TRIAL" "\$CITY"' "$f" \
    || fail "$(basename -- "$f") does not stop its trial through isolated_city_stop"
  grep -qE '^isolated_city_disable_dog "\$TRIAL" "\$CITY"$' "$f" \
    || fail "$(basename -- "$f") does not disable bd.dog in its isolated city"
done

# --- 2. the incident, replayed on each trial ---------------------------------
for f in "${trials[@]}"; do
  name=$(basename -- "$f")
  start=$(grep -n -m 1 '^cleanup() {$' "$f" | cut -d: -f1)
  end=$(grep -n -m 1 '^trap cleanup EXIT$' "$f" | cut -d: -f1)
  [ -n "$start" ] && [ -n "$end" ] && [ "$end" -gt "$start" ] \
    || fail "$name: no cleanup() { ... } followed by 'trap cleanup EXIT' to replay"
  for variant in without-helper with-helper; do
    : > "$CALLS"
    {
      echo '#!/usr/bin/env bash'
      echo 'set -Eeuo pipefail'
      echo "TRIAL=\$(mktemp -d \"$TMP/trial.XXXXXX\"); CITY=\"\$TRIAL/c\""
      [ "$variant" = without-helper ] || echo ". \"$HELPER\""
      # As on 2026-10-08: the range starts one line after `cleanup() {`.
      sed -n "$((start + 1)),${end}p" "$f"
    } > "$TMP/probe.sh"
    grep -q 'isolated_city_stop' "$TMP/probe.sh" || fail "$name: the replayed fragment holds no stop at all"
    run_fragment "$TMP/probe.sh"
    [ ! -s "$CALLS" ] || fail "$name ($variant): a fragment of its cleanup, run outside the trial, reached gc:
$(cat "$CALLS")"
  done
done

# --- 3. the helper ------------------------------------------------------------
# shellcheck source=tests/lib/isolated-city.sh
. "$HELPER"
PATH="$STUB:$PATH"
trial="$TMP/a-trial"
mkdir -p "$trial/h" "$trial/c" "$TMP/elsewhere"

refused() {  # refused <label> <GC_HOME or -> <trial>
  : > "$CALLS"
  if [ "$2" = - ]; then
    ( unset GC_HOME; isolated_city_stop "$3" "$3/c" ) 2>/dev/null && fail "$1: the stop was not refused"
  else
    ( GC_HOME="$2" isolated_city_stop "$3" "$3/c" ) 2>/dev/null && fail "$1: the stop was not refused"
  fi
  [ ! -s "$CALLS" ] || fail "$1: refused, yet gc was asked: $(cat "$CALLS")"
}
refused "GC_HOME unset" - "$trial"
refused "GC_HOME of another home" "$LIVE_HOME" "$trial"
refused "GC_HOME equal to the trial directory" "$trial" "$trial"
refused "GC_HOME leaving the trial directory by .." "$trial/../elsewhere" "$trial"
refused "GC_HOME with the trial directory as a mere prefix" "$trial-other/h" "$trial"
refused "no trial directory" "$trial/h" ""
refused "trial directory /" "$trial/h" "/"

: > "$CALLS"
( GC_HOME="$trial/h" isolated_city_stop "$trial" "$trial/c" ) || fail "the stop of a trial was refused inside its own environment"
expected=$(printf '%s\n' "--city $trial/c stop" "supervisor stop")
[ "$(cat "$CALLS")" = "$expected" ] || fail "inside the trial, expected the city then the supervisor to be stopped, got:
$(cat "$CALLS")"

: > "$CALLS"
( GC_HOME="$trial/h" isolated_city_stop "$trial" "" ) || fail "the supervisor of a trial was not stopped when no city is named"
[ "$(cat "$CALLS")" = "supervisor stop" ] || fail "a city outside the trial directory must not be stopped, got:
$(cat "$CALLS")"

# --- 4. imported maintenance agents are absent from delivery trials ----------
city="$trial/c"
printf '[workspace]\nprovider = "stub"\n' > "$city/city.toml"
isolated_city_disable_dog "$trial" "$city" || fail "the bd.dog patch was refused inside the trial"
isolated_city_disable_dog "$trial" "$city" || fail "the idempotent bd.dog patch was refused"
[ "$(grep -c '^# isolated-city: disable bd.dog$' "$city/city.toml")" = 1 ] \
  || fail "the bd.dog patch was not written exactly once: $(cat "$city/city.toml")"
grep -qE '^name = "dog"$' "$city/city.toml" || fail "the bd.dog patch names no dog agent"
grep -qE '^max_active_sessions = 0$' "$city/city.toml" || fail "the bd.dog patch does not disable the pool"

before=$(cat "$city/city.toml")
if isolated_city_disable_dog "$trial" "$TMP/elsewhere" 2>/dev/null; then
  fail "the bd.dog patch accepted a city outside the trial"
fi
[ "$(cat "$city/city.toml")" = "$before" ] || fail "a refused bd.dog patch changed the trial city"

# --- 5. a failed trial keeps one safely rotated diagnostic directory ------
evidence="$TMP/evidence"
latest="$evidence/af-rx0ocp-correction.last-failure"
first="$evidence/af-rx0ocp-correction.first"
second="$evidence/af-rx0ocp-correction.second"
mkdir -p "$first" "$second"
echo first > "$first/record"
echo second > "$second/record"
isolated_city_preserve_latest_failure "$first" "$latest" \
  || fail "the first failed trial was not preserved"
[ "$(readlink -- "$latest")" = "$first" ] \
  || fail "the latest-failure link does not name the first trial"
isolated_city_preserve_latest_failure "$second" "$latest" \
  || fail "the second failed trial did not replace the first"
[ ! -e "$first" ] || fail "the previous failed trial was not removed"
[ "$(readlink -- "$latest")" = "$second" ] \
  || fail "the latest-failure link does not name the second trial"

unsafe="$TMP/outside"
mkdir -p "$unsafe"
rm -f -- "$latest"
ln -s -- "$unsafe" "$latest"
if isolated_city_preserve_latest_failure "$second" "$latest" 2>/dev/null; then
  fail "latest-failure retention accepted a target outside its directory"
fi
[ -d "$unsafe" ] || fail "a refused latest-failure rotation removed its unsafe target"

rm -f -- "$latest"
echo occupied > "$latest"
if isolated_city_preserve_latest_failure "$second" "$latest" 2>/dev/null; then
  fail "latest-failure retention replaced a regular file"
fi
[ "$(cat "$latest")" = occupied ] || fail "a refused rotation changed a regular file"

# --- 6. a trial waits in host time, through the one helper (af-2crkwu) -------
for f in "${trials[@]}"; do
  own=$(grep -nE 'date \+%s\) \+ ' "$f" || true)
  [ -z "$own" ] || fail "$(basename -- "$f") waits on a wall-clock deadline of its own instead of isolated_city_wait_for:
$own"
done

LOAD="$TMP/loadavg"
export ISOLATED_CITY_LOADAVG_FILE="$LOAD" ISOLATED_CITY_CPUS=8 ISOLATED_CITY_WAIT_INTERVAL=0.1
never() { return 1; }
waited() {  # waited <load> <stretch> <seconds>: wall-clock ms until it gave up
  local start
  echo "$1 $1 $1 1/100 1" > "$LOAD"
  start=$(date +%s%3N)
  if ISOLATED_CITY_WAIT_STRETCH_MAX=$2 isolated_city_wait_for "$3" never 2>"$TMP/gave-up"; then
    fail "a command that never succeeds was waited for successfully"
  fi
  echo $(( $(date +%s%3N) - start ))
}
ms=$(waited 4.00 4 1)
[ "$ms" -ge 1000 ] && [ "$ms" -lt 1800 ] || fail "below its CPUs, the host gave 1 s of wait in ${ms} ms of wall clock"
grep -qF 'gave up after 1s of wall clock for 1s of host time (load 4.00 on 8 CPUs): never' "$TMP/gave-up" \
  || fail "the give-up does not name the wall clock and the load: $(cat "$TMP/gave-up")"
ms=$(waited 16.00 4 1)
[ "$ms" -ge 2000 ] && [ "$ms" -lt 2800 ] || fail "at twice its CPUs, the host gave 1 s of wait in ${ms} ms instead of about 2 s"
ms=$(waited 80.00 2 1)
[ "$ms" -ge 2000 ] && [ "$ms" -lt 2800 ] || fail "the wait was stretched past twice its seconds: ${ms} ms"

echo "4.00 4.00 4.00 1/100 1" > "$LOAD"
calls="$TMP/calls"; : > "$calls"
third() { echo . >> "$calls"; [ "$(wc -l < "$calls")" -ge 3 ]; }
isolated_city_wait_for 5 third || fail "a command that succeeds on its third run was not waited for"
[ "$(wc -l < "$calls")" = 3 ] || fail "the command ran $(wc -l < "$calls") times instead of 3"

echo "PASS: $SELF"
