#!/usr/bin/env bash
# T10 (af-u61al3): orders/lib/orders-restart-stagger.sh gates a `condition`
# order's due-ness so that, after the city has been paused for a while,
# several cooldown orders becoming due on the same controller tick fire
# spread out instead of all at once -- without skipping any, and without
# changing steady-state cadence. This test drives the script directly
# (pure shell, an isolated state dir, and an injectable clock via
# ORDERS_STAGGER_NOW) -- no gc, no bd, no live city.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
SCRIPT="$ROOT/orders/lib/orders-restart-stagger.sh"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

[ -x "$SCRIPT" ] || fail "$SCRIPT must exist and be executable"

STATE_DIR=$(mktemp -d /tmp/af-t10-orders-restart-stagger.XXXXXX)
cleanup() { rm -rf -- "$STATE_DIR"; }
trap cleanup EXIT

due_at() {
  # $1=order name $2=interval $3=now -> prints the tick's outcome
  ORDERS_STAGGER_STATE_DIR="$STATE_DIR" ORDERS_STAGGER_NOW="$3" \
    "$SCRIPT" "$1" "$2" 20 300 90
}

# --- 1. Restart burst: five orders all overdue at once are spread out,
#        none skipped ------------------------------------------------------

BURST_STATE="$STATE_DIR/burst"
mkdir -p "$BURST_STATE"
T0=100000
for n in o1 o2 o3 o4 o5; do
  echo $((T0 - 3600)) > "$BURST_STATE/$n.last_run"
done
echo $((T0 - 3600)) > "$BURST_STATE/.controller_heartbeat"

declare -A fired_at
remaining=(o1 o2 o3 o4 o5)
for tick in 0 30 60 90 120 150 180; do
  now=$((T0 + tick))
  still=()
  for n in "${remaining[@]}"; do
    if ORDERS_STAGGER_STATE_DIR="$BURST_STATE" ORDERS_STAGGER_NOW="$now" \
        "$SCRIPT" "$n" 300 20 300 90; then
      fired_at["$n"]=$tick
    else
      still+=("$n")
    fi
  done
  remaining=("${still[@]}")
done

[ "${#remaining[@]}" -eq 0 ] || fail "orders never fired after the restart burst: ${remaining[*]}"

# None of them may have skipped the restart tick entirely by never firing,
# and not all five may fire on the very first tick (that would just be the
# burst this order is meant to remove).
first_tick_fires=0
for n in o1 o2 o3 o4 o5; do
  [ "${fired_at[$n]}" -eq 0 ] && first_tick_fires=$((first_tick_fires + 1))
done
[ "$first_tick_fires" -lt 5 ] || fail "all 5 orders fired on the same restart tick -- still a burst"

# The first execution of every due order must land inside the first
# minute's worth of ticks the way a plain cooldown already would NOT (it
# would put all 5 there); verify instead that firings are spread across
# more than one tick, i.e. staggered.
distinct_ticks=$(printf '%s\n' "${fired_at[@]}" | sort -u | wc -l)
[ "$distinct_ticks" -ge 2 ] || fail "restart-burst firings all landed on one tick, expected them spread across several"

# --- 2. Outside a restart, cadence is exactly the plain interval, with no
#        added stagger delay -------------------------------------------

CADENCE_STATE="$STATE_DIR/cadence"
mkdir -p "$CADENCE_STATE"
T1=200000
fire_ticks=()
for tick in $(seq 0 30 900); do
  now=$((T1 + tick))
  if ORDERS_STAGGER_STATE_DIR="$CADENCE_STATE" ORDERS_STAGGER_NOW="$now" \
      "$SCRIPT" solo 300 20 300 90; then
    fire_ticks+=("$tick")
  fi
done

expected="0 300 600 900"
actual="${fire_ticks[*]}"
[ "$actual" = "$expected" ] || fail "cadence outside a restart changed: expected ticks [$expected], got [$actual]"

# --- 3. A lone order becoming due (no other order due nearby, no restart
#        gap) fires immediately, same as a plain cooldown trigger would --

LONE_STATE="$STATE_DIR/lone"
mkdir -p "$LONE_STATE"
T2=300000
echo $((T2 - 120)) > "$LONE_STATE/lone.last_run"
echo $((T2 - 5)) > "$LONE_STATE/.controller_heartbeat"
ORDERS_STAGGER_STATE_DIR="$LONE_STATE" ORDERS_STAGGER_NOW="$T2" \
  "$SCRIPT" lone 60 20 300 90 || fail "a due order with no restart gap must fire immediately"

echo "PASS: orders-restart-stagger.sh spreads a restart burst without skipping any order, and leaves outside-restart cadence unchanged"
