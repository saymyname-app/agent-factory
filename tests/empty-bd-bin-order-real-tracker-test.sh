#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime and an isolated Dolt server
#
# The order idle-ready-work-wake, checked by gc itself in a disposable city
# that shares nothing with the live Factory (af-d130xt).
#
# Gas City 1.5 gives an order `BD_BIN=`, set and empty. A tool that reads it
# as its `bd` runs '': its check answers exit 1, which gc reads as
# "condition: not met", so the order never fires and nothing fails. Here the
# city holds what the order exists for (ready delivery-plane work, no active
# worker, idle for an hour) and gc must find the order due. Whatever gc gives
# an order next is held the same way.
#
# Only the check is run: the exec mails the mayor with --notify, which starts
# an agent session in the city, and it reads `bd` by the same line.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc bd jq git dolt python3; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

TRIAL=$(mktemp -d /tmp/af-d130xt-empty-bd-bin.XXXXXX)
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
  # No mail is sent here; a tmux server on the city's socket would be an agent
  # session nothing in this test asked for.
  tmux -L "$CITY_NAME" kill-server >/dev/null 2>&1 || true
  if [ "${KEEP_TEST_CITY:-0}" = 1 ]; then
    echo "trial preserved at $TRIAL" >&2
  else
    rm -rf -- "$TRIAL"
  fi
  exit "$status"
}
trap cleanup EXIT

# Nothing of the live Factory may reach this city: no GC_* variable (hosted
# Dolt, city path, session identity, GC_BIN), no actor and no shared HOME.
# BD_BIN stays unset: gc runs it too, so a BD_BIN that calls gc starts gc
# again without end (it filled the host's memory on 2026-10-11).
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_|GH_BIN$)' || true)
export HOME="$TRIAL/home" TMUX_TMPDIR="$TRIAL/tmux"
export FACTORY_ROOT="$TEST_CITY"
mkdir -p "$HOME" "$TMUX_TMPDIR"
dolt config --global --add user.name "empty-bd-bin trial" >/dev/null
dolt config --global --add user.email "trial@example.invalid" >/dev/null
git config --global user.name "empty-bd-bin-trial"
git config --global user.email "trial@example.invalid"

gc init --template minimal --default-provider codex --skip-provider-readiness \
  --no-start --yes --name "$CITY_NAME" "$TEST_CITY" >/dev/null 2>&1 \
  || fail "gc init of the isolated city failed"
cd "$TEST_CITY"

# What the order exists for: ready delivery-plane work, idle for an hour.
bd create --title "ready delivery-plane work" --type task \
  --metadata '{"gc.plane":"delivery"}' >/dev/null 2>&1 || fail "could not create the delivery-plane bead"
ready=$(bd ready --json 2>/dev/null | jq '[.[] | select((.metadata // {})["gc.plane"] == "delivery")] | length')
[ "$ready" = 1 ] || fail "the city does not hold one ready delivery-plane bead (found: $ready)"
mkdir -p .gc/runtime
jq -n --arg since "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S+00:00)" \
  '{idle_since: $since, notified_at: null}' >.gc/runtime/idle-ready-work-state.json

# The Factory's order (orders/idle-ready-work-wake.toml), on this work tree's
# tool and this city.
mkdir -p orders
cat >orders/idle-ready-work-wake.toml <<EOF
[order]
description = "idle-ready-work-wake, as the Factory runs it"
trigger = "condition"
interval = "5m"
check = "$ROOT/bin/idle-ready-work-wake --repo-root $TEST_CITY --check-only"
exec = "$ROOT/bin/idle-ready-work-wake --repo-root $TEST_CITY"
timeout = "60s"
EOF
due=$(gc order check 2>&1 || true)
grep -Eq '^idle-ready-work-wake +condition +yes ' <<<"$due" \
  || fail "the order's check does not see the idle ready work: $(grep -E '^idle-ready-work-wake ' <<<"$due" || echo "$due")"
if tmux -L "$CITY_NAME" list-sessions >/dev/null 2>&1; then
  fail "the check started an agent session in the city"
fi

echo "PASS: empty-bd-bin-order-real-tracker"
