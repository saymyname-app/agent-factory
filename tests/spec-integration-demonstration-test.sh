#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime and an isolated Dolt server
#
# Demonstration line of T18 (af-gmz9s1), on the real tracker, in a disposable
# city that shares nothing with the live Factory: two tickets of the Delivery
# Fixture City finished at the same time are merged one after the other into
# the integration branch of their Spec, with a test record on each merged
# result; a commit added to the branch of the second after its verdict makes
# that verdict invalid, and the merge is refused. tests/spec-integration-test.py
# proves the same contract, refusal by refusal, on a fake tracker.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
TOOL="$ROOT/bin/spec-integration"
STATE="$ROOT/bin/convoy-state"
FIXTURE="tests/fixtures/delivery-fixture-city"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

# A write that must pass: its refusal, if any, is the failure message.
state() {
  local out
  out=$("$STATE" "$@") || fail "convoy-state $* did not pass: $out"
}

for required in gc bd jq git dolt python3 sha256sum; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

TRIAL=$(mktemp -d /tmp/af-gmz9s1-spec-integration.XXXXXX)
TEST_CITY="$TRIAL/city"
REPO="$TRIAL/product"
ORIGIN="$TRIAL/origin.git"
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

factory_git_state() {
  git -C "$ROOT" status --porcelain --untracked-files=all
  git -C "$ROOT" for-each-ref
  git -C "$ROOT" worktree list
}
FACTORY_BEFORE=$(factory_git_state)

# Nothing of the live Factory may reach this city: no GC_* variable (hosted
# Dolt, city path, session identity, GC_BIN) and no shared HOME.
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$|FACTORY_ROOT$)' || true)
export HOME="$TRIAL/home" TMUX_TMPDIR="$TRIAL/tmux" CONVOY_STATE_LOCK_DIR="$TRIAL/locks"
export EVIDENCE_STORE_DIR="$TRIAL/store" SPEC_INTEGRATION_LOCK_DIR="$TRIAL/locks" SPEC_INTEGRATION_WORK_DIR="$TRIAL/work"
mkdir -p "$HOME" "$TMUX_TMPDIR"
dolt config --global --add user.name "spec-integration trial" >/dev/null
dolt config --global --add user.email "trial@example.invalid" >/dev/null
git config --global user.name "spec-integration trial"
git config --global user.email "trial@example.invalid"

gc init --template minimal --default-provider codex --skip-provider-readiness \
  --no-start --yes --name af-gmz9s1-spec-integration "$TEST_CITY" >/dev/null 2>&1 \
  || fail "gc init of the isolated city failed"

# --- the product of the fixture, its remote, its protected branch -------------
mkdir -p "$REPO/$(dirname "$FIXTURE")"
cp -r "$ROOT/$FIXTURE" "$REPO/$FIXTURE"
# A bytecode cache left by an earlier test would be committed, then rewritten
# by the merged tests: the work tree would match no commit.
find "$REPO/$FIXTURE" -type d -name __pycache__ -prune -exec rm -rf {} +
PROFILE="$REPO/$FIXTURE/descriptor.json"
git init -q -b main "$REPO"
git -C "$REPO" add -A
git -C "$REPO" commit -q -m base
git init -q --bare -b main "$ORIGIN"
git -C "$REPO" remote add origin "$ORIGIN"
git -C "$REPO" push -q origin main
BASE=$(git -C "$REPO" rev-parse main)

# --- a marked convoy of two slices of the fixture -----------------------------
cd "$TEST_CITY"
SPEC=$(gc bd create --title "Spec d'essai" --type task --silent 2>/dev/null)
CONVOY=$(gc bd create --title "convoi d'essai" --type convoy --silent 2>/dev/null)
# A slice has acceptance criteria: its Ticket Evaluation gives one state per criterion.
CRITERIA="## Acceptance criteria

- [ ] Point d'entrée : GET / — Observable : la liste — Faux si : une ligne manque"
T1=$(gc bd create --title "tranche d'essai 1" --type task --silent --description "$CRITERIA" 2>/dev/null)
T2=$(gc bd create --title "tranche d'essai 2" --type task --silent --description "$CRITERIA" 2>/dev/null)
gc bd update "$CONVOY" --set-metadata "gc.spec_id=$SPEC" >/dev/null
for ticket in "$T1" "$T2"; do
  gc bd update "$ticket" --set-metadata gc.ticket_kind=vertical_slice >/dev/null
  gc bd dep add "$CONVOY" "$ticket" --type tracks >/dev/null
done
state mark "$CONVOY" --demonstration-line "$T1=La page d'accueil affiche les trois éléments" \
  --demonstration-line "$T2=GET /health répond 200" --user-stories "$T1=1" --user-stories "$T2=2"

