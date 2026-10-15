#!/usr/bin/env bash
# ci: local-only — requires the installed gc/bd runtime, an isolated Dolt server and its own supervisor
#
# Adoption trial of bin/graph-review (T08, af-n575g4; Spec af-wf4w5r §2,
# « Relecteur de graphe », user stories 7 and 8) in a disposable city that
# shares nothing with the live Factory: its own GC_HOME, runtime directory,
# supervisor port and tracker. tests/graph-review-test.py proves the command
# on a fake tracker; this trial proves what that fake assumes.
#
# Part 1, always, spends nothing — the real tracker:
#   the review state (JSON values under gc.graph_review.*) is written to and
#   read back from the real bd; the publication door refuses a draft without
#   a review, with a first pass that refuses, with a remaining refusal
#   Benjamin has not ruled on, and after the draft changed; it publishes once
#   he has ruled. A third pass is refused with the list of what remains.
#
# Part 2, only with GRAPH_REVIEW_TRIAL_SESSION=1 — one real reviewer session:
#   `graph-review review` routes the review through the real bin/dispatch-door
#   (`gc sling ... --on mol-graph-review`) to the reviewer role's agent, on
#   its read-only provider profile and with its real prompt; the session
#   claims the routed step, reads the draft of the fixture in which one
#   ticket is not demonstrable alone, and records its answers itself. The
#   trial then reads the verdict of that ticket. It costs one model session,
#   which is why bin/local-only-tests does not run it by default.
#
# The trial prints its record (« relevé d'essai ») on stdout.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
. "$ROOT/tests/lib/isolated-city.sh"
REVIEW="$ROOT/bin/graph-review"
DOOR="$ROOT/bin/ticket-graph-publish"
FIXTURES="$ROOT/tests/fixtures"
PROJECTS="$FIXTURES/spec-approve/projects"
PORT="${GRAPH_REVIEW_TRIAL_PORT:-18397}"
REVIEWER_AGENT=$(jq -r '.roles.reviewer.agent' "$ROOT/config/delivery-roles.json")
REVIEWER_PROVIDER=$(jq -r --arg a "$REVIEWER_AGENT" '.targets[$a].chain[0]' "$ROOT/config/provider-policy.json")

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for required in gc bd jq git dolt tmux python3 sha256sum; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

# One stable directory, the one bin/role-adoption-trial builds its own
# isolated city in: Claude Code asks a human to trust a folder it has never
# seen and exits otherwise, and that folder is the one already trusted for
# trial cities of the delivery roles. Not under /tmp either: the read-only
# sandbox of the reviewer role mounts an empty /tmp, and the session must
# still read the city it works for. Never erased if it exists: another
# trial may be using it.
# Without the real session nothing asks for that trusted folder, and
# bin/role-adoption-trial leaves it behind between its runs: part 1 alone
# takes a directory of its own, so that the nightly run does not depend on it.
if [ "${GRAPH_REVIEW_TRIAL_SESSION:-0}" = 1 ]; then
  TRIAL="${GRAPH_REVIEW_TRIAL_DIR:-$HOME/.local/share/af-role-trial}"
else
  TRIAL="${GRAPH_REVIEW_TRIAL_DIR:-$HOME/.local/share/af-graph-review-trial-$$}"
fi
[ ! -e "$TRIAL" ] || fail "$TRIAL exists: another trial is using it, or left it behind -- nothing is touched"
mkdir -p "$TRIAL"
CITY="$TRIAL/c"
SYSTEMD_USER_DIR="$HOME/.local/share/systemd/user"
cleanup() {
  status=$?
  trap - EXIT
  isolated_city_stop "$TRIAL" "$CITY" >/dev/null 2>&1 || true
  tmux -L "$(basename "$TRIAL")" kill-server >/dev/null 2>&1 || true
  # The supervisor, the city's managed Dolt server and the reviewer session
  # carry the trial directory on their command line; nothing else does.
  pkill -f -- "$TRIAL/" >/dev/null 2>&1 || true
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    pgrep -f -- "$TRIAL/" >/dev/null 2>&1 || break
    sleep 0.3
  done
  pkill -9 -f -- "$TRIAL/" >/dev/null 2>&1 || true
  # `gc start` installs a systemd user unit for the supervisor of whatever
  # GC_HOME it runs under when it can reach the user bus. The trial hides
  # the bus (below); should a unit of this trial exist anyway, it is
  # removed and the trial fails: it would restart at every login.
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

# Nothing of the live Factory may reach this city: no GC_* variable (hosted
# Dolt, city path, session identity, GC_BIN) and its own supervisor home.
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep -E '^(GC_|BEADS_|BD_BIN$|GH_BIN$|FACTORY_ROOT$|CONVOY_|DISPATCH_DOOR_|GRAPH_REVIEW_(BD|DISPATCH|PROVIDER|POLL)|TICKET_GRAPH_|DELIVERY_ROLE_)' || true)
export GC_HOME="$TRIAL/h" XDG_RUNTIME_DIR="$TRIAL/r" GC_DISABLE_USAGE_METRICS=1
# No user bus: `gc start` must not install or start a systemd unit for this
# trial's supervisor on the host (seen 2026-10-06: a unit enabled at login
# and restarting in a loop beside the live supervisor's).
unset DBUS_SESSION_BUS_ADDRESS
export PATH="/usr/local/bin:$HOME/.local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
mkdir -p "$GC_HOME" "$TRIAL/repo" "$TRIAL/locks"
# The repository of the project: the door opens the integration branch of the
# Spec there, at the tip of its protected branch (T18, af-gmz9s1).
git init -q -b main "$TRIAL/repo"
git -C "$TRIAL/repo" -c user.name="graph-review trial" -c user.email=trial@example.invalid \
  commit -q --allow-empty -m base
