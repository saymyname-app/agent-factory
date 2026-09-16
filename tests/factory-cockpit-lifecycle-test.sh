#!/usr/bin/env bash
# ci: local-only — starts and probes the real cockpit process on its port

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
page=$(curl --fail --silent "$URL/")
grep -Fq 'Comprendre l’usine en un coup d’œil' <<<"$page"
grep -Fq 'SANTÉ DE L’INFRASTRUCTURE' <<<"$page"
grep -Fq 'ACTIVITÉ DE LIVRAISON' <<<"$page"
grep -Fq 'REPRISE' <<<"$page"
grep -Fq 'id="campaign-block-global"' <<<"$page"
grep -Fq 'id="campaign-block-global" class="campaign-block-global hidden" data-view="today" type="button" role="alert" aria-live="assertive"' <<<"$page"
grep -Fq 'id="campaign-block-today"' <<<"$page"
grep -Fq 'Propriétaire de la reprise' <<<"$page"
grep -Fq 'Candidats produit' <<<"$page"
grep -Fq 'AIDE À LA DÉCISION' <<<"$page"
grep -Fq 'Parler au Mayor' <<<"$page"
grep -Fq 'Tokens, du détail au global' <<<"$page"
grep -Fq 'Mon PO GPT' <<<"$page"
grep -Fq 'Comprendre le produit' <<<"$page"
grep -Fq 'Documentation produit validée par l’humain' <<<"$page"
grep -Fq 'Objectifs, marché et validation' <<<"$page"
grep -Fq 'Décisions séparées par niveau' <<<"$page"
grep -Fq 'Du choix humain à la preuve' <<<"$page"
styles=$(curl --fail --silent "$URL/styles.css")
grep -Fq -- '--green:' <<<"$styles"
script=$(curl --fail --silent "$URL/app.js")
grep -Fq 'textContent' <<<"$script"
grep -Fq 'renderOperationalState' <<<"$script"
grep -Fq 'renderCampaignState' <<<"$script"
grep -Fq 'campaign-block-global-cause' <<<"$script"
grep -Fq 'campaign-block-today-action' <<<"$script"
if grep -Fq 'si cet état persiste' <<<"$script"; then
  printf 'cockpit still contains the misleading persistence advice\n' >&2
  exit 1
fi
[[ $(curl --silent --output /dev/null --write-out '%{http_code}' "$URL/../AGENTS.md") == 404 ]]
curl --fail --silent "$URL/api/snapshot" | jq -e \
  '.schema_version == 2 and .human_state.contract == "agent-factory-human-state/v1" and (.health.state == "available" or .health.state == "degraded" or .health.state == "unavailable") and (.activity.state == "working" or .activity.state == "waiting_automatic" or .activity.state == "waiting_action" or .activity.state == "stopped") and (.resume.automatic | type) == "boolean" and (.resume.owner == "system" or .resume.owner == "Mayor" or .resume.owner == "Benjamin" or .resume.owner == "none") and (.campaign.enabled | type) == "boolean" and (.campaign.blocked | type) == "boolean" and .zero_token_contract.model_calls == 0 and (.agents | length) >= 1 and (.product_work | type) == "array" and ([.queue[] | select(.state != "eligible" and .state != "paused")] | length) == 0 and ([.product_work[] | select((.state == "eligible") and (.id == "af-s1rv" or .id == "af-hxji"))] | length) == 0 and (.product_memory.roadmap | length) >= 1 and (.product_memory.business.objectives | length) >= 1 and (.product_memory.product_reference | length) >= 1 and (.product_memory.view_inventory | length) >= 1 and .product_memory.inventory_freshness.model_calls == 0 and (.product_memory.delivery_workflow | length) >= 1 and (.decision_aids | length) >= 1 and (.today.general_decisions | type) == "array" and (.today.effective_blockers | type) == "array"' >/dev/null
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
