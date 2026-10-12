#!/usr/bin/env bash
#
# af-31t0y8: pr-autopilot used to bring one BEHIND PR up to date per tick
# (3 minutes), whoever was already up to date. With one CI job at a time and
# a run of 14 to 45 minutes, ten PRs put ten runs in the queue, one merged,
# and its merge made the nine other runs stale (2026-10-11: 40 runs for 9
# merges). This drives pr-autopilot against a queue of BEHIND PRs on
# agent-factory and proves there is one queue head at a time:
#  1. ten BEHIND PRs: one tick updates the oldest only;
#  2. while that head is up to date with its required check waiting, running,
#     or green and armed, no other PR is updated, tick after tick;
#  3. once the head has merged, the next oldest is updated, alone;
#  4. a head whose required check is red is retried once and still holds the
#     queue during that retry; red again, it is flagged and the next BEHIND
#     PR is updated on that same tick;
#  5. a head in conflict (DIRTY) does not hold the queue;
#  6. a PR marked stuck (blocked with nothing pending) does not hold the queue;
#  7. among BEHIND PRs, one whose last required run is red is taken only when
#     no other waits, whatever its age;
#  8. a PR up to date whose run has only just been asked for (no check
#     reported yet) holds the queue.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory" "$TMP/bin"
: > "$TMP/gh.log"; : > "$TMP/gc.log"; : > "$TMP/comments.txt"

# prs <number>:<mergeStateStatus>:<Tests>[:armed][:stuck] ... -> the open PR
# fixture. <Tests> is SUCCESS, FAILURE, RUNNING or NONE.
prs() {
  python3 - "$TMP/af_open.json" "$@" <<'PY'
import json, sys
out = []
for spec in sys.argv[2:]:
    num, state, tests, *flags = spec.split(":")
    roll = {"SUCCESS": [{"name": "Tests", "conclusion": "SUCCESS"}],
            "FAILURE": [{"name": "Tests", "conclusion": "FAILURE"}],
            "RUNNING": [{"name": "Tests", "status": "IN_PROGRESS"}],
            "NONE": []}[tests]
    out.append({"number": int(num), "isCrossRepository": False,
                "author": {"login": "example-operator"}, "isDraft": False,
                "autoMergeRequest": {"mergeMethod": "SQUASH"} if "armed" in flags else None,
                "mergeStateStatus": state, "statusCheckRollup": roll,
                "headRefOid": "sha%s" % num,
                "labels": [{"name": "autopilot-stuck"}] if "stuck" in flags else []})
with open(sys.argv[1], "w") as f:
    json.dump(out, f)
PY
}

# gh stub: `api -X PUT .../pulls/<num>/update-branch` makes that PR up to date
# with its required run started (BLOCKED, Tests in progress), as GitHub does.
# `pr view --json comments` prints $TMP/comments.txt (the retry marker lives
# in a PR comment); `run list --commit` prints $RETRY_RUN, the failed run to
# rerun, when set.
cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ \$1 == api && \$2 == -X && \$3 == PUT && \$4 == repos/*/pulls/*/update-branch ]]; then
  num=\${4%/update-branch}; num=\${num##*/}
  python3 - "$TMP/af_open.json" "\$num" <<'PY'
import json, sys
path, num = sys.argv[1], int(sys.argv[2])
with open(path) as f:
    prs = json.load(f)
for pr in prs:
    if pr["number"] == num:
        pr["mergeStateStatus"] = "BLOCKED"
        pr["statusCheckRollup"] = [{"name": "Tests", "status": "IN_PROGRESS"}]
with open(path, "w") as f:
    json.dump(prs, f)
PY
  echo '{"message":"Updating pull request branch.","url":"x"}'
  exit 0
fi
if [[ \$1 == api ]] && [[ "\$*" == *"rules/branches"* ]]; then
  case "\$*" in
    *"saymyname-app/agent-factory"*) echo '["Tests"]' ;;
    *)                                echo '[]' ;;
  esac
  exit 0
fi
if [[ \$1 == pr && \$2 == list ]]; then
  if [[ "\$*" == *"--state merged"* ]]; then echo '[]'; exit 0; fi
  case "\$*" in
    *"saymyname-app/agent-factory"*) cat "$TMP/af_open.json" ;;
    *)                                echo '[]' ;;
  esac
  exit 0
fi
if [[ \$1 == pr && \$2 == view ]]; then
  if [[ "\$*" == *"--json comments"* ]]; then cat "$TMP/comments.txt"; exit 0; fi
  echo '["OPEN","false"]' | jq -r '@tsv'; exit 0
fi
if [[ \$1 == run && \$2 == list ]]; then echo "\${RETRY_RUN:-}"; exit 0; fi
exit 0
STUB
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gc.log"
if [[ \$1 == bd && \$2 == list ]]; then echo '[]'; exit 0; fi
exit 0
STUB
chmod +x "$TMP/bin/"*
export PATH="$TMP/bin:$PATH"
export FACTORY_ROOT="$TMP/factory"
export GC_PR_AUTHORS=example-operator
export REVERSIBILITY_CHECK_BIN="$TMP/bin/gh"

