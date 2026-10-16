#!/usr/bin/env bash
# ADR-0026 wiring: PR creation records waiting state; only deliver-close owns
# the merge+CI close transition.

set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

for formula in \
  "$ROOT/formulas/mol-do-work.formula.toml" \
  "$ROOT/formulas/mol-polecat-commit.formula.toml" \
  "$ROOT/formulas/mol-scoped-work.formula.toml"
do
  grep -q 'gc.delivery_contract=pr-ci-merged-v1' "$formula" \
    || fail "$(basename "$formula") does not mark PR-backed work"
  grep -q 'gc.delivery_status=waiting' "$formula" \
    || fail "$(basename "$formula") does not leave PR-backed work waiting"
  if grep -Fq 'gc bd close "$WORK_BEAD_ID"' "$formula"; then
    fail "$(basename "$formula") still closes the work bead at PR creation"
  fi
done

grep -q 'finalize_delivery .*required-workflow' "$ROOT/bin/pr-autopilot" \
  || grep -q -- '--required-workflow "$workflow"' "$ROOT/bin/pr-autopilot" \
  || fail "pr-autopilot does not route merged PRs through the required-CI door"

if grep -q -- '--set-metadata merge_result=merged' "$ROOT/bin/pr-autopilot"; then
  fail "pr-autopilot still writes merge completion around deliver-close"
fi

for field in merge_result=merged merged_sha= merged_target= gc.ci_run_id= gc.ci_head_sha= gc.ci_conclusion=success; do
  grep -q "$field" "$ROOT/bin/deliver-close" \
    || fail "deliver-close does not own structural field $field"
done

# af-hmqlf5: mol-do-work's push-and-pr block, run for real against a fake gc
# and a fake `factory-do-work-workspace finish`. When finish exits non-zero
# (other than 4) nothing was delivered and the worktree is still there: the
# block must write nothing on the work bead, or the re-run reads work_dir "."
# and does nothing.
TMP=$(mktemp -d "${TMPDIR:-/tmp}/delivery-formula-contract-test.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/root/bin"

python3 - "$ROOT/formulas/mol-do-work.formula.toml" > "$TMP/push-and-pr.sh" <<'PY'
import re
import sys

text = open(sys.argv[1], encoding="utf-8").read()
step = text.split('id = "push-and-pr"', 1)[1]
block = re.search(r'```bash\n(.*?)```', step, re.DOTALL).group(1)
print(block.replace("{{convoy_id}}", "cv-1"))
PY
grep -q 'factory-do-work-workspace" finish' "$TMP/push-and-pr.sh" \
  || fail "could not extract mol-do-work's push-and-pr block"

cat > "$TMP/bin/gc" <<'GC'
#!/usr/bin/env bash
case "$1 $2" in
  "convoy status") echo '{"children":[{"id":"wk-1"}]}' ;;
  "bd show") echo '[{"metadata":{"work_dir":"/wt/wk-1","gc.work_branch":"do-work/wk-1","gc.work_base_branch":"main"}}]' ;;
  "bd update") printf '%s\n' "$*" >> "$GC_UPDATE_LOG" ;;
esac
GC
cat > "$TMP/root/bin/factory-do-work-workspace" <<'WS'
#!/usr/bin/env bash
[ -n "${FAKE_PR_URL:-}" ] && echo "$FAKE_PR_URL"
exit "${FAKE_FINISH_RC:-0}"
WS
chmod +x "$TMP/bin/gc" "$TMP/root/bin/factory-do-work-workspace"

run_push_and_pr() {
  : > "$TMP/updates.log"
  PATH="$TMP/bin:$PATH" FACTORY_ROOT="$TMP/root" GC_UPDATE_LOG="$TMP/updates.log" \
    FAKE_FINISH_RC="$1" FAKE_PR_URL="${2:-}" bash "$TMP/push-and-pr.sh" >/dev/null 2>&1 || true
}

for rc in 1 3; do
  run_push_and_pr "$rc"
  [ ! -s "$TMP/updates.log" ] \
    || fail "push-and-pr wrote on the work bead after finish exited $rc: $(cat "$TMP/updates.log")"
done

run_push_and_pr 0 "https://example.invalid/pull/7"
grep -q 'gc.pr_url=https://example.invalid/pull/7' "$TMP/updates.log" \
  || fail "push-and-pr did not record the PR after a successful finish"
grep -q -- '--unset-metadata work_dir' "$TMP/updates.log" \
  || fail "push-and-pr kept work_dir after a successful finish"

run_push_and_pr 4
[ "$(cat "$TMP/updates.log")" = "bd update wk-1 --unset-metadata work_dir" ] \
  || fail "push-and-pr did not only drop work_dir after finish exited 4: $(cat "$TMP/updates.log")"

# af-m4np8z: a ticket resumed `unblocked` waited for a repair that landed on
# the integration branch, not on the ticket branch: its session brings the
# integration branch in, as `behind` does, or it meets the same defect again.
python3 - "$ROOT/formulas/mol-ticket-resume.formula.toml" <<'PY' || fail "mol-ticket-resume: an unblocked resume does not bring the integration branch into the ticket branch"
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
cause = re.search(r"^- `unblocked` (.*?)(?=^- `|\n\n)", text, re.MULTILINE | re.DOTALL)
sys.exit(0 if cause and 'git merge "origin/$INTEGRATION"' in cause.group(1) else 1)
PY

# af-o40g5r: a defect in the Factory's own tools or tests is fixed by
# maintenance on main; an author never turns it into a `repair` of the convoy.
for formula in mol-ticket-author mol-ticket-resume; do
  python3 - "$ROOT/formulas/$formula.formula.toml" <<'PY' \
    || fail "$formula does not send a Factory defect to operator_request, never a repair"
import re, sys
text = " ".join(open(sys.argv[1], encoding="utf-8").read().split())
rule = re.search(r"`operator_request`[^;]*?Factory's own tools or tests[^;]*?never a `repair`", text)
sys.exit(0 if rule else 1)
PY
done

echo "PASS: PR formulas wait and deliver-close owns merge+exact-head-CI completion"
