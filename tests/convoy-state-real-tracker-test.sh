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
# The tools name their city to gc from FACTORY_ROOT (af-2o6oyl); left unset,
# they name the repository they are run from -- the live Factory (af-xcfup7).
export FACTORY_ROOT="$TEST_CITY"
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
# A ticket is marked with its kind (T05); a prefactoring needs no demonstration line.
for ticket in "$T1" "$T2" "$T3"; do
  gc bd update "$ticket" --set-metadata gc.ticket_kind=prefactoring >/dev/null
done
# A slice with acceptance criteria in its description (T10, af-j8jo02).
T4=$(gc bd create --title "tranche d'essai" --type task --silent 2>/dev/null)
gc bd update "$T4" --set-metadata gc.ticket_kind=vertical_slice --description "## What to build

- [ ] pas un critère

## Acceptance criteria

- [ ] Le nombre d'éléments s'affiche
- [ ] La sonde nomme le jeu de données

## Target rigs

agent-factory" >/dev/null
gc bd dep add "$CONVOY" "$T1" --type tracks >/dev/null
gc bd dep add "$CONVOY" "$T2" --type tracks >/dev/null
gc bd dep add "$CONVOY" "$T4" --type tracks >/dev/null
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
state mark "$CONVOY" --demonstration-line "$T4=La page d'accueil affiche 3" --user-stories "$T4=1"
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
jq -e --arg t1 "$T1" --arg t2 "$T2" --arg t4 "$T4" --arg tip "$TIP" '
  .unruled == false
  and .convoy.mark == "new-flow/v1" and .convoy.counters == {end_rounds: 1}
  and (.tickets | map(.id) | sort) == ([$t1, $t2, $t4] | sort)
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

# --- acceptance criteria, steps of the TDD and stop of a ticket (T10) ---------
BASE=$(git -C "$REPO" rev-parse main)
state set-tdd "$CONVOY" "$T4" --step red --commit "$TIP" --base "$BASE"
# A freeze follows a favorable review of the criterion tests, given at the
# commit of the red (Spec §5): the trial records both as bin/test-review does.
REVIEWED='{"tests/test_probe.py": "sha256:'$(printf 'test de critère' | sha256sum | cut -d' ' -f1)'"}'
jq -n --argjson files "$REVIEWED" \
  '{files: $files, criteria: {"1": ["tests/test_probe.py::test_count"], "2": ["tests/test_probe.py::test_dataset"]}}' \
  >"$TRIAL/test-review-request.json"
state open-test-review "$CONVOY" "$T4" --commit "$TIP" --file "$TRIAL/test-review-request.json"
jq -n --argjson files "$REVIEWED" --arg commit "$TIP" \
  '{commit: $commit, files: $files, recorded_by: "trial-test-reviewer",
    tests: {"tests/test_probe.py::test_count": {state: "favorable"}, "tests/test_probe.py::test_dataset": {state: "favorable"}}}' \
  >"$TRIAL/test-review-verdict.json"
state record-test-review "$CONVOY" "$T4" --file "$TRIAL/test-review-verdict.json"
state set-tdd "$CONVOY" "$T4" --step freeze --commit "$TIP"
state set-tdd "$CONVOY" "$T4" --step amendment --commit "$TIP" --reason "le champ s'appelle « dataset_name » dans la Spec"
state set-tdd "$CONVOY" "$T4" --step green --commit "$TIP"
state set-tdd "$CONVOY" "$T2" --step prefactoring --commit "$TIP" --base "$BASE"
state stop-ticket "$CONVOY" "$T2" --reason amendment_exhausted --detail "un seul amendement par ticket : essai"

shown=$("$TOOL" show "$CONVOY" --repo "$REPO") || fail "show after the TDD steps failed: $shown"
jq -e --arg t2 "$T2" --arg t4 "$T4" --arg tip "$TIP" --arg base "$BASE" '
  .unruled == false
  and (.tickets[] | select(.id == $t4)
       | .criteria == ["Le nombre d\u0027éléments s\u0027affiche", "La sonde nomme le jeu de données"]
         and (.tdd | keys) == ["amendment", "freeze", "green", "red"]
         and .tdd.red.commit == $tip and .tdd.red.base == $base and .tdd.freeze.commit == $tip
         and .tdd.amendment.reason == "le champ s\u0027appelle « dataset_name » dans la Spec"
         and .stop == null)
  and (.tickets[] | select(.id == $t2)
       | .criteria == [] and .tdd.prefactoring.base == $base
         and .stop.reason == "amendment_exhausted" and .stop.detail == "un seul amendement par ticket : essai")
