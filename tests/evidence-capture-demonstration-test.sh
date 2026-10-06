#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime, an isolated Dolt server and a real Chromium
#
# Demonstration line of T09 (af-pvcg6t), on the real tracker and the real
# browser, in a disposable city that shares nothing with the live Factory:
# bin/evidence-capture, called on a command then on the page of the launched
# Delivery Fixture City, files two pieces under the named Spec and ticket;
# their fingerprints read back from the tracker; a file written by hand is
# refused. tests/evidence-capture-test.py proves the same contract on a fake
# tracker and a fake browser.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
TOOL="$ROOT/bin/evidence-capture"
STATE="$ROOT/bin/convoy-state"
LAUNCH="$ROOT/bin/project-launch"
DESCRIPTOR="$ROOT/tests/fixtures/delivery-fixture-city/descriptor.json"

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

TRIAL=$(mktemp -d /tmp/af-pvcg6t-evidence-capture.XXXXXX)
TEST_CITY="$TRIAL/city"
LAUNCH_STATE="$TRIAL/launch.json"
cleanup() {
  status=$?
  trap - EXIT
  [ -f "$LAUNCH_STATE" ] && "$LAUNCH" stop --state-file "$LAUNCH_STATE" >/dev/null 2>&1
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
  git -C "$ROOT" rev-list --all --count
}
FACTORY_BEFORE=$(factory_git_state)

# Nothing of the live Factory may reach this city: no GC_* variable (hosted
# Dolt, city path, session identity, GC_BIN) and no shared HOME.
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$)' || true)
export HOME="$TRIAL/home" TMUX_TMPDIR="$TRIAL/tmux" CONVOY_STATE_LOCK_DIR="$TRIAL/locks"
export EVIDENCE_STORE_DIR="$TRIAL/store" EVIDENCE_CAPTURE_BROWSER="$BROWSER"
mkdir -p "$HOME" "$TMUX_TMPDIR"
dolt config --global --add user.name "evidence-capture trial" >/dev/null
dolt config --global --add user.email "trial@example.invalid" >/dev/null
git config --global user.name "evidence-capture trial"
git config --global user.email "trial@example.invalid"

gc init --template minimal --default-provider codex --skip-provider-readiness \
  --no-start --yes --name af-pvcg6t-evidence-capture "$TEST_CITY" >/dev/null 2>&1 \
  || fail "gc init of the isolated city failed"
cd "$TEST_CITY"

SPEC=$(gc bd create --title "Spec d'essai" --type task --silent 2>/dev/null)
CONVOY=$(gc bd create --title "convoi d'essai" --type convoy --silent 2>/dev/null)
T1=$(gc bd create --title "ticket d'essai" --type task --silent 2>/dev/null)
gc bd update "$CONVOY" --set-metadata "gc.spec_id=$SPEC" >/dev/null
gc bd update "$T1" --set-metadata gc.ticket_kind=prefactoring >/dev/null
gc bd dep add "$CONVOY" "$T1" --type tracks >/dev/null
"$STATE" mark "$CONVOY" >/dev/null || fail "the trial convoy could not be marked"

"$LAUNCH" start "$DESCRIPTOR" --dataset content --state-file "$LAUNCH_STATE" >/dev/null \
  || fail "the Delivery Fixture City did not launch"
ADDRESS=$(jq -r .address "$LAUNCH_STATE")
COMMIT=$(jq -r .commit "$LAUNCH_STATE")

# --- a command, then the page of the launched fixture -------------------------
"$TOOL" command "$CONVOY" "$T1" --piece demo.sonde --launch-state "$LAUNCH_STATE" \
  -- python3 -c "import urllib.request; print(urllib.request.urlopen('$ADDRESS/health').read().decode())" >/dev/null \
  || fail "the command capture was refused"
"$TOOL" screenshot "$CONVOY" "$T1" --piece demo.page --launch-state "$LAUNCH_STATE" --path / >"$TRIAL/screenshot.out" \
  || fail "the screenshot capture was refused: $(cat "$TRIAL/screenshot.out")"