out=""
tick() { : > "$TMP/gh.log"; : > "$TMP/gc.log"; out=$("$AUTOPILOT" "$@" 2>&1 || true); }
updated() { grep -o 'pulls/[0-9]*/update-branch' "$TMP/gh.log" | grep -o '[0-9]\+' | tr '\n' ' ' | sed 's/ $//' || true; }
expect_updated() {  # "<numbers>" "<what the tick proves>"
  local got; got=$(updated)
  [ "$got" = "$1" ] || { echo "$out" >&2; fail "$2: updated [$got], expected [$1]"; }
}

# --- 1. ten BEHIND PRs: the oldest only ---
prs 101:BEHIND:SUCCESS 102:BEHIND:SUCCESS 103:BEHIND:SUCCESS 104:BEHIND:SUCCESS 105:BEHIND:SUCCESS \
    106:BEHIND:SUCCESS 107:BEHIND:SUCCESS 108:BEHIND:SUCCESS 109:BEHIND:SUCCESS 110:BEHIND:SUCCESS
tick
expect_updated "101" "ten BEHIND PRs, no head"

# --- 2. the head holds the queue: required run in progress (set by the stub) ---
tick -v
expect_updated "" "head #101 up to date, required run in progress"
grep -q "^pr merge 101 --repo saymyname-app/agent-factory --auto --squash" "$TMP/gh.log" \
  || { echo "$out" >&2; fail "head #101 (up to date) was not armed"; }
printf '%s\n' "$out" | grep -qF "PR #101 holds the queue -- 9 BEHIND PR(s) waiting" \
  || { echo "$out" >&2; fail "the waiting PRs were not reported behind head #101"; }
tick
expect_updated "" "head #101 still running on a third tick"

# ... armed with its run in progress, then green and armed, about to merge.
prs 101:BLOCKED:RUNNING:armed 102:BEHIND:SUCCESS 103:BEHIND:SUCCESS
tick
expect_updated "" "head #101 armed, required run in progress"
prs 101:CLEAN:SUCCESS:armed 102:BEHIND:SUCCESS 103:BEHIND:SUCCESS
tick
expect_updated "" "head #101 green and armed, not merged yet"

# --- 3. the head merged: the next oldest, alone ---
prs 102:BEHIND:SUCCESS 103:BEHIND:SUCCESS
tick
expect_updated "102" "head #101 merged"
tick
expect_updated "" "new head #102 running"

# --- 4. the head goes red: one retry, during which it still holds the queue ---
prs 102:BLOCKED:FAILURE:armed 103:BEHIND:SUCCESS 104:BEHIND:SUCCESS
export RETRY_RUN=777
tick
grep -q "^run rerun 777 " "$TMP/gh.log" || { echo "$out" >&2; fail "red head #102 was not retried once"; }
expect_updated "" "red head #102 being retried"
# Red again on the same head (the retry marker is on the PR): flagged, and the
# next BEHIND PR takes over on this tick.
echo "pr-autopilot: retried CI once for sha102" > "$TMP/comments.txt"
unset RETRY_RUN
tick
grep -qF "bd create [ci] PR #102 failed required checks" "$TMP/gc.log" \
  || { echo "$out" >&2; cat "$TMP/gc.log" >&2; fail "red head #102 was not flagged after its retry"; }
expect_updated "103" "head #102 red after its retry"
: > "$TMP/comments.txt"
tick
expect_updated "" "new head #103 running, #102 still red"

# --- 5. a head in conflict does not hold the queue ---
prs 120:DIRTY:SUCCESS:armed 121:BEHIND:SUCCESS 122:BEHIND:SUCCESS
tick
expect_updated "121" "head #120 in conflict"

# --- 6. a PR marked stuck does not hold the queue ---
prs 130:BLOCKED:SUCCESS:armed:stuck 131:BEHIND:SUCCESS
tick
expect_updated "131" "PR #130 blocked with nothing pending, marked stuck"

# --- 7. a red BEHIND PR is taken only when no other waits ---
prs 140:BEHIND:FAILURE 141:BEHIND:SUCCESS 142:BEHIND:SUCCESS
tick
expect_updated "141" "oldest BEHIND PR #140 red, #141 not red"
grep -q "^bd create" "$TMP/gc.log" && { echo "$out" >&2; fail "a BEHIND PR was flagged for the red of a head about to be replaced"; }
prs 140:BEHIND:FAILURE
tick
expect_updated "140" "red BEHIND PR #140 alone"

# --- 8. up to date, run only just asked for: it holds the queue ---
prs 150:BLOCKED:NONE:armed 151:BEHIND:SUCCESS
tick
expect_updated "" "head #150 up to date, no check reported yet"

grep -q "^pr update-branch" "$TMP/gh.log" && fail "pr-autopilot called 'gh pr update-branch' (absent from gh 2.45)"

if grep -q -- "--delete-branch" "$TMP/gh.log"; then
  fail "merge request must not delete a branch before GitHub confirms merge"
fi

echo "OK pr-autopilot keeps one queue head: a BEHIND PR is updated only when no PR is up to date with its required check waiting, running or green"
