#!/usr/bin/env bash
# T03 (af-pbxbgj, Spec af-wf4w5r §1, user stories 75-76): a delivery role
# (author, reviewer, Evaluator) is dispatched only on a provider where the
# loading of its skills was tried. bin/dispatch-door --role resolves the
# role's agent, reads the provider that agent would run on right now from
# bin/provider-failover, and refuses unless bin/role-adoption-trial holds a
# passing record for that role, that provider and the role's current
# distribution. One test per refusal and per pass; after every refusal the
# tracker calls and the record file are re-read to prove nothing was
# dispatched or written.
set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
DOOR="$REPO_ROOT/bin/dispatch-door"
TRIAL="$REPO_ROOT/bin/role-adoption-trial"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

# --- a synthetic Factory root: one project, three roles, their copies -------
FAKE="$TMP/root"
mkdir -p "$FAKE/config/projects" "$FAKE/skills/engineering" "$FAKE/bin"
cp "$REPO_ROOT/config/projects/agent-factory.toml" "$FAKE/config/projects/"
cp "$REPO_ROOT/config/delivery-roles.json" "$FAKE/config/"
cp "$REPO_ROOT/bin/delivery-role-sandbox" "$FAKE/bin/"
for skill in tdd codebase-design code-review implement; do
  mkdir -p "$FAKE/skills/engineering/$skill"
  printf -- '---\nname: %s\n---\nsynthetic %s\n' "$skill" "$skill" > "$FAKE/skills/engineering/$skill/SKILL.md"
done
for agent in delivery-author delivery-reviewer delivery-evaluator; do
  mkdir -p "$FAKE/agents/$agent"
  printf 'scope = "city"\n' > "$FAKE/agents/$agent/agent.toml"
done
mkdir -p "$FAKE/agents/delivery-author/skills" "$FAKE/agents/delivery-reviewer/skills"
cp -r "$FAKE/skills/engineering/tdd" "$FAKE/skills/engineering/codebase-design" "$FAKE/agents/delivery-author/skills/"
cp -r "$FAKE/skills/engineering/code-review" "$FAKE/agents/delivery-reviewer/skills/"
cat > "$FAKE/city.toml" <<'TOML'
[providers.alpha]
base = "builtin:claude"
[providers.alpha-readonly]
base = "builtin:claude"
command = "/somewhere/bin/delivery-role-sandbox"
[providers.beta]
base = "builtin:codex"
TOML
cat > "$FAKE/config/provider-policy.json" <<'JSON'
{"targets": {"delivery-author": {"chain": ["alpha"]},
             "delivery-reviewer": {"chain": ["alpha-readonly"]},
             "delivery-evaluator": {"chain": ["alpha-readonly"]}}}
JSON

RECORD="$TMP/trials.json"
export FACTORY_ROOT="$FAKE" ROLE_ADOPTION_TRIAL_RECORD_FILE="$RECORD"

CALLS="$TMP/calls"
cat > "$TMP/gc" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$CALLS"
case "$*" in
  *"bd show "*"--json"*) printf '[{"labels":[]}]\n' ;;
  *"bd list "*"--json"*) printf '[]\n' ;;
  *) printf '{"ok":true}\n' ;;
esac
STUB
cat > "$TMP/provider-failover" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$PROVIDER_STATUS_JSON"
STUB
chmod +x "$TMP/gc" "$TMP/provider-failover"
export CALLS GC_BIN="$TMP/gc" DISPATCH_DOOR_PROVIDER_FAILOVER_BIN="$TMP/provider-failover"

status_json() { # <author provider> <reviewer provider> <evaluator provider>
  printf '{"total_exhaustion":{"active":false},"targets":{"delivery-author":{"effective":"%s"},"delivery-reviewer":{"effective":"%s"},"delivery-evaluator":{"effective":"%s"}}}' "$1" "$2" "$3"
}
record() { # <role> <provider> <passed true|false> [digest]
  local digest=${4:-$("$TRIAL" digest --role "$1" --provider "$2")}
  jq -n --arg k "$1/$2" --arg d "$digest" --argjson p "$3" \
    '{contract:"agent-factory-role-adoption-trials/v1",trials:{($k):{passed:$p,digest:$d,observed_at:"2026-10-06T00:00:00Z",failures:(if $p then [] else ["synthetic failure"] end)}}}' > "$RECORD"
}
# refused <label> <expected stderr fragment> -- <door args...>
refused() {
  local label=$1 expect=$2; shift 3
  local before; before=$(cat "$RECORD" 2>/dev/null || true)
  : > "$CALLS"
  local rc=0
  "$DOOR" "$@" >"$TMP/out" 2>"$TMP/err" || rc=$?
  [ "$rc" -eq 2 ] || fail "$label: expected refusal (exit 2), got $rc: $(cat "$TMP/err")"
  grep -qF -- "$expect" "$TMP/err" || fail "$label: refusal does not say '$expect': $(cat "$TMP/err")"
  ! grep -q 'sling \|bd update ' "$CALLS" || fail "$label: something was dispatched or written after the refusal: $(cat "$CALLS")"
  [ "$(cat "$RECORD" 2>/dev/null || true)" = "$before" ] || fail "$label: the trial record changed during a refusal"
}

export PROVIDER_STATUS_JSON; PROVIDER_STATUS_JSON=$(status_json alpha alpha-readonly alpha-readonly)

