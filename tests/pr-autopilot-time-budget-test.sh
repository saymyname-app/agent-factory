#!/usr/bin/env bash
#
# pr-autopilot must finish inside its order's 120 s timeout with a report,
# even when a gh or gc call hangs.
#
# On 2026-09-29 23:58 and 2026-09-30 00:05 (Paris), with many PRs open during
# an overnight delivery, the order was killed at 120 s ("context deadline
# exceeded" -> order.failed): the old deadline was checked once per repo, and
# one repo's PR loop -- or one hung call inside it -- ran past it between two
# checks. Now every gh/gc call is bounded, no repo or PR starts once the run
# budget is spent (what was skipped is reported, exit 0, retried next tick),
# and a cut call is "unknown" -- never green, never a reason to arm, merge,
# flag or reject. Same shape as bin/factory-guard's run budget (PR #283).

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
. "$REPO_ROOT/tests/lib/sandbox.sh"
sandbox_init
TMP="$SANDBOX_DIR/t"
mkdir -p "$TMP/factory/rigs/example-backend" "$TMP/factory/rigs/example-frontend" "$TMP/bin"

fail() { printf 'FAIL: %s\n' "$1" >&2; [ -n "${out:-}" ] && printf '%s\n' "$out" >&2; exit 1; }

# The backend has one healthy PR: required check green, CLEAN, not armed yet.
cat > "$TMP/open-green.json" <<'JSON'
[{"number":7,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"name":"Maven verify","status":"COMPLETED","conclusion":"SUCCESS"}],"headRefOid":"abc7","labels":[]}]
JSON
# ... or one conflicted PR already marked stuck by an earlier pass (a second
# stuck pass files a bead unless one is already open).
cat > "$TMP/open-stuck.json" <<'JSON'
[{"number":8,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"DIRTY","statusCheckRollup":[{"name":"Maven verify","status":"COMPLETED","conclusion":"SUCCESS"}],"headRefOid":"abc8","labels":[{"name":"autopilot-stuck"}]}]
JSON

# gh/gc stubs: GH_HANG / GC_HANG name the one call that never answers (the
# saturated host). Anything the stubs were not written for is refused, as the
# real tools refuse an unknown subcommand.
cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [ -n "\${GH_HANG:-}" ] && [[ "\$*" == *"\$GH_HANG"* ]]; then exec sleep 120; fi
case "\$1 \$2" in
  "pr list")
    if [[ "\$*" == *"--state open"* && "\$*" == *"example-backend"* ]]; then cat "\$OPEN_JSON"; else echo '[]'; fi ;;
  "pr merge"|"pr edit"|"pr comment"|"label create") exit 0 ;;
  "pr view") exit 1 ;;
  "api repos/"*) exit 1 ;;   # ruleset unreadable (fine-grained PAT) -> "unknown", proceed on config
  *) echo "gh stub: unsupported: gh \$*" >&2; exit 1 ;;
esac
STUB
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gc.log"
if [ -n "\${GC_HANG:-}" ] && [[ "\$*" == *"\$GC_HANG"* ]]; then exec sleep 120; fi
case "\$1 \$2" in
  "bd list") echo '[]' ;;
  "bd create"|"bd update") exit 0 ;;
  *) echo "gc stub: unsupported: gc \$*" >&2; exit 1 ;;
esac
STUB
cat > "$TMP/bin/check" <<'STUB'
#!/usr/bin/env bash
exit 0   # every PR here is reversible
STUB
chmod +x "$TMP/bin/"*
export PATH="$TMP/bin:$PATH"
export FACTORY_ROOT="$TMP/factory"
export PROTECTED_RIGS_CONFIG_DIR="$REPO_ROOT/tests/fixtures/pr-autopilot-projects"
export REVERSIBILITY_CHECK_BIN="$TMP/bin/check"
export REVERSIBILITY_CACHE="$TMP/factory/.gc/rev-cache.tsv"
export PR_AUTOPILOT_RECONCILE_CACHE="$TMP/factory/.gc/reconciled.tsv"
export GC_OPERATOR_NAME=operator-1
export OPEN_JSON="$TMP/open-green.json"

pilot() {  # env... -> sets out, rc, elapsed
  : > "$TMP/gh.log"; : > "$TMP/gc.log"; rm -f "$REVERSIBILITY_CACHE"
  local start=$SECONDS
  rc=0; out=$(env "$@" "$AUTOPILOT" 2>&1) || rc=$?
  elapsed=$((SECONDS - start))
}

