#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime and an isolated Dolt server
#
# The two tools whose bare `bd close` met a bead another actor holds
# (af-vhvmsi), on the real tracker and as their real caller runs them, in a
# disposable city that shares nothing with the live Factory.
#
# Beads 1.3 refuses, exit 1, a `bd close` from any actor but the assignee.
# The verdict per command is in the first comment of af-vhvmsi; two broke:
#
#   1. bin/mail-reply-reap, run by gc as an order. A mail bead is assigned to
#      its recipient and the order runs as `order:<name>`: the close was
#      refused. And Gas City 1.5 gives an order `BD_BIN=`, set and empty: the
#      tool ran '' instead of bd, so its check answered exit 1, "nothing to
#      close", and the order never fired. The order is run here by gc itself,
#      so both are held, and so is whatever gc gives an order next.
#   2. bin/proposal-door reconvertir, run by the Mayor on the bug bead of a
#      maintenance proposal while the worker it was dispatched to holds it.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc bd jq git dolt python3; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

TRIAL=$(mktemp -d /tmp/af-vhvmsi-bare-close.XXXXXX)
TEST_CITY="$TRIAL/city"
CITY_NAME=$(basename "$TRIAL")
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
  # The mail of `proposal-door create` wakes the city's mayor: a tmux server
  # on a socket named after the city, whose command line names no trial path.
  tmux -L "$CITY_NAME" kill-server >/dev/null 2>&1 || true
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
# BD_BIN stays unset: gc runs it too, so a BD_BIN that calls gc starts gc
# again without end (it filled the host's memory on 2026-10-11).
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_|GH_BIN$)' || true)
export HOME="$TRIAL/home" TMUX_TMPDIR="$TRIAL/tmux" PROPOSAL_DOOR_LOCK_FILE="$TRIAL/proposal-door.lock"
# The tools name their city to gc from FACTORY_ROOT (af-2o6oyl); left unset,
# they name the repository they are run from -- the live Factory (af-xcfup7).
export FACTORY_ROOT="$TEST_CITY"
mkdir -p "$HOME" "$TMUX_TMPDIR"
dolt config --global --add user.name "bare-close trial" >/dev/null
dolt config --global --add user.email "trial@example.invalid" >/dev/null
git config --global user.name "bare-close-trial"
git config --global user.email "trial@example.invalid"

gc init --template minimal --default-provider codex --skip-provider-readiness \
  --no-start --yes --name "$CITY_NAME" "$TEST_CITY" >/dev/null 2>&1 \
  || fail "gc init of the isolated city failed"
cd "$TEST_CITY"

field() {  # id jq-filter
  gc bd show "$1" --json 2>/dev/null | jq -r ".[0] | $2"
}
expect() {  # id jq-filter wanted what
  local got
  got=$(field "$1" "$2")
  [ "$got" = "$3" ] || fail "$4: $1 has $2 = '$got', wanted '$3'"
}
mail_id() {  # subject -> id of the open mail bead that carries it
  bd list --include-infra --type message --status open --json --limit 0 2>/dev/null \
    | jq -r --arg s "$1" '[.[] | select(.title == $s)][0].id // ""'
}

# --- 1. bin/mail-reply-reap, run by gc as an order ---------------------------
gc mail send mayor -s "resolved reply" -m "ACTION: checked the bead
STATE: RESOLVED
EVIDENCE: none
NEXT: none" >/dev/null 2>&1 || fail "could not send the resolved mail"
gc mail send mayor -s "pending reply" -m "ACTION: reconciled a pull request
STATE: SHIPPED
EVIDENCE: none
NEXT: Mayor advances the work that waited on it." >/dev/null 2>&1 || fail "could not send the pending mail"
resolved=$(mail_id "resolved reply")
pending=$(mail_id "pending reply")
[ -n "$resolved" ] && [ -n "$pending" ] || fail "the two mail beads were not found in the city"
expect "$resolved" '.assignee' mayor "a mail bead is assigned to its recipient"

# The Factory's order (orders/mail-reply-reap.toml), on this work tree's tool
# and this city.
mkdir -p orders
cat >orders/mail-reply-reap.toml <<EOF
[order]
description = "mail-reply-reap, as the Factory runs it"
trigger = "condition"
interval = "5m"
check = "$ROOT/bin/mail-reply-reap --repo-root $TEST_CITY sweep --dry-run"
exec = "$ROOT/bin/mail-reply-reap --repo-root $TEST_CITY sweep"
timeout = "60s"
EOF
due=$(gc order check 2>&1 || true)
grep -Eq '^mail-reply-reap +condition +yes ' <<<"$due" \
  || fail "the order's check does not see the resolved mail: $(grep -E '^mail-reply-reap ' <<<"$due" || echo "$due")"
out=$(gc order run mail-reply-reap 2>&1) || fail "the order's exec failed: $out"
expect "$resolved" '.status' closed "mail-reply-reap, run as an order, on a mail held by its recipient"
expect "$pending" '.status' open "mail-reply-reap on a mail that still names a next step"
grep -qF "mail-reply-reap" <<<"$(field "$resolved" '[.close_reason, .notes] | map(. // "") | join(" ")')" \
  || fail "mail-reply-reap: the closed mail does not say what closed it"

# --- 2. bin/proposal-door reconvertir on a bug bead its worker holds ---------
langue=$("$ROOT/bin/operator-config" language) || fail "could not read the Operator Language"
payload=$(jq -nc --arg langue "$langue" '{
  quoi: "Corriger le filtre des pages fermées", pourquoi: "La liste montre encore des pages fermées",
  langue: $langue, classe: "maintenance",
  que_faire: [{option: "Corriger le filtre", consequence: "La liste ne montre plus les pages fermées."}]}')
out=$("$ROOT/bin/proposal-door" create "$payload" 2>&1) || fail "proposal-door create failed: $out"
proposal=$(sed -n 's/^PROPOSITION CRÉÉE: \([^ ]*\) .*/\1/p' <<<"$out")
[ -n "$proposal" ] || fail "proposal-door create did not name the proposal: $out"
bug=$(field "$proposal" '.metadata["gc.proposal_bug"] // ""')
[ -n "$bug" ] || fail "the maintenance proposal $proposal names no bug bead"
gc bd --actor factory-worker-trial update "$bug" --claim >/dev/null 2>&1 || fail "the worker could not claim the bug bead"
options=$(jq -nc '[
  {option: "Filtrer les pages fermées", consequence: "Tu ne verras plus les pages fermées dans la liste.",
   recommande: true, raison: "La liste redevient lisible."},
  {option: "Garder la liste telle quelle", consequence: "Rien ne change."}]')
out=$(BEADS_ACTOR=mayor "$ROOT/bin/proposal-door" reconvertir "$proposal" "Touche ce que l'opérateur voit" "$options" mayor 2>&1) \
  || fail "proposal-door reconvertir refused a bug bead held by its worker: $out"
expect "$bug" '.status' closed "proposal-door reconvertir"
expect "$proposal" '.metadata["gc.proposal_classe"]' decision "proposal-door reconvertir"
grep -qF "Reconvertie" <<<"$(field "$bug" '[.close_reason, .notes] | map(. // "") | join(" ")')" \
  || fail "proposal-door reconvertir: the closed bug bead does not say why"

echo "PASS: bare-close-held-bead-real-tracker"
