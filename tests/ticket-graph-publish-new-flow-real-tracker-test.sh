#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime and an isolated Dolt server
#
# Adoption trial of the publication door's new-flow contract (T05, af-c8n7ep;
# T06, af-cgauf8) on the real tracker, in a disposable city that shares nothing with the live
# Factory. tests/ticket-graph-publish-entry-contract-test.py proves the door
# on a fake tracker; this trial proves what that fake assumes of the real
# `bd create --graph` and of the real `gc bd show` / `gc bd update` behind
# bin/convoy-state: a conformant draft is published and marked, the Cockpit V2
# draft redeclared to the contract is refused with nothing written, and a
# draft that does not declare the contract is published without the mark.
# T06: a graph with an orphan user story is refused; a published ticket shows
# the pointers the door poses; an operator need blocks until it is lifted; a
# patch that only adds a repair is published without approval, tracked by the
# convoy and marked; a ticket is withdrawn behind its gate record.

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

SPEC_TEXT=$(cat "$ROOT/tests/fixtures/delivery-fixture-city/spec.md")
# The project's profile, with its launch recipe and entry points.
mkdir -p "$TRIAL/descriptors"
cp "$ROOT/tests/fixtures/delivery-fixture-city/descriptor.json" "$TRIAL/descriptors/delivery-fixture-city.json"
SPEC=$(gc bd create --title "Spec de la fixture" --type task --description "$SPEC_TEXT" --silent 2>/dev/null)
gc bd update "$SPEC" --set-metadata "spec_state=APPROVED_SPEC" \
  --set-metadata "approved_digest=$(digest_of "$(gc bd show "$SPEC" --json | jq -r '.[0].description')")" \
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
  "$DOOR" bd-publish "$1" --project acme --repo-root "$TRIAL/repo" --config-dir "$PROJECTS" \
    --descriptors-dir "$TRIAL/descriptors"
}

# A revised draft bead: $1 its text, $2 the digest it revises, $3 "approved" or not.
revision() {
  local id
  id=$(gc bd create --title "Brouillon révisé d'essai" --type task --description "$1" --silent 2>/dev/null)
  gc bd update "$id" --set-metadata "spec_id=$SPEC" --set-metadata "revises_digest=$2" >/dev/null
  if [ "${3:-}" = approved ]; then
    gc bd update "$id" --set-metadata "approved_by=benjamin" \
      --set-metadata "approved_evidence=« j'approuve le graphe révisé » (essai)" \
      --set-metadata "approved_digest=$(digest_of "$(gc bd show "$id" --json | jq -r '.[0].description')")" >/dev/null
  fi
  printf '%s' "$id"
}

patch() {
  local id=$1
  shift
  "$DOOR" bd-patch "$id" --author essai --reason "essai de patch" --project acme --repo-root "$TRIAL/repo" \
    --config-dir "$PROJECTS" --descriptors-dir "$TRIAL/descriptors" "$@"
}

# A repair ticket a patch adds: it restores user story 2.
export REPAIR_TICKET='{"id": "R1", "kind": "repair", "title": "La liste retrouve son troisième élément",
 "blocked_by": [], "target_rigs": ["fixture_city"],
 "what_it_delivers": "La page affiche de nouveau les trois éléments.",
 "restores": {"kind": "user_story", "ref": "user story 2"},
 "demonstration_line": "Sur le produit lancé, la page (GET /) affiche de nouveau « Gamma ».",
 "acceptance_criteria": [{"entry_point": "GET / sur le produit lancé",
   "observable": "la région « liste » contient « Gamma »", "false_if": "« Gamma » manque"}]}'

# The conformant draft of the fixture, edited by a Python statement: `d` is
# the draft, `t` its tickets by id, `repair` the repair ticket above.
edited() {
  python3 - "$FIXTURES/fixture-city-new-flow-draft.yaml" "$1" <<'PY'
import json, os, sys, yaml
d = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
t = {ticket["id"]: ticket for ticket in d["tickets"]}
repair = json.loads(os.environ["REPAIR_TICKET"])
exec(sys.argv[2])
print(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), end="")
PY
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

# --- a conformant draft of the fixture is published and marked ---------------
CONFORMANT=$(draft "$(cat "$FIXTURES/fixture-city-new-flow-draft.yaml")")
result=$(publish "$CONFORMANT") || fail "the conformant draft was refused"
CONVOY=$(jq -r '.ids._convoy' <<<"$result")
T1=$(jq -r '.ids.T1' <<<"$result"); T2=$(jq -r '.ids.T2' <<<"$result"); T3=$(jq -r '.ids.T3' <<<"$result")
T4=$(jq -r '.ids.T4' <<<"$result")
jq -e '.flow_contract == "new-flow/v1" and (.marked | length) == 5 and .mayor_notified == null' <<<"$result" >/dev/null \
  || fail "unexpected publication result: $result"

