#!/usr/bin/env bash
#
# pr-autopilot must never merge a PR that adds or retires a project
# descriptor (config/project-descriptors/) by itself (Spec af-oohx2x .101,
# af-1epwsn/T02): by exception to the "factory maintenance" auto-merge
# authorization, that PR is held, labelled and explained once on the PR --
# same pattern as the existing reversibility hold (ADR-0019) -- and only
# Benjamin merges it. A PR that only modifies an existing descriptor, or
# touches no descriptor at all, follows the normal green-PR path unchanged.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory/rigs/example-backend" "$TMP/factory/rigs/example-frontend" "$TMP/bin"
: > "$TMP/gh.log"; : > "$TMP/gc.log"

# Four green open PRs against the same rig:
#  1: adds a new project descriptor
#  2: removes an existing project descriptor
#  3: only modifies an existing project descriptor
#  4: touches no project descriptor at all
cat > "$TMP/backend-open.json" <<'JSON'
[
 {"number":1,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"conclusion":"SUCCESS"}],"headRefOid":"aaa1","labels":[]},
 {"number":2,"isDraft":false,"autoMergeRequest":{"mergeMethod":"SQUASH"},"mergeStateStatus":"CLEAN","statusCheckRollup":[{"conclusion":"SUCCESS"}],"headRefOid":"bbb1","labels":[]},
 {"number":3,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"conclusion":"SUCCESS"}],"headRefOid":"ccc1","labels":[]},
 {"number":4,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"conclusion":"SUCCESS"}],"headRefOid":"ddd1","labels":[]}
]
JSON

# These model the already-jq-filtered TSV output real `gh api ... --jq` would
# print for repos/{repo}/pulls/{num}/files (filename<TAB>status); the stub gh
# below just cats them, since it does not run jq itself.
printf 'config/project-descriptors/newproj.toml\tadded\n' > "$TMP/files-1.tsv"
printf 'config/project-descriptors/oldproj.toml\tremoved\n' > "$TMP/files-2.tsv"
printf 'config/project-descriptors/existing.toml\tmodified\n' > "$TMP/files-3.tsv"
printf 'bin/some-tool\tmodified\n' > "$TMP/files-4.tsv"

cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
# The host's gh 2.45 fails every "pr edit" on GitHub's retired Projects
# (classic) field -- the real cause of PR #356's repeated explanation.
if [[ \$1 == pr && \$2 == edit ]]; then
  echo 'GraphQL: Projects (classic) is being deprecated (repository.pullRequest.projectCards)' >&2; exit 1
fi
if [[ \$1 == pr && \$2 == comment ]]; then
  prev=; for a in "\$@"; do [[ \$prev == --body-file ]] && cat "\$a" >> "$TMP/comments-\$3.md"; prev=\$a; done
  exit 0
fi
if [[ \$1 == pr && \$2 == view && "\$*" == *"--json comments"* ]]; then cat "$TMP/comments-\$3.md" 2>/dev/null; exit 0; fi
if [[ \$1 == api && \$3 == POST && -e "$TMP/label-fails-once" ]]; then
  rm -f "$TMP/label-fails-once"; echo 'HTTP 502: Bad Gateway' >&2; exit 1
fi
if [[ \$1 == pr && \$2 == list ]]; then
  if [[ "\$*" == *"--state open"* && "\$*" == *"example-backend"* ]]; then cat "$TMP/backend-open.json"
  else echo '[]'; fi
  exit 0
fi
if [[ \$1 == pr && \$2 == view ]]; then echo '["OPEN","false"]' | jq -r '@tsv'; exit 0; fi
if [[ \$1 == api ]]; then
  for a in "\$@"; do
    if [[ "\$a" == repos/*/pulls/*/files ]]; then
      num=\$(echo "\$a" | sed -E 's#.*/pulls/([0-9]+)/files#\1#')
      cat "$TMP/files-\$num.tsv" 2>/dev/null
      exit 0
    fi
  done
  exit 0
fi
exit 0
STUB
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gc.log"
if [[ \$1 == bd && \$2 == list ]]; then echo '[]'; exit 0; fi
if [[ \$1 == bd && \$2 == show ]]; then echo '[]'; exit 0; fi
exit 0
STUB
chmod +x "$TMP/bin/"*
export PATH="$TMP/bin:$PATH"
export FACTORY_ROOT="$TMP/factory"
export REVERSIBILITY_CHECK_BIN="$TMP/bin/true-check"
cat > "$TMP/bin/true-check" <<'STUB'
#!/usr/bin/env bash
exit 0
STUB
chmod +x "$TMP/bin/true-check"
export PROTECTED_RIGS_CONFIG_DIR="$REPO_ROOT/tests/fixtures/pr-autopilot-projects"
export GC_OPERATOR_NAME=operator-1
export REVERSIBILITY_CACHE="$TMP/factory/.gc/rev-cache.tsv"
export PR_AUTOPILOT_NOW_EPOCH
PR_AUTOPILOT_NOW_EPOCH=$(date -u -d '2026-09-30T16:00:00Z' +%s)

pilot() { "$AUTOPILOT" "$@" 2>&1 || true; }

# Only the backend rig matters for this test; point frontend's repo lookup at
# an always-empty PR list by leaving it unconfigured (fixtures include it,
# but no frontend-open.json exists, so `gh pr list` for it returns []).

