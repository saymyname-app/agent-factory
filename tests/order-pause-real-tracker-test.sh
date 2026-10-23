#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime and an isolated Dolt server
#
# bin/order-pause (af-npz9v1.15) on the real tracker and the real `gc order
# run`, in a disposable city that shares nothing with the live Factory: what
# tests/order-pause-test.py assumes of its synthetic tracker (the flags of
# `bd create`, `update`, `list`), replayed on the real one, and the gate run
# by gc as an order's exec. No order of the Factory is paused: the order here
# is the trial city's own.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc bd jq git dolt python3; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

TRIAL=$(mktemp -d /tmp/af-npz9v1.15-order-pause.XXXXXX)
TEST_CITY="$TRIAL/city"
CITY_NAME=$(basename "$TRIAL")
cleanup() {
  status=$?
  trap - EXIT
  # The city's managed Dolt server and its watchdog outlive `gc init`; their
  # command lines carry the trial directory, and nothing else does.
  pkill -f -- "$TRIAL/" >/dev/null 2>&1 || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    pgrep -f -- "$TRIAL/" >/dev/null 2>&1 || break
    sleep 0.3
  done
  pkill -9 -f -- "$TRIAL/" >/dev/null 2>&1 || true
  tmux -L "$CITY_NAME" kill-server >/dev/null 2>&1 || true
  if [ "${KEEP_TEST_CITY:-0}" = 1 ]; then
    echo "trial preserved at $TRIAL" >&2
  else
    rm -rf -- "$TRIAL"
  fi
  exit "$status"
}
trap cleanup EXIT

# Nothing of the live Factory may reach this city (see
# tests/empty-bd-bin-order-real-tracker-test.sh for why BD_BIN stays unset).
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_|GH_BIN$)' || true)
export HOME="$TRIAL/home" TMUX_TMPDIR="$TRIAL/tmux"
mkdir -p "$HOME" "$TMUX_TMPDIR"
dolt config --global --add user.name "order-pause trial" >/dev/null
dolt config --global --add user.email "trial@example.invalid" >/dev/null
git config --global user.name "order-pause-trial"
git config --global user.email "trial@example.invalid"

gc init --template minimal --default-provider codex --skip-provider-readiness \
  --no-start --yes --name "$CITY_NAME" "$TEST_CITY" >/dev/null 2>&1 \
  || fail "gc init of the isolated city failed"
cd "$TEST_CITY"

# The trial city's own order, gated as every order of the Factory is.
RUNS="$TRIAL/runs"
mkdir -p orders
cat >orders/trial-order.toml <<EOF
[order]
description = "an order of the trial city, gated by bin/order-pause"
trigger = "manual"
exec = "$ROOT/bin/order-pause gate trial-order -- sh -c 'echo ran >> $RUNS'"
EOF
gc order show trial-order >/dev/null 2>&1 || fail "gc does not load the gated order"

# The door acts on this city: its orders, its city.toml, its tracker.
export ORDER_PAUSE_ROOT="$TEST_CITY"
door() { "$ROOT/bin/order-pause" "$@"; }
runs() { [ -f "$RUNS" ] && wc -l <"$RUNS" | tr -d ' ' || echo 0; }

out=$(door pause trial-order --by usine --words "pause d'essai" --reason "essai réel" 2>&1) \
  || fail "pause refused on the real tracker: $out"
record=$(bd list --has-metadata-key gc.order_pause --status open --json 2>/dev/null \
  | jq -r '.[] | select(.metadata["gc.order_pause"] == "trial-order") | .id')
[ -n "$record" ] || fail "no open pause record on the real tracker"
bd show "$record" --json 2>/dev/null | jq -e '(.[0] // .) as $b | ($b.labels | index("order-pause")) != null
  and $b.metadata["gc.order_pause_by"] == "usine" and $b.metadata["gc.order_pause_words"] == "pause d'"'"'essai"' \
  >/dev/null || fail "the pause record does not carry its label, who and words"

gc order run trial-order >/dev/null 2>&1 || fail "gc order run failed on a paused order"
[ "$(runs)" = 0 ] || fail "gc ran the command of a paused order"

out=$(door resume trial-order --by benjamin --words relance 2>&1) || fail "resume refused on the real tracker: $out"
bd show "$record" --json 2>/dev/null | jq -e '(.[0] // .) as $b | $b.status == "closed"
  and $b.metadata["gc.order_resume_by"] == "benjamin"' >/dev/null || fail "the resume did not close the record"

gc order run trial-order >/dev/null 2>&1 || fail "gc order run failed on a resumed order"
[ "$(runs)" = 1 ] || fail "gc did not run the command of a resumed order (runs: $(runs))"

printf 'PASS: order-pause pauses and resumes an order on the real tracker, and gc honours it\n'