' <<<"$shown" >/dev/null || fail "criteria, TDD steps or stop not read back from the real tracker: $shown"

# --- a refused write leaves the real tracker untouched ------------------------
before=$(gc bd show "$CONVOY" --json)
for refused in \
  "set-verdict $CONVOY $T1 --kind code_review --state favorable" \
  "set-verdict $CONVOY $T1 --kind code_review --state approved --commit $TIP" \
  "set-counter $CONVOY --ticket $T1 --counter resumes --value -1" \
  "set-tdd $CONVOY $T4 --step amendment --commit $TIP --reason encore" \
  "set-tdd $CONVOY $T4 --step red --commit $BASE --base $BASE" \
  "set-tdd $CONVOY $T2 --step prefactoring --commit $TIP --base $BASE"; do
  set +e
  # shellcheck disable=SC2086
  "$TOOL" $refused >/dev/null; rc=$?
  set -e
  [ "$rc" = 1 ] || fail "'$refused' exited $rc, want 1"
done
[ "$before" = "$(gc bd show "$CONVOY" --json)" ] || fail "a refused write changed the tracker"

# --- Ticket Handoff, parking and Declared Scope (T11, af-egkabn) ---------------
# T2 waits for T1 and T4 for T2; T5, added to the convoy since, waits for nothing.
T5=$(gc bd create --title "ticket sans lien" --type task --silent 2>/dev/null)
gc bd update "$T5" --set-metadata gc.ticket_kind=prefactoring \
  --set-metadata "gc.scope_paths=app/home.py,app/static/*" >/dev/null
gc bd dep add "$CONVOY" "$T5" --type tracks >/dev/null
gc bd dep add "$T2" "$T1" >/dev/null
gc bd dep add "$T4" "$T2" >/dev/null
state mark "$CONVOY"

# A Handoff of some twenty kilobytes, with quotes, « », = and accents in it.
HANDOFF="$TRIAL/handoff.json"
jq -n --arg tip "$TIP" '{
  sections: {
    done: [range(0; 150) | "Critère \(.) : l\u0027observation « a=b » obtenue sur GET /?jeu=contenu, champ \"label\" non vide, éléments Alpha, Bêta, Gamma"],
    deviations: "aucun",
    not_done: [{what: "La sonde n\u0027est pas branchée.", paths: ["app/home.py"]}],
    out_of_ticket: "aucun"},
  partial: false, commit: $tip,
  records: {commits: [{commit: $tip, subject: "work on t1"}], files_outside_declared_scope: ["README.md"],
            deferral_markers: [{path: "app/home.py", line: 3, marker: "TODO", text: "# TODO brancher", declared: true}]}
}' >"$HANDOFF"
[ "$(wc -c <"$HANDOFF")" -gt 20000 ] || fail "the trial Handoff is smaller than intended"
set +e
"$TOOL" set-handoff "$CONVOY" "$T1" --file "$HANDOFF" >/dev/null; rc=$?
set -e
[ "$rc" = 1 ] || fail "a Handoff whose records no piece seals exited $rc, want 1"
state add-evidence "$CONVOY" "$T1" --piece handoff_records \
  --digest "sha256:$(sha256sum <"$HANDOFF" | cut -d' ' -f1)" --commit "$TIP"
state set-handoff "$CONVOY" "$T1" --file "$HANDOFF"
state park "$CONVOY" "$T1" --cause planning_exception --detail "La Spec fixe l'ordre « alphabétique » ; a=b ?"

