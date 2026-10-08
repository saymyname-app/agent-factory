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
#      is inside the trial directory, and refuses every other case.

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

echo "PASS: $SELF"
