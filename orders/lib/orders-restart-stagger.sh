#!/usr/bin/env bash
# T10 (af-u61al3): `gc`'s cooldown trigger fires the instant an order's
# interval has elapsed since its last run, with no coordination between
# orders. After the city is paused for a while (PC sleep, a deliberate
# stop), every cooldown order's interval has elapsed by the next controller
# tick, so they all fire in the same ~30s tick -- a restart burst. This
# script replaces an order's `cooldown` trigger with a `condition` trigger
# (check = this script) that reproduces plain elapsed>=interval gating in
# steady state, but on a detected restart spreads the due orders' first
# firings across a window instead of letting them all go at once. Nothing
# is skipped: a staggered order just waits a few more 30s ticks.
#
# Usage: orders-restart-stagger.sh <order-name> <interval-seconds> \
#          [per-order-stagger-seconds] [epoch-window-seconds] [restart-gap-seconds]
#
# Exit 0 = due now (gc's condition trigger fires the order this tick).
# Exit 1 = not due yet (checked again next tick).
#
# State lives under $ORDERS_STAGGER_STATE_DIR (default: a host-local,
# gitignored dir under .gc/runtime/), one small file per order plus a
# couple of shared bookkeeping files. $ORDERS_STAGGER_NOW overrides the
# clock for tests; real runs always use the wall clock.

set -Eeuo pipefail

NAME="${1:?order name required}"
INTERVAL="${2:?interval seconds required}"
PER_ORDER_STAGGER="${3:-20}"
EPOCH_WINDOW="${4:-300}"
RESTART_GAP="${5:-90}"

STATE_DIR="${ORDERS_STAGGER_STATE_DIR:-/home/benja/agent-factory/.gc/runtime/orders-restart-stagger}"
mkdir -p "$STATE_DIR"

now() {
  if [ -n "${ORDERS_STAGGER_NOW:-}" ]; then
    printf '%s\n' "$ORDERS_STAGGER_NOW"
  else
    date +%s
  fi
}

read_file() {
  # $1=path $2=default
  [ -f "$1" ] && cat "$1" || printf '%s\n' "$2"
}

NOW=$(now)

LAST_RUN_FILE="$STATE_DIR/$NAME.last_run"
LAST_RUN=$(read_file "$LAST_RUN_FILE" 0)
ELAPSED=$((NOW - LAST_RUN))

# Plain cooldown gate -- identical to gc's own semantics, so cadence
# outside a restart is exactly what it was before this order was switched
# from `cooldown` to `condition`.
if [ "$ELAPSED" -lt "$INTERVAL" ]; then
  exit 1
fi

# Controller-liveness heartbeat, touched by every order's check on every
# tick. A gap much larger than the ~30s tick period means the controller
# (hence this whole city) was not ticking for a while: a restart.
HEARTBEAT_FILE="$STATE_DIR/.controller_heartbeat"
LAST_TICK=$(read_file "$HEARTBEAT_FILE" "$NOW")
printf '%s\n' "$NOW" > "$HEARTBEAT_FILE"
TICK_GAP=$((NOW - LAST_TICK))

EPOCH_FILE="$STATE_DIR/.restart_epoch"
EPOCH=$(read_file "$EPOCH_FILE" 0)

if [ "$TICK_GAP" -gt "$RESTART_GAP" ]; then
  EPOCH="$NOW"
  printf '%s\n' "$EPOCH" > "$EPOCH_FILE"
  rm -f "$STATE_DIR"/*.slot
  : > "$STATE_DIR/.slot_count"
fi

IN_BURST_WINDOW=0
if [ "$EPOCH" -gt 0 ] && [ $((NOW - EPOCH)) -le "$EPOCH_WINDOW" ]; then
  IN_BURST_WINDOW=1
fi

if [ "$IN_BURST_WINDOW" -eq 1 ]; then
  SLOT_FILE="$STATE_DIR/$NAME.slot"
  COUNT_FILE="$STATE_DIR/.slot_count"
  SLOT=$(read_file "$SLOT_FILE" "")
  if [ -z "$SLOT" ]; then
    SLOT=$(read_file "$COUNT_FILE" 0)
    printf '%s\n' "$SLOT" > "$SLOT_FILE"
    printf '%s\n' "$((SLOT + 1))" > "$COUNT_FILE"
  fi
  OFFSET=$((SLOT * PER_ORDER_STAGGER))
  [ "$OFFSET" -le "$EPOCH_WINDOW" ] || OFFSET="$EPOCH_WINDOW"
  FIRE_AT=$((EPOCH + OFFSET))
  if [ "$NOW" -lt "$FIRE_AT" ]; then
    exit 1
  fi
fi

printf '%s\n' "$NOW" > "$LAST_RUN_FILE"
exit 0