mkdir -m 700 "$XDG_RUNTIME_DIR"
printf '[supervisor]\nport = %s\n' "$PORT" > "$GC_HOME/supervisor.toml"

gc init --template minimal --default-provider claude --skip-provider-readiness \
  --no-start --yes --name "$(basename "$TRIAL")" "$CITY" >/dev/null 2>&1 \
  || fail "gc init of the isolated city failed"
# No Mayor in this city.
sed -i '/^\[\[named_session\]\]$/,+2d' "$CITY/pack.toml"
rm -rf "$CITY/agents/mayor"

# The Factory root the commands read is the city itself: the reviewer role,
# its agent with its real prompt and skills, its read-only provider profile
# (launched through this checkout's sandbox wrapper), the formula, and one
# project that allows it. Sessions of this city reach the commands of this
# checkout through FACTORY_ROOT, never the live root.
mkdir -p "$CITY/agents" "$CITY/formulas" "$CITY/config/projects"
ln -s "$ROOT/bin" "$CITY/bin"
cp -r "$ROOT/agents/$REVIEWER_AGENT" "$CITY/agents/$REVIEWER_AGENT"
cp "$ROOT/formulas/mol-graph-review.formula.toml" "$CITY/formulas/"
cp "$ROOT/config/delivery-roles.json" "$ROOT/config/model-catalog.json" "$CITY/config/"
cat > "$CITY/config/projects/agent-factory.toml" <<'TOML'
rig_dir = "."
repo = "example/trial"
protected_branch = "main"
required_ci = "CI"
sling_target = "delivery-reviewer"
formulas = "mol-graph-review"
TOML
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
chmod +x "$TRIAL/provider-failover" "$TRIAL/role-adoption-trial"

export FACTORY_ROOT="$CITY" CONVOY_STATE_LOCK_DIR="$TRIAL/locks"
export GRAPH_REVIEW_PROVIDER_FAILOVER_BIN="$TRIAL/provider-failover"
export DISPATCH_DOOR_PROVIDER_FAILOVER_BIN="$TRIAL/provider-failover" DISPATCH_DOOR_ROLE_TRIAL_BIN="$TRIAL/role-adoption-trial"
export TICKET_GRAPH_BD_WORKSPACE="$CITY" TICKET_GRAPH_PUBLISH_SKIP_MAYOR_NOTIFY=1
REVIEWER_MODEL=$(jq -r --arg p "$REVIEWER_PROVIDER" '.providers[$p].recommended[0]' "$ROOT/config/model-catalog.json")

cd "$CITY"

digest_of() {
  printf 'sha256:%s' "$(printf '%s' "$1" | sha256sum | cut -d' ' -f1)"
}

# The project's profile, with its launch recipe (T06).
mkdir -p "$TRIAL/descriptors"
cp "$ROOT/tests/fixtures/delivery-fixture-city/descriptor.json" "$TRIAL/descriptors/delivery-fixture-city.json"

SPEC_TEXT=$(cat <<'SPEC'
Spec synthétique de la Fixture City : une page d'accueil servie par le produit.

## User Stories

1. As a visiteur, I want la page d'accueil lister les éléments servis par l'API, so that je voie ce que le produit contient.
2. As a visiteur, I want voir le total des éléments sur la page d'accueil, so that je sache combien il y en a sans les compter.

Aucune story ne décrit une interface prototypée : il n'y a pas de Validated Prototype.
SPEC
)
SPEC=$(gc bd create --title "Spec de la fixture" --type task --description "$SPEC_TEXT" --silent 2>/dev/null)
gc bd update "$SPEC" --set-metadata "spec_state=APPROVED_SPEC" \
  --set-metadata "approved_digest=$(digest_of "$(gc bd show "$SPEC" --json | jq -r '.[0].description')")" \
  --set-metadata "gc.project_id=delivery-fixture-city" >/dev/null

