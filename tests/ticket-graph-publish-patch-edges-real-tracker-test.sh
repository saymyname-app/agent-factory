#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime and an isolated Dolt server
#
# Adoption trial of the patch door's blocking edges (T48, af-1zxao6; Spec
# af-wf4w5r §4, user story 12) on the real tracker, in a disposable city that
# shares nothing with the live Factory. On bd 1.2.2 `bd create --deps
# blocks:<id>` makes <id> wait for the new issue: a ticket added by
# bin/ticket-graph-publish bd-patch with `blocked_by` was ready before its
# blocker, and its blocker waited for it (patch af-o8g4mo, 2026-10-09). The
# suites prove the door on a fake tracker, and tests/fake-tool-contract-test.py
# that this fake poses each edge as the real bd does; this trial proves the
# door itself on the real one:
#   1. new flow: an unapproved patch adds a repair and a second repair blocked
#      by the first. The second waits for the first, `bd ready` gives the first
#      and not the second, a pass of bin/convoy-advance leaves the second
#      waiting for its blocker, and it is ready once the first is closed.
#   2. old flow: an approved patch adds a ticket B blocked by the unfinished
#      ticket A. `bd ready` gives A and not B, B shows A among what it waits
#      for, A waits for nothing, and B is ready once A is closed.

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

TRIAL=$(mktemp -d /tmp/af-1zxao6-patch-edges.XXXXXX)
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
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$|FACTORY_ROOT$|CONVOY_|DISPATCH_DOOR_)' || true)
export HOME="$TRIAL/home" TMUX_TMPDIR="$TRIAL/tmux" CONVOY_STATE_LOCK_DIR="$TRIAL/locks"
export CONVOY_ADVANCE_LOCK_DIR="$TRIAL/locks"
mkdir -p "$HOME" "$TMUX_TMPDIR" "$TRIAL/repo" "$TRIAL/locks"
dolt config --global --add user.name "patch-edges trial" >/dev/null
dolt config --global --add user.email "trial@example.invalid" >/dev/null
git config --global user.name "patch-edges trial"
git config --global user.email "trial@example.invalid"
git init -q -b main "$TRIAL/repo"
git -C "$TRIAL/repo" commit -q --allow-empty -m base

gc init --template minimal --default-provider codex --skip-provider-readiness \
  --no-start --yes --name af-1zxao6-patch-edges "$TEST_CITY" >/dev/null 2>&1 \
  || fail "gc init of the isolated city failed"
cd "$TEST_CITY"

# The door reaches the tracker through `bd -C <workspace>` and never wakes a
# Mayor here: there is none in this city, and the live one is out of reach.
# bin/convoy-state and bin/convoy-advance reach it through `gc --city
# $FACTORY_ROOT`: the disposable city, never the root this script runs from.
export TICKET_GRAPH_BD_WORKSPACE="$TEST_CITY" TICKET_GRAPH_PUBLISH_SKIP_MAYOR_NOTIFY=1 FACTORY_ROOT="$TEST_CITY"

digest_of() {
  printf 'sha256:%s' "$(printf '%s' "$1" | sha256sum | cut -d' ' -f1)"
}

SPEC_TEXT=$(cat "$ROOT/tests/fixtures/delivery-fixture-city/spec.md")
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
  "$DOOR" bd-patch "$1" --author essai --reason "essai de patch" --project acme --repo-root "$TRIAL/repo" \
    --config-dir "$PROJECTS" --descriptors-dir "$TRIAL/descriptors"
}

# What the real tracker says of a bead: the beads it waits for, and whether
# `bd ready` gives it.
waits_for() {
  gc bd show "$1" --json | jq -r '[.[0].dependencies // [] | .[] | select(.dependency_type == "blocks") | .id] | sort | join(",")'
}
ready() { # <id>...: those of the given beads `bd ready` lists, in the given order
  local listed out="" id
  listed=$(gc bd ready --json --limit 0 | jq -r '.[].id')
  for id in "$@"; do
    if grep -qxF -- "$id" <<<"$listed"; then out+="${out:+,}$id"; fi
  done
  printf '%s' "$out"
}

echo "relevé d'essai — arêtes bloquantes d'un patch sur le tracker réel ($(bd --version 2>/dev/null | head -1))"

# --- 1. new flow: a repair blocked by another added repair --------------------
# A draft of the new flow is published only with a graph review that holds
# for its digest (T08): this one answers every question favorably.
mkdir -p "$TRIAL/factory/config"
echo '{"roles": {"reviewer": {"agent": "delivery-reviewer"}}}' > "$TRIAL/factory/config/delivery-roles.json"
printf '[providers.reviewer-profile]\nargs_append = ["--model", "modele-relecteur"]\n' > "$TRIAL/factory/city.toml"
review() {
  FACTORY_ROOT="$TRIAL/factory" GRAPH_REVIEW_BD_WORKSPACE="$TEST_CITY" DELIVERY_ROLE_READ_ONLY=1 \
    GRAPH_REVIEW_PROVIDER_FAILOVER_BIN="$ROOT/tests/fixtures/graph-review/provider-failover" "$ROOT/bin/graph-review" "$@"
}
CONFORMANT=$(draft "$(cat "$FIXTURES/fixture-city-new-flow-draft.yaml")")
review request "$CONFORMANT" --author-model modele-auteur >/dev/null || fail "graph review request refused"
review brief "$CONFORMANT" | jq '
  def answers($checks): {checks: ($checks | with_entries(.value = {state: "favorable"}))};
  {digest, tickets: (.tickets | map({key: .id, value: answers(.checks)}) | from_entries), graph: answers(.graph_checks)}
