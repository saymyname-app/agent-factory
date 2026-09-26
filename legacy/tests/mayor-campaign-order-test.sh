#!/usr/bin/env bash
# ci: local-only — drives the live `gc` binary and the city's bead store

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
order=$(gc order show mayor-campaign --city "$ROOT" --json)
jq -e --arg source "$ROOT/orders/mayor-campaign.toml" '
  .ok == true and
  .order.type == "exec" and
  .order.trigger == "cooldown" and
  .order.interval == "1m" and
  .order.timeout == "50s" and
  .order.exec == "./bin/mayor-campaign sentinel" and
  .order.enabled == true and
  .order.source == $source
' >/dev/null <<<"$order"

printf 'PASS: city-local Mayor campaign Order is discoverable and deterministic\n'