shown=$("$STATE" show "$CONVOY" --repo "$TRIAL/repo") || fail "convoy-state show found the published convoy incoherent: $shown"
jq -e --arg t1 "$T1" --arg t2 "$T2" --arg t3 "$T3" --arg t4 "$T4" '
  .unruled == false and .convoy.mark == "new-flow/v1"
  and (.tickets | map(.id) | sort) == ([$t1, $t2, $t3, $t4] | sort)
  and (.tickets[] | select(.id == $t2) | .user_stories == ["1", "2"])
  and (.tickets[] | select(.id == $t4) | .user_stories == ["3"] and .establishes_launch_recipe == false)
  and (.tickets[] | select(.id == $t1) | .user_stories == null)
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

# T06: the pointers the door poses are read on the published ticket.
SPEC_DIGEST=$(digest_of "$(gc bd show "$SPEC" --json | jq -r '.[0].description')")
for pointer in "## Spec" "$SPEC — $SPEC_DIGEST" \
  "- 1. As a visiteur, I want voir l'état du jeu de données" "- 2. As a visiteur, I want voir la liste des éléments" \
  "## Sibling tickets" "- T4 (vertical_slice) — La sonde de santé répond : Sur le produit lancé, GET /health répond 200" \
  "- T1 (prefactoring) — " "## Seams" "- Point d'entrée du profil : GET /health (http)" \
  "- Testing Decisions de la Spec : Fixture City Oracle et ligne de commande des portes."; do
  grep -qF -- "$pointer" <<<"$text" || fail "the published ticket does not show the pointer '$pointer': $text"
done
grep -qF "$SPEC_DIGEST" "$FIXTURES/fixture-city-new-flow-draft.yaml" && fail "the Spec digest is written in the draft"

# Publishing again changes nothing.
before=$(tracker)
again=$(publish "$CONFORMANT") || fail "the second publication of the same draft failed"
[ "$(jq -S .ids <<<"$result")" = "$(jq -S .ids <<<"$again")" ] || fail "the second publication created other beads"
[ "$before" = "$(tracker)" ] || fail "the second publication wrote to the real tracker"

# --- T06: a graph with an orphan user story is refused with its number -------
ORPHAN=$(draft "$(edited 't["T2"]["user_stories"] = [1]')")
before=$(tracker)
set +e
refusal=$(publish "$ORPHAN" 2>&1 >/dev/null); rc=$?
set -e
[ "$rc" != 0 ] || fail "a graph with an orphan user story was published"
grep -qF -- "- graphe : user stories couvertes par aucun ticket : 2 (" <<<"$refusal" \
  || fail "the refusal does not name the orphan story: $refusal"
[ "$before" = "$(tracker)" ] || fail "a refused publication (orphan story) wrote to the real tracker"

# --- T06: an operator need blocks publication until it is lifted -------------
NEEDY=$(draft "$(edited 'd["operator_needs"] = [{"id": "cle_api_meteo", "kind": "secret", "what": "Clé de la météo au coffre"}]')")
before=$(tracker)
set +e
refusal=$(publish "$NEEDY" 2>&1 >/dev/null); rc=$?
set -e
[ "$rc" != 0 ] || fail "a graph with an open operator need was published"
grep -qF -- "besoin opérateur non levé : cle_api_meteo (secret)" <<<"$refusal" || fail "the refusal does not name the need: $refusal"
[ "$before" = "$(tracker)" ] || fail "a refused publication (operator need) wrote to the real tracker"
"$DOOR" lift-need "$NEEDY" --need cle_api_meteo --by mayor --evidence "fait" --project acme --config-dir "$PROJECTS" \
  >/dev/null 2>&1 && fail "someone else than the declared human approver lifted a need"
"$DOOR" lift-need "$NEEDY" --need cle_api_meteo --by benjamin --evidence "« la clé est au coffre »" --project acme \
  --config-dir "$PROJECTS" >/dev/null || fail "the declared human approver could not lift the need"
publish "$NEEDY" >/dev/null || fail "the draft was refused after its operator need was lifted"

# --- T06: a patch that only adds a repair needs no approval -------------------
GRAPH_DIGEST=$(jq -r .graph_digest <<<"$result")
# Without approval, an added slice is refused and nothing is written.
SLICE=$(revision "$(edited 'd["tickets"].append({**t["T4"], "id": "T5", "title": "Une autre sonde"})')" "$GRAPH_DIGEST")
before=$(tracker)
set +e
refusal=$(patch "$SLICE" 2>&1 >/dev/null); rc=$?
set -e
[ "$rc" != 0 ] || fail "an unapproved patch added a vertical_slice"
grep -qF "seul un repair s'ajoute sans approbation" <<<"$refusal" || fail "unexpected refusal: $refusal"
[ "$before" = "$(tracker)" ] || fail "a refused patch wrote to the real tracker"
# A repair without demonstration line is refused as any ticket (T05's refusal).
BAD=$(revision "$(edited 'del repair["demonstration_line"]; d["tickets"].append(repair)')" "$GRAPH_DIGEST")
before=$(tracker)
set +e
refusal=$(patch "$BAD" 2>&1 >/dev/null); rc=$?
set -e
[ "$rc" != 0 ] || fail "a patch added a repair without demonstration line"
grep -qF -- "- R1 : pas de ligne de démonstration" <<<"$refusal" || fail "unexpected refusal: $refusal"
[ "$before" = "$(tracker)" ] || fail "a refused patch wrote to the real tracker"
# The repair alone, blocking T2: published, tracked by the convoy, marked.
REPAIR=$(revision "$(edited 'd["tickets"] = [t["T1"], t["T2"], repair]; t["T2"]["blocked_by"] = ["T1", "R1"]')" "$GRAPH_DIGEST")
patched=$(patch "$REPAIR") || fail "an unapproved patch that only adds a repair was refused"
R1=$(jq -r '.ids.R1' <<<"$patched")
jq -e '.created == ["R1"] and .approved == false and .mayor_notified == null' <<<"$patched" >/dev/null \
  || fail "unexpected patch result: $patched"
