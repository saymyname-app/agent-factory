#!/usr/bin/env bash
#
# pr-autopilot must leave an outsider's pull request alone (af-996mmd). Once a
# repository is public anyone can open a pull request, and the workflow that
# runs for it is the pull request's own: a stranger can make the required
# check green. So only a pull request opened from a branch of the repository
# itself, by one of the operator's own GitHub accounts
# (config/operator.toml, `github_logins`), is armed, merged, retried,
# labelled or turned into a bead. An empty list arms nothing.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory/rigs/example-backend" "$TMP/factory/rigs/example-frontend" "$TMP/bin"
: > "$TMP/gh.log"; : > "$TMP/gc.log"

# Six open pull requests against the same rig:
#  1: branch of the repository, author on the list, green      -> armed
#  2: fork, author on the list, green                          -> left alone
#  3: branch of the repository, author not on the list, green  -> left alone
#  4: neither field reported, green                            -> left alone
#  5: fork of a stranger, required check red, labelled stuck   -> left alone
#  6: branch of the repository, second account of the list     -> armed
cat > "$TMP/backend-open.json" <<'JSON'
[
 {"number":1,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"conclusion":"SUCCESS"}],"headRefOid":"aaa1","labels":[]},
 {"number":2,"isCrossRepository":true,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"conclusion":"SUCCESS"}],"headRefOid":"bbb1","labels":[]},
 {"number":3,"isCrossRepository":false,"author":{"login":"a-stranger"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"conclusion":"SUCCESS"}],"headRefOid":"ccc1","labels":[]},
 {"number":4,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"conclusion":"SUCCESS"}],"headRefOid":"ddd1","labels":[]},
 {"number":5,"isCrossRepository":true,"author":{"login":"a-stranger"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BLOCKED","statusCheckRollup":[{"conclusion":"FAILURE"}],"headRefOid":"eee1","labels":[{"name":"autopilot-stuck"}]},
 {"number":6,"isCrossRepository":false,"author":{"login":"second-account"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"CLEAN","statusCheckRollup":[{"conclusion":"SUCCESS"}],"headRefOid":"fff1","labels":[]}
]
JSON

cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ \$1 == pr && \$2 == list ]]; then
  if [[ "\$*" == *"--state open"* && "\$*" == *"example-backend"* ]]; then cat "$TMP/backend-open.json"
  else echo '[]'; fi
  exit 0
fi
if [[ \$1 == pr && \$2 == view ]] && [[ "\$*" == *"--json state,autoMergeRequest,mergeStateStatus,statusCheckRollup,headRefOid"* ]]; then
  case \$3 in 1) sha=aaa1 ;; 3) sha=ccc1 ;; 6) sha=fff1 ;; *) exit 1 ;; esac
  printf '{"state":"OPEN","autoMergeRequest":{"mergeMethod":"SQUASH"},"mergeStateStatus":"CLEAN","statusCheckRollup":[{"status":"COMPLETED","conclusion":"SUCCESS"}],"headRefOid":"%s"}\n' "\$sha"
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
cat > "$TMP/bin/true-check" <<'STUB'
#!/usr/bin/env bash
exit 0
STUB
chmod +x "$TMP/bin/"*
export PATH="$TMP/bin:$PATH"
export FACTORY_ROOT="$TMP/factory"
export REVERSIBILITY_CHECK_BIN="$TMP/bin/true-check"
export PROTECTED_RIGS_CONFIG_DIR="$REPO_ROOT/tests/fixtures/pr-autopilot-projects"
export GC_OPERATOR_NAME=operator-1
export REVERSIBILITY_CACHE="$TMP/factory/.gc/rev-cache.tsv"
export PR_AUTOPILOT_NOW_EPOCH
PR_AUTOPILOT_NOW_EPOCH=$(date -u -d '2026-10-11T13:00:00Z' +%s)

pilot() { "$AUTOPILOT" "$@" 2>&1 || true; }

# Nothing at all may be done to an outsider's pull request: no call names it.
untouched() {  # num
  grep -qE "^pr [a-z]+ $1 |/(issues|pulls)/$1(/| |$)" "$TMP/gh.log" \
    && { cat "$TMP/gh.log" >&2; fail "PR $1 is an outsider's and gh was called for it"; }
  return 0
}

# --- the list comes from config/operator.toml -------------------------------------
cat > "$TMP/operator.toml" <<'TOML'
name = "operator-1"
github_logins = "example-operator, second-account"
TOML
export OPERATOR_CONFIG_FILE="$TMP/operator.toml"

out=$(pilot)
grep -qE '^pr list .*--json [^ ]*author' "$TMP/gh.log" || fail "the open PR list does not ask for the author"
grep -qE '^pr list .*--json [^ ]*isCrossRepository' "$TMP/gh.log" || fail "the open PR list does not ask whether the branch is a fork's"

grep -q "^pr merge 1 --repo example-corp/example-backend --auto --squash" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "the operator's own PR was not armed"; }
grep -q "^pr merge 6 --repo example-corp/example-backend --auto --squash" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "the PR of the list's second account was not armed"; }
for n in 2 3 4 5; do
  untouched "$n"
  grep -q "PR #$n: fork or outside author -> left to a human" <<<"$out" \
    || { echo "$out" >&2; fail "PR $n: the pass does not say it was left to a human"; }
done
# 5 is red and labelled stuck: no retry, no bead, no label removed.
grep -q '^run ' "$TMP/gh.log" && fail "a workflow run was listed or rerun for an outsider's red PR"
grep -qE '^bd (create|update)' "$TMP/gc.log" && fail "a bead was created or updated for an outsider's PR"
grep -q "armed=2 " <<<"$out" || { echo "$out" >&2; fail "summary does not count exactly the two armed PRs"; }

# --- the environment names the list (what the other tests use) ---------------------
: > "$TMP/gh.log"
out=$(GC_PR_AUTHORS=a-stranger pilot)
grep -q "^pr merge 3 --repo example-corp/example-backend --auto --squash" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "GC_PR_AUTHORS did not name the list"; }
untouched 1; untouched 5

# --- an empty list arms nothing, and says so ---------------------------------------
: > "$TMP/gh.log"
printf 'name = "operator-1"\n' > "$TMP/operator.toml"
out=$(pilot)
grep -q "^pr merge " "$TMP/gh.log" && { echo "$out" >&2; fail "a PR was armed although no account is on the list"; }
grep -q "names no github_logins" <<<"$out" || { echo "$out" >&2; fail "an empty list is not reported"; }
grep -qE 'errors=[1-9]' <<<"$out" || { echo "$out" >&2; fail "an empty list is not counted as an error"; }

# --- the real configuration names at least one account -----------------------------
grep -qE '^github_logins[[:space:]]*=[[:space:]]*"[^"]+"' "$REPO_ROOT/config/operator.toml" \
  || fail "config/operator.toml names no github_logins: pr-autopilot would arm nothing"

echo "PASS: pr-autopilot leaves a fork's or an outside author's PR to a human"
