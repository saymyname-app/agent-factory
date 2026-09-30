#!/usr/bin/env bash
# ci: local-only — drives the live `gc` binary and the city's bead store

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
order=$(gc order show factory-session-loop-guard --city "$ROOT" --json)
jq -e --arg source "$ROOT/orders/factory-session-loop-guard.toml" --arg exec "$ROOT/bin/factory-session-loop-guard --quiet" '
  .ok == true and
  .order.type == "exec" and
  .order.trigger == "condition" and
  .order.interval == "5m" and
  .order.timeout == "180s" and
  .order.exec == $exec and
  .order.enabled == true and
  .order.source == $source
' >/dev/null <<<"$order"

printf 'PASS: city-local factory-session-loop-guard Order is discoverable and deterministic\n'
