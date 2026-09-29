#!/usr/bin/env bash
#
# P16 (af-45knz): a ticket-owned PR that goes DIRTY is a real merge conflict,
# and it is measurement input for "dynamic leases" -- pr-autopilot must record
# it (both tickets and their declared scopes, plus the conflict sha) via
# bin/overlap-conflict-log record-conflict, identifying the "other" ticket as
# the most recently closed, merged ticket from the same published graph. This
# drives pr-autopilot against a stub overlap-conflict-log binary and proves:
# a fresh DIRTY rejection (PR #10) records exactly one conflict naming both
# tickets, their declared scopes and the head sha; a required-check-failure
# rejection (PR #20, not a merge conflict) never records anything; and a
# second pass on an already-rejected head (idempotent, no fresh rejection)
# does not record the conflict again.

set -Eeuo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
AUTOPILOT="$REPO_ROOT/bin/pr-autopilot"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

mkdir -p "$TMP/factory/rigs/saymyname-backend" "$TMP/factory/rigs/saymyname-frontend" "$TMP/bin"
: > "$TMP/gh.log"; : > "$TMP/gc.log"; : > "$TMP/escalation.log"; : > "$TMP/overlap.log"

# PR 10: DIRTY, belongs to ticket af-tick1 (branch do-work/af-tick1, ticket id
#   P20, declared scope "a.txt"), never rejected before. The same published
#   graph (gc.graph_digest sha256:same) already closed+merged af-tick0
#   (ticket id P19, declared scope "b.txt") -- the "other" ticket the conflict
#   is measured against.
# PR 20: required check FAILURE (not a merge conflict) -- must never record a
#   conflict even though it is a fresh, ticket-owned rejection.
cat > "$TMP/open.json" <<'JSON'
[
 {"number":10,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"DIRTY","statusCheckRollup":[],"headRefOid":"sha10a","labels":[]},
 {"number":20,"isDraft":false,"autoMergeRequest":null,"mergeStateStatus":"BLOCKED","statusCheckRollup":[{"conclusion":"FAILURE"}],"headRefOid":"sha20a","labels":[]}
]
JSON

cat > "$TMP/all-beads.json" <<'JSON'
[
 {"id":"af-tick1","status":"in_progress","updated_at":"2026-09-29T09:00:00Z",
  "metadata":{"gc.work_branch":"do-work/af-tick1","gc.ticket_id":"P20",
              "gc.graph_digest":"sha256:same","gc.scope_paths":"a.txt"}},
 {"id":"af-tick0","status":"closed","updated_at":"2026-09-28T08:00:00Z",
  "metadata":{"gc.ticket_id":"P19","gc.graph_digest":"sha256:same",
              "gc.scope_paths":"b.txt","merge_result":"merged"}},
 {"id":"af-tick2","status":"in_progress","updated_at":"2026-09-29T09:00:00Z",
  "metadata":{"gc.work_branch":"do-work/af-tick2"}}
]
JSON

cat > "$TMP/bin/gh" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gh.log"
if [[ "\$1" == pr && "\$2" == list ]]; then
  if [[ "\$*" != *"Say-my-name-back"* ]]; then echo '[]'; exit 0; fi
  if [[ "\$*" == *"--state open"* ]]; then cat "$TMP/open.json";
  else echo '[]'; fi
  exit 0
fi
if [[ "\$1" == pr && "\$2" == view && "\$*" == *"--json comments"* ]]; then
  case " \$* " in
    *" 10 "*) [[ "\${COMMENTS_MODE:-first}" == second ]] && echo "pr-autopilot: rejected af-tick1 for sha10a" ;;
    *" 20 "*) echo "pr-autopilot: retried CI once for sha20a" ;;
  esac
  exit 0
fi
if [[ "\$1" == pr && "\$2" == view && "\$*" == *"--json headRefName"* ]]; then
  case " \$* " in
    *" 10 "*) echo "do-work/af-tick1" ;;
    *" 20 "*) echo "do-work/af-tick2" ;;
  esac
  exit 0
fi
if [[ "\$1" == pr && "\$2" == view ]]; then echo '["OPEN","false"]' | jq -r '@tsv'; exit 0; fi
if [[ "\$1" == api ]]; then
  if [[ "\$*" == *"/commits/"* ]]; then echo "deadbeefcafefeed1234567890abcdef12345678"; exit 0; fi
  exit 1
fi
if [[ "\$1" == run && "\$2" == list ]]; then echo ""; exit 0; fi
if [[ "\$1" == pr && "\$2" == comment ]]; then exit 0; fi
if [[ "\$1" == pr && "\$2" == edit ]]; then exit 0; fi
if [[ "\$1" == label && "\$2" == create ]]; then exit 0; fi
exit 0
STUB
cat > "$TMP/bin/gc" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/gc.log"
if [[ "\$1" == bd && "\$2" == list ]]; then
  if [[ "\$*" == *"--all"* ]]; then cat "$TMP/all-beads.json"; else echo '[]'; fi
  exit 0
fi
exit 0
STUB
cat > "$TMP/bin/escalation-door" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/escalation.log"
exit 0
STUB
cat > "$TMP/bin/overlap-conflict-log" <<STUB
#!/usr/bin/env bash
echo "\$*" >> "$TMP/overlap.log"
exit 0
STUB
chmod +x "$TMP/bin/"*
export PATH="$TMP/bin:$PATH"
export FACTORY_ROOT="$TMP/factory"
export REVERSIBILITY_CHECK_BIN="$TMP/bin/gh"
export ESCALATION_DOOR_BIN="$TMP/bin/escalation-door"
export GC_BIN="$TMP/bin/gc"
export OVERLAP_CONFLICT_LOG_BIN="$TMP/bin/overlap-conflict-log"

pilot() { COMMENTS_MODE="$1" "$AUTOPILOT" 2>&1 || true; }

out=$(pilot first)

# PR 10 (DIRTY, fresh rejection): exactly one conflict recorded, naming both
# tickets, their declared scopes and the head sha.
[ "$(wc -l < "$TMP/overlap.log")" = "1" ] \
  || { echo "$out" >&2; cat "$TMP/overlap.log" >&2; fail "expected exactly one overlap-conflict-log call, PR #20's CI failure must never record a conflict"; }
grep -qF "record-conflict --ticket-a P20 --scope-a a.txt --ticket-b P19 --scope-b b.txt --sha sha10a --rig saymyname-app/Say-my-name-back" "$TMP/overlap.log" \
  || { echo "$out" >&2; cat "$TMP/overlap.log" >&2; fail "PR #10's conflict was not recorded with both tickets, their scopes and the sha"; }

# --- second pass: already rejected for this head -> idempotent, no re-record ---
: > "$TMP/overlap.log"; : > "$TMP/gc.log"; : > "$TMP/gh.log"
out=$(pilot second)
[ -s "$TMP/overlap.log" ] \
  && { echo "$out" >&2; fail "an already-rejected head recorded a conflict again"; }

echo "OK pr-autopilot records a fresh DIRTY conflict (both tickets, scopes, sha) via overlap-conflict-log, never records a CI-failure rejection, and is idempotent per head"
