#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime and an isolated Dolt server
#
# Adoption trial of the publication door's new-flow contract (T05, af-c8n7ep)
# on the real tracker, in a disposable city that shares nothing with the live
# Factory. tests/ticket-graph-publish-entry-contract-test.py proves the door
# on a fake tracker; this trial proves what that fake assumes of the real
# `bd create --graph` and of the real `gc bd show` / `gc bd update` behind
# bin/convoy-state: a conformant draft is published and marked, the Cockpit V2
# draft redeclared to the contract is refused with nothing written, and a
# draft that does not declare the contract is published without the mark.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
DOOR="$ROOT/bin/ticket-graph-publish"
STATE="$ROOT/bin/convoy-state"
FIXTURES="$ROOT/tests/fixtures/ticket-graph-publish"
PROJECTS="$ROOT/tests/fixtures/spec-approve/projects"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc bd jq git dolt python3 sha256sum; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

TRIAL=$(mktemp -d /tmp/af-c8n7ep-entry-contract.XXXXXX)
TEST_CITY="$TRIAL/city"
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
  if [ "${KEEP_TEST_CITY:-0}" = 1 ]; then
    echo "trial preserved at $TRIAL" >&2
  else
    rm -rf -- "$TRIAL"
  fi
  exit "$status"
}
trap cleanup EXIT

# Nothing of the live Factory may reach this city: no GC_* variable (hosted
# Dolt, city path, session identity, GC_BIN) and no shared HOME.
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$|FACTORY_ROOT$)' || true)
export HOME="$TRIAL/home" TMUX_TMPDIR="$TRIAL/tmux" CONVOY_STATE_LOCK_DIR="$TRIAL/locks"
mkdir -p "$HOME" "$TMUX_TMPDIR" "$TRIAL/repo"
dolt config --global --add user.name "entry-contract trial" >/dev/null
dolt config --global --add user.email "trial@example.invalid" >/dev/null
git config --global user.name "entry-contract trial"
git config --global user.email "trial@example.invalid"

gc init --template minimal --default-provider codex --skip-provider-readiness \
  --no-start --yes --name af-c8n7ep-entry-contract "$TEST_CITY" >/dev/null 2>&1 \
  || fail "gc init of the isolated city failed"
cd "$TEST_CITY"

# The door reaches the tracker through `bd -C <workspace>` and never wakes a
# Mayor here: there is none in this city, and the live one is out of reach.
export TICKET_GRAPH_BD_WORKSPACE="$TEST_CITY" TICKET_GRAPH_PUBLISH_SKIP_MAYOR_NOTIFY=1

digest_of() {
  printf 'sha256:%s' "$(printf '%s' "$1" | sha256sum | cut -d' ' -f1)"
}

SPEC_TEXT="Spec synthétique de la Fixture City."
SPEC=$(gc bd create --title "Spec de la fixture" --type task --description "$SPEC_TEXT" --silent 2>/dev/null)
gc bd update "$SPEC" --set-metadata "spec_state=APPROVED_SPEC" \
  --set-metadata "approved_digest=$(digest_of "$SPEC_TEXT")" \
  --set-metadata "gc.project_id=delivery-fixture-city" >/dev/null

# An approved Ticket Graph Draft bead holding this description.
draft() {
  local id
  id=$(gc bd create --title "Brouillon d'essai" --type task --description "$1" --silent 2>/dev/null)
  # The digest is taken on what the tracker gives back, as the door does.
  gc bd update "$id" --set-metadata "spec_id=$SPEC" --set-metadata "approved_by=benjamin" \
    --set-metadata "approved_evidence=« j'approuve le graphe » (essai)" \
    --set-metadata "approved_digest=$(digest_of "$(gc bd show "$id" --json | jq -r '.[0].description')")" \
    --set-metadata "display_title=Fixture City : essai" --set-metadata "language=fr" >/dev/null
  printf '%s' "$id"
}

publish() {
  "$DOOR" bd-publish "$1" --project acme --repo-root "$TRIAL/repo" --config-dir "$PROJECTS"
}

tracker() {
  gc bd list --all --limit 0 --json | jq -S 'map({id, status, title, description, metadata}) | sort_by(.id)'
}