# --- the integration branch of the Spec ---------------------------------------
opened=$("$TOOL" open "$CONVOY" --repo "$REPO" --protected main) || fail "the integration branch was not opened: $opened"
INTEGRATION="integration/$SPEC"
jq -e --arg branch "$INTEGRATION" --arg base "$BASE" '.branch == $branch and .base == $base and .created == true' \
  <<<"$opened" >/dev/null || fail "unexpected answer of open: $opened"
[ "$(git -C "$ORIGIN" rev-parse "refs/heads/$INTEGRATION")" = "$BASE" ] \
  || fail "the integration branch is not on the remote at the tip of the protected branch"

# What stands for the author of a ticket: one commit on its branch, pushed,
# then its Ticket Exit « terminé » at that commit (bin/ticket-exit, T11).
commit_on() {  # TICKET FILE TEXT
  local branch="ticket/$1"
  git -C "$REPO" checkout -q "$branch" 2>/dev/null || git -C "$REPO" checkout -q -b "$branch" "origin/$INTEGRATION"
  mkdir -p "$(dirname "$REPO/$2")"
  printf '%s\n' "$3" > "$REPO/$2"
  git -C "$REPO" add -A
  git -C "$REPO" commit -q -m "travail de $1"
  git -C "$REPO" push -q origin "$branch"
  git -C "$REPO" rev-parse HEAD
  git -C "$REPO" checkout -q --detach "$BASE"
}
finish() {  # TICKET COMMIT
  local handoff="$TRIAL/handoff-$1.json"
  jq -n --arg commit "$2" '{sections: {done: ["Critère 1 observé sur GET /."], deviations: "aucun", not_done: "aucun",
    out_of_ticket: "aucun"}, partial: false, commit: $commit, records: {}}' > "$handoff"
  state add-evidence "$CONVOY" "$1" --piece handoff_records \
    --digest "sha256:$(sha256sum <"$handoff" | cut -d' ' -f1)" --commit "$2"
  state set-handoff "$CONVOY" "$1" --file "$handoff"
  state set-exit "$CONVOY" "$1" --exit finished
}
evaluated() {  # TICKET COMMIT REPO: a favorable Ticket Evaluation, as an Evaluator session records it (bin/ticket-evaluation, T15)
  local shown
  shown=$("$ROOT/bin/convoy-state" show "$CONVOY" --repo "$3" | jq -c --arg t "$1" '.tickets[] | select(.id == $t)')
  jq -n '{roles: {author: null, evaluator: null, same_provider: null, other_declared: []},
    environment: [{dataset: null, address: "http://127.0.0.1:1", state_file: "/launch.json"}]}' > "$TRIAL/evaluation-request-$1.json"
  state open-evaluation "$CONVOY" "$1" --commit "$2" --file "$TRIAL/evaluation-request-$1.json" >/dev/null
  state add-evidence "$CONVOY" "$1" --piece evaluation.seen --digest "sha256:$(printf '%064d' 0)" --commit "$2" >/dev/null
  jq -n --arg commit "$2" --argjson t "$shown" '{commit: $commit, recorded_by: "delivery-evaluator-trial",
    criteria: [$t.criteria | to_entries[] | {number: (.key + 1), text: .value, state: "observed", evidence: "evaluation.seen"}],
    demonstration_line: {text: $t.demonstration_line, state: "observed", evidence: "evaluation.seen"}}' > "$TRIAL/evaluation-$1.json"
  state record-evaluation "$CONVOY" "$1" --file "$TRIAL/evaluation-$1.json" >/dev/null
}
judge() {  # TICKET COMMIT
  # The code review as a reviewer session records it (bin/code-review, T14),
  # and the Ticket Evaluation as an Evaluator session records it
  # (bin/ticket-evaluation, T15): the merge takes no ticket without them.
  jq -n --arg commit "$2" '{commit: $commit, recorded_by: "delivery-reviewer-trial", findings: [], answers: {}}' \
    > "$TRIAL/review-$1.json"
  state open-code-review "$CONVOY" "$1" --kind review --commit "$2" --base "$BASE"
  state record-code-review "$CONVOY" "$1" --file "$TRIAL/review-$1.json"
  evaluated "$1" "$2" "$REPO"
}

git -C "$REPO" fetch -q origin
for ticket in "$T1" "$T2"; do
  state record-gate "$CONVOY" "$ticket" --gate dispatch
  state set-branch "$CONVOY" "$ticket" --branch "ticket/$ticket"
  gc bd update "$ticket" --status in_progress >/dev/null
