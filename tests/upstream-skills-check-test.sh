#!/usr/bin/env bash
# W13 (A6b, af-hxc8ra): bin/upstream-skills-check compares mattpocock/skills'
# published tags against the Method Baseline pinned in
# docs/UPSTREAM_SKILLS.md, files exactly one proposal bead the first time a
# new tag appears, never files a second one for the same tag, files nothing
# when there is no new tag, changes no skill file/pin/branch/config, and
# loads through gc's own order validation. Drives the CLI against a fake
# `bd`, never the live runtime.
#
# 2026-10-07 (af-3yo0we, af-yc2ly0): a tag at or before the pinned baseline
# tag is never proposed, and a pending proposal for such a tag is resolved
# through bin/proposal-door resoudre with the pin (its commit and PR) as
# proof -- a proposal for a tag beyond the pin, or one Benjamin already
# accepted, is left alone.
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
# The pending proposals the fake tracker holds (a JSON array), for the
# resolve-against-the-pin pass: `bd list` returns it, `bd show` one of it.
PROPOSALS_FILE="$TMP/proposals.json"
printf '[]\n' >"$PROPOSALS_FILE"
FAKE_GC="$TMP/gc"
cat >"$FAKE_GC" <<'STUB'
#!/usr/bin/env bash
{ printf -- '--- call: %s ---\n' "$*"; } >> "$GC_CALLS_LOG"
if [ "${1:-}" = bd ] && [ "${2:-}" = list ]; then cat "$PROPOSALS_FILE"; exit 0; fi
if [ "${1:-}" = bd ] && [ "${2:-}" = show ]; then jq -c --arg id "$3" '[.[] | select(.id == $id)]' "$PROPOSALS_FILE"; exit 0; fi
echo "Created issue: af-fakeprop"
STUB
chmod +x "$FAKE_GC"

# The pinned baseline lives in its own small git repo, so the pin's proof
# (last commit touching the file, PR number in its subject) is real.
PIN_REPO="$TMP/pin-repo"
mkdir -p "$PIN_REPO/docs"
BASELINE_FILE="$PIN_REPO/docs/UPSTREAM_SKILLS.md"
git -C "$PIN_REPO" init -q
pin_baseline() {  # tag commit-subject
  printf 'Pinned baseline commit: `c55ee46073ed0000000000000000000000000000`\nPinned baseline tag: `%s`\n' "$1" >"$BASELINE_FILE"
  git -C "$PIN_REPO" add docs/UPSTREAM_SKILLS.md
  git -C "$PIN_REPO" -c user.name=t -c user.email=t@example.invalid commit -q -m "$2"
}
pin_baseline v1.0.0 "pin v1.0.0 (#1)"

NO_TAGS_FILE="$TMP/tags-none.txt"
: >"$NO_TAGS_FILE"

ONE_TAG_FILE="$TMP/tags-v1.txt"
printf 'abc123def456\trefs/tags/v1.2.3\n' >"$ONE_TAG_FILE"

STATE_FILE="$TMP/state.json"

run_check() {
  local tags_file="$1"; shift
  GC_BIN="$FAKE_GC" \
    GC_CALLS_LOG="$GC_CALLS_LOG" \
    PROPOSALS_FILE="$PROPOSALS_FILE" \
    UPSTREAM_SKILLS_CHECK_BASELINE_FILE="$BASELINE_FILE" \
    UPSTREAM_SKILLS_CHECK_TAGS_FILE="$tags_file" \
    UPSTREAM_SKILLS_CHECK_STATE_FILE="$STATE_FILE" \
    UPSTREAM_SKILLS_CHECK_NOW=1000 \
    "$CLI" "$@"
}

# 1. Before touching git state, capture it so we can prove the order changes
#    nothing in the repo it runs from, whatever the tag list.
# Other CI tests run concurrently and may create unrelated files in the
# checkout. Observe only the vendored skills, pin, and configuration.
BEFORE_STATUS=$(cd "$ROOT" && git status --porcelain -- skills docs/UPSTREAM_SKILLS.md config .claude city.toml)
CURRENT_BRANCH_BEFORE=$(cd "$ROOT" && git rev-parse --abbrev-ref HEAD)

