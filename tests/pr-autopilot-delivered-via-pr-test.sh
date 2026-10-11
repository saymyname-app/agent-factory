#!/usr/bin/env bash
#
# P07 (af-87f9u): a repair sometimes lands on another ticket's branch instead
# of its own -- the fix and the other change are the same logical unit, so
# the worker commits it there instead of opening a branch/PR for the fixed
# ticket. formulas/mol-do-work.formula.toml (step 3c) has the worker record
# that with gc.delivered_via_pr=<PR number> on the fixed ticket, leaving it
# open with no branch/PR of its own. This drives pr-autopilot against stub
# gh/gc/deliver-close binaries and proves: a ticket naming a PR that has since
# merged closes with the merge SHA recorded, through the same deliver-close
# door as an ordinary branch-linked reconciliation; a ticket naming a PR that
# is still open, or one that closed without merging, stays open untouched.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory/rigs/saymyname-backend" "$TMP/factory/rigs/saymyname-frontend" "$TMP/bin"
: > "$TMP/gh.log"; : > "$TMP/gc.log"; : > "$TMP/deliver-close.log"

# PR 90: merged, hosts the fix for af-fixed-1 (delivered_via_pr=90) as well as
#   its own ticket af-owner (gc.work_branch=do-work/af-owner).
# PR 91: still OPEN (never merged) -- af-fixed-2 names it but must stay open.
cat > "$TMP/open.json" <<'JSON'
[
 {"number":91,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[],"headRefOid":"sha91a","labels":[]}
]
JSON
cat > "$TMP/merged.json" <<'JSON'
[
 {"number":90,"headRefName":"do-work/af-owner","mergeCommit":{"oid":"eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"},"mergedAt":"2026-09-24T00:40:00Z"}
]
JSON

cat > "$TMP/all-beads.json" <<'JSON'
[
 {"id":"af-owner","status":"in_progress","metadata":{"gc.work_branch":"do-work/af-owner"}},
 {"id":"af-fixed-1","status":"in_progress","metadata":{"gc.delivered_via_pr":"90","gc.work_branch":"do-work/af-fixed-1"}},
 {"id":"af-fixed-2","status":"in_progress","metadata":{"gc.delivered_via_pr":"91"}},
 {"id":"af-fixed-closed","status":"closed","metadata":{"gc.delivered_via_pr":"90"}}
]
JSON

cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ "\$1" == pr && "\$2" == list ]]; then
  if [[ "\$*" != *"Say-my-name-back"* ]]; then echo '[]'; exit 0; fi
  if [[ "\$*" == *"--state open"* ]]; then cat "$TMP/open.json";
  elif [[ "\$*" == *"--state merged"* ]]; then cat "$TMP/merged.json";
  else echo '[]'; fi
  exit 0
fi
if [[ "\$1" == pr && "\$2" == view ]]; then echo '["OPEN","false"]' | jq -r '@tsv'; exit 0; fi
exit 0
STUB
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gc.log"
if [[ "\$1" == bd && "\$2" == list && "\$*" == *"--status open"* ]]; then echo '[]'; exit 0; fi
if [[ "\$1" == bd && "\$2" == list && "\$*" == *"--all"* ]]; then cat "$TMP/all-beads.json"; exit 0; fi
if [[ "\$1" == bd && "\$2" == show ]]; then
  case " \$* " in
    *" af-owner "*) echo '[{"id":"af-owner","status":"in_progress"}]' ;;
    *) echo '[]' ;;
  esac
  exit 0
fi
if [[ "\$1" == mail ]]; then exit 0; fi
exit 0
STUB
cat > "$TMP/bin/deliver-close" <<STUB
#!/usr/bin/env bash
set -Eeuo pipefail
echo "\$*" >> "$TMP/deliver-close.log"
bead=\$1
gc bd update "\$bead" --set-metadata merge_result=merged --set-metadata gc.merge_commit="eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" --status=closed
STUB
chmod +x "$TMP/bin/"*
export PATH="$TMP/bin:$PATH"
export FACTORY_ROOT="$TMP/factory"
export GC_PR_AUTHORS=example-operator
export REVERSIBILITY_CHECK_BIN="$TMP/bin/gh"
export DELIVER_CLOSE_BIN="$TMP/bin/deliver-close"
export GC_BIN="$TMP/bin/gc"

pilot() { "$AUTOPILOT" "$@" 2>&1 || true; }
out=$(pilot)

# af-fixed-1 named merged PR #90 (not its own branch) -- deliver-close runs
# for it with the merge SHA, and the bead closes.
grep -q "^af-fixed-1 --repo saymyname-app/Say-my-name-back --pr 90 " "$TMP/deliver-close.log" \
  || { echo "$out" >&2; fail "af-fixed-1 (delivered_via_pr=90) was not reconciled through deliver-close"; }
grep -q "^bd update af-fixed-1 .*gc.merge_commit=eeeeeeee.*--status=closed$" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "af-fixed-1 was not closed with the merge SHA recorded"; }

# af-owner (the PR's own branch-linked ticket) is unaffected by the new path
# -- still reconciled exactly once, by the pre-existing branch-keyed loop.
[ "$(grep -c '^af-owner --repo' "$TMP/deliver-close.log")" = "1" ] \
  || { echo "$out" >&2; fail "af-owner (branch-linked owner) was reconciled zero or more than once"; }

# af-fixed-2 named PR #91, which is still open (never merged) -- it must never
# be touched.
grep -qF "af-fixed-2" "$TMP/deliver-close.log" \
  && { echo "$out" >&2; fail "af-fixed-2 (delivered_via_pr=91, unmerged) was reconciled -- it must stay open"; }
grep -qF "af-fixed-2" "$TMP/gc.log" \
  && { echo "$out" >&2; fail "af-fixed-2 (delivered_via_pr=91, unmerged) was touched at all"; }

# af-fixed-closed already closed -- never re-processed even though it also
# names the now-merged PR #90.
grep -qF "af-fixed-closed" "$TMP/deliver-close.log" \
  && { echo "$out" >&2; fail "af-fixed-closed (already closed) was reconciled again"; }

echo "OK pr-autopilot closes a ticket naming a merged delivered_via_pr PR with the merge SHA, and leaves one naming an unmerged PR open"
