#!/usr/bin/env bash
#
# factory-guard must repair a campaign coordination bead whose
# gc.campaign_candidate/condition went missing, or whose coordination
# pointers hold an empty string, instead of leaving the sentinel to crash
# (ADR-0023, af-hihkg).
#
# Replays the 2026-09-18 08:43Z incident: gc.campaign_candidate vanished on
# the coordination bead by a hand-write while the automatic campaign stayed
# marked active, and gc.current held an empty string instead of "none". The
# sentinel then died with "Une campagne active doit exposer sa condition et
# son candidat d'autorisation" and `mayor-campaign activate` refused to touch
# an already-active campaign, so nothing could repair it short of another
# hand-write -- exactly what ADR-0023 exists to end. factory-guard now calls
# `mayor-campaign repair --mayor` every run (section 7c), which is a no-op
# when nothing needs fixing, and pages the Mayor exactly once per run that
# actually repaired something.
#
# The gc here is a stub on PATH, generic enough to serve mayor-campaign's own
# `bd show`/`bd update af-1vr4 --set-metadata ...` calls (looping over every
# pair in one call, the shape mayor-campaign always uses) as well as
# factory-guard's own coordination-bead reads.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
GUARD="$REPO_ROOT/bin/factory-guard"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

# --- a throwaway city: committed city.toml, ignored .gc ----------------------
git init -q --bare "$TMP/origin.git"
git init -q "$TMP/city"
cd "$TMP/city"
git config user.email t@t; git config user.name t; git config commit.gpgsign false
git remote add origin "$TMP/origin.git"
mkdir -p .gc
printf '.gc/\n' > .gitignore
printf '[workspace]\nprovider = "claude"\n' > city.toml
git add -A; git commit -qm city; git branch -M main; git push -q origin main; git fetch -q origin

COORD="$TMP/coord.json"
CALLS="$TMP/calls.log"; : > "$CALLS"
mkdir -p "$TMP/bin"

cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "\$*" >> "$CALLS"
if [[ \${1:-} == bd && \${2:-} == show && \${3:-} == af-1vr4 ]]; then
  cat "$COORD"
  exit 0
fi
if [[ \${1:-} == bd && \${2:-} == show ]]; then
  echo '[]'
  exit 0