approve() {
  # The digest is taken on what the tracker gives back, as the door does.
  gc bd update "$1" --set-metadata "spec_id=$SPEC" --set-metadata "approved_by=benjamin" \
    --set-metadata "approved_evidence=« j'approuve le graphe » (essai)" \
    --set-metadata "approved_digest=$(digest_of "$(gc bd show "$1" --json | jq -r '.[0].description')")" \
    --set-metadata "display_title=Fixture City : essai" --set-metadata "language=fr" >/dev/null
}
draft() {
  local id
  id=$(gc bd create --title "Brouillon d'essai" --type task --description "$1" --silent 2>/dev/null)
  approve "$id"
  printf '%s' "$id"
}
publish() {
  "$DOOR" bd-publish "$1" --project acme --repo-root "$TRIAL/repo" --config-dir "$PROJECTS" \
    --descriptors-dir "$TRIAL/descriptors"
}
tracker() {
  gc bd list --all --limit 0 --json | jq -S 'map({id, status, title, description, metadata}) | sort_by(.id)'
}
refused() {
  # refused <mention> -- <command...>: the command fails, says so, writes nothing.
  local mention="$1" before out rc
  shift 2
  before=$(tracker)
  set +e
  out=$("$@" 2>&1 >/dev/null); rc=$?
  set -e
  [ "$rc" != 0 ] || fail "not refused: $*"
  grep -qF -- "$mention" <<<"$out" || fail "the refusal of '$*' does not say '$mention': $out"
  [ "$before" = "$(tracker)" ] || fail "a refusal wrote to the real tracker: $*"
}
# What a reviewer session does, without the session: answer every question
# of the brief favorably, except those named in $2 ({target: {check: reason}}).
answer() {
  local brief
  "$REVIEW" request "$1" --author-model "modele-auteur-essai" >/dev/null || fail "review request refused for $1"
  brief=$("$REVIEW" brief "$1") || fail "no brief for $1"
  jq --argjson refuse "$2" '
    def answers($target; $checks): {checks: ($checks | with_entries(.key as $k | .value = (
      if $refuse[$target][$k] then {state: "unfavorable", reason: $refuse[$target][$k]}
      elif $k == "prototype_fold_present_and_first" then {state: "not_applicable", reason: "aucun ticket d'"'"'interface"}
      else {state: "favorable"} end)))};
    {digest, tickets: (.tickets | map({key: .id, value: answers(.id; .checks)}) | from_entries),
     graph: answers("graphe"; .graph_checks)}' <<<"$brief" > "$TRIAL/verdict.json"
  DELIVERY_ROLE_READ_ONLY=1 "$REVIEW" record "$1" --verdict-file "$TRIAL/verdict.json" \
    || fail "the real tracker refused the verdict of $1"
}
NOT_DEMONSTRABLE='{"T2": {"demonstrable_alone": "GET / n'"'"'affiche « Total : 3 » qu'"'"'une fois T3 livré"}}'
FIXTURE_DRAFT=$(cat "$FIXTURES/graph-review/not-demonstrable-draft.yaml")

echo "== relevé d'essai : bin/graph-review, cité isolée $(basename "$TRIAL")"
echo "   gc $(gc version 2>/dev/null | head -1), bd $(bd version 2>/dev/null | head -1)"

# --- part 1: the real tracker -------------------------------------------------
D1=$(draft "$FIXTURE_DRAFT")
refused "n'a pas de relecture de graphe" -- publish "$D1"

first=$(answer "$D1" "$NOT_DEMONSTRABLE")
jq -e --arg d "$(digest_of "$(gc bd show "$D1" --json | jq -r '.[0].description')")" '
  .pass == 1 and .digest == $d and .tickets.T2.verdict == "unfavorable" and .tickets.T1.verdict == "favorable"
  and .tickets.T1.checks.declared_scope_includes_wiring.state == "not_applicable"
  and .tickets.T3.checks.declared_scope_includes_wiring.state == "favorable"
  and (.refusals | map(.target)) == ["T2"]' <<<"$first" >/dev/null || fail "first pass not read back from the real tracker: $first"
refused "la première passe du relecteur de graphe refuse T2" -- publish "$D1"
refused "T2 n'est pas un refus restant" -- "$REVIEW" decide "$D1" --ticket T2 --decision publish \
  --approved-by benjamin --words "je garde T2" --project acme --config-dir "$PROJECTS"

answer "$D1" "$NOT_DEMONSTRABLE" >/dev/null
before=$(tracker)
set +e
third=$("$REVIEW" request "$D1" --author-model "modele-auteur-essai" 2>&1 >/dev/null); rc=$?
set -e
[ "$rc" = 5 ] || fail "a third pass was not refused with exit 5 (exit $rc): $third"
grep -qF -- "- T2 — à trancher par Benjamin" <<<"$third" || fail "the third-pass refusal does not list T2: $third"
[ "$before" = "$(tracker)" ] || fail "the refused third pass wrote to the real tracker"
refused "sans décision de Benjamin" -- publish "$D1"
refused "avec les mots de Benjamin" -- "$REVIEW" decide "$D1" --ticket T2 --decision publish \
  --approved-by benjamin --words "  " --project acme --config-dir "$PROJECTS"
refused "n'est pas l'approbateur humain déclaré" -- "$REVIEW" decide "$D1" --ticket T2 --decision publish \
  --approved-by "$REVIEWER_AGENT" --words "je garde T2" --project acme --config-dir "$PROJECTS"
"$REVIEW" decide "$D1" --ticket T2 --decision publish --approved-by benjamin \
  --words "T2 reste ainsi : T3 suit dans la même Spec, l'écart « = » est voulu." --project acme --config-dir "$PROJECTS" >/dev/null \
  || fail "Benjamin's decision was refused"
grep -qF "« T2 reste ainsi : T3 suit dans la même Spec, l'écart « = » est voulu. »" <<<"$("$REVIEW" remaining "$D1" --text)" \
  || fail "Benjamin's words are not read back as recorded"
published=$(publish "$D1") || fail "the reviewed and ruled draft was refused"
jq -e '.graph_review.pass == 2 and .graph_review.decisions.T2.by == "benjamin" and (.ids | length) == 4' <<<"$published" >/dev/null \
  || fail "unexpected publication result: $published"
echo "   partie 1 : état de relecture écrit et relu sur le vrai tracker (2 passes, refus restant T2,"
echo "              troisième passe refusée, décision de Benjamin, publication) — conforme"

D2=$(draft "$FIXTURE_DRAFT")
answer "$D2" '{}' >/dev/null
"$REVIEW" check "$D2" >/dev/null || fail "a favorable review of the current digest does not hold"
gc bd update "$D2" --description "$FIXTURE_DRAFT
# corrigé après la relecture" >/dev/null
approve "$D2"
refused "a changé depuis sa relecture de graphe" -- publish "$D2"
echo "              brouillon modifié après relecture : publication refusée — conforme"

# --- part 2: one real reviewer session ---------------------------------------
if [ "${GRAPH_REVIEW_TRIAL_SESSION:-0}" != 1 ]; then
  echo "   partie 2 : non lancée (GRAPH_REVIEW_TRIAL_SESSION=1 lance une session réelle du rôle relecteur)"
  echo "PASS"
  exit 0
fi

env -u CLAUDE_CODE_SESSION_ID gc supervisor run >"$TRIAL/supervisor.out" 2>&1 </dev/null &
sleep 3
gc --city "$CITY" start >"$TRIAL/start.out" 2>&1 || true

D3=$(draft "$FIXTURE_DRAFT")
AUTHOR_MODEL="${GRAPH_REVIEW_TRIAL_AUTHOR_MODEL:-gpt-5.6-sol}"
set +e
reviewed=$("$REVIEW" review "$D3" --author-model "$AUTHOR_MODEL" --timeout "${GRAPH_REVIEW_TRIAL_TIMEOUT:-1500}" 2>"$TRIAL/review.err"); rc=$?
set -e
if [ "$rc" != 0 ]; then
  gc --city "$CITY" session list 2>&1 | head -20 >&2 || true
  fail "the real review did not return a verdict (exit $rc): $(cat "$TRIAL/review.err")"
fi
echo "   partie 2 : session réelle du rôle relecteur ($REVIEWER_AGENT, $REVIEWER_PROVIDER, $REVIEWER_MODEL), auteur déclaré $AUTHOR_MODEL"
jq -r '"              ticket de relecture \(.review_bead), passe \(.pass), digest \(.digest)",
       "              même modèle que l'"'"'auteur : \(.same_model)",
       (.tickets | to_entries[] | "              \(.key) : \(.value.verdict)"),
       "              graphe : \(.graph.verdict)",
       (.refusals[] | .target as $t | .reasons[] | "              refus \($t) — \(.question) : \(.reason)")' <<<"$reviewed"
jq -e '.refusals | any(.target == "T2" and (.reasons | any(.check == "demonstrable_alone")))' <<<"$reviewed" >/dev/null \
  || fail "the reviewer session did not refuse T2 as not demonstrable alone: $reviewed"
bead=$(jq -r '.review_bead' <<<"$reviewed")
gc bd show "$bead" --json | jq -e '.[0].metadata["gc.dispatched_via"] == "dispatch-door" and .[0].metadata["gc.dispatch_formula"] == "mol-graph-review"' >/dev/null \
  || fail "the review bead was not routed through the dispatch door"
echo "              T2 refusé comme non démontrable seul par la session réelle — conforme"
echo "PASS"
