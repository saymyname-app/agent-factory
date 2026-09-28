#!/usr/bin/env bash
# O03 (af-ui0ua): bin/dispatch-door is the one door every rig and formula
# dispatches through -- it validates the rig and formula against
# config/projects/<rig>.toml, resolves the qualified sling target, always
# passes --reassign, and stamps gc.dispatched_via so
# bin/dispatch-door-guard can detect a raw `gc sling` that skipped it.
# O11 (af-eabd4): it also refuses to dispatch a bead labelled `proposal` --
# improvement ideas are triaged at the next Planning Run, never dispatched.
set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
DOOR="$REPO_ROOT/bin/dispatch-door"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

CALLS="$TMP/calls"
cat > "$TMP/gc" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$CALLS"
case "$*" in
  *"bd show "*"--json"*)
    printf '%s\n' "$BEAD_LABELS_JSON"
    ;;
  *)
    printf '{"ok":true}\n'
    ;;
esac
STUB
chmod +x "$TMP/gc"
export CALLS
export BEAD_LABELS_JSON='[{"labels":[]}]'

# A stub provider-failover that reports providers available by default --
# O08's exhaustion gate must not depend on this host's live provider state.
cat > "$TMP/provider-failover" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$PROVIDER_STATUS_JSON"
STUB
chmod +x "$TMP/provider-failover"
export DISPATCH_DOOR_PROVIDER_FAILOVER_BIN="$TMP/provider-failover"
export PROVIDER_STATUS_JSON='{"total_exhaustion":{"active":false}}'

# ---------------------------------------------------------------------------
# 1. Every rig, every formula that project registers in the real repo --
#    including build-basic, which had no valid door before this (O03's
#    explicit acceptance criterion) -- resolves to a correct sling command.
# ---------------------------------------------------------------------------
# shellcheck source=lib/project_registry.sh
. "$REPO_ROOT/lib/project_registry.sh"
CONFIG_DIR="$REPO_ROOT/config/projects"
COVERED_BUILD_BASIC=0

while IFS='|' read -r rig_dir _repo _branch _ci rig_name; do
  target=$(project_registry_dispatch_target "$CONFIG_DIR" "$rig_name")
  formulas_csv=$(project_registry_dispatch_formulas "$CONFIG_DIR" "$rig_name")
  [ -n "$target" ] || fail "$rig_name has no sling_target -- dispatch-door cannot cover it"
  [ -n "$formulas_csv" ] || fail "$rig_name has no formulas list -- dispatch-door cannot cover it"

  qualified="$target"
  [ "$rig_dir" = "." ] || qualified="$rig_name/$target"

  IFS=',' read -ra formulas <<<"$formulas_csv"
  for formula in "${formulas[@]}"; do
    [ "$formula" = "build-basic" ] && COVERED_BUILD_BASIC=1
    : > "$CALLS"
    out=$(GC_BIN="$TMP/gc" FACTORY_ROOT="$REPO_ROOT" "$DOOR" "${rig_name}-fixture" --rig "$rig_name" --formula "$formula") \
      || fail "$rig_name/$formula: dispatch-door rejected a formula it advertises as valid"
    label_check=$(cat "$CALLS" | sed -n '1p')
    [[ $label_check == "--city $REPO_ROOT bd show ${rig_name}-fixture --json" ]] \
      || fail "$rig_name/$formula: unexpected label-check call: $label_check"
    call=$(cat "$CALLS" | sed -n '2p')
    [[ $call == "--city $REPO_ROOT sling $qualified ${rig_name}-fixture --on $formula --reassign" ]] \
      || fail "$rig_name/$formula: unexpected sling call: $call"
    [[ $call == *"--reassign"* ]] || fail "$rig_name/$formula: dropped --reassign"
    stamp=$(cat "$CALLS" | sed -n '3p')
    [[ $stamp == "--city $REPO_ROOT bd update ${rig_name}-fixture --set-metadata gc.dispatched_via=dispatch-door --set-metadata gc.dispatch_formula=$formula --set-metadata gc.dispatch_target=$qualified --set-metadata gc.dispatch_rig=$rig_name" ]] \
      || fail "$rig_name/$formula: unexpected (or missing) dispatch-door stamp call: $stamp"
  done
done < <(project_registry_rows "$CONFIG_DIR")

[ "$COVERED_BUILD_BASIC" = "1" ] \
  || fail "no project in config/projects/ registers build-basic -- the door-tests-build-basic acceptance criterion is untested"

# ---------------------------------------------------------------------------
# 2. Rejections happen before any gc call, and stay generic (no rig name is
#    hardcoded in the door itself -- it only ever reads config/projects/).
# ---------------------------------------------------------------------------
: > "$CALLS"
if GC_BIN="$TMP/gc" FACTORY_ROOT="$REPO_ROOT" "$DOOR" af-fixture --rig agent-factory --formula build-basic >/dev/null 2>&1; then
  fail "accepted a formula not in agent-factory's formulas list"
fi
[ ! -s "$CALLS" ] || fail "called gc after rejecting an invalid formula"

: > "$CALLS"
if GC_BIN="$TMP/gc" FACTORY_ROOT="$REPO_ROOT" "$DOOR" zz-fixture --rig zz-nonexistent-rig --formula mol-do-work >/dev/null 2>&1; then
  fail "accepted a rig with no config/projects/*.toml file"
fi
[ ! -s "$CALLS" ] || fail "called gc after rejecting an unknown rig"

