#!/usr/bin/env bash
# Deterministic regression for af-5z6p7. The fixture has two dependent source
# anchors and exercises the repository adapter directly, while formula
# assertions lock Gas City's single-lane/fail-skip contract and prove the
# separate-drain graph is unchanged.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
HELPER="$ROOT/bin/factory-shared-drain-workspace"
FORMULA="$ROOT/formulas/build-basic.formula.toml"
FAKE_GC="$ROOT/tests/fixtures/shared-drain/fake-gc.py"
FAKE_GH="$ROOT/tests/fixtures/shared-drain/fake-gh.py"
TMP=$(mktemp -d)
RIG="$TMP/rig"
STATE="$TMP/state"
WORKTREE=""

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  status=$?
  trap - EXIT
  if [ -d "$RIG/.git" ]; then
    while IFS= read -r candidate; do
      [ "$candidate" = "$RIG" ] && continue
      git -C "$RIG" worktree remove --force "$candidate" >/dev/null 2>&1 || true
    done < <(git -C "$RIG" worktree list --porcelain 2>/dev/null | sed -n 's/^worktree //p')
  fi
  rm -rf -- "$TMP"
  exit "$status"
}
trap cleanup EXIT

for required in git jq python3; do
  command -v "$required" >/dev/null 2>&1 || fail "required command is unavailable: $required"
done
[ -x "$HELPER" ] || fail "$HELPER is not executable"

git init -q --bare "$TMP/origin.git"
git init -q "$RIG"
git -C "$RIG" config user.email test@example.invalid
git -C "$RIG" config user.name test
git -C "$RIG" config commit.gpgsign false
git -C "$RIG" remote add origin "$TMP/origin.git"
printf 'base\n' >"$RIG/base.txt"
git -C "$RIG" add base.txt
git -C "$RIG" commit -qm base
git -C "$RIG" branch -M dev
git -C "$RIG" push -q -u origin dev

mkdir -p "$STATE/beads"
jq -n --arg root "$RIG" '[{id:"test-root",status:"open",metadata:{"gc.work_dir":$root}}]' \
  >"$STATE/beads/test-root.json"
jq -n '[{id:"item-one",status:"open",metadata:{}}]' >"$STATE/beads/item-one.json"
jq -n '[{id:"item-two",status:"open",metadata:{},dependencies:[{id:"item-one",dependency_type:"blocks"}]}]' \
  >"$STATE/beads/item-two.json"
jq -n '{ok:true,convoy:{id:"test-convoy",status:"open"},children:[
  {id:"item-one",status:"open"},
  {id:"item-two",status:"open"}
]}' >"$STATE/convoy.json"

export FAKE_GC_STATE="$STATE"
export GC_BIN="$FAKE_GC"
export GH_BIN="$FAKE_GH"

# A source anchor that already owns another worktree is a hard ownership
# conflict. Preparation must fail before creating or overwriting anything.
"$FAKE_GC" bd update item-two --set-metadata "work_dir=$TMP/foreign-worktree" >/dev/null
if "$HELPER" prepare test-root test-convoy >/dev/null 2>&1; then
  fail "prepare overwrote a source anchor's existing worktree ownership"
fi
[ "$(git -C "$RIG" worktree list --porcelain | grep -c '^worktree ')" = 1 ] \
  || fail "ownership conflict created a partial shared worktree"
"$FAKE_GC" bd update item-two --unset-metadata work_dir >/dev/null

# 1. Preparation creates exactly one non-launcher worktree and publishes the
# same authoritative path to both dependent source anchors.
PREPARE_JSON=$("$HELPER" prepare test-root test-convoy)
WORKTREE=$(jq -r '.worktree' <<<"$PREPARE_JSON")
[ "$(jq -r '.status' <<<"$PREPARE_JSON")" = prepared ] || fail "prepare did not report prepared"
[ -d "$WORKTREE" ] || fail "shared worktree was not created"
[ "$WORKTREE" != "$RIG" ] || fail "launcher checkout was selected as implementation worktree"
[ "$(git -C "$RIG" worktree list --porcelain | grep -c '^worktree ')" = 2 ] \
  || fail "prepare did not create exactly one additional worktree"
for item in item-one item-two; do
  [ "$(jq -r '.[0].metadata.work_dir' "$STATE/beads/$item.json")" = "$WORKTREE" ] \
    || fail "$item does not resolve the shared worktree"
done

# 2. Simulate the single lane: item two begins only after item one's commit and
# therefore retains it in the same branch history.
git -C "$WORKTREE" config user.email test@example.invalid
git -C "$WORKTREE" config user.name test
git -C "$WORKTREE" config commit.gpgsign false
printf 'one\n' >"$WORKTREE/item-one.txt"
git -C "$WORKTREE" add item-one.txt
git -C "$WORKTREE" commit -qm 'item one'
ITEM_ONE_COMMIT=$(git -C "$WORKTREE" rev-parse HEAD)
[ -f "$WORKTREE/item-one.txt" ] || fail "item one output disappeared before item two"
printf 'two sees one\n' >"$WORKTREE/item-two.txt"
git -C "$WORKTREE" add item-two.txt
git -C "$WORKTREE" commit -qm 'item two'
ITEM_TWO_COMMIT=$(git -C "$WORKTREE" rev-parse HEAD)
git -C "$WORKTREE" merge-base --is-ancestor "$ITEM_ONE_COMMIT" "$ITEM_TWO_COMMIT" \
  || fail "item two commit did not retain item one's commit"