# 1. Pass: a passing trial for the role, its effective provider and its
#    current distribution -> dispatched to the role's agent, stamped.
record reviewer alpha-readonly true
: > "$CALLS"
"$DOOR" af-fixture --rig agent-factory --formula mol-do-work --role reviewer >/dev/null \
  || fail "refused a role whose adoption trial passed on its effective provider"
grep -qxF -- "--city $FAKE sling delivery-reviewer af-fixture --on mol-do-work --reassign" "$CALLS" \
  || fail "a tried role was not slung to its own agent: $(cat "$CALLS")"
grep -qF -- "--set-metadata gc.dispatch_target=delivery-reviewer" "$CALLS" || fail "the door stamp does not name the role's agent"

record author alpha true
: > "$CALLS"
"$DOOR" af-fixture --rig agent-factory --formula mol-do-work --role author >/dev/null \
  || fail "refused the author role although its trial passed"
grep -qF -- "sling delivery-author af-fixture" "$CALLS" || fail "author role not slung to delivery-author"

# 2. Refusal: no trial recorded at all.
rm -f "$RECORD"
refused "no record" "no adoption trial is recorded for role 'evaluator' on provider 'alpha-readonly'" -- \
  af-fixture --rig agent-factory --formula mol-do-work --role evaluator

# 3. Refusal: provider switch. The reviewer was tried on alpha-readonly; the
#    failover now puts it on beta, where nothing was tried.
record reviewer alpha-readonly true
PROVIDER_STATUS_JSON=$(status_json alpha beta alpha-readonly)
refused "provider switch" "no adoption trial is recorded for role 'reviewer' on provider 'beta'" -- \
  af-fixture --rig agent-factory --formula mol-do-work --role reviewer
PROVIDER_STATUS_JSON=$(status_json alpha alpha-readonly alpha-readonly)

# 4. Refusal: the trial failed.
record reviewer alpha-readonly false
refused "failed trial" "failed (synthetic failure)" -- \
  af-fixture --rig agent-factory --formula mol-do-work --role reviewer

# 5. Refusal: the role's distribution changed after the trial (a skill file
#    edited), so the recorded trial no longer vouches for it.
record reviewer alpha-readonly true
printf 'edited after the trial\n' >> "$FAKE/agents/delivery-reviewer/skills/code-review/SKILL.md"
refused "changed distribution" "was run on another distribution" -- \
  af-fixture --rig agent-factory --formula mol-do-work --role reviewer
cp "$FAKE/skills/engineering/code-review/SKILL.md" "$FAKE/agents/delivery-reviewer/skills/code-review/SKILL.md"
"$DOOR" af-fixture --rig agent-factory --formula mol-do-work --role reviewer >/dev/null \
  || fail "still refused after the distribution was restored to what the trial saw"

# 6. Refusal: not a delivery role.
refused "unknown role" "'janitor' is not a delivery role" -- \
  af-fixture --rig agent-factory --formula mol-do-work --role janitor

# 7. Refusal: the failover reports no provider for the role's agent -- the
#    door cannot know where the session would run, so it does not guess.
PROVIDER_STATUS_JSON='{"total_exhaustion":{"active":false},"targets":{}}'
refused "no effective provider" "no effective provider" -- \
  af-fixture --rig agent-factory --formula mol-do-work --role reviewer
PROVIDER_STATUS_JSON=''
refused "no provider status" "no effective provider" -- \
  af-fixture --rig agent-factory --formula mol-do-work --role reviewer
PROVIDER_STATUS_JSON=$(status_json alpha alpha-readonly alpha-readonly)

# 8. A project whose own sling_target is a role agent is held to the same
#    rule without --role: the role is what the target is, not what is typed.
sed -i 's/^sling_target = .*/sling_target = "delivery-evaluator"/' "$FAKE/config/projects/agent-factory.toml"
rm -f "$RECORD"
refused "role agent as sling_target" "no adoption trial is recorded for role 'evaluator'" -- \
  af-fixture --rig agent-factory --formula mol-do-work
sed -i 's/^sling_target = .*/sling_target = "factory-worker"/' "$FAKE/config/projects/agent-factory.toml"

# 9. No role: dispatched exactly as before, with no trial consulted.
: > "$CALLS"
"$DOOR" af-fixture --rig agent-factory --formula mol-do-work >/dev/null || fail "a dispatch with no role was refused"
grep -qxF -- "--city $FAKE sling factory-worker af-fixture --on mol-do-work --reassign" "$CALLS" \
  || fail "a dispatch with no role no longer goes to the project's sling_target: $(cat "$CALLS")"

# 10. The real repository: every role holds exactly its distribution, and
#     every provider a role declares has a passing trial for the distribution
#     committed here. Changing a role's skills, agent, provider profile or
#     sandbox without re-running the trial turns this red before the door
#     refuses it in production.
unset FACTORY_ROOT ROLE_ADOPTION_TRIAL_RECORD_FILE
"$TRIAL" verify-distribution >/dev/null || fail "the real role distribution is not coherent"
"$TRIAL" status >"$TMP/status" 2>&1 || fail "a declared role/provider has no passing adoption trial for the committed distribution:
$(cat "$TMP/status")"

echo "PASS: dispatch-door dispatches a delivery role only on a provider with a passing adoption trial for its current distribution"
