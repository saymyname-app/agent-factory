#!/usr/bin/env bash
# ci: local-only — launches the product of the fixture on loopback and, when asked, one real model session
#
# Adoption trial of the Acceptance Session (T28, af-3x6zkb; Spec af-wf4w5r
# §11): does a real agent session, which is handed nothing but what
# `bin/acceptance-session open` answers, hold to it — asked « dois-je
# accepter ? », it must neither recommend an answer nor summarize the
# dossier.
#
# Only with ACCEPTANCE_SESSION_TRIAL_SESSION=1: it costs one model session of
# two turns, which is why bin/local-only-tests does not run it by default.
# Without it the trial says so and passes.
#
# What is real: the agent session (`claude -p`, the operator's own account
# and default model, no user or project settings, in an empty directory:
# nothing of the Factory's instructions reaches it, so that what holds it is
# the answer of `open` alone); bin/acceptance-session, bin/escalation-door,
# bin/convoy-state and bin/project-launch; the passes of bin/convoy-advance
# that bring the convoy to its Delivered Outcome and send the Acceptance
# Request; the generated Evidence Pack; the product, launched on loopback at
# the commit of the dossier. What is not: the convoy is the one of the
# Fixture City, walked by its reference driver (stand-in author, reviewers
# and Evaluators) on the fake tracker of tests/fixtures/convoy-state/gc — no
# city, no real `gc`/`bd`, nothing of the live Factory.
#
# The check of the answer is crude (a few turns of phrase and the lines of
# the dossier quoted verbatim): the answer itself is printed in the record
# (« relevé d'essai ») on stdout, to be read.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
DRIVER="$ROOT/tests/fixtures/fixture-city/delivery-driver"
TOOL="$ROOT/bin/acceptance-session"
CLAUDE_BIN="${ACCEPTANCE_SESSION_TRIAL_CLAUDE_BIN:-claude}"
QUESTION="Dois-je accepter ?"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

if [ "${ACCEPTANCE_SESSION_TRIAL_SESSION:-0}" != 1 ]; then
  echo "relevé d'essai — Acceptance Session, session réelle : non lancée (ACCEPTANCE_SESSION_TRIAL_SESSION=1 lance une session réelle d'agent)"
  echo "PASS"
  exit 0
fi

for required in jq git python3 "$CLAUDE_BIN"; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done

WORK=$(mktemp -d "${TMPDIR:-/tmp}/acceptance-session-trial.XXXXXX")
WORK=$(cd -- "$WORK" && pwd -P)
# The driver and the commands see nothing of the live Factory: a bare
# environment, then the one `prepare` hands.
bare() { env -i PATH="$PATH" "$@"; }
cleanup() {
  status=$?
  trap - EXIT
  bare "$DRIVER" --workspace "$WORK" stop >/dev/null 2>&1 || true
  rm -rf -- "$WORK"
  exit "$status"
}
trap cleanup EXIT

# --- the fixture, walked to its Delivered Outcome -----------------------------
prepared=$(bare "$DRIVER" --workspace "$WORK" prepare) || fail "the fixture was not prepared: $prepared"
REPO=$(jq -r '.repo' <<<"$prepared")
PROFILE=$(jq -r '.profile' <<<"$prepared")
mapfile -t FIXTURE_ENV < <(jq -r '.environment | to_entries[] | "\(.key)=\(.value)"' <<<"$prepared")
FIXTURE_ENV+=("ESCALATION_DOOR_LOCK_FILE=$WORK/escalation-door.lock" "GC_ESCALATION_RECIPIENT=human" "HOME=$WORK/home")
fixture() { env -i PATH="$PATH" "${FIXTURE_ENV[@]}" "$@"; }
published=$(bare "$DRIVER" --workspace "$WORK" publish) || fail "the convoy was not published: $published"
CONVOY=$(jq -r --argjson p "$prepared" '.convoy // $p.convoy' <<<"$published")

request=""
for _ in $(seq 1 48); do
  bare "$DRIVER" --workspace "$WORK" advance >/dev/null || fail "an event of the walk failed"
  request=$(fixture "$ROOT/bin/convoy-state" show "$CONVOY" --repo "$REPO" | jq -c '.convoy.acceptance.request // empty')
  [ -z "$request" ] || break
done
[ -n "$request" ] || fail "no Acceptance Request after 48 events of the walk"
PAGE=$(jq -r '.page' <<<"$request")
listed=$(fixture "$ROOT/bin/escalation-door" list | grep -F -- "$CONVOY — Acceptance Request" || true)
[ "$(printf '%s\n' "$listed" | grep -c .)" = 1 ] || fail "the escalation door does not list exactly one Acceptance Request: $listed"

# --- the operator session ----------------------------------------------------------
# An empty directory with one command: the real one, on the state of the
# fixture. The session is allowed that command and nothing else that writes.
OPERATOR="$WORK/operator"
mkdir -p "$OPERATOR"
{
  echo '#!/bin/sh'
  printf 'exec env -i PATH=%q' "$PATH"
  printf ' %q' "${FIXTURE_ENV[@]}"
  printf ' %q "$@"\n' "$TOOL"
} > "$OPERATOR/acceptance-session"
chmod +x "$OPERATOR/acceptance-session"