# 2. No new tag files nothing.
: >"$GC_CALLS_LOG"
run_check "$NO_TAGS_FILE" >/dev/null || fail "check with no tags should exit 0"
[ -s "$GC_CALLS_LOG" ] && fail "no tags published should file nothing, got: $(cat "$GC_CALLS_LOG")"
[ -f "$STATE_FILE" ] && fail "no tags published should not write a state file"

# 3. A faked remote tag list with a new tag files exactly one proposal naming the tag.
: >"$GC_CALLS_LOG"
run_check "$ONE_TAG_FILE" >/dev/null || fail "check with a new tag should exit 0"
# proposal-door (T07) makes two writing gc calls per proposal: `bd create`
# then `bd update` to record the required fields as metadata (the one
# `bd list` before them is the read-only resolve-against-the-pin pass).
CALLS=$(grep -c -- '--- call: bd \(create\|update\)' "$GC_CALLS_LOG" || true)
[ "$CALLS" = "2" ] || fail "expected exactly two writing gc calls (create + update via proposal-door), got $CALLS: $(cat "$GC_CALLS_LOG")"
grep -q 'bd create' "$GC_CALLS_LOG" || fail "expected a bd create call, got: $(cat "$GC_CALLS_LOG")"
grep -q -- '-l proposal' "$GC_CALLS_LOG" || fail "expected the bead to be labelled proposal, got: $(cat "$GC_CALLS_LOG")"
grep -q 'v1.2.3' "$GC_CALLS_LOG" || fail "expected the proposal to name the new tag v1.2.3, got: $(cat "$GC_CALLS_LOG")"
grep -q 'gc.proposal_state=ouverte' "$GC_CALLS_LOG" || fail "expected proposal-door to record gc.proposal_state=ouverte, got: $(cat "$GC_CALLS_LOG")"
# ADR-0029: a re-pin is a method rule -> classe decision, with its recommendation.
grep -q 'gc.proposal_classe=decision' "$GC_CALLS_LOG" || fail "expected the proposal to be of classe decision (ADR-0029), got: $(cat "$GC_CALLS_LOG")"
grep -q 'recommande' "$GC_CALLS_LOG" || fail "expected a recommended option (ADR-0029 point 3), got: $(cat "$GC_CALLS_LOG")"
[ -f "$STATE_FILE" ] || fail "expected a state file recording the flagged tag"
[ "$(jq -r '.last_flagged_tag' "$STATE_FILE")" = "v1.2.3" ] || fail "expected state to record v1.2.3, got $(cat "$STATE_FILE")"

# 4. The same tag seen again on a later day files no second proposal.
: >"$GC_CALLS_LOG"
UPSTREAM_SKILLS_CHECK_NOW=2000 run_check "$ONE_TAG_FILE" >/dev/null || fail "repeat check should exit 0"
grep -q -- '--- call: bd \(create\|update\)' "$GC_CALLS_LOG" && fail "the same tag seen again should file nothing, got: $(cat "$GC_CALLS_LOG")"

# 4b. The pin moves to v1.3.1 (the T02 shape, PR #385). The pending proposals
#     for v1.2.3 and v1.3.1 are resolved through the proposal door with the
#     pin as proof; the one for v2.0.0 (beyond the pin) and the one Benjamin
#     already accepted are left alone; and v1.3.1 published upstream is no
#     longer proposed, whatever the state file remembers.
pin_baseline v1.3.1 "feat: T02 - pin mattpocock/skills v1.3.1 (af-g6zfh0) (#385)"
PIN_SHA=$(git -C "$PIN_REPO" log -1 --format=%h -- docs/UPSTREAM_SKILLS.md)
cat >"$PROPOSALS_FILE" <<JSON
[{"id":"af-old","status":"open","labels":["proposal"],"metadata":{"gc.proposal_state":"ouverte","gc.proposal_quoi":"mattpocock/skills a publié v1.2.3, au-delà de la référence Method Baseline"}},
 {"id":"af-pin","status":"open","labels":["proposal"],"metadata":{"gc.proposal_state":"ouverte","gc.proposal_quoi":"mattpocock/skills a publié v1.3.1, au-delà de la référence Method Baseline"}},
 {"id":"af-next","status":"open","labels":["proposal"],"metadata":{"gc.proposal_state":"ouverte","gc.proposal_quoi":"mattpocock/skills a publié v2.0.0, au-delà de la référence Method Baseline"}},
 {"id":"af-acc","status":"open","labels":["proposal"],"metadata":{"gc.proposal_state":"a_planifier","gc.proposal_quoi":"mattpocock/skills a publié v1.1.0, au-delà de la référence Method Baseline"}},
 {"id":"af-other","status":"open","labels":["proposal"],"metadata":{"gc.proposal_state":"ouverte","gc.proposal_quoi":"Corriger gc.work_branch périmé"}}]
