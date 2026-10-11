#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime and an isolated Dolt server
#
# What an operator session and the planning tools do to a bead another actor
# holds, on the real tracker (af-bm9y90, af-tql60u), in a disposable city that
# shares nothing with the live Factory.
#
# Beads 1.3 refuses, exit 1, a `bd close` from any actor but the assignee and
# an `--assignee` written over another actor's in_progress claim. Beads 1.2.2
# refused neither. Two things written for 1.2.2 broke the day of the upgrade,
# and no test ran them against the installed bd: the Take over of
# docs/agents/issue-tracker.md (af-tql60u), and the closes of
# bin/planning-map and bin/planning-artifacts-close (af-bm9y90). This test
# runs them: it is the check docs/OPERATIONS.md names for a Beads upgrade.
#
#   1. the operator-session commands of docs/agents/issue-tracker.md, as
#      written there: Offer, Take over (a rival's is refused with exit 13 and
#      changes nothing), Resolve;
#   2. bin/planning-map close on a map a po-agent session holds, run without
#      that session's actor, as bin/spec-approve bd-approve runs it; and
#      close --abandon on a child a sibling session holds;
#   3. bin/planning-artifacts-close on a closed convoy whose Spec bead a
#      po-agent session still holds (Spec handoff) and whose Draft bead
#      nobody holds.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc bd jq git dolt; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

