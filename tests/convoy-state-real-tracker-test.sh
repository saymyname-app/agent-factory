#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime and an isolated Dolt server
#
# Adoption trial of bin/convoy-state (T33, af-p4d6ec) on the real tracker, in
# a disposable city that shares nothing with the live Factory: the fake
# tracker of tests/convoy-state-test.py only proves the command against what
# this trial observes of the real `gc bd show` / `gc bd update`.

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

TRIAL=$(mktemp -d /tmp/af-p4d6ec-convoy-state.XXXXXX)
TEST_CITY="$TRIAL/city"
REPO="$TRIAL/repo"
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
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$)' || true)
export HOME="$TRIAL/home" TMUX_TMPDIR="$TRIAL/tmux" CONVOY_STATE_LOCK_DIR="$TRIAL/locks"
mkdir -p "$HOME" "$TMUX_TMPDIR"
dolt config --global --add user.name "convoy-state trial" >/dev/null
dolt config --global --add user.email "trial@example.invalid" >/dev/null
git config --global user.name "convoy-state trial"
git config --global user.email "trial@example.invalid"

gc init --template minimal --default-provider codex --skip-provider-readiness \
  --no-start --yes --name af-p4d6ec-convoy-state "$TEST_CITY" >/dev/null 2>&1 \
  || fail "gc init of the isolated city failed"
cd "$TEST_CITY"

CONVOY=$(gc bd create --title "convoi d'essai" --type convoy --silent 2>/dev/null)
T1=$(gc bd create --title "ticket d'essai 1" --type task --silent 2>/dev/null)
T2=$(gc bd create --title "ticket d'essai 2" --type task --silent 2>/dev/null)
PLAIN=$(gc bd create --title "convoi sans marque" --type convoy --silent 2>/dev/null)
T3=$(gc bd create --title "ticket d'un convoi sans marque" --type task --silent 2>/dev/null)
gc bd dep add "$CONVOY" "$T1" --type tracks >/dev/null
gc bd dep add "$CONVOY" "$T2" --type tracks >/dev/null
gc bd dep add "$PLAIN" "$T3" --type tracks >/dev/null

git init -q -b main "$REPO"
git -C "$REPO" commit -q --allow-empty -m base
git -C "$REPO" checkout -q -b ticket/t1
git -C "$REPO" commit -q --allow-empty -m "work on t1"
TIP=$(git -C "$REPO" rev-parse HEAD)

# --- a convoy without the mark is left exactly as it is ----------------------
before=$(gc bd show "$PLAIN" --json)
set +e
answer=$("$TOOL" show "$PLAIN" --repo "$REPO"); rc=$?
set -e
[ "$rc" = 4 ] || fail "show on an unmarked convoy exited $rc, want 4"
jq -e '.message | contains("pas un convoi du nouveau flux")' <<<"$answer" >/dev/null \
  || fail "unmarked convoy not reported as such: $answer"
set +e
"$TOOL" set-verdict "$PLAIN" "$T3" --kind code_review --state favorable --commit "$TIP" >/dev/null; rc=$?
set -e
[ "$rc" = 4 ] || fail "write on an unmarked convoy exited $rc, want 4"
[ "$before" = "$(gc bd show "$PLAIN" --json)" ] || fail "an unmarked convoy was written"

# --- the whole state, written then read back ---------------------------------
state mark "$CONVOY"
state set-branch "$CONVOY" "$T1" --branch ticket/t1
state record-gate "$CONVOY" "$T1" --gate dispatch
gc bd update "$T1" --status in_progress >/dev/null
state set-exit "$CONVOY" "$T1" --exit finished
state set-verdict "$CONVOY" "$T1" --kind code_review --state favorable --commit "$TIP"
state set-verdict "$CONVOY" "$T1" --kind evaluation --state unfavorable --commit "$TIP"
state bump-counter "$CONVOY" --ticket "$T1" --counter resumes --counter correction_rounds
state bump-counter "$CONVOY" --counter end_rounds
state add-evidence "$CONVOY" "$T1" --piece red_proof \
  --digest "sha256:$(printf essai | sha256sum | cut -d' ' -f1)" --commit "$TIP"

shown=$("$TOOL" show "$CONVOY" --repo "$REPO") || fail "show of a coherent convoy failed: $shown"
jq -e --arg t1 "$T1" --arg t2 "$T2" --arg tip "$TIP" '
  .unruled == false
  and .convoy.mark == "new-flow/v1" and .convoy.counters == {end_rounds: 1}
  and (.tickets | map(.id) | sort) == ([$t1, $t2] | sort)
  and (.tickets[] | select(.id == $t1)
       | .mark == "new-flow/v1" and .status == "in_progress" and .tip == $tip
         and .exit.exit == "finished"
         and .verdicts.code_review == (.verdicts.code_review | {state: "favorable", commit: $tip, valid: true, at})
         and .verdicts.evaluation.state == "unfavorable"
         and .counters == {resumes: 1, correction_rounds: 1}
         and .evidence.red_proof.commit == $tip
         and (.gates | keys) == ["dispatch"])
  and (.tickets[] | select(.id == $t2) | .counters == {resumes: 0, correction_rounds: 0} and .unruled == [])
' <<<"$shown" >/dev/null || fail "state read back from the real tracker is not what was written: $shown"

# --- a refused write leaves the real tracker untouched ------------------------
before=$(gc bd show "$CONVOY" --json)
for refused in \
  "set-verdict $CONVOY $T1 --kind code_review --state favorable" \
  "set-verdict $CONVOY $T1 --kind code_review --state approved --commit $TIP" \
  "set-counter $CONVOY --ticket $T1 --counter resumes --value -1"; do
  set +e
  # shellcheck disable=SC2086
  "$TOOL" $refused >/dev/null; rc=$?
  set -e
  [ "$rc" = 1 ] || fail "'$refused' exited $rc, want 1"
done
[ "$before" = "$(gc bd show "$CONVOY" --json)" ] || fail "a refused write changed the tracker"

# --- a commit after the verdict makes it invalid -----------------------------
git -C "$REPO" commit -q --allow-empty -m "one more commit"
shown=$("$TOOL" show "$CONVOY" --repo "$REPO") || fail "show after a new commit failed: $shown"
jq -e --arg t1 "$T1" '.tickets[] | select(.id == $t1) | .verdicts.code_review.valid == false' <<<"$shown" >/dev/null \
  || fail "verdict still valid after the branch tip moved: $shown"

# --- a ticket closed outside the gate is an "état sans règle" ----------------
gc bd close "$T1" --reason "fermé à la main pour l'essai" >/dev/null
set +e
shown=$("$TOOL" show "$CONVOY" --repo "$REPO"); rc=$?
set -e
[ "$rc" = 3 ] || fail "show with a ticket closed outside the gate exited $rc, want 3"
jq -e --arg t1 "$T1" '.tickets[] | select(.id == $t1) | .signal == "état sans règle"' <<<"$shown" >/dev/null \
  || fail "ticket closed outside the gate not signalled: $shown"

echo "PASS: convoy-state reads and writes a marked convoy on the real tracker, and leaves an unmarked one untouched"
