#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime, an isolated Dolt server and a real Chromium
#
# Demonstration line of T16 (af-622nya), on the real tracker and the real
# browser, in a disposable city that shares nothing with the live Factory:
# bin/prototype-fidelity, run on the page of the Delivery Fixture City served
# at its real address, is green on every prototyped state; after an anchor is
# removed or a token changed it is red and names the anchor and the state.
# The result, the sealed record and the side-by-side captures are read back
# from the real tracker and the evidence store; a deviation turns « accepté
# par Benjamin » only once the Planning Exception that names its anchor is
# answered so. tests/prototype-fidelity-test.py proves the same contract on a
# fake tracker and a fake browser.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
TOOL="$ROOT/bin/prototype-fidelity"
STATE="$ROOT/bin/convoy-state"
CAPTURE="$ROOT/bin/evidence-capture"
FIXTURE="tests/fixtures/delivery-fixture-city"
STYLE='<style>:root{--fixture-accent:#0b5fff;--fixture-gap:12px}h1{color:var(--fixture-accent);font-size:28px}ul{padding:var(--fixture-gap)}</style>'

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc bd jq git dolt sha256sum; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

# The browser is looked up with the operator's HOME, before the trial replaces it.
BROWSER=${EVIDENCE_CAPTURE_BROWSER:-}
[ -n "$BROWSER" ] || BROWSER=$(command -v chrome-headless-shell 2>/dev/null) || true
if [ -z "$BROWSER" ]; then
  BROWSER=$(ls -1 "$HOME"/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell 2>/dev/null | sort -r | head -1)
fi
[ -n "$BROWSER" ] && [ -x "$BROWSER" ] || fail "no chrome-headless-shell found (set EVIDENCE_CAPTURE_BROWSER)"

TRIAL=$(mktemp -d /tmp/af-622nya-prototype-fidelity.XXXXXX)
TEST_CITY="$TRIAL/city"
PRODUCT="$TRIAL/product"
PROTOTYPE="$TRIAL/prototype"
cleanup() {
  status=$?
  trap - EXIT
  # The city's managed Dolt server, and a product a failed run left launched:
  # their command lines carry the trial directory, and nothing else does.
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

factory_git_state() {
  git -C "$ROOT" status --porcelain --untracked-files=all
  # The checkout's own commit, not a count over every ref: the refs of the
  # repository move under any other work tree or fetch during the run (T49).
  git -C "$ROOT" rev-parse HEAD
}
FACTORY_BEFORE=$(factory_git_state)

# Nothing of the live Factory may reach this city: no GC_* variable (hosted
# Dolt, city path, session identity, GC_BIN) and no shared HOME.
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$)' || true)
export HOME="$TRIAL/home" TMUX_TMPDIR="$TRIAL/tmux" CONVOY_STATE_LOCK_DIR="$TRIAL/locks" TMPDIR="$TRIAL/tmp"
# The tools name their city to gc from FACTORY_ROOT (af-2o6oyl); left unset,
# they name the repository they are run from -- the live Factory (af-xcfup7).
export FACTORY_ROOT="$TEST_CITY"
export EVIDENCE_STORE_DIR="$TRIAL/store" EVIDENCE_CAPTURE_BROWSER="$BROWSER"
mkdir -p "$HOME" "$TMUX_TMPDIR" "$TMPDIR"
dolt config --global --add user.name "prototype-fidelity trial" >/dev/null
dolt config --global --add user.email "trial@example.invalid" >/dev/null
git config --global user.name "prototype-fidelity trial"
git config --global user.email "trial@example.invalid"

# The product is a copy of the fixture in its own repository, so that the
# trial can deliver a deviation; the prototype is a copy of the frozen one.
mkdir -p "$PRODUCT/$(dirname "$FIXTURE")"
cp -r "$ROOT/$FIXTURE" "$PRODUCT/$FIXTURE"
cp -r "$ROOT/$FIXTURE/prototype" "$PROTOTYPE"
DESCRIPTOR="$PRODUCT/$FIXTURE/descriptor.json"
APP="$PRODUCT/$FIXTURE/app.py"
git -C "$PRODUCT" init -q -b main
deliver() {
  git -C "$PRODUCT" add -A
  git -C "$PRODUCT" commit -q -m "$1"
  git -C "$PRODUCT" rev-parse HEAD
}
COMMIT=$(deliver "produit conforme")

