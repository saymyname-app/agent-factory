#!/usr/bin/env bash
# ci: local-only — drives the live `gc` binary and the city's bead store

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
order=$(gc order show delivery-seat-release --city "$ROOT" --json)
jq -e --arg source "$ROOT/orders/delivery-seat-release.toml" --arg exec "/home/benja/agent-factory/bin/order-pause gate delivery-seat-release -- /home/benja/agent-factory/bin/delivery-seat-release" '
  .ok == true and
  .order.type == "exec" and
  .order.trigger == "condition" and
  .order.interval == "2m" and
  .order.timeout == "60s" and
  .order.exec == $exec and
  .order.enabled == true and
  .order.source == $source
' >/dev/null <<<"$order"

printf 'PASS: city-local delivery-seat-release Order is discoverable and deterministic\n'