done
TIP1=$(commit_on "$T1" docs/t1.md "tranche 1")
TIP2=$(commit_on "$T2" docs/t2.md "tranche 2")
finish "$T1" "$TIP1"; judge "$T1" "$TIP1"
finish "$T2" "$TIP2"; judge "$T2" "$TIP2"

# --- a commit added to the branch of the second after its verdict --------------
NEWER=$(commit_on "$T2" docs/t2.md "tranche 2, retouchée après le verdict")
finish "$T2" "$NEWER"

set +e
answer=$("$TOOL" merge "$CONVOY" --repo "$REPO" --profile "$PROFILE"); rc=$?
set -e
[ "$rc" = 1 ] || fail "the pass with an outdated verdict exited $rc, want 1: $answer"
jq -e --arg t1 "$T1" --arg t2 "$T2" '
  .ok == false and ([.merged[].id] == [$t1])
  and ([.refused[].id] == [$t2]) and .refused[0].invalidated == ["code_review", "evaluation"]
' <<<"$answer" >/dev/null || fail "unexpected answer of the first pass: $answer"
FIRST=$(jq -r '.merged[0].commit' <<<"$answer")
[ "$(git -C "$ORIGIN" rev-parse "refs/heads/$INTEGRATION")" = "$FIRST" ] || fail "the integration branch is not on the first merge"
[ "$(git -C "$ORIGIN" rev-list --parents -n 1 "$FIRST")" = "$FIRST $BASE $TIP1" ] || fail "the first merge is not base + ticket 1"
git -C "$ORIGIN" merge-base --is-ancestor "$TIP2" "$FIRST" && fail "the second ticket was merged despite its outdated verdict"

shown=$("$STATE" show "$CONVOY" --repo "$REPO") || fail "show after the first pass failed: $shown"
jq -e --arg t1 "$T1" --arg t2 "$T2" --arg first "$FIRST" --arg judged "$TIP2" --arg newer "$NEWER" '
  .unruled == false
  and (.tickets[] | select(.id == $t1)
       | .merge.outcome == "merged" and .merge.commit == $first and .evidence.merged_tests.commit == $first)
  and (.tickets[] | select(.id == $t2)
       | .merge == null and .counters.resumes == 1
         and ([.verdicts.code_review, .verdicts.evaluation]
              | all(.valid == false and .commit == $judged and .invalidated.tip == $newer)))
' <<<"$shown" >/dev/null || fail "merge of T1, or invalid verdicts and resume of T2, not read back from the real tracker: $shown"

# --- the verdicts replayed on the new tip: the second merge follows the first --
judge "$T2" "$NEWER"
answer=$("$TOOL" merge "$CONVOY" --repo "$REPO" --profile "$PROFILE") || fail "the second pass was refused: $answer"
jq -e --arg t2 "$T2" '.ok and ([.merged[].id] == [$t2])' <<<"$answer" >/dev/null || fail "unexpected answer of the second pass: $answer"
SECOND=$(jq -r '.merged[0].commit' <<<"$answer")
[ "$(git -C "$ORIGIN" rev-list --parents -n 1 "$SECOND")" = "$SECOND $FIRST $NEWER" ] \
  || fail "the second merge is not made on the result of the first"
[ "$(git -C "$ORIGIN" rev-parse "refs/heads/$INTEGRATION")" = "$SECOND" ] || fail "the integration branch is not on the second merge"

# --- a test record on each merged result, sealed by the capture tool ----------
for pair in "$T1=$FIRST" "$T2=$SECOND"; do
  piece="$EVIDENCE_STORE_DIR/$SPEC/${pair%%=*}/merged_tests.json"
  jq -e --arg commit "${pair#*=}" '.kind == "command" and .exit_code == 0 and .commit == $commit' "$piece" >/dev/null \
    || fail "no green test record at the commit of the merged result for ${pair%%=*}: $(cat "$piece" 2>&1)"
  "$ROOT/bin/evidence-capture" verify "$CONVOY" "${pair%%=*}" --piece merged_tests >/dev/null \
    || fail "the test record of ${pair%%=*} does not verify"
done

# --- the protected branch received nothing; nothing reached the Factory -------
[ "$(git -C "$ORIGIN" rev-parse refs/heads/main)" = "$BASE" ] || fail "the protected branch received a commit"
[ "$(git -C "$REPO" worktree list | wc -l)" = 1 ] || fail "a merge work tree was left behind"
[ "$FACTORY_BEFORE" = "$(factory_git_state)" ] || fail "the trial changed the Factory's Git state"

echo "PASS: on the real tracker, two finished tickets of the fixture are merged one after the other with a test record on each merged result, and a commit added after a verdict invalidates it, counts one resume and refuses the merge until the verdicts are replayed"