gc init --template minimal --default-provider codex --skip-provider-readiness \
  --no-start --yes --name af-622nya-prototype-fidelity "$TEST_CITY" >/dev/null 2>&1 \
  || fail "gc init of the isolated city failed"
cd "$TEST_CITY"

SPEC=$(gc bd create --title "Spec d'essai" --type task --silent 2>/dev/null)
CONVOY=$(gc bd create --title "convoi d'essai" --type convoy --silent 2>/dev/null)
T1=$(gc bd create --title "ticket d'essai" --type task --silent 2>/dev/null)
gc bd update "$CONVOY" --set-metadata "gc.spec_id=$SPEC" >/dev/null
gc bd update "$T1" --set-metadata gc.ticket_kind=prefactoring >/dev/null
gc bd dep add "$CONVOY" "$T1" --type tracks >/dev/null
"$STATE" mark "$CONVOY" >/dev/null || fail "the trial convoy could not be marked"
"$STATE" set-branch "$CONVOY" "$T1" --branch main >/dev/null || fail "the ticket branch could not be recorded"

check() {
  # check <expected exit> <commit>: the answer is left in $TRIAL/answer.json
  local expected=$1 commit=$2 rc
  set +e
  "$TOOL" check "$DESCRIPTOR" --repo-root "$PRODUCT" --commit "$commit" --prototype "$PROTOTYPE" \
    --convoy "$CONVOY" --ticket "$T1" >"$TRIAL/answer.json" 2>"$TRIAL/answer.err"
  rc=$?
  set -e
  [ "$rc" = "$expected" ] || fail "fidelity check exited $rc, expected $expected: $(head -c 2000 "$TRIAL/answer.json") $(cat "$TRIAL/answer.err")"
}
fidelity_on_ticket() {
  "$STATE" show "$CONVOY" --repo "$PRODUCT" | jq --arg t1 "$T1" '.tickets[] | select(.id == $t1)'
}

# --- the conforming fixture: green on every prototyped state -------------------
check 0 "$COMMIT"
jq -e '
  .ok and .result == "vert" and (.deviations | length) == 0 and (.states | keys) == ["content", "empty"]
  and ([.states[].records[] | .verdict] | unique) == ["identique"]
  and ([.states[] | .records | length] | unique) == [6]
' "$TRIAL/answer.json" >/dev/null || fail "the conforming fixture is not green on every state: $(cat "$TRIAL/answer.json")"
# The real browser computed real styles on both sides.
jq -e '.states.content.records | length == 6' "$TRIAL/answer.json" >/dev/null
PIECES="$EVIDENCE_STORE_DIR/$SPEC/$T1"
for state in empty content; do
  for viewport in desktop narrow; do
    piece="fidelity.$state.$viewport"
    jq -e --arg commit "$COMMIT" --arg state "$state" '
      .kind == "comparison" and .commit == $commit and (.reference | contains("/states/" + $state + ".html"))
      and (.pixels > 100000) and (.differing_pixels | type) == "number"
    ' "$PIECES/$piece.json" >/dev/null || fail "capture $piece is not a comparison of both sides: $(cat "$PIECES/$piece.json" 2>&1)"
    for image in "$piece.png" "$piece--difference.png"; do
      [ "$(head -c 8 "$PIECES/$image" | od -An -tx1 | tr -d ' \n')" = "89504e470d0a1a0a" ] || fail "$image is not a PNG image"
      [ "$(stat -c %s "$PIECES/$image")" -gt 1000 ] || fail "$image is an empty image"
    done
  done
done
"$CAPTURE" verify "$CONVOY" "$T1" >/dev/null || fail "the pieces of the fidelity check do not verify"
fidelity_on_ticket | jq -e --arg commit "$COMMIT" '
  .fidelity.state == "vert" and .fidelity.commit == $commit and .fidelity.screens == ["accueil"]
  and .verdicts.fidelity.state == "favorable" and .verdicts.fidelity.valid == true
  and .evidence.fidelity.commit == $commit
' >/dev/null || fail "the green result is not read back from the real tracker: $(fidelity_on_ticket)"

