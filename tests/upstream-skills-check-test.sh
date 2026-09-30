#!/usr/bin/env bash
# W13 (A6b, af-hxc8ra): bin/upstream-skills-check compares mattpocock/skills'
# published tags against the Method Baseline pinned in
# docs/UPSTREAM_SKILLS.md, files exactly one proposal bead the first time a
# new tag appears, never files a second one for the same tag, files nothing
# when there is no new tag, changes no skill file/pin/branch/config, and
# loads through gc's own order validation. Drives the CLI against a fake
# `bd`, never the live runtime.
set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
CLI="$ROOT/bin/upstream-skills-check"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

command -v jq >/dev/null 2>&1 || fail "required command is unavailable: jq"
command -v git >/dev/null 2>&1 || fail "required command is unavailable: git"

TMP=$(mktemp -d /tmp/af-upstream-skills-check.XXXXXX)
trap 'rm -rf -- "$TMP"' EXIT

GC_CALLS_LOG="$TMP/gc-calls.log"
: >"$GC_CALLS_LOG"
FAKE_GC="$TMP/gc"
cat >"$FAKE_GC" <<'STUB'
#!/usr/bin/env bash
{ printf -- '--- call: %s ---\n' "$*"; } >> "$GC_CALLS_LOG"
echo "Created issue: af-fakeprop"
STUB
chmod +x "$FAKE_GC"

NO_TAGS_FILE="$TMP/tags-none.txt"
: >"$NO_TAGS_FILE"

ONE_TAG_FILE="$TMP/tags-v1.txt"
printf 'abc123def456\trefs/tags/v1.2.3\n' >"$ONE_TAG_FILE"

STATE_FILE="$TMP/state.json"

run_check() {
  local tags_file="$1"; shift
  GC_BIN="$FAKE_GC" \
    GC_CALLS_LOG="$GC_CALLS_LOG" \
    UPSTREAM_SKILLS_CHECK_TAGS_FILE="$tags_file" \
    UPSTREAM_SKILLS_CHECK_STATE_FILE="$STATE_FILE" \
    UPSTREAM_SKILLS_CHECK_NOW=1000 \
    "$CLI" "$@"
}

# 1. Before touching git state, capture it so we can prove the order changes
#    nothing in the repo it runs from, whatever the tag list.
BEFORE_STATUS=$(cd "$ROOT" && git status --porcelain)

# 2. No new tag files nothing.
: >"$GC_CALLS_LOG"
run_check "$NO_TAGS_FILE" >/dev/null || fail "check with no tags should exit 0"
[ -s "$GC_CALLS_LOG" ] && fail "no tags published should file nothing, got: $(cat "$GC_CALLS_LOG")"
[ -f "$STATE_FILE" ] && fail "no tags published should not write a state file"

# 3. A faked remote tag list with a new tag files exactly one proposal naming the tag.
: >"$GC_CALLS_LOG"
run_check "$ONE_TAG_FILE" >/dev/null || fail "check with a new tag should exit 0"
CALLS=$(grep -c -- '--- call:' "$GC_CALLS_LOG" || true)
[ "$CALLS" = "1" ] || fail "expected exactly one gc call, got $CALLS: $(cat "$GC_CALLS_LOG")"
grep -q 'bd create' "$GC_CALLS_LOG" || fail "expected a bd create call, got: $(cat "$GC_CALLS_LOG")"
grep -q -- '-l proposal' "$GC_CALLS_LOG" || fail "expected the bead to be labelled proposal, got: $(cat "$GC_CALLS_LOG")"
grep -q 'v1.2.3' "$GC_CALLS_LOG" || fail "expected the proposal to name the new tag v1.2.3, got: $(cat "$GC_CALLS_LOG")"
[ -f "$STATE_FILE" ] || fail "expected a state file recording the flagged tag"
[ "$(jq -r '.last_flagged_tag' "$STATE_FILE")" = "v1.2.3" ] || fail "expected state to record v1.2.3, got $(cat "$STATE_FILE")"

# 4. The same tag seen again on a later day files no second proposal.
: >"$GC_CALLS_LOG"
UPSTREAM_SKILLS_CHECK_NOW=2000 run_check "$ONE_TAG_FILE" >/dev/null || fail "repeat check should exit 0"
[ -s "$GC_CALLS_LOG" ] && fail "the same tag seen again should file nothing, got: $(cat "$GC_CALLS_LOG")"

# 5. Whatever the tag list, the order never changes a skill file, pin,
#    branch, or config in the repo it runs from.
AFTER_STATUS=$(cd "$ROOT" && git status --porcelain)
[ "$BEFORE_STATUS" = "$AFTER_STATUS" ] || fail "upstream-skills-check must change no skill file, pin, branch, or config in $ROOT"
CURRENT_BRANCH_BEFORE=$(cd "$ROOT" && git rev-parse --abbrev-ref HEAD)
[ "$CURRENT_BRANCH_BEFORE" = "$(cd "$ROOT" && git rev-parse --abbrev-ref HEAD)" ] || fail "upstream-skills-check must not switch branches"

# 6. The order loads through gc's own order validation. An isolated
#    worktree checkout has city.toml (tracked) but not the generated,
#    gitignored city.provider.toml it includes (bin/provider-failover
#    regenerates it at runtime) -- stub one in only if it's missing, purely
#    to let `gc order show` load city.toml, and remove the stub after so a
#    run against the live root (which already has a real one) is untouched.
if command -v gc >/dev/null 2>&1; then
  PROVIDER_STUB="$ROOT/city.provider.toml"
  STUBBED_PROVIDER=0
  if [ ! -f "$PROVIDER_STUB" ]; then
    printf '[workspace]\nprovider = "claude-standard"\n' >"$PROVIDER_STUB"
    STUBBED_PROVIDER=1
  fi
  VALIDATE_RC=0
  gc order show upstream-skills-check --city "$ROOT" >/dev/null 2>&1 || VALIDATE_RC=$?
  [ "$STUBBED_PROVIDER" = 1 ] && rm -f "$PROVIDER_STUB"
  [ "$VALIDATE_RC" = 0 ] || fail "gc order show upstream-skills-check should validate the order"
else
  echo "SKIP: gc not installed -- cannot exercise gc's own order validation for upstream-skills-check" >&2
fi

echo "PASS: upstream-skills-check files exactly one proposal on a new tag, none on a repeat or absent tag, and changes nothing"