' > "$TRIAL/graph-verdict.json"
review record "$CONFORMANT" --verdict-file "$TRIAL/graph-verdict.json" >/dev/null || fail "graph review verdict refused"
result=$(publish "$CONFORMANT") || fail "the conformant draft was refused"
CONVOY=$(jq -r '.ids._convoy' <<<"$result")
GRAPH_DIGEST=$(jq -r '.graph_digest' <<<"$result")
T1=$(jq -r '.ids.T1' <<<"$result"); T2=$(jq -r '.ids.T2' <<<"$result")
jq -e '.flow_contract == "new-flow/v1"' <<<"$result" >/dev/null || fail "the draft was not published as new flow: $result"

# Two repairs: RB is blocked by RA; T2, the Prototype Fold, waits for RB (an
# interface repair is before the Fold or after it, never beside it).
REVISED=$(python3 - "$FIXTURES/fixture-city-new-flow-draft.yaml" <<'PY'
import copy, sys, yaml
d = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
t = {ticket["id"]: ticket for ticket in d["tickets"]}
ra = {"id": "RA", "kind": "repair", "title": "La liste retrouve son troisième élément",
      "blocked_by": [], "target_rigs": ["fixture_city"],
      "what_it_delivers": "La page affiche de nouveau les trois éléments.",
      "restores": {"kind": "user_story", "ref": "user story 2"},
      "demonstration_line": "Sur le produit lancé, la page (GET /) affiche de nouveau « Gamma ».",
      "acceptance_criteria": [{"entry_point": "GET / sur le produit lancé",
                               "observable": "la région « liste » contient « Gamma »",
                               "false_if": "« Gamma » manque"}]}
rb = {**copy.deepcopy(ra), "id": "RB", "title": "La liste retrouve son ordre", "blocked_by": ["RA"],
      "what_it_delivers": "La page affiche de nouveau les éléments dans l'ordre.",
      "demonstration_line": "Sur le produit lancé, la page (GET /) affiche « Alpha » avant « Gamma »."}
t["T2"]["blocked_by"] = ["T1", "RB"]
d["tickets"] = [t["T1"], t["T2"], ra, rb]
print(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), end="")
PY
)
patched=$(patch "$(revision "$REVISED" "$GRAPH_DIGEST")") || fail "the unapproved patch that only adds two repairs was refused"
RA=$(jq -r '.ids.RA' <<<"$patched"); RB=$(jq -r '.ids.RB' <<<"$patched")
jq -e '(.created | sort) == ["RA", "RB"] and .approved == false' <<<"$patched" >/dev/null || fail "unexpected patch result: $patched"
shown=$("$STATE" show "$CONVOY" --repo "$TRIAL/repo") || fail "the patched convoy is incoherent: $shown"
jq -e --arg ra "$RA" --arg rb "$RB" '.unruled == false
  and ([.tickets[] | select(.id == $ra or .id == $rb) | .mark] == ["new-flow/v1", "new-flow/v1"])' <<<"$shown" >/dev/null \
  || fail "the added repairs are not tracked by the convoy and marked: $shown"
[ "$(gc bd show "$RB" --json | jq -r '.[0].metadata["gc.blocked_by"]')" = RA ] || fail "RB does not carry gc.blocked_by=RA"
[ "$(waits_for "$RB")" = "$RA" ] || fail "RB waits for « $(waits_for "$RB") » in the real tracker, want RA ($RA)"
[ -z "$(waits_for "$RA")" ] || fail "RA waits for « $(waits_for "$RA") » in the real tracker: the edge is backwards"
[ "$(ready "$RA" "$RB")" = "$RA" ] || fail "bd ready gives « $(ready "$RA" "$RB") » among RA ($RA) and RB ($RB), want RA alone"
echo "nouveau flux : RA=$RA RB=$RB (RB bloqué par RA) ; RB attend « $(waits_for "$RB") », RA n'attend rien ; bd ready : $(ready "$RA" "$RB")"