shown=$("$TOOL" show "$CONVOY" --repo "$REPO") || fail "show after the Handoff and the parking failed: $shown"
jq -e --arg t1 "$T1" --arg t2 "$T2" --arg t4 "$T4" --arg t5 "$T5" --slurpfile given "$HANDOFF" '
  .unruled == false
  and (.tickets[] | select(.id == $t1)
       | (.handoff | del(.at)) == $given[0]
         and .park.cause == "planning_exception" and .park.origin == $t1
         and .park.detail == "La Spec fixe l\u0027ordre « alphabétique » ; a=b ?")
  and ([.tickets[] | select(.id == $t2 or .id == $t4) | .park.origin] == [$t1, $t1])
  and (.tickets[] | select(.id == $t5)
       | .park == null and .handoff == null and .declared_scope == ["app/home.py", "app/static/*"])
' <<<"$shown" >/dev/null || fail "Handoff, parking or Declared Scope not read back from the real tracker: $shown"

before=$(gc bd show "$CONVOY" --json)
set +e
"$TOOL" park "$CONVOY" "$T1" --cause planning_exception --detail "encore" >/dev/null; rc=$?
set -e
[ "$rc" = 1 ] || fail "parking a parked ticket exited $rc, want 1"
[ "$before" = "$(gc bd show "$CONVOY" --json)" ] || fail "a refused parking changed the tracker"

# --- a commit after the verdict makes it invalid -----------------------------
git -C "$REPO" commit -q --allow-empty -m "one more commit"
shown=$("$TOOL" show "$CONVOY" --repo "$REPO") || fail "show after a new commit failed: $shown"
jq -e --arg t1 "$T1" '.tickets[] | select(.id == $t1) | .verdicts.code_review.valid == false' <<<"$shown" >/dev/null \
  || fail "verdict still valid after the branch tip moved: $shown"

# --- the integration branch, a verdict made invalid, a merge (T18, af-gmz9s1) --
NEW_TIP=$(git -C "$REPO" rev-parse HEAD)
BASE=$(git -C "$REPO" rev-parse main)
state set-integration "$CONVOY" --branch integration/essai --protected main --base "$BASE"
state invalidate-verdicts "$CONVOY" "$T1" --tip "$NEW_TIP" --kind code_review --kind evaluation
# a second time: already invalid, nothing more is counted
state invalidate-verdicts "$CONVOY" "$T1" --tip "$NEW_TIP" --kind code_review
state set-merge "$CONVOY" "$T1" --outcome red --ticket-commit "$NEW_TIP" --integration "$BASE" --commit "$TIP"

shown=$("$TOOL" show "$CONVOY" --repo "$REPO") || fail "show after the integration records failed: $shown"
jq -e --arg t1 "$T1" --arg tip "$TIP" --arg new "$NEW_TIP" --arg base "$BASE" '
  .unruled == false
  and (.convoy.integration | del(.at)) == {branch: "integration/essai", protected: "main", base: $base}
  and (.tickets[] | select(.id == $t1)
       | .verdicts.code_review.valid == false and .verdicts.code_review.invalidated.tip == $new
         and .verdicts.code_review.commit == $tip and .verdicts.code_review.state == "favorable"
         and .verdicts.evaluation.invalidated.tip == $new
         and .counters == {resumes: 2, correction_rounds: 1}
         and (.merge | del(.at)) == {outcome: "red", ticket_commit: $new, integration: $base, commit: $tip})
' <<<"$shown" >/dev/null || fail "integration branch, invalidated verdicts or merge not read back from the real tracker: $shown"

before=$(gc bd show "$CONVOY" --json)
set +e
"$TOOL" set-integration "$CONVOY" --branch integration/autre --protected main --base "$BASE" >/dev/null; rc=$?
set -e
[ "$rc" = 1 ] || fail "recording another integration branch exited $rc, want 1"
[ "$before" = "$(gc bd show "$CONVOY" --json)" ] || fail "a refused integration record changed the tracker"

# --- a ticket closed outside the gate is an "état sans règle" ----------------
gc bd close "$T1" --reason "fermé à la main pour l'essai" >/dev/null
set +e
shown=$("$TOOL" show "$CONVOY" --repo "$REPO"); rc=$?
set -e
[ "$rc" = 3 ] || fail "show with a ticket closed outside the gate exited $rc, want 3"
jq -e --arg t1 "$T1" '.tickets[] | select(.id == $t1) | .signal == "état sans règle"' <<<"$shown" >/dev/null \
  || fail "ticket closed outside the gate not signalled: $shown"

echo "PASS: convoy-state reads and writes a marked convoy on the real tracker, and leaves an unmarked one untouched"
