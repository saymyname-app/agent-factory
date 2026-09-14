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
curl --fail --silent "$URL/" | grep -Fq 'Ce que l’usine fait maintenant'
curl --fail --silent "$URL/styles.css" | grep -Fq -- '--green:'
curl --fail --silent "$URL/app.js" | grep -Fq 'textContent'
[[ $(curl --silent --output /dev/null --write-out '%{http_code}' "$URL/../AGENTS.md") == 404 ]]
curl --fail --silent "$URL/api/snapshot" | jq -e \
  '.schema_version == 1 and .zero_token_contract.model_calls == 0 and (.agents | length) >= 1' >/dev/null
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

if grep -RE 'openai|codex exec|chatgpt' \
  "$ROOT/lib/factory_cockpit.py" "$ROOT/ui/factory-cockpit" >/dev/null; then
  printf 'cockpit runtime must not call a model\n' >&2
  exit 1
fi

printf 'PASS: Factory cockpit lifecycle, safety, and zero-token contract\n'