# One pass of bin/convoy-advance on the real tracker. This city has no agent
# and no running controller: whatever the dispatch door answers for a ticket
# that may start, the pass must leave RB waiting for its blocker and unstarted.
mkdir -p "$TEST_CITY/config"
cp -r "$PROJECTS" "$TEST_CITY/config/projects"
cp "$ROOT/config/delivery-roles.json" "$TEST_CITY/config/delivery-roles.json"
jq '.max_sessions = 9' "$ROOT/config/delivery-flow.json" > "$TEST_CITY/config/delivery-flow.json"
set +e
pass=$("$ROOT/bin/convoy-advance" "$CONVOY" 2>"$TRIAL/advance.err"); pass_rc=$?
set -e
jq -e . <<<"$pass" >/dev/null 2>&1 || fail "the pass of convoy-advance gave no answer (exit $pass_rc): $(head -c 600 "$TRIAL/advance.err")"
echo "passe de convoy-advance (exit $pass_rc) : $(jq -c --arg ra "$RA" --arg rb "$RB" '
  [.. | objects | select(has("started") and has("waiting"))][0]
  | {started, refused: [.refused[]? | (.id // .)], waiting: [.waiting[] | select(.id == $ra or .id == $rb)]}' <<<"$pass")"
jq -e --arg ra "$RA" --arg rb "$RB" '
  [.. | objects | select(has("started") and has("waiting"))][0] as $c
  | ($c.waiting | any(.id == $rb and (.reason | contains("bloqué par") and contains($ra))))
  and ($c.started | map(if type == "object" then .id else . end) | index($rb) | not)
  and ($c.waiting | any(.id == $ra and (.reason | contains("bloqué par"))) | not)' <<<"$pass" >/dev/null \
  || fail "the pass did not leave RB waiting for RA, or held RA behind a blocker: $pass"
gc bd show "$RB" --json | jq -e '.[0].metadata["gc.flow.gate.dispatch"] == null and .[0].metadata["gc.dispatched_via"] == null' >/dev/null \
  || fail "the pass started RB, which its blocker RA still blocks"

gc bd close "$RA" --reason "essai : le bloqueur est terminé" >/dev/null 2>&1 || fail "RA could not be closed"
[ "$(ready "$RB")" = "$RB" ] || fail "RB is not ready once its blocker RA is closed"
echo "nouveau flux : RA fermé ; bd ready : $(ready "$RA" "$RB")"

# --- 2. old flow: a ticket added behind an unfinished one ---------------------
LEGACY_A="- id: T1
  title: Un ticket de l'ancien flux
  blocked_by: []
  target_rigs: [fixture_city]
  what_it_delivers: fait une chose
  acceptance_criteria: [Un test montre que la chose est faite]"
LEGACY=$(draft "global_execution_contract:
  models: none
tickets:
$LEGACY_A")
result=$(publish "$LEGACY") || fail "a draft that does not declare the contract was refused"
PLAIN=$(jq -r '.ids._convoy' <<<"$result")
A=$(jq -r '.ids.T1' <<<"$result")
jq -e 'has("flow_contract") | not' <<<"$result" >/dev/null || fail "an undeclared draft was published as new flow"
LEGACY_REVISED=$(revision "global_execution_contract:
  models: none
tickets:
$LEGACY_A
- id: T2
  title: Un ticket ajouté derrière le premier
  blocked_by: [T1]
  target_rigs: [fixture_city]
  what_it_delivers: fait une autre chose
  acceptance_criteria: [Un test montre que l'autre chose est faite]" "$(jq -r '.graph_digest' <<<"$result")" approved)
patched=$(patch "$LEGACY_REVISED") || fail "the approved patch of the old flow was refused"
B=$(jq -r '.ids.T2' <<<"$patched")
jq -e '.created == ["T2"]' <<<"$patched" >/dev/null || fail "unexpected patch result: $patched"
[ "$(gc bd show "$B" --json | jq -r '.[0].metadata["gc.blocked_by"]')" = T1 ] || fail "B does not carry gc.blocked_by=T1"
[ "$(waits_for "$B")" = "$A" ] || fail "B waits for « $(waits_for "$B") » in the real tracker, want A ($A)"
[ -z "$(waits_for "$A")" ] || fail "A waits for « $(waits_for "$A") » in the real tracker: the edge is backwards"
[ "$(ready "$A" "$B")" = "$A" ] || fail "bd ready gives « $(ready "$A" "$B") » among A ($A) and B ($B), want A alone"
echo "ancien flux : A=$A B=$B (B bloqué par A) ; B attend « $(waits_for "$B") », A n'attend rien ; bd ready : $(ready "$A" "$B")"
# Observed, not judged here: how the old flow ties the added ticket to its convoy.
echo "ancien flux, observé : arêtes tracks de B : $(gc bd show "$B" --json | jq -c '[.[0].dependencies // [] | .[] | select(.dependency_type == "tracks") | .id]') ; du convoi $PLAIN : $(gc bd show "$PLAIN" --json | jq -c '[.[0].dependencies // [] | .[] | select(.dependency_type == "tracks") | .id]')"
gc bd close "$A" --reason "essai : le bloqueur est terminé" >/dev/null 2>&1 || fail "A could not be closed"
[ "$(ready "$B")" = "$B" ] || fail "B is not ready once its blocker A is closed"
echo "ancien flux : A fermé ; bd ready : $(ready "$A" "$B")"

echo "PASS: on the real tracker, a ticket added by bd-patch waits for the ticket that blocks it, in the new flow (a repair behind another added repair, left waiting by a pass of convoy-advance) and in the old one; it is ready once its blocker is closed"
