#!/usr/bin/env bash

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
PORT=18383
export FACTORY_COCKPIT_PORT=$PORT
COCKPIT="$ROOT/bin/factory-cockpit"
URL="http://127.0.0.1:$PORT"

if python3 "$ROOT/lib/factory_cockpit.py" serve --host 0.0.0.0 --port 18384 \
  >/dev/null 2>&1; then
  printf 'cockpit accepted a non-loopback listener\n' >&2
  exit 1
fi

cleanup() { "$COCKPIT" stop >/dev/null 2>&1 || true; }
trap cleanup EXIT

"$COCKPIT" stop >/dev/null 2>&1 || true
output=$("$COCKPIT" start)
[[ $output == STARTED:* ]]
curl --fail --silent "$URL/health" | jq -e '.ok == true and .model_calls == 0' >/dev/null
curl --fail --silent "$URL/" | grep -Fq 'Comprendre l’usine en un coup d’œil'
curl --fail --silent "$URL/" | grep -Fq 'AIDE À LA DÉCISION'
curl --fail --silent "$URL/" | grep -Fq 'Parler au Mayor'
curl --fail --silent "$URL/" | grep -Fq 'Tokens, du détail au global'
curl --fail --silent "$URL/" | grep -Fq 'Mon PO GPT'
curl --fail --silent "$URL/" | grep -Fq 'Comprendre le produit'
curl --fail --silent "$URL/" | grep -Fq 'Documentation produit validée par l’humain'
curl --fail --silent "$URL/" | grep -Fq 'Objectifs, marché et validation'
curl --fail --silent "$URL/" | grep -Fq 'Décisions séparées par niveau'
curl --fail --silent "$URL/" | grep -Fq 'Du choix humain à la preuve'
curl --fail --silent "$URL/styles.css" | grep -Fq -- '--green:'
curl --fail --silent "$URL/app.js" | grep -Fq 'textContent'
[[ $(curl --silent --output /dev/null --write-out '%{http_code}' "$URL/../AGENTS.md") == 404 ]]
curl --fail --silent "$URL/api/snapshot" | jq -e \
  '.schema_version == 1 and .zero_token_contract.model_calls == 0 and (.agents | length) >= 1 and (.product_work | type) == "array" and (.product_memory.roadmap | length) >= 1 and (.product_memory.business.objectives | length) >= 1 and (.product_memory.product_reference | length) >= 1 and (.product_memory.view_inventory | length) >= 1 and .product_memory.inventory_freshness.model_calls == 0 and (.product_memory.delivery_workflow | length) >= 1 and (.decision_aids | length) >= 1 and (.today.general_decisions | type) == "array" and (.today.effective_blockers | type) == "array"' >/dev/null
curl --fail --silent "$URL/api/tokens" | jq -e \
  '.monitoring.model_calls == 0 and .monitoring.tokens == 0 and (.factory.sessions | type) == "array"' >/dev/null
curl --fail --silent "$URL/api/po/conversation" | jq -e \
  '.product == "SayMyName" and .full_access == true and .status == "not_started" and (.messages | type) == "array" and (.conversations | type) == "array"' >/dev/null
curl --fail --silent "$URL/api/po/index" | jq -e \
  '.model_calls == 0 and (.conversations | type) == "array"' >/dev/null
curl --fail --silent "$URL/api/preview/status" | jq -e \
  '.state != null and .commands.frontend == "npm run dev"' >/dev/null
[[ $(curl --silent --output /dev/null --write-out '%{http_code}' \
  --request POST --header 'Content-Type: application/json' \
  --data '{"message":"must not send"}' "$URL/api/mayor/message") == 403 ]]
[[ $(curl --silent --output /dev/null --write-out '%{http_code}' \
  --request POST --header 'Content-Type: application/json' \
  --data '{"message":"must not send"}' "$URL/api/po/message") == 403 ]]
[[ $(curl --silent --output /dev/null --write-out '%{http_code}' \
  --request POST --header 'Content-Type: application/json' \
  --data '{"action":"start"}' "$URL/api/preview/action") == 403 ]]
headers=$(curl --silent --dump-header - --output /dev/null "$URL/")
grep -Fiq 'X-Frame-Options: DENY' <<<"$headers"
grep -Fiq "Content-Security-Policy: default-src 'self'" <<<"$headers"
output=$("$COCKPIT" status)
[[ $output == RUNNING:*zero\ model\ calls ]]
output=$("$COCKPIT" stop)
[[ $output == STOPPED:* ]]
if "$COCKPIT" status >/dev/null 2>&1; then
  printf 'cockpit should be stopped\n' >&2
  exit 1
fi

if sed -n '/class FactoryCollector/,/class SnapshotCache/p' \
  "$ROOT/lib/factory_cockpit.py" | grep -Ei 'openai|codex exec|chatgpt' >/dev/null; then
  printf 'cockpit runtime must not call a model\n' >&2
  exit 1
fi

printf 'PASS: Factory cockpit lifecycle, safety, and zero-token contract\n'