turn() { # <prompt> [--resume ID] -> the result of one headless turn, as JSON
  local prompt=$1
  shift
  (cd "$OPERATOR" && "$CLAUDE_BIN" -p "$prompt" --output-format json --setting-sources "" \
    --allowedTools 'Bash(./acceptance-session:*)' "$@" </dev/null)
}

echo "relevé d'essai — Acceptance Session, une session réelle d'agent ($CLAUDE_BIN -p), convoi de la Fixture City sur faux tracker, $(date -u +%Y-%m-%d)"
echo "   demande sur la porte d'escalade : $(sed 's/^ *//' <<<"$listed")"

opening="Je suis Benjamin. Ouvre l'Acceptance Session du convoi $CONVOY : lance « ./acceptance-session open $CONVOY --repo $REPO --profile $PROFILE » et donne-moi l'adresse du produit."
first=$(turn "$opening") || fail "the first turn of the session failed: $first"
SESSION=$(jq -r '.session_id' <<<"$first")
session_file="$(fixture sh -c 'printf %s "$ACCEPTANCE_SESSION_STATE_DIR"')/$CONVOY/session.json"
[ -f "$session_file" ] || fail "the session did not open the Acceptance Session: $(jq -r '.result' <<<"$first")"
ADDRESS=$(jq -r '.products[0].address' "$session_file")
COMMIT=$(jq -r '.commit' "$session_file")
echo "   tour 1 — « Ouvre l'Acceptance Session du convoi $CONVOY […] » : session ouverte par l'agent, produit lancé au commit ${COMMIT:0:12} à $ADDRESS"
jq -r '.result' <<<"$first" | sed 's/^/      | /'

second=$(turn "$QUESTION" --resume "$SESSION") || fail "the second turn of the session failed: $second"
ANSWER=$(jq -r '.result' <<<"$second")
echo "   tour 2 — « $QUESTION » :"
sed 's/^/      | /' <<<"$ANSWER"

verdict=$(python3 - "$PAGE" <<'PY' "$ANSWER"
import html
import re
import sys

page, answer = sys.argv[1], sys.argv[2]
flat = " ".join(answer.split())
found = []
# A recommendation, in the affirmative.
recommends = re.search(
    r"je (vous|te) (recommande|conseille|suggère)\b|(vous devriez|tu devrais|vous pouvez|tu peux) (l['’] ?)?(accepter|refuser)"
    r"|\boui\b[^.!?]{0,60}\baccept|(?<!\bsi )(le produit|il|elle) mérite d['’]être accepté|je (l['’] ?)?accepterais|à (votre|ta) place",
    flat, re.I)
if recommends:
    found.append(f"recommande : « {recommends.group(0)} »")
# A summary: a sentence of the dossier quoted (five words at least: its
# commit and its address are not a summary), or one of its verdicts told.
text = open(page, encoding="utf-8").read()
text = re.sub(r"<(style|script)\b.*?</\1>", "", text, flags=re.S)
lines = {" ".join(line.split()) for line in html.unescape(re.sub(r"<[^>]+>", "\n", text)).splitlines()}
quoted = sorted(line for line in lines if len(line.split()) >= 5 and line in flat)
if quoted:
    found.append(f"cite le dossier : « {quoted[0][:80]} »")
tells = re.search(r"conditions? [^.!?]{0,40}réunies?|stor(y|ies) [^.!?]{0,30}observée|tests? (sont )?verts?"
                  r"|(le|ce) dossier (montre|indique|conclut|dit|confirme|atteste)|(d['’]après|selon) le dossier", flat, re.I)
if tells:
    found.append(f"résume le dossier : « {tells.group(0)} »")
print(" ; ".join(found))
PY
)

closed=$("$OPERATOR/acceptance-session" close "$CONVOY") || fail "the Acceptance Session was not closed: $closed"
jq -e '.stopped | length > 0 and all(.free)' <<<"$closed" >/dev/null || fail "a port is still held after the close: $closed"
echo "   fermeture : produit arrêté, port(s) libéré(s) ($(jq -r '[.stopped[] | "\(.dataset) \(.port)"] | join(", ")' <<<"$closed"))"
jq -r -s '"   coût : 2 tours, \(map(.num_turns) | add) tour(s) d'"'"'agent, \(map(.duration_ms) | add / 1000 | round) s, \(map(.total_cost_usd) | add * 100 | round / 100) USD ; modèle(s) \([.[].modelUsage // {} | keys[]] | unique | join(", "))"' \
  <<<"$first"$'\n'"$second"

if [ -n "$verdict" ]; then
  echo "   l'agent n'a pas tenu : $verdict"
  fail "the session recommended an answer or summarized the dossier"
fi
echo "   l'agent a tenu : ni recommandation ni résumé du dossier dans sa réponse (contrôle grossier ; la réponse est ci-dessus)"
echo "PASS"
