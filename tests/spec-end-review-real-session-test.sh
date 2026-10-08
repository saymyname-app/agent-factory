#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime, an isolated Dolt server, its own supervisor and, when asked, one real model session
#
# Adoption trial of the end code review on a diff of the size of a real convoy
# (T25, af-ji2ruy; Spec af-wf4w5r §6 « Fin de Spec »): does one real session of
# the reviewer role hold on it — how long it takes, and whether its output
# covers the two axes and every file of the diff. An incomplete output counts
# as a review that did not pass.
#
# Only with SPEC_END_REVIEW_TRIAL_SESSION=1: it costs one model session (two
# when the first gives no result), which is why bin/local-only-tests does not
# run it by default. Without it the trial says so and passes.
#
# What is real: the reviewer agent of the Factory, with its prompt, its
# `code-review` skill and its read-only provider profile, launched through
# this checkout's sandbox wrapper; the formula mol-end-review; the dispatch
# door that routes the review; bin/spec-end-review (settle, brief, record) and
# bin/convoy-state on the real tracker of a disposable city that shares
# nothing with the live Factory. What is written by the trial: the convoy as
# the flow leaves it at the end of a Spec (one ticket closed by its gate, the
# three mechanical verdicts recorded on the tip) and a short synthetic Spec.
# The diff under review is a range of this repository's own history
# (SPEC_END_REVIEW_TRIAL_BASE..SPEC_END_REVIEW_TRIAL_TIP, by default the last
# ten commits of origin/main): the size is real, the Spec is not the one that
# code was written for, so the findings of the Spec axis say nothing here.
#
# The trial prints its record (« relevé d'essai ») on stdout.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
. "$ROOT/tests/lib/isolated-city.sh"
TOOL="$ROOT/bin/spec-end-review"
STATE="$ROOT/bin/convoy-state"
PORT="${SPEC_END_REVIEW_TRIAL_PORT:-18452}"
TIMEOUT="${SPEC_END_REVIEW_TRIAL_TIMEOUT:-7200}"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

if [ "${SPEC_END_REVIEW_TRIAL_SESSION:-0}" != 1 ]; then
  echo "relevé d'essai — revue de code de fin, session réelle : non lancée (SPEC_END_REVIEW_TRIAL_SESSION=1 lance une session réelle du rôle relecteur)"
  echo "PASS"
  exit 0
fi

for required in gc bd jq git dolt tmux python3 sha256sum; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

REVIEWER_AGENT=$(jq -r '.roles.reviewer.agent' "$ROOT/config/delivery-roles.json")
REVIEWER_PROVIDER=$(jq -r --arg a "$REVIEWER_AGENT" '.targets[$a].chain[0]' "$ROOT/config/provider-policy.json")
REVIEWER_MODEL=$(jq -r --arg p "$REVIEWER_PROVIDER" '.providers[$p].recommended[0]' "$ROOT/config/model-catalog.json")
TIP=$(git -C "$ROOT" rev-parse --verify --quiet "${SPEC_END_REVIEW_TRIAL_TIP:-origin/main}^{commit}") \
  || fail "the tip of the diff under review is not a commit of this repository"
BASE=$(git -C "$ROOT" rev-parse --verify --quiet "${SPEC_END_REVIEW_TRIAL_BASE:-$TIP~10}^{commit}") \
  || fail "the base of the diff under review is not a commit of this repository"

# The directory bin/role-adoption-trial builds its own city in: the one
# folder Claude Code already trusts for trial cities of the delivery roles,
# and not under /tmp, which the read-only sandbox of the role mounts empty
# (tests/graph-review-isolated-city-test.sh). Never erased if it exists.
TRIAL="${SPEC_END_REVIEW_TRIAL_DIR:-$HOME/.local/share/af-role-trial}"
[ ! -e "$TRIAL" ] || fail "$TRIAL exists: another trial is using it, or left it behind -- nothing is touched"
mkdir -p "$TRIAL"
CITY="$TRIAL/c"
PRODUCT="$TRIAL/repo"
SYSTEMD_USER_DIR="$HOME/.local/share/systemd/user"
cleanup() {
  status=$?
  trap - EXIT
  isolated_city_stop "$TRIAL" "$CITY" >/dev/null 2>&1 || true
  tmux -L "$(basename "$TRIAL")" kill-server >/dev/null 2>&1 || true
  pkill -f -- "$TRIAL/" >/dev/null 2>&1 || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    pgrep -f -- "$TRIAL/" >/dev/null 2>&1 || break
    sleep 0.3
  done
  pkill -9 -f -- "$TRIAL/" >/dev/null 2>&1 || true
  for unit in "$SYSTEMD_USER_DIR"/gascity-supervisor-*.service; do
    [ -f "$unit" ] && grep -qF -- "$TRIAL/" "$unit" || continue
    echo "FAIL: the trial left the systemd user unit $(basename "$unit"); removing it" >&2
    systemctl --user disable --now "$(basename "$unit")" >/dev/null 2>&1 || true
    rm -f -- "$unit"
    systemctl --user daemon-reload >/dev/null 2>&1 || true
    [ "$status" != 0 ] || status=1
  done
  if [ "${KEEP_TEST_CITY:-0}" = 1 ]; then
    echo "trial preserved at $TRIAL" >&2
  else
    rm -rf -- "$TRIAL"
  fi
  exit "$status"
}
trap cleanup EXIT

