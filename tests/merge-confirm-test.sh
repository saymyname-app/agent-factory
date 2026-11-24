#!/usr/bin/env bash
# merge-confirm-test.sh — table test of merge_and_confirm (lib/merge_confirm.sh),
# the passage point of rule S.merge-confirmed (af-56yoam.6): a PR state is
# announced only once read back on GitHub. Each row gives the request's exit,
# what GitHub reads after it, and the state and return code expected; a fake
# gh on PATH logs every call, so a row also proves a read happened or not.
set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/bin"
cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
case "\$1 \$2" in
  "pr view"|"run view") [ -n "\$FAKE_VIEW" ] && printf '%s\n' "\$FAKE_VIEW"; exit "\$FAKE_VIEW_RC" ;;
  *) exit "\$FAKE_REQ_RC" ;;
esac
STUB
chmod +x "$TMP/bin/gh"
export PATH="$TMP/bin:$PATH"
# shellcheck source=lib/merge_confirm.sh
. "$REPO_ROOT/lib/merge_confirm.sh"

OPEN='{"state":"OPEN","autoMergeRequest":null,"mergeStateStatus":"BLOCKED","headRefOid":"abc"}'
ARMED='{"state":"OPEN","autoMergeRequest":{"mergeMethod":"SQUASH"},"mergeStateStatus":"BLOCKED","headRefOid":"abc"}'
MERGED='{"state":"MERGED","autoMergeRequest":null}'

# name | action args | request exit | read exit | read JSON | state | rc | reads
while IFS='|' read -r name args req_rc view_rc view want_state want_rc want_reads; do
  [ -n "$name" ] || continue
  : > "$TMP/gh.log"
  export FAKE_REQ_RC=$req_rc FAKE_VIEW_RC=$view_rc FAKE_VIEW=${view//\$OPEN/$OPEN}
  FAKE_VIEW=${FAKE_VIEW//\$ARMED/$ARMED}; FAKE_VIEW=${FAKE_VIEW//\$MERGED/$MERGED}
  # shellcheck disable=SC2086
  merge_and_confirm $args && rc=0 || rc=$?
  reads=$(grep -cE '^(pr|run) view ' "$TMP/gh.log" || true)
  [ "$MERGE_CONFIRMED_STATE" = "$want_state" ] \
    || fail "$name: state '$MERGE_CONFIRMED_STATE', expected '$want_state'"
  [ "$rc" = "$want_rc" ] || fail "$name: returned $rc, expected $want_rc"
  [ "$reads" = "$want_reads" ] || fail "$name: GitHub read $reads time(s), expected $want_reads"
done <<'TABLE'
merge accepted, PR still in the queue: not merged|merge o/r 7 abc|0|0|$OPEN|queued|1|1
merge read back MERGED: merged|merge o/r 7 abc|0|0|$MERGED|merged|0|1
merge exit 1 but GitHub reads MERGED: merged|merge o/r 7 abc|1|0|$MERGED|merged|0|1
merge refused, PR open: not merged|merge o/r 7 abc|1|0|$OPEN|open|1|1
merge accepted, GitHub read fails: unknown|merge o/r 7 abc|0|1||unknown|2|1
merge accepted, GitHub answers garbage: unknown|merge o/r 7 abc|0|0|OPEN|unknown|2|1
merge request cut, PR still open: unknown|merge o/r 7 abc|124|0|$OPEN|unknown|2|1
arm accepted, no autoMergeRequest: not armed|arm o/r 7|0|0|$OPEN|open|1|1
arm read back armed: armed|arm o/r 7|0|0|$ARMED|armed|0|1
arm accepted, GitHub read fails: unknown|arm o/r 7|0|1||unknown|2|1
arm request cut: unknown, no read|arm o/r 7|124|0|$ARMED|unknown|2|0
disarm read back without request: disarmed|disarm o/r 7|0|0|$OPEN|disarmed|0|1
disarm accepted, still armed: not disarmed|disarm o/r 7|0|0|$ARMED|armed|1|1
rerun read back queued: rerun|rerun o/r 99|0|0|{"status":"queued","conclusion":""}|rerun|0|1
rerun accepted, run still completed: not rerun|rerun o/r 99|0|0|{"status":"completed","conclusion":"failure"}|completed|1|1
rerun refused: not rerun, no read|rerun o/r 99|1|0||completed|1|0
rerun accepted, GitHub read fails: unknown|rerun o/r 99|0|1||unknown|2|1
TABLE

# The merge request pins the head it was given; the read is of the same PR.
: > "$TMP/gh.log"; FAKE_REQ_RC=0 FAKE_VIEW_RC=0 FAKE_VIEW=$MERGED merge_and_confirm merge o/r 7 abc || true
grep -qx "pr merge 7 --repo o/r --squash --match-head-commit abc" "$TMP/gh.log" \
  || fail "the merge request did not pin the head: $(cat "$TMP/gh.log")"
grep -q "^pr view 7 --repo o/r --json state," "$TMP/gh.log" || fail "the merge was not read back on PR 7"

echo "PASS: merge_and_confirm announces only the state GitHub reads back"