# 3. Lock the graph contract: a failure skips later rows, only one item lane is
# allowed, preparation gates the shared drain, and the separate drain is still
# the unmodified do-work lifecycle.
python3 - "$FORMULA" <<'PY'
import sys
import tomllib

with open(sys.argv[1], "rb") as handle:
    formula = tomllib.load(handle)
steps = {step["id"]: step for step in formula["steps"]}

prepare = steps["prepare-shared-worktree"]
shared = steps["implement-same-session"]
separate = steps["implement"]
cleanup = steps["cleanup-shared-worktree"]

assert prepare["needs"] == ["decompose"]
assert prepare["condition"] == "{{drain_policy}} == same-session"
assert shared["needs"] == ["prepare-shared-worktree"]
assert shared["drain"]["context"] == "shared"
assert shared["drain"]["on_item_failure"] == "skip_remaining"
assert shared["drain"]["member_access"] == "exclusive"
assert shared["drain"]["item"]["single_lane"] is True
assert separate["needs"] == ["decompose"]
assert separate["condition"] == "{{drain_policy}} == separate"
assert separate["drain"] == {
    "context": "separate",
    "formula": "do-work",
    "member_access": "exclusive",
}
assert cleanup["needs"] == ["build-pipeline"]
assert cleanup["metadata"]["gc.scope_role"] == "teardown"
print("ok: shared failure skips remaining items; separate drain unchanged")
PY

# 4. Publish twice. The branch contains both commits, but the adapter creates
# exactly one PR and records that same URL on every source anchor.
PUBLISH_JSON=$("$HELPER" publish test-root test-convoy true true)
[ "$(jq -r '.status' <<<"$PUBLISH_JSON")" = published ] || fail "publish did not report published"
"$HELPER" publish test-root test-convoy true true >/dev/null
[ "$(cat "$STATE/pr-create-count")" = 1 ] || fail "publish created more than one PR"
git --git-dir="$TMP/origin.git" show build-basic/test-root:item-one.txt >/dev/null \
  || fail "published branch lost item one"
git --git-dir="$TMP/origin.git" show build-basic/test-root:item-two.txt >/dev/null \
  || fail "published branch lost item two"
for item in item-one item-two; do
  [ "$(jq -r '.[0].metadata["gc.pr_url"]' "$STATE/beads/$item.json")" = 'https://example.invalid/pull/1' ] \
    || fail "$item did not receive the shared PR URL"
done

# 5. Successful teardown removes the registration before a later merged-branch
# cleanup and clears only metadata that still points to this shared path.
CLEANUP_JSON=$("$HELPER" cleanup test-root test-convoy)
[ "$(jq -r '.status' <<<"$CLEANUP_JSON")" = removed ] || fail "cleanup did not remove the worktree"
[ ! -e "$WORKTREE" ] || fail "shared worktree directory survived cleanup"
[ "$(git -C "$RIG" worktree list --porcelain | grep -c '^worktree ')" = 1 ] \
  || fail "shared worktree still pins the published branch"
for item in item-one item-two; do
  [ "$(jq -r '.[0].metadata.work_dir // empty' "$STATE/beads/$item.json")" = "" ] \
    || fail "$item retained stale work_dir metadata"
done

# Disabled publication remains a structured no-op, retains the local branch,
# and still allows teardown to release the clean worktree.
PREPARE_JSON=$("$HELPER" prepare test-root test-convoy)
NOOP_JSON=$("$HELPER" publish test-root test-convoy false false)
[ "$(jq -r '.status' <<<"$NOOP_JSON")" = noop ] || fail "disabled publish did not report noop"
"$HELPER" cleanup test-root test-convoy >/dev/null

# 6. A failed item may leave dirty recovery evidence. Teardown reports and
# preserves it rather than deleting work; core's graph contract above still
# guarantees later items are skipped.
PREPARE_JSON=$("$HELPER" prepare test-root test-convoy)
WORKTREE=$(jq -r '.worktree' <<<"$PREPARE_JSON")
printf 'recovery\n' >"$WORKTREE/uncommitted-recovery.txt"
CLEANUP_JSON=$("$HELPER" cleanup test-root test-convoy)
[ "$(jq -r '.status' <<<"$CLEANUP_JSON")" = preserved ] \
  || fail "dirty failure evidence was not preserved"
[ -f "$WORKTREE/uncommitted-recovery.txt" ] || fail "dirty recovery evidence was deleted"

echo "PASS: shared drain prepares one authoritative worktree, retains sequential commits, publishes one PR, skips after failure by graph contract, cleans safely, and leaves separate drain unchanged"