# --- dry run first: nothing may change ---------------------------------------------
out=$(pilot --dry-run)
grep -q "PR #1: HELD -> project-declaration-needs-benjamin" <<<"$out" || { echo "$out" >&2; fail "dry-run did not report the hold for the added descriptor"; }
grep -q "PR #2: HELD -> project-declaration-needs-benjamin" <<<"$out" || { echo "$out" >&2; fail "dry-run did not report the hold for the removed descriptor"; }
grep -qE '^(pr (merge|comment|edit)|label create|api -X)' "$TMP/gh.log" && fail "--dry-run mutated GitHub"

# --- the real pass -------------------------------------------------------------------
: > "$TMP/gh.log"
out=$(pilot)

# 1: adds a descriptor -> held, labelled, explained once, never merged
grep -q "^pr merge 1 " "$TMP/gh.log" && fail "PR adding a project descriptor was merged/armed"
grep -q "^label create project-declaration-needs-benjamin" "$TMP/gh.log" || fail "hold label not created for the added descriptor"
grep -q "^pr comment 1 " "$TMP/gh.log" || fail "hold not explained on PR 1 (added descriptor)"
grep -q "^api -X POST repos/[^ ]*/issues/1/labels -f labels\[\]=project-declaration-needs-benjamin" "$TMP/gh.log" || fail "PR 1 not labelled"

# 2: removes a descriptor, was already armed -> disarmed, labelled, explained, never merged
grep -q "^pr merge 2 --repo example-corp/example-backend --disable-auto" "$TMP/gh.log" || fail "already-armed PR removing a descriptor was not disarmed"
grep -q "^pr merge 2 --repo example-corp/example-backend --auto" "$TMP/gh.log" && fail "PR removing a project descriptor was (re)armed"
grep -q "^pr comment 2 " "$TMP/gh.log" || fail "hold not explained on PR 2 (removed descriptor)"
grep -q "^api -X POST repos/[^ ]*/issues/2/labels -f labels\[\]=project-declaration-needs-benjamin" "$TMP/gh.log" || fail "PR 2 not labelled"

# 3: only modifies an existing descriptor -> normal path, armed
grep -q "^pr merge 3 --repo example-corp/example-backend --auto --squash" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR only modifying an existing descriptor was not armed"; }

# 4: touches no descriptor at all -> normal path, armed
grep -q "^pr merge 4 --repo example-corp/example-backend --auto --squash" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR touching no project descriptor was not armed"; }

grep -q "held=2" <<<"$out" || { echo "$out" >&2; fail "summary does not count the two project-declaration holds"; }

# --- second pass: label already present -> no second comment, no second label create --------
jq '(.[]|select(.number==1)).labels=[{"name":"project-declaration-needs-benjamin"}]
  | (.[]|select(.number==2)).labels=[{"name":"project-declaration-needs-benjamin"}]
  | (.[]|select(.number==2)).autoMergeRequest=null' \
  "$TMP/backend-open.json" > "$TMP/next.json" && mv "$TMP/next.json" "$TMP/backend-open.json"
: > "$TMP/gh.log"
pilot >/dev/null
grep -q "^pr comment 1 " "$TMP/gh.log" && fail "PR 1's hold was explained twice"
grep -q "^pr comment 2 " "$TMP/gh.log" && fail "PR 2's hold was explained twice"
grep -q "^pr merge 1 " "$TMP/gh.log" && fail "held PR 1 was merged on a later pass"
grep -q "^pr merge 2 .*--auto" "$TMP/gh.log" && fail "held PR 2 was rearmed on a later pass"

# --- the descriptor change is reverted: released back to the normal path --------------------
printf 'config/project-descriptors/newproj.toml\tmodified\n' > "$TMP/files-1.tsv"
: > "$TMP/gh.log"
out=$(pilot)
grep -q "^api -X DELETE repos/[^ ]*/issues/1/labels/project-declaration-needs-benjamin" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR 1 kept its hold label after the descriptor add was reverted"; }
grep -q "^pr merge 1 --repo example-corp/example-backend --auto --squash" "$TMP/gh.log" \
  || fail "PR 1 was not armed once it no longer added a descriptor"

# --- PR #356 regression: the label does not stick -> still explained once -----------
# A pass whose label call fails leaves the PR unlabelled; the next pass must
# find its own explanation (hidden marker) instead of posting it again.
printf 'config/project-descriptors/fifth.json\tadded\n' > "$TMP/files-5.tsv"
cat > "$TMP/backend-open.json" <<'JSON'
[{"number":5,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"conclusion":"SUCCESS"}],"headRefOid":"eee1","labels":[]}]
JSON
: > "$TMP/label-fails-once"
: > "$TMP/gh.log"
out=$(pilot)
grep -q "^pr comment 5 " "$TMP/gh.log" || { echo "$out" >&2; fail "PR 5's hold was not explained"; }
grep -q "could not add label 'project-declaration-needs-benjamin'" <<<"$out" \
  || { echo "$out" >&2; fail "a failed label call was not reported"; }
: > "$TMP/gh.log"
out=$(pilot)   # labels still [] on GitHub: the first label call failed
grep -q "^pr comment 5 " "$TMP/gh.log" && { echo "$out" >&2; fail "PR 5's hold was explained twice after a failed label call (PR #356)"; }
grep -q "^api -X POST repos/example-corp/example-backend/issues/5/labels -f labels\[\]=project-declaration-needs-benjamin" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR 5's label was not retried on the next pass"; }
[ "$(grep -c '<!-- pr-autopilot:project-declaration-needs-benjamin -->' "$TMP/comments-5.md")" = 1 ] \
  || fail "PR 5 does not carry exactly one explanation"
grep -q "^pr merge 5 .*--auto" "$TMP/gh.log" && fail "PR 5 was armed while its label was missing"

echo "OK pr-autopilot never merges a project descriptor add/remove by itself"
