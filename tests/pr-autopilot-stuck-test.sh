#!/usr/bin/env bash
#
# pr-autopilot must not let a DIRTY, BLOCKED, or zero-check PR sit forever
# with one identical log line per pass (af-grln2 / audit finding D3). It acts
# directly on data the loop already fetched this tick (mergeStateStatus,
# statusCheckRollup, labels): the first stuck pass marks the PR with a label;
# a second stuck pass (the label already present) files one bead and comments
# once; a PR that recovers sheds the label.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory/rigs/saymyname-backend" "$TMP/factory/rigs/saymyname-frontend" "$TMP/bin"
: > "$TMP/gh.log"; : > "$TMP/gc.log"

# PR 1: DIRTY, no labels yet. PR 2: BLOCKED with the stuck label already
# present (simulating a prior pass). PR 3: NONE checks, healthy mergeState,
# also already labelled -- a recovered PR that must shed the label.
cat > "$TMP/open.json" <<'JSON'
[
 {"number":1,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"DIRTY","statusCheckRollup":[],"headRefOid":"aaa1","labels":[]},
 {"number":2,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BLOCKED","statusCheckRollup":[],"headRefOid":"bbb1","labels":[{"name":"autopilot-stuck"}]},
 {"number":3,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"conclusion":"SUCCESS"}],"headRefOid":"ccc1","labels":[{"name":"autopilot-stuck"}]}
]
JSON

cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ \$1 == pr && \$2 == list ]]; then
  if [[ "\$*" == *"Say-my-name-back"* ]]; then cat "$TMP/open.json"; else echo '[]'; fi
  exit 0
fi
if [[ \$1 == pr && \$2 == view ]]; then echo '["OPEN","false"]' | jq -r '@tsv'; exit 0; fi
exit 0
STUB
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gc.log"
[[ \$1 == bd && \$2 == list ]] && echo '[]'
exit 0
STUB
chmod +x "$TMP/bin/"*
export PATH="$TMP/bin:$PATH"
export FACTORY_ROOT="$TMP/factory"
export REVERSIBILITY_CHECK_BIN="$TMP/bin/gh"   # unused by these PRs (already CLEAN/no migration path hit)

pilot() { "$AUTOPILOT" "$@" 2>&1 || true; }

out=$(pilot)

# PR 1 (first stuck pass): labelled, not yet filed.
grep -q "^label create autopilot-stuck --repo saymyname-app/Say-my-name-back" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "stuck label was not created"; }
grep -q "^pr edit 1 --repo saymyname-app/Say-my-name-back --add-label autopilot-stuck" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #1 (DIRTY, first pass) was not marked stuck"; }
grep -q "^bd create \[autopilot\] PR #1" "$TMP/gc.log" && fail "PR #1 filed a bead on its first stuck pass"

# PR 2 (already labelled -> second stuck pass): files a bead, comments once.
grep -qF "bd create [autopilot] PR #2 stuck:" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "PR #2 (BLOCKED, already labelled) did not file a bead"; }
grep -q "^pr comment 2 --repo saymyname-app/Say-my-name-back" "$TMP/gh.log" \
  || fail "PR #2 was not commented on when filed"

# PR 3 (healthy again, was labelled) -> label removed, nothing filed.
grep -q "^pr edit 3 --repo saymyname-app/Say-my-name-back --remove-label autopilot-stuck" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #3 (recovered) did not shed the stuck label"; }
grep -qF "PR #3" "$TMP/gc.log" && fail "PR #3 (recovered) should never reach gc bd/mail"

# --- a second run on the same (still-labelled, still-stuck) PR #2 does not duplicate ---
: > "$TMP/gh.log"
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gc.log"
if [[ \$1 == bd && \$2 == list ]]; then
  echo '[{"id":"af-stuck2","title":"[autopilot] PR #2 stuck: blocked (a required check has not run or is pending); no status check ever reported"}]'
  exit 0
fi
exit 0
STUB
chmod +x "$TMP/bin/gc"
: > "$TMP/gc.log"
out=$(pilot)
grep -qF "bd create [autopilot] PR #2" "$TMP/gc.log" && fail "PR #2 was filed a second time"

echo "OK pr-autopilot flags PRs stuck across passes, once, and un-flags recovered ones"
