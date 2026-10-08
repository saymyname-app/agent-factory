#!/usr/bin/env bash
#
# bin/ci-minutes (af-mzuprx): billed minutes are each job's duration rounded
# up to the minute, a job that never got a runner is billed nothing, and the
# day is the Europe/Paris day. Proven against a fake `gh` that answers two
# runs: no network, no token.

set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
TMP=$(mktemp -d)
trap 'rm -rf -- "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

cat >"$TMP/gh" <<'FAKE'
#!/usr/bin/env bash
case "$2" in
  *"/actions/runs?"*)
    # 22:30 UTC on the 6th is 00:30 on the 7th in Paris.
    echo '{"workflow_runs":[
      {"id":1,"event":"pull_request","conclusion":"success","created_at":"2026-10-06T22:30:00Z","head_branch":"maint/a"},
      {"id":2,"event":"pull_request","conclusion":"failure","created_at":"2026-10-07T09:00:00Z","head_branch":"maint/b"},
      {"id":3,"event":"pull_request","conclusion":"success","created_at":"2026-10-07T10:00:00Z","head_branch":"maint/c"}]}' ;;
  *"/runs/1/jobs"*)
    echo '{"jobs":[
      {"name":"Tests","run_attempt":1,"started_at":"2026-10-06T22:30:00Z","completed_at":"2026-10-06T22:40:01Z","steps":[{"conclusion":"success"}]},
      {"name":"Lot 2","run_attempt":1,"started_at":"2026-10-06T22:30:00Z","completed_at":"2026-10-06T22:33:00Z","steps":[{"conclusion":"success"}]}]}' ;;
  *"/runs/2/jobs"*)
    echo '{"jobs":[
      {"name":"Tests","run_attempt":1,"started_at":"2026-10-07T09:00:00Z","completed_at":"2026-10-07T09:00:05Z","steps":[]}]}' ;;
  *"/runs/3/jobs"*)
    # The host's own runner (af-r1ymfm): 15 min 23 s that GitHub does not bill.
    echo '{"jobs":[
      {"name":"Tests","run_attempt":1,"runner_group_name":"Default","started_at":"2026-10-07T10:00:00Z","completed_at":"2026-10-07T10:15:23Z","steps":[{"conclusion":"success"}]}]}' ;;
  *) echo "unexpected: $*" >&2; exit 1 ;;
esac
FAKE
chmod +x "$TMP/gh"

out=$(GH_BIN="$TMP/gh" "$ROOT/bin/ci-minutes" --since 2026-10-06) || fail "ci-minutes failed: $out"
grep -Eq '^2026-10-07 +3 +14 +14 +0 +0 +0 +16$' <<<"$out" \
  || { echo "$out" >&2; fail "expected one Paris day, 3 runs, 11 + 3 = 14 billed minutes, none for the job that never started, none for the 16 minutes on the host"; }
grep -Fq 'Tests=0  (on the host: 16 min, not billed)' <<<"$out" || { echo "$out" >&2; fail "a job on a self-hosted runner must be billed 0 and its duration shown apart"; }
grep -Fq 'Tests=11' <<<"$out" || { echo "$out" >&2; fail "10 min 01 s must be billed 11 minutes"; }
grep -Fq '2026-10-07 00:30' <<<"$out" || { echo "$out" >&2; fail "times must be Europe/Paris"; }
if grep -q '^2026-10-06 ' <<<"$out"; then echo "$out" >&2; fail "a run was counted on its UTC day"; fi

printf 'PASS: ci-minutes rounds each job up, bills nothing for a job that never started or ran on the host, counts by Paris day\n'
