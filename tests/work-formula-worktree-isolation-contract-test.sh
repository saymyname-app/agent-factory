#!/usr/bin/env bash
# af-jz4zb (P08): every work formula allowed on a rig must isolate its work
# in a git worktree, never the rig checkout or the live root -- af-ogg8z /
# af-09hxz's incident class (a worker committing straight into the live
# root or a product rig's protected branch, no branch, no PR). This is a
# static contract test over formula prose, not a behavioral one: it proves
# each formula's workspace-setup step actually calls a worktree-isolation
# mechanism, rather than proceeding to implement/commit in whatever
# directory it was dispatched into.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

resolve_step_text() {
  local formula="$1" step_id="$2"
  python3 - "$formula" "$step_id" <<'PY'
import re
import sys

formula_path, step_id = sys.argv[1], sys.argv[2]
text = open(formula_path, encoding="utf-8").read()

# Each [[steps]] table runs until the next [[steps]] or a new top-level
# table/array-of-tables header at column 0.
blocks = re.split(r'\n(?=\[\[steps\]\]|\[[A-Za-z])', text)
for block in blocks:
    if not block.lstrip().startswith('[[steps]]'):
        continue
    id_match = re.search(r'^id\s*=\s*"([^"]+)"', block, re.MULTILINE)
    if not id_match or id_match.group(1) != step_id:
        continue
    desc_match = re.search(r'description\s*=\s*"""(.*?)"""', block, re.DOTALL)
    if desc_match:
        print(desc_match.group(1))
        raise SystemExit(0)
    file_match = re.search(r'description_file\s*=\s*"([^"]+)"', block)
    if file_match:
        import os
        asset = os.path.normpath(os.path.join(os.path.dirname(formula_path), file_match.group(1)))
        print(open(asset, encoding="utf-8").read())
        raise SystemExit(0)
    print("")
    raise SystemExit(0)

print("")
PY
}

assert_isolates() {
  local formula="$1" step_id="$2" needle="$3"
  local text
  text=$(resolve_step_text "$formula" "$step_id")
  [ -n "$text" ] || fail "$(basename "$formula") step '$step_id' has no resolvable description text"
  printf '%s' "$text" | grep -Fq "$needle" \
    || fail "$(basename "$formula") step '$step_id' does not call '$needle' -- it can run with the rig checkout or live root as its work dir"
}

# mol-do-work: workspace-setup calls the shared, locked, fail-loud
# do-work-workspace adapter unconditionally.
assert_isolates "$ROOT/formulas/mol-do-work.formula.toml" "workspace-setup" \
  "bin/factory-do-work-workspace\" enter"

# mol-scoped-work: workspace-setup always creates its own worktree before
# any implement step is eligible (needed by "body"'s scope).
assert_isolates "$ROOT/formulas/mol-scoped-work.formula.toml" "workspace-setup" \
  "git worktree add"

# mol-polecat-commit: workspace-setup always creates (or resumes) an
# isolated worktree/branch before implementation begins.
assert_isolates "$ROOT/formulas/mol-polecat-commit.formula.toml" "workspace-setup" \
  "git worktree add"

# build-basic (same-session drain): prepare-shared-worktree calls the
# shared-drain adapter, which is the only thing allowed to set work_dir for
# the convoy's source anchors.
assert_isolates "$ROOT/formulas/build-basic.formula.toml" "prepare-shared-worktree" \
  "bin/factory-shared-drain-workspace\" prepare"

# The do-work-workspace adapter itself must actually fail loudly if it
# cannot give back an isolated worktree with a working safety net, not
# silently proceed as if isolation had happened.
grep -q 'could not install the auto-push hook' "$ROOT/bin/factory-do-work-workspace" \
  || fail "bin/factory-do-work-workspace no longer fails loudly on a hook-install failure"
grep -q 'with_repo_lock' "$ROOT/bin/factory-do-work-workspace" \
  || fail "bin/factory-do-work-workspace no longer takes an exclusive per-repository lock in enter"

echo "PASS: mol-do-work, mol-scoped-work, mol-polecat-commit, and build-basic (same-session) all isolate work in a worktree before implementation, never the rig checkout or live root"