: > "$CALLS"
if GC_BIN="$TMP/gc" FACTORY_ROOT="$REPO_ROOT" "$DOOR" af-fixture --rig agent-factory >/dev/null 2>&1; then
  fail "dispatched with no --formula"
fi
[ ! -s "$CALLS" ] || fail "called gc with no --formula given"

# ---------------------------------------------------------------------------
# 3. --dry-run prints the command and calls gc for neither the sling nor
#    the stamp.
# ---------------------------------------------------------------------------
: > "$CALLS"
out=$(GC_BIN="$TMP/gc" FACTORY_ROOT="$REPO_ROOT" "$DOOR" af-fixture --rig agent-factory --formula mol-do-work --dry-run)
out="${out% }"
[[ $out == "$TMP/gc --city $REPO_ROOT sling factory-worker af-fixture --on mol-do-work --reassign" ]] \
  || fail "unexpected --dry-run output: $out"
[ ! -s "$CALLS" ] || fail "--dry-run called gc"

# ---------------------------------------------------------------------------
# 4. A bead labelled `proposal` is refused, after the label check but before
#    any sling or stamp call -- and dry-run previews still bypass the check
#    entirely (dry-run never touches gc at all).
# ---------------------------------------------------------------------------
: > "$CALLS"
BEAD_LABELS_JSON='[{"labels":["proposal"]}]'
if GC_BIN="$TMP/gc" FACTORY_ROOT="$REPO_ROOT" BEAD_LABELS_JSON="$BEAD_LABELS_JSON" "$DOOR" af-fixture --rig agent-factory --formula mol-do-work >/dev/null 2>&1; then
  fail "dispatched a bead labelled proposal"
fi
label_check=$(cat "$CALLS" | sed -n '1p')
[[ $label_check == "--city $REPO_ROOT bd show af-fixture --json" ]] \
  || fail "proposal refusal: expected a label check before refusing, got: $label_check"
[ "$(wc -l < "$CALLS")" -eq 1 ] \
  || fail "proposal refusal: called gc after the label check ($(cat "$CALLS"))"
BEAD_LABELS_JSON='[{"labels":[]}]'

# ---------------------------------------------------------------------------
# 5. The Mayor prompt names only the door for dispatch (O03 acceptance
#    criterion): it points at bin/dispatch-door for every rig, and every
#    remaining `gc sling` mention is a prohibition or an incident citation,
#    never an instruction to build one by hand.
# ---------------------------------------------------------------------------
MAYOR_PROMPT="$REPO_ROOT/agents/mayor/prompt.template.md"
grep -qF './bin/dispatch-door' "$MAYOR_PROMPT" \
  || fail "Mayor prompt does not name bin/dispatch-door for non-HQ dispatch"
grep -qF './bin/factory-work-dispatch' "$MAYOR_PROMPT" \
  || fail "Mayor prompt does not name bin/factory-work-dispatch for HQ dispatch"
while IFS= read -r line; do
  case "$line" in
    *'never raw `gc sling`'*|*'Never construct a `gc sling`'*|*'a raw `gc sling'*) ;;
    *) fail "Mayor prompt still instructs building a gc sling command by hand: $line" ;;
  esac
done < <(grep -F 'gc sling' "$MAYOR_PROMPT")

# ---------------------------------------------------------------------------
# 6. Total provider exhaustion (O08, af-harft): dispatch is refused before
#    any gc call, with an explicit reason naming the tracked bead; --dry-run
#    still bypasses it (a pure preview of the sling command).
# ---------------------------------------------------------------------------
: > "$CALLS"
PROVIDER_STATUS_JSON='{"total_exhaustion":{"active":true,"next_reset":"2026-09-29T05:00:00Z","bead":"af-exh1"}}'
if GC_BIN="$TMP/gc" FACTORY_ROOT="$REPO_ROOT" PROVIDER_STATUS_JSON="$PROVIDER_STATUS_JSON" \
    "$DOOR" af-fixture --rig agent-factory --formula mol-do-work >/dev/null 2>/tmp/dispatch-door-exhaustion-err.$$; then
  fail "dispatched while provider-failover reported total exhaustion"
fi
err=$(cat "/tmp/dispatch-door-exhaustion-err.$$")
rm -f "/tmp/dispatch-door-exhaustion-err.$$"
[[ $err == *"total provider exhaustion"* ]] || fail "exhaustion refusal did not name the reason: $err"
[[ $err == *"af-exh1"* ]] || fail "exhaustion refusal did not name the tracked bead: $err"
[ ! -s "$CALLS" ] || fail "called gc while refusing dispatch for total provider exhaustion"

: > "$CALLS"
out=$(GC_BIN="$TMP/gc" FACTORY_ROOT="$REPO_ROOT" PROVIDER_STATUS_JSON="$PROVIDER_STATUS_JSON" \
  "$DOOR" af-fixture --rig agent-factory --formula mol-do-work --dry-run)
out="${out% }"
[[ $out == "$TMP/gc --city $REPO_ROOT sling factory-worker af-fixture --on mol-do-work --reassign" ]] \
  || fail "--dry-run did not bypass the exhaustion gate: $out"
PROVIDER_STATUS_JSON='{"total_exhaustion":{"active":false}}'
export PROVIDER_STATUS_JSON

echo "PASS: dispatch-door validates target/formula/--reassign for every rig and formula from project files"
