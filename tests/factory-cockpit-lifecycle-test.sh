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
curl --fail --silent "$URL/" | grep -Fq 'PO GPT SayMyName'
curl --fail --silent "$URL/" | grep -Fq 'Comprendre le produit et son système'
curl --fail --silent "$URL/styles.css" | grep -Fq -- '--green:'
curl --fail --silent "$URL/app.js" | grep -Fq 'textContent'
[[ $(curl --silent --output /dev/null --write-out '%{http_code}' "$URL/../AGENTS.md") == 404 ]]
curl --fail --silent "$URL/api/snapshot" | jq -e \
  '.schema_version == 1 and .zero_token_contract.model_calls == 0 and (.agents | length) >= 1 and (.product_work | type) == "array" and (.product_memory.roadmap | length) >= 1 and (.decision_aids | length) >= 1' >/dev/null
curl --fail --silent "$URL/api/tokens" | jq -e \
  '.monitoring.model_calls == 0 and .monitoring.tokens == 0 and (.factory.sessions | type) == "array"' >/dev/null
curl --fail --silent "$URL/api/po/conversation" | jq -e \
  '.product == "SayMyName" and .full_access == true and (.messages | type) == "array"' >/dev/null
[[ $(curl --silent --output /dev/null --write-out '%{http_code}' \
  --request POST --header 'Content-Type: application/json' \
  --data '{"message":"must not send"}' "$URL/api/mayor/message") == 403 ]]
[[ $(curl --silent --output /dev/null --write-out '%{http_code}' \
  --request POST --header 'Content-Type: application/json' \
  --data '{"message":"must not send"}' "$URL/api/po/message") == 403 ]]
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