TRIAL=$(mktemp -d /tmp/af-bm9y90-held-bead.XXXXXX)
TEST_CITY="$TRIAL/city"
cleanup() {
  status=$?
  trap - EXIT
  # gc starts a named session on demand, in a tmux server whose command
  # line does not carry the trial directory: its socket does.
  for sock in "$TRIAL"/tmux/tmux-*/*; do
    [ -S "$sock" ] || continue
    tmux -S "$sock" kill-server >/dev/null 2>&1 || true
  done
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
# Dolt, city path, session identity, GC_BIN), no actor and no shared HOME.
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_|GH_BIN$)' || true)
export HOME="$TRIAL/home" TMUX_TMPDIR="$TRIAL/tmux" CONVOY_STATE_LOCK_DIR="$TRIAL/locks"
# The tools name their city to gc from FACTORY_ROOT (af-2o6oyl); left unset,
# they name the repository they are run from -- the live Factory (af-xcfup7).
export FACTORY_ROOT="$TEST_CITY"
mkdir -p "$HOME" "$TMUX_TMPDIR" "$TRIAL/stubbin"
# A stub `codex` ahead of PATH: a write on a bead makes gc start the city's
# named session, and without the stub that session is the real codex CLI,
# left running after the test (five of them on 2026-10-11; the same trap as
# tests/local-only-tests-order-test.sh).
printf '#!/usr/bin/env bash\nexit 0\n' > "$TRIAL/stubbin/codex"
chmod +x "$TRIAL/stubbin/codex"
export PATH="$TRIAL/stubbin:$PATH"
dolt config --global --add user.name "held-bead trial" >/dev/null
dolt config --global --add user.email "trial@example.invalid" >/dev/null
# The actor of a write that names none: the tools below run as this one.
git config --global user.name "held-bead-trial"
git config --global user.email "trial@example.invalid"

gc init --template minimal --default-provider codex --skip-provider-readiness \
  --no-start --yes --name af-bm9y90-held-bead "$TEST_CITY" >/dev/null 2>&1 \
  || fail "gc init of the isolated city failed"
cd "$TEST_CITY"

# bin/planning-map runs plain `bd` from the city, as in the live root. BD_BIN
# stays unset: gc runs it too, so a BD_BIN that calls gc starts gc again
# without end (it filled the host's memory on 2026-10-11).

new() {  # title [create flags...]
  local title=$1
  shift
  gc bd create --title "$title" --type task --silent "$@" 2>/dev/null
}
field() {  # id jq-filter
  gc bd show "$1" --json 2>/dev/null | jq -r ".[0] | $2"
}
expect() {  # id jq-filter wanted what
  local got
  got=$(field "$1" "$2")
  [ "$got" = "$3" ] || fail "$4: $1 has $2 = '$got', wanted '$3'"
}

OFFERER=po-agent/offerer
TAKER=po-agent/taker
RIVAL=po-agent/rival

# --- 1. Operator-session commands of docs/agents/issue-tracker.md -----------
ticket=$(new "ticket offered by one session, run by another")
gc bd --actor "$OFFERER" update "$ticket" --claim >/dev/null 2>&1 \
  || fail "Offer: the claim of a free ticket was refused"
gc bd --actor "$OFFERER" update "$ticket" --set-metadata "wayfinder.offered_by=$OFFERER" >/dev/null 2>&1 \
  || fail "Offer: the offerer could not mark its own ticket"
gc bd --actor "$TAKER" update "$ticket" --if-assignee "$OFFERER" --assignee "$TAKER" \
  --unset-metadata wayfinder.offered_by >/dev/null 2>&1 \
  || fail "Take over: refused to the launched session (af-tql60u)"
expect "$ticket" '.assignee' "$TAKER" "Take over"
expect "$ticket" '.metadata["wayfinder.offered_by"] // ""' "" "Take over"
rc=0
gc bd --actor "$RIVAL" update "$ticket" --if-assignee "$OFFERER" --assignee "$RIVAL" \
  --unset-metadata wayfinder.offered_by >/dev/null 2>&1 || rc=$?
[ "$rc" = 13 ] || fail "Take over by a second session: exit $rc, wanted 13"
expect "$ticket" '.assignee' "$TAKER" "Take over by a second session"
gc bd --actor "$TAKER" close "$ticket" --reason "answered" >/dev/null 2>&1 \
  || fail "Resolve: the session that holds the ticket could not close it"
expect "$ticket" '.status' closed "Resolve"

# --- 2. bin/planning-map close on a held map ---------------------------------
map=$(new "map held by its /to-spec session" --labels wayfinder:map)
child=$(new "question already answered" --parent "$map" --no-inherit-labels)
gc bd close "$child" --reason "answered" >/dev/null 2>&1 || fail "could not close the free child of the map"
gc bd --actor "$TAKER" update "$map" --claim >/dev/null 2>&1 || fail "could not claim the map"
out=$("$ROOT/bin/planning-map" close --map "$map" --reason "Spec approved by trial") \
  || fail "planning-map close refused a map held by $TAKER: $out"
expect "$map" '.status' closed "planning-map close"
expect "$map" '.close_reason' "Spec approved by trial" "planning-map close"
grep -qF "$TAKER" <<<"$(field "$map" '.notes // ""')" \
  || fail "planning-map close: the closed map no longer names the session that held it"

map=$(new "map abandoned while a sibling session holds a ticket" --labels wayfinder:map)
child=$(new "question a sibling session is on" --parent "$map" --no-inherit-labels)
gc bd --actor "$RIVAL" update "$child" --claim >/dev/null 2>&1 || fail "could not claim the child"
gc bd --actor "$TAKER" update "$map" --claim >/dev/null 2>&1 || fail "could not claim the map"
out=$("$ROOT/bin/planning-map" close --map "$map" --reason "superseded" --abandon) \
  || fail "planning-map close --abandon refused a child held by $RIVAL: $out"
expect "$child" '.status' closed "planning-map close --abandon"
expect "$map" '.status' closed "planning-map close --abandon"

# --- 3. bin/planning-artifacts-close on a held Spec bead ----------------------
spec=$(new "Spec held through delivery (Spec handoff)")
draft=$(new "Ticket Graph Draft nobody holds")
gc bd --actor "$TAKER" update "$spec" --claim >/dev/null 2>&1 || fail "could not claim the Spec bead"
convoy=$(gc bd create --title "convoi d'essai" --type convoy --silent 2>/dev/null)
gc bd update "$convoy" --set-metadata "gc.artifact_id=$draft" --set-metadata "gc.spec_id=$spec" >/dev/null 2>&1 \
  || fail "could not stamp the convoy"
gc bd close "$convoy" --reason "delivered" >/dev/null 2>&1 || fail "could not close the convoy"
out=$("$ROOT/bin/planning-artifacts-close" 2>&1) \
  || fail "planning-artifacts-close failed on a Spec bead held by $TAKER: $out"
grep -q "closed=2 skipped=0 failed=0" <<<"$out" || fail "planning-artifacts-close did not close both beads: $out"
expect "$spec" '.status' closed "planning-artifacts-close"
expect "$draft" '.status' closed "planning-artifacts-close"
grep -qF "Convoy $convoy " <<<"$(field "$spec" '.close_reason // ""')" \
  || fail "planning-artifacts-close: the close reason of the Spec bead does not name the convoy"

echo "PASS: held-bead-close-real-tracker"
