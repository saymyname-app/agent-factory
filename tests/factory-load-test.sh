#!/usr/bin/env bash
# ci: local-only — drives the live `gc` binary, real CPU, and the city's bead store
#
# Raises CPU and gc load to a configurable level (N parallel `gc bd` readers
# plus synthetic CPU burn sized to the host) for a fixed window, sampling
# saymyname-product-status and mayor-campaign sentinel wall-clock durations
# throughout, and reports whether factory-guard/factory-watchdog/pr-autopilot
# emitted any order.failed events during the window (af-liak1).
#
# Usage:
#   tests/factory-load-test.sh [-n N] [-w SECONDS] [-o OUT_DIR]
#
#   -n N        parallel `gc bd list` readers plus N CPU-burn workers
#               (default: 6)
#   -w SECONDS  test window duration (default: 120)
#   -o OUT_DIR  where to write raw per-tick samples (default: mktemp -d)
#
# Exit codes:
#   0  every measured median <= half its timeout, and zero order.failed
#      events were observed for the window
#   1  a median exceeded half its timeout, or an order.failed event fired
#   2  usage / environment error (missing gc, not in a city, etc.)
#
# SAFETY: this test deliberately drives the host toward the load conditions
# that caused the 2026-09-17/18 incident (city.toml, af-48sx3). Before
# running with N>=4, check `uptime` and `free -h` — if the host is already
# heavily loaded, this test will make it worse, potentially disrupting real
# work in flight. Prefer a maintenance window with the Factory idle.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd "$ROOT"

N=6
WINDOW=120
OUT_DIR=""

while getopts "n:w:o:h" opt; do
  case "$opt" in
    n) N=$OPTARG ;;
    w) WINDOW=$OPTARG ;;
    o) OUT_DIR=$OPTARG ;;
    h)
      sed -n '2,25p' "$0"
      exit 0
      ;;
    *)
      echo "usage: $0 [-n N] [-w SECONDS] [-o OUT_DIR]" >&2
      exit 2
      ;;
  esac
done

command -v gc >/dev/null 2>&1 || { echo "factory-load-test: gc not found on PATH" >&2; exit 2; }
command -v jq >/dev/null 2>&1 || { echo "factory-load-test: jq not found on PATH" >&2; exit 2; }

if [ -z "$OUT_DIR" ]; then
  OUT_DIR=$(mktemp -d "${TMPDIR:-/tmp}/factory-load-test.XXXXXX")
fi
mkdir -p "$OUT_DIR"

STATUS_BIN="${SAYMYNAME_STATUS_BIN:-$ROOT/bin/saymyname-product-status}"
SENTINEL_CMD=("$ROOT/bin/mayor-campaign" "sentinel")
# Wall-clock timeouts these durations are checked against (see bin/mayor-campaign
# and orders/mayor-campaign.toml): the order-level timeout for the sentinel is
# 50s; saymyname-product-status is called from inside it with a 20s budget.
STATUS_TIMEOUT="${CAMPAIGN_STATUS_COMMAND_TIMEOUT:-20}"
SENTINEL_TIMEOUT=50

echo "factory-load-test: N=$N window=${WINDOW}s out_dir=$OUT_DIR" >&2
echo "factory-load-test: host before test:" >&2
uptime >&2 || true
free -h >&2 || true

PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" >/dev/null 2>&1 || true
  done
  wait >/dev/null 2>&1 || true
}
trap cleanup EXIT

# --- Load generators -------------------------------------------------------

# N synthetic CPU burners, sized to the host: each pins one core doing
# nothing useful, same shape as the rigs' Maven/Testcontainers runs that
# co-occurred with the incident.
for i in $(seq 1 "$N"); do
  ( while :; do :; done ) &
  PIDS+=($!)
done

# N parallel `gc bd` readers, same shape as concurrent pool-worker sessions
# each polling for work.
for i in $(seq 1 "$N"); do
  ( while :; do gc bd list --status open --limit 5 --json >/dev/null 2>&1; done ) &
  PIDS+=($!)
done

echo "factory-load-test: load generators started (2N=$((2 * N)) background workers)" >&2

# --- Sampling loop -----------------------------------------------------------

STATUS_SAMPLES="$OUT_DIR/status-durations.txt"
SENTINEL_SAMPLES="$OUT_DIR/sentinel-durations.txt"
FAILED_LOG="$OUT_DIR/order-failed-events.jsonl"
: >"$STATUS_SAMPLES"
: >"$SENTINEL_SAMPLES"
: >"$FAILED_LOG"