# --- the Cockpit V2 draft, redeclared to the contract, is refused ------------
COCKPIT=$(draft "$(cat "$FIXTURES/cockpit-v2-draft.yaml")
flow_contract: new-flow/v1")
before=$(tracker)
set +e
refusal=$(publish "$COCKPIT" 2>&1 >/dev/null); rc=$?
set -e
[ "$rc" != 0 ] || fail "the redeclared Cockpit V2 draft was published"
for expected in "rien n'est écrit" "- T03 : pas de ligne de démonstration" "genre inconnu « prefactor »" \
  "Un test montre que l'outil de roadmap" "nomme un test"; do
  grep -qF -- "$expected" <<<"$refusal" || fail "refusal does not say '$expected': $(head -5 <<<"$refusal")"
done
for n in $(seq -w 1 25); do
  grep -q -- "^- T$n : " <<<"$refusal" || fail "refusal does not name ticket T$n"
done
[ "$before" = "$(tracker)" ] || fail "a refused publication wrote to the real tracker"

# A draft of the new flow is published only with a graph review that holds
# for its digest (T08, tests/graph-review-isolated-city-test.sh): this one
# answers every question of the brief favorably, as a reviewer session would.
mkdir -p "$TRIAL/factory/config"
echo '{"roles": {"reviewer": {"agent": "delivery-reviewer"}}}' > "$TRIAL/factory/config/delivery-roles.json"
printf '[providers.reviewer-profile]\nargs_append = ["--model", "modele-relecteur"]\n' > "$TRIAL/factory/city.toml"
review() {
  FACTORY_ROOT="$TRIAL/factory" GRAPH_REVIEW_BD_WORKSPACE="$TEST_CITY" DELIVERY_ROLE_READ_ONLY=1 \
    GRAPH_REVIEW_PROVIDER_FAILOVER_BIN="$ROOT/tests/fixtures/graph-review/provider-failover" "$ROOT/bin/graph-review" "$@"
}
review_favorably() {
  review request "$1" --author-model modele-auteur >/dev/null || fail "graph review request refused for $1"
  review brief "$1" | jq '
    def answers($checks): {checks: ($checks | with_entries(.value = (
      if .key == "prototype_fold_present_and_first" then {state: "not_applicable", reason: "aucun ticket d'"'"'interface"}
      else {state: "favorable"} end)))};
    {digest, tickets: (.tickets | map({key: .id, value: answers(.checks)}) | from_entries), graph: answers(.graph_checks)}
  ' > "$TRIAL/graph-verdict.json"
  review record "$1" --verdict-file "$TRIAL/graph-verdict.json" >/dev/null || fail "graph review verdict refused for $1"
}

# --- a conformant draft of the fixture is published and marked ---------------
CONFORMANT=$(draft "$(cat "$FIXTURES/fixture-city-new-flow-draft.yaml")")
review_favorably "$CONFORMANT"
result=$(publish "$CONFORMANT") || fail "the conformant draft was refused"
CONVOY=$(jq -r '.ids._convoy' <<<"$result")
T1=$(jq -r '.ids.T1' <<<"$result"); T2=$(jq -r '.ids.T2' <<<"$result"); T3=$(jq -r '.ids.T3' <<<"$result")
jq -e '.flow_contract == "new-flow/v1" and (.marked | length) == 4 and .mayor_notified == null' <<<"$result" >/dev/null \
  || fail "unexpected publication result: $result"

shown=$("$STATE" show "$CONVOY" --repo "$TRIAL/repo") || fail "convoy-state show found the published convoy incoherent: $shown"
jq -e --arg t1 "$T1" --arg t2 "$T2" --arg t3 "$T3" '
  .unruled == false and .convoy.mark == "new-flow/v1"
  and (.tickets | map(.id) | sort) == ([$t1, $t2, $t3] | sort)
  and (.tickets | all(.mark == "new-flow/v1" and .unruled == []))
  and (.tickets[] | select(.id == $t1) | .kind == "prefactoring" and .demonstration_line == null)
  and (.tickets[] | select(.id == $t2) | .kind == "vertical_slice"
       and .demonstration_line == "Sur le produit lancé avec le jeu de données « contenu », la page d'"'"'accueil (GET /) affiche les trois éléments « Alpha », « Bêta » et « Gamma ».")
  and (.tickets[] | select(.id == $t3) | .kind == "repair"
       and .demonstration_line == "Sur le produit lancé, GET /api/items rend pour chaque élément un champ « label » non vide.")
' <<<"$shown" >/dev/null || fail "mark, kind or demonstration line not read back from the real tracker: $shown"

text=$(gc bd show "$T2" --json | jq -r '.[0].description')
grep -qi "execution contract" <<<"$text" && fail "the published ticket text still carries an execution contract"
grep -qF "## Demonstration line" <<<"$text" || fail "the published ticket text has no demonstration line: $text"
# The dependency edges of the graph are the real ones: T2 waits for T1.
gc bd show "$T2" --json | jq -e --arg t1 "$T1" '.[0].dependencies | any(.id == $t1 and .dependency_type == "blocks")' >/dev/null \
  || fail "T2 is not blocked by T1 in the real tracker"

# Publishing again changes nothing.
before=$(tracker)
again=$(publish "$CONFORMANT") || fail "the second publication of the same draft failed"
[ "$(jq -S .ids <<<"$result")" = "$(jq -S .ids <<<"$again")" ] || fail "the second publication created other beads"
[ "$before" = "$(tracker)" ] || fail "the second publication wrote to the real tracker"

# --- a draft that does not declare the contract is published without mark ----
LEGACY=$(draft "global_execution_contract:
  models: none
tickets:
- id: T1
  title: Un ticket de l'ancien flux
  blocked_by: []
  target_rigs: [fixture_city]
  what_it_delivers: fait une chose
  acceptance_criteria: [Un test montre que la chose est faite]")
result=$(publish "$LEGACY") || fail "a draft that does not declare the contract was refused"
PLAIN=$(jq -r '.ids._convoy' <<<"$result")
jq -e 'has("flow_contract") | not' <<<"$result" >/dev/null || fail "an undeclared draft was published as new flow"
gc bd list --all --limit 0 --json | jq -e --arg d "$(jq -r .graph_digest <<<"$result")" '
  map(select(.metadata["gc.graph_digest"] == $d)) | length == 2
  and all((.metadata | keys | map(select(startswith("gc.flow."))) | length) == 0)' >/dev/null \
  || fail "a bead of the undeclared draft carries a gc.flow.* field"
gc bd show "$(jq -r '.ids.T1' <<<"$result")" --json | jq -e '.[0].description | contains("## Autonomous execution contract")' >/dev/null \
  || fail "the ticket of the undeclared draft lost its execution contract"
set +e
"$STATE" show "$PLAIN" --repo "$TRIAL/repo" >/dev/null; rc=$?
set -e
[ "$rc" = 4 ] || fail "convoy-state show on the undeclared convoy exited $rc, want 4 (pas un convoi du nouveau flux)"

echo "PASS: on the real tracker, the door refuses the redeclared Cockpit V2 draft without writing, publishes and marks a conformant draft, and publishes an undeclared draft as before"