# --- (a) a hung `gh pr list` is cut; the rest is reported, not run; exit 0 ---
pilot GH_HANG="example-backend --state open" PR_AUTOPILOT_BUDGET_SECONDS=6 PR_AUTOPILOT_GRACE_SECONDS=0
[ "$rc" = 0 ] || fail "(a) exited $rc instead of reporting and exiting 0"
[ "$elapsed" -lt 20 ] || fail "(a) ran ${elapsed}s: the hung gh was not cut"
grep -q "open PRs unknown (a gh call timed out)" <<<"$out" || fail "(a) the unknown open-PR list was not reported"
grep -q "could not list open PRs" <<<"$out" && fail "(a) a timeout was reported as an error"
grep -q "^pr merge" "$TMP/gh.log" && fail "(a) something was armed while the PR list was unknown"
grep -q "example-corp/example-frontend and any repo after it — not checked (time budget exhausted" <<<"$out" \
  || fail "(a) the repo after the budget was not reported as not checked"
grep -q "example-frontend" "$TMP/gh.log" && fail "(a) a repo was started after the budget was spent"
grep -qE "^timing: [0-9]+s of a 6s budget — loadavg [0-9]" <<<"$out" || fail "(a) no timing/loadavg line"
grep -qE "repos: example-corp/example-backend [0-9]+s" <<<"$out" || fail "(a) per-repo duration missing"
grep -q "timed out: example-corp/example-backend: gh pr list" <<<"$out" || fail "(a) the cut call was not named"
grep -q "errors=0" <<<"$out" || fail "(a) skipped work was counted as an error"

# --- (b) a hung arm request is unknown: no re-read, no direct merge ----------
pilot GH_HANG="--auto" PR_AUTOPILOT_BUDGET_SECONDS=5 PR_AUTOPILOT_GRACE_SECONDS=0
[ "$rc" = 0 ] || fail "(b) exited $rc instead of reporting and exiting 0"
[ "$elapsed" -lt 20 ] || fail "(b) ran ${elapsed}s: the hung arm call was not cut"
grep -q "arm request timed out -- outcome unknown" <<<"$out" || fail "(b) the unknown arm outcome was not reported"
[ "$(grep -c '^pr merge 7' "$TMP/gh.log" || true)" = 1 ] || fail "(b) a timed-out arm was followed by another merge call"
grep -q "^pr view 7" "$TMP/gh.log" && fail "(b) a timed-out arm was treated as a refusal (state re-read)"
grep -q "armed=0" <<<"$out" || fail "(b) a timed-out arm was counted as armed"
grep -q "timed out: example-corp/example-backend: gh pr merge 7" <<<"$out" || fail "(b) the cut arm call was not named"

# --- (c) a hung open-bead read: the repo is skipped, no duplicate flag -------
pilot OPEN_JSON="$TMP/open-stuck.json" GC_HANG="--status open" PR_AUTOPILOT_BUDGET_SECONDS=4 PR_AUTOPILOT_GRACE_SECONDS=0
[ "$rc" = 0 ] || fail "(c) exited $rc instead of reporting and exiting 0"
grep -q "open beads unknown (gc bd list timed out)" <<<"$out" || fail "(c) the unknown bead list was not reported"
grep -q "^bd create" "$TMP/gc.log" && fail "(c) a stuck bead was filed while open beads were unknown"
grep -qE "^pr (comment|edit) 8" "$TMP/gh.log" && fail "(c) PR #8 was acted on while open beads were unknown"

# --- (d) a fast, healthy run: default budget, arms, no timing noise ----------
pilot
[ "$rc" = 0 ] || fail "(d) a healthy run exited $rc"
grep -q "armed=1 " <<<"$out" || fail "(d) the green PR was not armed"
grep -q "^pr merge 7 --repo example-corp/example-backend --auto --squash" "$TMP/gh.log" || fail "(d) arm call missing"
grep -q "^timing: " <<<"$out" && fail "(d) a fast run printed timing noise"
grep -q "not checked (time budget" <<<"$out" && fail "(d) a fast run skipped work"

# --- (e) an invalid budget is refused, not silently defaulted -----------------
pilot PR_AUTOPILOT_BUDGET_SECONDS=soon
[ "$rc" = 2 ] || fail "(e) an invalid budget exited $rc instead of 2"
[ -s "$TMP/gh.log" ] && fail "(e) an invalid budget still ran"

echo "OK pr-autopilot bounds every call and stays inside its time budget"