# Nothing of the live Factory may reach this city.
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$|FACTORY_ROOT$|CONVOY_|DISPATCH_DOOR_|ESCALATION_DOOR_|SPEC_END_(REVIEW_DISPATCH|LOCK|WORK)|DELIVERY_ROLE_)' || true)
export GC_HOME="$TRIAL/h" XDG_RUNTIME_DIR="$TRIAL/r" GC_DISABLE_USAGE_METRICS=1
unset DBUS_SESSION_BUS_ADDRESS
export PATH="/usr/local/bin:$HOME/.local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
mkdir -p "$GC_HOME"
mkdir -m 700 "$XDG_RUNTIME_DIR"
printf '[supervisor]\nport = %s\n' "$PORT" > "$GC_HOME/supervisor.toml"

# --- the product: a range of this repository's history, in a repository of its own ---
SPEC_BRANCH_BASE=main
git init -q -b "$SPEC_BRANCH_BASE" "$PRODUCT"
git -C "$PRODUCT" fetch -q "$ROOT" "$TIP"
git -C "$PRODUCT" merge-base --is-ancestor "$BASE" "$TIP" || fail "the base $BASE is not an ancestor of the tip $TIP"
git -C "$PRODUCT" update-ref "refs/heads/$SPEC_BRANCH_BASE" "$BASE"
git -C "$PRODUCT" reset -q --hard "$BASE"

gc init --template minimal --default-provider claude --skip-provider-readiness \
  --no-start --yes --name "$(basename "$TRIAL")" "$CITY" >/dev/null 2>&1 \
  || fail "gc init of the isolated city failed"
sed -i '/^\[\[named_session\]\]$/,+2d' "$CITY/pack.toml"
rm -rf "$CITY/agents/mayor"

# The Factory root the commands read is the city: the reviewer role, its
# agent with its real prompt and skill, its read-only provider profile, the
# formula, and one project that allows it and holds the product.
mkdir -p "$CITY/agents" "$CITY/formulas" "$CITY/config/projects"
ln -s "$ROOT/bin" "$CITY/bin"
cp -r "$ROOT/agents/$REVIEWER_AGENT" "$CITY/agents/$REVIEWER_AGENT"
cp "$ROOT/formulas/mol-end-review.formula.toml" "$CITY/formulas/"
cp "$ROOT/config/delivery-roles.json" "$ROOT/config/model-catalog.json" "$CITY/config/"
[ ! -f "$ROOT/config/operator.json" ] || cp "$ROOT/config/operator.json" "$CITY/config/"
cat > "$CITY/config/projects/agent-factory.toml" <<TOML
rig_dir = "../repo"
repo = "example/trial"
protected_branch = "main"
required_ci = "CI"
sling_target = "$REVIEWER_AGENT"
formulas = "mol-end-review"
TOML
jq -n --argjson timeout "$TIMEOUT" '{contract: "agent-factory-delivery-flow/v1", max_sessions: 2,
  end_review: {formula: "mol-end-review", role: "reviewer", rig: "agent-factory", timeout_seconds: $timeout}}' \
  > "$CITY/config/delivery-flow.json"
python3 - "$ROOT" "$CITY" "$REVIEWER_PROVIDER" > "$CITY/city.toml" <<'PY'
import json, sys, tomllib
root, city, provider = sys.argv[1:]
profile = tomllib.load(open(f"{root}/city.toml", "rb"))["providers"][provider]
profile["command"] = f"{root}/bin/delivery-role-sandbox"
profile.setdefault("env", {})["FACTORY_ROOT"] = city
print(f'[workspace]\nprovider = "{provider}"\n\n[providers.{provider}]')
tables = {k: v for k, v in profile.items() if isinstance(v, dict)}
for key, value in profile.items():
    if key not in tables:
        print(f"{key} = {json.dumps(value)}")