PIECES="$EVIDENCE_STORE_DIR/$SPEC/$T1"
[ "$(ls -1 "$PIECES" | sort | tr '\n' ' ')" = "demo.page.json demo.page.png demo.sonde.json " ] \
  || fail "the two pieces are not filed under the Spec and the ticket: $(ls -1 "$PIECES" 2>&1)"
jq -e --arg commit "$COMMIT" --arg address "$ADDRESS" '
  .kind == "command" and .exit_code == 0 and (.output | fromjson) == {status: "ok"}
  and .commit == $commit and .address == $address and (.command | length) == 3 and (.at | length) == 20
' "$PIECES/demo.sonde.json" >/dev/null || fail "command piece is not what was run: $(cat "$PIECES/demo.sonde.json")"
jq -e --arg commit "$COMMIT" --arg address "$ADDRESS/" '
  .kind == "screenshot" and .commit == $commit and .address == $address and .image == "demo.page.png" and (.at | length) == 20
' "$PIECES/demo.page.json" >/dev/null || fail "screenshot piece is not the launched page: $(cat "$PIECES/demo.page.json")"
[ "$(head -c 8 "$PIECES/demo.page.png" | od -An -tx1 | tr -d ' \n')" = "89504e470d0a1a0a" ] \
  || fail "the screenshot is not a PNG image"
[ "$(stat -c %s "$PIECES/demo.page.png")" -gt 1000 ] || fail "the screenshot is an empty image"

# --- their fingerprints read back from the real tracker -----------------------
shown=$("$STATE" show "$CONVOY") || fail "show of the trial convoy failed: $shown"
for piece in demo.sonde demo.page; do
  digest="sha256:$(sha256sum "$PIECES/$piece.json" | cut -d' ' -f1)"
  jq -e --arg t1 "$T1" --arg piece "$piece" --arg digest "$digest" --arg commit "$COMMIT" '
    .tickets[] | select(.id == $t1) | .evidence[$piece] | .digest == $digest and .commit == $commit
  ' <<<"$shown" >/dev/null || fail "fingerprint of $piece not read back from the tracker: $shown"
done
"$TOOL" verify "$CONVOY" "$T1" >/dev/null || fail "the two captured pieces do not verify"

# --- a file written by hand is refused ----------------------------------------
jq '.piece = "demo.redigee" | .output = "tout est vert\n"' "$PIECES/demo.sonde.json" > "$PIECES/demo.redigee.json"
"$STATE" add-evidence "$CONVOY" "$T1" --piece demo.redigee \
  --digest "sha256:$(sha256sum "$PIECES/demo.redigee.json" | cut -d' ' -f1)" --commit "$COMMIT" >/dev/null
set +e
answer=$("$TOOL" verify "$CONVOY" "$T1" --piece demo.redigee); rc=$?
set -e
[ "$rc" = 1 ] || fail "a hand-written piece verified (exit $rc): $answer"
jq -e '.error | contains("pas été produite par l'"'"'outil de capture")' <<<"$answer" >/dev/null \
  || fail "hand-written piece not refused for what it is: $answer"
"$TOOL" verify "$CONVOY" "$T1" --piece demo.page >/dev/null || fail "a captured piece stopped verifying"

# --- nothing reached a Git history, and the Spec is purged alone --------------
[ "$FACTORY_BEFORE" = "$(factory_git_state)" ] || fail "a capture changed the Factory's Git state"
"$TOOL" purge --spec "$SPEC" >/dev/null || fail "purge of the trial Spec failed"
[ ! -e "$EVIDENCE_STORE_DIR/$SPEC" ] || fail "the pieces of the purged Spec are still in the store"

echo "PASS: a command and the page of the launched fixture are captured under their Spec and ticket, fingerprinted in the real tracker; a hand-written piece is refused"