JSON
PIN_TAG_FILE="$TMP/tags-v131.txt"
printf 'abc123def456\trefs/tags/v1.2.3\nabc123def457\trefs/tags/v1.3.1\n' >"$PIN_TAG_FILE"
: >"$GC_CALLS_LOG"
OUT=$(UPSTREAM_SKILLS_CHECK_NOW=3000 run_check "$PIN_TAG_FILE") || fail "check at the pin should exit 0: $OUT"
grep -q -- '--- call: bd create' "$GC_CALLS_LOG" && fail "a tag at the pin must not be proposed, got: $(cat "$GC_CALLS_LOG")"
for id in af-old af-pin; do
  grep -q -- "--- call: bd update $id .*gc.proposal_state=resolue" "$GC_CALLS_LOG" \
    || fail "expected $id to be resolved against the pin, got: $(cat "$GC_CALLS_LOG")"
  grep -q -- "--- call: bd update $id .*gc.proposal_resolved_by=pin v1.3.1 dans UPSTREAM_SKILLS.md, PR #385, commit $PIN_SHA" "$GC_CALLS_LOG" \
    || fail "expected $id's proof to name the pin, PR #385 and commit $PIN_SHA, got: $(cat "$GC_CALLS_LOG")"
done
for id in af-next af-acc af-other; do
  grep -q -- "--- call: bd update $id" "$GC_CALLS_LOG" && fail "$id must not be touched, got: $(cat "$GC_CALLS_LOG")"
done
printf '%s\n' "$OUT" | grep -q 'v1.3.1 is at or before the pinned baseline tag v1.3.1' || fail "expected the order to say the tag is at the pin, got: $OUT"

# 4c. A tag beyond the new pin is still proposed exactly once.
NEXT_TAG_FILE="$TMP/tags-v140.txt"
printf 'abc123def457\trefs/tags/v1.3.1\nabc123def458\trefs/tags/v1.4.0\n' >"$NEXT_TAG_FILE"
: >"$GC_CALLS_LOG"
UPSTREAM_SKILLS_CHECK_NOW=4000 run_check "$NEXT_TAG_FILE" >/dev/null || fail "check beyond the pin should exit 0"
grep -q -- '--- call: bd create.*v1.4.0' "$GC_CALLS_LOG" || fail "a tag beyond the pin must be proposed, got: $(cat "$GC_CALLS_LOG")"
[ "$(jq -r '.last_flagged_tag' "$STATE_FILE")" = "v1.4.0" ] || fail "expected state to record v1.4.0, got $(cat "$STATE_FILE")"

# 5. Whatever the tag list, the order never changes a skill file, pin,
#    branch, or config in the repo it runs from.
AFTER_STATUS=$(cd "$ROOT" && git status --porcelain -- skills docs/UPSTREAM_SKILLS.md config .claude city.toml)
[ "$BEFORE_STATUS" = "$AFTER_STATUS" ] || fail "upstream-skills-check must change no skill file, pin, or config in $ROOT"
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

echo "PASS: upstream-skills-check files exactly one proposal on a new tag, none on a repeat, absent or already-pinned tag, resolves pending proposals at or before the pin, and changes nothing"