for name, table in tables.items():
    print(f"\n[providers.{provider}.{name}]")
    for key, value in table.items():
        print(f"{key} = {json.dumps(value)}")
PY
cat > "$TRIAL/provider-failover" <<SH
#!/bin/sh
printf '%s\n' '{"total_exhaustion": {"active": false}, "targets": {"$REVIEWER_AGENT": {"effective": "$REVIEWER_PROVIDER"}}}'
SH
# The adoption record of the role is the one of this checkout: the trial
# city holds a copy of the same distribution.
cat > "$TRIAL/role-adoption-trial" <<SH
#!/bin/sh
FACTORY_ROOT="$ROOT" exec "$ROOT/bin/role-adoption-trial" "\$@"
SH
printf '#!/bin/sh\necho 0\n' > "$TRIAL/proposal-door"
chmod +x "$TRIAL/provider-failover" "$TRIAL/role-adoption-trial" "$TRIAL/proposal-door"

# No lock directory of the trial's own: the locks of bin/convoy-state go
# where they go in the Factory, under XDG_RUNTIME_DIR -- here the trial's --
# which is what the sandbox of a read-only role leaves writable. A lock
# directory elsewhere under the trial is read-only in the reviewer session,
# and its record is refused (seen on the first run of this trial).
export FACTORY_ROOT="$CITY"
export DISPATCH_DOOR_PROVIDER_FAILOVER_BIN="$TRIAL/provider-failover" DISPATCH_DOOR_ROLE_TRIAL_BIN="$TRIAL/role-adoption-trial"
export DELIVERY_ROLE_PROVIDER_FAILOVER_BIN="$TRIAL/provider-failover"
export ESCALATION_DOOR_LOCK_FILE="$TRIAL/escalation-door.lock" PROPOSAL_DOOR_BIN="$TRIAL/proposal-door"

cd "$CITY"

state() {
  local out
  out=$("$STATE" "$@") || fail "convoy-state $* did not pass: $out"
}

# --- the convoy, as the flow leaves it at the end of a Spec ----------------------
SPEC_TEXT=$(cat <<'SPEC'
Spec synthétique de l'essai : une tranche de l'historique de l'usine, relue d'un bloc.

## User Stories

1. As an exploitant, I want chaque commande de l'usine répondre par un seul objet JSON sur sa sortie standard, so that un autre outil puisse la lire.
2. As an exploitant, I want chaque refus d'une commande dire sa raison sur une ligne, so that je sache quoi corriger.

Aucune story ne décrit une interface prototypée : il n'y a pas de Validated Prototype.
SPEC
)
SPEC=$(gc bd create --title "Spec de l'essai" --type task --description "$SPEC_TEXT" --silent 2>/dev/null)
CONVOY=$(gc bd create --title "convoi d'essai" --type convoy --silent 2>/dev/null)
TICKET_TEXT=$(printf '%s\n\n%s\n\n%s\n' \
  "## What to build" \
  "La tranche de l'historique de l'usine que porte la branche d'intégration, sans changer le comportement que la Spec décrit." \
  $'## Target rigs\n\nagent-factory')
T1=$(gc bd create --title "ticket d'essai" --type task --description "$TICKET_TEXT" --silent 2>/dev/null)
gc bd update "$T1" --set-metadata gc.ticket_kind=prefactoring >/dev/null
gc bd update "$CONVOY" --set-metadata "gc.spec_id=$SPEC" >/dev/null
gc bd dep add "$CONVOY" "$T1" --type tracks >/dev/null
BRANCH="integration/$SPEC"
git -C "$PRODUCT" update-ref "refs/heads/$BRANCH" "$TIP"
state mark "$CONVOY"
state set-integration "$CONVOY" --branch "$BRANCH" --protected "$SPEC_BRANCH_BASE" --base "$BASE"
state close-ticket "$CONVOY" "$T1" --commit "$TIP" --file "$ROOT/tests/fixtures/convoy-state/ticket-end-report.json"
jq -n '{version: "spec-end/v4", conditions: [
  {number: 1, name: "registry", verdict: "pass", detail: "1 ticket fermé par la porte (relevé d'"'"'essai)"},
  {number: 2, name: "tests", verdict: "pass", detail: "réunie (relevé d'"'"'essai)"},
  {number: 3, name: "fidelity", verdict: "pass", detail: "sans objet (relevé d'"'"'essai)"}]}' > "$TRIAL/spec-end.json"
state record-spec-end "$CONVOY" --commit "$TIP" --protected "$BASE" --file "$TRIAL/spec-end.json"

