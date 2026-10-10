#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime and an isolated Dolt server
#
# Adoption trial of the red of an integration branch (T21, af-cbp84n) on the
# real tracker, in a disposable city that shares nothing with the live
# Factory: what bin/convoy-state writes of a red (`record-integration-red`,
# `set-integration-repair`, `clear-integration-red`) is one JSON record in
# one metadata value, written by `gc bd update --set-metadata` and removed by
# `--unset-metadata`. The fake tracker of tests/convoy-state-test.py only
# proves the command against what this trial observes of the real one.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
TOOL="$ROOT/bin/convoy-state"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

# A write that must pass: its refusal, if any, is the failure message.
state() {
  local out
  out=$("$TOOL" "$@") || fail "convoy-state $* did not pass: $out"
}

for required in gc bd jq git dolt; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

TRIAL=$(mktemp -d /tmp/af-cbp84n-convoy-stops.XXXXXX)
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
# Dolt, city path, session identity, GC_BIN), no FACTORY_ROOT and no shared HOME.
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$|FACTORY_ROOT$)' || true)
export HOME="$TRIAL/home" TMUX_TMPDIR="$TRIAL/tmux" CONVOY_STATE_LOCK_DIR="$TRIAL/locks"
# The tools name their city to gc from FACTORY_ROOT (af-2o6oyl); left unset,
# they name the repository they are run from -- the live Factory (af-xcfup7).
export FACTORY_ROOT="$TEST_CITY"
mkdir -p "$HOME" "$TMUX_TMPDIR"
dolt config --global --add user.name "convoy-stops trial" >/dev/null
dolt config --global --add user.email "trial@example.invalid" >/dev/null

gc init --template minimal --default-provider codex --skip-provider-readiness \
  --no-start --yes --name af-cbp84n-convoy-stops "$TEST_CITY" >/dev/null 2>&1 \
  || fail "gc init of the isolated city failed"
cd "$TEST_CITY"

CONVOY=$(gc bd create --title "convoi d'essai" --type convoy --silent 2>/dev/null)
T1=$(gc bd create --title "ticket d'essai" --type task --silent 2>/dev/null)
R1=$(gc bd create --title "repair d'essai" --type task --silent 2>/dev/null)
R2=$(gc bd create --title "second repair d'essai" --type task --silent 2>/dev/null)
gc bd update "$T1" --set-metadata gc.ticket_kind=prefactoring >/dev/null
for repair in "$R1" "$R2"; do
  gc bd update "$repair" --set-metadata gc.ticket_kind=repair >/dev/null
  gc bd dep add "$CONVOY" "$repair" --type tracks >/dev/null
done
gc bd dep add "$CONVOY" "$T1" --type tracks >/dev/null
state mark "$CONVOY" \
  --demonstration-line "$R1=La commande de régression se termine avec le code 0" \
  --demonstration-line "$R2=La commande de régression se termine avec le code 0"

BASE=0123456789abcdef0123456789abcdef01234567
RED=89abcdef0123456789abcdef0123456789abcdef
state set-integration "$CONVOY" --branch integration/essai --protected main --base "$BASE"

# The control is quoted as bin/spec-integration writes it: a command line with
# quotes, parentheses, an equals sign and accents, in one metadata value.
CONTROL="commande de régression (sh -c 'test ! -e rouge' --seuil=1) : code 1, sur integration/essai après reprise de main"
DETAIL="AssertionError: « liste » absente de la page d'accueil"
state record-integration-red "$CONVOY" --commit "$RED" --integration "$BASE" --protected "$BASE" \
  --control "$CONTROL" --detail "$DETAIL"
shown=$("$TOOL" show "$CONVOY") || fail "show after the red record failed: $shown"
jq -e --arg control "$CONTROL" --arg detail "$DETAIL" --arg red "$RED" --arg base "$BASE" '
  .unruled == false
  and (.convoy.integration_red | del(.at))
      == {control: $control, commit: $red, integration: $base, protected: $base, detail: $detail}
' <<<"$shown" >/dev/null || fail "red of the integration branch not read back from the real tracker: $shown"

# The same red again writes nothing.
before=$(gc bd show "$CONVOY" --json)
state record-integration-red "$CONVOY" --commit "$RED" --integration "$BASE" --protected "$BASE" \
  --control "$CONTROL" --detail "$DETAIL"
[ "$before" = "$(gc bd show "$CONVOY" --json)" ] || fail "the same red recorded again changed the tracker"

# One repair per red: a ticket that is not a repair, then a second repair, are refused.
set +e
"$TOOL" set-integration-repair "$CONVOY" --ticket "$T1" >/dev/null; rc=$?
set -e
[ "$rc" = 1 ] || fail "naming a ticket that is not a repair exited $rc, want 1"
[ "$before" = "$(gc bd show "$CONVOY" --json)" ] || fail "a refused repair of the red changed the tracker"
state set-integration-repair "$CONVOY" --ticket "$R1"
before=$(gc bd show "$CONVOY" --json)
set +e
out=$("$TOOL" set-integration-repair "$CONVOY" --ticket "$R2"); rc=$?
set -e
[ "$rc" = 1 ] || fail "a second repair for the same red exited $rc, want 1"
grep -q "un seul repair par rouge" <<<"$out" || fail "the refusal of a second repair does not say why: $out"
[ "$before" = "$(gc bd show "$CONVOY" --json)" ] || fail "a refused second repair changed the tracker"
shown=$("$TOOL" show "$CONVOY") || fail "show after the repair was named failed: $shown"
jq -e --arg r1 "$R1" '.unruled == false and .convoy.integration_red.repair == $r1' <<<"$shown" >/dev/null \
  || fail "repair of the red not read back from the real tracker: $shown"

# The red withdrawn: the record leaves the convoy bead.
state clear-integration-red "$CONVOY"
shown=$("$TOOL" show "$CONVOY") || fail "show after the red was withdrawn failed: $shown"
jq -e '.unruled == false and .convoy.integration_red == null' <<<"$shown" >/dev/null \
  || fail "red of the integration branch not withdrawn on the real tracker: $shown"
gc bd show "$CONVOY" --json | jq -e '.[0].metadata | has("gc.flow.integration_red") | not' >/dev/null \
  || fail "the red record is still on the convoy bead after clear-integration-red"

echo "PASS: the red of an integration branch, its one repair and its withdrawal are written and read back on the real tracker"