shown=$("$STATE" show "$CONVOY" --repo "$TRIAL/repo") || fail "the patched convoy is incoherent: $shown"
jq -e --arg r1 "$R1" '.unruled == false and (.tickets | length) == 5
  and (.tickets[] | select(.id == $r1) | .mark == "new-flow/v1" and .kind == "repair"
       and .demonstration_line == "Sur le produit lancé, la page (GET /) affiche de nouveau « Gamma »."
       and .counters == {"resumes": 0, "correction_rounds": 0})' <<<"$shown" >/dev/null \
  || fail "the added repair is not tracked by the convoy and marked: $shown"
gc bd show "$T2" --json | jq -e --arg r1 "$R1" '.[0].dependencies | any(.id == $r1 and .dependency_type == "blocks")' >/dev/null \
  || fail "T2 is not blocked by the added repair in the real tracker"
gc bd show "$T4" --json | jq -r '.[0].description' | grep -qF -- "- R1 (repair) — La liste retrouve son troisième élément" \
  || fail "a ticket the patch did not carry does not name its new sibling"

# --- T06: a ticket withdrawn after a resolved Planning Exception --------------
REGISTER="$TRIAL/register.json"
printf '{"beads": {"%s": {"blocked_by": []}}}' "$T4" >"$TRIAL/graph.json"
"$ROOT/bin/planning-exception" init --run essai --out "$REGISTER" >/dev/null
"$ROOT/bin/planning-exception" raise "$REGISTER" --graph "$TRIAL/graph.json" --bead "$T4" --kind topology --run essai \
  --decision-id pd-1 --summary "la sonde n'est plus voulue" --raised-by essai >/dev/null
WITHDRAWAL=$(revision "$(edited 'd["tickets"] = [t["T1"], t["T2"]]; t["T2"]["blocked_by"] = ["T1"]; d["withdrawn"] = [{"ticket": "T4", "planning_exception": "pd-1"}]')" \
  "$(jq -r .graph_digest <<<"$patched")" approved)
before=$(tracker)
set +e
refusal=$(patch "$WITHDRAWAL" --planning-exception-register "$REGISTER" 2>&1 >/dev/null); rc=$?
set -e
[ "$rc" != 0 ] || fail "a ticket was withdrawn while its Planning Exception is open"
grep -qF "la Planning Exception pd-1 n'est pas résolue" <<<"$refusal" || fail "unexpected refusal: $refusal"
grep -qF "couvertes par aucun ticket : 3 (" <<<"$refusal" || fail "the orphaned story is not named: $refusal"
[ "$before" = "$(tracker)" ] || fail "a refused withdrawal wrote to the real tracker"
"$ROOT/bin/planning-exception" resolve "$REGISTER" --decision pd-1 --kind tactical --note "Benjamin retire la sonde" >/dev/null
# The Spec, amended and approved again, no longer holds story 3.
gc bd update "$SPEC" --description "$(grep -v '^3\. As an exploitant' <<<"$SPEC_TEXT")" >/dev/null
gc bd update "$SPEC" --set-metadata "approved_digest=$(digest_of "$(gc bd show "$SPEC" --json | jq -r '.[0].description')")" >/dev/null
withdrawn=$(patch "$WITHDRAWAL" --planning-exception-register "$REGISTER") || fail "the withdrawal was refused"
jq -e --arg t4 "$T4" '.withdrawn == {"T4": $t4}' <<<"$withdrawn" >/dev/null || fail "unexpected withdrawal result: $withdrawn"
[ "$(gc bd show "$T4" --json | jq -r '.[0].status')" = closed ] || fail "the withdrawn ticket is not closed"
shown=$("$STATE" show "$CONVOY" --repo "$TRIAL/repo") || fail "the convoy is incoherent after the withdrawal: $shown"
jq -e --arg t4 "$T4" '.unruled == false and (.tickets[] | select(.id == $t4) | .gates | has("withdrawn"))' <<<"$shown" >/dev/null \
  || fail "the withdrawn ticket has no gate record: $shown"

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

echo "PASS: on the real tracker, the door refuses the redeclared Cockpit V2 draft without writing, publishes and marks a conformant draft with its pointers, refuses an orphan user story and an open operator need, adds a repair by patch without approval, withdraws a ticket behind its gate record, and publishes an undeclared draft as before"