gc supervisor run >"$TRIAL/supervisor.out" 2>&1 </dev/null &
sleep 3
gc --city "$CITY" start >"$TRIAL/start.out" 2>&1 || true

review() { "$TOOL" show "$CONVOY" --repo "$PRODUCT"; }
print_round() { # <round json>
  jq -r '"              sortie \(.outcome) : \(.coverage.files)/\(.extent.files) fichier(s) relus, axes \(.coverage.axes | join(", ")), "
           + "\((.coverage.missing_count // (.coverage.missing | length))) fichier(s) non relu(s) ; durée \(.duration_seconds) s ; "
           + "\(.findings | length) constat(s) dont \([.findings[] | select(.blocking)] | length) bloquant(s) ; session \(.recorded_by)"' <<<"$1"
}

echo "relevé d'essai — revue de code de fin, session réelle du rôle relecteur ($REVIEWER_AGENT, $REVIEWER_PROVIDER, $REVIEWER_MODEL), cité isolée, $(date -u +%Y-%m-%d)"
settled=$("$TOOL" settle "$CONVOY" --repo "$PRODUCT") || fail "the end review was not launched: $settled"
[ "$(jq -r '.action' <<<"$settled")" = launched ] || fail "the end review was not launched: $settled"
jq -r '"   diff relu : \(.base[:12])..\(.commit[:12]) de l'"'"'historique de l'"'"'usine — \(.extent.files) fichier(s), \(.extent.commits) commit(s), +\(.extent.insertions) −\(.extent.deletions)",
       "   \(now | strftime("%H:%M:%S")) lancement 1 : bead \(.bead), délai \('"$TIMEOUT"') s"' <<<"$settled"

# One pass a minute, as the order does: a launch without result is launched
# once more, then the review is stopped.
seen=0
deadline=$(( $(date +%s) + 2 * TIMEOUT + 600 ))
while :; do
  shown=$(review) || fail "the end review cannot be read: $shown"
  rounds=$(jq '.rounds | length' <<<"$shown")
  while [ "$seen" -lt "$rounds" ]; do
    echo "   $(date -u +%H:%M:%S) passe $((seen + 1)) enregistrée"
    print_round "$(jq -c ".rounds[$seen]" <<<"$shown")"
    seen=$((seen + 1))
  done
  outcome=$(jq -r '.state.outcome // ""' <<<"$shown")
  if [ "$outcome" = favorable ] || [ "$outcome" = unfavorable ]; then
    jq -r '.rounds[-1].findings[] | "              \(.id) [\(.axis)\(if .blocking then ", bloquant" else "" end)] \(.summary)"' <<<"$shown"
    independence=$(jq -r '.independence // "relecteur d'"'"'un autre modèle que les auteurs"' <<<"$shown")
    echo "   indépendance : $independence"
    echo "   la revue a tenu : sortie complète, issue $outcome ; tour(s) de fin compté(s) : $("$STATE" show "$CONVOY" | jq -r '.convoy.counters.end_rounds')"
    break
  fi
  if [ "$(jq -r '.stop.reason // ""' <<<"$shown")" != "" ]; then
    echo "   $(date -u +%H:%M:%S) revue arrêtée : $(jq -r '.stop.reason + " — " + .stop.detail' <<<"$shown")"
    echo "   la revue n'a pas tenu : aucune sortie complète en deux lancements ; elle compte non passée"
    break
  fi
  [ "$(date +%s)" -lt "$deadline" ] || fail "the end review was neither recorded nor stopped within $((2 * TIMEOUT + 600))s: $shown"
  sleep 60
  settled=$("$TOOL" settle "$CONVOY" --repo "$PRODUCT") || true
  case "$(jq -r '.action // ""' <<<"$settled")" in
    relaunched) echo "   $(date -u +%H:%M:%S) lancement 2 (le premier n'a rendu aucun résultat complet) : bead $(jq -r '.bead' <<<"$settled")" ;;
    stopped) echo "   $(date -u +%H:%M:%S) arrêt : $(jq -r '.stop' <<<"$settled")" ;;
    pending|reviewed|deferred) ;;
    *) echo "   $(date -u +%H:%M:%S) settle : $(jq -c '.' <<<"$settled" 2>/dev/null || printf '%s' "$settled")" ;;
  esac
done
# An incomplete output is never a passed review.
jq -e '[.rounds[] | select(.outcome == "incomplete")] | all(.coverage.files < .extent.files or (.coverage.axes | length) < 2)' \
  <<<"$shown" >/dev/null || fail "a round recorded as incomplete covers the whole diff: $shown"
echo "PASS"
