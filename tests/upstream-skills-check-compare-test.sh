#!/usr/bin/env bash
# D01 T02 (Spec af-wf4w5r user story 74, AR-008): bin/upstream-skills-check
# compare proves the vendored skills/ directory is byte-identical to the
# pinned mattpocock/skills tag, names the offending file on any drift, and
# refuses without an Adaptation Register entry for the pinned tag. This is
# the mechanism that makes a PR touching a vendored skill red in CI.
set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
CLI="$ROOT/bin/upstream-skills-check"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

command -v git >/dev/null 2>&1 || fail "required command is unavailable: git"

TMP=$(mktemp -d /tmp/af-upstream-skills-check-compare.XXXXXX)
trap 'rm -rf -- "$TMP"' EXIT

# A local checkout standing in for the pinned tag's upstream content, so this
# test never depends on network access or the real mattpocock/skills repo
# being reachable. Built by copying the repo's own vendored skills/ -- since
# the whole point of this ticket is that the two are identical today.
REF_DIR="$TMP/ref"
mkdir -p "$REF_DIR"
cp -r "$ROOT/skills" "$REF_DIR/skills"

AR_FILE="$TMP/adaptation-register.md"
cp "$ROOT/docs/ADAPTATION_REGISTER.md" "$AR_FILE"

run_compare() {
  local skills_dir="$1"; shift
  UPSTREAM_SKILLS_CHECK_REF_DIR="$REF_DIR" \
    UPSTREAM_SKILLS_CHECK_LOCAL_SKILLS_DIR="$skills_dir" \
    UPSTREAM_SKILLS_CHECK_ADAPTATION_REGISTER_FILE="$AR_FILE" \
    UPSTREAM_SKILLS_CHECK_BASELINE_FILE="$ROOT/docs/UPSTREAM_SKILLS.md" \
    "$CLI" compare "$@"
}

# 1. Intact copy: exit 0, names the pinned tag.
OUT=$(run_compare "$ROOT/skills" 2>&1) || fail "compare should exit 0 on an intact copy, got: $OUT"
printf '%s\n' "$OUT" | grep -q 'v1.3.1' || fail "compare's PASS output does not name the pinned tag, got: $OUT"

# 2. One byte changed in a vendored skill file: exit non-zero, names the file.
MOD_DIR="$TMP/mod-byte"
cp -r "$ROOT/skills" "$MOD_DIR"
TARGET_FILE="$MOD_DIR/engineering/tdd/SKILL.md"
[ -f "$TARGET_FILE" ] || fail "fixture assumption broken: $TARGET_FILE does not exist"
printf 'x' >>"$TARGET_FILE"
OUT=$(run_compare "$MOD_DIR" 2>&1) && fail "compare should exit non-zero on a byte-modified file"
printf '%s\n' "$OUT" | grep -q 'skills/engineering/tdd/SKILL.md' \
  || fail "compare did not name the modified file, got: $OUT"

# 3. A file added to a vendored skill directory: exit non-zero, names the file.
ADD_DIR="$TMP/add-file"
cp -r "$ROOT/skills" "$ADD_DIR"
echo "unexpected" >"$ADD_DIR/engineering/tdd/EXTRA-NOT-UPSTREAM.md"
OUT=$(run_compare "$ADD_DIR" 2>&1) && fail "compare should exit non-zero on an added file"
printf '%s\n' "$OUT" | grep -q 'skills/engineering/tdd/EXTRA-NOT-UPSTREAM.md' \
  || fail "compare did not name the added file, got: $OUT"

# 4. A file removed from a vendored skill directory: exit non-zero, names the file.
RM_DIR="$TMP/rm-file"
cp -r "$ROOT/skills" "$RM_DIR"
RM_TARGET="$RM_DIR/engineering/tdd/SKILL.md"
[ -f "$RM_TARGET" ] || fail "fixture assumption broken: $RM_TARGET does not exist"
rm -f "$RM_TARGET"
OUT=$(run_compare "$RM_DIR" 2>&1) && fail "compare should exit non-zero on a removed file"
printf '%s\n' "$OUT" | grep -q 'skills/engineering/tdd/SKILL.md' \
  || fail "compare did not name the removed file, got: $OUT"

# 5. Without an Adaptation Register entry naming the pinned tag: exit non-zero.
EMPTY_AR="$TMP/empty-adaptation-register.md"
echo "# Adaptation Register" >"$EMPTY_AR"
OUT=$(UPSTREAM_SKILLS_CHECK_REF_DIR="$REF_DIR" \
  UPSTREAM_SKILLS_CHECK_LOCAL_SKILLS_DIR="$ROOT/skills" \
  UPSTREAM_SKILLS_CHECK_ADAPTATION_REGISTER_FILE="$EMPTY_AR" \
  UPSTREAM_SKILLS_CHECK_BASELINE_FILE="$ROOT/docs/UPSTREAM_SKILLS.md" \
  "$CLI" compare 2>&1) && fail "compare should refuse without an Adaptation Register entry for the pinned tag"
printf '%s\n' "$OUT" | grep -qi 'adaptation register\|AR-NNN' \
  || fail "compare's refusal does not mention the missing Adaptation Register entry, got: $OUT"

# 6. The real Adaptation Register in this repo does carry the required entry,
#    and the real pin file does name a tag -- otherwise 1-5 above would be
#    testing a fixture that could never pass against the live docs.
grep -qE 'AR-[0-9]{3}.*v1\.3\.1' "$ROOT/docs/ADAPTATION_REGISTER.md" \
  || fail "docs/ADAPTATION_REGISTER.md has no AR-NNN entry naming v1.3.1"

# 7. resolving-merge-conflicts is no longer distributed.
[ -d "$ROOT/skills/engineering/resolving-merge-conflicts" ] \
  && fail "skills/engineering/resolving-merge-conflicts is still distributed"

# 8. /wayfinder, /to-spec and /to-tickets remain reserved to Benjamin: their
#    vendored SKILL.md disables model invocation, and their agents/openai.yaml
#    disables implicit invocation on Codex (docs/agents/issue-tracker.md).
for skill in wayfinder to-spec to-tickets; do
  skill_md="$ROOT/skills/engineering/$skill/SKILL.md"
  [ -f "$skill_md" ] || fail "missing vendored skill: $skill_md"
  grep -q 'disable-model-invocation: true' "$skill_md" \
    || fail "$skill_md does not disable model invocation -- an agent call would not be refused"

  openai_yaml="$ROOT/skills/engineering/$skill/agents/openai.yaml"
  [ -f "$openai_yaml" ] || fail "missing $openai_yaml"
  grep -q 'allow_implicit_invocation: false' "$openai_yaml" \
    || fail "$openai_yaml does not disable implicit invocation"
done

# 9. The real thing: no REF_DIR override, so this clones the actual pinned
#    tag from mattpocock/skills over the network -- the same path CI runs on
#    every PR. Network-dependent by design (docs/UPSTREAM_SKILLS.md); a
#    runner with no outbound access fails here, not silently.
if OUT=$("$CLI" compare 2>&1); then
  printf '%s\n' "$OUT" | grep -q 'v1.3.1' \
    || fail "live compare against mattpocock/skills passed but did not name v1.3.1, got: $OUT"
else
  fail "live compare against the real mattpocock/skills v1.3.1 failed -- vendored skills/ has drifted or the network is unreachable: $OUT"
fi

printf 'PASS: upstream-skills-check compare proves the vendored copy, refuses without an Adaptation Register entry, and the human-only skills stay reserved\n'