fi
if [[ \${1:-} == bd && \${2:-} == update && \${3:-} == af-1vr4 ]]; then
  shift 3
  tmp="$COORD.tmp"
  cp "$COORD" "\$tmp"
  while [[ \$# -gt 0 ]]; do
    [[ \$1 == --set-metadata && \$# -ge 2 ]] || exit 64
    pair=\$2; key=\${pair%%=*}; value=\${pair#*=}
    jq --arg k "\$key" --arg v "\$value" '.[0].metadata[\$k] = \$v' "\$tmp" > "\$tmp.next"
    mv "\$tmp.next" "\$tmp"
    shift 2
  done
  mv "\$tmp" "$COORD"
  printf '{}\n'
  exit 0
fi
if [[ \${1:-} == mail && \${2:-} == send ]]; then
  exit 0
fi
exit 0
STUB
chmod +x "$TMP/bin/gc"
export PATH="$TMP/bin:$PATH"
# ADR-0023: this section shells out to bin/mayor-campaign, a separate
# process. Relying on PATH alone to shadow `gc` for that nested exec is not
# reliable everywhere `gc` is a real command already on PATH; GC_BIN is an
# explicit environment variable mayor-campaign reads itself, so export it
# too -- the same belt-and-braces pattern tests/campaign-pointer-test.sh and
# tests/factory-guard-liveness-test.sh already use.
export GC_BIN="$TMP/bin/gc"
export CAMPAIGN_LOCK_FILE="$TMP/campaign.lock"

write_coord() {  # write_coord <json metadata object>
  jq -n --argjson m "$1" '[{id:"af-1vr4", metadata:$m}]' > "$COORD"
}

guard() { FACTORY_ROOT="$TMP/city" "$GUARD" "$@" 2>&1 || true; }
mail_count() { grep -c '^mail send mayor' "$CALLS" 2>/dev/null || true; }

broken_metadata='{
  "gc.current": "",
  "gc.current_jit": "none",
  "gc.needs_benjamin": "none",
  "gc.campaign_mode": "automatic",
  "gc.campaign_state": "active",
  "gc.campaign_condition": "Le Mayor enchaîne le premier candidat éligible",
  "gc.campaign_candidate_last": "af-cm1l",
  "gc.campaign_condition_last": "Le Mayor enchaîne le premier candidat éligible",
  "gc.campaign_owner": "Mayor", "gc.campaign_action": "Aucune action de Benjamin",
  "gc.campaign_wake_state": "none", "gc.campaign_failure_count": "0"
}'

healthy_metadata='{
  "gc.current": "none",
  "gc.current_jit": "none",
  "gc.needs_benjamin": "none",
  "gc.campaign_mode": "automatic",
  "gc.campaign_state": "active",
  "gc.campaign_candidate": "af-cm1l",
  "gc.campaign_condition": "Le Mayor enchaîne le premier candidat éligible",
  "gc.campaign_candidate_last": "af-cm1l",
  "gc.campaign_condition_last": "Le Mayor enchaîne le premier candidat éligible",
  "gc.campaign_owner": "Mayor", "gc.campaign_action": "Aucune action de Benjamin",
  "gc.campaign_wake_state": "none", "gc.campaign_failure_count": "0"
}'

# 1. --check-only never invokes the --mayor door: reports and writes nothing --
write_coord "$broken_metadata"
out=$(guard --check-only)
grep -q "campaign-repair — not checked (--check-only never invokes a --mayor door)" <<<"$out" \
  || { echo "$out" >&2; fail "--check-only did not stand down"; }
[ "$(jq -r '.[0].metadata["gc.campaign_candidate"] // "missing"' "$COORD")" = "missing" ] \
  || fail "--check-only wrote to the coordination bead"
[ "$(mail_count)" = "0" ] || fail "--check-only paged the Mayor"

# 2. the default run repairs the missing candidate and the empty pointer,
#    reports FIXED, and pages the Mayor exactly once --------------------------
write_coord "$broken_metadata"
: > "$CALLS"
out=$(guard)
grep -q "FIXED: campaign-repair: gc.campaign_candidate -> af-cm1l" <<<"$out" \
  || { echo "$out" >&2; fail "missing candidate was not restored and reported"; }
grep -q "FIXED: campaign-repair: gc.current -> none" <<<"$out" \
  || { echo "$out" >&2; fail "empty gc.current was not normalised and reported"; }
[ "$(jq -r '.[0].metadata["gc.campaign_candidate"]' "$COORD")" = "af-cm1l" ] \
  || fail "gc.campaign_candidate was not actually restored on the coordination bead"
[ "$(jq -r '.[0].metadata["gc.current"]' "$COORD")" = "none" ] \
  || fail "gc.current was not actually normalised on the coordination bead"
[ "$(mail_count)" = "1" ] || fail "expected exactly one page to the Mayor for the repair"

# 3. a healthy campaign is left alone, and nothing is repaired twice ---------
write_coord "$healthy_metadata"
: > "$CALLS"
out=$(guard)
grep -q "campaign-repair — coordination candidate/condition intact" <<<"$out" \
  || { echo "$out" >&2; fail "a healthy campaign was not reported healthy"; }
grep -q "^FIXED: campaign-repair" <<<"$out" && fail "a healthy campaign must not report a repair"
[ "$(mail_count)" = "0" ] || fail "a healthy campaign must not page the Mayor"

echo "PASS: factory-guard repairs a missing campaign candidate/condition and empty coordination pointers exactly once"