START_EPOCH=$(date +%s)
END_EPOCH=$((START_EPOCH + WINDOW))

time_cmd() {
  # Prints elapsed wall-clock seconds (float) for "$@" to stdout; discards
  # the command's own stdout/stderr — only timing and exit status matter here.
  local start end status
  start=$(date +%s.%N)
  if "$@" >/dev/null 2>&1; then
    status=0
  else
    status=$?
  fi
  end=$(date +%s.%N)
  awk -v s="$start" -v e="$end" 'BEGIN { printf "%.3f", (e - s) }'
  return "$status"
}

while [ "$(date +%s)" -lt "$END_EPOCH" ]; do
  d=$(time_cmd "$STATUS_BIN" --json) || true
  echo "$d" >>"$STATUS_SAMPLES"

  d=$(time_cmd "${SENTINEL_CMD[@]}") || true
  echo "$d" >>"$SENTINEL_SAMPLES"
done

# --- order.failed events during the window ----------------------------------

ELAPSED_SINCE="$((($(date +%s) - START_EPOCH) + 5))s"
gc events --type order.failed --since "$ELAPSED_SINCE" 2>/dev/null \
  >"$FAILED_LOG" || true

FAILED_COUNT=$(wc -l <"$FAILED_LOG" | tr -d ' ')

# --- Report ------------------------------------------------------------------

stats() {
  # Reads a newline-delimited list of floats on stdin, prints "min median max".
  sort -n | awk '
    { a[NR] = $1 }
    END {
      if (NR == 0) { print "n/a n/a n/a"; exit }
      min = a[1]; max = a[NR]
      mid = int((NR + 1) / 2)
      if (NR % 2 == 1) { med = a[mid] } else { med = (a[mid] + a[mid + 1]) / 2 }
      printf "%.3f %.3f %.3f\n", min, med, max
    }'
}

read -r STATUS_MIN STATUS_MED STATUS_MAX < <(stats <"$STATUS_SAMPLES")
read -r SENTINEL_MIN SENTINEL_MED SENTINEL_MAX < <(stats <"$SENTINEL_SAMPLES")

echo "" >&2
echo "factory-load-test: results (N=$N, window=${WINDOW}s)" >&2
printf '%-28s %10s %10s %10s %10s\n' "command" "min(s)" "median(s)" "max(s)" "timeout(s)"
printf '%-28s %10s %10s %10s %10s\n' "saymyname-product-status" "$STATUS_MIN" "$STATUS_MED" "$STATUS_MAX" "$STATUS_TIMEOUT"
printf '%-28s %10s %10s %10s %10s\n' "mayor-campaign sentinel" "$SENTINEL_MIN" "$SENTINEL_MED" "$SENTINEL_MAX" "$SENTINEL_TIMEOUT"
echo "order.failed events observed: $FAILED_COUNT" >&2

FAIL=0

if [ "$STATUS_MED" != "n/a" ]; then
  half=$(awk -v t="$STATUS_TIMEOUT" 'BEGIN { printf "%.3f", t / 2 }')
  if awk -v m="$STATUS_MED" -v h="$half" 'BEGIN { exit !(m > h) }'; then
    echo "FAIL: saymyname-product-status median ${STATUS_MED}s exceeds half its ${STATUS_TIMEOUT}s timeout" >&2
    FAIL=1
  fi
fi

if [ "$SENTINEL_MED" != "n/a" ]; then
  half=$(awk -v t="$SENTINEL_TIMEOUT" 'BEGIN { printf "%.3f", t / 2 }')
  if awk -v m="$SENTINEL_MED" -v h="$half" 'BEGIN { exit !(m > h) }'; then
    echo "FAIL: mayor-campaign sentinel median ${SENTINEL_MED}s exceeds half its ${SENTINEL_TIMEOUT}s timeout" >&2
    FAIL=1
  fi
fi

if [ "$FAILED_COUNT" -gt 0 ]; then
  echo "FAIL: $FAILED_COUNT order.failed event(s) observed during the window" >&2
  FAIL=1
fi

echo "factory-load-test: raw samples in $OUT_DIR" >&2

if [ "$FAIL" -eq 0 ]; then
  echo "PASS: sentinel and status stayed under half their timeouts, zero order.failed events"
  exit 0
else
  exit 1
fi