# --- the same style sheet on both sides, then a token changed: red, named ------
for page in "$PROTOTYPE"/states/*.html; do
  sed -i "s|</head>|$STYLE\n</head>|" "$page"
done
sed -i "s|</title></head>|</title>$STYLE</head>|" "$APP"
STYLED=$(deliver "feuille de style")
check 0 "$STYLED"
jq -e '.result == "vert" and .states.content.tokens.compared == 2' "$TRIAL/answer.json" >/dev/null \
  || fail "the styled fixture is not green with its two tokens compared: $(cat "$TRIAL/answer.json")"
sed -i 's#--fixture-gap:12px#--fixture-gap:16px#' "$APP"
TOKEN=$(deliver "token modifié")
check 1 "$TOKEN"
jq -e '
  .result == "rouge"
  and ([.deviations[] | select(.kind == "token" and .property == "--fixture-gap" and .prototype == "12px" and .delivered == "16px") | .state] | sort) == ["content", "empty"]
  and ([.deviations[] | select(.anchor == "fixture-items" and .kind == "style" and .property == "padding" and .state == "content" and .viewport == "desktop")] | length) == 1
  and ([.deviations[] | select(.kind == "style") | .anchor] | unique) == ["fixture-items"]
' "$TRIAL/answer.json" >/dev/null || fail "a changed token is not red with the token, the anchor and the state named: $(jq .deviations "$TRIAL/answer.json")"

# --- an anchor removed: red, the anchor and the state named ---------------------
sed -i 's#--fixture-gap:16px#--fixture-gap:12px#; s#<ul data-anchor="fixture-items">#<ul>#' "$APP"
ANCHOR=$(deliver "ancre retirée")
check 1 "$ANCHOR"
jq -e '
  .result == "rouge" and ([.deviations[] | .anchor] | unique) == ["fixture-items"]
  and ([.deviations[] | select(.kind == "absent") | .state + "/" + .viewport] | sort)
      == ["content/desktop", "content/narrow", "empty/desktop", "empty/narrow"]
' "$TRIAL/answer.json" >/dev/null || fail "a removed anchor is not red with the anchor and the state named: $(jq .deviations "$TRIAL/answer.json")"
fidelity_on_ticket | jq -e --arg commit "$ANCHOR" '
  .fidelity.state == "rouge" and .fidelity.commit == $commit and .verdicts.fidelity.state == "unfavorable"
  and ([.fidelity.deviations[] | .status] | unique) == ["ouvert"]
' >/dev/null || fail "the red result is not read back from the real tracker: $(fidelity_on_ticket)"

# --- only a resolved Planning Exception that names the anchor accepts it -------
"$STATE" raise-planning-exception "$CONVOY" "$T1" --kind semantic --summary "La liste est livrée sans sa région" \
  --anchor fixture-items --accept-option c >/dev/null || fail "the Planning Exception could not be recorded"
fidelity_on_ticket | jq -e '.fidelity.state == "rouge" and .planning_exceptions[0].state == "open"' >/dev/null \
  || fail "a Planning Exception that is not answered lifted the red: $(fidelity_on_ticket)"
check 1 "$ANCHOR"
# What bin/escalation-door repondre writes on the ticket when the operator
# answers « c » (the door itself mails the Mayor, which this city has not).
sleep 1
gc bd update "$T1" --set-metadata gc.needs_benjamin=none --set-metadata gc.escalation_response_option=c \
  --set-metadata "gc.escalation_response_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --set-metadata gc.escalation_response_actor=benjamin >/dev/null
fidelity_on_ticket | jq -e '
  .fidelity.state == "accepté par Benjamin" and .accepted_anchors == ["fixture-items"]
  and .fidelity.verdict == "unfavorable" and .planning_exceptions[0].accepted == true
' >/dev/null || fail "the answered Planning Exception did not turn the deviation accepted: $(fidelity_on_ticket)"
check 0 "$ANCHOR"
jq -e '.result == "accepté par Benjamin" and ([.deviations[] | .status] | unique) == ["accepté par Benjamin"]' \
  "$TRIAL/answer.json" >/dev/null || fail "the command does not read the accepted deviation: $(cat "$TRIAL/answer.json")"

# --- nothing is left running, nothing reached the Factory ----------------------
[ -z "$(git -C "$PRODUCT" worktree list --porcelain | grep -c '^worktree' | grep -v '^1$' || true)" ] \
  || fail "a launched product left its work tree behind: $(git -C "$PRODUCT" worktree list)"
[ "$FACTORY_BEFORE" = "$(factory_git_state)" ] || fail "the fidelity check changed the Factory's Git state"

echo "PASS: the fixture is green on every prototyped state at its real address; a changed token and a removed anchor are red with the anchor, the state and the property named; the result, its sealed record and the side-by-side captures are read back from the real tracker; only an answered Planning Exception that names the anchor turns the deviation « accepté par Benjamin »"
