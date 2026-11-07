#!/usr/bin/env bash
#
# A required check failing is not proof the PR is broken -- GitHub's own
# hosted runners occasionally never get past actions/checkout's initial
# fetch (a not-yet-warm TLS cert store, a network blip reaching github.com),
# failing within seconds before a single test runs. This drives
# pr-autopilot against stub gh/gc binaries and proves: the first FAILURE
# seen on a commit triggers exactly one `gh run rerun` plus a marker
# comment and does NOT file a bug bead; a FAILURE reported by the required
# check while its workflow is still running waits for the next pass without
# consuming the retry; a rejected rerun request does the same; a second
# FAILURE on the same commit (marker already posted) is not retried again and
# falls through to the existing flag-as-bug path.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory/rigs/saymyname-backend" "$TMP/factory/rigs/saymyname-frontend" "$TMP/bin"
: > "$TMP/gh.log"; : > "$TMP/gc.log"

# PR 50: first look at a FAILURE on commit aaa1, no retry marker posted yet.
# PR 51: FAILURE on commit bbb2, but bbb2 already carries the retry marker.
# PR 52: the required check is FAILURE on ccc3 while its workflow still runs.
# PR 53: the completed workflow is FAILURE but GitHub refuses the rerun request.
cat > "$TMP/open.json" <<'JSON'
[
 {"number":50,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BLOCKED","statusCheckRollup":[{"conclusion":"FAILURE"}],"headRefOid":"aaa1","labels":[]},
 {"number":51,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BLOCKED","statusCheckRollup":[{"conclusion":"FAILURE"}],"headRefOid":"bbb2","labels":[]},
 {"number":52,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BLOCKED","statusCheckRollup":[{"conclusion":"FAILURE"}],"headRefOid":"ccc3","labels":[]},
 {"number":53,"isCrossRepository":false,"author":{"login":"example-operator"},"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BLOCKED","statusCheckRollup":[{"conclusion":"FAILURE"}],"headRefOid":"ddd4","labels":[]}
]
JSON

cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ "\$1" == pr && "\$2" == list ]]; then
  if [[ "\$*" != *"Say-my-name-back"* ]]; then echo '[]'; exit 0; fi
  if [[ "\$*" == *"--state open"* ]]; then cat "$TMP/open.json";
  elif [[ "\$*" == *"--state merged"* ]]; then echo '[]';
  else echo '[]'; fi
  exit 0
fi
if [[ "\$1" == pr && "\$2" == view && "\$*" == *"--json comments"* ]]; then
  case " \$* " in
    *" 51 "*) echo "pr-autopilot: retried CI once for bbb2" ;;
  esac
  exit 0
fi
if [[ "\$1" == pr && "\$2" == view ]]; then echo '["OPEN","false"]' | jq -r '@tsv'; exit 0; fi
if [[ "\$1" == run && "\$2" == list ]]; then
  case " \$* " in
    *" aaa1 "*) echo "run-50" ;;
    *" ddd4 "*) echo "run-53" ;;
  esac
  exit 0
fi
if [[ "\$1" == run && "\$2" == rerun ]]; then
  [[ "\$3" == run-50 ]]
  exit
fi
if [[ "\$1" == pr && "\$2" == comment ]]; then exit 0; fi
exit 0
STUB
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gc.log"
if [[ "\$1" == bd && "\$2" == list ]]; then echo '[]'; exit 0; fi
exit 0
STUB
chmod +x "$TMP/bin/"*
export PATH="$TMP/bin:$PATH"
export FACTORY_ROOT="$TMP/factory"
export GC_PR_AUTHORS=example-operator
export REVERSIBILITY_CHECK_BIN="$TMP/bin/gh"
export DELIVER_CLOSE_BIN="$TMP/bin/gh"

pilot() { "$AUTOPILOT" "$@" 2>&1 || true; }
out=$(pilot)

# PR 50: retried exactly once, marker posted, no bead filed for it.
grep -q "^run rerun run-50 --repo saymyname-app/Say-my-name-back --failed$" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #50 was not retried"; }
grep -q "^pr comment 50 --repo saymyname-app/Say-my-name-back --body pr-autopilot: retried CI once for aaa1$" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #50's retry marker comment was not posted"; }
grep -q "PR #50 failed" "$TMP/gc.log" \
  && { echo "$out" >&2; fail "PR #50 was flagged as a bug on its first (retried) failure"; }

# PR 51: marker already present for commit bbb2 -> no second retry, flag as before.
[ "$(grep -c '^run rerun run-50 ' "$TMP/gh.log")" = "1" ] \
  || { echo "$out" >&2; fail "PR #50 was not retried exactly once"; }
grep -q -- '--commit bbb2' "$TMP/gh.log" \
  && { echo "$out" >&2; fail "PR #51 looked up a run despite its existing retry marker"; }
grep -q "bd create \[ci\] PR #51 failed required checks on dev" "$TMP/gc.log" \
  || { echo "$out" >&2; fail "PR #51 (already retried once) was not flagged"; }

# PR 52: the required check can turn red before the workflow completes. Its
# active run is neither rerun nor treated as proof that the retry was spent.
grep -q "^run rerun run-52 " "$TMP/gh.log" \
  && { echo "$out" >&2; fail "PR #52's still-running workflow was sent a rerun request"; }
grep -q "^pr comment 52 .*retried CI once" "$TMP/gh.log" \
  && { echo "$out" >&2; fail "PR #52's still-running workflow consumed the retry marker"; }
grep -q "PR #52 failed" "$TMP/gc.log" \
  && { echo "$out" >&2; fail "PR #52 was flagged before its workflow completed"; }

# PR 53: a rejected rerun request is not a retry. There is no marker or
# terminal signal; the next pass may try again once GitHub accepts it.
grep -q "^run rerun run-53 " "$TMP/gh.log" \
  || { echo "$out" >&2; fail "PR #53's completed failed workflow was not offered its retry"; }
grep -q "^pr comment 53 .*retried CI once" "$TMP/gh.log" \
  && { echo "$out" >&2; fail "PR #53's rejected rerun request consumed the retry marker"; }
grep -q "PR #53 failed" "$TMP/gc.log" \
  && { echo "$out" >&2; fail "PR #53 was flagged although its rerun request was rejected"; }

echo "OK pr-autopilot retries a required-check failure once per commit before flagging"
